"""No database: immutable keys, guarded orchestration and exact schema shape."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from returnops_domain import founder_codec as finite
from returnops_api.private_return_execution import compose_private_return_execution
from returnops_api.security.authentication import AuthConfig
from returnops_domain.canonical import canonical_bytes, digest
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.core_return_mock import Ticket
from returnops_domain.return_execution import ReturnExecutionService, ExecutionResult
from returnops_domain.return_execution_sources import control_payload, accepted_payload, stable, verify_fact, ledger_payload, project_result
from returnops_domain.return_execution_tables import controls, permissions, ledger, CONTROL_IDS, CONTROL_HASHES, CONTROL_NUMBERS
from test_approval_admission_offline import command


def reservation():
    at = datetime(2026, 10, 14, tzinfo=timezone.utc)
    value = {name: name + '_original' for name in CONTROL_IDS}
    value.update({name: '1' * 64 for name in CONTROL_HASHES})
    value.update({name: 1 for name in CONTROL_NUMBERS})
    value.update(effect_key='effect_original', dispatch_at=at, dispatch_deadline=at + timedelta(seconds=30))
    return value


@pytest.mark.parametrize('field', ['operation_id', 'first_record_id', 'dispatch_record_id', 'request_fingerprint',
    'original_key_hash', 'config_hash', 'provider_revision', 'dispatch_deadline'])
def test_RE_G1_G3_original_dispatch_binding_covers_every_effect_identity(field):
    row = reservation(); original = digest(control_payload(row), 'return-reservation/v1')
    row[field] = row[field] + timedelta(seconds=1) if field == 'dispatch_deadline' else 2 if field == 'provider_revision' else 'replacement'
    assert digest(control_payload(row), 'return-reservation/v1') != original


def test_RE_G1_G10_independent_ledger_has_no_domain_fk_or_command_body_and_no_defaults():
    assert not ledger.foreign_key_constraints
    assert not {'command', 'parameters', 'body', 'token', 'original_key'} & set(ledger.columns.keys())
    assert not {'command', 'parameters', 'body', 'token', 'original_key'} & set(controls.columns.keys())
    assert all(column.server_default is None and column.default is None
               for table in (controls, permissions, ledger) for column in table.columns)
    compiled = str(CreateTable(ledger).compile(dialect=postgresql.dialect()))
    assert 'FOREIGN KEY' not in compiled and 'UNIQUE (operation_id)' in compiled and 'PRIMARY KEY (effect_key)' in compiled


@pytest.mark.parametrize('status', ['SUCCEEDED', 'FAILED'])
def test_RE_G2_G7_ledger_metadata_keys_are_plain_strings_without_value_coercion(status):
    expected = dict(effect_key='effect_original', store_id='store_original',
        provider_id='provider-mock-return', config_id='core-return-sql-v1', config_hash='1' * 64,
        operation_id='operation_original', dispatch_record_id='dispatch_original',
        dispatch_binding_hash='2' * 64, operation_fingerprint='3' * 64,
        provider_operation_id='mock_return_original', parcel_id='parcel_original', status=status,
        provider_return_id='return_original' if status == 'SUCCEEDED' else None,
        error_code=None if status == 'SUCCEEDED' else 'INTERNAL_ERROR',
        accepted_at='2026-10-14T00:00:00.000000Z')
    row = {**expected, 'accepted_at': datetime(2026, 10, 14, tzinfo=timezone.utc), 'fact_hash': '4' * 64}
    before = dict(row)
    # Use the real SQLAlchemy ledger metadata: its column keys are quoted_name
    # str subclasses, while the unchanged typed codec admits exact str only.
    raw_keys = {name: expected[name] for name in ledger.columns.keys() if name != 'fact_hash'}
    assert set(raw_keys) == set(expected) and any(type(name) is not str for name in raw_keys)
    with pytest.raises(FlowError) as rejected:
        digest(raw_keys, 'core-return-fact/v1')
    assert rejected.value.code == 'VALIDATION_ERROR'
    payload = ledger_payload(row)
    assert payload == expected and all(type(name) is str for name in payload)
    assert canonical_bytes(payload, 'core-return-fact/v1') == canonical_bytes(expected, 'core-return-fact/v1')
    assert digest(payload, 'core-return-fact/v1') == digest(expected, 'core-return-fact/v1')
    assert row == before and row['accepted_at'] is before['accepted_at']
    class UnsupportedString(str):
        pass
    for unsupported in (UnsupportedString('parcel_original'), object()):
        changed = {**row, 'parcel_id': unsupported}
        projected = ledger_payload(changed)
        assert projected['parcel_id'] is unsupported and changed['parcel_id'] is unsupported
        with pytest.raises(FlowError) as rejected:
            digest(projected, 'core-return-fact/v1')
        assert rejected.value.code == 'VALIDATION_ERROR'


def test_RE_G2_G9_result_projection_keeps_wire_result_and_finite_history_profiles_separate():
    fact = dict(status='SUCCEEDED', provider_return_id='return_original', parcel_id='parcel_original')
    before = dict(fact)
    expected = dict(type='CREATE_RETURN', provider_return_id='return_original', parcel_id='parcel_original')
    projected = project_result(fact)
    assert projected == expected and projected is not fact and fact == before
    projected['parcel_id'] = 'different_parcel'
    assert fact == before and project_result(fact) == expected
    assert project_result(dict(status='FAILED')) is None
    # Do not expand the shared finite-history schema allowlist for this DTO.
    with pytest.raises(FlowError) as rejected:
        finite.validate('OperationResult', expected)
    assert rejected.value.code == 'INTERNAL_ERROR'


@pytest.mark.parametrize('field', ['provider_return_id', 'parcel_id'])
def test_RE_G2_G9_result_projection_rejects_malformed_frozen_identifiers(field):
    fact = dict(status='SUCCEEDED', provider_return_id='return_original', parcel_id='parcel_original')
    for malformed in ('x', 'invalid identifier', 7):
        changed = {**fact, field: malformed}
        before = dict(changed)
        with pytest.raises(FlowError) as rejected:
            project_result(changed)
        assert rejected.value.code == 'INTERNAL_ERROR' and changed == before


@pytest.mark.parametrize('entry', ['execute', 'query'])
def test_RE_G4_unknown_reservation_entry_never_calls_mock(entry):
    calls = []
    class Uncertain:
        def __init__(self, *args, **kwargs): calls.append('construct')
        def __enter__(self): calls.append('enter'); raise AcceptanceOutcomeUnknown()
        def __exit__(self, *args): raise AssertionError('Unentered transaction cannot exit')
    def mock(*args): raise AssertionError('Mock cannot run before T1 commit and close')
    caller = ReturnExecutionService(object(), object(), uow_factory=Uncertain, mock_factory=mock)
    if entry == 'execute':
        result = caller.execute_prepared_create_return('case_original', 1, 'work_original', 'original-key', command(), 'correlation_original')
    else:
        result = caller.reconcile_create_return('case_original', 'work_original', 'original-key', 'correlation_original')
    assert result == ExecutionResult('UNKNOWN') and calls == ['construct', 'enter']


def test_RE_G8_G10_private_composition_is_lazy_and_outputs_are_immutable():
    class NoEngine:
        def __getattr__(self, name): raise AssertionError('Unexpected eager engine access')
    engine = NoEngine()
    caller = compose_private_return_execution(engine, AuthConfig('issuer', 'audience', b'x' * 32), None)
    assert caller.engine is engine
    with pytest.raises(FrozenInstanceError): ExecutionResult('UNKNOWN').status = 'COMMITTED'
    with pytest.raises(FrozenInstanceError): Ticket('prep', 'case', 'secret', 'hash', 'QUERY', 'claim', 1).epoch = 2


def test_RE_G9_retained_confirmation_payload_is_minimal_and_binds_known_fact():
    row = {**reservation(), 'binding_hash': '2' * 64}
    fact = dict(fact_hash='3' * 64, provider_operation_id='provider_operation', status='SUCCEEDED')
    payload = accepted_payload(row, fact)
    assert payload['content_available'] is False and payload['confirmed_effect_status'] == 'SUCCEEDED'
    assert not {'body', 'result', 'parameters', 'parcel_id', 'provider_return_id', 'original_key'} & payload.keys()
    original = digest(payload, 'audit-payload/v1')
    for changed in ({**fact, 'fact_hash': '4' * 64}, {**fact, 'status': 'FAILED'}):
        assert digest(accepted_payload(row, changed), 'audit-payload/v1') != original
