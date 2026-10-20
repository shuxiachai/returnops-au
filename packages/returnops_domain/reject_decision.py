"""Private HUMAN REJECT acceptance, ending at unclaimed NOTIFICATION_PENDING.

No public route, grant provisioning, approval, return/label or notification
dispatch. UNKNOWN never retries or records a denial; recovery reads only.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from sqlalchemy import select, update
from . import customer_tables as old, founder_tables as finite_tables, lifecycle_tables as t
from . import founder_codec as finite, idempotency
from .audit import append_event, identifier, timestamp
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .lifecycle_events import OutcomeAccepted
from .lifecycle_guards import LifecycleGuards
from .lifecycle_schema import version, APPROVAL_VERSIONS, NOTIFICATION
from .lifecycle_state import current, installed, reject
from .manual_target import one
from .reject_denial import COMPONENT, OPERATION, authorize, record_denial
from .reject_sources import read_target, accepted_reject, check_seal, MESSAGE
from .wire import validate


@dataclass(frozen=True, repr=False)
class RejectResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class FounderRejectService:
    def __init__(self, engine, authority, *, clock=lambda: datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork, recovery_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.uow_factory, self.recovery_uow, self.audit_uow = uow_factory, recovery_uow, audit_uow
        self.guard = LifecycleGuards(COMPONENT, clock=clock)

    @staticmethod
    def _request(request):
        value = validate('FounderDecisionRequest', request)
        if value['decision'] != 'REJECT' or 'proposal_id' not in value:
            raise FlowError('INVALID_STATE')
        return value

    def _lookup(self, uow, actor, head, request, key):
        fingerprint = digest(request, 'founder-reject-request/v1')

        def check(fact):
            if (fact['resource_kind'] != 'CASE' or fact['resource_id'] != head['case_id']
                    or fact['store_id'] != actor.store_id):
                reject(uow, 'FORBIDDEN')

        return idempotency.lookup(uow, actor, OPERATION, head['case_id'], key, fingerprint,
            check_resource=check), fingerprint

    def _same_authority(self, uow, actor, head, grant):
        a, h, g = authorize(uow, self.authority, head['case_id'])
        if (a != actor or h['owner_principal_id'] != head['owner_principal_id']
                or h['store_id'] != head['store_id'] or dict(g) != dict(grant)):
            reject(uow, 'FORBIDDEN')
        return h

    def _replay(self, uow, fact, actor, head, grant, request):
        _, receipt = idempotency.original_receipt(uow, fact)
        validate('DecisionReceipt', receipt, internal=True)
        source = uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
            old.history.c.kind == 'DECISION', old.history.c.object_id == receipt['decision_id'])).mappings().one_or_none()
        if source is None:
            reject(uow)
        seal = accepted_reject(uow, head, source['record_id'], COMPONENT)
        if (receipt['case_id'] != head['case_id'] or receipt['decision'] != 'REJECT'
                or receipt['case_version'] != seal['event']['case_version']
                or receipt['decision_id'] != seal['body']['decision_id']
                or seal['body']['principal_id'] != actor.principal_id
                or any(seal['body'][k] != request[k] for k in ('decision', 'proposal_id', 'proposal_version', 'reason'))
                or seal['event']['pre_case_version'] != request['expected_case_version']
                or receipt['accepted_at'] != timestamp(fact['accepted_at'])
                or seal['event']['accepted_at'] != fact['accepted_at']):
            reject(uow)
        original_receipt = one(uow, old.receipts, acceptance_id=fact['acceptance_id'])

        def check():
            h = self._same_authority(uow, actor, head, grant)
            if accepted_reject(uow, h, source['record_id'], COMPONENT) != seal:
                reject(uow)
            self._same_authority(uow, actor, head, grant)
            check_seal(uow, seal)
            if (one(uow, old.acceptances, acceptance_id=fact['acceptance_id']) != fact
                    or one(uow, old.receipts, acceptance_id=fact['acceptance_id']) != original_receipt
                    or version(uow.connection) not in APPROVAL_VERSIONS):
                reject(uow)

        uow.before_commit(check)
        return receipt

    @staticmethod
    def _append(uow, case_id, kind, body, actor, correlation, now, *, payload=None):
        finite.validate('FounderDecisionRecord' if kind == 'DECISION' else 'NotificationRecord', body)
        head = one(uow, old.case_heads, case_id=case_id)
        record_id = identifier('reject_source')
        object_id = body['decision_id' if kind == 'DECISION' else 'notification_id']
        ref = dict(record_id=record_id, kind=kind, object_id=object_id, object_version=1)
        source_hash = finite.digest(body)
        uow.execute(old.history.insert().values(**ref, case_id=case_id, case_version=head['case_version'],
            recorded_sequence=head['history_sequence'] + 1, recorded_at=now,
            content_sha256=source_hash, retention_state='AVAILABLE', removal_reason=None))
        uow.execute(old.history_contents.insert().values(record_id=record_id, body=finite.encode_document(body)))
        uow.execute(finite_tables.encodings.insert().values(record_id=record_id, profile=finite.PROFILE,
            source_content_sha256=source_hash, projected_content_sha256=source_hash, receipt_id=None))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case_id).values(
            history_sequence=head['history_sequence'] + 1))
        append_event(uow, case_id, actor=actor,
            event_type='FOUNDER_DECISION_ACCEPTED' if kind == 'DECISION' else 'NOTIFICATION_REVISION_RECORDED',
            correlation_id=correlation, payload={'private_reject':True} if payload is None else payload,
            object_ids=[object_id], history_refs=[ref], now=now)
        return record_id, source_hash

    def _new(self, uow, actor, head, grant, request, key, fingerprint, correlation):
        if not installed(uow) or version(uow.connection) not in APPROVAL_VERSIONS:
            reject(uow)
        if head['case_version'] != request['expected_case_version']:
            reject(uow, 'STALE_CASE_VERSION')
        state = current(uow, head)
        if state is None:
            reject(uow)
        original_state = dict(state)
        source = read_target(uow, head, state, request, COMPONENT)
        from .preview_sources import accepted_preview, consume_payload, consume
        preview = None if state['preview_id'] is None else accepted_preview(uow, head, state['preview_id'])
        payload = None if preview is None else consume_payload(preview['row'])
        now = self.clock()
        if now.utcoffset() is None:
            reject(uow)
        work_id = self.guard.prepare(uow, head['case_id'], head['case_version'], OutcomeAccepted, now)
        claim = self.guard.claim(uow, work_id, now)
        if claim is None:
            reject(uow)
        original_lease = one(uow, t.work, work_id=work_id)['lease_expires_at']
        decision = dict(decision_id=identifier('reject_decision'), case_id=head['case_id'],
            decision='REJECT', principal_id=actor.principal_id, reason=request['reason'],
            decided_at=timestamp(now), **{k:request[k] for k in ('proposal_id', 'proposal_version')})
        decision_id, decision_hash = self._append(uow, head['case_id'], 'DECISION', decision,
            {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':actor.principal_id}, correlation, now, payload=payload)
        uow.execute(t.sources.insert().values(record_id=decision_id, case_id=head['case_id'],
            **asdict(claim), source_hash=decision_hash, target_record_id=source['record']['record_id'], slot='PRIMARY'))
        from .notification_intent import initial_format, initial_payload
        note_payload = (initial_payload(COMPONENT, 'REJECTED', decision_id, decision_hash)
                        if version(uow.connection) == NOTIFICATION else payload)
        note = dict(notification_id=identifier('reject_notification'), case_id=head['case_id'],
            case_version=head['case_version'], status='PENDING', outcome='REJECTED',
            **initial_format(uow, 'REJECTED', MESSAGE), attempt_count=0, updated_at=timestamp(now))
        note_id, note_hash = self._append(uow, head['case_id'], 'NOTIFICATION', note,
            {'kind':'SERVICE', 'component_id':COMPONENT}, correlation, now, payload=note_payload)
        uow.execute(t.sources.insert().values(record_id=note_id, case_id=head['case_id'], **asdict(claim),
            source_hash=note_hash, target_record_id=decision_id, slot='NOTIFICATION'))
        if preview is not None:
            consume(uow, preview, decision_id, now)
        event = self.guard.apply(uow, OutcomeAccepted(identifier('reject_event'), claim, decision_id, note_id), now)
        receipt = dict(case_id=head['case_id'], case_version=event['case_version'], decision_id=decision['decision_id'],
            decision='REJECT', accepted_at=timestamp(now), processing_status='ACCEPTED')
        validate('DecisionReceipt', receipt, internal=True)
        acceptance = idempotency.record_acceptance(uow, actor, OPERATION, head['case_id'], key, fingerprint,
            'CASE', head['case_id'], 200, now)
        refs = [('CASE', head['case_id'])] + [(r['kind'], r['object_id']) for r in
            uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
                old.history.c.kind.in_(['STATEMENT', 'EVIDENCE']))).mappings()]
        idempotency.record_receipt(uow, acceptance, receipt, refs)
        fact_seal = one(uow, old.acceptances, acceptance_id=acceptance)
        receipt_seal = one(uow, old.receipts, acceptance_id=acceptance)
        accepted_head = one(uow, old.case_heads, case_id=head['case_id'])
        accepted = accepted_reject(uow, accepted_head, decision_id, COMPONENT)
        state_seal = dict(current(uow, accepted_head))
        bindings_seal = [dict(r) for r in uow.execute(select(t.sources).where(
            t.sources.c.work_id == work_id, t.sources.c.epoch == claim.epoch).order_by(t.sources.c.slot)).mappings()]

        def check():
            h = self._same_authority(uow, actor, head, grant)
            s = current(uow, h)
            if (s is None or dict(s) != state_seal
                    or read_target(uow, h, s, request, COMPONENT, original_state=original_state, consumer=decision_id) != source
                    or accepted_reject(uow, h, decision_id, COMPONENT) != accepted):
                reject(uow)
            # The costly source proofs must precede final current authorization
            # and the exact original, never renewed, claim/lease/state seals.
            final_head = self._same_authority(uow, actor, head, grant)
            actual_bindings = [dict(r) for r in uow.execute(select(t.sources).where(
                t.sources.c.work_id == work_id, t.sources.c.epoch == claim.epoch).order_by(t.sources.c.slot)).mappings()]
            if (final_head['status'] != 'NOTIFICATION_PENDING' or final_head['case_version'] != event['case_version']
                    or final_head['input_version'] != head['input_version'] or dict(current(uow, final_head)) != state_seal
                    or version(uow.connection) not in APPROVAL_VERSIONS or actual_bindings != bindings_seal
                    or one(uow, t.work, work_id=work_id) != accepted['work']
                    or one(uow, t.work, work_id=state_seal['notification_work_id']) != accepted['notification_work']
                    or one(uow, t.events, record_id=decision_id) != event
                    or one(uow, old.acceptances, acceptance_id=acceptance) != fact_seal
                    or one(uow, old.receipts, acceptance_id=acceptance) != receipt_seal
                    or accepted['notification_work']['state'] != 'PENDING'
                    or accepted['notification_work']['epoch'] != 0
                    or any(accepted['notification_work'][name] is not None for name in
                        ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))
                    or accepted['work']['claim_id'] != claim.claim_id or accepted['work']['epoch'] != claim.epoch
                    or accepted['work']['authority_revision'] != claim.authority_revision
                    or self.clock() >= original_lease or self.guard.clock() >= original_lease):
                reject(uow)

        uow.before_commit(check)
        return receipt

    def accept(self, case_id, request, original_key, correlation_id):
        """One explicit attempt; never retry a lost commit acknowledgment."""
        uow = None
        committed = False
        code = 'INTERNAL_ERROR'
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                validate('Id', case_id)
                actor, head, grant = authorize(uow, self.authority, case_id)
                request = self._request(request)
                validate('Id', correlation_id)
                fact, fingerprint = self._lookup(uow, actor, head, request, original_key)
                receipt = (self._replay(uow, fact, actor, head, grant, request) if fact is not None
                    else self._new(uow, actor, head, grant, request, original_key, fingerprint, correlation_id))
                uow.commit()
                committed = True
            return RejectResult('ACCEPTED', receipt)
        except AcceptanceOutcomeUnknown:
            return RejectResult('UNKNOWN')
        except FlowError as error:
            code = error.code
        except Exception:
            pass
        if committed or (uow is not None and uow.connection is not None and not uow.connection.closed):
            return RejectResult('UNKNOWN')
        audit = record_denial(self.engine, self.authority, case_id, code, self.clock, uow_factory=self.audit_uow)
        return RejectResult('DENIED', safe_code=code, audit=audit)

    def recover(self, case_id, request, original_key):
        """Fresh authorization and original receipt only; absence stays UNKNOWN."""
        try:
            with self.recovery_uow(self.engine, write=True) as uow:
                validate('Id', case_id)
                actor, head, grant = authorize(uow, self.authority, case_id)
                request = self._request(request)
                fact, _ = self._lookup(uow, actor, head, request, original_key)
                if fact is None:
                    uow.before_commit(lambda: self._same_authority(uow, actor, head, grant))
                    uow.commit()
                    return RejectResult('UNKNOWN')
                receipt = self._replay(uow, fact, actor, head, grant, request)
                uow.commit()
            return RejectResult('ACCEPTED', receipt)
        except FlowError as error:
            return RejectResult('UNKNOWN', safe_code=error.code)
        except Exception:
            return RejectResult('UNKNOWN')
