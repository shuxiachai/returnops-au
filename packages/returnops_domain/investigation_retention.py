"""Erase every derived personal copy on source removal, under the same fence."""
from sqlalchemy import select, update, delete
from . import investigation_tables as t

def remove_case_payloads(uow,case_id):
    receipt_ids=select(t.receipts.c.receipt_id).where(t.receipts.c.case_id==case_id)
    projection_ids=select(t.projections.c.projection_id).where(t.projections.c.case_id==case_id)
    work_ids=select(t.work.c.work_id).where(t.work.c.case_id==case_id)
    uow.execute(delete(t.receipt_contents).where(t.receipt_contents.c.receipt_id.in_(receipt_ids)))
    uow.execute(update(t.receipts).where(t.receipts.c.case_id==case_id).values(available=False))
    uow.execute(delete(t.projection_contents).where(t.projection_contents.c.projection_id.in_(projection_ids)))
    uow.execute(update(t.projections).where(t.projections.c.case_id==case_id).values(available=False))
    uow.execute(update(t.inputs).where(t.inputs.c.work_id.in_(work_ids)).values(reference=None,available=False))
    uow.execute(update(t.clarification_inputs).where(t.clarification_inputs.c.case_id==case_id).values(reference=None,available=False))
    uow.execute(update(t.work).where(t.work.c.case_id==case_id,t.work.c.state.in_(['PENDING','RUNNING','PAUSED']))
        .values(state='PAUSED',safe_reason='CONTENT_UNAVAILABLE'))
    uow.execute(update(t.state).where(t.state.c.case_id==case_id).values(current_projection_id=None))
