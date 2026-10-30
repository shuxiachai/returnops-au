from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import pytest
from sqlalchemy import create_engine,select,text,update
from alembic import command
from alembic.config import Config
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.customer_service import CustomerFlow
from returnops_domain import customer_tables as old, investigation_tables as t
from returnops_domain.audit import identifier
from returnops_domain.canonical import encode_document,decode_document
from returnops_domain.case_state import transition
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor,LookupObservation
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from test_outcomes_postgresql import admitted,rows,BrokenSource
from test_recovery_postgresql import OneUnknownCommit


def test_upgrade_from_0004_preserves_real_acceptance_and_is_repeatable(flow_engine,identities):
    schema='investigation_upgrade_'+uuid4().hex
    with flow_engine.begin() as connection: connection.execute(text('CREATE SCHEMA '+schema))
    engine=create_engine(flow_engine.url,hide_parameters=True,echo=False,
        connect_args={'options':'-c search_path='+schema+' -c statement_timeout=10000'})
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    try:
        with engine.begin() as connection:
            config.attributes['connection']=connection;command.upgrade(config,'0004_pre_case_audit')
        TrustedRegistry(engine).provision(list(identities.people.values()),list(identities.sessions.values()))
        flow=CustomerFlow(engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['customer_a']))
        original=flow.create({'original_message':'legacy accepted\x00\ud800','order_reference':'SYN-1001'},'legacy-key',identifier('corr'))
        # Explicit legacy-completed fixture, with genuine acceptance/receipt and
        # source rows. No new migration or startup is permitted to backfill it.
        with CustomerUnitOfWork(engine,write=True) as uow:
            uow.execute(update(old.case_heads).values(status='UNDER_INVESTIGATION',case_version=2))
            uow.execute(update(old.intake_work).values(state='DONE',completed_at=datetime.now(timezone.utc)))
            uow.execute(update(old.intake_sessions).values(status='COMPLETE'))
            uow.commit()
        def snapshot():
            with engine.connect() as connection:
                return {table.name:sorted([tuple(row) for row in connection.execute(select(table))],key=repr)
                    for table in old.CUSTOMER_TABLES}
        before=snapshot()
        with engine.begin() as connection:
            config.attributes['connection']=connection;command.upgrade(config,'head');command.upgrade(config,'head')
        assert snapshot()==before
        assert rows(engine,t.services)==rows(engine,t.grants)==rows(engine,t.work)==[]
        assert not InvestigationProcessor(engine).run_once()
        assert flow.create({'original_message':'legacy accepted\x00\ud800','order_reference':'SYN-1001'},'legacy-key',identifier('corr')).body==original.body
        assert rows(engine,t.work)==[]
    finally:
        engine.dispose()
        with flow_engine.begin() as connection: connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))


def test_legacy_and_questions_remain_and_under_enabled_service(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities,None);case=original.body['case_id']
    q1,q2=identifier('question'),identifier('question');qs=identifier('questions')
    questions=[{'question_id':value,'text':'Please answer this separate question.','reason':'Independent required context.'} for value in [q1,q2]]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(old.questions.insert().values(question_set_id=qs,case_id=case,input_version=1,questions=encode_document(questions),
            question_kinds=encode_document({q1:'TEXT_RESPONSE',q2:'TEXT_RESPONSE'})))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status='AWAITING_INFORMATION',current_question_set_id=qs))
        uow.commit()
    view=identities.flow().get_case(case).body
    accepted=identities.flow().clarify(case,{'expected_case_version':view['case_version'],'question_set_id':qs,
        'answers':[{'question_id':q1,'text':'one answer'}],'evidence_ids':[]},'partial-key',identifier('corr'))
    assert accepted.body['status']=='AWAITING_INFORMATION'
    assert [q['question_id'] for q in accepted.body['clarification']['questions']]==[q2]
    assert IntakeProcessor(flow_engine).run_once()
    assert identities.flow().get_case(case).body['status']=='AWAITING_INFORMATION'
    assert rows(flow_engine,t.groups)==[]


def test_invalid_transition_poison_rolls_back_prior_work_even_if_caught(flow_engine,identities,enabled):
    admitted(flow_engine,identities)
    head=rows(flow_engine,old.case_heads)[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(t.work).values(failure_count=4))
        with pytest.raises(FlowError): transition(uow,head,'APPROVAL_ACCEPTED','APPROVED',datetime.now(timezone.utc))
        with pytest.raises(FlowError): uow.commit()
    assert rows(flow_engine,t.work)[0]['failure_count']==0
    assert rows(flow_engine,old.case_heads)[0]['status']=='UNDER_INVESTIGATION'


