"""Real fence ordering, real DB time, historical query and retention boundaries."""
from dataclasses import asdict
from datetime import datetime
from time import sleep,monotonic
import pytest
from sqlalchemy import select,text,update
from returnops_domain import customer_tables as old,lifecycle_tables as life,founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.core_label_mock import CoreLabelMock,Ticket
from returnops_domain.errors import AcceptanceOutcomeUnknown
from returnops_domain.label_execution_tables import controls,permissions,ledger,artifact_work
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from label_execution_helpers import ready,service,execute,reconcile,reserve,control,rows,snapshot,evidence
from test_founder_approve_late_postgresql import _overlap_at_actual_fence


class LostResponse(CoreLabelMock):
    def perform(self,ticket,callback):
        result=super().perform(ticket,callback)
        assert result.status=='FOUND',asdict(result)
        raise AcceptanceOutcomeUnknown()


def purge(engine,case_id):
    original,=[r for r in rows(engine,old.history) if r['case_id']==case_id and r['kind']=='STATEMENT']
    assert RetentionService(engine).remove('STATEMENT',original['object_id']) is True


@pytest.mark.parametrize('change',['permission','session','retention'])
@pytest.mark.parametrize('first',['change','mock'])
def test_LE_G4_G6_G7_actual_fence_orders_live_change_against_SQL_effect(flow_engine,identities,enabled,request,monkeypatch,change,first):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=reserve(caller,args)
    def mutate():
        if change=='session':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
        elif change=='retention':purge(flow_engine,args['case_id'])
        else:
            with CustomerUnitOfWork(flow_engine,write=True) as uow:
                assert uow.execute(update(permissions).values(create_enabled=False,revision=2)).rowcount==1;uow.commit()
        return 'changed'
    results,overlap=_overlap_at_actual_fence(flow_engine,monkeypatch,
        dict(change=mutate,mock=lambda:CoreLabelMock(flow_engine).perform(ticket,caller.authority)),first=first)
    assert results['change']=='changed' and results['mock'].status==('FOUND' if first=='mock' else 'DENIED'),asdict(results['mock'])
    assert len(rows(flow_engine,ledger))==(first=='mock') and rows(flow_engine,artifact_work)==[]
    evidence(request.node.nodeid,change=change,first=first,overlap=overlap,mock=asdict(results['mock']),after=snapshot(flow_engine))


def test_LE_G7_actual_INSERT_clock_rejects_deadline_after_slow_final_preparation(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=reserve(caller,args);times=[]
    class Slow(CoreLabelMock):
        def _insert(self,uow,row,actor,permission,bounds,source,outcome):
            before=uow.execute(text('SELECT clock_timestamp()')).scalar_one();started=monotonic()
            while True:
                at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()
                if at>=row['dispatch_deadline']:break
                assert monotonic()-started<35;sleep(.02)
            times.append(dict(before=before,at=at,deadline=row['dispatch_deadline']))
            return super()._insert(uow,row,actor,permission,bounds,source,outcome)
    reply=Slow(flow_engine).perform(ticket,caller.authority)
    assert reply.status=='NOT_FOUND' and len(times)==1 and rows(flow_engine,ledger)==[]
    before=snapshot(flow_engine);again=execute(caller,args)
    assert again.status=='UNKNOWN' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,reply=asdict(reply),times=times,again=asdict(again),after=before)


@pytest.mark.parametrize('phase,fault',[('T1','head_version'),('T1','source_pointer'),('T3','head_version'),('T3','artifact_state')])
def test_LE_G5_final_seal_rejects_unexpected_delta_without_absorbing_new_head(flow_engine,identities,enabled,request,phase,fault):
    args,_=ready(flow_engine,identities);injected=[]
    class Changed(CustomerUnitOfWork):
        def before_commit(self,check):
            if check.__name__=='check' and not injected:
                def mutate():
                    if fault=='head_version':statement=update(old.case_heads).values(case_version=old.case_heads.c.case_version+1)
                    elif fault=='source_pointer':statement=update(life.state).values(review_record_id=None)
                    else:statement=update(artifact_work).values(state='PAUSED')
                    assert self.execute(statement).rowcount==1;injected.append(fault)
                super().before_commit(mutate)
            return super().before_commit(check)
    if phase=='T1':
        before=snapshot(flow_engine);result=execute(service(flow_engine,identities,uow_factory=Changed),args)
    else:
        caller=service(flow_engine,identities);ticket=reserve(caller,args)
        reply=CoreLabelMock(flow_engine).perform(ticket,caller.authority);assert reply.status=='FOUND'
        before=snapshot(flow_engine);result=service(flow_engine,identities,uow_factory=Changed)._accept(ticket,reply.fact,'unexpected-delta')
    assert injected==[fault] and result.status=='DENIED',asdict(result)
    assert snapshot(flow_engine)==before and len(rows(flow_engine,ledger))==(phase=='T3')
    evidence(request.node.nodeid,phase=phase,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))


