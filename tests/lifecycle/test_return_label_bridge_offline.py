"""Pure request/identity/context boundaries; these are not retained PG proof."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from returnops_domain.errors import FlowError
from returnops_domain.return_label_bridge import ReturnLabelBridge
from returnops_domain.return_label_sources import identity, context


def example():
    return SimpleNamespace(principal_id='founder-a',session_id='session-a'), dict(
        case_id='case-a',store_id='store-a',owner_principal_id='owner-a',input_version=2,case_version=9), dict(
        control=dict(execution_work_id='execution-a',preparation_id='preparation-a',
            approval_acceptance_id='acceptance-a',dispatch_record_id='dispatch-a',binding_hash='1'*64,
            original_key_hash='2'*64,operation_id='operation-a'),
        root={'approval':{'record':dict(record_id='approval-a',content_sha256='3'*64)}},
        record=dict(record_id='result-a',content_sha256='4'*64), fact={'fact_hash':'5'*64},
        state={'generation':4},body={'result':{'provider_return_id':'provider-return-a','parcel_id':'parcel-a'}},
        label_command={'command_id':'label-a','type':'GENERATE_LABEL','provider_id':'provider-mock-label',
            'parameters':{'return_command_id':'return-a','parcel_id':'parcel-a'}})


def test_RB_offline_identity_excludes_current_version_session_clock_and_claim():
    actor,head,source=example(); before=deepcopy((head,source)); first=identity(actor,head,source)
    actor.session_id='session-b';head['case_version']=23
    source['state']['authority_revision']=7;source['state']['claim_id']='later-claim'
    assert identity(actor,head,source)==first
    assert set(first)=={'work_id','event_id','idempotency_key','target_hash'}
    assert all(len(value)<=80 for value in first.values())
    assert before[0]['case_version']==9


@pytest.mark.parametrize('location,key',[
    ('head','case_id'),('head','store_id'),('head','owner_principal_id'),('head','input_version'),
    ('control','execution_work_id'),('control','preparation_id'),('control','approval_acceptance_id'),
    ('control','dispatch_record_id'),('control','binding_hash'),('control','original_key_hash'),
    ('record','record_id'),('record','content_sha256'),('fact','fact_hash'),('state','generation'),
    ('approval','record_id'),('approval','content_sha256'),('actor','principal_id')])
def test_RB_offline_identity_binds_each_full_root_and_key_field(location,key):
    actor,head,source=example(); first=identity(actor,head,source)
    if location=='actor':actor.principal_id='founder-b'
    else:
        target=head if location=='head' else source['root']['approval']['record'] if location=='approval' else source[location]
        target[key]=target[key]+1 if type(target[key]) is int else target[key]+'b'
    changed=identity(actor,head,source)
    assert all(changed[name]!=first[name] for name in first)


def test_RB_offline_context_is_copied_and_never_changes_approved_parameters():
    _,_,source=example();before=deepcopy(source);result=context(source)
    assert result['provider_return_id']=='provider-return-a'
    assert result['label_command']==source['label_command']
    assert 'provider_return_id' not in result['label_command']['parameters']
    result['label_command']['parameters']['parcel_id']='changed'
    assert source==before and context(source)['label_command']['parameters']['parcel_id']=='parcel-a'


@pytest.mark.parametrize('field,value',[
    ('case_id',''),('case_id',None),('execution_work_id','bad id'),('correlation_id','x'*81),
    ('original_approval_key',''),('original_approval_key',[]),
    ('expected_case_version',True),('expected_case_version',0),('expected_case_version',1.5),
    ('expected_case_version',9007199254740992)])
def test_RB_offline_invalid_request_never_reaches_transaction(field,value):
    attempts=[]
    def forbidden(*args,**kwargs):
        attempts.append('transaction');raise AssertionError('Invalid request reached transaction')
    bridge=ReturnLabelBridge(object(),object(),uow_factory=forbidden)
    args=dict(case_id='case-a',execution_work_id='work-a',correlation_id='correlation-a',
        original_approval_key='original-a',expected_case_version=3)
    args[field]=value;result=bridge.accept_return_source(**args)
    assert result.status=='DENIED' and result.safe_code=='VALIDATION_ERROR'
    assert result.label_context is None and attempts==[]


@pytest.mark.parametrize('value',[True,False,0,-1,301,1.5,None,'60'])
def test_RB_offline_invalid_lease_is_rejected_before_any_io(value):
    with pytest.raises(FlowError) as error:ReturnLabelBridge(object(),object(),lease_seconds=value)
    assert error.value.code=='INTERNAL_ERROR'
