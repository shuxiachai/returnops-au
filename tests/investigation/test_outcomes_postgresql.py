from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
import pytest
from returnops_domain import customer_tables as old, investigation_tables as t
from returnops_domain.audit import identifier,verify_chain
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.investigation_policy import InvestigationPolicy
from returnops_domain.mock_orders import load_builtin_catalogue
from returnops_domain.order_ports import OrderSourceUnavailable


def rows(engine,table):
    with engine.connect() as c: return list(c.execute(select(table)).mappings())

def admitted(engine,identities,reference='SYN-1001',key='create-key'):
    request={'original_message':'  unchanged original\x00\ud800  '}
    if reference is not None: request['order_reference']=reference
    original=identities.flow().create(request,key,identifier('corr'))
    assert (original.status,original.body['status'],original.body['input_version'])==(201,'SUBMITTED',1)
    assert IntakeProcessor(engine).run_once()
    return original,request

@pytest.mark.parametrize('reference,status,outcome',[
    ('SYN-1001','POLICY_ASSESSMENT','MATCHED'),('missing','AWAITING_INFORMATION','NOT_FOUND'),
    ('SYN-CONFLICT','ESCALATED','CONFLICT'),('SYN-1003','AWAITING_INFORMATION','NOT_FOUND'),
    ('SYN-1004','AWAITING_INFORMATION','NOT_FOUND')])
def test_real_scoped_outcomes_and_original_receipt(flow_engine,identities,enabled,reference,status,outcome):
    original,request=admitted(flow_engine,identities,reference)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();assert claim
    observation=processor.lookup(claim);assert processor.finish(observation)
    case=original.body['case_id'];view=identities.flow().get_case(case).body
    assert view['status']==status and view['case_version']==3
    assert view['input_version']==(2 if outcome=='MATCHED' else 1)
    receipt=rows(flow_engine,t.receipts)[0];raw=decode_document(rows(flow_engine,t.receipt_contents)[0]['body'])
    assert receipt['status']==outcome and raw['request']['input_version']==raw['result']['input_version']==1
    assert raw['service_signature']==claim.service_signature and raw['grant_signature']==claim.grant_signature
    assert raw['catalogue']=={key:getattr(processor.catalogue.metadata,key) for key in ('format_version','provider_id','dataset_version','provider_version','dataset_sha256')}
    assert identities.flow().create(request,'create-key',identifier('corr')).body==original.body
    assert processor.finish(observation) and len(rows(flow_engine,t.receipts))==1
    assert identities.flow().get_case(case).body['input_version']==view['input_version']
    assert 'snapshot' not in view and 'order_lookup_block' not in view
    if outcome=='MATCHED':
        projection=rows(flow_engine,t.projections)[0]
        assert (projection['source_input_version'],projection['input_version'])==(1,2)
        assert decode_document(rows(flow_engine,t.projection_contents)[0]['body'])==raw['result']['snapshot']
        assert rows(flow_engine,old.intake_sessions)[0]['input_version']==1
    if outcome=='CONFLICT':
        assert rows(flow_engine,t.blocks)[0]['input_version']==1
        assert [r['kind'] for r in rows(flow_engine,old.history)]==['STATEMENT','ORDER_LOOKUP_BLOCK']
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert verify_chain(uow,case);uow.commit()

@pytest.mark.parametrize('grant',[False,None])
def test_explicit_denial_and_absent_grant_are_business_blocks(flow_engine,identities,grant):
    policy=InvestigationPolicy(flow_engine);policy.configure('synthetic_au_store')
    if grant is not None: policy.grant('synthetic_au_store','synthetic_commerce',can_read=False)
    original,_=admitted(flow_engine,identities)
    assert InvestigationProcessor(flow_engine).run_once()
    assert identities.flow().get_case(original.body['case_id']).body['status']=='ESCALATED'
    assert rows(flow_engine,t.receipts)[0]['status']=='AUTHORITY_DENIED'
    assert rows(flow_engine,t.work)[0]['failure_count']==0
    assert rows(flow_engine,old.processing_failures)==[]

class BrokenSource:
    metadata=load_builtin_catalogue().metadata
    def read_matches(self,*args): raise OrderSourceUnavailable()

