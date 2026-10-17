"""Private one-shot CREATE_RETURN: reserve/close, independent mock, fresh accept.

An existing reservation is never sent to create again. Recovery only queries
the original durable identity, including after a pre-call process crash.
"""
from dataclasses import dataclass
from datetime import timedelta
from secrets import token_hex
from sqlalchemy import select, update
from . import customer_tables as old, lifecycle_tables as life, founder_codec as finite
from .audit import append_event, timestamp
from .canonical import digest
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError, AcceptanceOutcomeUnknown
from .approval_admission_sources import command_request, check_time, check_session_time, session_bounds
from .execution_preparation_sources import discover, retained_proof as strict_preparation, source_closure
from .lifecycle_state import current, reject, MAX_VERSION
from .manual_target import one
from .lifecycle_sources import authority as current_grant
from .pass_review_sources import accepted_review
from .preview_profile import APPROVAL_COMPONENT
from .return_execution_tables import controls, ledger
from .return_execution_sources import (CONFIG, COMPONENT, config_hash, database_now, key_hash, stable,
    authorize, control_identity, control_payload, dispatch_payload, continued_proof, verify_fact, project_result, accepted_payload,
    provider_permission)
from .return_execution_history import append_operation, effect_values
from .core_return_mock import CoreReturnMock, Ticket, claim_current
from .wire import validate


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionResult:
    status: str
    operation_id: str | None = None
    operation_state: str | None = None
    provider_operation_id: str | None = None
    record_id: str | None = None
    safe_code: str | None = None
    provider_fact_status: str | None = None


def observed(status, row, *, code=None):
    return ExecutionResult(status, row['operation_id'], row['status'],
        row['confirmed_provider_operation_id'], row['result_record_id'], code, row['confirmed_effect_status'])


