"""G4/G7/G8 narrow pure boundaries; actual-source claims belong to PG tests."""
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import column, select, table
from returnops_api.private_approval_admission import compose_private_approval_admission
from returnops_api.security.authentication import AuthConfig
from returnops_domain.approval_admission import AdmissionResult, ApprovalAdmissionService
from returnops_domain.approval_admission_sources import (ProofReads, restricted_bytes, command_request,
    check_time, check_session_time, session_bounds)
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError


def command():
    return dict(command_id='return_command', type='CREATE_RETURN', provider_id='provider-mock-return',
        parameters=dict(order_id='order_fixture', parcel_id='parcel_fixture',
                        line_items=[dict(line_item_id='line_fixture', quantity=1)]))


@pytest.mark.parametrize('value', [1.0, True, 0, -1])
def test_AG_G4_quantity_is_a_strict_positive_integer(value):
    body = command(); body['parameters']['line_items'][0]['quantity'] = value
    with pytest.raises(FlowError):
        command_request(body)


@pytest.mark.parametrize('value', [{'unexpected':'value'}, {'x':'\u00e9'}, {'x':datetime.now(timezone.utc)},
                                  {'x':None}, {'x':float('nan')}])
def test_AG_G4_malformed_or_non_ascii_candidates_are_not_normalized(value):
    with pytest.raises(FlowError):
        command_request(value)


def test_AG_G4_exact_bytes_preserve_types_order_and_freeze_request():
    supplied = command(); saved = command_request(supplied)
    supplied['parameters']['line_items'][0]['quantity'] = 2
    assert saved == command() and saved is not supplied
    assert restricted_bytes({'b':[2,1], 'a':False}) == b'{"a":false,"b":[2,1]}'
    assert restricted_bytes({'n':True}) != restricted_bytes({'n':1})
    nested = {}
    for _ in range(14): nested = {'x':nested}
    with pytest.raises(FlowError): restricted_bytes(nested)


def test_AG_G7_proof_facade_blocks_trusted_helper_mutations():
    observed = []
    uow = SimpleNamespace(connection=object(), poison=lambda:observed.append('poison'),
        execute=lambda statement, parameters:observed.append(statement))
    reads = ProofReads(uow); fixture = table('fixture', column('id'))
    reads.execute(select(fixture))
    assert len(observed) == 1
    for statement in (fixture.insert().values(id=1), fixture.update().values(id=2), fixture.delete()):
        with pytest.raises(FlowError): reads.execute(statement)
    assert len(observed) == 4 and observed[1:] == ['poison']*3


def test_AG_G8_composition_and_result_never_provision_or_connect():
    class NoEngine:
        def __getattr__(self, name): raise AssertionError('composition used engine')
    engine = NoEngine()
    result = compose_private_approval_admission(engine, AuthConfig('issuer','audience',b'x'*32), None)
    assert result.engine is engine
    checked = AdmissionResult('CHECKED')
    assert asdict(checked) == {'status':'CHECKED', 'safe_code':None}
    with pytest.raises(FrozenInstanceError): checked.status = 'DENIED'
    assert not hasattr(checked, 'receipt') and not hasattr(checked, 'scope')


def test_AG_G7_unknown_entry_never_retries_or_audits():
    calls=[]
    class Unknown:
        def __init__(self,*args,**kwargs): calls.append('construct')
        def __enter__(self): calls.append('enter'); raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args): raise AssertionError('unentered UoW cannot exit')
    result = ApprovalAdmissionService(object(), object(), uow_factory=Unknown).check(
        'case_fixture', 1, 'execution_fixture', 'original-key', command())
    assert asdict(result) == {'status':'UNKNOWN','safe_code':None}
    assert calls == ['construct','enter']


@pytest.mark.parametrize('kind',['naive','offset','expiry','before_issue','backwards','not_datetime'])
def test_AG_G4_G7_time_is_strict_utc_and_final_window(kind):
    issued=datetime(2026,10,13,tzinfo=timezone.utc); expiry=issued+timedelta(minutes=5)
    proof={'approval':{'record':{'recorded_at':issued},'preview':{'row':{'issued_at':issued,'expires_at':expiry}}}}
    initial=issued+timedelta(minutes=1)
    values={'naive':initial.replace(tzinfo=None),'offset':initial.astimezone(timezone(timedelta(hours=1))),
        'expiry':expiry,'before_issue':issued-timedelta(seconds=1),'backwards':issued,'not_datetime':None}
    with pytest.raises(FlowError): check_time(values[kind],proof,initial=initial)
    check_time(initial,proof,initial=initial)


@pytest.mark.parametrize('offset',[-1,0,1,9,10])
def test_AG_G7_session_deadline_has_no_admission_leeway(offset):
    at=datetime(2026,10,13,tzinfo=timezone.utc); issued=int(at.timestamp())
    bounds=('principal_fixture','session_fixture',issued,issued+1,issued+10,False)
    sampled=at+timedelta(seconds=offset)
    if 1<=offset<10:
        check_session_time(sampled,bounds)
    else:
        with pytest.raises(FlowError): check_session_time(sampled,bounds)


@pytest.mark.parametrize('field,value',[('issued_at',True),('not_before',1.0),('expires_at',None),
    ('issued_at',-1),('not_before',11),('revoked',True)])
def test_AG_G7_registry_deadline_tuple_is_strict_and_not_a_caller_flag(field,value):
    actor=SimpleNamespace(principal_id='principal_fixture',session_id='session_fixture')
    row=dict(principal_id=actor.principal_id,session_id=actor.session_id,
             issued_at=1,not_before=1,expires_at=10,revoked=False)
    row[field]=value
    class Reads:
        def poison(self): pass
        def execute(self,*args): return self
        def mappings(self): return self
        def one_or_none(self): return row
    with pytest.raises(FlowError): session_bounds(Reads(),actor)
