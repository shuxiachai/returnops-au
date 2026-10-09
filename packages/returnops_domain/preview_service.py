"""Private synchronous preview acceptance, without a queue or public route."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from . import customer_tables as old, lifecycle_tables as t, preview_profile as policy
from .preview_tables import previews
from .audit import append_event, identifier, timestamp
from .canonical import digest, encode_document
from . import founder_codec as finite
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .lifecycle_state import current, reject, MAX_VERSION
from .manual_target import one
from .preview_sources import (authorize, source_target, accepted_preview, payload,
    request_fingerprint, current_policy, EMPTY)
from .wire import validate


@dataclass(frozen=True, repr=False)
class PreviewResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class PreviewService:
    def __init__(self, engine, *, clock=lambda:datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork, recovery_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine, self.clock = engine, clock
        self.uow_factory, self.recovery_uow, self.audit_uow = uow_factory, recovery_uow, audit_uow

    def _same(self, uow, head, grant):
        h, g = authorize(uow, head['case_id'])
        if (h['store_id'] != head['store_id'] or h['owner_principal_id'] != head['owner_principal_id']
                or dict(g) != dict(grant)):
            reject(uow, 'FORBIDDEN')
        return h

    @staticmethod
    def _lookup(uow, head, expected, key):
        validate('Version', expected); validate('IdempotencyKey', key)
        row = uow.execute(select(previews).where(previews.c.component_id == policy.COMPONENT,
            previews.c.store_id == head['store_id'], previews.c.case_id == head['case_id'],
            previews.c.request_key == key)).mappings().one_or_none()
        if row is not None and (row['owner_id'] != head['owner_principal_id']
                or row['request_fingerprint'] != request_fingerprint(expected)):
            reject(uow, 'IDEMPOTENCY_CONFLICT')
        return None if row is None else dict(row)

    @staticmethod
    def _receipt(seal):
        row = seal['row']
        return dict(case_id=row['case_id'], case_version=row['post_case_version'],
                    accepted_at=timestamp(row['issued_at']), action_preview=seal['body'])

    def _replay(self, uow, head, grant, row):
        seal = accepted_preview(uow, head, row['preview_id'])
        def check():
            h = self._same(uow, head, grant)
            if accepted_preview(uow, h, row['preview_id']) != seal:
                reject(uow)
            self._same(uow, head, grant)
            if one(uow, previews, preview_id=row['preview_id']) != seal['row']:
                reject(uow)
        uow.before_commit(check)
        return self._receipt(seal)

    def _new(self, uow, head, grant, expected, key, correlation):
        if head['case_version'] != expected:
            reject(uow, 'STALE_CASE_VERSION')
        state = current(uow, head)
        if (state is None or head['status'] != 'AWAITING_APPROVAL' or expected >= MAX_VERSION
                or any(state[name] is not None for name in EMPTY)):
            reject(uow)
        review, previous = source_target(uow, head, state, expected_version=expected)
        now = self.clock()
        if (now.utcoffset() is None or now < review['event']['accepted_at']
                or previous is not None and now < previous['row']['expires_at']):
            reject(uow)
        profile = policy.profile()
        preview_id = identifier('preview')
        body = policy.build(preview_id, review['proposal']['body'], review['body']['review'], now, profile)
        row = dict(preview_id=preview_id, case_id=head['case_id'], component_id=policy.COMPONENT,
            store_id=head['store_id'], owner_id=head['owner_principal_id'], input_version=head['input_version'],
            generation=state['generation'], proposal_record_id=review['proposal']['record']['record_id'],
            proposal_hash=review['proposal']['record']['content_sha256'], review_record_id=review['record']['record_id'],
            review_hash=review['record']['content_sha256'], review_event_id=review['event']['event_id'],
            review_event_hash=review['event']['fingerprint'], order_projection_id=review['proposal']['binding']['order_projection_id'],
            order_hash=finite.digest(review['proposal']['body']['order_lookup']), profile_version=profile['version'],
            profile_hash=policy.profile_hash(profile), authority_revision=grant['revision'],
            pre_case_version=expected, post_case_version=expected+1,
            previous_preview_id=None if previous is None else previous['row']['preview_id'], issued_at=now,
            expires_at=now+timedelta(seconds=profile['ttl_seconds']), body_hash=digest(body, 'action-preview-body/v1'),
            body=encode_document(body), available=True, removal_reason=None,
            request_key=key, request_fingerprint=request_fingerprint(expected),
            consuming_decision_record_id=None, consumed_at=None)
        changed = uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id'],
            old.case_heads.c.case_version == expected).values(case_version=expected+1, updated_at=now))
        if changed.rowcount != 1:
            reject(uow, 'STALE_CASE_VERSION')
        audit = append_event(uow, head['case_id'], actor={'kind':'SERVICE','component_id':policy.COMPONENT},
            event_type='ACTION_PREVIEW_ACCEPTED', correlation_id=correlation, payload=payload(row),
            object_ids=[preview_id], history_refs=[], now=now)
        row.update(audit_event_id=audit['event_id'], audit_hash=audit['event_hash'])
        uow.execute(previews.insert().values(**row))
        uow.execute(update(t.state).where(t.state.c.case_id == head['case_id']).values(preview_id=preview_id))
        accepted_head = one(uow, old.case_heads, case_id=head['case_id'])
        seal = accepted_preview(uow, accepted_head, preview_id)
        saved_state = dict(current(uow, accepted_head))
        def check():
            h = self._same(uow, head, grant)
            s = current(uow, h)
            r, p = source_target(uow, h, s, expected_version=expected+1)
            if r != review or p != seal:
                reject(uow)
            current_policy(uow, h, seal['row'])
            h = self._same(uow, head, grant)
            if (h['status'] != 'AWAITING_APPROVAL' or h['case_version'] != expected+1
                    or h['input_version'] != head['input_version'] or dict(current(uow, h)) != saved_state
                    or one(uow, previews, preview_id=preview_id) != seal['row']
                    or self.clock() >= row['expires_at']):
                reject(uow)
        uow.before_commit(check)
        return self._receipt(seal)

    def accept(self, case_id, expected_case_version, original_key, correlation_id):
        uow = None; committed = False; code = 'INTERNAL_ERROR'
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                validate('Id', case_id)
                head, grant = authorize(uow, case_id)
                validate('Id', correlation_id)
                row = self._lookup(uow, head, expected_case_version, original_key)
                receipt = (self._replay(uow, head, grant, row) if row is not None else
                    self._new(uow, head, grant, expected_case_version, original_key, correlation_id))
                uow.commit(); committed = True
            return PreviewResult('ACCEPTED', receipt)
        except AcceptanceOutcomeUnknown:
            return PreviewResult('UNKNOWN')
        except FlowError as error:
            code = error.code
        except Exception:
            pass
        if committed or uow is not None and uow.connection is not None and not uow.connection.closed:
            return PreviewResult('UNKNOWN')
        return PreviewResult('DENIED', safe_code=code, audit=self._denial(case_id, code))

    def recover(self, case_id, expected_case_version, original_key):
        try:
            with self.recovery_uow(self.engine, write=True) as uow:
                validate('Id', case_id)
                head, grant = authorize(uow, case_id)
                row = self._lookup(uow, head, expected_case_version, original_key)
                if row is None:
                    uow.before_commit(lambda:self._same(uow, head, grant)); uow.commit()
                    return PreviewResult('UNKNOWN')
                receipt = self._replay(uow, head, grant, row); uow.commit()
            return PreviewResult('ACCEPTED', receipt)
        except FlowError as error:
            return PreviewResult('UNKNOWN', safe_code=error.code)
        except Exception:
            return PreviewResult('UNKNOWN')

    def _denial(self, case_id, code):
        from .reject_denial import DENIAL_CODES
        if code not in DENIAL_CODES:
            return 'NOT_RECORDED'
        committed = False
        try:
            with self.audit_uow(self.engine, write=True) as uow:
                head, grant = authorize(uow, case_id)
                state = current(uow, head)
                if state is not None and not state['available']:
                    reject(uow)
                def check():
                    h = self._same(uow, head, grant)
                    s = current(uow, h)
                    if s is not None and not s['available']:
                        reject(uow)
                uow.before_commit(check)
                append_event(uow, case_id, actor={'kind':'SERVICE','component_id':policy.COMPONENT},
                    event_type='ACTION_PREVIEW_DENIED', correlation_id=identifier('denial_corr'),
                    payload={'purpose':'PREVIEW','reason':code}, object_ids=[], history_refs=[], now=self.clock())
                uow.commit(); committed = True
            return 'RECORDED'
        except AcceptanceOutcomeUnknown:
            return 'UNKNOWN'
        except Exception:
            return 'UNKNOWN' if committed else 'NOT_RECORDED'
