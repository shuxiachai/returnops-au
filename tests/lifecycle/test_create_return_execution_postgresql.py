"""RE G1-G4/G8/G10 actual cloud PostgreSQL, never collection-as-execution."""
from copy import deepcopy
from dataclasses import asdict
import pytest
from sqlalchemy import inspect, select, text, update
from returnops_domain import customer_tables as old, lifecycle_tables as life, storage
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.execution_preparation_tables import preparations
from returnops_domain.lifecycle_schema import PREPARATION, EXECUTION, version
from returnops_domain.return_execution_tables import metadata, controls, permissions, ledger
from returnops_domain.return_execution_sources import COMPONENT
from returnops_domain.registry import TrustedRegistry
from create_return_execution_helpers import (ready, provision, service, execute, reconcile, control,
    successes, assert_complete, rows, snapshot, evidence)
from preparation_helpers import service as preparation_service
from approve_helpers import approve
from conftest import migrate


@pytest.mark.parametrize('flow_engine', [PREPARATION], indirect=True)
def test_RE_G1_retained0010_upgrade_and_original_approval_preparation_replay(flow_engine, identities, enabled, request):
    arguments, setup = ready(flow_engine, identities, grants=False)
    before = snapshot(flow_engine)
    migrate(flow_engine, EXECUTION); migrate(flow_engine, EXECUTION)
    after = snapshot(flow_engine)
    assert set(after) - set(before) == set(metadata.tables)
    assert all(after[name] == [] for name in metadata.tables)
    assert {name: value for name, value in after.items() if name not in {*metadata.tables, 'alembic_version'}} == {
        name: value for name, value in before.items() if name != 'alembic_version'}
    with flow_engine.connect() as connection:
        assert version(connection) == EXECUTION and inspect(connection).get_foreign_keys(ledger.name) == []
    approval = approve(flow_engine, identities).accept(setup['case'], setup['request'], arguments['original_approval_key'], 'replay-old-approval')
    prepared = preparation_service(flow_engine, identities).prepare(**arguments)
    assert approval.receipt == setup['result'].receipt and prepared.status == 'REPLAYED'
    assert prepared.operation_id == setup['preparation'].operation_id and snapshot(flow_engine) == after
    evidence(request.node.nodeid, before0010=before, after0011=after, approval=asdict(approval), preparation=asdict(prepared))


@pytest.mark.parametrize('flow_engine', [PREPARATION], indirect=True)
def test_RE_G1_upgrade_requires_exact_complete0010_descriptor(flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities, grants=False)
    with flow_engine.begin() as connection:
        connection.execute(text('ALTER TABLE lifecycle_execution_preparations DROP CONSTRAINT ck_preparation_command'))
    before = snapshot(flow_engine)
    with pytest.raises(RuntimeError, match='exact complete 0010'):
        migrate(flow_engine, EXECUTION)
    assert snapshot(flow_engine) == before and not set(metadata.tables) & set(inspect(flow_engine).get_table_names())
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), rejected_incomplete0010=True)