class ReturnExecutionService:
    def __init__(self, engine, authority, *, uow_factory=CustomerUnitOfWork, mock_factory=CoreReturnMock):
        self.engine, self.authority = engine, authority
        self.uow_factory, self.mock_factory = uow_factory, mock_factory

    def execute_prepared_create_return(self, case_id, expected_case_version, execution_work_id,
            original_approval_key, candidate_command, correlation_id):
        ticket = self._reserve(case_id, expected_case_version, execution_work_id,
                               original_approval_key, candidate_command, correlation_id)
        if type(ticket) is ExecutionResult:
            return ticket
        return self._perform(ticket, correlation_id)

    def reconcile_create_return(self, case_id, execution_work_id, original_approval_key, correlation_id):
        ticket = self._query_claim(case_id, execution_work_id, original_approval_key, correlation_id)
        if type(ticket) is ExecutionResult:
            return ticket
        return self._perform(ticket, correlation_id)

    @staticmethod
    def _request(case_id, work_id, original_key, correlation):
        for name in (case_id, work_id, correlation):
            validate('Id', name)
        validate('IdempotencyKey', original_key)

    def _reserve(self, case_id, expected, work_id, original_key, candidate, correlation):
        committing = False
        try:
            self._request(case_id, work_id, original_key, correlation)
            if type(expected) is not int:
                raise FlowError('VALIDATION_ERROR')
            validate('Version', expected)
            command = command_request(candidate)
            with self.uow_factory(self.engine, write=True) as uow:
                actor, head, query_grant, query_permission, bounds = authorize(uow, self.authority, case_id, create=False)
                existing = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
                if existing is not None:
                    control_identity(uow, actor, head, existing, original_key)
                    from .execution_preparation_sources import request_fingerprint
                    if expected != existing['approval_case_version'] or request_fingerprint(command) != existing['request_fingerprint']:
                        reject(uow, 'IDEMPOTENCY_CONFLICT')
                    # Existing is query/replay-only, never a second business call.
                    continued_proof(uow, actor, head, existing, original_key)
                    committing = True
                    value = self._finish_observation(uow, (actor, head, query_grant, query_permission, bounds),
                                                     work_id, original_key, dict(existing))
                else:
                    create_actor, create_head, grant, permission, create_bounds = authorize(
                        uow, self.authority, case_id, create=True)
                    if create_actor != actor or create_head != head or create_bounds != bounds:
                        reject(uow)
                    prep = discover(uow, work_id)
                    if prep is None:
                        reject(uow)
                    proof = strict_preparation(uow, actor, head, expected, work_id, original_key, command, prep)
                    state = current(uow, head, initialize=False)
                    if accepted_review(uow, head, state, APPROVAL_COMPONENT, current=True) != proof['approval']['preview']['review']:
                        reject(uow)
                    now = database_now(uow); check_time(now, proof); check_session_time(now, bounds)
                    if max(head['case_version'], head['history_sequence'], head['audit_sequence']) >= MAX_VERSION:
                        reject(uow)
                    next_version = head['case_version'] + 1
                    body = {**proof['body'], 'status': 'EXECUTING', 'case_version': next_version, 'updated_at': timestamp(now)}
                    row = dict(preparation_id=prep['preparation_id'], case_id=case_id, store_id=head['store_id'],
                        owner_id=head['owner_principal_id'], principal_id=actor.principal_id, session_id=actor.session_id,
                        execution_work_id=work_id, approval_record_id=proof['approval']['record']['record_id'],
                        approval_acceptance_id=prep['original_approval_acceptance_id'], operation_id=prep['operation_id'],
                        first_record_id=prep['first_operation_record_id'], dispatch_record_id=stable('dispatch', prep['preparation_id']),
                        dispatch_claim_id=stable('rclaim', prep['preparation_id']), command_id=body['command_id'], approval_id=body['approval_id'],
                        proposal_id=body['proposal_id'], provider_id=body['provider_id'], config_id=CONFIG['config_id'],
                        parcel_id=command['parameters']['parcel_id'], effect_key=prep['effect_key'], preparation_hash=prep['binding_hash'],
                        first_body_hash=proof['record']['content_sha256'], dispatch_body_hash=finite.digest(body),
                        request_fingerprint=prep['request_fingerprint'], operation_fingerprint=body['operation_fingerprint'],
                        original_key_hash=key_hash(actor, original_key), profile_hash=prep['profile_hash'], config_hash=config_hash(),
                        input_version=body['input_version'], generation=proof['approval']['event']['generation'],
                        proposal_version=body['proposal_version'], approval_case_version=expected, dispatch_case_version=next_version,
                        execution_authority_revision=grant['revision'], provider_revision=permission['revision'], dispatch_at=now,
                        dispatch_deadline=min(now + timedelta(seconds=30), proof['approval']['preview']['row']['expires_at']),
                        status='EXECUTING', query_epoch=0, query_claim_id=None, query_lease_until=None,
                        result_record_id=None, result_audit_id=None, confirmed_ledger_hash=None,
                        confirmed_provider_operation_id=None, confirmed_effect_status=None, confirmation_audit_id=None,
                        result_retained=False, source_available=True)
                    row['binding_hash'] = digest(control_payload(row), 'return-reservation/v1')
                    changed = uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case_id,
                        old.case_heads.c.case_version == expected, old.case_heads.c.status == 'APPROVED').values(
                            case_version=next_version, status='ACTION_IN_PROGRESS', updated_at=now))
                    if changed.rowcount != 1:
                        reject(uow)
                    dispatched_head = {**head, 'case_version': next_version, 'status': 'ACTION_IN_PROGRESS', 'updated_at': now}
                    _, event = append_operation(uow, dispatched_head, row['dispatch_record_id'], body, 2,
                                                dispatch_payload(row), correlation, now)
                    row['dispatch_audit_id'] = event['event_id']
                    uow.execute(controls.insert().values(**row))
                    ticket = Ticket(row['preparation_id'], case_id, original_key, row['binding_hash'], 'DISPATCH', row['dispatch_claim_id'], 0)
                    def final_check():
                        a, h, g, p, b = authorize(uow, self.authority, case_id, create=True)
                        current_row = one(uow, controls, preparation_id=row['preparation_id'])
                        if a != actor or g != grant or p != permission or b != bounds or current_row != row:
                            reject(uow)
                        qa, qh, qg, qp, qb = authorize(uow, self.authority, case_id, create=False)
                        if qa != a or qh != h or qb != b or qg != query_grant or qp != query_permission:
                            reject(uow)
                        root = continued_proof(uow, a, h, current_row, original_key, creating=True)
                        if any(root[key] != proof[key] for key in ('approval', 'original_receipt', 'operation_fingerprint', 'record', 'body', 'origin')):
                            reject(uow)
                        claim_current(uow, current_row, ticket, a, g, p)
                        if self.authority(uow.connection, 'getSession') != actor:
                            reject(uow, 'UNAUTHENTICATED')
                    uow.before_commit(final_check)
                    committing = True; uow.commit(); value = ticket
            # The only path returning a dispatch ticket is after confirmed close.
            return value
        except FlowError as error:
            return ExecutionResult('UNKNOWN' if committing or error.code == 'INTERNAL_ERROR' else 'DENIED', safe_code=error.code)
        except Exception:
            return ExecutionResult('UNKNOWN')

    @staticmethod
    def _observation_value(row, now):
        """No I/O after the final current-authority/time sample."""
        if row is None:
            return ExecutionResult('UNKNOWN')
        if row['status'] in {'SUCCEEDED', 'FAILED'} or row['confirmed_effect_status'] is not None:
            return observed('REPLAYED' if row['status'] in {'SUCCEEDED', 'FAILED'} else 'FACT_REPLAYED', row)
        active = (row['query_lease_until'] if row['query_claim_id'] is not None else row['dispatch_deadline'])
        return observed('IN_PROGRESS' if active is not None and now < active else 'UNKNOWN', row)

    @staticmethod
    def _observation_seal(uow, case_id):
        """Exact transient case source/control/ledger rows; never returned/logged."""
        seal = source_closure(uow, case_id)
        seal[controls.name] = [dict(row) for row in uow.execute(select(controls).where(
            controls.c.case_id == case_id).order_by(controls.c.preparation_id)).mappings()]
        keys = select(controls.c.effect_key).where(controls.c.case_id == case_id)
        seal[ledger.name] = [dict(row) for row in uow.execute(select(ledger).where(
            ledger.c.effect_key.in_(keys)).order_by(ledger.c.effect_key)).mappings()]
        return seal

    def _finish_observation(self, uow, authorization, work_id, original_key, saved):
        """One final query-only guard for every read-result branch.

        Read-only replay is still authorized at its final observation point.
        The fence protects trusted changes, but strict DB time is sampled after
        all potentially slow proof/ledger reads. No approval window is renewed.
        The caller still has to leave its context successfully before returning.
        """
        actor, head, grant, permission, bounds = authorization
        seal = self._observation_seal(uow, head['case_id'])
        answer = []
        def final_check():
            fresh = authorize(uow, self.authority, head['case_id'], create=False)
            if fresh != authorization:
                reject(uow)
            latest = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
            latest = None if latest is None else dict(latest)
            if latest != saved:
                reject(uow)
            if latest is not None:
                continued_proof(uow, actor, head, latest, original_key)
            if self._observation_seal(uow, head['case_id']) != seal:
                reject(uow)
            if self.authority(uow.connection, 'getSession') != actor:
                reject(uow, 'UNAUTHENTICATED')
            if (session_bounds(uow, actor) != bounds
                    or dict(current_grant(uow, head, COMPONENT, 'EFFECT')) != grant
                    or provider_permission(uow, head, create=False) != permission
                    or one(uow, old.case_heads, case_id=head['case_id']) != head
                    or self._observation_seal(uow, head['case_id']) != seal):
                reject(uow)
            now = database_now(uow)
            check_session_time(now, bounds)
            answer.append(self._observation_value(latest, now))
        uow.before_commit(final_check)
        uow.commit()
        if len(answer) != 1:
            raise AcceptanceOutcomeUnknown()
        return answer[0]

    def _query_claim(self, case_id, work_id, original_key, correlation):
        committing = False
        try:
            self._request(case_id, work_id, original_key, correlation)
            with self.uow_factory(self.engine, write=True) as uow:
                actor, head, grant, permission, bounds = authorize(uow, self.authority, case_id, create=False)
                found = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
                if found is None:
                    committing = True
                    return self._finish_observation(uow, (actor, head, grant, permission, bounds), work_id, original_key, None)
                row = dict(found)
                continued_proof(uow, actor, head, row, original_key)
                if row['status'] in {'SUCCEEDED', 'FAILED'} or row['confirmed_effect_status'] is not None:
                    committing = True
                    return self._finish_observation(uow, (actor, head, grant, permission, bounds), work_id, original_key, row)
                else:
                    now = database_now(uow)
                    if row['query_claim_id'] is not None and now < row['query_lease_until']:
                        committing = True
                        return self._finish_observation(uow, (actor, head, grant, permission, bounds), work_id, original_key, row)
                    if row['query_epoch'] >= MAX_VERSION:
                        reject(uow)
                    claim_id = 'query_' + token_hex(16)
                    epoch = row['query_epoch'] + 1
                    changes = dict(query_epoch=epoch, query_claim_id=claim_id, query_lease_until=now + timedelta(seconds=30))
                    if uow.execute(update(controls).where(controls.c.preparation_id == row['preparation_id'],
                        controls.c.query_epoch == row['query_epoch'], controls.c.status == 'EXECUTING').values(**changes)).rowcount != 1:
                        reject(uow)
                    value = Ticket(row['preparation_id'], case_id, original_key, row['binding_hash'], 'QUERY', claim_id, epoch)
                    row.update(changes)
                    def final_check():
                        a, h, g, p, b = authorize(uow, self.authority, case_id, create=False)
                        current_row = one(uow, controls, preparation_id=row['preparation_id'])
                        if a != actor or g != grant or p != permission or b != bounds or current_row != row:
                            reject(uow)
                        continued_proof(uow, a, h, current_row, original_key)
                        claim_current(uow, current_row, value, a, g, p)
                    uow.before_commit(final_check)
                committing = True; uow.commit()
            return value
        except FlowError as error:
            return ExecutionResult('UNKNOWN' if committing or error.code == 'INTERNAL_ERROR' else 'DENIED', safe_code=error.code)
        except Exception:
            return ExecutionResult('UNKNOWN')

    def _perform(self, ticket, correlation):
        try:
            reply = self.mock_factory(self.engine).perform(ticket, self.authority)
        except Exception:
            return ExecutionResult('UNKNOWN')
        if reply.status != 'FOUND' or reply.fact is None:
            return ExecutionResult('DENIED' if reply.status == 'DENIED' else 'UNKNOWN', safe_code=reply.safe_code)
        return self._accept(ticket, reply.fact, correlation)

    def _accept(self, ticket, returned, correlation):
        committing = False
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                actor, head, grant, permission, bounds = authorize(uow, self.authority, ticket.case_id, create=False)
                row = one(uow, controls, preparation_id=ticket.preparation_id)
                continued_proof(uow, actor, head, row, ticket.original_key)
                if row['status'] != 'EXECUTING' or row['confirmed_effect_status'] is not None:
                    committing = True
                    return self._finish_observation(uow, (actor, head, grant, permission, bounds),
                                                    row['execution_work_id'], ticket.original_key, row)
                # T3 requires current EFFECT/query permission. The original
                # dispatch lease is checked without pretending this is create.
                claim_current(uow, row, ticket, actor, grant, permission, require_create_authority=False)
                fact = one(uow, ledger, effect_key=row['effect_key'])
                if dict(fact) != returned:
                    reject(uow)
                verify_fact(uow, row, fact)
                now = database_now(uow)
                changes = dict(confirmed_ledger_hash=fact['fact_hash'], confirmed_effect_status=fact['status'],
                    confirmed_provider_operation_id=fact['provider_operation_id'], query_claim_id=None, query_lease_until=None)
                if row['source_available']:
                    result = project_result(fact)
                    from .lifecycle_sources import Sources
                    _, dispatched = Sources(uow, head, COMPONENT).read(row['dispatch_record_id'], {'OPERATION'})
                    body = {**dispatched, 'status': fact['status'], 'updated_at': timestamp(now),
                            'provider_operation_id': fact['provider_operation_id']}
                    if result is not None:
                        body['result'] = result
                    else:
                        body['error'] = dict(error=dict(code='INTERNAL_ERROR', message='Core mock confirmed no effect.',
                            correlation_id=correlation, retryable=False, details=[]))
                    record_id = stable('rresult', row['preparation_id'])
                    record, event = append_operation(uow, head, record_id, body, 3,
                        accepted_payload(row, fact, finite.digest(body)), correlation, now)
                    uow.execute(life.effects.insert().values(**effect_values(row, body, record)))
                    changes.update(status=fact['status'], result_record_id=record_id, result_audit_id=event['event_id'], result_retained=True)
                else:
                    # No erased proposal/command/operation body is reconstructed.
                    dispatch = one(uow, old.history, record_id=row['dispatch_record_id'])
                    ref = {name: dispatch[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}
                    event = append_event(uow, head['case_id'], actor={'kind': 'SERVICE', 'component_id': COMPONENT},
                        event_type='RETURN_EFFECT_CONFIRMED_RETAINED', correlation_id=correlation,
                        payload=accepted_payload(row, fact), object_ids=[row['operation_id']], history_refs=[ref], now=now)
                    changes.update(confirmation_audit_id=event['event_id'], result_retained=False)
                if uow.execute(update(controls).where(controls.c.preparation_id == row['preparation_id'],
                    controls.c.status == 'EXECUTING', controls.c.query_epoch == row['query_epoch']).values(**changes)).rowcount != 1:
                    reject(uow)
                final_row = {**row, **changes}
                def final_check():
                    a, h, g, p, b = authorize(uow, self.authority, ticket.case_id, create=False)
                    latest = one(uow, controls, preparation_id=row['preparation_id'])
                    if a != actor or g != grant or p != permission or b != bounds or latest != final_row:
                        reject(uow)
                    if one(uow, ledger, effect_key=row['effect_key']) != fact:
                        reject(uow)
                    continued_proof(uow, a, h, latest, ticket.original_key)
                    if self.authority(uow.connection, 'getSession') != actor:
                        reject(uow, 'UNAUTHENTICATED')
                    deadline = row['dispatch_deadline'] if ticket.kind == 'DISPATCH' else row['query_lease_until']
                    check_session_time(database_now(uow), bounds)
                    if deadline is None or database_now(uow) >= deadline:
                        reject(uow)
                uow.before_commit(final_check)
                committing = True; uow.commit()
            return observed('COMMITTED' if row['source_available'] else 'FACT_RECORDED', final_row)
        except FlowError as error:
            return ExecutionResult('UNKNOWN' if committing or error.code == 'INTERNAL_ERROR' else 'DENIED', safe_code=error.code)
        except Exception:
            return ExecutionResult('UNKNOWN')