def test_wrong_state_customer_clarification_is_denied_and_audited(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities);assert InvestigationProcessor(flow_engine).run_once()
    case=original.body['case_id'];head=rows(flow_engine,old.case_heads)[0]
    before={name:len(rows(flow_engine,table)) for name,table in [('acceptances',old.acceptances),('intake',old.intake_work),('investigation',t.work)]}
    with pytest.raises(FlowError) as error:
        identities.flow().clarify(case,{'expected_case_version':head['case_version'],'question_set_id':'unknown_question_set',
            'answers':[{'question_id':'unknown_question','text':'some text'}],'evidence_ids':[]},'wrong-state',identifier('corr'))
    assert error.value.code=='INVALID_STATE'
    assert before=={name:len(rows(flow_engine,table)) for name,table in [('acceptances',old.acceptances),('intake',old.intake_work),('investigation',t.work)]}
    assert decode_document(rows(flow_engine,old.audit)[-1]['body'])['event_type']=='CUSTOMER_TRANSITION_DENIED'

@pytest.mark.parametrize('kind',['not_found','conflict','denied','failure'])
def test_retention_preserves_terminal_status_safe_target_and_work(flow_engine,identities,enabled,kind):
    if kind=='denied': enabled.grant('synthetic_au_store','synthetic_commerce',can_read=False)
    reference={'not_found':'missing','conflict':'SYN-CONFLICT'}.get(kind,'SYN-1001')
    original,_=admitted(flow_engine,identities,reference)
    processor=InvestigationProcessor(flow_engine,catalogue=BrokenSource() if kind=='failure' else None,retry_seconds=0)
    assert processor.run_once()
    if kind=='failure': assert processor.run_once()
    head=rows(flow_engine,old.case_heads)[0];work=rows(flow_engine,t.work)[0];state=rows(flow_engine,t.state)[0]
    statement=original.body['statements'][0]['statement_id']
    assert RetentionService(flow_engine).remove('STATEMENT',statement)
    current=rows(flow_engine,old.case_heads)[0];current_state=rows(flow_engine,t.state)[0]
    assert current['status']==head['status'] and current['input_version']==head['input_version']
    assert current['case_version']==head['case_version']+1 and current['current_question_set_id'] is None
    assert current['current_failure_id']==head['current_failure_id']
    assert current_state['current_block_id']==state['current_block_id']
    assert rows(flow_engine,t.work)[0]['state']==work['state']
    assert rows(flow_engine,t.receipt_contents)==[]
    if current['status']=='ESCALATED': assert sum(v is not None for v in [current['current_failure_id'],current_state['current_block_id']])==1
    assert not RetentionService(flow_engine).remove('STATEMENT',statement)
    assert rows(flow_engine,old.case_heads)[0]['case_version']==current['case_version']
    assert not processor.run_once()
    # Frozen customer view permits unavailable clarification material while
    # status is historical; never fabricate questions or reopen business state.
    assert identities.flow().get_case(original.body['case_id']).body['status']==head['status']


def test_disabled_service_requires_explicit_resume(flow_engine,identities):
    from returnops_domain.investigation_policy import InvestigationPolicy
    policy=InvestigationPolicy(flow_engine);policy.configure('synthetic_au_store',enabled=False)
    policy.grant('synthetic_au_store','synthetic_commerce',can_read=True)
    admitted(flow_engine,identities)
    work=rows(flow_engine,t.work)[0]
    policy.configure('synthetic_au_store',enabled=True)
    processor=InvestigationProcessor(flow_engine);assert not processor.run_once()
    policy.resume(work['work_id'],expected_input_version=1)
    assert processor.run_once() and not processor.run_once()
    assert len(rows(flow_engine,t.receipts))==1


def test_worker_retries_original_observation_after_unknown_result_commit(flow_engine,identities,enabled):
    admitted(flow_engine,identities)
    from returnops_domain.mock_orders import load_builtin_catalogue
    builtin=load_builtin_catalogue();calls=[]
    class CountingSource:
        metadata=builtin.metadata
        def read_matches(self,*args): calls.append(1);return builtin.read_matches(*args)
    processor=InvestigationProcessor(flow_engine,catalogue=CountingSource());claim=processor.claim()
    observation=processor.lookup(claim)
    processor.uow_factory=OneUnknownCommit(committed=False)
    assert not processor.finish(observation)
    assert processor.run_once() and calls==[1]
    assert rows(flow_engine,t.receipts)[0]['receipt_id']==claim.invocation_id


