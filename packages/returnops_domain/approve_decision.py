"""Private exact-preview HUMAN approval. Stops at APPROVED/unclaimed intent."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from sqlalchemy import select, update
from . import customer_tables as old, founder_tables as ft, lifecycle_tables as t
from . import founder_codec as finite, idempotency
from .audit import append_event, identifier, timestamp
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .lifecycle_events import ApprovalAccepted
from .lifecycle_guards import LifecycleGuards
from .lifecycle_schema import CURRENT, version
from .lifecycle_state import current, reject
from .manual_target import one
from .approve_denial import COMPONENT, OPERATION, authorize, record_denial
from .approve_sources import read_target, accepted_approval, check_seal
from .preview_sources import consume, consume_payload, current_policy
from .wire import validate


@dataclass(frozen=True, repr=False)
class ApproveResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class FounderApproveService:
    def __init__(self, engine, authority, *, clock=lambda:datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork, recovery_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.uow_factory, self.recovery_uow, self.audit_uow = uow_factory, recovery_uow, audit_uow
        self.guard = LifecycleGuards(COMPONENT, clock=clock)

    @staticmethod
    def _request(request):
        value = validate('FounderDecisionRequest', request)
        if value['decision'] != 'APPROVE' or 'proposal_id' not in value:
            raise FlowError('INVALID_STATE')
        return value

    def _lookup(self, uow, actor, head, request, key):
        fingerprint = digest(request, 'founder-approve-request/v1')
        def check(fact):
            if (fact['resource_kind'] != 'CASE' or fact['resource_id'] != head['case_id']
                    or fact['store_id'] != actor.store_id):
                reject(uow, 'FORBIDDEN')
        return idempotency.lookup(uow, actor, OPERATION, head['case_id'], key, fingerprint,
                                  check_resource=check), fingerprint

    def _same_authority(self, uow, actor, head, grant):
        a, h, g = authorize(uow, self.authority, head['case_id'])
        if (a != actor or h['store_id'] != head['store_id']
                or h['owner_principal_id'] != head['owner_principal_id'] or dict(g) != dict(grant)):
            reject(uow, 'FORBIDDEN')
        return h

    def _replay(self, uow, fact, actor, head, grant, request):
        _, receipt = idempotency.original_receipt(uow, fact)
        validate('DecisionReceipt', receipt, internal=True)
        record = uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
            old.history.c.kind == 'APPROVAL', old.history.c.object_id == receipt.get('approval_id'))).mappings().one_or_none()
        if record is None:
            reject(uow)
        seal = accepted_approval(uow, head, record['record_id'], COMPONENT)
        decision, approval = seal['decision'], seal['body']
        if (receipt['case_id'] != head['case_id'] or receipt['decision'] != 'APPROVE'
                or receipt['decision_id'] != decision['decision_id'] or receipt['approval_id'] != approval['approval_id']
                or receipt['case_version'] != seal['event']['case_version']
                or decision['principal_id'] != actor.principal_id
                or any(decision[name] != request[name] for name in ('decision','proposal_id','proposal_version','reason'))
                or request['preview_id'] != approval['preview_id'] or request['scope_fingerprint'] != approval['scope_fingerprint']
                or request['expected_case_version'] != seal['event']['pre_case_version']
                or receipt['accepted_at'] != timestamp(fact['accepted_at'])
                or fact['accepted_at'] != seal['event']['accepted_at']):
            reject(uow)
        original_receipt = one(uow, old.receipts, acceptance_id=fact['acceptance_id'])
        def check():
            h = self._same_authority(uow, actor, head, grant)
            if accepted_approval(uow, h, record['record_id'], COMPONENT) != seal:
                reject(uow)
            self._same_authority(uow, actor, head, grant)
            check_seal(uow, seal)
            if (one(uow, old.acceptances, acceptance_id=fact['acceptance_id']) != dict(fact)
                    or one(uow, old.receipts, acceptance_id=fact['acceptance_id']) != original_receipt
                    or version(uow.connection) != CURRENT):
                reject(uow)
        uow.before_commit(check)
        return receipt

    @staticmethod
    def _append(uow, case_id, kind, body, actor, correlation, payload, now):
        finite.validate('FounderDecisionRecord' if kind == 'DECISION' else 'ApprovalRecord', body)
        head = one(uow, old.case_heads, case_id=case_id)
        record_id = identifier('approve_source')
        object_id = body['decision_id' if kind == 'DECISION' else 'approval_id']
        ref = dict(record_id=record_id, kind=kind, object_id=object_id, object_version=1)
        source_hash = finite.digest(body)
        uow.execute(old.history.insert().values(**ref, case_id=case_id, case_version=head['case_version'],
            recorded_sequence=head['history_sequence']+1, recorded_at=now,
            content_sha256=source_hash, retention_state='AVAILABLE', removal_reason=None))
        uow.execute(old.history_contents.insert().values(record_id=record_id, body=finite.encode_document(body)))
        uow.execute(ft.encodings.insert().values(record_id=record_id, profile=finite.PROFILE,
            source_content_sha256=source_hash, projected_content_sha256=source_hash, receipt_id=None))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case_id).values(
            history_sequence=head['history_sequence']+1))
        append_event(uow, case_id, actor=actor,
            event_type='FOUNDER_DECISION_ACCEPTED' if kind == 'DECISION' else 'FOUNDER_APPROVAL_ISSUED',
            correlation_id=correlation, payload=payload, object_ids=[object_id], history_refs=[ref], now=now)
        return record_id, source_hash

    def _new(self, uow, actor, head, grant, request, key, fingerprint, correlation):
        if head['case_version'] != request['expected_case_version']:
            reject(uow, 'STALE_CASE_VERSION')
        state = current(uow, head)
        preview = read_target(uow, head, state, request, COMPONENT)
        original_state = dict(state)
        preview_grant = current_policy(uow, head, preview['row'])
        now = self.clock()
        if (now.utcoffset() is None or now < preview['row']['issued_at']
                or now >= preview['row']['expires_at']):
            reject(uow)
        work_id = self.guard.prepare(uow, head['case_id'], head['case_version'], ApprovalAccepted, now)
        claim = self.guard.claim(uow, work_id, now)
        if claim is None:
            reject(uow)
        lease = one(uow, t.work, work_id=work_id)['lease_expires_at']
        approval_id = identifier('approval')
        decision = dict(decision_id=identifier('approve_decision'), case_id=head['case_id'], decision='APPROVE',
            principal_id=actor.principal_id, reason=request['reason'], decided_at=timestamp(now), approval_id=approval_id,
            **{name:request[name] for name in ('proposal_id','proposal_version')})
        human = {'kind':'HUMAN','role':'FOUNDER','principal_id':actor.principal_id}
        payload = consume_payload(preview['row'])
        decision_id, _ = self._append(uow, head['case_id'], 'DECISION', decision, human, correlation, payload, now)
        approval = dict(approval_id=approval_id, decision_id=decision['decision_id'], principal_id=actor.principal_id,
            issued_at=timestamp(now), **preview['body'])
        record_id, source_hash = self._append(uow, head['case_id'], 'APPROVAL', approval, human, correlation, payload, now)
        uow.execute(t.sources.insert().values(record_id=record_id, case_id=head['case_id'], **asdict(claim),
            source_hash=source_hash, target_record_id=preview['row']['review_record_id'], slot='PRIMARY',
            order_projection_id=preview['row']['order_projection_id']))
        consume(uow, preview, decision_id, now)
        event = self.guard.apply(uow, ApprovalAccepted(identifier('approve_event'), claim, record_id,
                                                       decision_id, preview['row']['preview_id']), now)
        receipt = dict(case_id=head['case_id'], case_version=event['case_version'], decision_id=decision['decision_id'],
            approval_id=approval_id, decision='APPROVE', accepted_at=timestamp(now), processing_status='ACCEPTED')
        validate('DecisionReceipt', receipt, internal=True)
        acceptance = idempotency.record_acceptance(uow, actor, OPERATION, head['case_id'], key, fingerprint,
            'CASE', head['case_id'], 200, now)
        refs = [('CASE', head['case_id'])] + [(row['kind'],row['object_id']) for row in
            uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
                old.history.c.kind.in_(['STATEMENT','EVIDENCE']))).mappings()]
        idempotency.record_receipt(uow, acceptance, receipt, refs)
        fact = one(uow, old.acceptances, acceptance_id=acceptance)
        original_receipt = one(uow, old.receipts, acceptance_id=acceptance)
        h = one(uow, old.case_heads, case_id=head['case_id'])
        accepted = accepted_approval(uow, h, record_id, COMPONENT)
        saved_state = dict(current(uow, h))
        def check():
            h = self._same_authority(uow, actor, head, grant)
            s = current(uow, h)
            target = read_target(uow, h, s, request, COMPONENT, original_state=original_state, consumer=decision_id)
            if (target != accepted['preview'] or accepted_approval(uow, h, record_id, COMPONENT) != accepted
                    or current_policy(uow, h, target['row']) != preview_grant):
                reject(uow)
            h = self._same_authority(uow, actor, head, grant)
            current_policy(uow, h, target['row'])
            check_seal(uow, accepted)
            if (h['status'] != 'APPROVED' or h['case_version'] != event['case_version']
                    or h['input_version'] != head['input_version'] or dict(current(uow, h)) != saved_state
                    or version(uow.connection) != CURRENT or accepted['work']['claim_id'] != claim.claim_id
                    or accepted['work']['epoch'] != claim.epoch or accepted['work']['authority_revision'] != claim.authority_revision
                    or accepted['execution']['state'] != 'PENDING' or accepted['execution']['epoch'] != 0
                    or one(uow, old.acceptances, acceptance_id=acceptance) != fact
                    or one(uow, old.receipts, acceptance_id=acceptance) != original_receipt
                    or self.clock() >= lease or self.guard.clock() >= lease
                    or self.clock() >= target['row']['expires_at']):
                reject(uow)
        uow.before_commit(check)
        return receipt

    def accept(self, case_id, request, original_key, correlation_id):
        uow = None; committed = False; code = 'INTERNAL_ERROR'
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                validate('Id', case_id)
                actor, head, grant = authorize(uow, self.authority, case_id)
                request = self._request(request); validate('Id', correlation_id)
                fact, fingerprint = self._lookup(uow, actor, head, request, original_key)
                receipt = (self._replay(uow, fact, actor, head, grant, request) if fact is not None else
                    self._new(uow, actor, head, grant, request, original_key, fingerprint, correlation_id))
                uow.commit(); committed = True
            return ApproveResult('ACCEPTED', receipt)
        except AcceptanceOutcomeUnknown:
            return ApproveResult('UNKNOWN')
        except FlowError as error:
            code = error.code
        except Exception:
            pass
        if committed or uow is not None and uow.connection is not None and not uow.connection.closed:
            return ApproveResult('UNKNOWN')
        audit = record_denial(self.engine, self.authority, case_id, code, self.clock, uow_factory=self.audit_uow)
        return ApproveResult('DENIED', safe_code=code, audit=audit)

    def recover(self, case_id, request, original_key):
        try:
            with self.recovery_uow(self.engine, write=True) as uow:
                validate('Id', case_id)
                actor, head, grant = authorize(uow, self.authority, case_id)
                request = self._request(request)
                fact, _ = self._lookup(uow, actor, head, request, original_key)
                if fact is None:
                    uow.before_commit(lambda:self._same_authority(uow, actor, head, grant)); uow.commit()
                    return ApproveResult('UNKNOWN')
                receipt = self._replay(uow, fact, actor, head, grant, request); uow.commit()
            return ApproveResult('ACCEPTED', receipt)
        except FlowError as error:
            return ApproveResult('UNKNOWN', safe_code=error.code)
        except Exception:
            return ApproveResult('UNKNOWN')
