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
    if version(uow.connection)!=NOTIFICATION:
        reject(uow)
    head=one(uow,old.case_heads,case_id=row['case_id'])
    control=one(uow,controls,notification_id=row['object_id'])
    fact=one(uow,facts,fact_id=control['accepted_fact_id'])
    proof=CaseProof(uow,head)
    origin=proof.origin(row)
    payload=dict(profile='notification-customer-message/v2',intent_hash=control['intent_hash'],
        fact_hash=fact['fact_hash'],notification_record_id=control['accepted_record_id'])
    expected_id='nmessage_'+digest({'notification_id':control['notification_id']},'notification-customer-id/v2')
    if (row['record_id']!=expected_id or row['object_version']!=1
            or control['case_id']!=head['case_id'] or fact['status']!='SENT'
            or origin['event_type']!='NOTIFICATION_CUSTOMER_MESSAGE_RECORDED'
            or origin['actor']!={'kind':'SERVICE','component_id':COMPONENT}
            or origin['correlation_id']!=control['accepted_event_id']
            or origin['payload_hash']!=digest(payload,'audit-payload/v1')):
        reject(uow)
    if row['retention_state']!='AVAILABLE':
        from .notification_retention import verify_retained
        verify_retained(uow,head,control)
        return
    seal=validate_control(uow,head,control)
    note=seal['note']
    raw=one(uow,old.history_contents,record_id=row['record_id'])['body']
    expected={name:note[name] for name in ('notification_id','outcome','message','next_steps','sent_at')}
    if (control['state']!='SENT' or note['status']!='SENT' or decode_document(raw)!=expected
            or note['sent_at']!=timestamp(fact['accepted_at'])):
        reject(uow)
