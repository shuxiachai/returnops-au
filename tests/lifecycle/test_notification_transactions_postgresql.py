"""Cloud-only lost acknowledgement, transaction rollback and late authority."""
from dataclasses import asdict
import pytest
from sqlalchemy import update
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError,AcceptanceOutcomeUnknown
from returnops_domain.notification_mock import CoreMockNotification
from returnops_domain.notification_profile import COMPONENT
from returnops_domain.notification_tables import controls,facts
from notification_helpers import ready,service,rows,snapshot,evidence


@pytest.mark.parametrize('phase',['T1','T3'])
@pytest.mark.parametrize('point',['before_commit','after_commit','close'])
def test_unknown_acknowledgement_never_replays_sender_and_preserves_independent_fact(
        flow_engine,identities,enabled,request,phase,point):
    setup=ready(flow_engine,identities);writes=[];sends=[]
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if point=='before_commit':
                self.poison();raise AcceptanceOutcomeUnknown()
            super().commit()
            if point=='after_commit':raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):
            result=super().__exit__(*args)
            if point=='close':raise AcceptanceOutcomeUnknown()
            return result
    def factory(engine,**options):
        if options['write']:writes.append(len(writes)+1)
        use=options['write'] and len(writes)==(1 if phase=='T1' else 2)
        return (Fault if use else CustomerUnitOfWork)(engine,**options)
    class Observed(CoreMockNotification):
        def deliver(self,reservation_id):
            sends.append(reservation_id)
            return super().deliver(reservation_id)
    result=service(flow_engine,identities,uow_factory=factory,mock=Observed(flow_engine)).send(setup['work_id'])
    assert result.status=='UNKNOWN',asdict(result)
    assert len(sends)==int(phase=='T3')
    before=snapshot(flow_engine);original_facts=rows(flow_engine,facts)
    class QueryOnly(CoreMockNotification):
        def deliver(self,*args):pytest.fail('Acknowledgement recovery invoked sender')
    recovered=service(flow_engine,identities,mock=QueryOnly(flow_engine)).reconcile(setup['work_id'])
    if phase=='T1':
        assert recovered.status==('READY' if point=='before_commit' else 'UNKNOWN')
        assert snapshot(flow_engine)==before and original_facts==[]
    else:
        assert recovered.status=='SENT',asdict(recovered)
        assert rows(flow_engine,facts)==original_facts and len(original_facts)==1
        if point!='before_commit':
            assert snapshot(flow_engine)==before
        frozen=snapshot(flow_engine)
        assert service(flow_engine,identities).reconcile(setup['work_id']).status=='SENT'
        assert snapshot(flow_engine)==frozen
    evidence(request.node.nodeid,phase=phase,point=point,sends=sends,result=asdict(result),
        recovered=asdict(recovered),before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('point',['before_commit','after_commit','close'])
def test_t2_uncertain_ack_is_query_only_and_never_no_effect_failure(
        flow_engine,identities,enabled,request,point):
    setup=ready(flow_engine,identities)
    class Fault(CustomerUnitOfWork):
        def commit(self):
            if point=='before_commit':
                self.poison();raise AcceptanceOutcomeUnknown()
            super().commit()
            if point=='after_commit':raise AcceptanceOutcomeUnknown()
        def __exit__(self,*args):
            result=super().__exit__(*args)
            if point=='close':raise AcceptanceOutcomeUnknown()
            return result
    caller=service(flow_engine,identities,mock=CoreMockNotification(flow_engine,uow_factory=Fault))
    uncertain=caller.send(setup['work_id'])
    assert uncertain.status in {'UNKNOWN','SENT'}
    saved=rows(flow_engine,facts)
    assert all(fact['status']=='SENT' for fact in saved)
    assert len(saved)==int(point!='before_commit')
    before=snapshot(flow_engine)
    class QueryOnly(CoreMockNotification):
        def deliver(self,*args):pytest.fail('T2 uncertainty attempted send')
    recovered=service(flow_engine,identities,mock=QueryOnly(flow_engine)).reconcile(setup['work_id'])
    assert recovered.status==('UNKNOWN' if point=='before_commit' else 'SENT')
    assert rows(flow_engine,facts)==saved
    if point=='before_commit':assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,point=point,result=asdict(uncertain),recovered=asdict(recovered),
        before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('phase',['T1','T3'])
@pytest.mark.parametrize('table_name',['notification_delivery_controls','customer_history_revisions',
    'customer_history_contents','founder_history_encodings','case_heads','customer_audit_events',
    'lifecycle_source_bindings','case_lifecycle_state','lifecycle_event_receipts','lifecycle_work'])
def test_each_domain_write_family_rolls_back_without_losing_committed_t2(
        flow_engine,identities,enabled,request,phase,table_name):
    setup=ready(flow_engine,identities)
    if phase=='T3':
        from test_notification_delivery_postgresql import LostReply
        assert service(flow_engine,identities,mock=LostReply(flow_engine)).send(setup['work_id']).status=='UNKNOWN'
        assert len(rows(flow_engine,facts))==1
    before=snapshot(flow_engine);hit=[]
    class Fault(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            result=super().execute(statement,parameters)
            table=getattr(statement,'table',None)
            if (not getattr(statement,'is_select',False) and table is not None
                    and table.name==table_name and not hit):
                hit.append(table.name);self.poison();raise FlowError('INTERNAL_ERROR')
            return result
    caller=service(flow_engine,identities,uow_factory=Fault)
    result=caller.send(setup['work_id']) if phase=='T1' else caller.reconcile(setup['work_id'])
    assert hit==[table_name] and result.status=='UNKNOWN'
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,phase=phase,table=table_name,result=asdict(result),
        before=before,after=snapshot(flow_engine))


def test_authority_change_after_guard_apply_cannot_commit_or_send(flow_engine,identities,enabled,request,monkeypatch):
    setup=ready(flow_engine,identities);caller=service(flow_engine,identities)
    original=caller.guard.apply;hit=[]
    def changed(uow,event,now):
        result=original(uow,event,now)
        assert uow.execute(update(life.authorities).where(
            life.authorities.c.component_id==COMPONENT).values(enabled=False,revision=2)).rowcount==1
        hit.append(True)
        return result
    monkeypatch.setattr(caller.guard,'apply',changed)
    before=snapshot(flow_engine)
    assert caller.send(setup['work_id']).status=='UNKNOWN'
    assert hit==[True] and snapshot(flow_engine)==before and rows(flow_engine,facts)==[]
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))
