"""Private A2.06: committed T1, independent CORE_MOCK T2, guarded Domain T3.

No public HTTP mutation, provider dispatch, label render or arbitrary message.
Uncertain acknowledgement is never converted to proof of no effect.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from . import customer_tables as old, lifecycle_tables as life
from .audit import identifier, timestamp, append_event
from .canonical import digest, encode_document, decode_document
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError, AcceptanceOutcomeUnknown
from .lifecycle_events import OutcomeAccepted, NotificationObserved
from .lifecycle_guards import LifecycleGuards
from .lifecycle_sources import authority
from .lifecycle_state import reject, MAX_VERSION
from .lifecycle_schema import NOTIFICATION, version
from .manual_target import one
from .notification_profile import COMPONENT, render
from .notification_tables import controls, facts
from .notification_intent import RETURN_PRODUCER, initial_payload
from .notification_sources import validate_control, reservation_core, phase_payload
from .notification_history import append_note, append_customer
from .notification_mock import CoreMockNotification, verify_fact
from .return_execution_sources import database_now


@dataclass(frozen=True)
class NotificationResult:
    status: str
    notification_work_id: str | None = None
    notification_id: str | None = None
    reservation_id: str | None = None
    case_version: int | None = None


def result(control, status, case_version=None):
    return NotificationResult(status,control['notification_work_id'],control['notification_id'],
                              control['reservation_id'],case_version)


class NotificationService:
    def __init__(self, engine, authority_callback=None, *, mock=None,
                 uow_factory=CustomerUnitOfWork, clock=lambda:datetime.now(timezone.utc)):
        self.engine, self.authority_callback = engine, authority_callback
        self.uow_factory, self.clock = uow_factory, clock
        self.guard = LifecycleGuards(COMPONENT,clock=clock)
        self.mock = CoreMockNotification(engine) if mock is None else mock
        if not isinstance(self.mock, CoreMockNotification):
            raise ValueError('Only the closed CORE_MOCK notification implementation is supported')

    @staticmethod
    def _load(uow, work_id):
        if version(uow.connection) != NOTIFICATION:
            reject(uow)
        work = one(uow,life.work,work_id=work_id)
        head = one(uow,old.case_heads,case_id=work['case_id'])
        authority(uow,head,COMPONENT,'NOTIFICATION',lock_rows=uow.write)
        control = uow.execute(select(controls).where(controls.c.notification_work_id==work_id)).mappings().one_or_none()
        if control is None:
            return head, None, None
        control = dict(control)
        return head, control, validate_control(uow,head,control)

    def produce_return(self, case_id, expected_case_version):
        """Create the real RETURN_CREATED outcome from the saved complete pair."""
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                if version(uow.connection) != NOTIFICATION:
                    reject(uow)
                head = one(uow,old.case_heads,case_id=case_id)
                authority(uow,head,RETURN_PRODUCER,'OUTCOME')
                if head['case_version'] != expected_case_version:
                    reject(uow,'STALE_CASE_VERSION')
                from .notification_execution import completed_pair
                pair = completed_pair(uow,head)
                from .lifecycle_state import current
                if current(uow,head,initialize=False)['outcome'] is not None:
                    reject(uow)
                now = database_now(uow)
                guard = LifecycleGuards(RETURN_PRODUCER,clock=self.clock)
                work_id = guard.prepare(uow,case_id,expected_case_version,OutcomeAccepted,now)
                claim = guard.claim(uow,work_id,now)
                if claim is None:
                    reject(uow)
                record_id = identifier('notification_initial')
                note = dict(notification_id=identifier('notification'),case_id=case_id,
                    case_version=head['case_version'],status='PENDING',outcome='RETURN_CREATED',
                    **render('RETURN_CREATED',label_evidence_id=pair['evidence_id']),
                    attempt_count=0,updated_at=timestamp(now))
                append_note(uow,head,note,record_id=record_id,object_version=1,actor_component=RETURN_PRODUCER,
                    correlation=identifier('notification_origin'),payload=initial_payload(RETURN_PRODUCER,
                        'RETURN_CREATED',pair['label_record_id'],pair['artifact']['result_record']['content_sha256']),
                    now=now,claim=claim,target=record_id)
                guard.apply(uow,OutcomeAccepted(identifier('notification_outcome'),claim,record_id,record_id,
                            pair['return_record_id'],pair['label_record_id']),now)
                state = current(uow,one(uow,old.case_heads,case_id=case_id),initialize=False)
                control = one(uow,controls,notification_work_id=state['notification_work_id'])
                answer = result(control,'READY',expected_case_version+1)
                uow.commit()
            return answer
        except (FlowError,AcceptanceOutcomeUnknown):
            return NotificationResult('UNKNOWN')

    def send(self, work_id):
        """Only this invocation's acknowledged fresh T1 may call T2 once."""
        fresh = False
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                head, control, seal = self._load(uow,work_id)
                if control is None:
                    return NotificationResult('HOLD',work_id)
                if control['state'] != 'READY':
                    reservation_id = control['reservation_id']
                else:
                    now = database_now(uow)
                    claim = self.guard.claim(uow,work_id,now)
                    if claim is None or control['attempt_count'] >= MAX_VERSION:
                        reject(uow)
                    claimed = one(uow,life.work,work_id=work_id)
                    reservation_id, record_id, event_id = (identifier(prefix) for prefix in
                        ('notification_reservation','notification_reserved','notification_event'))
                    staged = {**control,'attempt_count':control['attempt_count']+1,'reservation_id':reservation_id}
                    core = reservation_core(staged,claim,now,claimed['lease_expires_at'])
                    values = dict(state='RESERVED',attempt_count=staged['attempt_count'],reservation_id=reservation_id,
                        reservation_claim_id=claim.claim_id,reservation_epoch=claim.epoch,
                        reservation_case_version=claim.case_version,reservation_authority_revision=claim.authority_revision,
                        reservation_at=now,reservation_deadline=claimed['lease_expires_at'],
                        reservation_core=encode_document(core),reservation_hash=digest(core,'notification-reservation/v2'),
                        reservation_record_id=record_id,reservation_event_id=event_id)
                    uow.execute(update(controls).where(controls.c.notification_work_id==work_id).values(**values))
                    control = {**control,**values}
                    body = {name:value for name,value in seal['note'].items() if name not in {'error','sent_at'}}
                    body.update(case_version=head['case_version'],status='PENDING',
                                attempt_count=control['attempt_count'],updated_at=timestamp(now))
                    append_note(uow,head,body,record_id=record_id,object_version=len(seal['revisions'])+1,
                        actor_component=COMPONENT,correlation=event_id,
                        payload=phase_payload(control,'RESERVE',control['reservation_hash']),
                        now=now,claim=claim,target=control['outcome_record_id'])
                    self.guard.apply(uow,NotificationObserved(event_id,claim,record_id),now)
                    uow.commit()
                    fresh = True
            # Context exit must also acknowledge close before the sending call.
            if fresh:
                self.mock.deliver(reservation_id)
            return self.reconcile(work_id)
        except (FlowError,AcceptanceOutcomeUnknown):
            return NotificationResult('UNKNOWN',work_id)

    def reconcile(self, work_id):
        """Query the original reservation; never invoke deliver or a business effect."""
        try:
            with self.uow_factory(self.engine,write=False) as uow:
                head,control,seal = self._load(uow,work_id)
                if control is None:
                    return NotificationResult('HOLD',work_id)
                if control['reservation_id'] is None:
                    return result(control,'READY',head['case_version'])
                reservation_id = control['reservation_id']
                uow.commit()
            observed = self.mock.query(reservation_id)
            if observed is None:
                return result(control,'UNKNOWN')
            with self.uow_factory(self.engine,write=True) as uow:
                head,control,seal = self._load(uow,work_id)
                fact = one(uow,facts,fact_id=observed['fact_id'])
                verify_fact(uow,control,fact)
                if fact != observed or fact['reservation_id'] != control['reservation_id']:
                    reject(uow)
                if control['accepted_fact_id'] == fact['fact_id']:
                    return result(control,control['state'],head['case_version'])
                if control['state'] not in {'RESERVED','UNKNOWN'}:
                    reject(uow)
                now = database_now(uow)
                claim = self.guard.claim(uow,work_id,now)
                if claim is None:
                    reject(uow)
                record_id, event_id = identifier('notification_result'), identifier('notification_event')
                status = 'SENT' if fact['status']=='SENT' else 'FAILED'
                body = {name:value for name,value in seal['note'].items() if name not in {'error','sent_at'}}
                body.update(case_version=head['case_version'],status=status,updated_at=timestamp(now))
                if status=='SENT':
                    body['sent_at']=timestamp(fact['accepted_at'])
                values=dict(state=fact['status'],accepted_fact_id=fact['fact_id'],
                            accepted_record_id=record_id,accepted_event_id=event_id)
                uow.execute(update(controls).where(controls.c.notification_work_id==work_id).values(**values))
                control={**control,**values}
                append_note(uow,head,body,record_id=record_id,object_version=len(seal['revisions'])+1,
                    actor_component=COMPONENT,correlation=event_id,payload=phase_payload(control,'FACT',fact['fact_hash']),
                    now=now,claim=claim,target=control['outcome_record_id'])
                accepted=self.guard.apply(uow,NotificationObserved(event_id,claim,record_id),now)
                if status=='SENT':
                    append_customer(uow,head,control,fact,body,now)
                answer=result(control,control['state'],accepted['case_version'])
                uow.commit()
            return answer
        except (FlowError,AcceptanceOutcomeUnknown):
            return NotificationResult('UNKNOWN',work_id)

    def retry(self, work_id, expected_case_version):
        """Current Founder may authorize only a proven NO_EFFECT_FAILED attempt."""
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                head,control,seal=self._load(uow,work_id)
                if control is None:
                    return NotificationResult('HOLD',work_id)
                if self.authority_callback is None:
                    reject(uow,'FORBIDDEN')
                actor=self.authority_callback(uow.connection,'getSession')
                if (actor.role!='FOUNDER' or actor.store_id!=head['store_id']
                        or self.authority_callback(uow.connection,'getFounderCase',head['case_id'])!=actor):
                    reject(uow,'FORBIDDEN')
                if head['case_version']!=expected_case_version:
                    reject(uow,'STALE_CASE_VERSION')
                if control['state']!='NO_EFFECT_FAILED' or seal['note']['status']!='FAILED':
                    reject(uow)
                fact=one(uow,facts,fact_id=control['accepted_fact_id'])
                verify_fact(uow,control,fact)
                if fact['status']!='NO_EFFECT_FAILED' or any(saved['status']=='SENT' for saved in seal['facts']):
                    reject(uow)
                from .approval_admission_sources import session_bounds,check_session_time
                bounds=session_bounds(uow,actor)
                now=database_now(uow);check_session_time(now,bounds)
                claim=self.guard.claim(uow,work_id,now)
                if claim is None:reject(uow)
                record_id,event_id=identifier('notification_retry'),identifier('notification_event')
                entry=dict(record_id=record_id,event_id=event_id,principal_id=actor.principal_id,
                    session_id=actor.session_id,session_bounds=list(bounds[2:5]),
                    expected_case_version=expected_case_version,fact_id=fact['fact_id'],
                    fact_hash=fact['fact_hash'],authorized_at=timestamp(now))
                audit=append_event(uow,head['case_id'],
                    actor={'kind':'HUMAN','role':'FOUNDER','principal_id':actor.principal_id},
                    event_type='NOTIFICATION_RETRY_AUTHORIZED',correlation_id=event_id,payload=entry,
                    object_ids=[control['notification_id']],history_refs=[],now=now)
                entry={**entry,'audit_id':audit['event_id']}
                previous=[] if control['retry_authorization'] is None else decode_document(control['retry_authorization'])
                values=dict(state='READY',retry_record_id=record_id,retry_event_id=event_id,
                            retry_authorization=encode_document([*previous,entry]))
                uow.execute(update(controls).where(controls.c.notification_work_id==work_id).values(**values))
                control={**control,**values}
                body={name:value for name,value in seal['note'].items() if name not in {'error','sent_at'}}
                body.update(case_version=head['case_version'],status='PENDING',updated_at=timestamp(now))
                append_note(uow,head,body,record_id=record_id,object_version=len(seal['revisions'])+1,
                    actor_component=COMPONENT,correlation=event_id,
                    payload=phase_payload(control,'RETRY',digest(entry,'notification-retry/v2')),
                    now=now,claim=claim,target=control['outcome_record_id'])
                accepted=self.guard.apply(uow,NotificationObserved(event_id,claim,record_id),now)
                def check():
                    if (self.authority_callback(uow.connection,'getSession')!=actor
                            or self.authority_callback(uow.connection,'getFounderCase',head['case_id'])!=actor
                            or session_bounds(uow,actor)!=bounds):
                        reject(uow,'UNAUTHENTICATED')
                    check_session_time(database_now(uow),bounds)
                uow.before_commit(check)
                answer=result(control,'READY',accepted['case_version'])
                uow.commit()
            return answer
        except (FlowError,AcceptanceOutcomeUnknown):
            return NotificationResult('UNKNOWN',work_id)
