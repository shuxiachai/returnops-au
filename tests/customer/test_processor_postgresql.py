"""Real PostgreSQL durable intake lifecycle and immutable receipt regressions."""
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,func,update
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier,verify_chain
from returnops_domain.canonical import decode_document,encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError,AcceptanceOutcomeUnknown
from returnops_domain.intake_processor import IntakeProcessor,IntakeResult
from returnops_domain.registry import TrustedRegistry

def rows(engine,table):
    with engine.connect() as c: return list(c.execute(select(table)).mappings())

def test_original_receipt_survives_processing_and_replay_does_not_enqueue(flow_engine,identities):
    flow=identities.flow(); request={'original_message':'unchanged original'}
    accepted=flow.create(request,'original-key',identifier('corr'))
    assert accepted.body['status']=='SUBMITTED'
    worker=IntakeProcessor(flow_engine);assert worker.run_once()
    current=flow.get_case(accepted.body['case_id']).body
    assert (current['status'],current['case_version'],current['input_version'])==('AWAITING_INFORMATION',2,1)
    assert 'alternative' in current['clarification']['questions'][0]['text']
    replay=flow.create(request,'original-key',identifier('corr'))
    assert replay.replayed and replay.body==accepted.body
    assert len(rows(flow_engine,t.intake_work))==1
    assert not worker.run_once()
    assert rows(flow_engine,t.intake_sessions)[0]['clarification_round']==1
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert verify_chain(uow,current['case_id']);uow.commit()

def test_clarification_admits_then_processes_preserving_receipt(flow_engine,identities):
    flow=identities.flow();case=flow.create({'original_message':'original'},'create-key',identifier('corr')).body['case_id']
    worker=IntakeProcessor(flow_engine);assert worker.run_once(); view=flow.get_case(case).body
    request={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
             'answers':[{'question_id':view['clarification']['questions'][0]['question_id'],'text':'  alternative context\x00\ud800  '}],'evidence_ids':[]}
    accepted=flow.clarify(case,request,'answer-key',identifier('corr'))
    assert (accepted.status,accepted.body['status'],accepted.body['case_version'],accepted.body['input_version'])==(202,'UNDER_INVESTIGATION',3,2)
    assert rows(flow_engine,t.intake_sessions)[0]['status']=='CLARIFICATION_RECEIVED'
    assert worker.run_once()
    assert flow.get_case(case).body['case_version']==4
    assert flow.clarify(case,request,'answer-key',identifier('corr')).body==accepted.body
    assert len(rows(flow_engine,t.intake_work))==2
    assert [s['raw_text'] for s in accepted.body['statements']]==['original','  alternative context\x00\ud800  ']

def test_reference_is_structural_only_and_description_keywords_do_not_prove_purchase(flow_engine,identities):
    flow=identities.flow();a=flow.create({'original_message':'receipt invoice proof words'},'words-key',identifier('corr')).body
    b=flow.create({'original_message':'problem','order_reference':'  unverified-reference  '},'reference-key',identifier('corr')).body
    worker=IntakeProcessor(flow_engine);assert worker.run_once();assert worker.run_once()
    assert flow.get_case(a['case_id']).body['status']=='AWAITING_INFORMATION'
    assert flow.get_case(b['case_id']).body['status']=='UNDER_INVESTIGATION'
    assert all(r['status']!='COMPLETED' for r in rows(flow_engine,t.case_heads))

def test_two_workers_and_expired_claim_discard_late_result(flow_engine,identities):
    flow=identities.flow();case=flow.create({'original_message':'original'},'create-key',identifier('corr')).body['case_id']
    now=datetime.now(timezone.utc);worker=IntakeProcessor(flow_engine,clock=lambda:now,lease_seconds=1)
    claim=worker.claim();assert claim is not None
    assert worker.claim() is None
    now+=timedelta(seconds=2)
    newer=worker.claim();assert newer.epoch==claim.epoch+1
    assert not worker.finish(claim,IntakeResult(True))
    assert worker.finish(newer,IntakeResult(True));assert worker.finish(newer,IntakeResult(True))
    assert flow.get_case(case).body['case_version']==2
    assert len(rows(flow_engine,t.audit))==2

def test_concurrent_workers_claim_once(flow_engine,identities):
    flow=identities.flow();flow.create({'original_message':'original'},'create-key',identifier('corr'))
    def run(_): return IntakeProcessor(flow_engine).run_once()
    with ThreadPoolExecutor(max_workers=4) as pool: outcomes=list(pool.map(run,range(4)))
    assert outcomes.count(True)==1
    assert len(rows(flow_engine,t.audit))==2

def test_http_session_revocation_does_not_cancel_accepted_work(flow_engine,identities):
    flow=identities.flow();flow.create({'original_message':'original'},'create-key',identifier('corr'))
    TrustedRegistry(flow_engine).revoke_session(identities.sessions['customer_a']['session_id'])
    with pytest.raises(FlowError) as e: flow.session()
    assert e.value.code=='UNAUTHENTICATED'
    assert IntakeProcessor(flow_engine).run_once()
    assert rows(flow_engine,t.intake_work)[0]['state']=='DONE'

