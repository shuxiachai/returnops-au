"""A3 sandbox carrier adapter through the actual label execution on PostgreSQL 17.

docs/49-a3-carrier-sandbox.md; OF-004, FR-010, UC-04, NFR-004, NFR-007.
The unchanged LabelExecutionService runs the actual approved chain with
SandboxLabelFactory passed as its existing ``mock_factory``; the adapter reaches
the local contract-test carrier sandbox over real HTTP on 127.0.0.1. No carrier
is contacted and every value is synthetic.

Registered on 1 November 2026 in tools/checks/lifecycle-groups.json (group
label_execution_bridge_3), so the PostgreSQL CI part runs it. To run it alone:

    python -B -m pytest tests/lifecycle/test_label_carrier_sandbox_postgresql.py -q
"""
from dataclasses import asdict
import pytest
from returnops_domain.carrier_adapter import SandboxLabelFactory
from returnops_domain.carrier_sandbox import CarrierSandbox
from returnops_domain.label_execution_tables import controls, ledger, artifact_work
from returnops_domain.registry import TrustedRegistry
from label_execution_helpers import ready, service, execute, reconcile, reserve, control, assert_complete, rows, snapshot, evidence


@pytest.fixture
def sandbox():
    with CarrierSandbox() as running:
        yield running


def statuses(adapter):
    return [(item['phase'], item['method'], item['status'], item['error']) for item in adapter.attempts]


def receipts(factory):
    return [adapter.carrier_result.receipt() for adapter in factory.adapters if adapter.carrier_result is not None]


def assert_no_key(key, factory, sandbox):
    assert key not in repr(receipts(factory)) + repr(sandbox.requests()) + repr(factory) + repr(sandbox)


def test_A3_sandbox_label_through_actual_execution_and_confirmed_replay(flow_engine,identities,enabled,sandbox,request):
    args,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=1.0);caller=service(flow_engine,identities,mock_factory=factory)
    result=execute(caller,args);after=assert_complete(flow_engine,args,result,before)
    assert result.status=='COMMITTED',asdict(result)
    key=control(flow_engine)['effect_key'];adapter,=factory.adapters
    assert statuses(adapter)==[('create','POST',201,None)]
    assert sandbox.labels_for_key(key)==1 and sandbox.label_count()==1 and len(rows(flow_engine,ledger))==1
    server,=sandbox.requests(adapter.carrier_result.correlation_id)
    assert server['request_id']==adapter.attempts[0]['request_id'] and server['status']==201
    sent=len(sandbox.requests());again=execute(caller,args)
    assert again.status=='REPLAYED' and snapshot(flow_engine)==after,asdict(again)
    assert len(factory.adapters)==1 and len(sandbox.requests())==sent
    assert_no_key(key,factory,sandbox)
    evidence(request.node.nodeid,result=asdict(result),again=asdict(again),carrier=receipts(factory),sandbox=sandbox.requests())


def test_A3_timeout_after_commit_recovered_with_one_sandbox_label_and_one_ledger_row(flow_engine,identities,enabled,sandbox,request):
    args,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    sandbox.inject('timeout_after_commit',delay=2.0)
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=0.5)
    result=execute(service(flow_engine,identities,mock_factory=factory),args)
    assert_complete(flow_engine,args,result,before)
    assert result.status=='COMMITTED',asdict(result)
    key=control(flow_engine)['effect_key'];adapter,=factory.adapters
    assert statuses(adapter)==[('create','POST',None,'TIMEOUT'),('verify','GET',200,None)]
    assert adapter.carrier_result.recovered
    assert sandbox.wait_idle(10)
    assert sandbox.labels_for_key(key)==1 and sandbox.label_count()==1
    fact,=rows(flow_engine,ledger);assert fact['status']=='SUCCEEDED' and fact['effect_key']==key
    server=sandbox.requests(adapter.carrier_result.correlation_id)
    assert sorted((item['method'],item['status'],item['fault']) for item in server)==[('GET',200,None),('POST',201,'timeout_after_commit')]
    assert_no_key(key,factory,sandbox)
    evidence(request.node.nodeid,result=asdict(result),carrier=receipts(factory),sandbox=server)


