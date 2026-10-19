from dataclasses import replace
from datetime import timedelta
import pytest
from sqlalchemy import select, update, func
from returnops_domain import customer_tables as old, lifecycle_tables as t, investigation_tables as investigation
from returnops_domain.audit import identifier, verify_chain
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.lifecycle_events import ProposalAccepted, RevisionRequested, NotificationObserved
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.lifecycle_state import invalidate
from returnops_domain.retention import RetentionService
from synthetic_sources import COMPONENT, now, ready, proposal, outcome, notify, rows, head, material, stage, bind_source, claim


@pytest.mark.parametrize('flow_engine',['0007_lifecycle_guards','head'],indirect=True)
def test_proposal_then_same_input_revision_revokes_actual_old_claim_and_keeps_monotonic_version(flow_engine,identities,enabled):
    from returnops_domain.lifecycle_schema import version, CURRENT
    from returnops_domain.lifecycle_events import LifecycleClaim, OutcomeAccepted
    with flow_engine.connect() as connection:
        modern=version(connection)==CURRENT
    revision_component=late_component=proposal_component=COMPONENT
    if modern:
        # Modern HUMAN revision has a full real fixed proposal/PASS predecessor;
        # exact 0007 retains the original legacy fixture and assertions below.
        from pass_revision_helpers import ready as pass_ready, attempt, assert_revised
        from manual_helpers import provision_outcome
        from returnops_domain.manual_denial import COMPONENT as MANUAL
        from returnops_domain.revision_denial import COMPONENT as REVISION
        from returnops_domain.proposal_processor import FixedProposalProcessor
        from pass_review_helpers import build_positive
        def stored_event(kind, event_type):
            saved=next(r for r in rows(flow_engine,t.events) if r['event_kind']==kind)
            work=next(r for r in rows(flow_engine,t.work) if r['work_id']==saved['work_id'])
            token=LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],
                work['input_version'],work['generation'],work['authority_revision'])
            return event_type(saved['event_id'],token,saved['record_id']),dict(saved),work['component_id']
        case,request_body,action,at=pass_ready(flow_engine,identities,preview_mode='none')
        first,_,proposal_component=stored_event('PROPOSAL',ProposalAccepted)
        before=rows(flow_engine,old.case_heads)[0]
        provision_outcome(flow_engine,identities)
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            late=claim(uow,case,OutcomeAccepted,component=MANUAL);uow.commit()
        at=now()
        assert_revised(flow_engine,case,request_body,attempt(flow_engine,identities,case,request_body,at),action=action)
        event,accepted,revision_component=stored_event('REVISION',RevisionRequested)
        revision=event.claim
        late_component=MANUAL
        assert revision_component==REVISION
    else:
        original=ready(flow_engine,identities);case=original['case_id']
        first,_=proposal(flow_engine,identities,case)
        before=rows(flow_engine,old.case_heads)[0]
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            # Explicit legacy later-A2 initial condition for the legal edge.
            uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status='AWAITING_APPROVAL'))
            revision=claim(uow,case,RevisionRequested)
            # A second consumer is durably claimed against this same current target.
            late=claim(uow,case,OutcomeAccepted)
            h=head(uow,case);body=material('DECISION',h,identities)['content']
            body.update(decision='REQUEST_REVISION');body.pop('approval_id',None)
            source=stage(uow,h,'DECISION',body);bind_source(uow,source,revision,target_record_id=first.record_id)
            event=RevisionRequested(identifier('event'),revision,source)
            accepted=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
    current=rows(flow_engine,old.case_heads)[0];state=rows(flow_engine,t.state)[0]
    assert current['input_version']==before['input_version'] and current['status']=='POLICY_ASSESSMENT'
    assert state['proposal_record_id'] is None and state['proposal_version']==1
    accepted_work=next(r for r in rows(flow_engine,t.work) if r['work_id']==revision.work_id)
    assert (accepted_work['state'],accepted_work['claim_id'],accepted_work['epoch'],accepted_work['generation'])==(
        'DONE',revision.claim_id,revision.epoch,revision.generation)
    assert next(r for r in rows(flow_engine,t.work) if r['work_id']==late.work_id)['state']=='SUPERSEDED'
    history_count=len(rows(flow_engine,old.history))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        h=head(uow,case);body=material('DECISION',h,identities)['content']
        body.update(decision='MANUAL_HANDLING',decision_id=identifier('late_decision'));body.pop('approval_id',None)
        late_source=stage(uow,h,'DECISION',body);bind_source(uow,late_source,late)
        from returnops_domain.lifecycle_events import OutcomeAccepted
        with pytest.raises(FlowError):
            LifecycleGuards(late_component).apply(uow,OutcomeAccepted(identifier('late_event'),late,late_source,'absent_notification'),now())
        with pytest.raises(FlowError): uow.commit()
    assert len(rows(flow_engine,old.history))==history_count
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert LifecycleGuards(revision_component).apply(uow,event,now())==accepted
        uow.commit()
    # Clearing current references never permits the old source to be accepted again.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):
            LifecycleGuards(proposal_component).apply(uow,replace(first,event_id=identifier('different_event')),now())
        with pytest.raises(FlowError): uow.commit()
    if modern:
        processor=FixedProposalProcessor(flow_engine,build=build_positive)
        assert processor.process(processor.prepare(case)).status=='ACCEPTED'
        from types import SimpleNamespace
        second=SimpleNamespace(record_id=rows(flow_engine,t.state)[0]['proposal_record_id'])
    else:
        second,_=proposal(flow_engine,identities,case,version=2)
    assert second.record_id!=first.record_id and rows(flow_engine,t.state)[0]['proposal_version']==2
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert verify_chain(uow,case);uow.commit()


