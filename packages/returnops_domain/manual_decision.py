"""Private trusted HUMAN manual acceptance, ending at NOTIFICATION_PENDING.

No public endpoint, default producer, grant provisioning, approval or effect.
UNKNOWN never automatically retries or records a denial. Recovery reads only
the original acceptance under fresh authority; absence remains UNKNOWN.
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
from .lifecycle_state import current, installed, reject
from .manual_denial import COMPONENT, OPERATION, authorize, record_denial
from .manual_target import read_target, one
from .pass_manual_sources import (accepted_manual, read_preview, check_current,
    check_actor, check_seal, MESSAGE)
from .preview_sources import consume, consume_payload
from .wire import validate


@dataclass(frozen=True, repr=False)
class ManualResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class FounderDecisionService:
    def __init__(self, engine, authority, *, clock=lambda: datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork, recovery_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.uow_factory, self.recovery_uow, self.audit_uow = uow_factory, recovery_uow, audit_uow
        self.guard = LifecycleGuards(COMPONENT, clock=clock)

    @staticmethod
    def _request(request):
        value = validate('FounderDecisionRequest', request)
        if value['decision'] != 'MANUAL_HANDLING':
            raise FlowError('INVALID_STATE')
        return value

    def _lookup(self, uow, actor, head, request, key):
        fingerprint = digest(request, 'founder-manual-request/v1')
        def check(fact):
            if (fact['resource_kind'] != 'CASE' or fact['resource_id'] != head['case_id']
                    or fact['store_id'] != actor.store_id):
                reject(uow, 'FORBIDDEN')
        return idempotency.lookup(uow, actor, OPERATION, head['case_id'], key, fingerprint,
                                  check_resource=check), fingerprint

    def _replay(self, uow, fact, actor, head, grant, request, key):
        _, receipt = idempotency.original_receipt(uow, fact)
        validate('DecisionReceipt', receipt, internal=True)
        if (receipt['case_id'] != head['case_id'] or receipt['decision'] != 'MANUAL_HANDLING'
                or receipt['accepted_at'] != timestamp(fact['accepted_at'])):
            reject(uow)
        # The separately erasable original receipt is never reconstructed.
        # Its accepted fact and domain receipt must still identify one event.
        source = uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
            old.history.c.kind == 'DECISION', old.history.c.object_id == receipt['decision_id'])).mappings().one_or_none()
        if source is None:
            reject(uow)
        event = one(uow, t.events, record_id=source['record_id'])
        if (event['event_kind'] != 'OUTCOME' or event['case_version'] != receipt['case_version']
                or event['source_hash'] != source['content_sha256'] or event['accepted_at'] != fact['accepted_at']):
            reject(uow)
        from .lifecycle_sources import Sources
        _, decision=Sources(uow,head,COMPONENT).read(source['record_id'],{'DECISION'},current_actor=False)
        if 'proposal_id' in decision:
            seal = accepted_manual(uow, head, source['record_id'], COMPONENT)
            if (receipt['decision_id'] != seal['body']['decision_id']
                    or receipt['case_version'] != seal['event']['case_version']
                    or seal['body']['principal_id'] != actor.principal_id
                    or any(seal['body'][name] != request.get(name) for name in
                        ('decision', 'proposal_id', 'proposal_version', 'reason'))
                    or seal['event']['pre_case_version'] != request['expected_case_version']
                    or seal['event']['accepted_at'] != fact['accepted_at']
                    or any(fact[name] != value for name, value in dict(principal_id=actor.principal_id,
                        store_id=actor.store_id, method='POST', operation=OPERATION, target=head['case_id'],
                        request_key=key, fingerprint=digest(request, 'founder-manual-request/v1'),
                        resource_kind='CASE', resource_id=head['case_id'], response_status=200).items())):
                reject(uow)
            fact_seal = dict(fact)
            receipt_seal = one(uow, old.receipts, acceptance_id=fact['acceptance_id'])
            def check():
                h = self._same_authority(uow, actor, head, grant)
                if accepted_manual(uow, h, source['record_id'], COMPONENT) != seal:
                    reject(uow)
                h = self._same_authority(uow, actor, head, grant)
                check_actor(uow, h, seal)
                check_seal(uow, seal)
                if (one(uow, old.acceptances, acceptance_id=fact['acceptance_id']) != fact_seal
                        or one(uow, old.receipts, acceptance_id=fact['acceptance_id']) != receipt_seal):
                    reject(uow)
            uow.before_commit(check)
        else:
            uow.before_commit(lambda: self._same_authority(uow, actor, head, grant))
        return receipt

    def _same_authority(self, uow, actor, head, grant):
        a, h, g = authorize(uow, self.authority, head['case_id'])
        if (a != actor or h['owner_principal_id'] != head['owner_principal_id']
                or h['store_id'] != head['store_id'] or dict(g) != dict(grant)):
            reject(uow, 'FORBIDDEN')
        return h

    @staticmethod
    def _append(uow, case_id, kind, body, actor, correlation, now, *, payload=None):
        finite.validate('FounderDecisionRecord' if kind == 'DECISION' else 'NotificationRecord', body)
        head = one(uow, old.case_heads, case_id=case_id)
        record_id = identifier('manual_source')
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
            correlation_id=correlation, payload={'private_manual':True} if payload is None else payload,
            object_ids=[object_id], history_refs=[ref], now=now)
        return record_id, source_hash

    def _new(self, uow, actor, head, grant, request, key, fingerprint, correlation):
        if not installed(uow):
            reject(uow)
        if 'proposal_id' in request:
            from .lifecycle_schema import version,APPROVAL_VERSIONS
            if version(uow.connection)not in APPROVAL_VERSIONS:
                reject(uow)
        if head['case_version'] != request['expected_case_version']:
            reject(uow, 'STALE_CASE_VERSION')
        if head['status'] not in ({'ESCALATED', 'AWAITING_APPROVAL'} if 'proposal_id' in request else {'ESCALATED'}):
            reject(uow)
        # Original input=1 intake/order failures may have no lifecycle sidecar.
        # Initialize only inside this authorized new-intent transaction; every
        # denial rolls this insertion back and GET/replay never initializes it.
        state = current(uow, head, initialize='proposal_id' not in request)
        excluded=('approval_record_id','outcome_record_id','outcome')
        if 'proposal_id' not in request:
            excluded+=('proposal_record_id','review_record_id','preview_id')
        if state is None or not state['available'] or any(state[name] is not None for name in excluded):
            reject(uow)
        original_state = dict(state)
        source = read_target(uow, head, state, request, COMPONENT)
        preview = (read_preview(uow, head, state, request['expected_case_version'])
                   if 'proposal_id' in request else None)
        payload = None if preview is None else consume_payload(preview['row'])
        now = self.clock()
        if (now.utcoffset() is None or preview is not None and now < preview['row']['issued_at']
                or 'proposal_id' in request and now < source['event']['accepted_at']):
            reject(uow)
        # Necessary OUTCOME work/claim is part of this one business transaction;
        # no capability is provisioned, and notification work stays unclaimed.
        work_id = self.guard.prepare(uow, head['case_id'], head['case_version'], OutcomeAccepted, now)
        claim = self.guard.claim(uow, work_id, now)
        if claim is None:
            reject(uow)
        original_lease = one(uow, t.work, work_id=work_id)['lease_expires_at']
        if 'proposal_id' in request:
            target_fields={k:request[k] for k in ('proposal_id','proposal_version')}
        else:
            target_field = 'processing_failure_id' if 'processing_failure_id' in request else 'order_lookup_block_id'
            target_fields={target_field:request[target_field]}
        decision = dict(decision_id=identifier('manual_decision'), case_id=head['case_id'],
            decision='MANUAL_HANDLING', principal_id=actor.principal_id, reason=request['reason'],
            decided_at=timestamp(now), **target_fields)
        decision_id, decision_hash = self._append(uow, head['case_id'], 'DECISION', decision,
            {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':actor.principal_id}, correlation, now, payload=payload)
        uow.execute(t.sources.insert().values(record_id=decision_id, case_id=head['case_id'],
            **asdict(claim), source_hash=decision_hash, target_record_id=source['record']['record_id'], slot='PRIMARY'))
        from .notification_intent import initial_format, initial_payload
        from .lifecycle_schema import NOTIFICATION, version
        note_payload = (initial_payload(COMPONENT, 'MANUAL_HANDLED', decision_id, decision_hash)
                        if version(uow.connection) == NOTIFICATION else payload)
        note = dict(notification_id=identifier('manual_notification'), case_id=head['case_id'],
            case_version=head['case_version'], status='PENDING', outcome='MANUAL_HANDLED',
            **initial_format(uow, 'MANUAL_HANDLED', MESSAGE),
            attempt_count=0, updated_at=timestamp(now))
        note_id, note_hash = self._append(uow, head['case_id'], 'NOTIFICATION', note,
            {'kind':'SERVICE', 'component_id':COMPONENT}, correlation, now, payload=note_payload)
        uow.execute(t.sources.insert().values(record_id=note_id, case_id=head['case_id'], **asdict(claim),
            source_hash=note_hash, target_record_id=decision_id, slot='NOTIFICATION'))
        if preview is not None:
            consume(uow, preview, decision_id, now)
        event = self.guard.apply(uow, OutcomeAccepted(identifier('manual_event'), claim, decision_id, note_id), now)
        receipt = dict(case_id=head['case_id'], case_version=event['case_version'], decision_id=decision['decision_id'],
            decision='MANUAL_HANDLING', accepted_at=timestamp(now), processing_status='ACCEPTED')
        validate('DecisionReceipt', receipt, internal=True)
        acceptance = idempotency.record_acceptance(uow, actor, OPERATION, head['case_id'], key, fingerprint,
            'CASE', head['case_id'], 200, now)
        # Retention of any retained input also erases this derived receipt copy.
        refs = [('CASE', head['case_id'])] + [(r['kind'], r['object_id']) for r in
            uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
                old.history.c.kind.in_(['STATEMENT', 'EVIDENCE']))).mappings()]
        idempotency.record_receipt(uow, acceptance, receipt, refs)
        fact_seal = one(uow, old.acceptances, acceptance_id=acceptance)
        receipt_seal = one(uow, old.receipts, acceptance_id=acceptance)
        accepted_work = one(uow, t.work, work_id=work_id)
        accepted = None
        if 'proposal_id' in request:
            accepted_head = one(uow, old.case_heads, case_id=head['case_id'])
            accepted = accepted_manual(uow, accepted_head, decision_id, COMPONENT)
            accepted_state = dict(current(uow, accepted_head))
        def check():
            h = self._same_authority(uow, actor, head, grant)
            s = current(uow, h)
            if accepted is not None:
                if (accepted_manual(uow, h, decision_id, COMPONENT) != accepted
                        or s is None or dict(s) != accepted_state
                        or read_preview(uow, h, original_state, request['expected_case_version'],
                            consumer=decision_id) != accepted['preview']):
                    reject(uow)
            if (h['status'] != 'NOTIFICATION_PENDING' or h['case_version'] != event['case_version']
                    or h['input_version'] != head['input_version'] or s is None
                    or read_target(uow, h, s, request, COMPONENT,
                        original_state=original_state, consumer=decision_id) != source
                    or one(uow, old.acceptances, acceptance_id=acceptance) != fact_seal
                    or one(uow, old.receipts, acceptance_id=acceptance) != receipt_seal):
                reject(uow)
            if accepted is not None:
                check_current(uow, h, original_state, source, COMPONENT)
            # Full retained-source reads can be expensive. Recheck BOTH actual
            # authorities and the original claim/lease after those reads, as
            # the final callback; never renew or borrow a replacement lease.
            if one(uow, t.work, work_id=work_id) != accepted_work:
                reject(uow)
            final_head=self._same_authority(uow, actor, head, grant)
            if accepted is not None:
                check_actor(uow, final_head, accepted)
                check_seal(uow, accepted)
                note_work = accepted['notification_work']
                from .lifecycle_schema import version, APPROVAL_VERSIONS
                if (version(uow.connection) not in APPROVAL_VERSIONS or note_work['state'] != 'PENDING'
                        or note_work['epoch'] != 0 or note_work['work_id'] != accepted_state['notification_work_id']
                        or any(note_work[name] is not None for name in
                            ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))
                        or one(uow, old.acceptances, acceptance_id=acceptance) != fact_seal
                        or one(uow, old.receipts, acceptance_id=acceptance) != receipt_seal):
                    reject(uow)
            if (final_head['status']!='NOTIFICATION_PENDING' or final_head['case_version']!=event['case_version']
                    or final_head['input_version']!=head['input_version'] or dict(current(uow,final_head))!=dict(s)
                    or self.clock() >= original_lease or self.guard.clock() >= original_lease
                    or accepted_work['claim_id'] != claim.claim_id or accepted_work['epoch'] != claim.epoch
                    or accepted_work['authority_revision'] != claim.authority_revision):
                reject(uow)
        uow.before_commit(check)
        return receipt

    def accept(self, case_id, request, original_key, correlation_id):
        """One explicit caller attempt. Never retry a lost commit acknowledgment."""
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
                receipt = (self._replay(uow, fact, actor, head, grant, request, original_key) if fact is not None
                    else self._new(uow, actor, head, grant, request, original_key, fingerprint, correlation_id))
                uow.commit()
                committed = True
            return ManualResult('ACCEPTED', receipt)
        except AcceptanceOutcomeUnknown:
            return ManualResult('UNKNOWN')
        except FlowError as error:
            code = error.code
        except Exception:
            pass
        if committed or (uow is not None and uow.connection is not None and not uow.connection.closed):
            return ManualResult('UNKNOWN')
        audit = record_denial(self.engine, self.authority, case_id, code, self.clock, uow_factory=self.audit_uow)
        return ManualResult('DENIED', safe_code=code, audit=audit)

    def recover(self, case_id, request, original_key):
        """Fresh-fence receipt query; a missing record is never rollback proof.

        Independent actual rollback evidence belongs to the caller. Only that
        caller may explicitly invoke accept again with the same key/parameters.
        Recovery itself neither issues a retry nor constructs a new intent.
        """
        try:
            with self.recovery_uow(self.engine, write=True) as uow:
                validate('Id', case_id)
                actor, head, grant = authorize(uow, self.authority, case_id)
                request = self._request(request)
                fact, _ = self._lookup(uow, actor, head, request, original_key)
                if fact is None:
                    uow.before_commit(lambda: self._same_authority(uow, actor, head, grant))
                    uow.commit()
                    return ManualResult('UNKNOWN')
                receipt = self._replay(uow, fact, actor, head, grant, request, original_key)
                uow.commit()
            return ManualResult('ACCEPTED', receipt)
        except FlowError as error:
            return ManualResult('UNKNOWN', safe_code=error.code)
        except Exception:
            return ManualResult('UNKNOWN')