def test_LE_G8_not_found_and_pre_call_crash_never_authorize_redispatch(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);reserve(caller,args)
    calls=[]
    class QueryOnly(CoreLabelMock):
        def perform(self,ticket,callback):
            calls.append(ticket.kind);assert ticket.kind=='QUERY';return super().perform(ticket,callback)
        def _insert(self,*a,**k):raise AssertionError('Query cannot create')
    recovered=reconcile(service(flow_engine,identities,mock_factory=QueryOnly),args)
    assert recovered.status=='UNKNOWN' and calls==['QUERY'] and rows(flow_engine,ledger)==[]
    before=snapshot(flow_engine)
    class NoCall(CoreLabelMock):
        def perform(self,*a,**k):raise AssertionError('Existing execute cannot invoke adapter')
    repeated=execute(service(flow_engine,identities,mock_factory=NoCall),args)
    assert repeated.status=='UNKNOWN' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,recovered=asdict(recovered),repeated=asdict(repeated),calls=calls,after=before)


def test_LE_G6_G8_expired_query_epoch_rejects_late_worker_without_second_effect(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities)
    assert execute(service(flow_engine,identities,mock_factory=LostResponse),args).status=='UNKNOWN'
    caller=service(flow_engine,identities);query=[args[k] for k in ('case_id','execution_work_id','original_approval_key','correlation_id')]
    first=caller._query_claim(*query);assert type(first) is Ticket
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(controls).values(query_lease_until=text("clock_timestamp() - interval '1 second'"))).rowcount==1;uow.commit()
    second=caller._query_claim(*query);assert type(second) is Ticket and second.epoch==first.epoch+1
    fact,=rows(flow_engine,ledger);before=snapshot(flow_engine)
    late=caller._accept(first,fact,'late-label-query');assert late.status=='DENIED' and snapshot(flow_engine)==before
    current=caller._perform(second,'current-label-query');assert current.status=='COMMITTED' and len(rows(flow_engine,ledger))==1
    evidence(request.node.nodeid,first_epoch=first.epoch,second_epoch=second.epoch,late=asdict(late),current=asdict(current),after=snapshot(flow_engine))


@pytest.mark.parametrize('when',['before_reserve','before_mock','after_fact','after_confirmation'])
def test_LE_G9_real_retention_never_reconstructs_body_or_runnable_artifact(flow_engine,identities,enabled,request,when):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities)
    if when=='before_mock':ticket=reserve(caller,args)
    elif when=='after_fact':assert execute(service(flow_engine,identities,mock_factory=LostResponse),args).status=='UNKNOWN'
    elif when=='after_confirmation':assert execute(caller,args).status=='COMMITTED'
    purge(flow_engine,args['case_id']);before=snapshot(flow_engine)
    if when=='before_reserve':
        result=execute(caller,args);assert result.status=='DENIED' and snapshot(flow_engine)==before
    elif when=='before_mock':
        denied=CoreLabelMock(flow_engine).perform(ticket,caller.authority);assert denied.status=='DENIED'
        result=reconcile(caller,args);assert result.status=='UNKNOWN'
    elif when=='after_fact':
        result=reconcile(caller,args);assert result.status=='FACT_RECORDED',asdict(result)
        after=snapshot(flow_engine);prior,=before[old.case_heads.name];head,=after[old.case_heads.name]
        assert {k:v for k,v in head.items() if k not in {'audit_sequence','audit_head'}}=={k:v for k,v in prior.items() if k not in {'audit_sequence','audit_head'}}
        assert head['audit_sequence']==prior['audit_sequence']+1
        assert before[old.history.name]==after[old.history.name] and before[old.history_contents.name]==after[old.history_contents.name]
        assert rows(flow_engine,artifact_work)==[]
        replay=reconcile(caller,args);assert replay.status=='FACT_REPLAYED' and snapshot(flow_engine)==after
    else:
        row=control(flow_engine);work,=rows(flow_engine,artifact_work)
        assert row['confirmation_retained'] is False and work['state']=='PAUSED'
        result=reconcile(caller,args);assert result.status=='REPLAYED' and snapshot(flow_engine)==before
    assert len(rows(flow_engine,ledger))==(when in {'after_fact','after_confirmation'})
    assert all(r['retention_state']!='AVAILABLE' for r in rows(flow_engine,old.history) if r['kind']=='OPERATION')
    evidence(request.node.nodeid,when=when,result=asdict(result),before=before,after=snapshot(flow_engine),actual_retention=True)