@pytest.mark.parametrize('decision,terminal',[('REJECT','REJECTED'),('MANUAL_HANDLING','MANUAL_HANDLED')])
@pytest.mark.parametrize('flow_engine',['0007_lifecycle_guards','head'],indirect=True)
def test_saved_notification_pending_failed_sent_keeps_identity_and_has_no_effects(flow_engine,identities,enabled,decision,terminal):
    from returnops_domain.lifecycle_schema import version, CURRENT
    with flow_engine.connect() as connection:
        modern=version(connection)==CURRENT
        modern_reject=decision=='REJECT' and modern
    component=COMPONENT
    if modern_reject:
        # Modern schema proves a real accepted PASS before the actual private
        # HUMAN REJECT entry. Exact 0007 retains its original fixture below.
        from reject_helpers import ready as reject_ready, attempt, assert_rejected
        from returnops_domain.reject_denial import COMPONENT as REJECT_COMPONENT
        case,body=reject_ready(flow_engine,identities)
        assert_rejected(flow_engine,case,body,attempt(flow_engine,identities,case,body))
        component=REJECT_COMPONENT
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=component,purpose='NOTIFICATION',revision=1,enabled=True));uow.commit()
    elif modern:
        from pass_manual_helpers import accepted_pass_manual
        case,accepted,_,component=accepted_pass_manual(flow_engine,identities)
    else:
        original=ready(flow_engine,identities);case=original['case_id'];proposal(flow_engine,identities,case)
        accepted,_=outcome(flow_engine,identities,case,decision=decision)
    frozen=rows(flow_engine,t.state)[0]
    event,receipt=notify(flow_engine,identities,case,'FAILED',component=component)
    assert receipt['status']=='NOTIFICATION_FAILED'
    first_work=event.claim.work_id
    event,receipt=notify(flow_engine,identities,case,'PENDING',component=component)
    assert receipt['status']=='NOTIFICATION_PENDING' and event.claim.work_id==first_work
    event,receipt=notify(flow_engine,identities,case,'SENT',component=component)
    assert receipt['status']==terminal and event.claim.work_id==first_work
    state=rows(flow_engine,t.state)[0]
    assert (state['outcome'],state['notification_id'],state['notification_hash'])==(frozen['outcome'],frozen['notification_id'],frozen['notification_hash'])
    assert rows(flow_engine,t.effects)==[]
    assert not [r for r in rows(flow_engine,old.history) if r['kind']=='OPERATION']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert LifecycleGuards(component).apply(uow,event,now())==receipt;uow.commit()
    # Each modern decision adds the actual REVIEW_PASS receipt; original outcome,
    # FAILED -> PENDING -> SENT and replay assertions remain above.
    assert len(rows(flow_engine,t.events))==(6 if modern else 5)


@pytest.mark.parametrize('field,value',[('notification_id','foreign_notification'),('outcome','RETURN_CREATED'),
    ('message','changed message'),('next_steps',['changed next step'])])
def test_notification_cannot_change_frozen_identity_or_payload(flow_engine,identities,enabled,field,value):
    from pass_manual_helpers import accepted_pass_manual
    case,_,_,component=accepted_pass_manual(flow_engine,identities)
    before=rows(flow_engine,t.state)[0];history=len(rows(flow_engine,old.history))
    with pytest.raises(FlowError):
        notify(flow_engine,identities,case,'SENT',mutate=lambda body:body.update({field:value}),component=component)
    assert rows(flow_engine,t.state)[0]==before and len(rows(flow_engine,old.history))==history


@pytest.mark.parametrize('field,value',[('epoch',88),('claim_id','foreign_claim'),('work_id','foreign_work'),
    ('generation',999),('input_version',88),('authority_revision',88)])
