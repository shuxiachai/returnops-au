from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select, update, text
from sqlalchemy.exc import DBAPIError
from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError, AcceptanceOutcomeUnknown
from returnops_domain.lifecycle_events import ProposalAccepted
from returnops_domain.lifecycle_guards import LifecycleGuards
from synthetic_sources import COMPONENT,now,ready,head,claim,material,stage,bind_source,rows


def staged(uow,identities,case):
    token=claim(uow,case,ProposalAccepted);h=head(uow,case)
    source=stage(uow,h,'PROPOSAL',material('PROPOSAL',h,identities,uow=uow)['content']);bind_source(uow,source,token)
    return ProposalAccepted(identifier('event'),token,source)


def test_lease_is_rechecked_at_caller_commit_after_guard_return(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];clock=[now()]
    guard=LifecycleGuards(COMPONENT,clock=lambda:clock[0]);before=len(rows(flow_engine,old.history))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case);guard.apply(uow,event,now())
        clock[0]=now()+timedelta(seconds=301)
        with pytest.raises(FlowError):uow.commit()
    assert len(rows(flow_engine,old.history))==before and rows(flow_engine,t.events)==[]


def test_same_transaction_capability_revocation_poison_rolls_back_all_sources(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];before=len(rows(flow_engine,old.history))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case);LifecycleGuards(COMPONENT).apply(uow,event,now())
        uow.execute(update(t.authorities).where(t.authorities.c.purpose=='PROPOSAL').values(enabled=False))
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,t.events)==[] and len(rows(flow_engine,old.history))==before
    assert all(row['enabled'] for row in rows(flow_engine,t.authorities))


def test_row_lock_serializes_even_raw_authority_revocation_until_commit(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id']
    def revoke():
        with flow_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='100ms'"))
            try:
                connection.execute(update(t.authorities).where(t.authorities.c.purpose=='PROPOSAL').values(enabled=False))
            except DBAPIError as error:
                assert getattr(error.orig,'sqlstate',None)=='55P03'
                return 'locked'
            raise AssertionError('Concurrent authority write crossed the locked acceptance')
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case);LifecycleGuards(COMPONENT).apply(uow,event,now())
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(revoke).result(timeout=5)=='locked'
        uow.commit()
    with flow_engine.begin() as connection:
        connection.execute(update(t.authorities).where(t.authorities.c.purpose=='PROPOSAL').values(enabled=False))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,event,now())
        with pytest.raises(FlowError):uow.commit()


def test_unknown_commit_new_component_instance_resolves_original_receipt_once(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id']
    class LostAcknowledgement(CustomerUnitOfWork):
        def commit(self):
            super().commit()
            raise AcceptanceOutcomeUnknown()
    with pytest.raises(AcceptanceOutcomeUnknown):
        with LostAcknowledgement(flow_engine,write=True) as uow:
            event=staged(uow,identities,case);receipt=LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        assert LifecycleGuards(COMPONENT).apply(uow,event,now())==receipt;uow.commit()
    assert len(rows(flow_engine,t.events))==1


def test_real_new_interpreter_reuses_saved_work_acceptance(flow_engine,identities,enabled,tmp_path):
    from dataclasses import asdict
    import json,subprocess,sys
    from pathlib import Path
    original=ready(flow_engine,identities);case=original['case_id']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case);LifecycleGuards(COMPONENT).apply(uow,event,now());uow.commit()
    request=tmp_path/'saved-reference.json';request.write_text(json.dumps(asdict(event)))
    result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('restart_probe.py')),
        flow_engine._customer_test_schema,str(request)],capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode==0,result.stderr
    assert 'PASS original persisted lifecycle acceptance after interpreter restart' in result.stdout
    assert len(rows(flow_engine,t.events))==1


