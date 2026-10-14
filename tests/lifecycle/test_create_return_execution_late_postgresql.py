"""RE G7/G9 actual effect-boundary ordering and retention-safe recovery."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from time import sleep, monotonic
from uuid import uuid4
import jwt
import pytest
from sqlalchemy import select, text, update
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.core_return_mock import CoreReturnMock, Ticket
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from returnops_domain.return_execution_tables import controls, permissions, ledger
from returnops_domain.return_execution_sources import COMPONENT
from returnops_api.private_return_execution import compose_private_return_execution
from create_return_execution_helpers import ready, service, execute, reconcile, control, successes, rows, snapshot, evidence
from test_founder_approve_late_postgresql import _overlap_at_actual_fence


class LostResponse(CoreReturnMock):
    def perform(self, ticket, callback):
        result = super().perform(ticket, callback)
        assert result.status == 'FOUND'
        raise AcceptanceOutcomeUnknown()


def reserve(caller, arguments):
    result = caller._reserve(*(arguments[key] for key in ('case_id', 'expected_case_version', 'execution_work_id',
        'original_approval_key', 'candidate_command', 'correlation_id')))
    assert type(result) is Ticket
    return result


def purge(engine, case):
    original, = [row for row in rows(engine, old.history) if row['case_id'] == case and row['kind'] == 'STATEMENT']
    assert RetentionService(engine).remove('STATEMENT', original['object_id']) is True


def unchanged_except_confirmation(before, after):
    assert {name: value for name, value in before.items() if name not in {controls.name, old.audit.name, old.case_heads.name}} == {
        name: value for name, value in after.items() if name not in {controls.name, old.audit.name, old.case_heads.name}}
    prior, = before[old.case_heads.name]; current, = after[old.case_heads.name]
    assert {key: value for key, value in prior.items() if key not in {'audit_sequence', 'audit_head'}} == {
        key: value for key, value in current.items() if key not in {'audit_sequence', 'audit_head'}}
    assert current['audit_sequence'] == prior['audit_sequence'] + 1
    assert len(after[old.audit.name]) == len(before[old.audit.name]) + 1


@pytest.mark.parametrize('change', ['permission', 'session', 'retention'])
@pytest.mark.parametrize('first', ['change', 'mock'])
def test_RE_G7_actual_global_fence_orders_revocation_retention_against_effect(flow_engine, identities, enabled, request, monkeypatch, change, first):
    arguments, _ = ready(flow_engine, identities); caller = service(flow_engine, identities)
    ticket = reserve(caller, arguments)
    def mutate():
        if change == 'session':
            TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
        elif change == 'retention':
            purge(flow_engine, arguments['case_id'])
        else:
            with CustomerUnitOfWork(flow_engine, write=True) as uow:
                assert uow.execute(update(permissions).values(create_enabled=False, revision=2)).rowcount == 1
                uow.commit()
        return 'changed'
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch,
        dict(change=mutate, mock=lambda: CoreReturnMock(flow_engine).perform(ticket, caller.authority)), first=first)
    assert results['change'] == 'changed'
    assert results['mock'].status == ('FOUND' if first == 'mock' else 'DENIED')
    assert len(successes(flow_engine)) == (first == 'mock')
    assert control(flow_engine)['status'] == 'EXECUTING'
    evidence(request.node.nodeid, change=change, first=first, overlap=overlap,
        mock_status=results['mock'].status, ledger=rows(flow_engine, ledger), after=snapshot(flow_engine))


def test_RE_G7_actual_insert_db_clock_rejects_deadline_crossed_after_full_proof(flow_engine, identities, enabled, request, monkeypatch):
    arguments, _ = ready(flow_engine, identities)
    reached = []
    class Late(CoreReturnMock):
        def _insert(self, uow, row, actor, permission, bounds, outcome):
            before = uow.execute(select(text('clock_timestamp()'))).scalar_one()
            assert before < row['dispatch_deadline']
            while uow.execute(select(text('clock_timestamp()'))).scalar_one() < row['dispatch_deadline']:
                sleep(.02)
            at = uow.execute(select(text('clock_timestamp()'))).scalar_one()
            reached.append(dict(before=before, deadline=row['dispatch_deadline'], actual_at=at))
            return super()._insert(uow, row, actor, permission, bounds, outcome)
    result = execute(service(flow_engine, identities, mock_factory=Late), arguments)
    assert result.status == 'UNKNOWN' and len(reached) == 1 and rows(flow_engine, ledger) == []
    assert control(flow_engine)['status'] == 'EXECUTING'
    evidence(request.node.nodeid, result=asdict(result), actual_insert_boundary=reached, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['lock_timeout', 'connection_loss'])
def test_RE_G7_actual_t2_connection_lock_failures_are_unknown_without_effect(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities); caller = service(flow_engine, identities); ticket = reserve(caller, arguments)
    if fault == 'lock_timeout':
        with ThreadPoolExecutor(max_workers=1) as pool:
            with CustomerUnitOfWork(flow_engine, write=True) as holder:
                future = pool.submit(CoreReturnMock(flow_engine).perform, ticket, caller.authority)
                result = future.result(timeout=8)
                holder.commit()
    else:
        class LostConnection(CoreReturnMock):
            def _insert(self, uow, *args):
                uow.connection.invalidate()
                return super()._insert(uow, *args)
        result = LostConnection(flow_engine).perform(ticket, caller.authority)
    assert result.status == 'UNKNOWN' and rows(flow_engine, ledger) == []
    assert control(flow_engine)['status'] == 'EXECUTING'
    evidence(request.node.nodeid, fault=fault, result=asdict(result), after=snapshot(flow_engine))


def test_RE_G9_actual_retention_after_effect_allows_minimal_fact_only(flow_engine, identities, enabled, request, monkeypatch):
    from returnops_domain import return_execution as implementation, return_execution_sources as sources
    arguments, _ = ready(flow_engine, identities)
    assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    assert len(successes(flow_engine)) == 1
    purge(flow_engine, arguments['case_id'])
    before = snapshot(flow_engine); original = control(flow_engine); queries = []
    def forbidden(*args, **kwargs): raise AssertionError('No retained body/result reconstruction or OPERATION append')
    monkeypatch.setattr(implementation, 'project_result', forbidden)
    monkeypatch.setattr(sources, 'project_result', forbidden)
    monkeypatch.setattr(implementation, 'append_operation', forbidden)
    class QueryOnly(CoreReturnMock):
        def perform(self, ticket, callback):
            assert ticket.kind == 'QUERY'; queries.append(ticket.epoch)
            return super().perform(ticket, callback)
    caller = service(flow_engine, identities, mock_factory=QueryOnly)
    result = reconcile(caller, arguments)
    assert result.status == 'FACT_RECORDED' and result.provider_fact_status == 'SUCCEEDED'
    assert result.operation_state == 'EXECUTING' and result.record_id is None
    after = snapshot(flow_engine); unchanged_except_confirmation(before, after)
    current = control(flow_engine)
    assert current['result_record_id'] == original['result_record_id'] is None
    assert current['result_audit_id'] == original['result_audit_id'] is None
    assert current['source_available'] is current['result_retained'] is False
    assert current['confirmation_audit_id'] and current['confirmed_ledger_hash']
    replay = reconcile(caller, arguments)
    assert replay.status == 'FACT_REPLAYED' and snapshot(flow_engine) == after and len(queries) == 1
    assert len(successes(flow_engine)) == 1 and rows(flow_engine, life.effects) == []
    evidence(request.node.nodeid, before=before, after=after, result=asdict(result), replay=asdict(replay), query_epochs=queries)


def test_RE_G9_completed_result_retention_preserves_exact_tombstone_refs(flow_engine, identities, enabled, request, monkeypatch):
    from returnops_domain import return_execution as implementation, return_execution_sources as sources
    arguments, _ = ready(flow_engine, identities); caller = service(flow_engine, identities)
    result = execute(caller, arguments); assert result.status == 'COMMITTED'
    original = control(flow_engine); effect = rows(flow_engine, life.effects)
    purge(flow_engine, arguments['case_id']); before = snapshot(flow_engine)
    def forbidden(*args, **kwargs): raise AssertionError('No projection or history reconstruction after retention')
    monkeypatch.setattr(implementation, 'project_result', forbidden); monkeypatch.setattr(sources, 'project_result', forbidden)
    monkeypatch.setattr(implementation, 'append_operation', forbidden)
    replay = reconcile(caller, arguments)
    assert replay.status == 'REPLAYED' and snapshot(flow_engine) == before
    assert rows(flow_engine, life.effects) == effect
    current = control(flow_engine)
    assert current['result_record_id'] == original['result_record_id'] and current['result_audit_id'] == original['result_audit_id']
    assert current['confirmation_audit_id'] is None and current['source_available'] is current['result_retained'] is False
    evidence(request.node.nodeid, original_result=asdict(result), replay=asdict(replay), after_retention=before, effect_refs=effect)


def test_RE_G9_pre_call_crash_then_retention_not_found_never_creates_confirmation(flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities); caller = service(flow_engine, identities)
    reserve(caller, arguments); purge(flow_engine, arguments['case_id']); before = snapshot(flow_engine)
    result = reconcile(caller, arguments); after = snapshot(flow_engine)
    assert result.status == 'UNKNOWN' and rows(flow_engine, ledger) == []
    current = control(flow_engine)
    assert current['confirmed_effect_status'] is current['confirmation_audit_id'] is None
    assert current['status'] == 'EXECUTING' and current['source_available'] is False
    assert {name: value for name, value in after.items() if name != controls.name} == {name: value for name, value in before.items() if name != controls.name}
    evidence(request.node.nodeid, result=asdict(result), before=before, after=after, business_create_calls=0)


def test_RE_G9_retention_revokes_old_query_epoch_and_fresh_query_records_only_fact(flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities)
    assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    caller = service(flow_engine, identities)
    ticket = caller._query_claim(*(arguments[key] for key in ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')))
    assert type(ticket) is Ticket
    fact, = rows(flow_engine, ledger); purge(flow_engine, arguments['case_id']); before = snapshot(flow_engine)
    assert control(flow_engine)['query_epoch'] > ticket.epoch
    late = caller._accept(ticket, fact, 'retained-old-query')
    assert late.status == 'DENIED' and snapshot(flow_engine) == before
    fresh = reconcile(caller, arguments)
    assert fresh.status == 'FACT_RECORDED' and len(successes(flow_engine)) == 1
    unchanged_except_confirmation(before, snapshot(flow_engine))
    evidence(request.node.nodeid, old_epoch=ticket.epoch, late=asdict(late), fresh=asdict(fresh), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['effect_permission', 'query_permission', 'session', 'key', 'control_hash', 'fact_hash'])
def test_RE_G9_current_authority_and_original_fact_binding_guard_retained_confirmation(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    purge(flow_engine, arguments['case_id'])
    if fault == 'session': TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    elif fault == 'key': arguments['original_approval_key'] = 'replacement-recovery-key'
    else:
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            statement = (update(life.authorities).where(life.authorities.c.component_id == COMPONENT, life.authorities.c.purpose == 'EFFECT').values(enabled=False, revision=2)
                if fault == 'effect_permission' else update(permissions).values(query_enabled=False, revision=2)
                if fault == 'query_permission' else update(controls).values(binding_hash='0' * 64)
                if fault == 'control_hash' else update(ledger).values(fact_hash='0' * 64))
            assert uow.execute(statement).rowcount == 1; uow.commit()
    before = snapshot(flow_engine); result = reconcile(service(flow_engine, identities), arguments)
    assert result.status == 'DENIED' and snapshot(flow_engine) == before
    assert len(successes(flow_engine)) == 1 and control(flow_engine)['confirmation_audit_id'] is None
    evidence(request.node.nodeid, fault=fault, result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['audit_write', 'commit_before', 'commit_after'])
def test_RE_G9_minimal_confirmation_is_atomic_and_replay_uses_original_fact(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    purge(flow_engine, arguments['case_id']); calls = []
    class Fault(CustomerUnitOfWork):
        def execute(self, statement, parameters=None):
            if fault == 'audit_write' and getattr(statement, 'is_insert', False) and statement.table.name == old.audit.name:
                self.poison(); raise AcceptanceOutcomeUnknown()
            return super().execute(statement, parameters)
        def commit(self):
            if fault == 'commit_before': self.poison(); raise AcceptanceOutcomeUnknown()
            super().commit()
            if fault == 'commit_after': raise AcceptanceOutcomeUnknown()
    def factory(engine, **options):
        calls.append(len(calls) + 1)
        return (Fault if len(calls) == 2 else CustomerUnitOfWork)(engine, **options)
    result = reconcile(service(flow_engine, identities, uow_factory=factory), arguments)
    assert result.status == 'UNKNOWN'
    after = snapshot(flow_engine)
    if fault != 'commit_after':
        assert control(flow_engine)['confirmation_audit_id'] is None
        # Explicitly expire the abandoned query lease in this test; no create.
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            assert uow.execute(update(controls).values(query_lease_until=text("clock_timestamp() - interval '1 second'"))).rowcount == 1
            uow.commit()
    recovered = reconcile(service(flow_engine, identities), arguments)
    assert recovered.status == ('FACT_REPLAYED' if fault == 'commit_after' else 'FACT_RECORDED')
    assert len(successes(flow_engine)) == 1 and control(flow_engine)['result_record_id'] is None
    evidence(request.node.nodeid, fault=fault, result=asdict(result), recovered=asdict(recovered), after_unknown=after, final=snapshot(flow_engine))


def test_RE_G8_natural_approval_expiry_allows_current_query_but_never_new_create(flow_engine, identities, enabled, request):
    arguments, setup = ready(flow_engine, identities)
    assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    expires = datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z', '+00:00'))
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(update(life.authorities).where(life.authorities.c.component_id == COMPONENT,
            life.authorities.c.purpose == 'EXECUTION').values(enabled=False, revision=2)).rowcount == 1
        assert uow.execute(update(permissions).values(create_enabled=False, revision=2)).rowcount == 1
        uow.commit()
    started = monotonic()
    # Genuine wall-clock expiry, not an assigned fake source/approval status.
    while True:
        with flow_engine.connect() as connection:
            observed_now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        if observed_now >= expires:
            break
        assert 0 < (expires - observed_now).total_seconds() <= 301 and monotonic() - started < 330
        sleep(min(1, (expires - observed_now).total_seconds()))
    before = snapshot(flow_engine); calls = []
    class QueryOnly(CoreReturnMock):
        def perform(self, ticket, callback):
            assert ticket.kind == 'QUERY'; calls.append(ticket.kind)
            return super().perform(ticket, callback)
    result = reconcile(service(flow_engine, identities, mock_factory=QueryOnly), arguments)
    assert result.status == 'COMMITTED' and calls == ['QUERY'] and len(successes(flow_engine)) == 1
    assert control(flow_engine)['status'] == 'SUCCEEDED' and control(flow_engine)['query_epoch'] == 1
    evidence(request.node.nodeid, approval_expires_at=expires, actual_db_time=observed_now,
        create_permission_revoked=True, result=asdict(result), calls=calls, before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('found', [False, True])
def test_RE_G9_synthetic_terminal_metadata_after_real_retention_is_preserved(flow_engine, identities, enabled, request, found):
    """Preservation fixture only: not real post-APPROVE manual or sender acceptance."""
    arguments, _ = ready(flow_engine, identities)
    if found:
        assert execute(service(flow_engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
    else:
        reserve(service(flow_engine, identities), arguments)
    purge(flow_engine, arguments['case_id'])
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == arguments['case_id'])).mappings().one()
        state = uow.execute(select(life.state).where(life.state.c.case_id == arguments['case_id'])).mappings().one()
        # No HUMAN event or invented outcome/history record. Nullable record
        # pointers remain absent; the seeded work pointer refers to a real
        # test-only paused work row, never a sent notification.
        work_id = 'synthetic_terminal_notice_work'
        uow.execute(life.work.insert().values(work_id=work_id, case_id=arguments['case_id'],
            component_id='test-only-terminal-fixture', store_id=head['store_id'], owner_id=head['owner_principal_id'],
            purpose='NOTIFICATION', input_version=head['input_version'], generation=state['generation'],
            target_hash='a' * 64, target_record_id=None, state='PAUSED', claim_id=None, epoch=0,
            claimed_case_version=None, authority_revision=None, idempotency_key='synthetic-terminal-notice-key',
            lease_expires_at=None, created_at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()))
        assert uow.execute(update(life.state).where(life.state.c.case_id == arguments['case_id']).values(
            outcome='MANUAL_HANDLED', notification_id='synthetic_terminal_notice',
            notification_hash='b' * 64, notification_work_id=work_id)).rowcount == 1
        assert uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == arguments['case_id'])
            .values(status='MANUAL_HANDLED')).rowcount == 1
        uow.commit()
    before = snapshot(flow_engine)
    result = reconcile(service(flow_engine, identities), arguments)
    after = snapshot(flow_engine)
    assert result.status == ('FACT_RECORDED' if found else 'UNKNOWN')
    assert after[life.state.name] == before[life.state.name] and after[life.work.name] == before[life.work.name]
    if found:
        unchanged_except_confirmation(before, after)
    else:
        assert {name: value for name, value in after.items() if name != controls.name} == {
            name: value for name, value in before.items() if name != controls.name}
    assert len(successes(flow_engine)) == int(found)
    evidence(request.node.nodeid, acceptance_origin='TEST_ONLY_SYNTHETIC',
        proves='historical query does not overwrite seeded protected state after actual retention',
        found=found, result=asdict(result), before=before, after=after)


OBSERVATIONS = ('execute_result', 'query_result', 'accept_result', 'query_fact',
                'execute_pending', 'query_active', 'query_missing')


def observation_setup(engine, identities, branch):
    """Actual N1/N2/retention state; no assigned operation result or expiry."""
    arguments, _ = ready(engine, identities)
    caller = service(engine, identities)
    ticket = None
    fact = None
    if branch in {'execute_result', 'query_result', 'accept_result'}:
        ticket = reserve(caller, arguments)
        assert caller._perform(ticket, arguments['correlation_id']).status == 'COMMITTED'
        fact, = rows(engine, ledger)
    elif branch == 'query_fact':
        assert execute(service(engine, identities, mock_factory=LostResponse), arguments).status == 'UNKNOWN'
        purge(engine, arguments['case_id'])
        assert reconcile(caller, arguments).status == 'FACT_RECORDED'
    elif branch in {'execute_pending', 'query_active'}:
        reserve(caller, arguments)
        if branch == 'query_active':
            ticket = caller._query_claim(*(arguments[key] for key in
                ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')))
            assert type(ticket) is Ticket
    else:
        assert branch == 'query_missing' and rows(engine, controls) == []
    def invoke(observing):
        if branch.startswith('execute_'):
            return execute(observing, arguments)
        if branch == 'accept_result':
            return observing._accept(ticket, fact, arguments['correlation_id'])
        return reconcile(observing, arguments)
    expected = ('REPLAYED' if branch.endswith('_result') else 'FACT_REPLAYED' if branch == 'query_fact'
                else 'UNKNOWN' if branch == 'query_missing' else 'IN_PROGRESS')
    before = snapshot(engine)
    assert invoke(caller).status == expected
    assert snapshot(engine) == before
    return arguments, invoke, expected


def short_observer(engine, identities, **options):
    """Legitimate new current session; original session/source dates are untouched."""
    with engine.connect() as connection:
        now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    issued = int(now.timestamp())
    expires = issued + 20
    session_id = 'observe_' + uuid4().hex
    principal_id = identities.people['founder']['principal_id']
    TrustedRegistry(engine).register_session(principal_id, session_id, issued, issued, expires)
    config = identities.auth_config
    token = jwt.encode(dict(iss=config.issuer, aud=config.audience, sub=principal_id,
        jti=session_id, iat=issued, nbf=issued, exp=expires), config.signing_key, algorithm='HS256')
    caller = compose_private_return_execution(engine, config, 'Bearer ' + token, **options)
    return caller, session_id, expires


@pytest.mark.parametrize('branch', OBSERVATIONS)
def test_RE_G7_observation_rechecks_actual_session_expiry_after_final_ledger_read(
        flow_engine, identities, enabled, request, monkeypatch, branch):
    from returnops_domain.return_execution import ReturnExecutionService
    _, invoke, original_status = observation_setup(flow_engine, identities, branch)
    provider_calls = []
    class NoProvider(CoreReturnMock):
        def perform(self, *args):
            provider_calls.append(True)
            raise AssertionError('An observation must not call create or query')
    caller, session_id, expires = short_observer(flow_engine, identities, mock_factory=NoProvider)
    before = snapshot(flow_engine)
    original = ReturnExecutionService._observation_seal
    reads = []
    boundary = []
    def slow_last_read(uow, case_id):
        value = original(uow, case_id)
        reads.append(len(reads) + 1)
        if len(reads) == 3:
            start = monotonic()
            first = uow.execute(text('SELECT clock_timestamp()')).scalar_one()
            assert first.timestamp() < expires
            while True:
                at = uow.execute(text('SELECT clock_timestamp()')).scalar_one()
                if at.timestamp() >= expires:
                    break
                assert monotonic() - start < 22
                sleep(.02)
            boundary.append(dict(before=first, expires_at=expires, actual_at=at))
        return value
    monkeypatch.setattr(ReturnExecutionService, '_observation_seal', staticmethod(slow_last_read))
    result = invoke(caller)
    assert reads == [1, 2, 3] and len(boundary) == 1
    assert result.status == 'UNKNOWN' and result.operation_id is None
    assert provider_calls == [] and snapshot(flow_engine) == before
    evidence(request.node.nodeid, branch=branch, original_status=original_status,
        legitimate_new_session=session_id, actual_expiry_boundary=boundary, result=asdict(result),
        before=before, after=snapshot(flow_engine), provider_calls=0)


@pytest.mark.parametrize('revocation', ['session', 'effect', 'query'])
def test_RE_G7_observation_fresh_registry_and_grants_after_proof(
        flow_engine, identities, enabled, request, monkeypatch, revocation):
    from returnops_domain.return_execution import ReturnExecutionService
    _, invoke, _ = observation_setup(flow_engine, identities, 'query_result')
    caller = service(flow_engine, identities)
    before = snapshot(flow_engine)
    original = ReturnExecutionService._observation_seal
    reads = []
    def revoke_after_proof(uow, case_id):
        value = original(uow, case_id)
        reads.append(len(reads) + 1)
        if len(reads) == 2:
            # Trusted fault injection inside this fenced transaction. It proves
            # a fresh DB read, not that another trusted writer bypasses the fence.
            statement = (update(old.sessions).where(old.sessions.c.session_id ==
                identities.sessions['founder']['session_id']).values(revoked=True)
                if revocation == 'session' else update(life.authorities).where(
                    life.authorities.c.component_id == COMPONENT, life.authorities.c.purpose == 'EFFECT')
                    .values(enabled=False, revision=2) if revocation == 'effect'
                else update(permissions).values(query_enabled=False, revision=2))
            assert uow.execute(statement).rowcount == 1
        return value
    monkeypatch.setattr(ReturnExecutionService, '_observation_seal', staticmethod(revoke_after_proof))
    result = invoke(caller)
    assert reads == [1, 2] and result.status == 'UNKNOWN' and result.operation_id is None
    # The rejected transaction also rolls back the injected registry change.
    assert snapshot(flow_engine) == before and len(successes(flow_engine)) == 1
    evidence(request.node.nodeid, revocation=revocation, injection='same-transaction-after-proof',
        result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('branch', OBSERVATIONS)
@pytest.mark.parametrize('fault', ['commit_before', 'commit_after', 'close_after'])
def test_RE_G4_observation_requires_confirmed_commit_and_close(
        flow_engine, identities, enabled, request, branch, fault):
    _, invoke, original_status = observation_setup(flow_engine, identities, branch)
    before = snapshot(flow_engine)
    checks = []
    class Fault(CustomerUnitOfWork):
        def commit(self):
            checks.append('commit')
            if fault == 'commit_before':
                self.poison()
                raise AcceptanceOutcomeUnknown()
            super().commit()
            checks.append('committed')
            if fault == 'commit_after':
                raise AcceptanceOutcomeUnknown()
        def __exit__(self, kind, value, trace):
            result = super().__exit__(kind, value, trace)
            checks.append('closed')
            if fault == 'close_after' and kind is None:
                raise AcceptanceOutcomeUnknown()
            return result
    result = invoke(service(flow_engine, identities, uow_factory=Fault))
    assert result.status == 'UNKNOWN' and result.operation_id is None
    assert checks == (['commit', 'closed'] if fault == 'commit_before' else ['commit', 'committed', 'closed'])
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, branch=branch, original_status=original_status,
        fault=fault, transaction_observations=checks, result=asdict(result), before=before, after=snapshot(flow_engine))


def test_RE_G8_existing_execute_replay_needs_only_current_query_authority(
        flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities)
    caller = service(flow_engine, identities)
    assert execute(caller, arguments).status == 'COMMITTED'
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(update(life.authorities).where(life.authorities.c.component_id == COMPONENT,
            life.authorities.c.purpose == 'EXECUTION').values(enabled=False, revision=2)).rowcount == 1
        assert uow.execute(update(permissions).values(create_enabled=False, revision=2)).rowcount == 1
        uow.commit()
    before = snapshot(flow_engine)
    result = execute(caller, arguments)
    assert result.status == 'REPLAYED' and snapshot(flow_engine) == before and len(successes(flow_engine)) == 1
    evidence(request.node.nodeid, create_authority_revoked=True, result=asdict(result), before=before, after=snapshot(flow_engine))