def test_mismatched_claim_poison_rolls_back_staged_source(flow_engine,identities,enabled,field,value):
    original=ready(flow_engine,identities);case=original['case_id'];before=len(rows(flow_engine,old.history))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,ProposalAccepted);h=head(uow,case)
        source=stage(uow,h,'PROPOSAL',material('PROPOSAL',h,identities,uow=uow)['content'])
        bind_source(uow,source,token)
        event=ProposalAccepted(identifier('event'),replace(token,**{field:value}),source)
        with pytest.raises(FlowError): LifecycleGuards(COMPONENT).apply(uow,event,now())
        with pytest.raises(FlowError): uow.commit()
    assert len(rows(flow_engine,old.history))==before and rows(flow_engine,t.events)==[]


def test_claim_exclusion_lease_epoch_and_revoked_capability(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];guard=LifecycleGuards(COMPONENT)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        first=claim(uow,case,ProposalAccepted);uow.commit()
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert guard.claim(uow,first.work_id,now()) is None
        second=guard.claim(uow,first.work_id,now()+timedelta(seconds=61));uow.commit()
    assert second.epoch==first.epoch+1 and second.claim_id!=first.claim_id
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(t.authorities).where(t.authorities.c.purpose=='PROPOSAL').values(enabled=False))
        uow.commit()
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError): guard.claim(uow,first.work_id,now()+timedelta(seconds=122))
        with pytest.raises(FlowError): uow.commit()


def test_current_order_block_allows_manual_outcome_but_cannot_revision(flow_engine,identities,enabled):
    original=ready(flow_engine,identities,reference='SYN-CONFLICT');case=original['case_id']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError): claim(uow,case,RevisionRequested)
        with pytest.raises(FlowError): uow.commit()
    outcome(flow_engine,identities,case,target_kind='ORDER_LOOKUP_BLOCK')
    assert notify(flow_engine,identities,case,'SENT')[1]['status']=='MANUAL_HANDLED'
    assert rows(flow_engine,t.effects)==[]


def test_retention_erases_derived_bodies_pauses_claim_and_never_restores_source(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];proposal(flow_engine,identities,case)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,RevisionRequested);uow.commit()
    previous=rows(flow_engine,old.case_heads)[0]
    assert RetentionService(flow_engine).remove('STATEMENT',original['statements'][0]['statement_id'])
    state=rows(flow_engine,t.state)[0]
    assert not state['available'] and state['proposal_record_id'] is None
    assert rows(flow_engine,old.case_heads)[0]['status']==previous['status']
    assert next(r for r in rows(flow_engine,t.work) if r['work_id']==token.work_id)['state']=='PAUSED'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError): LifecycleGuards(COMPONENT).claim(uow,token.work_id,now()+timedelta(seconds=61))
        with pytest.raises(FlowError): uow.commit()
    assert all(r['retention_state']=='DELETED' for r in rows(flow_engine,old.history))
    assert rows(flow_engine,old.history_contents)==[]


def test_cross_case_source_reference_poison_does_not_leave_foreign_history(flow_engine,identities,enabled):
    first=ready(flow_engine,identities,key='first-case');second=ready(flow_engine,identities,key='second-case')
    before=len(rows(flow_engine,old.history))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,first['case_id'],ProposalAccepted);foreign=head(uow,second['case_id'])
        source=stage(uow,foreign,'PROPOSAL',material('PROPOSAL',foreign,identities,uow=uow)['content'])
        bind_source(uow,source,token)
        with pytest.raises(FlowError):
            LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(identifier('event'),token,source),now())
        with pytest.raises(FlowError):uow.commit()
    assert len(rows(flow_engine,old.history))==before and rows(flow_engine,t.events)==[]


@pytest.mark.parametrize('change',[{'enabled':False},{'role':'CUSTOMER'},{'store_id':'foreign_store'}])
def test_new_decision_rechecks_causal_founder_current_principal(flow_engine,identities,enabled,change,monkeypatch):
    from returnops_domain.registry import TrustedRegistry
    from returnops_domain.lifecycle_sources import Sources
    from manual_helpers import snapshot
    from pass_manual_helpers import ready as pass_ready, prove_pass_manual_target, stage_pass_manual_event
    case,body,_,_=pass_ready(flow_engine,identities,preview_mode='none')
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        _,proven_before=prove_pass_manual_target(uow,case,body);uow.commit()
    TrustedRegistry(flow_engine).change_principal(identities.people['founder']['principal_id'],**change)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        _,proven_after=prove_pass_manual_target(uow,case,body)
        assert proven_after==proven_before
        uow.commit()
    before=len(rows(flow_engine,old.history))
    saved=snapshot(flow_engine);observed=[];original_read=Sources.read
    at=now()
    assert at.utcoffset() is not None and at>=proven_after['event']['accepted_at']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        guard,event=stage_pass_manual_event(uow,identities,case,body,at)
        def causal_read(self,record_id,kinds,**options):
            try:
                return original_read(self,record_id,kinds,**options)
            except FlowError as error:
                if record_id==event.record_id and options.get('current_actor',True):
                    observed.append((record_id,tuple(sorted(kinds)),error.code))
                raise
        monkeypatch.setattr(Sources,'read',causal_read)
        with pytest.raises(FlowError) as denied:
            guard.apply(uow,event,at)
        assert denied.value.code=='FORBIDDEN'
        assert observed==[(event.record_id,('DECISION','NOTIFICATION'),'FORBIDDEN')]
        with pytest.raises(FlowError):uow.commit()
    assert len(rows(flow_engine,old.history))==before and rows(flow_engine,t.state)[0]['outcome'] is None
    assert snapshot(flow_engine)==saved


