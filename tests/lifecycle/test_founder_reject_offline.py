"""Offline request/UNKNOWN boundaries only; no PostgreSQL claim is made."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import pytest
from returnops_api.private_reject import compose_private_reject
from returnops_api.security.authentication import AuthConfig
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.reject_decision import FounderRejectService


REQUEST=dict(expected_case_version=7,proposal_id='proposal_fixture',proposal_version=1,
    decision='REJECT',reason='Reject the retained proposal.')


def test_R01_offline_valid_request_is_copied_and_preserves_reason():
    supplied=deepcopy(REQUEST)
    value=FounderRejectService._request(supplied)
    assert value==REQUEST and value is not supplied
    supplied['reason']='caller mutated later'
    assert value['reason']==REQUEST['reason']


@pytest.mark.parametrize('patch', [
    {'decision':'MANUAL_HANDLING'}, {'decision':'REQUEST_REVISION'}, {'decision':'APPROVE'},
    {'expected_case_version':0}, {'expected_case_version':True}, {'proposal_version':0},
    {'proposal_id':''}, {'reason':''}, {'reason':'x'*2001}, {'principal_id':'forged'},
    {'review_id':'forged'}, {'generation':1}, {'status':'REJECTED'}, {'grant':'forged'},
    {'processing_failure_id':'other_target'}, {'order_lookup_block_id':'other_target'},
])
def test_R02_offline_frozen_request_rejects_other_scope(patch):
    with pytest.raises(FlowError):FounderRejectService._request({**REQUEST,**patch})


@pytest.mark.parametrize('field', ['proposal_id','proposal_version','reason','expected_case_version'])
def test_R02_offline_required_request_fields(field):
    value=deepcopy(REQUEST);value.pop(field)
    with pytest.raises(FlowError):FounderRejectService._request(value)


def test_R04_offline_same_operation_uses_distinct_request_domains(monkeypatch):
    from returnops_domain import idempotency
    from returnops_domain.manual_decision import FounderDecisionService
    from returnops_domain.revision_decision import FounderRevisionService
    from returnops_domain.canonical import digest
    observed=[]
    def lookup(uow, actor, operation, case_id, key, fingerprint, **options):
        observed.append((operation,case_id,key,fingerprint))
        return None
    monkeypatch.setattr(idempotency,'lookup',lookup)
    actor=SimpleNamespace(store_id='store_fixture');head={'case_id':'case_fixture'}
    # Identical bytes isolate domain separation from the decision field change.
    fingerprints=[]
    for cls in (FounderRejectService,FounderDecisionService,FounderRevisionService):
        caller=cls(object(),object())
        _, fingerprint=caller._lookup(object(),actor,head,REQUEST,'same-key')
        fingerprints.append(fingerprint)
    assert {entry[:3] for entry in observed}=={('recordFounderDecision','case_fixture','same-key')}
    assert len(set(fingerprints))==3
    assert fingerprints[0]==digest(REQUEST,'founder-reject-request/v1')
    _, again=FounderRejectService(object(),object())._lookup(object(),actor,head,deepcopy(REQUEST),'same-key')
    assert again==fingerprints[0]


def test_R07_offline_composition_has_no_engine_or_authority_activity():
    class NeverConnect:
        def __getattr__(self,name):raise AssertionError('Composition touched engine '+name)
    engine=NeverConnect()
    caller=compose_private_reject(engine,AuthConfig('fixture-issuer','fixture-audience',b'x'*32),None)
    assert isinstance(caller,FounderRejectService) and caller.engine is engine
    assert caller.guard.component_id=='founder-reject-v1'


@pytest.mark.parametrize('operation', ['accept','recover'])
def test_R05_offline_unknown_signal_no_retry_no_denial(monkeypatch,operation):
    from returnops_domain import reject_decision
    calls=[]
    class UnknownUow:
        def __init__(self,*args,**kwargs):calls.append('construct')
        def __enter__(self):calls.append('enter');raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):raise AssertionError('Unentered UoW cannot exit')
    def no_denial(*args,**kwargs):raise AssertionError('UNKNOWN must not record denial')
    monkeypatch.setattr(reject_decision,'record_denial',no_denial)
    caller=FounderRejectService(object(),object(),uow_factory=UnknownUow,recovery_uow=UnknownUow)
    result=(caller.accept('case_fixture',REQUEST,'original-key','corr_fixture') if operation=='accept'
        else caller.recover('case_fixture',REQUEST,'original-key'))
    assert asdict(result)==dict(status='UNKNOWN',receipt=None,safe_code=None,audit='NOT_ATTEMPTED')
    assert calls==['construct','enter']


@pytest.mark.parametrize('revision', ['0013_label_artifact_result','0014_notification_delivery'])
@pytest.mark.parametrize('stale', [False,True])
def test_R01_offline_schema_gate_reaches_original_version_check(monkeypatch,revision,stale):
    """Exercise the real entry gate; no database or acceptance proof is replaced."""
    from returnops_domain import reject_decision
    calls=[]
    class ReachedCurrentState(Exception):
        pass
    class NoDatabase:
        connection=object()
        def poison(self):calls.append('poison')
        def execute(self,*args,**kwargs):raise AssertionError('Offline gate reached SQL')
    uow=NoDatabase()
    monkeypatch.setattr(reject_decision,'installed',lambda actual:actual is uow)
    def schema(connection):
        assert connection is uow.connection
        calls.append('schema')
        return revision
    def current(actual,head):
        assert actual is uow
        calls.append('current')
        raise ReachedCurrentState()
    monkeypatch.setattr(reject_decision,'version',schema)
    monkeypatch.setattr(reject_decision,'current',current)
    caller=FounderRejectService(object(),object())
    head={'case_version':REQUEST['expected_case_version']-int(stale)}
    if stale:
        with pytest.raises(FlowError) as caught:
            caller._new(uow,None,head,None,REQUEST,None,None,None)
        assert caught.value.code=='STALE_CASE_VERSION'
        assert calls==['schema','poison']
    else:
        with pytest.raises(ReachedCurrentState):
            caller._new(uow,None,head,None,REQUEST,None,None,None)
        assert calls==['schema','current']
