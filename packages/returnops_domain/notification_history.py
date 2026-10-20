"""Domain-owned finite notification history; customer projection only after SENT."""
from dataclasses import asdict
from sqlalchemy import select, update
from . import customer_tables as old, founder_tables as finite_tables, lifecycle_tables as life
from . import founder_codec as finite
from .audit import append_event
from .manual_target import one
from .notification_profile import COMPONENT
from .lifecycle_state import reject


def append_note(uow, head, body, *, record_id, object_version, actor_component,
                correlation, payload, now, claim, target, slot='PRIMARY'):
    finite.validate('NotificationRecord', body)
    current = one(uow, old.case_heads, case_id=head['case_id'])
    ref = dict(record_id=record_id, kind='NOTIFICATION',
               object_id=body['notification_id'], object_version=object_version)
    value_hash = finite.digest(body)
    uow.execute(old.history.insert().values(**ref, case_id=head['case_id'],
        case_version=head['case_version'], recorded_sequence=current['history_sequence']+1,
        recorded_at=now, content_sha256=value_hash, retention_state='AVAILABLE', removal_reason=None))
    uow.execute(old.history_contents.insert().values(record_id=record_id, body=finite.encode_document(body)))
    uow.execute(finite_tables.encodings.insert().values(record_id=record_id, profile=finite.PROFILE,
        source_content_sha256=value_hash, projected_content_sha256=value_hash, receipt_id=None))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==head['case_id']).values(
        history_sequence=current['history_sequence']+1))
    append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':actor_component},
        event_type='NOTIFICATION_REVISION_RECORDED',correlation_id=correlation,payload=payload,
        object_ids=[body['notification_id']],history_refs=[ref],now=now)
    uow.execute(life.sources.insert().values(record_id=record_id,case_id=head['case_id'],**asdict(claim),
        source_hash=value_hash,target_record_id=target,slot=slot))
    return record_id


def append_customer(uow, head, control, fact, note, now):
    from .canonical import digest, encode_document
    from .wire import validate
    if note['status'] != 'SENT' or fact['status'] != 'SENT' or control['accepted_fact_id'] != fact['fact_id']:
        reject(uow)
    record_id = 'nmessage_' + digest({'notification_id':note['notification_id']},'notification-customer-id/v2')
    if uow.execute(select(old.history.c.record_id).where(old.history.c.record_id==record_id)).first():
        reject(uow)
    body = {name:note[name] for name in ('notification_id','outcome','message','next_steps','sent_at')}
    validate('CustomerOutcomeMessage',body,internal=True)
    current = one(uow,old.case_heads,case_id=head['case_id'])
    ref = dict(record_id=record_id,kind='OUTCOME_MESSAGE',object_id=note['notification_id'],object_version=1)
    uow.execute(old.history.insert().values(**ref,case_id=head['case_id'],case_version=current['case_version'],
        recorded_sequence=current['history_sequence']+1,recorded_at=now,
        content_sha256=digest(body,'history/v1'),retention_state='AVAILABLE',removal_reason=None))
    uow.execute(old.history_contents.insert().values(record_id=record_id,body=encode_document(body)))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==head['case_id']).values(
        history_sequence=current['history_sequence']+1))
    append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':COMPONENT},
        event_type='NOTIFICATION_CUSTOMER_MESSAGE_RECORDED',correlation_id=control['accepted_event_id'],
        payload=dict(profile='notification-customer-message/v2',intent_hash=control['intent_hash'],
            fact_hash=fact['fact_hash'],notification_record_id=control['accepted_record_id']),
        object_ids=[note['notification_id']],history_refs=[ref],now=now)