def test_A3_reject_auth_ends_in_the_existing_failed_handling(flow_engine,identities,enabled,sandbox,request):
    args,_=ready(flow_engine,identities)
    sandbox.inject('reject_auth')
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=1.0);caller=service(flow_engine,identities,mock_factory=factory)
    result=execute(caller,args)
    assert result.status=='COMMITTED' and result.operation_state=='FAILED' and result.provider_fact_status=='FAILED',asdict(result)
    assert rows(flow_engine,artifact_work)==[]
    fact,=rows(flow_engine,ledger);assert fact['status']=='FAILED' and fact['provider_label_id'] is None
    adapter,=factory.adapters
    assert statuses(adapter)==[('create','POST',401,None)] and adapter.carrier_result.error=='CARRIER_AUTH_REJECTED'
    assert sandbox.label_count()==0
    before=snapshot(flow_engine);again=execute(caller,args)
    assert again.status=='REPLAYED' and snapshot(flow_engine)==before and len(factory.adapters)==1,asdict(again)
    assert_no_key(control(flow_engine)['effect_key'],factory,sandbox)
    evidence(request.node.nodeid,result=asdict(result),again=asdict(again),carrier=receipts(factory),sandbox=sandbox.requests())


def test_A3_outcome_still_unknown_keeps_the_existing_unknown_without_a_ledger_row(flow_engine,identities,enabled,sandbox,request):
    args,_=ready(flow_engine,identities)
    sandbox.inject('error_before_commit',times=None)
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=0.5);caller=service(flow_engine,identities,mock_factory=factory)
    result=execute(caller,args)
    assert result.status=='UNKNOWN',asdict(result)
    assert rows(flow_engine,ledger)==[] and rows(flow_engine,artifact_work)==[] and sandbox.label_count()==0
    adapter,=factory.adapters
    assert [item[2] for item in statuses(adapter)]==[503,404,503,404]
    row=control(flow_engine);assert row['status']=='EXECUTING' and row['confirmed_effect_status'] is None
    # The core query path reads only its own ledger; it never calls the carrier again.
    sandbox.clear();sent=len(sandbox.requests());recovered=reconcile(caller,args)
    assert recovered.status=='UNKNOWN',asdict(recovered)
    assert len(factory.adapters)==2 and factory.adapters[1].carrier_result is None and len(sandbox.requests())==sent
    assert rows(flow_engine,ledger)==[] and sandbox.label_count()==0
    evidence(request.node.nodeid,result=asdict(result),recovered=asdict(recovered),carrier=receipts(factory),sandbox=sandbox.requests())


@pytest.mark.parametrize('fault',['missing_grants','customer','wrong_key'])
def test_A3_same_approval_rules_deny_before_any_carrier_call(flow_engine,identities,enabled,sandbox,request,fault):
    args,_=ready(flow_engine,identities,grants=fault!='missing_grants')
    if fault=='wrong_key':args['original_approval_key']='replacement-original-key'
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=1.0)
    before=snapshot(flow_engine);result=execute(service(flow_engine,identities,'customer_a' if fault=='customer' else 'founder',mock_factory=factory),args)
    assert result.status=='DENIED',asdict(result)
    assert snapshot(flow_engine)==before and rows(flow_engine,controls)==rows(flow_engine,ledger)==[]
    assert factory.adapters==[] and sandbox.requests()==[] and sandbox.label_count()==0
    evidence(request.node.nodeid,fault=fault,result=asdict(result))


def test_A3_session_revoked_after_reservation_denies_inside_the_fence_before_the_carrier(flow_engine,identities,enabled,sandbox,request):
    args,_=ready(flow_engine,identities)
    factory=SandboxLabelFactory(sandbox.base_url,request_timeout=1.0);caller=service(flow_engine,identities,mock_factory=factory)
    ticket=reserve(caller,args)
    TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    before=snapshot(flow_engine);result=caller._perform(ticket,args['correlation_id'])
    assert result.status=='DENIED',asdict(result)
    adapter,=factory.adapters
    assert adapter.carrier_result is None and sandbox.requests()==[] and sandbox.label_count()==0
    assert snapshot(flow_engine)==before and rows(flow_engine,ledger)==[]
    evidence(request.node.nodeid,result=asdict(result))
