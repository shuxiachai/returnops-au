"""Fresh REVIEW authority only after the rejected acceptance UoW is closed."""
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .audit import append_event, identifier
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown
from .lifecycle_sources import authority
from .lifecycle_state import reject
from .lifecycle_schema import version, CURRENT
from .pass_review_sources import COMPONENT

DENIAL_CODES=frozenset({'INVALID_STATE','STALE_CASE_VERSION','FORBIDDEN','NOT_FOUND',
                       'IDEMPOTENCY_CONFLICT','VALIDATION_ERROR','INTERNAL_ERROR'})


def authorize(uow,case_id):
    if version(uow.connection)!=CURRENT:
        reject(uow)
    head=uow.execute(select(old.case_heads).where(old.case_heads.c.case_id==case_id).with_for_update()).mappings().one_or_none()
    if head is None or not head['available']:
        reject(uow,'NOT_FOUND')
    grant=authority(uow,head,COMPONENT,'REVIEW')
    state=uow.execute(select(t.state).where(t.state.c.case_id==case_id)).mappings().one_or_none()
    if state is not None and not state['available']:
        reject(uow)
    return head,grant


def record_denial(engine,case_id,code,clock,*,uow_factory=CustomerUnitOfWork):
    if code not in DENIAL_CODES:
        return 'NOT_RECORDED'
    committed=False
    try:
        with uow_factory(engine,write=True) as uow:
            head,grant=authorize(uow,case_id)
            def check():
                h,g=authorize(uow,case_id)
                if h['owner_principal_id']!=head['owner_principal_id'] or h['store_id']!=head['store_id'] or g!=grant:
                    reject(uow)
            uow.before_commit(check)
            append_event(uow,case_id,actor={'kind':'SERVICE','component_id':COMPONENT},
                event_type='LIFECYCLE_GUARD_DENIED',correlation_id=identifier('pass_review_denial'),
                payload={'purpose':'REVIEW','reason':code},object_ids=[],history_refs=[],now=clock())
            uow.commit();committed=True
        return 'RECORDED'
    except AcceptanceOutcomeUnknown:
        return 'UNKNOWN'
    except Exception:
        return 'UNKNOWN' if committed else 'NOT_RECORDED'