def test_only_actual_provider_failure_spends_bounded_budget(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine,catalogue=BrokenSource(),retry_seconds=0)
    assert processor.run_once()
    view=identities.flow().get_case(original.body['case_id']).body
    assert (view['status'],view['case_version'],view['input_version'])==('UNDER_INVESTIGATION',2,1)
    assert rows(flow_engine,t.work)[0]['failure_count']==1
    assert processor.run_once();assert not processor.run_once()
    assert identities.flow().get_case(original.body['case_id']).body['status']=='ESCALATED'
    assert [r['status'] for r in rows(flow_engine,t.receipts)]==['PROVIDER_FAILURE','PROVIDER_FAILURE']
    failure=decode_document(rows(flow_engine,old.processing_failures)[0]['body'])
    assert failure['stage']=='ORDER_LOOKUP' and not failure['error']['error']['retryable']
    assert rows(flow_engine,t.work)[0]['failure_count']==2

def test_future_only_absence_and_disabled_binding(flow_engine,identities):
    original,_=admitted(flow_engine,identities)
    assert rows(flow_engine,t.work)==[]
    policy=InvestigationPolicy(flow_engine);policy.configure('synthetic_au_store',enabled=False)
    assert not InvestigationProcessor(flow_engine).run_once()
    assert rows(flow_engine,t.work)==[]
    second,_=admitted(flow_engine,identities,key='second-key')
    assert rows(flow_engine,t.work)[0]['state']=='PAUSED'
    assert rows(flow_engine,t.work)[0]['safe_reason']=='SERVICE_DISABLED'
    assert identities.flow().get_case(original.body['case_id']).body['status']=='UNDER_INVESTIGATION'
    assert policy.verify('synthetic_au_store')

@pytest.mark.parametrize('mode',['reference','description'])
def test_no_reference_first_question_and_either_answer(flow_engine,identities,enabled,mode):
    original,request=admitted(flow_engine,identities,None)
    processor=InvestigationProcessor(flow_engine);assert processor.run_once()
    case=original.body['case_id'];view=identities.flow().get_case(case).body
    assert len(view['clarification']['questions'])==2
    group=rows(flow_engine,t.groups)[0]
    answer={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
        'answers':[{'question_id':group['reference_question_id'] if mode=='reference' else group['context_question_id'],
            'text':'SYN-1001' if mode=='reference' else '  alternative purchase detail\x00\ud800  '}],'evidence_ids':[]}
    accepted=identities.flow().clarify(case,answer,'answer-key',identifier('corr'))
    assert (accepted.status,accepted.body['status'],accepted.body['input_version'])==(202,'UNDER_INVESTIGATION',2)
    assert IntakeProcessor(flow_engine).run_once()
    assert processor.run_once() is (mode=='reference')
    current=identities.flow().get_case(case).body
    assert current['status']==('POLICY_ASSESSMENT' if mode=='reference' else 'UNDER_INVESTIGATION')
    assert current['input_version']==(3 if mode=='reference' else 2)
    if mode=='description':
        assert rows(flow_engine,t.work)[-1]['safe_reason']=='ALTERNATIVE_PROOF_REQUIRES_VERIFICATION'
        assert len(rows(flow_engine,t.receipts))==1 and rows(flow_engine,t.projections)==[]
    assert identities.flow().clarify(case,answer,'answer-key',identifier('corr')).body==accepted.body
    assert identities.flow().create(request,'create-key',identifier('corr')).body==original.body

@pytest.mark.parametrize('reference,first',[(None,'Provide an order reference'),('syn-1001','We could not find an order with that reference')])
def test_question_says_when_a_given_reference_was_not_found(flow_engine,identities,enabled,reference,first):
    # 30 October 2026 review: matching stays exact (docs/22), but a reference that
    # matched nothing must not come back as the same unexplained question.
    original,_=admitted(flow_engine,identities,reference)
    assert InvestigationProcessor(flow_engine).run_once()
    view=identities.flow().get_case(original.body['case_id']).body
    assert view['status']=='AWAITING_INFORMATION'
    questions=view['clarification']['questions']
    assert len(questions)==2 and questions[0]['text'].startswith(first)
    assert questions[1]['text'].startswith('Alternatively, describe the purchase')

def test_oversize_reference_is_saved_without_truncation_or_lookup(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities,None);assert InvestigationProcessor(flow_engine).run_once()
    case=original.body['case_id'];view=identities.flow().get_case(case).body;group=rows(flow_engine,t.groups)[0]
    answer={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
        'answers':[{'question_id':group['reference_question_id'],'text':'X'*121}],'evidence_ids':[]}
    result=identities.flow().clarify(case,answer,'oversize-key',identifier('corr'))
    assert result.body['status']=='AWAITING_INFORMATION'
    assert result.body['statements'][-1]['raw_text']=='X'*121
    assert len(result.body['clarification']['questions'])==2
    assert IntakeProcessor(flow_engine).run_once()
    assert not InvestigationProcessor(flow_engine).run_once()
    assert len(rows(flow_engine,t.receipts))==1
