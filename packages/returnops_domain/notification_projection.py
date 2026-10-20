"""Authorized existing read paths expose only proven SENT customer content."""
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import digest, decode_document
from .founder_integrity import CaseProof
from .lifecycle_schema import NOTIFICATION, version
from .lifecycle_state import reject
from .manual_target import one
from .notification_profile import COMPONENT
from .notification_tables import controls, facts
from .notification_sources import validate_control


def verify_founder_note(uow, head, row):
    if version(uow.connection) != NOTIFICATION:
        return
    saved = uow.execute(select(controls).where(controls.c.notification_id==row['object_id'])).mappings().one_or_none()
    if saved is None:
        from .notification_intent import RETURN_PRODUCER
        actor = CaseProof(uow,head).origin(row)['actor']
        if actor.get('component_id') in {COMPONENT,RETURN_PRODUCER}:
            reject(uow)
        state=one(uow,life.state,case_id=head['case_id'])
        if state['notification_id']!=row['object_id'] or state['notification_work_id'] is None:
            reject(uow)
        work=one(uow,life.work,work_id=state['notification_work_id'])
        if (work['component_id']==COMPONENT or work['component_id']!=actor.get('component_id')
                or work['purpose']!='NOTIFICATION' or work['case_id']!=head['case_id']
                or work['store_id']!=head['store_id'] or work['owner_id']!=head['owner_principal_id']):
            reject(uow)
        return  # Retained v1 is historical only; the write gate keeps it HOLD.
    if saved['case_id'] != head['case_id']:
        reject(uow)
    if row['retention_state']=='AVAILABLE':
        validate_control(uow,head,dict(saved))
    else:
        from .notification_retention import verify_retained
        verify_retained(uow,head,dict(saved))


def verify_message(uow, row):
    from .notification_customer_origin import (
        message_markers, verify_customer_origin, verify_accepted_metadata)
    modern, markers = message_markers(uow,row)
    if not modern:
        return False  # Original historical DTO/hash/tombstone oracle remains in history.read_revision.
    head=one(uow,old.case_heads,case_id=row['case_id'])
    control=one(uow,controls,notification_id=row['object_id'])
    fact=one(uow,facts,fact_id=control['accepted_fact_id'])
    proof=CaseProof(uow,head)
    accepted=verify_customer_origin(uow,head,row,control,fact,proof,markers)
    verify_accepted_metadata(uow,head,control,fact,accepted,proof)
    if row['retention_state']!='AVAILABLE':
        from .notification_retention import verify_retained
        verify_retained(uow,head,control)
        return True
    seal=validate_control(uow,head,control)
    note=seal['note']
    raw=one(uow,old.history_contents,record_id=row['record_id'])['body']
    expected={name:note[name] for name in ('notification_id','outcome','message','next_steps','sent_at')}
    if (control['state']!='SENT' or note['status']!='SENT' or decode_document(raw)!=expected
            or note['sent_at']!=timestamp(fact['accepted_at'])
            or digest(expected,'history/v1')!=row['content_sha256']):
        reject(uow)
    return True


def current_messages(uow, head, messages):
    """Legacy rows never become current SENT evidence or modern cardinality."""
    from .notification_customer_origin import current_case_markers
    from .notification_mock import verify_fact
    markers=current_case_markers(uow,head)
    modern = [row for row in messages if verify_message(uow,row)]
    saved=markers['controls']
    if (len(modern)>1 or len(saved)>1 or markers['facts'] and not saved
            or markers['events'] and (len(modern)!=1 or len(saved)!=1)):
        reject(uow)
    for control in saved:
        if (control['case_id']!=head['case_id'] or control['store_id']!=head['store_id']
                or control['owner_id']!=head['owner_principal_id']):
            reject(uow)
        for fact in markers['facts']:
            verify_fact(uow,control,fact)
        accepted=(control['accepted_fact_id'] is not None and
                  one(uow,facts,fact_id=control['accepted_fact_id'])['status']=='SENT')
        if bool(accepted)!=bool(modern):
            reject(uow)
    return modern
