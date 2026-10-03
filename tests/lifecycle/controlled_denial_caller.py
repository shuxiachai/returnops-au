"""PRIVATE TEST COMPOSITION ONLY: independently authorize a denial audit.

No runtime route/worker imports this caller. Its context and callables belong to
server-side test composition, never to a rejected DTO. There is deliberately no
actor, audit-payload, arbitrary-event, retry, or new-grant parameter.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from returnops_domain import customer_tables as old, lifecycle_tables as lifecycle
from returnops_domain.audit import append_event, identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.lifecycle_guards import PURPOSES
from returnops_domain.lifecycle_sources import authority
from returnops_domain.lifecycle_state import reject
from returnops_domain.wire import validate
from synthetic_sources import COMPONENT

DENIAL_EVENT = 'LIFECYCLE_GUARD_DENIED'
DENIAL_CODES = frozenset({'INVALID_STATE', 'STALE_CASE_VERSION', 'FORBIDDEN', 'NOT_FOUND'})


@dataclass(frozen=True)
class TrustedContext:
    case_id: str
    owner_id: str
    store_id: str
    purpose: str
    component_id: str = COMPONENT


@dataclass(frozen=True)
class Result:
    operation: str
    safe_code: str | None
    audit: str


class ControlledCaller:
    """A bounded proof harness, not a reusable production denial service."""

    def __init__(self, engine, context, *, operation_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork):
        self.engine = engine
        self.context = context
        self.operation_uow = operation_uow
        self.audit_uow = audit_uow

    def _valid_context(self):
        context = self.context
        if (type(context) is not TrustedContext or context.component_id != COMPONENT
                or type(context.purpose) is not str or context.purpose not in PURPOSES.values()):
            return False
        try:
            for value in (context.case_id, context.owner_id, context.store_id):
                validate('Id', value)
        except FlowError:
            return False
        return True

    def _current_authority(self, uow):
        context = self.context
        head = uow.execute(select(old.case_heads).where(
            old.case_heads.c.case_id == context.case_id).with_for_update()).mappings().one_or_none()
        if head is None or not head['available']:
            reject(uow, 'NOT_FOUND')
        if (head['owner_principal_id'], head['store_id']) != (context.owner_id, context.store_id):
            reject(uow, 'FORBIDDEN')
        # Reading this optional row must never initialize a business sidecar.
        state = uow.execute(select(lifecycle.state).where(
            lifecycle.state.c.case_id == context.case_id).with_for_update()).mappings().one_or_none()
        if state is not None and not state['available']:
            reject(uow, 'NOT_FOUND')
        return authority(uow, head, context.component_id, context.purpose)

    def _audit(self, safe_code):
        status = 'NOT_RECORDED'
        try:
            with self.audit_uow(self.engine, write=True) as uow:
                grant = self._current_authority(uow)
                revision = grant['revision']

                def reauthorize():
                    if self._current_authority(uow)['revision'] != revision:
                        reject(uow, 'FORBIDDEN')

                uow.before_commit(reauthorize)
                append_event(uow, self.context.case_id,
                    actor={'kind': 'SERVICE', 'component_id': self.context.component_id},
                    event_type=DENIAL_EVENT, correlation_id=identifier('denial_corr'),
                    payload={'purpose': self.context.purpose, 'reason': safe_code},
                    object_ids=[], history_refs=[], now=datetime.now(timezone.utc))
                uow.commit()
                status = 'RECORDED'
        except AcceptanceOutcomeUnknown:
            status = 'UNKNOWN'
        except Exception:
            # A failure after an acknowledged commit cannot honestly mean rollback.
            status = 'UNKNOWN' if status == 'RECORDED' else 'NOT_RECORDED'
        return status

    def run(self, operation):
        if not self._valid_context():
            return Result('DENIED', 'VALIDATION_ERROR', 'NOT_RECORDED')
        safe_code = None
        uow = None
        committed = False
        try:
            with self.operation_uow(self.engine, write=True) as uow:
                operation(uow)
                uow.commit()
                committed = True
        except AcceptanceOutcomeUnknown:
            return Result('UNKNOWN', None, 'NOT_ATTEMPTED')
        except FlowError as error:
            safe_code = error.code if error.code in DENIAL_CODES else None
        except Exception:
            return Result('FAILED', 'INTERNAL_ERROR', 'NOT_ATTEMPTED')
        else:
            return Result('ACCEPTED', None, 'NOT_ATTEMPTED')
        if committed:
            return Result('UNKNOWN', None, 'NOT_ATTEMPTED')
        # Only a definite guard rejection after complete UoW exit qualifies.
        if (safe_code is None or uow is None or uow.connection is None
                or not uow.finished or not uow.connection.closed):
            return Result('FAILED', 'INTERNAL_ERROR', 'NOT_ATTEMPTED')
        return Result('DENIED', safe_code, self._audit(safe_code))
