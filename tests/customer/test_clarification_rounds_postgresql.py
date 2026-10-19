"""A real sequence beyond three clarification rounds, using internal questions."""
from sqlalchemy import select,update
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier
from returnops_domain.canonical import encode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.intake_processor import IntakeProcessor

def test_six_information_rounds_are_allowed_and_original_is_not_overwritten(flow_engine,identities):
    flow=identities.flow();original='  original remains exact\x00\ud800  '
    accepted=flow.create({'original_message':original},'rounds-create-key',identifier('corr')).body
    case=accepted['case_id'];worker=IntakeProcessor(flow_engine);assert worker.run_once()
    current=flow.get_case(case).body
    questions=[{'question_id':identifier('question'),'text':'Provide structural context '+str(i),'reason':'A distinct collection question.'} for i in range(6)]
    # A legitimate internal service-issued fixture exercises the generic partial
    # policy. It creates no new public endpoint, model result or verified fact.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(t.questions).where(t.questions.c.question_set_id==current['clarification']['question_set_id']).values(
            questions=encode_document(questions),question_kinds=encode_document({q['question_id']:'TEXT_RESPONSE' for q in questions})));uow.commit()
    for index,question in enumerate(questions):
        current=flow.get_case(case).body
        request={'expected_case_version':current['case_version'],'question_set_id':current['clarification']['question_set_id'],
                 'answers':[{'question_id':question['question_id'],'text':'  supplied context '+str(index)+'  '}],'evidence_ids':[]}
        response=flow.clarify(case,request,'round-answer-'+str(index),identifier('corr'))
        assert response.status==202 and response.body['input_version']==index+2
        if index<5:
            assert response.body['status']=='AWAITING_INFORMATION'
            assert response.body['clarification']['questions']==questions[index+1:]
        else: assert response.body['status']=='UNDER_INVESTIGATION' and 'clarification' not in response.body
        assert worker.run_once()
    final=flow.get_case(case).body
    assert final['statements'][0]['raw_text']==original and len(final['statements'])==7
    assert (final['case_version'],final['input_version'],final['status'])==(14,7,'UNDER_INVESTIGATION')
    with flow_engine.connect() as c:
        assert c.execute(select(t.intake_sessions.c.clarification_round)).scalar_one()==6
        assert len(c.execute(select(t.intake_work)).all())==7
