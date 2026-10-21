"""Offline boundaries are separate from real PostgreSQL acceptance evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
from inspect import signature
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from returnops_domain import founder_codec as finite
from returnops_domain.canonical import digest
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.label_execution import LabelExecutionService,LabelExecutionResult
from returnops_domain.label_execution_sources import identities,stable,control_payload,confirmation_body,ledger_payload,verify_fact,accepted_payload
from returnops_domain.label_execution_tables import controls,permissions,ledger,artifact_work,CONTROL_IDS,CONTROL_HASHES,CONTROL_NUMBERS
from returnops_domain.core_label_mock import Ticket


def reservation():
    now = datetime(2026,10,15,tzinfo=timezone.utc)
    row = {name:name+'_original' for name in CONTROL_IDS}
    row.update({name:'1'*64 for name in CONTROL_HASHES});row.update({name:1 for name in CONTROL_NUMBERS})
    row.update(effect_key='effect_original',dispatch_at=now,dispatch_deadline=now+timedelta(seconds=30))
    return row


def operation():
    return dict(operation_id='operation_original',case_id='case_original',case_version=7,command_id='command_original',
        approval_id='approval_original',proposal_id='proposal_original',proposal_version=1,input_version=2,
        provider_id='provider-mock-label',operation_fingerprint='a'*64,status='EXECUTING',attempt_count=1,
        updated_at='2026-10-15T00:00:00.000000Z',idempotency_key='effect_original')


def test_LE_G2_G8_stable_identity_has_only_original_work_and_fixed_label_slot():
    first = identities('work_original')
    assert first == identities('work_original') and set(first) == {'control_id','operation_id','first_record_id','dispatch_record_id','dispatch_claim_id','effect_key'}
    assert all(v != identities('work_changed')[k] for k,v in first.items())
    from returnops_domain.execution_preparation_sources import identities as returns
    assert not set(first.values()) & set(returns('work_original').values())
    assert list(signature(LabelExecutionService.execute_accepted_label).parameters) == ['self','case_id','expected_case_version','execution_work_id','original_approval_key','correlation_id']
    assert all(len(value) <= 80 for value in first.values())


@pytest.mark.parametrize('field',['bridge_event_id','bridge_target_hash','bridge_receipt_hash','return_result_hash','return_ledger_hash',
    'provider_return_id','command_hash','parcel_id','operation_fingerprint','provider_revision','effect_authority_revision','dispatch_deadline'])
def test_LE_G3_binding_covers_full_original_source_command_and_authority(field):
    row = reservation();original = digest(control_payload(row),'label-reservation/v1')
    row[field] = row[field]+timedelta(seconds=1) if field == 'dispatch_deadline' else 2 if type(row[field]) is int else 'changed'
    assert digest(control_payload(row),'label-reservation/v1') != original


@pytest.mark.parametrize('field,value',[('case_id',''),('execution_work_id','bad id'),('original_approval_key',[]),
    ('correlation_id','x'*81),('expected_case_version',True),('expected_case_version',0),('expected_case_version',1.5),
    ('expected_case_version',9007199254740992)])
def test_LE_G3_invalid_request_never_opens_transaction(field,value):
    calls=[]
    def forbidden(*args,**kwargs):calls.append('transaction');raise AssertionError('Invalid request reached I/O')
    caller=LabelExecutionService(object(),object(),uow_factory=forbidden)
    args=dict(case_id='case_original',execution_work_id='work_original',original_approval_key='original-key',
        correlation_id='correlation_original',expected_case_version=7);args[field]=value
    result=caller.execute_accepted_label(**args)
    assert result.status=='DENIED' and result.safe_code=='VALIDATION_ERROR' and calls==[]


@pytest.mark.parametrize('entry',['execute','reconcile'])
def test_LE_G5_unknown_transaction_never_invokes_mock(entry):
    calls=[]
    class Uncertain:
        def __init__(self,*args,**kwargs):calls.append('construct')
        def __enter__(self):raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):raise AssertionError('Never entered')
    def mock(*args):raise AssertionError('No confirmed T1 commit and close')
    caller=LabelExecutionService(object(),object(),uow_factory=Uncertain,mock_factory=mock)
    result=caller.execute_accepted_label('case_original',7,'work_original','original-key','correlation_original') if entry=='execute' else caller.reconcile_label('case_original','work_original','original-key','correlation_original')
    assert result==LabelExecutionResult('UNKNOWN') and calls==['construct']


def test_LE_G1_G9_ledger_independent_and_artifact_intent_cannot_be_claimed_or_duplicated():
    assert not ledger.foreign_key_constraints
    assert set(controls.metadata.tables)=={'lifecycle_label_execution_controls','label_provider_permissions','core_mock_label_ledger','lifecycle_label_artifact_work'}
    sql=str(CreateTable(artifact_work).compile(dialect=postgresql.dialect()))
    assert 'FOREIGN KEY(control_id, case_id)' in sql and 'UNIQUE (control_id)' in sql and 'UNIQUE (case_id)' in sql
    assert 'epoch = 0 AND claim_id IS NULL' in sql and 'PENDING' in sql and 'PAUSED' in sql
    assert not {'body','command','parameters','token','original_key','label_evidence_id'} & set(ledger.columns.keys())
    assert all(c.default is None and c.server_default is None for table in controls.metadata.tables.values() for c in table.columns)


@pytest.mark.parametrize('status',['SUCCEEDED','FAILED'])
def test_LE_G2_G9_confirmation_preserves_dispatch_version_and_never_fabricates_artifact(status):
    body=operation();before=deepcopy(body);now=datetime(2026,10,15,0,1,tzinfo=timezone.utc)
    fact=dict(status=status,provider_operation_id='mock_label_original')
    result=confirmation_body(body,fact,now,'correlation_original')
    assert result['case_version']==7 and result['attempt_count']==1 and body==before
    assert result['status']==('EXECUTING' if status=='SUCCEEDED' else 'FAILED')
    assert result['provider_operation_id']=='mock_label_original' and 'result' not in result and 'label_evidence_id' not in repr(result)
    assert ('error' in result)==(status=='FAILED')
    assert finite.validate('OperationAttempt',result)==result


def test_LE_G9_minimal_retained_payload_binds_fact_without_reconstructing_body():
    row=reservation();fact=dict(fact_hash='2'*64,provider_operation_id='mock_label_original',status='SUCCEEDED')
    value=accepted_payload(row,fact)
    assert value['content_available'] is False and not {'body','parameters','provider_label_id','parcel_id','provider_return_id','original_key'} & value.keys()
    assert accepted_payload(row,{**fact,'fact_hash':'3'*64})!=value


def test_LE_G11_result_and_internal_ticket_are_immutable_and_hide_sensitive_repr():
    result=LabelExecutionResult('UNKNOWN');ticket=Ticket('control_original','case_original','secret-original','a'*64,'QUERY','claim_original',1)
    with pytest.raises(FrozenInstanceError):result.status='COMMITTED'
    with pytest.raises(FrozenInstanceError):ticket.epoch=2
    assert 'secret-original' not in repr(ticket)


def test_LE_G1_G2_ledger_payload_uses_plain_keys_and_exact_accepted_time():
    now=datetime(2026,10,15,tzinfo=timezone.utc)
    row={str(name):'value_original' for name in ledger.columns.keys()};row.update(accepted_at=now,fact_hash='a'*64)
    payload=ledger_payload(row)
    assert all(type(k) is str for k in payload) and 'fact_hash' not in payload
    assert payload['accepted_at']=='2026-10-15T00:00:00.000000Z' and row['accepted_at'] is now
