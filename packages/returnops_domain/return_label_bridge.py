"""Private single-transaction acceptance of a complete retained modern return.

No return/label/provider adapter is called. Context is disclosed only after a
confirmed commit and context close, with current EFFECT/query authority.
"""
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import update
from . import customer_tables as old, lifecycle_tables as life
from .approval_admission_sources import check_session_time, session_bounds
from .audit import append_event
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .lifecycle_events import LifecycleClaim
from .lifecycle_guards import LifecycleGuards
from .lifecycle_sources import authority as current_grant
from .lifecycle_state import reject, MAX_VERSION
from .manual_target import one
from .return_execution_sources import COMPONENT, authorize, database_now, provider_permission
from .return_label_sources import (closure, read_source, identity, event_for, audit_payload,
    binding_values, receipt_values, retained_acceptance, expected_delta, context)
from .wire import validate


@dataclass(frozen=True, slots=True, repr=False)
class ReturnSourceResult:
    status: str
    label_context: dict | None = None
    event_id: str | None = None
    source_record_id: str | None = None
    safe_code: str | None = None


class ReturnLabelBridge:
    def __init__(self, engine, authority, *, uow_factory=CustomerUnitOfWork, lease_seconds=60):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise FlowError('INTERNAL_ERROR')
        self.engine, self.authority, self.uow_factory = engine, authority, uow_factory
        self.lease_seconds = lease_seconds

    def accept_return_source(self, case_id, expected_case_version, execution_work_id,
                             original_approval_key, correlation_id):
        return self._run(case_id, execution_work_id, original_approval_key, correlation_id,
                         expected=expected_case_version, accepting=True)

    def recover_return_source(self, case_id, execution_work_id, original_approval_key, correlation_id):
        return self._run(case_id, execution_work_id, original_approval_key, correlation_id,
                         expected=None, accepting=False)

    @staticmethod
    def _request(case_id, execution_work_id, original_key, correlation_id, expected, accepting):
        for value in (case_id, execution_work_id, correlation_id):
            validate('Id', value)
        validate('IdempotencyKey', original_key)
        if accepting:
            if type(expected) is not int:
                raise FlowError('VALIDATION_ERROR')
            validate('Version', expected)

    def _run(self, case_id, execution_work_id, original_key, correlation_id, *, expected, accepting):
        phase = {'commit_possible': False}
        try:
            self._request(case_id, execution_work_id, original_key, correlation_id, expected, accepting)
            with self.uow_factory(self.engine, write=True) as uow:
                authorization = authorize(uow, self.authority, case_id, create=False)
                actor, head, grant, permission, bounds = authorization
                before = closure(uow, case_id)
                source = read_source(uow, authorization, execution_work_id, original_key)
                if closure(uow, case_id) != before:
                    reject(uow)
                if source is None:
                    if accepting:
                        reject(uow)
                    ids = saved = None
                    after, new_head, lease = before, head, None
                    answer = ReturnSourceResult('UNKNOWN')
                else:
                    ids = identity(actor, head, source)
                    saved = retained_acceptance(uow, head, source, ids)
                    if closure(uow, case_id) != before:
                        reject(uow)
                    if saved is not None:
                        if accepting and expected != saved['receipt']['pre_case_version']:
                            reject(uow, 'IDEMPOTENCY_CONFLICT')
                        after, new_head, lease = before, head, None
                        answer = ReturnSourceResult('REPLAYED', context(source), ids['event_id'], source['record']['record_id'])
                    elif not accepting:
                        after, new_head, lease = before, head, None
                        answer = ReturnSourceResult('UNKNOWN')
                    else:
                        if head['case_version'] != expected:
                            reject(uow, 'STALE_CASE_VERSION')
                        if max(head['case_version'], head['audit_sequence']) >= MAX_VERSION:
                            reject(uow)
                        after, new_head, lease, saved = self._stage(uow, authorization, source, ids, before)
                        answer = ReturnSourceResult('ACCEPTED', context(source), ids['event_id'], source['record']['record_id'])
                self._final(uow, authorization, source, ids, saved, execution_work_id, original_key,
                            after, new_head, lease, phase)
                uow.commit()
            # Neither commit acknowledgment nor __exit__/close may be uncertain.
            return answer
        except FlowError as error:
            return ReturnSourceResult('UNKNOWN' if phase['commit_possible'] or error.code == 'INTERNAL_ERROR'
                                      else 'DENIED', safe_code=error.code)
        except Exception:
            return ReturnSourceResult('UNKNOWN')

    def _stage(self, uow, authorization, source, ids, before):
        actor, head, grant, permission, bounds = authorization
        created_at = database_now(uow)
        check_session_time(created_at, bounds)
        work = dict(work_id=ids['work_id'], case_id=head['case_id'], component_id=COMPONENT,
            store_id=head['store_id'], owner_id=head['owner_principal_id'], purpose='EFFECT',
            input_version=head['input_version'], generation=source['state']['generation'],
            target_hash=ids['target_hash'], target_record_id=source['record']['record_id'],
            state='PENDING', claim_id=None, epoch=0, claimed_case_version=None, authority_revision=None,
            idempotency_key=ids['idempotency_key'], lease_expires_at=None, created_at=created_at)
        uow.execute(life.work.insert().values(**work))
        accepted_at = database_now(uow)
        claim = LifecycleGuards(COMPONENT).claim(uow, ids['work_id'], accepted_at, lease_seconds=self.lease_seconds)
        if (type(claim) is not LifecycleClaim or claim.work_id != ids['work_id'] or claim.epoch != 1
                or claim.case_version != head['case_version'] or claim.input_version != head['input_version']
                or claim.generation != source['state']['generation'] or claim.authority_revision != grant['revision']):
            reject(uow)
        running = dict(one(uow, life.work, work_id=ids['work_id']))
        expected_running = {**work, 'state':'RUNNING', 'claim_id':claim.claim_id, 'epoch':1,
            'claimed_case_version':claim.case_version, 'authority_revision':claim.authority_revision,
            'lease_expires_at':accepted_at + timedelta(seconds=self.lease_seconds)}
        if running != expected_running:
            reject(uow)
        event = event_for(ids, claim, source)
        binding = binding_values(head, event, source)
        receipt = receipt_values(head, event, source, accepted_at)
        uow.execute(life.sources.insert().values(**binding))
        uow.execute(life.events.insert().values(**receipt))
        changed = uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == head['case_id'],
            old.case_heads.c.case_version == claim.case_version, old.case_heads.c.status == 'ACTION_IN_PROGRESS')
            .values(case_version=claim.case_version + 1, updated_at=accepted_at))
        if changed.rowcount != 1:
            reject(uow, 'STALE_CASE_VERSION')
        audit = append_event(uow, head['case_id'], actor={'kind':'SERVICE','component_id':COMPONENT},
            event_type='LIFECYCLE_EVENT_ACCEPTED', correlation_id=event.event_id, payload=audit_payload(event),
            object_ids=[source['control']['operation_id'], claim.work_id], history_refs=[], now=accepted_at)
        completed = {**running, 'state':'DONE', 'lease_expires_at':None}
        if uow.execute(update(life.work).where(life.work.c.work_id == claim.work_id,
            life.work.c.state == 'RUNNING', life.work.c.claim_id == claim.claim_id, life.work.c.epoch == 1)
            .values(state='DONE', lease_expires_at=None)).rowcount != 1:
            reject(uow)
        expected = expected_delta(uow, before, head, completed, binding, receipt, audit)
        new_head, = expected[old.case_heads.name]
        saved = dict(work=completed, binding=binding, receipt=receipt, audit=audit, event=event)
        return expected, new_head, running['lease_expires_at'], saved

    def _final(self, uow, initial, source, ids, saved, execution_work_id, original_key,
               expected_seal, expected_head, lease_deadline, phase):
        actor, head, grant, permission, bounds = initial
        def final_check():
            fresh = authorize(uow, self.authority, head['case_id'], create=False)
            fresh_actor, fresh_head, fresh_grant, fresh_permission, fresh_bounds = fresh
            if (fresh_actor != actor or fresh_head != expected_head or fresh_grant != grant
                    or fresh_permission != permission or fresh_bounds != bounds):
                reject(uow)
            latest = read_source(uow, fresh, execution_work_id, original_key)
            if latest != source:
                reject(uow)
            if source is not None:
                if identity(fresh_actor, fresh_head, latest) != ids:
                    reject(uow)
                observed = retained_acceptance(uow, fresh_head, latest, ids)
                if observed != saved:
                    reject(uow)
            if closure(uow, head['case_id']) != expected_seal:
                reject(uow)
            if self.authority(uow.connection, 'getSession') != actor:
                reject(uow, 'UNAUTHENTICATED')
            if (session_bounds(uow, actor) != bounds
                    or dict(current_grant(uow, fresh_head, COMPONENT, 'EFFECT')) != grant
                    or provider_permission(uow, fresh_head, create=False) != permission
                    or one(uow, old.case_heads, case_id=head['case_id']) != expected_head
                    or closure(uow, head['case_id']) != expected_seal):
                reject(uow)
            # This is after the last potentially slow source/authority read.
            now = database_now(uow)
            check_session_time(now, bounds)
            if lease_deadline is not None and now >= lease_deadline:
                reject(uow)
        uow.before_commit(final_check)
        # A conclusive guard rejection is DENIED. Only after all guards succeed
        # can a commit/close failure mean that acceptance may have committed.
        uow.before_commit(lambda: phase.update(commit_possible=True))

