"""Bounded lifecycle mutation gate. Callers hold the exclusive Domain fence.

No approval/revision/notification event is implemented by this slice. Rejected
HTTP attempts use record_denial before committing only their audit observation.
"""
from sqlalchemy import update
from . import customer_tables as t
from .audit import append_event
from .errors import FlowError

_TARGETS = {
    'INTAKE_COMPLETE': ({'SUBMITTED','UNDER_INVESTIGATION','AWAITING_INFORMATION'}, {'UNDER_INVESTIGATION','AWAITING_INFORMATION'}),
    'INTAKE_FAILED': ({'SUBMITTED','UNDER_INVESTIGATION','AWAITING_INFORMATION'}, {'ESCALATED'}),
    'CLARIFICATION_ACCEPTED': ({'AWAITING_INFORMATION'}, {'UNDER_INVESTIGATION','AWAITING_INFORMATION'}),
    'ORDER_MATCHED': ({'UNDER_INVESTIGATION'}, {'POLICY_ASSESSMENT'}),
    'ORDER_NOT_FOUND': ({'UNDER_INVESTIGATION'}, {'AWAITING_INFORMATION'}),
    'ORDER_BLOCKED': ({'UNDER_INVESTIGATION'}, {'ESCALATED'}),
    'ORDER_FAILED': ({'UNDER_INVESTIGATION'}, {'ESCALATED'}),
}

def transition(uow, head, event, status, now, *, input_delta=0, question_set_id=None, failure_id=None):
    allowed = _TARGETS.get(event)
    if (allowed is None or head['status'] not in allowed[0] or status not in allowed[1]
            or type(input_delta) is not int or input_delta not in {0,1}
            or (input_delta and event not in {'CLARIFICATION_ACCEPTED','ORDER_MATCHED'})
            or (event == 'CLARIFICATION_ACCEPTED' and input_delta != 1)
            or (status == 'AWAITING_INFORMATION') != (question_set_id is not None)
            or (failure_id is not None and event not in {'INTAKE_FAILED','ORDER_FAILED'})):
        uow.poison()
        raise FlowError('INVALID_STATE')
    values = dict(case_version=head['case_version']+1, input_version=head['input_version']+input_delta,
        status=status, updated_at=now, current_question_set_id=question_set_id, current_failure_id=failure_id)
    if max(values['case_version'],values['input_version']) > 9007199254740991:
        uow.poison();raise FlowError('INVALID_STATE')
    changed = uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==head['case_id'],
        t.case_heads.c.case_version==head['case_version'],t.case_heads.c.input_version==head['input_version']).values(**values))
    if changed.rowcount != 1:
        uow.poison();raise FlowError('STALE_CASE_VERSION')
    return {**head, **values}

def initial_head(case_id, owner, store, now):
    return dict(case_id=case_id,owner_principal_id=owner,store_id=store,case_version=1,input_version=1,
        status='SUBMITTED',created_at=now,updated_at=now,history_sequence=0,audit_sequence=0,
        audit_head=None,current_question_set_id=None,available=True)

def record_denial(uow, case_id, actor, event, reason, correlation, now):
    # Do not include arbitrary caller event/reason strings in audit payloads.
    event = event if event in _TARGETS or event == 'submitClarification' else 'UNSUPPORTED_EVENT'
    reason = reason if reason in {'INVALID_STATE','STALE_CASE_VERSION'} else 'INVALID_STATE'
    append_event(uow,case_id,actor=actor,event_type='CUSTOMER_TRANSITION_DENIED',correlation_id=correlation,
        payload={'operation':event,'reason':reason},object_ids=[],history_refs=[],now=now)


def retain_content_state(uow,head,now):
    """Availability change, not a business restart or an escalation resolution.

    Retention can remove an AWAITING_INFORMATION question set, and keeps the
    sanitized escalation target. Normal transition invariants remain strict.
    """
    if head['case_version']>=9007199254740991:
        uow.poison();raise FlowError('INVALID_STATE')
    changed=uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==head['case_id'],
        t.case_heads.c.case_version==head['case_version']).values(case_version=head['case_version']+1,
            updated_at=now,current_question_set_id=None))
    if changed.rowcount!=1:
        uow.poison();raise FlowError('STALE_CASE_VERSION')
