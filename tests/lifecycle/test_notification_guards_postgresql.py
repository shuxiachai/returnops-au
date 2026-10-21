"""Cloud-only direct Domain attacks and final-commit provenance closure."""
from dataclasses import asdict
import pytest
from sqlalchemy import select, update, delete
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.audit import identifier, timestamp
from returnops_domain.canonical import digest, encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.lifecycle_events import NotificationObserved
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.manual_target import one
from returnops_domain.notification_tables import controls, facts
from returnops_domain.notification_profile import COMPONENT
from returnops_domain.notification_history import append_note
from returnops_domain.notification_sources import validate_control, reservation_core, phase_payload
from returnops_domain.return_execution_sources import database_now
from notification_helpers import ready, service, rows, snapshot, evidence
from test_notification_delivery_postgresql import LostReply


@pytest.mark.parametrize('status',['SENT','NO_EFFECT_FAILED'])
def test_direct_guard_cannot_reserve_again_after_unaccepted_independent_fact(
        flow_engine,identities,enabled,request,status):
    setup=ready(flow_engine,identities)
    class Lost(LostReply):
        def _outcome(self):return status
    assert service(flow_engine,identities,mock=Lost(flow_engine)).send(setup['work_id']).status=='UNKNOWN'
    assert rows(flow_engine,facts)[0]['status']==status
    before=snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=one(uow,old.case_heads,case_id=setup['case_id'])
        control=one(uow,controls,notification_work_id=setup['work_id'])
        seal=validate_control(uow,head,control)
        guard=LifecycleGuards(COMPONENT)
        now=database_now(uow);claim=guard.claim(uow,setup['work_id'],now)
        claimed=one(uow,life.work,work_id=setup['work_id'])
        record_id,event_id=identifier('attack_note'),identifier('attack_event')
        staged={**control,'attempt_count':2,'reservation_id':identifier('attack_reservation')}
        core=reservation_core(staged,claim,now,claimed['lease_expires_at'])
        values=dict(state='RESERVED',attempt_count=2,reservation_id=staged['reservation_id'],
            reservation_claim_id=claim.claim_id,reservation_epoch=claim.epoch,
            reservation_case_version=claim.case_version,reservation_authority_revision=claim.authority_revision,
            reservation_at=now,reservation_deadline=claimed['lease_expires_at'],
            reservation_core=encode_document(core),reservation_hash=digest(core,'notification-reservation/v2'),
            reservation_record_id=record_id,reservation_event_id=event_id)
        uow.execute(update(controls).where(controls.c.notification_work_id==setup['work_id']).values(**values))
        body={**seal['note'],'case_version':head['case_version'],'attempt_count':2,'updated_at':timestamp(now)}
        append_note(uow,head,body,record_id=record_id,object_version=len(seal['revisions'])+1,
            actor_component=COMPONENT,correlation=event_id,
            payload=phase_payload(control,'RESERVE',values['reservation_hash']),
            now=now,claim=claim,target=control['outcome_record_id'])
        with pytest.raises(FlowError):
            guard.apply(uow,NotificationObserved(event_id,claim,record_id),now)
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,independent_status=status,before=before,after=snapshot(flow_engine))


def test_current_independent_fact_cannot_be_prefilled_as_domain_acceptance(
        flow_engine,identities,enabled,request):
    setup=ready(flow_engine,identities)
    assert service(flow_engine,identities,mock=LostReply(flow_engine)).send(setup['work_id']).status=='UNKNOWN'
    fact=rows(flow_engine,facts)[0];control=rows(flow_engine,controls)[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(controls).values(accepted_fact_id=fact['fact_id'],
            accepted_record_id=control['reservation_record_id'],accepted_event_id=control['reservation_event_id']))
        uow.commit()
    before=snapshot(flow_engine)
    assert service(flow_engine,identities).reconcile(setup['work_id']).status=='UNKNOWN'
    assert snapshot(flow_engine)==before
    assert not [row for row in rows(flow_engine,old.history) if row['kind']=='OUTCOME_MESSAGE']
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))


def test_fresh_initial_producer_note_without_control_is_not_a_legacy_read(
        flow_engine,identities,enabled,request):
    from returnops_domain.notification_projection import verify_founder_note
    setup=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert uow.execute(delete(controls).where(controls.c.notification_work_id==setup['work_id'])).rowcount==1
        uow.commit()
    before=snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        head=one(uow,old.case_heads,case_id=setup['case_id'])
        note=one(uow,old.history,record_id=setup['control']['initial_notification_record_id'])
        with pytest.raises(FlowError):verify_founder_note(uow,head,note)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('field,value',[('source_id','unrelated_source_record'),('case_id','unrelated_case'),
    ('pre_input_version',13),('pre_generation',13),('status','COMPLETED')])
def test_original_outcome_receipt_corruption_cannot_start_delivery(
        flow_engine,identities,enabled,request,field,value):
    setup=ready(flow_engine,identities,'manual_block')
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(life.events).where(life.events.c.event_id==setup['control']['outcome_event_id']).values(
            **{field:value}))
        uow.commit()
    before=snapshot(flow_engine)
    assert service(flow_engine,identities).send(setup['work_id']).status=='UNKNOWN'
    assert rows(flow_engine,facts)==[] and snapshot(flow_engine)==before
    evidence(request.node.nodeid,field=field,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('field,value',[('source_id','unrelated_source_record'),
    ('pre_input_version',13),('pre_generation',13),('status','COMPLETED')])
def test_guard_final_commit_rejects_notification_receipt_changed_after_apply(
        flow_engine,identities,enabled,request,monkeypatch,field,value):
    setup=ready(flow_engine,identities);caller=service(flow_engine,identities)
    original=caller.guard.apply;seen=[]
    def changed(uow,event,now):
        accepted=original(uow,event,now)
        assert uow.execute(update(life.events).where(life.events.c.event_id==event.event_id).values(
            **{field:value})).rowcount==1
        seen.append(event.event_id)
        return accepted
    monkeypatch.setattr(caller.guard,'apply',changed)
    before=snapshot(flow_engine)
    assert caller.send(setup['work_id']).status=='UNKNOWN'
    assert len(seen)==1 and snapshot(flow_engine)==before and rows(flow_engine,facts)==[]
    evidence(request.node.nodeid,field=field,seen=seen,before=before,after=snapshot(flow_engine))
