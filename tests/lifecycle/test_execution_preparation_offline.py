"""Pure identity, immutable binding and no-connect/UNKNOWN boundaries only."""
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
from datetime import datetime, timezone
import pytest
from returnops_api.private_execution_preparation import compose_private_execution_preparation
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_tables as old
from returnops_domain import founder_codec as finite
from returnops_domain.canonical import digest
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.execution_preparation import ExecutionPreparationService, PreparationResult
from returnops_domain.execution_preparation_sources import identities, request_fingerprint, payload, expected_closure
from test_approval_admission_offline import command


def test_EP_G1_G4_stable_identity_is_independent_of_candidate_parameters():
    original = command(); changed = deepcopy(original); changed['parameters']['line_items'][0]['quantity'] = 2
    same = identities('execution_original')
    assert same == identities('execution_original') and len(set(same.values())) == 4
    assert request_fingerprint(original) != request_fingerprint(changed)
    assert not set(same.values()) & set(identities('execution_other').values())
    from returnops_domain.wire import validate
    for name,value in same.items(): validate('IdempotencyKey' if name == 'effect_key' else 'Id', value)


def test_EP_G4_binding_excludes_audit_output_and_mutable_state_but_binds_parameters():
    row = dict(**identities('execution_original'), case_id='case_original',
        approval_execution_work_id='execution_original', original_approval_acceptance_id='accepted_original',
        command_type='CREATE_RETURN', request_fingerprint=request_fingerprint(command()), profile_hash='1'*64,
        prepared_authority_revision=1, created_at=datetime(2026,10,13,tzinfo=timezone.utc),
        state='PENDING', binding_hash='2'*64, origin_audit_event_id='audit_original')
    original = payload(row, {'status':'PENDING'}, '3'*64)
    changed = {**row, 'state':'PAUSED', 'binding_hash':'4'*64, 'origin_audit_event_id':'audit_new'}
    assert payload(changed, {'status':'PENDING'}, '3'*64) == original
    changed['request_fingerprint'] = '5'*64
    assert digest(payload(changed, {'status':'PENDING'}, '3'*64), 'execution-preparation/v1') != digest(original, 'execution-preparation/v1')


@pytest.mark.parametrize('mutation', ['case_version','status','history_sequence','audit_sequence','audit_head'])
def test_EP_G3_write_delta_rejects_non_exact_head_change(mutation):
    before = {old.case_heads.name:[dict(case_id='case_original', case_version=7, status='APPROVED',
        history_sequence=4, audit_sequence=8, audit_head='old_hash')]}
    head = {**before[old.case_heads.name][0], 'history_sequence':5, 'audit_sequence':9, 'audit_head':'new_hash'}
    head[mutation] = (8 if mutation == 'case_version' else 'COMPLETED' if mutation == 'status'
        else 7 if mutation.endswith('sequence') else 'old_hash')
    with pytest.raises(ValueError): expected_closure(before, [], head)


def test_EP_G6_composition_is_lazy_and_unknown_entry_never_retries():
    class NoEngine:
        def __getattr__(self, name): raise AssertionError('unexpected engine access')
    engine = NoEngine(); caller = compose_private_execution_preparation(engine, AuthConfig('issuer','audience',b'x'*32),None)
    assert caller.engine is engine
    calls=[]
    class Unknown:
        def __init__(self,*args,**kwargs): calls.append('construct')
        def __enter__(self): calls.append('enter'); raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args): raise AssertionError('Unentered context cannot exit')
    caller = ExecutionPreparationService(engine, object(), uow_factory=Unknown)
    args = ('case_original',1,'execution_original','original-key',command())
    assert caller.prepare(*args,'correlation_original') == PreparationResult('UNKNOWN')
    assert caller.recover_preparation(*args) == PreparationResult('UNKNOWN')
    assert calls == ['construct','enter','construct','enter']
    with pytest.raises(FrozenInstanceError): PreparationResult('UNKNOWN').status = 'PREPARED'
    assert all(value is None for name,value in asdict(PreparationResult('UNKNOWN')).items() if name != 'status')


def test_EP_G1_first_producer_uses_one_but_legacy_zero_wire_remains_valid():
    value = dict(operation_id='operation_legacy', case_id='case_original', case_version=1,
        command_id='command_original', approval_id='approval_original', proposal_id='proposal_original',
        proposal_version=1, input_version=1, provider_id='provider_original', operation_fingerprint='1'*64,
        status='PENDING', attempt_count=0, updated_at='2026-10-13T00:00:00Z', idempotency_key='legacy-key')
    assert finite.validate('OperationAttempt',value)['attempt_count'] == 0
