"""Fresh HUMAN/F.03 and separate APPROVAL authority, including denial audit."""
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .audit import append_event, identifier
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown
from .lifecycle_schema import CURRENT, version
from .lifecycle_sources import authority
from .lifecycle_state import reject
from .preview_profile import APPROVAL_COMPONENT as COMPONENT
from .reject_denial import OPERATION, DENIAL_CODES


def authorize(uow, callback, case_id):
    actor = callback(uow.connection, 'getSession')
    if actor.role != 'FOUNDER':
        reject(uow, 'FORBIDDEN')
    current = callback(uow.connection, OPERATION, case_id)
    if current != actor:
        reject(uow, 'UNAUTHENTICATED')
    if version(uow.connection) != CURRENT:
        reject(uow)
    head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case_id)
        .with_for_update()).mappings().one_or_none()
    if head is None or not head['available']:
        reject(uow, 'NOT_FOUND')
    if head['store_id'] != actor.store_id:
        reject(uow, 'FORBIDDEN')
    return actor, head, authority(uow, head, COMPONENT, 'APPROVAL')


def record_denial(engine, callback, case_id, code, clock, *, uow_factory=CustomerUnitOfWork):
    if code not in DENIAL_CODES:
        return 'NOT_RECORDED'
    committed = False
    try:
        with uow_factory(engine, write=True) as uow:
            actor, head, grant = authorize(uow, callback, case_id)
            def check():
                a, h, g = authorize(uow, callback, case_id)
                state = uow.execute(select(t.state).where(t.state.c.case_id == case_id)).mappings().one_or_none()
                if (a != actor or h['owner_principal_id'] != head['owner_principal_id']
                        or h['store_id'] != head['store_id'] or dict(g) != dict(grant)
                        or state is not None and not state['available']):
                    reject(uow)
            check()
            uow.before_commit(check)
            append_event(uow, case_id, actor={'kind':'HUMAN','role':'FOUNDER','principal_id':actor.principal_id},
                event_type='FOUNDER_APPROVE_DENIED', correlation_id=identifier('denial_corr'),
                payload={'purpose':'APPROVAL','reason':code}, object_ids=[], history_refs=[], now=clock())
            uow.commit(); committed = True
        return 'RECORDED'
    except AcceptanceOutcomeUnknown:
        return 'UNKNOWN'
    except Exception:
        return 'UNKNOWN' if committed else 'NOT_RECORDED'