def test_same_snapshot_identity_with_conflicting_content_rejects_atomically(flow_engine,identities,enabled):
    # A prior trusted snapshot observation is an integrity constraint. No
    # public endpoint is added to inject/replace order facts for this test.
    original,_=admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    assert processor.finish(observation)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        # Rollback-only harness simulates an inconsistent prior projection and
        # the same still-current source result; no test mutation persists.
        head=uow.execute(select(old.case_heads)).mappings().one()
        uow.execute(update(old.case_heads).values(status='UNDER_INVESTIGATION',input_version=1,case_version=claim.case_version))
        uow.execute(update(t.projections).values(snapshot_hash='0'*64))
        replay_head={**head,'status':'UNDER_INVESTIGATION','input_version':1,'case_version':claim.case_version}
        work=uow.execute(select(t.work)).mappings().one()
        with pytest.raises(FlowError): processor._accept(uow,work,replay_head,decode_document(observation.body)['result'],datetime.now(timezone.utc))
    assert rows(flow_engine,t.projections)[0]['snapshot_hash']!='0'*64
    assert rows(flow_engine,old.case_heads)[0]['status']=='POLICY_ASSESSMENT'

def test_photo_lodged_without_reference_is_asked_for_the_order(flow_engine,identities,enabled):
    # 30 October 2026 review: a damage photo lodged without an order reference used
    # to count as alternative purchase proof and pause the case with no way forward.
    import io
    from PIL import Image
    from returnops_domain.evidence_validation import validate_evidence
    image=io.BytesIO();Image.new('RGB',(2,2),(200,10,10)).save(image,format='PNG')
    staged=identities.flow().stage(validate_evidence(image.getvalue(),'chipped-cup.png','image/png'),'photo-key',identifier('corr'))
    created=identities.flow().create({'original_message':'Two of the cups arrived chipped.','evidence_ids':[staged.body['evidence_id']]},
        'photo-create-key',identifier('corr'))
    assert created.status==201 and IntakeProcessor(flow_engine).run_once()
    processor=InvestigationProcessor(flow_engine);assert processor.run_once()
    case=created.body['case_id'];view=identities.flow().get_case(case).body
    assert view['status']=='AWAITING_INFORMATION' and len(view['clarification']['questions'])==2
    assert rows(flow_engine,t.work)[0]['safe_reason'] is None and rows(flow_engine,t.work)[0]['state']=='DONE'
    group=rows(flow_engine,t.groups)[0]
    answer={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
        'answers':[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],'evidence_ids':[]}
    assert identities.flow().clarify(case,answer,'photo-answer-key',identifier('corr')).status==202
    assert IntakeProcessor(flow_engine).run_once() and processor.run_once()
    assert identities.flow().get_case(case).body['status']=='POLICY_ASSESSMENT'

def test_authorized_bound_file_satisfies_or_without_fake_order(flow_engine,identities,enabled):
    import io
    from PIL import Image
    from returnops_domain.evidence_validation import validate_evidence
    original,_=admitted(flow_engine,identities,None);assert InvestigationProcessor(flow_engine).run_once()
    case=original.body['case_id'];view=identities.flow().get_case(case).body
    image=io.BytesIO();Image.new('RGB',(2,2),(255,255,255)).save(image,format='PNG')
    staged=identities.flow().stage(validate_evidence(image.getvalue(),'purchase.png','image/png'),'file-key',identifier('corr'))
    accepted=identities.flow().clarify(case,{'expected_case_version':view['case_version'],
        'question_set_id':view['clarification']['question_set_id'],'answers':[],
        'evidence_ids':[staged.body['evidence_id']]},'file-answer-key',identifier('corr'))
    assert accepted.body['status']=='UNDER_INVESTIGATION' and accepted.body['input_version']==2
    assert IntakeProcessor(flow_engine).run_once() and not InvestigationProcessor(flow_engine).run_once()
    assert rows(flow_engine,t.work)[-1]['safe_reason']=='ALTERNATIVE_PROOF_REQUIRES_VERIFICATION'
    assert rows(flow_engine,t.projections)==[]
    assert RetentionService(flow_engine).remove('EVIDENCE',staged.body['evidence_id'])
    assert not rows(flow_engine,t.clarification_inputs)[0]['available']
    assert rows(flow_engine,t.work)[-1]['safe_reason']=='CONTENT_UNAVAILABLE'


def test_stale_input_fence_drops_late_result(flow_engine,identities,enabled):
    admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    # Isolated metadata mutation fixture: emulate a separately authorized input
    # generation advancing. This is not a new customer operation or transfer.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(old.case_heads).values(input_version=2,case_version=3));uow.commit()
    assert not processor.finish(observation)
    assert rows(flow_engine,t.work)[0]['state']=='SUPERSEDED'
    assert rows(flow_engine,t.receipts)==rows(flow_engine,t.projections)==[]
    assert rows(flow_engine,t.work)[0]['failure_count']==0


def test_policy_audit_binds_indexed_identity_and_scope(flow_engine,identities,enabled):
    assert enabled.verify('synthetic_au_store')
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        row=uow.execute(select(t.policy_events).order_by(t.policy_events.c.sequence).limit(1)).mappings().one()
        uow.execute(update(t.policy_events).where(t.policy_events.c.event_id==row['event_id']).values(event_id=identifier('tampered')))
        uow.commit()
    assert not enabled.verify('synthetic_au_store')
