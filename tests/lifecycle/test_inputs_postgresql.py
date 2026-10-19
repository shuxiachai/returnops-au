"""Actual intake/order callers invalidate explicitly seeded obsolete future refs."""
from sqlalchemy import select, update
from returnops_domain import customer_tables as old, lifecycle_tables as t, investigation_tables as investigation
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.lifecycle_state import current
from synthetic_sources import head, now, rows, ready


def obsolete(uow, case_id):
    h=head(uow,case_id);state=current(uow,h,initialize=True)
    # Synthetic initial metadata for future producers that are not registered.
    # No approved operation or effect is created by this fixture.
    uow.execute(update(t.state).where(t.state.c.case_id==case_id).values(
        proposal_record_id='synthetic_old_proposal',review_record_id='synthetic_old_review',
        preview_id='synthetic_old_preview',approval_record_id='synthetic_old_approval'))
    work=identifier('obsolete_work')
    uow.execute(t.work.insert().values(work_id=work,case_id=case_id,component_id='synthetic_old_component',
        store_id=h['store_id'],owner_id=h['owner_principal_id'],purpose='PROPOSAL',input_version=h['input_version'],
        generation=state['generation'],target_hash='a'*64,target_record_id=None,state='PENDING',claim_id=None,epoch=0,
        claimed_case_version=None,authority_revision=1,lease_expires_at=None,created_at=now()))
    return state,work


def assert_invalidated(engine, before, work):
    state=rows(engine,t.state)[0]
    assert state['input_version']==before['input_version']+1 and state['generation']==before['generation']+1
    assert all(state[name] is None for name in ('proposal_record_id','review_record_id','preview_id','approval_record_id'))
    assert next(row for row in rows(engine,t.work) if row['work_id']==work)['state']=='SUPERSEDED'


def test_actual_order_acceptance_invalidates_old_current_refs_and_keeps_source_receipt(flow_engine,identities,enabled):
    original=identities.flow().create({'original_message':'synthetic fact','order_reference':'SYN-1001'},'input-key',identifier('corr'))
    case=original.body['case_id'];assert IntakeProcessor(flow_engine).run_once()
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        before,work=obsolete(uow,case);uow.commit()
    processor=InvestigationProcessor(flow_engine);token=processor.claim();observation=processor.lookup(token)
    assert processor.finish(observation);assert_invalidated(flow_engine,before,work)
    receipt=rows(flow_engine,investigation.receipts)[0]
    assert receipt['input_version']==1 and receipt['body_hash']==observation.body_hash
    assert rows(flow_engine,investigation.projections)[0]['input_version']==2
    assert rows(flow_engine,investigation.work)[0]['state']=='DONE'
    state=rows(flow_engine,t.state)[0];assert processor.finish(observation)
    assert rows(flow_engine,t.state)[0]==state


def test_actual_clarification_invalidates_refs_atomically_and_keeps_old_receipt(flow_engine,identities,enabled):
    original=ready(flow_engine,identities,reference=None);case=original['case_id']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        before,work=obsolete(uow,case);uow.commit()
    receipt=rows(flow_engine,investigation.receipts)[0]
    view=identities.flow().get_case(case).body
    group=rows(flow_engine,investigation.groups)[0]
    request={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
        'answers':[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],'evidence_ids':[]}
    result=identities.flow().clarify(case,request,'clarification-key',identifier('corr'))
    assert result.status==202;assert_invalidated(flow_engine,before,work)
    assert rows(flow_engine,investigation.receipts)[0]==receipt
