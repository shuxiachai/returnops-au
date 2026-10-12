"""Private trusted HUMAN revision acceptance, ending at POLICY_ASSESSMENT.

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
from .lifecycle_events import RevisionRequested
from .lifecycle_guards import LifecycleGuards
from .lifecycle_state import current, installed, reject
from .revision_denial import COMPONENT, OPERATION, authorize, record_denial
from .revision_sources import read_target, read_preview, accepted_revision, check_current, check_seal
from .preview_sources import consume, consume_payload
from .manual_target import one
from .wire import validate


@dataclass(frozen=True, repr=False)
class RevisionResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class FounderRevisionService:
    def __init__(self, engine, authority, *, clock=lambda: datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork, recovery_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.uow_factory, self.recovery_uow, self.audit_uow = uow_factory, recovery_uow, audit_uow
        self.guard = LifecycleGuards(COMPONENT, clock=clock)

    @staticmethod
    def _request(request):
        value = validate('FounderDecisionRequest', request)
        if value['decision'] != 'REQUEST_REVISION' or 'proposal_id' not in value:
            raise FlowError('INVALID_STATE')
        return value

    def _lookup(self, uow, actor, head, request, key):
        fingerprint = digest(request, 'founder-revision-request/v1')
        def check(fact):
            if (fact['resource_kind'] != 'CASE' or fact['resource_id'] != head['case_id']
                    or fact['store_id'] != actor.store_id):
                reject(uow, 'FORBIDDEN')
        return idempotency.lookup(uow, actor, OPERATION, head['case_id'], key, fingerprint,
                                  check_resource=check), fingerprint

    def _replay(self, uow, fact, actor, head, grant, request, key):
        _, receipt = idempotency.original_receipt(uow, fact)
        fact_seal = dict(fact)
        receipt_seal = one(uow, old.receipts, acceptance_id=fact['acceptance_id'])
        validate('DecisionReceipt', receipt, internal=True)
        source = uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
            old.history.c.kind == 'DECISION', old.history.c.object_id == receipt['decision_id'])).mappings().one_or_none()
        if source is None:
            reject(uow)
        seal = accepted_revision(uow, head, source['record_id'], COMPONENT)
        if (receipt['case_id'] != head['case_id'] or receipt['decision'] != 'REQUEST_REVISION'
                or receipt['case_version'] != seal['event']['case_version']
                or receipt['decision_id'] != seal['body']['decision_id']
                or seal['body']['principal_id'] != actor.principal_id
                or any(seal['body'][name] != request[name] for name in
                    ('decision', 'proposal_id', 'proposal_version', 'reason'))
                or request['expected_case_version'] != seal['event']['pre_case_version']
                or any(fact[name] != value for name, value in dict(principal_id=actor.principal_id,
                    store_id=actor.store_id, method='POST', operation=OPERATION, target=head['case_id'],
                    request_key=key, fingerprint=digest(request, 'founder-revision-request/v1'),
                    resource_kind='CASE', resource_id=head['case_id'], response_status=200).items())
                or receipt['accepted_at'] != timestamp(fact['accepted_at'])
                or seal['event']['accepted_at'] != fact['accepted_at']):
            reject(uow)
        def check():
            h = self._same_authority(uow, actor, head, grant)
            if accepted_revision(uow, h, source['record_id'], COMPONENT) != seal:
                reject(uow)
            self._same_authority(uow, actor, head, grant)
            check_seal(uow, seal)
            if (one(uow, old.acceptances, acceptance_id=fact['acceptance_id']) != fact_seal
                    or one(uow, old.receipts, acceptance_id=fact['acceptance_id']) != receipt_seal):
                reject(uow)
        uow.before_commit(check)
        return receipt

    def _same_authority(self, uow, actor, head, grant):
        a, h, g = authorize(uow, self.authority, head['case_id'])
        if (a != actor or h['owner_principal_id'] != head['owner_principal_id']
                or h['store_id'] != head['store_id'] or dict(g) != dict(grant)):
            reject(uow, 'FORBIDDEN')
        return h

    @staticmethod
    def _append(uow, case_id, body, actor, correlation, now, *, payload=None):
        finite.validate('FounderDecisionRecord', body)
        head = one(uow, old.case_heads, case_id=case_id)
        record_id = identifier('revision_source')
        ref = dict(record_id=record_id, kind='DECISION', object_id=body['decision_id'], object_version=1)
        source_hash = finite.digest(body)
        uow.execute(old.history.insert().values(**ref, case_id=case_id, case_version=head['case_version'],
            recorded_sequence=head['history_sequence'] + 1, recorded_at=now,
            content_sha256=source_hash, retention_state='AVAILABLE', removal_reason=None))
        uow.execute(old.history_contents.insert().values(record_id=record_id, body=finite.encode_document(body)))
        uow.execute(finite_tables.encodings.insert().values(record_id=record_id, profile=finite.PROFILE,
            source_content_sha256=source_hash, projected_content_sha256=source_hash, receipt_id=None))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case_id).values(
            history_sequence=head['history_sequence'] + 1))
        append_event(uow, case_id, actor={'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':actor.principal_id},
            event_type='FOUNDER_DECISION_ACCEPTED', correlation_id=correlation,
            payload={'private_revision':True} if payload is None else payload,
            object_ids=[body['decision_id']], history_refs=[ref], now=now)
        return record_id, source_hash

    def _new(self, uow, actor, head, grant, request, key, fingerprint, correlation):
        from .lifecycle_schema import version, CURRENT
        if not installed(uow) or version(uow.connection) != CURRENT:
            reject(uow)
        if head['case_version'] != request['expected_case_version']:
            reject(uow, 'STALE_CASE_VERSION')
        if head['status'] not in {'ESCALATED', 'AWAITING_APPROVAL'}:
            reject(uow)
        state = current(uow, head)
        if state is None:
            reject(uow)
        original_state = dict(state)
        source = read_target(uow, head, state, request, COMPONENT)
        preview = read_preview(uow, head, state, request['expected_case_version'])
        now = self.clock()
        if now.utcoffset() is None or preview is not None and now < preview['row']['issued_at']:
            reject(uow)
        # The pre-provisioned REVISION capability owns this exact old target.
        # No next-proposal, outcome or notification work is created.
        work_id = self.guard.prepare(uow, head['case_id'], head['case_version'], RevisionRequested, now)
        claim = self.guard.claim(uow, work_id, now)
        if claim is None:
            reject(uow)
        original_lease = one(uow, t.work, work_id=work_id)['lease_expires_at']
        decision = dict(decision_id=identifier('revision_decision'), case_id=head['case_id'],
            decision='REQUEST_REVISION', principal_id=actor.principal_id, reason=request['reason'],
            decided_at=timestamp(now), **{k:request[k] for k in ('proposal_id','proposal_version')})
        decision_id, decision_hash = self._append(uow, head['case_id'], decision, actor, correlation, now,
            payload=None if preview is None else consume_payload(preview['row']))
        uow.execute(t.sources.insert().values(record_id=decision_id, case_id=head['case_id'],
            **asdict(claim), source_hash=decision_hash, target_record_id=source['record']['record_id'], slot='PRIMARY'))
        if preview is not None:
            consume(uow, preview, decision_id, now)
        event = self.guard.apply(uow, RevisionRequested(identifier('revision_event'), claim, decision_id), now)
        receipt = dict(case_id=head['case_id'], case_version=event['case_version'], decision_id=decision['decision_id'],
            decision='REQUEST_REVISION', accepted_at=timestamp(now), processing_status='ACCEPTED')
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
        accepted_head = one(uow, old.case_heads, case_id=head['case_id'])
        accepted = accepted_revision(uow, accepted_head, decision_id, COMPONENT)
        accepted_state = dict(current(uow, accepted_head))
        def check():
            h = self._same_authority(uow, actor, head, grant)
            s = current(uow, h)
            if (h['status'] != 'POLICY_ASSESSMENT' or h['case_version'] != event['case_version']
                    or h['input_version'] != head['input_version'] or s is None
                    or dict(s) != accepted_state
                    or accepted_revision(uow, h, decision_id, COMPONENT) != accepted
                    or read_target(uow, h, s, request, COMPONENT,
                        original_state=original_state, consumer=decision_id) != source
                    or read_preview(uow, h, original_state, request['expected_case_version'],
                        consumer=decision_id) != accepted.get('preview')
                    or one(uow, old.acceptances, acceptance_id=acceptance) != fact_seal
                    or one(uow, old.receipts, acceptance_id=acceptance) != receipt_seal):
                reject(uow)
            # The historical proof above does not validate mutable raw inputs.
            # Repeat current=True after it, without requiring old producer grants.
            check_current(uow, h, original_state, source, COMPONENT)
            # Full retained-source reads can be expensive. Recheck BOTH actual
            # authorities and the original claim/lease after those reads, as
            # the final callback; never renew or borrow a replacement lease.
            if one(uow, t.work, work_id=work_id) != accepted_work:
                reject(uow)
            final_head=self._same_authority(uow, actor, head, grant)
            check_seal(uow, accepted)
            if (final_head['status']!='POLICY_ASSESSMENT' or final_head['case_version']!=event['case_version']
                    or final_head['input_version']!=head['input_version'] or dict(current(uow,final_head))!=dict(s)
                    or one(uow, old.acceptances, acceptance_id=acceptance) != fact_seal
                    or one(uow, old.receipts, acceptance_id=acceptance) != receipt_seal
                    or version(uow.connection) != CURRENT
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
            return RevisionResult('ACCEPTED', receipt)
        except AcceptanceOutcomeUnknown:
            return RevisionResult('UNKNOWN')
        except FlowError as error:
            code = error.code
        except Exception:
            pass
        if committed or (uow is not None and uow.connection is not None and not uow.connection.closed):
            return RevisionResult('UNKNOWN')
        audit = record_denial(self.engine, self.authority, case_id, code, self.clock, uow_factory=self.audit_uow)
        return RevisionResult('DENIED', safe_code=code, audit=audit)

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
                    return RevisionResult('UNKNOWN')
                receipt = self._replay(uow, fact, actor, head, grant, request, original_key)
                uow.commit()
            return RevisionResult('ACCEPTED', receipt)
        except FlowError as error:
            return RevisionResult('UNKNOWN', safe_code=error.code)
        except Exception:
            return RevisionResult('UNKNOWN')