@pytest.mark.parametrize('fault', ['extra_table', 'nullable', 'collation', 'missing_check', 'weaker_check', 'ledger_fk', 'unvalidated_fk', 'extra_index'])
def test_RE_G1_exact0011_descriptor_rejects_counterfeit_schema(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    mutations = {
        'extra_table': 'CREATE TABLE unexpected_return_table (id integer)',
        'nullable': 'ALTER TABLE lifecycle_return_execution_controls ALTER COLUMN binding_hash DROP NOT NULL',
        'collation': 'ALTER TABLE lifecycle_return_execution_controls ALTER COLUMN binding_hash TYPE varchar(64) COLLATE "C"',
        'missing_check': 'ALTER TABLE core_mock_return_ledger DROP CONSTRAINT ck_mock_return_status',
        'weaker_check': "ALTER TABLE core_mock_return_ledger DROP CONSTRAINT ck_mock_return_status; ALTER TABLE core_mock_return_ledger ADD CONSTRAINT ck_mock_return_status CHECK (status <> '')",
        'ledger_fk': 'ALTER TABLE core_mock_return_ledger ADD CONSTRAINT forbidden_mock_fk FOREIGN KEY (dispatch_record_id) REFERENCES customer_history_revisions(record_id)',
        'unvalidated_fk': 'ALTER TABLE lifecycle_return_execution_controls DROP CONSTRAINT fk_return_control_case_id; ALTER TABLE lifecycle_return_execution_controls ADD CONSTRAINT fk_return_control_case_id FOREIGN KEY (case_id) REFERENCES case_heads(case_id) NOT VALID',
        'extra_index': 'CREATE INDEX unexpected_mock_index ON core_mock_return_ledger (store_id)',
    }
    with flow_engine.begin() as connection:
        for statement in mutations[fault].split('; '):
            connection.execute(text(statement))
        assert version(connection) is None
    before = snapshot(flow_engine); result = execute(service(flow_engine, identities), arguments)
    assert result.status == 'DENIED' and snapshot(flow_engine) == before and successes(flow_engine) == []
    evidence(request.node.nodeid, fault=fault, result=asdict(result), before=before, after=snapshot(flow_engine))


def test_RE_G2_G10_full_actual_source_sql_effect_domain_result_and_exact_T2_delta(flow_engine, identities, enabled, request):
    arguments, setup = ready(flow_engine, identities); before = snapshot(flow_engine); observations = []
    class Observed(CoreReturnMock):
        def perform(self, ticket, callback):
            initial = snapshot(self.engine)
            result = super().perform(ticket, callback)
            final = snapshot(self.engine)
            assert {name: value for name, value in final.items() if name != ledger.name} == {
                name: value for name, value in initial.items() if name != ledger.name}
            assert len(final[ledger.name]) == len(initial[ledger.name]) + 1
            observations.append(dict(before=initial, after=final))
            return result
    caller = service(flow_engine, identities, mock_factory=Observed)
    result = execute(caller, arguments); after = assert_complete(flow_engine, arguments, result, before)
    assert len(observations) == 1
    replay = execute(caller, arguments)
    assert replay.status == 'REPLAYED' and snapshot(flow_engine) == after and len(observations) == 1
    n1 = preparation_service(flow_engine, identities).prepare(**arguments)
    assert n1.status == 'REPLAYED' and n1.operation_id == result.operation_id and snapshot(flow_engine) == after
    original = approve(flow_engine, identities).accept(setup['case'], setup['request'], arguments['original_approval_key'], 'original-approval-after-effect')
    assert original.receipt == setup['result'].receipt and snapshot(flow_engine) == after
    evidence(request.node.nodeid, result=asdict(result), replay=asdict(replay), actual_T2=observations, after=after,
        stop='operation SUCCEEDED; case ACTION_IN_PROGRESS; no label/outcome/notification')


@pytest.mark.parametrize('fault', ['no_session', 'customer', 'wrong_key', 'wrong_version', 'changed_command',
    'revoked_session', 'owner_disabled', 'execution_revoked', 'effect_revoked', 'provider_revoked', 'query_revoked', 'provider_config', 'source_changed'])
def test_RE_G3_denied_identity_role_scope_source_and_permission_have_zero_effect(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities)
    name = None if fault == 'no_session' else 'customer_a' if fault == 'customer' else 'founder'
    if fault == 'wrong_key': arguments['original_approval_key'] = 'replacement-original-key'
    elif fault == 'wrong_version': arguments['expected_case_version'] += 1
    elif fault == 'changed_command': arguments['candidate_command']['parameters']['line_items'][0]['quantity'] += 1
    elif fault == 'revoked_session': TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    elif fault == 'owner_disabled': TrustedRegistry(flow_engine).change_principal(identities.people['customer_a']['principal_id'], enabled=False)
    elif fault in {'execution_revoked', 'effect_revoked', 'provider_revoked', 'query_revoked', 'provider_config', 'source_changed'}:
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            if fault in {'execution_revoked', 'effect_revoked'}:
                statement = update(life.authorities).where(life.authorities.c.component_id == COMPONENT,
                    life.authorities.c.purpose == ('EXECUTION' if fault == 'execution_revoked' else 'EFFECT')).values(enabled=False, revision=2)
            elif fault.startswith('provider') or fault == 'query_revoked':
                changes = {'create_enabled': False, 'revision': 2} if fault == 'provider_revoked' else {'query_enabled': False, 'revision': 2} if fault == 'query_revoked' else {'config_hash': '0' * 64}
                statement = update(permissions).values(**changes)
            else:
                statement = update(storage.original_statement_contents).values(raw_text=b'changed retained customer source')
            assert uow.execute(statement).rowcount == 1; uow.commit()
    before = snapshot(flow_engine); result = execute(service(flow_engine, identities, name), arguments)
    assert result.status == ('UNKNOWN' if fault == 'wrong_key' else 'DENIED') and snapshot(flow_engine) == before
    assert rows(flow_engine, controls) == [] and rows(flow_engine, ledger) == []
    evidence(request.node.nodeid, fault=fault, result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('fault', ['t1_before_commit', 't1_after_commit', 't1_close', 't2_lost_response', 't3_before_commit', 't3_after_commit', 't3_close'])
def test_RE_G4_G8_commit_close_and_lost_response_never_repeat_business_effect(flow_engine, identities, enabled, request, fault):
    arguments, _ = ready(flow_engine, identities); domain_calls = []; mock_calls = []
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if fault.endswith('before_commit'):
                self.poison(); raise AcceptanceOutcomeUnknown()
            super().commit()
            if fault.endswith('after_commit'):
                raise AcceptanceOutcomeUnknown()
        def __exit__(self, *args):
            result = super().__exit__(*args)
            if fault.endswith('close'):
                raise AcceptanceOutcomeUnknown()
            return result
    def factory(engine, **options):
        domain_calls.append(len(domain_calls) + 1)
        selected = (fault.startswith('t1') and len(domain_calls) == 1) or (fault.startswith('t3') and len(domain_calls) == 2)
        return (Fault if selected else CustomerUnitOfWork)(engine, **options)
    class Observed(CoreReturnMock):
        def perform(self, ticket, callback):
            mock_calls.append(ticket.kind)
            result = super().perform(ticket, callback)
            if fault == 't2_lost_response': raise AcceptanceOutcomeUnknown()
            return result
    before = snapshot(flow_engine)
    result = execute(service(flow_engine, identities, uow_factory=factory, mock_factory=Observed), arguments)
    assert result.status == 'UNKNOWN', asdict(result)
    initial_effects = len(successes(flow_engine))
    assert initial_effects == (0 if fault.startswith('t1') else 1)
    assert len(mock_calls) == (0 if fault.startswith('t1') else 1)
    after_unknown = snapshot(flow_engine)
    recovered = reconcile(service(flow_engine, identities), arguments)
    assert len(successes(flow_engine)) == initial_effects
    if initial_effects:
        assert recovered.status in {'COMMITTED', 'REPLAYED'} and control(flow_engine)['status'] == 'SUCCEEDED'
        assert len([r for r in rows(flow_engine, old.history) if r['kind'] == 'OPERATION']) == 3
    else:
        assert recovered.status == 'UNKNOWN'
        if fault != 't1_before_commit':
            assert control(flow_engine)['status'] == 'EXECUTING'
            assert len([r for r in rows(flow_engine, old.history) if r['kind'] == 'OPERATION']) == 2
    evidence(request.node.nodeid, fault=fault, result=asdict(result), recovered=asdict(recovered),
        before=before, after_unknown=after_unknown, after_recovery=snapshot(flow_engine), create_calls=mock_calls)


def test_RE_G8_expired_query_claim_cannot_overwrite_new_epoch(flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities)
    class Lost(CoreReturnMock):
        def perform(self, ticket, callback):
            super().perform(ticket, callback); raise AcceptanceOutcomeUnknown()
    assert execute(service(flow_engine, identities, mock_factory=Lost), arguments).status == 'UNKNOWN'
    caller = service(flow_engine, identities)
    query_args = [arguments[key] for key in ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')]
    first = caller._query_claim(*query_args)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert uow.execute(update(controls).where(controls.c.query_epoch == first.epoch)
            .values(query_lease_until=text("clock_timestamp() - interval '1 second'"))).rowcount == 1
        uow.commit()
    second = caller._query_claim(*query_args)
    assert second.epoch == first.epoch + 1 and second.claim_id != first.claim_id
    fact, = rows(flow_engine, ledger); before = snapshot(flow_engine)
    late = caller._accept(first, fact, 'late-old-query')
    assert late.status == 'DENIED' and snapshot(flow_engine) == before
    current = caller._perform(second, 'current-query')
    assert current.status == 'COMMITTED' and len(successes(flow_engine)) == 1
    evidence(request.node.nodeid, first_epoch=first.epoch, second_epoch=second.epoch,
        late=asdict(late), current=asdict(current), before=before, after=snapshot(flow_engine))


def test_RE_G8_typed_confirmed_no_effect_failure_is_durable_and_never_retried(flow_engine, identities, enabled, request):
    arguments, _ = ready(flow_engine, identities); calls = []
    class NoEffect(CoreReturnMock):
        def _outcome(self, row, command): calls.append('actual guarded no-effect ledger'); return 'FAILED'
    caller = service(flow_engine, identities, mock_factory=NoEffect)
    result = execute(caller, arguments)
    assert result.status == 'COMMITTED' and result.operation_state == 'FAILED'
    assert successes(flow_engine) == [] and len(rows(flow_engine, ledger)) == 1
    after = snapshot(flow_engine); again = execute(caller, arguments)
    assert again.status == 'REPLAYED' and snapshot(flow_engine) == after and len(calls) == 1
    evidence(request.node.nodeid, result=asdict(result), replay=asdict(again), ledger=rows(flow_engine, ledger), calls=calls)


@pytest.mark.parametrize('phase', ['T1', 'T3'])
@pytest.mark.parametrize('point', range(1, 9))
def test_RE_G4_each_domain_write_rolls_back_without_erasing_independent_effect(flow_engine, identities, enabled, request, phase, point):
    arguments, _ = ready(flow_engine, identities); writes = []; calls = []
    class Fault(CustomerUnitOfWork):
        def execute(self, statement, parameters=None):
            if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                writes.append(statement.table.name)
                if len(writes) == point:
                    self.poison(); raise AcceptanceOutcomeUnknown()
            return super().execute(statement, parameters)
    def no_mock(*args): calls.append('unexpected'); raise AssertionError('Uncommitted reservation cannot dispatch')
    if phase == 'T1':
        before = snapshot(flow_engine)
        result = execute(service(flow_engine, identities, uow_factory=Fault, mock_factory=no_mock), arguments)
    else:
        class Lost(CoreReturnMock):
            def perform(self, ticket, callback):
                value = super().perform(ticket, callback); assert value.status == 'FOUND'; raise AcceptanceOutcomeUnknown()
        assert execute(service(flow_engine, identities, mock_factory=Lost), arguments).status == 'UNKNOWN'
        normal = service(flow_engine, identities)
        ticket = normal._query_claim(*(arguments[key] for key in ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')))
        fact, = rows(flow_engine, ledger); before = snapshot(flow_engine)
        result = service(flow_engine, identities, uow_factory=Fault)._accept(ticket, fact, 'each-result-write')
    assert result.status == 'UNKNOWN' and len(writes) == point and calls == []
    assert snapshot(flow_engine) == before and len(successes(flow_engine)) == (phase == 'T3')
    evidence(request.node.nodeid, phase=phase, point=point, attempted_writes=writes, result=asdict(result), before=before, after=snapshot(flow_engine))


# C12 cloud-only additions; the shared flow_engine consumes its indirect request.param.
class _C12ReturnCatalogConnection:
    def __init__(self, connection, *, fail_structural=False):
        self.connection = connection
        self.calls = []
        self.fail_structural = fail_structural
        self.errors = []

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, statement, parameters=None):
        parameters = dict(parameters or {})
        self.calls.append((str(statement), parameters))
        expected = dict(control_name='lifecycle_return_execution_controls',
                        permission_name='return_provider_permissions', ledger_name='core_mock_return_ledger')
        if self.fail_structural and parameters == expected and 'SELECT jsonb_build_object(' in str(statement):
            try:
                return self.connection.execute(text('SELECT 1 / 0'))
            except Exception as error:
                self.errors.append(error)
                raise
        return self.connection.execute(statement, parameters) if parameters else self.connection.execute(statement)


@pytest.mark.parametrize('flow_engine,expected_revision', [
    ('0011_return_execution', '0011_return_execution'),
    ('0012_label_execution', '0012_label_execution'),
    ('0013_label_artifact_result', '0013_label_artifact_result'),
    ('0014_notification_delivery', '0014_notification_delivery'),
], indirect=['flow_engine'])
def test_C12_return_batch_supported_versions_have_one_real_structural_query(flow_engine, expected_revision):
    from returnops_domain.return_execution_schema import descriptor
    with flow_engine.connect() as connection:
        assert version(connection) == expected_revision
        observed = _C12ReturnCatalogConnection(connection)
        assert descriptor(observed) is True
        assert len(observed.calls) == 1
        sql, parameters = observed.calls[0]
        assert parameters == dict(control_name='lifecycle_return_execution_controls',
                                  permission_name='return_provider_permissions', ledger_name='core_mock_return_ledger')
        assert 'n.nspname=current_schema()' in sql and "'table_name', r.relname" in sql


@pytest.mark.parametrize('table_name', ['lifecycle_return_execution_controls', 'return_provider_permissions',
                                       'core_mock_return_ledger'])
def test_C12_return_batch_rereads_every_table_after_ddl_and_rollback(flow_engine, table_name):
    from returnops_domain.return_execution_schema import descriptor
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        transaction = connection.begin()
        observed = _C12ReturnCatalogConnection(connection)
        try:
            assert version(connection) == '0014_notification_delivery'
            assert descriptor(observed) is True
            connection.execute(text('ALTER TABLE ' + quote(table_name) + ' ADD COLUMN c12_unexpected integer'))
            assert descriptor(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert descriptor(observed) is True and version(connection) == '0014_notification_delivery'
        assert len(observed.calls) == 3


@pytest.mark.parametrize('table_name', ['lifecycle_return_execution_controls', 'return_provider_permissions',
                                       'core_mock_return_ledger'])
def test_C12_return_batch_cannot_borrow_a_same_named_relation_from_another_schema(flow_engine, table_name):
    from uuid import uuid4
    from returnops_domain.return_execution_schema import descriptor
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        current_schema = quote(flow_engine._customer_test_schema)
        shadow = quote('c12_shadow_' + uuid4().hex)
        transaction = connection.begin()
        observed = _C12ReturnCatalogConnection(connection)
        try:
            assert descriptor(observed) is True
            connection.execute(text('CREATE SCHEMA ' + shadow))
            connection.execute(text('CREATE TABLE ' + shadow + '.' + quote(table_name) +
                                    ' (LIKE ' + current_schema + '.' + quote(table_name) + ' INCLUDING ALL)'))
            connection.execute(text('SET LOCAL search_path TO ' + current_schema + ', ' + shadow))
            connection.execute(text('ALTER TABLE ' + current_schema + '.' + quote(table_name) +
                                    ' RENAME TO c12_displaced_relation'))
            assert descriptor(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert descriptor(observed) is True
        assert len(observed.calls) == 3


def test_C12_return_batch_propagates_real_driver_failure_and_reads_after_rollback(flow_engine):
    from sqlalchemy.exc import DBAPIError
    from returnops_domain.return_execution_schema import descriptor
    before = snapshot(flow_engine)
    with flow_engine.connect() as connection:
        transaction = connection.begin()
        observed = _C12ReturnCatalogConnection(connection, fail_structural=True)
        try:
            with pytest.raises(DBAPIError) as caught:
                descriptor(observed)
            assert len(observed.calls) == len(observed.errors) == 1
            assert caught.value is observed.errors[0]
        finally:
            transaction.rollback()
        observed.fail_structural = False
        assert descriptor(observed) is True and len(observed.calls) == 2
    assert snapshot(flow_engine) == before


@pytest.mark.parametrize('entry', ['execute', 'reconcile'])
def test_C12_return_catalog_driver_failure_keeps_unknown_without_retry_or_effect(flow_engine, identities, enabled, request, entry):
    arguments, _ = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    observed_connections = []
    mock_calls = []
    class Fault(CustomerUnitOfWork):
        def __enter__(self):
            super().__enter__()
            self.connection = _C12ReturnCatalogConnection(self.connection, fail_structural=True)
            observed_connections.append(self.connection)
            return self
    def no_mock(*args):
        mock_calls.append('unexpected')
        raise AssertionError('A failed catalog read cannot authorize a provider call')
    caller = service(flow_engine, identities, uow_factory=Fault, mock_factory=no_mock)
    result = execute(caller, arguments) if entry == 'execute' else reconcile(caller, arguments)
    assert result.status == 'UNKNOWN'
    assert sum(len(connection.errors) for connection in observed_connections) == 1
    assert mock_calls == [] and successes(flow_engine) == [] and snapshot(flow_engine) == before
    evidence(request.node.nodeid, entry=entry, result=asdict(result), before=before, after=snapshot(flow_engine),
             catalog_errors=1, automatic_retry=False, provider_calls=mock_calls)