def test_notification_retry_uses_current_service_not_expired_original_human_authority(flow_engine,identities,enabled):
    from returnops_domain.registry import TrustedRegistry
    from pass_manual_helpers import accepted_pass_manual
    case,_,_,component=accepted_pass_manual(flow_engine,identities)
    TrustedRegistry(flow_engine).change_principal(identities.people['founder']['principal_id'],enabled=False)
    assert notify(flow_engine,identities,case,'SENT',component=component)[1]['status']=='MANUAL_HANDLED'


def test_failed_notification_requires_saved_pending_retry_before_sent(flow_engine,identities,enabled):
    from pass_manual_helpers import accepted_pass_manual
    case,_,_,component=accepted_pass_manual(flow_engine,identities)
    notify(flow_engine,identities,case,'FAILED',component=component);before=rows(flow_engine,old.history)
    with pytest.raises(FlowError):notify(flow_engine,identities,case,'SENT',component=component)
    assert rows(flow_engine,old.history)==before
    notify(flow_engine,identities,case,'PENDING',component=component)
    assert notify(flow_engine,identities,case,'SENT',component=component)[1]['status']=='MANUAL_HANDLED'


def test_risk_revise_consumes_exact_current_proposal_without_increasing_input(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];accepted,_=proposal(flow_engine,identities,case)
    before=rows(flow_engine,old.case_heads)[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,RevisionRequested);h=head(uow,case)
        body=material('REVIEW',h,identities,proposal_record_id=accepted.record_id)['content']
        body['review'].update(outcome='REVISE',revision_requests=['bounded synthetic revision'],questions=[])
        source=stage(uow,h,'REVIEW',body);bind_source(uow,source,token,target_record_id=accepted.record_id)
        result=LifecycleGuards(COMPONENT).apply(uow,RevisionRequested(identifier('event'),token,source),now());uow.commit()
    assert result['status']=='POLICY_ASSESSMENT' and result['input_version']==before['input_version']
    assert rows(flow_engine,t.state)[0]['proposal_record_id'] is None
    work=next(row for row in rows(flow_engine,t.work) if row['work_id']==token.work_id)
    assert (work['claim_id'],work['epoch'],work['state'])==(token.claim_id,token.epoch,'DONE')


def test_outcome_atomically_saves_stable_unclaimed_notification_intent_without_grant(flow_engine,identities,enabled):
    from pass_manual_helpers import accepted_pass_manual
    case,event,receipt,component=accepted_pass_manual(flow_engine,identities,notification_grant=False)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(t.authorities.delete().where(t.authorities.c.purpose=='NOTIFICATION'));uow.commit()
    state=rows(flow_engine,t.state)[0]
    notification=next(row for row in rows(flow_engine,t.work) if row['purpose']=='NOTIFICATION')
    assert notification['work_id']==state['notification_work_id'] and notification['idempotency_key']
    assert (notification['state'],notification['epoch'],notification['authority_revision'])==('PENDING',0,None)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert LifecycleGuards(component).apply(uow,event,now())==receipt;uow.commit()
    assert next(row for row in rows(flow_engine,t.work) if row['purpose']=='NOTIFICATION')==notification
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):claim(uow,case,NotificationObserved,component=component)
        with pytest.raises(FlowError):uow.commit()
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(t.authorities.insert().values(store_id=identities.people['customer_a']['store_id'],
            component_id=component,purpose='NOTIFICATION',enabled=True,revision=7));uow.commit()
    sent,_=notify(flow_engine,identities,case,'SENT',component=component)
    current_work=next(row for row in rows(flow_engine,t.work) if row['purpose']=='NOTIFICATION')
    assert sent.claim.work_id==notification['work_id'] and sent.claim.authority_revision==7
    assert current_work['idempotency_key']==notification['idempotency_key']
