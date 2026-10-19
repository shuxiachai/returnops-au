"""Bounded production denial audit after the rejected UoW has fully closed."""
from datetime import datetime, timezone
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .audit import append_event, identifier
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown
from .lifecycle_sources import authority
from .lifecycle_state import reject
from .proposal_policy import ACTOR, COMPONENT

DENIAL_CODES = frozenset({'INVALID_STATE','STALE_CASE_VERSION','FORBIDDEN','NOT_FOUND','IDEMPOTENCY_CONFLICT'})


def record_denial(engine, key, code, *, uow_factory=CustomerUnitOfWork):
    if code not in DENIAL_CODES or key.get('component_id') != COMPONENT or key.get('purpose') != 'PROPOSAL':
        return 'NOT_RECORDED'
    status = 'NOT_RECORDED'
    try:
        with uow_factory(engine, write=True) as uow:
            def reauthorize():
                head = uow.execute(select(old.case_heads).where(
                    old.case_heads.c.case_id == key['case_id']).with_for_update()).mappings().one_or_none()
                if head is None or not head['available']:
                    reject(uow, 'NOT_FOUND')
                if head['store_id'] != key['store_id'] or head['owner_principal_id'] != key['owner_id']:
                    reject(uow, 'FORBIDDEN')
                state = uow.execute(select(t.state).where(t.state.c.case_id == head['case_id']).with_for_update()).mappings().one_or_none()
                if state is not None and not state['available']:
                    reject(uow, 'NOT_FOUND')
                return authority(uow, head, COMPONENT, 'PROPOSAL')['revision']
            revision = reauthorize()
            def check():
                if reauthorize() != revision:
                    reject(uow, 'FORBIDDEN')
            uow.before_commit(check)
            append_event(uow, key['case_id'], actor=ACTOR, event_type='LIFECYCLE_GUARD_DENIED',
                correlation_id=identifier('denial_corr'), payload={'purpose':'PROPOSAL','reason':code},
                object_ids=[], history_refs=[], now=datetime.now(timezone.utc))
            uow.commit()
            status = 'RECORDED'
    except AcceptanceOutcomeUnknown:
        status = 'UNKNOWN'
    except Exception:
        status = 'UNKNOWN' if status == 'RECORDED' else 'NOT_RECORDED'
    return status
