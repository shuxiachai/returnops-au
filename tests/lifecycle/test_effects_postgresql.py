import pytest
from sqlalchemy import update
from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from synthetic_sources import ready, outcome, notify, rows
from synthetic_effects import existing_execution, observe, return_outcome


@pytest.mark.parametrize('decision,terminal',[('REJECT','REJECTED'),('MANUAL_HANDLING','MANUAL_HANDLED')])
@pytest.mark.parametrize('notification_status',['PENDING','FAILED','SENT'])
def test_late_both_effect_successes_preserve_accepted_outcome_and_notification(flow_engine,identities,enabled,decision,terminal,notification_status):
    original=ready(flow_engine,identities);case=original['case_id']
    operations=existing_execution(flow_engine,identities,case)
    # Explicit private future-A2 failure starting condition; no provider runs.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(
            status='AWAITING_APPROVAL' if decision=='REJECT' else 'ESCALATED'));uow.commit()
    outcome(flow_engine,identities,case,decision=decision)
    if notification_status!='PENDING':
        notify(flow_engine,identities,case,notification_status)
    state=rows(flow_engine,t.state)[0];status=rows(flow_engine,old.case_heads)[0]['status']
    notes=[r for r in rows(flow_engine,old.history) if r['kind']=='NOTIFICATION']
    for operation in operations:
        observe(flow_engine,identities,case,operation)
    assert rows(flow_engine,old.case_heads)[0]['status']==status
    assert rows(flow_engine,t.state)[0]==state
    assert [r for r in rows(flow_engine,old.history) if r['kind']=='NOTIFICATION']==notes
    assert len(rows(flow_engine,t.effects))==2
    if notification_status!='SENT':
        if notification_status=='FAILED':notify(flow_engine,identities,case,'PENDING')
        assert notify(flow_engine,identities,case,'SENT')[1]['status']==terminal


@pytest.mark.parametrize('status',['ACTION_IN_PROGRESS','RECONCILING'])
def test_current_saved_return_label_then_matching_sent_is_completed(flow_engine,identities,enabled,status):
    original=ready(flow_engine,identities);case=original['case_id'];operations=existing_execution(flow_engine,identities,case)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status=status));uow.commit()
    returned,_=observe(flow_engine,identities,case,operations[0])
    labeled,_=observe(flow_engine,identities,case,operations[1])
    assert return_outcome(flow_engine,identities,case,returned.record_id,labeled.record_id)[1]['status']=='NOTIFICATION_PENDING'
    before=rows(flow_engine,t.effects)
    assert notify(flow_engine,identities,case,'FAILED')[1]['status']=='NOTIFICATION_FAILED'
    assert notify(flow_engine,identities,case,'PENDING')[1]['status']=='NOTIFICATION_PENDING'
    assert notify(flow_engine,identities,case,'SENT')[1]['status']=='COMPLETED'
    assert rows(flow_engine,t.effects)==before


@pytest.mark.parametrize('field,value',[('command_id','wrong_command'),('provider_id','wrong_provider'),
    ('operation_fingerprint','f'*64),('approval_id','wrong_approval'),('input_version',9)])
def test_mismatched_operation_chain_rejected_atomically(flow_engine,identities,enabled,field,value):
    original=ready(flow_engine,identities);case=original['case_id'];operations=existing_execution(flow_engine,identities,case)
    before=len(rows(flow_engine,old.history))
    with pytest.raises(FlowError):
        observe(flow_engine,identities,case,operations[0],mutate=lambda body:body.update({field:value}))
    assert rows(flow_engine,t.effects)==[] and len(rows(flow_engine,old.history))==before


def test_arbitrary_same_case_pdf_cannot_replace_original_label_artifact(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];operations=existing_execution(flow_engine,identities,case)
    with pytest.raises(FlowError):
        observe(flow_engine,identities,case,operations[1],mutate=lambda body:body['result'].update(label_evidence_id='different_saved_pdf'))
    assert rows(flow_engine,t.effects)==[]


@pytest.mark.parametrize('status',['EXECUTING','UNKNOWN','RECONCILING'])
def test_unindexed_latest_operation_blocks_return_outcome_with_no_partial_notification(flow_engine,identities,enabled,status):
    from copy import deepcopy
    from returnops_domain.audit import identifier
    from synthetic_sources import head,stage
    original=ready(flow_engine,identities);case=original['case_id'];operations=existing_execution(flow_engine,identities,case)
    returned,_=observe(flow_engine,identities,case,operations[0]);labeled,_=observe(flow_engine,identities,case,operations[1])
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        extra=deepcopy(operations[0]['body']);extra.update(operation_id=identifier('unindexed_operation'),status=status)
        stage(uow,head(uow,case),'OPERATION',extra);uow.commit()
    before_history=rows(flow_engine,old.history);before_events=rows(flow_engine,t.events)
    with pytest.raises(FlowError):return_outcome(flow_engine,identities,case,returned.record_id,labeled.record_id)
    assert rows(flow_engine,old.history)==before_history and rows(flow_engine,t.events)==before_events
    assert rows(flow_engine,t.state)[0]['outcome'] is None


@pytest.mark.parametrize('status,decision',[
    ('RISK_REVIEW','REJECT'),('RISK_REVIEW','MANUAL_HANDLING'),('ESCALATED','REJECT'),
    ('ACTION_IN_PROGRESS','REJECT'),('ACTION_FAILED','MANUAL_HANDLING'),('RECONCILING','MANUAL_HANDLING')])
def test_decision_outcome_does_not_borrow_execution_or_review_edges(flow_engine,identities,enabled,status,decision):
    from synthetic_sources import proposal
    original=ready(flow_engine,identities);case=original['case_id'];proposal(flow_engine,identities,case)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status=status));uow.commit()
    before=rows(flow_engine,old.history)
    with pytest.raises(FlowError):outcome(flow_engine,identities,case,decision=decision,fixture_prepare=False)
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.state)[0]['outcome'] is None


def test_notification_claim_survives_unrelated_late_effect_case_version_changes(flow_engine,identities,enabled):
    from sqlalchemy import select
    from returnops_domain import founder_codec as finite
    from returnops_domain.audit import identifier,timestamp
    from returnops_domain.lifecycle_events import NotificationObserved
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from synthetic_sources import COMPONENT,claim,head,stage,bind_source,now
    original=ready(flow_engine,identities);case=original['case_id'];operations=existing_execution(flow_engine,identities,case)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status='ESCALATED'));uow.commit()
    outcome(flow_engine,identities,case)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,NotificationObserved);uow.commit()
    for operation in operations:observe(flow_engine,identities,case,operation)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        h=head(uow,case);state=uow.execute(select(t.state).where(t.state.c.case_id==case)).mappings().one()
        assert h['case_version']==token.case_version+2
        body=finite.decode_document(uow.execute(select(old.history_contents.c.body).where(
            old.history_contents.c.record_id==state['notification_record_id'])).scalar_one())
        body.update(status='SENT',case_version=h['case_version'],sent_at=timestamp(now()))
        source=stage(uow,h,'NOTIFICATION',body,object_version=2);bind_source(uow,source,token,target_record_id=state['outcome_record_id'])
        result=LifecycleGuards(COMPONENT).apply(uow,NotificationObserved(identifier('event'),token,source),now());uow.commit()
    assert result['status']=='MANUAL_HANDLED'