@pytest.mark.parametrize('terminal',[False,True])
def test_LE_G9_retained_bodies_but_lost_current_eligibility_confirm_PAUSED_at_observation_version(flow_engine,identities,enabled,request,terminal):
    from returnops_domain.lifecycle_state import invalidate
    args,_=ready(flow_engine,identities)
    assert execute(service(flow_engine,identities,mock_factory=LostResponse),args).status=='UNKNOWN'
    dispatch=control(flow_engine)['dispatch_case_version']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one());invalidate(uow,head)
        changes=dict(case_version=head['case_version']+1)
        if terminal:changes['status']='NOTIFICATION_PENDING'
        uow.execute(update(old.case_heads).values(**changes));uow.commit()
    before=snapshot(flow_engine);result=reconcile(service(flow_engine,identities),args)
    assert result.status=='COMMITTED' and result.operation_state=='EXECUTING',asdict(result)
    row=control(flow_engine);work,=rows(flow_engine,artifact_work)
    assert work['state']=='PAUSED' and row['confirmation_case_version']==dispatch+1
    history=next(r for r in rows(flow_engine,old.history) if r['record_id']==row['confirmation_record_id'])
    content=next(r for r in rows(flow_engine,old.history_contents) if r['record_id']==row['confirmation_record_id'])
    assert finite.decode_document(content['body'])['case_version']==dispatch and history['case_version']==dispatch+1
    prior,=before[old.case_heads.name];after=snapshot(flow_engine);head,=after[old.case_heads.name]
    assert {k:v for k,v in head.items() if k not in {'history_sequence','audit_sequence','audit_head'}}=={k:v for k,v in prior.items() if k not in {'history_sequence','audit_sequence','audit_head'}}
    evidence(request.node.nodeid,synthetic_protective_state=True,not_reachable_human_workflow=True,terminal=terminal,
        result=asdict(result),dispatch_version=dispatch,observation_version=dispatch+1,before=before,after=after)


@pytest.mark.parametrize('existing_fact',[False,True])
def test_LE_G4_G8_natural_approval_expiry_allows_current_query_but_no_new_create(flow_engine,identities,enabled,request,existing_fact):
    args,setup=ready(flow_engine,identities)
    if existing_fact:assert execute(service(flow_engine,identities,mock_factory=LostResponse),args).status=='UNKNOWN'
    expires=datetime.fromisoformat(setup['action']['scope']['expires_at'].replace('Z','+00:00'))
    started=monotonic()
    while True:
        with flow_engine.connect() as connection:now=connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        if now>=expires:break
        assert monotonic()-started<330;sleep(min(1,(expires-now).total_seconds()))
    if not existing_fact:
        before=snapshot(flow_engine);result=execute(service(flow_engine,identities),args)
        assert result.status=='DENIED' and snapshot(flow_engine)==before and rows(flow_engine,ledger)==[]
        evidence(request.node.nodeid,natural_expiry=expires,actual_db_time=now,result=asdict(result),after=before)
        return
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(update(permissions).values(create_enabled=False,revision=2)).rowcount==1;uow.commit()
    calls=[]
    class Historical(CoreLabelMock):
        def perform(self,ticket,callback):calls.append(ticket.kind);assert ticket.kind=='QUERY';return super().perform(ticket,callback)
    result=reconcile(service(flow_engine,identities,mock_factory=Historical),args)
    assert result.status=='COMMITTED' and calls==['QUERY'] and len(rows(flow_engine,ledger))==1,asdict(result)
    before=snapshot(flow_engine);again=execute(service(flow_engine,identities),args)
    assert again.status=='REPLAYED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,natural_expiry=expires,actual_db_time=now,result=asdict(result),calls=calls,after=before)


@pytest.mark.parametrize('phase',['T1','T3'])
def test_LE_G7_real_session_expiry_after_last_slow_source_read_denies_commit(flow_engine,identities,enabled,request,monkeypatch,phase):
    from uuid import uuid4
    import jwt
    from returnops_api.private_label_execution import compose_private_label_execution
    import returnops_domain.label_execution as module
    args,_=ready(flow_engine,identities)
    with flow_engine.connect() as connection:now=connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    issued=int(now.timestamp());expires=issued+20;session='label_observer_'+uuid4().hex
    principal=identities.people['founder']['principal_id'];TrustedRegistry(flow_engine).register_session(principal,session,issued,issued,expires)
    auth=identities.auth_config
    token=jwt.encode(dict(iss=auth.issuer,aud=auth.audience,sub=principal,jti=session,iat=issued,nbf=issued,exp=expires),auth.signing_key,algorithm='HS256')
    caller=compose_private_label_execution(flow_engine,auth,'Bearer '+token)
    if phase=='T3':
        ticket=reserve(caller,args);reply=CoreLabelMock(flow_engine).perform(ticket,caller.authority);assert reply.status=='FOUND'
    before=snapshot(flow_engine);original=module.closure;calls=[];times=[]
    def delayed(uow,case_id):
        value=original(uow,case_id);calls.append(len(calls)+1)
        if len(calls)==3:
            start=uow.execute(text('SELECT clock_timestamp()')).scalar_one();assert start.timestamp()<expires
            deadline=monotonic()+25
            while True:
                at=uow.execute(text('SELECT clock_timestamp()')).scalar_one()
                if at.timestamp()>=expires:break
                assert monotonic()<deadline;sleep(.02)
            times.append(dict(before=start,after=at,expires=expires))
        return value
    monkeypatch.setattr(module,'closure',delayed)
    result=execute(caller,args) if phase=='T1' else caller._accept(ticket,reply.fact,'late-session-confirmation')
    assert result.status=='DENIED' and calls==[1,2,3] and len(times)==1,asdict(result)
    assert snapshot(flow_engine)==before and len(rows(flow_engine,ledger))==(phase=='T3')
    evidence(request.node.nodeid,phase=phase,result=asdict(result),actual_times=times,before=before,after=snapshot(flow_engine))
