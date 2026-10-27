"""Atomic bridges from accepted intake and explicit investigation questions."""
from sqlalchemy import select, update
from . import customer_tables as old, investigation_tables as t
from .audit import identifier
from .canonical import decode_document, encode_document
from .investigation_policy import SERVICE_ID, service
from .storage import original_statement_contents, original_statement_records


def configured(uow, store):
    return service(uow,store) is not None


def ensure_work(uow, intake, head, now):
    """Use the caller's successful intake transaction; future-only, no backfill."""
    policy=service(uow,head['store_id'])
    if policy is None: return None
    previous=uow.execute(select(t.work).where(t.work.c.case_id==head['case_id'],t.work.c.input_version==head['input_version'])).mappings().one_or_none()
    if previous is not None: return previous['work_id']
    projection=uow.execute(select(t.clarification_inputs).where(t.clarification_inputs.c.case_id==head['case_id'],
        t.clarification_inputs.c.input_version==head['input_version'])).mappings().one_or_none()
    if projection is None:
        reference=uow.execute(select(original_statement_contents.c.original_order_reference).join(original_statement_records,
            original_statement_contents.c.statement_id==original_statement_records.c.statement_id)
            .where(original_statement_records.c.case_id==head['case_id'])).scalar_one_or_none()
        alternative=reference is None and uow.execute(select(old.evidence.c.evidence_id).where(old.evidence.c.case_id==head['case_id'],
            old.evidence.c.available.is_(True),old.evidence.c.status=='BOUND').limit(1)).first() is not None
        available=True
    else:
        reference,alternative,available=projection['reference'],projection['alternative'],projection['available']
    work_id=identifier('investigation')
    reason=('CONTENT_UNAVAILABLE' if not available else 'ALTERNATIVE_PROOF_REQUIRES_VERIFICATION' if alternative
        else 'SERVICE_DISABLED' if not policy['enabled'] else None)
    uow.execute(t.work.insert().values(work_id=work_id,case_id=head['case_id'],intake_work_id=intake['work_id'],
        acceptance_id=intake['acceptance_id'],input_version=head['input_version'],phase='ORDER_LOOKUP',
        state='PAUSED' if reason else 'PENDING',owner_id=head['owner_principal_id'],store_id=head['store_id'],service_id=SERVICE_ID,
        epoch=0,failure_count=0,safe_reason=reason,created_at=now,next_attempt_at=now))
    uow.execute(t.inputs.insert().values(work_id=work_id,reference=reference,available=available,alternative=alternative))
    current=uow.execute(select(t.state).where(t.state.c.case_id==head['case_id'])).mappings().one_or_none()
    values=dict(current_work_id=work_id,current_projection_id=None,current_block_id=None)
    if current is None: uow.execute(t.state.insert().values(case_id=head['case_id'],**values))
    else: uow.execute(update(t.state).where(t.state.c.case_id==head['case_id']).values(**values))
    return work_id


def answer_group(uow, current, questions, answers, eligible):
    """None retains legacy AND semantics; only persisted group IDs imply OR."""
    group=uow.execute(select(t.groups).where(t.groups.c.question_set_id==current['question_set_id'],
        t.groups.c.case_id==current['case_id'],t.groups.c.input_version==current['input_version'])).mappings().one_or_none()
    if group is None: return None
    by_id={a['question_id']:a['text'] for a in answers}
    reference=by_id.get(group['reference_question_id'])
    valid_reference=reference is not None and bool(reference.strip()) and len(reference)<=120
    context=by_id.get(group['context_question_id'])
    alternative=bool(eligible) or (context is not None and bool(context.strip()))
    remaining=[] if valid_reference or alternative else [dict(q) for q in questions]
    if reference is not None and not valid_reference:
        for q in remaining:
            if q['question_id']==group['reference_question_id']:
                q['text']='Provide an order reference of at most 120 characters, or answer the alternative purchase-context question.'
    return dict(group=dict(group),remaining=remaining,reference=reference.encode('utf-8','surrogatepass') if valid_reference else None,
        alternative=alternative and not valid_reference)


def record_answers(uow, case_id, input_version, question_set_id, decision, now):
    # Invalidates older claims even before a new intake can complete.
    uow.execute(update(t.work).where(t.work.c.case_id==case_id,t.work.c.state.in_(['PENDING','RUNNING','PAUSED']))
        .values(state='SUPERSEDED',completed_at=now,safe_reason='STALE_INPUT'))
    if decision is None: return
    uow.execute(t.clarification_inputs.insert().values(case_id=case_id,input_version=input_version,
        reference=decision['reference'],alternative=decision['alternative'],available=True))
    if question_set_id is not None:
        group=decision['group']
        uow.execute(t.groups.insert().values(question_set_id=question_set_id,case_id=case_id,input_version=input_version,
            reference_question_id=group['reference_question_id'],context_question_id=group['context_question_id']))


def issue_questions(uow, head, now):
    reference_id,context_id=identifier('question'),identifier('question')
    questions=[{'question_id':reference_id,'text':'Provide an order reference (at most 120 characters), or use the alternative purchase-context question.',
        'reason':'No order is verified. Either an order reference or alternative purchase material can continue the investigation.'},
        {'question_id':context_id,'text':'Alternatively, describe the purchase or attach supporting evidence; you do not also need an order reference.',
        'reason':'Alternative material will be retained for further verification; it does not itself verify an order.'}]
    question_set_id=identifier('questions')
    uow.execute(old.questions.insert().values(question_set_id=question_set_id,case_id=head['case_id'],input_version=head['input_version'],
        questions=encode_document(questions),question_kinds=encode_document({reference_id:'ORDER_REFERENCE',context_id:'PURCHASE_CONTEXT'})))
    uow.execute(t.groups.insert().values(question_set_id=question_set_id,case_id=head['case_id'],input_version=head['input_version'],
        reference_question_id=reference_id,context_question_id=context_id))
    return question_set_id
