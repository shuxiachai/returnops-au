"""Atomic notification tombstones; facts and original identity never regenerate."""
from sqlalchemy import select, update, delete
from . import customer_tables as old, lifecycle_tables as life
from .audit import append_event, identifier
from .canonical import digest
from .founder_integrity import CaseProof
from .lifecycle_state import reject
from .lifecycle_schema import NOTIFICATION, version
from .manual_target import one
from .notification_tables import controls
from .return_execution_sources import database_now

ACTOR = {'kind':'SERVICE','component_id':'retention-v1'}
EVENT = 'NOTIFICATION_SOURCE_WITHDRAWN'


def payload(control, reason, disposition):
    return dict(profile='notification-retention/v2',notification_work_id=control['notification_work_id'],
        notification_id=control['notification_id'],intent_hash=control['intent_hash'],source_hash=control['source_hash'],
        reason=reason,retention_state=disposition)


def withdraw(uow,case_id,reason,redact,now=None):
    if version(uow.connection)!=NOTIFICATION:
        return
    now=database_now(uow) if now is None else now
    for control in uow.execute(select(controls).where(controls.c.case_id==case_id)).mappings().all():
        if not control['available']:
            verify_retained(uow,one(uow,old.case_heads,case_id=case_id),dict(control))
            continue
        disposition='REDACTED' if redact else 'DELETED'
        ids=select(old.history.c.record_id).where(old.history.c.case_id==case_id,
            old.history.c.object_id==control['notification_id'],
            old.history.c.kind.in_(['NOTIFICATION','OUTCOME_MESSAGE']))
        uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id.in_(ids)))
        uow.execute(update(old.history).where(old.history.c.record_id.in_(ids),
            old.history.c.retention_state=='AVAILABLE').values(retention_state=disposition,removal_reason=reason))
        uow.execute(update(controls).where(controls.c.notification_work_id==control['notification_work_id']).values(
            available=False,state='RETAINED',source_manifest=None))
        uow.execute(update(life.work).where(life.work.c.work_id==control['notification_work_id'],
            life.work.c.state.in_(['PENDING','RUNNING'])).values(state='PAUSED',lease_expires_at=None))
        append_event(uow,case_id,actor=ACTOR,event_type=EVENT,correlation_id=identifier('notification_retention'),
            payload=payload(control,reason,disposition),object_ids=[control['notification_id']],history_refs=[],now=now)
        def final(work_id=control['notification_work_id']):
            saved=one(uow,controls,notification_work_id=work_id)
            verify_retained(uow,one(uow,old.case_heads,case_id=case_id),saved)
        uow.before_commit(final)


def verify_retained(uow,head,control):
    if (control['available'] or control['state']!='RETAINED' or control['source_manifest'] is not None
            or control['case_id']!=head['case_id']):
        reject(uow)
    proof=CaseProof(uow,head)
    records=[row for row in proof.revisions.values() if row['object_id']==control['notification_id']
             and row['kind'] in {'NOTIFICATION','OUTCOME_MESSAGE'}]
    if not records or control['initial_notification_record_id'] not in {row['record_id'] for row in records}:
        reject(uow)
    first=records[0]
    if (first['retention_state'] not in {'DELETED','REDACTED'} or first['removal_reason'] not in
            {'RETENTION_POLICY','OWNER_REQUEST'}
            or any(row['retention_state']!=first['retention_state'] or row['removal_reason']!=first['removal_reason']
                   for row in records)):
        reject(uow)
    if uow.execute(select(old.history_contents.c.record_id).where(
        old.history_contents.c.record_id.in_([row['record_id'] for row in records]))).first():
        reject(uow)
    expected=digest(payload(control,first['removal_reason'],first['retention_state']),'audit-payload/v1')
    events=[event for event in proof.events if event['event_type']==EVENT
            and event['object_ids']==[control['notification_id']]]
    if (len(events)!=1 or events[0]['actor']!=ACTOR or events[0]['payload_hash']!=expected
            or events[0]['history_refs']!=[]):
        reject(uow)
