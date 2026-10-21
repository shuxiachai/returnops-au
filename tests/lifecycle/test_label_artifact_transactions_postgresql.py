"""P07–P09: every T1/T3 mutation, final check, commit and close boundary."""
from dataclasses import asdict
from datetime import timedelta
import pytest
from sqlalchemy import select,update
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError,AcceptanceOutcomeUnknown
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
from returnops_domain.label_artifact_tables import controls,claims,artifacts,contents
from label_artifact_helpers import ready,service,complete,recover,claim,rows,snapshot,evidence,pdf_call_counts

@pytest.mark.parametrize('phase,point',[('T1',p) for p in range(1,4)]+[('T3',p) for p in range(1,16)])
def test_LA_P08_every_actual_write_rolls_back_exactly(flow_engine,identities,enabled,request,phase,point):
    args,_=ready(flow_engine,identities);writes=[];calls=[]
    class Fault(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            result=super().execute(statement,parameters)
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                writes.append(statement.table.name)
                if len(writes)==point:self.poison();raise FlowError('INTERNAL_ERROR')
            return result
    if phase=='T1':
        def forbidden(*a):calls.append(True);raise AssertionError('No ticket before acknowledged T1')
        before=snapshot(flow_engine);result=complete(service(flow_engine,identities,uow_factory=Fault,mock_factory=forbidden),args)
    else:
        caller=service(flow_engine,identities);ticket=claim(caller,args)
        reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
        before=snapshot(flow_engine);result=service(flow_engine,identities,uow_factory=Fault)._complete(ticket,reply.content,'fault-completion')
    assert len(writes)==point and result.status=='UNKNOWN' and not calls and snapshot(flow_engine)==before
    assert not rows(flow_engine,artifacts) and not rows(flow_engine,contents)
    evidence(request.node.nodeid,phase=phase,point=point,writes=writes,result=asdict(result),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['t1_before_commit','t1_after_commit','t1_close','t2_lost_reply','t3_before_commit','t3_after_commit','t3_close'])
def test_LA_P09_unknown_commit_or_close_has_query_only_recovery(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities);transactions=[];renders=[]
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if fault.endswith('before_commit'):self.poison();raise AcceptanceOutcomeUnknown()
            super().commit()
            if fault.endswith('after_commit'):raise AcceptanceOutcomeUnknown()
        def __exit__(self,*a):
            result=super().__exit__(*a)
            if fault.endswith('close'):raise AcceptanceOutcomeUnknown()
            return result
    def factory(engine,**kwargs):
        transactions.append(len(transactions)+1)
        selected=(fault.startswith('t1') and len(transactions)==1 or fault.startswith('t3') and len(transactions)==2)
        return (Fault if selected else CustomerUnitOfWork)(engine,**kwargs)
    class Observed(CoreLabelArtifactMock):
        def retrieve_original_label(self,ticket,authority):
            renders.append(ticket.claim_id);reply=super().retrieve_original_label(ticket,authority)
            if fault=='t2_lost_reply':assert reply.status=='FOUND';raise AcceptanceOutcomeUnknown()
            return reply
    result=complete(service(flow_engine,identities,uow_factory=factory,mock_factory=Observed),args)
    assert result.status=='UNKNOWN'
    assert len(renders)==int(not fault.startswith('t1'))
    committed=fault in {'t3_after_commit','t3_close'}
    assert len(rows(flow_engine,artifacts))==int(committed)
    before=snapshot(flow_engine)
    with pdf_call_counts() as recovery_calls:
        recovered=recover(service(flow_engine,identities,mock_factory=lambda *a:pytest.fail('Pure recover invoked T2')),args)
    assert recovered.status==('REPLAYED' if committed else 'PENDING' if fault=='t1_before_commit' else 'IN_PROGRESS')
    assert all(recovery_calls[name]==0 for name in ('render','text_line','assembly','expected_pdf','return_provider','label_provider','artifact_retrieval'))
    if committed:assert recovery_calls['validation']>0
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=asdict(result),recovered=asdict(recovered),renders=renders,
        recovery_actual_code_calls=recovery_calls,before=before,after=snapshot(flow_engine))

def test_LA_P07_final_slow_source_read_checks_real_lease_deadline(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain import label_artifact as module,label_artifact_sources as sources
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    with flow_engine.connect() as connection:deadline=connection.execute(select(claims.c.lease_expires_at)).scalar_one()
    original=module.closure;seen=[]
    def slow(uow,case_id):
        saved=original(uow,case_id)
        if saved[artifacts.name]:
            seen.append('completed source read')
            monkeypatch.setattr(sources,'database_now',lambda u:deadline)
            monkeypatch.setattr(module,'database_now',lambda u:deadline)
        return saved
    monkeypatch.setattr(module,'closure',slow)
    before=snapshot(flow_engine);result=caller._complete(ticket,reply.content,'late-lease-completion')
    assert seen and result.status=='DENIED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,result=asdict(result),slow_read=seen,before=before,after=snapshot(flow_engine))

def test_LA_P07_P19_current_advance_invalidates_claim_and_old_epoch_cannot_finish(flow_engine,identities,enabled,request):
    from returnops_domain.lifecycle_state import invalidate
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one());invalidate(uow,head)
        uow.execute(update(old.case_heads).values(case_version=head['case_version']+1));uow.commit()
    before=snapshot(flow_engine);late=caller._complete(ticket,reply.content,'old-epoch-completion')
    assert late.status=='DENIED' and snapshot(flow_engine)==before
    result=complete(caller,args);assert result.status=='COMMITTED'
    assert len(rows(flow_engine,claims))==2 and rows(flow_engine,controls)[0]['epoch']>ticket.epoch
    evidence(request.node.nodeid,protective_generation_advance=True,late=asdict(late),result=asdict(result),before=before,after=snapshot(flow_engine))