# Historical v1 synthetic delivery compatibility; actual v2 delivery has separate oracles.
@pytest.mark.parametrize('flow_engine',['0013_label_artifact_result'],indirect=True)
def test_supported_same_uow_notification_reclaim_invalidates_earlier_commit_proof(flow_engine,identities,enabled):
    from returnops_domain import founder_codec as finite
    from returnops_domain.lifecycle_events import NotificationObserved
    from pass_manual_helpers import accepted_pass_manual
    case,_,_,component=accepted_pass_manual(flow_engine,identities)
    before_history=rows(flow_engine,old.history);before_events=rows(flow_engine,t.events)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,NotificationObserved,component=component);h=head(uow,case)
        state=uow.execute(select(t.state).where(t.state.c.case_id==case)).mappings().one()
        body=finite.decode_document(uow.execute(select(old.history_contents.c.body).where(
            old.history_contents.c.record_id==state['notification_record_id'])).scalar_one())
        body.update(status='FAILED',case_version=h['case_version'])
        source=stage(uow,h,'NOTIFICATION',body,object_version=2,actor={'kind':'SERVICE','component_id':component})
        bind_source(uow,source,token,target_record_id=state['outcome_record_id'])
        guard=LifecycleGuards(component)
        guard.apply(uow,NotificationObserved(identifier('event'),token,source),now())
        replacement=guard.claim(uow,token.work_id,now())
        assert replacement.epoch==token.epoch+1
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before_history and rows(flow_engine,t.events)==before_events


def test_supported_same_uow_effect_reclaim_invalidates_earlier_commit_proof(flow_engine,identities,enabled):
    from copy import deepcopy
    from returnops_domain.lifecycle_events import EffectObserved
    from synthetic_effects import existing_execution
    original=ready(flow_engine,identities);case=original['case_id'];operation=existing_execution(flow_engine,identities,case)[0]
    before=rows(flow_engine,old.history)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        token=claim(uow,case,EffectObserved,target_record_id=operation['original']);h=head(uow,case)
        body=deepcopy(operation['body']);body.update(status='UNKNOWN',case_version=h['case_version'])
        source=stage(uow,h,'OPERATION',body,object_version=2)
        bind_source(uow,source,token,target_record_id=operation['approval'],dispatch_source_record_id=operation['original'],
            provider_operation_id=body['provider_operation_id'])
        guard=LifecycleGuards(COMPONENT);guard.apply(uow,EffectObserved(identifier('event'),token,source),now())
        assert guard.claim(uow,token.work_id,now()).epoch==token.epoch+1
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.effects)==[]


def test_callback_failure_has_no_sensitive_message_cause_context_or_traceback(flow_engine):
    import traceback
    marker='sensitive-callback-'+identifier('marker')
    def broken():
        raise RuntimeError(marker)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.before_commit(broken)
        with pytest.raises(FlowError) as caught:uow.commit()
        error=caught.value
        assert marker not in str(error)+repr(error)+''.join(traceback.format_exception(error))
        assert error.__cause__ is None and error.__context__ is None
        with pytest.raises(FlowError):uow.commit()


def test_lease_expiring_during_final_proof_validation_cannot_commit(flow_engine,identities,enabled):
    original=ready(flow_engine,identities);case=original['case_id'];before=rows(flow_engine,old.history)
    samples=iter([now(),now()+timedelta(seconds=301)])
    guard=LifecycleGuards(COMPONENT,clock=lambda:next(samples))
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case);guard.apply(uow,event,now())
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]


def test_unexpected_guard_failure_poison_and_diagnostics_do_not_retain_sensitive_context(flow_engine,identities,enabled):
    import traceback
    original=ready(flow_engine,identities);case=original['case_id'];before=rows(flow_engine,old.history)
    marker='sensitive-validation-'+identifier('marker')
    def broken(*args):raise RuntimeError(marker)
    guard=LifecycleGuards(COMPONENT);guard._proposal=broken
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        event=staged(uow,identities,case)
        with pytest.raises(FlowError) as caught:guard.apply(uow,event,now())
        error=caught.value
        assert marker not in str(error)+repr(error)+''.join(traceback.format_exception(error))
        assert error.__cause__ is None and error.__context__ is None
        with pytest.raises(FlowError):uow.commit()
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]