def test_policy_change_during_compute_pauses_without_failure(flow_engine,identities):
    flow=identities.flow();flow.create({'original_message':'original'},'create-key',identifier('corr'))
    worker=IntakeProcessor(flow_engine);claim=worker.claim()
    registry=TrustedRegistry(flow_engine);registry.change_principal(identities.people['customer_a']['principal_id'],enabled=False)
    assert not worker.finish(claim,IntakeResult(True))
    work=rows(flow_engine,t.intake_work)[0]
    assert (work['state'],work['failure_count'])==('PAUSED',0)
    assert rows(flow_engine,t.case_heads)[0]['case_version']==1
    assert not rows(flow_engine,t.processing_failures)
    registry.change_principal(identities.people['customer_a']['principal_id'],enabled=True)
    assert worker.run_once()

def test_actual_compute_errors_exhaust_local_budget_only(flow_engine,identities):
    flow=identities.flow();flow.create({'original_message':'original'},'create-key',identifier('corr'))
    def fail(_): raise RuntimeError('PRIVATE ORIGINAL NOT TO BE STORED')
    worker=IntakeProcessor(flow_engine,evaluate=fail,retry_seconds=0)
    assert not worker.run_once();assert worker.run_once()
    work=rows(flow_engine,t.intake_work)[0];head=rows(flow_engine,t.case_heads)[0]
    assert (work['state'],work['failure_count'],head['status'],head['case_version'])==('FAILED',2,'ESCALATED',2)
    failure=decode_document(rows(flow_engine,t.processing_failures)[0]['body'])
    assert failure['stage']=='COORDINATOR' and not failure['error']['error']['retryable']
    assert 'PRIVATE' not in repr(failure)
    assert rows(flow_engine,t.intake_sessions)[0]['status']=='ESCALATED_FAILURE'

def test_result_commit_ack_loss_reconciles_without_duplicate_effect(flow_engine,identities):
    flow=identities.flow();flow.create({'original_message':'original'},'create-key',identifier('corr'))
    worker=IntakeProcessor(flow_engine);claim=worker.claim()
    class LostAck(CustomerUnitOfWork):
        raised=False
        def commit(self):
            super().commit()
            if not type(self).raised:
                type(self).raised=True;raise AcceptanceOutcomeUnknown()
    worker.uow_factory=LostAck
    assert worker.finish(claim,IntakeResult(True))
    assert worker.finish(claim,IntakeResult(True))
    assert len(rows(flow_engine,t.audit))==2
    assert len(rows(flow_engine,t.questions))==1
    assert rows(flow_engine,t.intake_sessions)[0]['clarification_round']==1

def test_partial_admission_replaces_question_set_but_processor_reuses_it(flow_engine,identities):
    flow=identities.flow();case=flow.create({'original_message':'original'},'create-key',identifier('corr')).body['case_id']
    worker=IntakeProcessor(flow_engine);assert worker.run_once()
    # Legitimate internal service-issued multi-question fixture. No public route,
    # provider, model output or verified purchase claim is introduced.
    view=flow.get_case(case).body; first=view['clarification']['questions'][0];second={'question_id':identifier('question'),'text':'Provide item context.','reason':'Further structural context.'}
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(t.questions).where(t.questions.c.question_set_id==view['clarification']['question_set_id']).values(
            questions=encode_document([first,second]),question_kinds=encode_document({first['question_id']:'PURCHASE_CONTEXT',second['question_id']:'TEXT_RESPONSE'})));uow.commit()
    req={'expected_case_version':2,'question_set_id':view['clarification']['question_set_id'],'answers':[{'question_id':first['question_id'],'text':'context'}],'evidence_ids':[]}
    accepted=flow.clarify(case,req,'partial-key',identifier('corr')).body
    assert accepted['status']=='AWAITING_INFORMATION' and accepted['input_version']==2
    assert accepted['clarification']['question_set_id']!=view['clarification']['question_set_id']
    assert accepted['clarification']['questions']==[second]
    assert worker.run_once()
    current=flow.get_case(case).body
    assert current['clarification']==accepted['clarification']
    assert rows(flow_engine,t.intake_sessions)[0]['clarification_round']==2

def test_denied_transition_audited_without_acceptance_or_business_mutation(flow_engine,identities):
    flow=identities.flow();case=flow.create({'original_message':'original'},'create-key',identifier('corr')).body['case_id']
    for version,code in [(1,'INVALID_STATE'),(999,'STALE_CASE_VERSION')]:
        with pytest.raises(FlowError) as e:
            flow.clarify(case,{'expected_case_version':version,'question_set_id':'questions_unknown','answers':[],'evidence_ids':['evidence_unknown']},'rejected-key',identifier('corr'))
        assert e.value.code==code
    assert len(rows(flow_engine,t.acceptances))==1 and len(rows(flow_engine,t.intake_work))==1
    assert rows(flow_engine,t.case_heads)[0]['case_version']==1
    events=[decode_document(r['body']) for r in rows(flow_engine,t.audit)]
    assert [e['event_type'] for e in events]==['CUSTOMER_CASE_ACCEPTED','CUSTOMER_TRANSITION_DENIED','CUSTOMER_TRANSITION_DENIED']
    assert all(not e['history_refs'] for e in events[1:])
