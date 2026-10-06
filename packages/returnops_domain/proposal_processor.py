"""Durable fixed synthetic proposal producer, ending at RISK_REVIEW.

First commit only a stable PENDING intent. Claim, complete-source construction,
append, audit, binding and guarded acceptance share the next fenced transaction.
UNKNOWN is resolved against the original intent on a fresh exclusive fence;
only proven rollback can resume that same identity. No future effect is run.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, select, update
from . import customer_tables as old, founder_tables as finite_tables, lifecycle_tables as t
from . import founder_codec as finite
from .audit import append_event, timestamp
from .canonical import digest, encode_document
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .fixed_proposal import build_fixed_proposal, ProposalCapacityError, CAPACITY_MESSAGE
from .lifecycle_events import LifecycleClaim, ProposalAccepted, ProposalFailed
from .lifecycle_guards import LifecycleGuards, target
from .lifecycle_state import reject
from .proposal_denial import record_denial, DENIAL_CODES
from .proposal_policy import ACTOR, COMPONENT, KEY_FIELDS, intent_key, stable_id
from .proposal_sources import read_material
from .wire import validate

@dataclass(frozen=True, repr=False)
class Intent:
    work_id: str
    key: dict
    created_at: str
    authority_revision: int


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    work_id: str | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'

    def __bool__(self):
        return self.status in {'ACCEPTED','FAILED'}


class _ProposalUnitOfWork(CustomerUnitOfWork):
    """Keep retryable check failures distinguishable after base-UoW sanitizing.

    The base transaction still poisons, closes and sanitizes exactly as before.
    This flag contains no SQL, exception, source body or diagnostic payload.
    """
    retryable_rollback = False

    def execute(self, statement, parameters=None):
        try:
            return super().execute(statement,parameters)
        except FlowError as error:
            if error.code == 'INTERNAL_ERROR':
                self.retryable_rollback = True
            raise

    def before_commit(self, check):
        def classified_check():
            try:
                return check()
            except FlowError as error:
                if error.code == 'INTERNAL_ERROR':
                    self.retryable_rollback = True
                raise
            except Exception:
                self.retryable_rollback = True
                raise
        super().before_commit(classified_check)


class FixedProposalProcessor:
    def __init__(self, engine, *, clock=lambda: datetime.now(timezone.utc), lease_seconds=60,
                 uow_factory=_ProposalUnitOfWork, resolve_uow=CustomerUnitOfWork,
                 audit_uow=CustomerUnitOfWork, build=build_fixed_proposal,retry_seconds=1):
        if (type(lease_seconds) is not int or not 1 <= lease_seconds <= 300
                or type(retry_seconds) is not int or not 1 <= retry_seconds <= 30):
            raise FlowError('VALIDATION_ERROR')
        self.engine, self.clock, self.lease_seconds = engine, clock, lease_seconds
        self.uow_factory, self.resolve_uow, self.audit_uow = uow_factory, resolve_uow, audit_uow
        self.build = build
        self.guard = LifecycleGuards(COMPONENT, clock=clock)
        self._uncertain = None
        self.retry_seconds = retry_seconds
        self._retry_intent = None
        self._retry_after = None
        self._retry_failures = 0

    @staticmethod
    def _closed(uow):
        return uow is None or uow.connection is None or (uow.finished and uow.connection.closed)

    def _retryable(self,intent,*,resume=True):
        self._retry_failures = min(self._retry_failures+1,7)
        delay = min(60,self.retry_seconds * 2**(self._retry_failures-1))
        self._retry_after = self.clock()+timedelta(seconds=delay)
        self._retry_intent = intent if resume else None
        return ProcessingResult('RETRYABLE',None if intent is None else intent.work_id,'INTERNAL_ERROR')

    def _clear_retry(self):
        self._retry_intent = self._retry_after = None
        self._retry_failures = 0

    def _uow(self, *, resolve=False):
        factory = self.resolve_uow if resolve else self.uow_factory
        return factory(self.engine, write=True, lock_timeout_ms=500)

    @staticmethod
    def _intent(row):
        return Intent(row['work_id'], {key: row[key] for key in KEY_FIELDS},
                      timestamp(row['created_at']),row['authority_revision'])

    @staticmethod
    def _work(uow, intent):
        if (type(intent) is not Intent or set(intent.key) != set(KEY_FIELDS)
                or intent.key['component_id'] != COMPONENT or intent.key['purpose'] != 'PROPOSAL'
                or intent.work_id != stable_id('work',intent.key)):
            reject(uow,'IDEMPOTENCY_CONFLICT')
        row = uow.execute(select(t.work).where(t.work.c.work_id == intent.work_id)).mappings().one_or_none()
        if row is not None and (any(row[key] != value for key,value in intent.key.items())
                or timestamp(row['created_at']) != intent.created_at
                or row['authority_revision'] != intent.authority_revision
                or row['target_record_id'] is not None or row['idempotency_key'] is not None):
            reject(uow, 'IDEMPOTENCY_CONFLICT')
        return row

    @staticmethod
    def _empty_attempt(uow, intent):
        source_id = stable_id('source', intent.work_id)
        if (uow.execute(select(t.sources.c.record_id).where(t.sources.c.work_id == intent.work_id)).first()
                or uow.execute(select(t.events.c.event_id).where(t.events.c.work_id == intent.work_id)).first()
                or uow.execute(select(old.history.c.record_id).where(old.history.c.record_id == source_id)).first()
                or uow.execute(select(t.effects.c.record_id).where(or_(
                    t.effects.c.record_id == source_id,t.effects.c.dispatch_source_record_id == source_id))).first()
                or uow.execute(select(old.processing_failures.c.failure_id).where(
                    old.processing_failures.c.failure_id == stable_id('failure',intent.work_id))).first()):
            reject(uow, 'IDEMPOTENCY_CONFLICT')

    def _context(self, uow, intent, work):
        head,state,grant = self.guard._load(uow,intent.key['case_id'],'PROPOSAL')
        self.guard._work_context(uow,head,state,grant,work)
        if work['authority_revision'] != grant['revision']:
            reject(uow,'FORBIDDEN')
        return head,state,grant

    @staticmethod
    def _material(uow,head):
        invalid = False
        try:
            return read_material(uow,head)
        except FlowError as error:
            # The private UoW identifies SQL failures independently. A complete
            # successful read whose retained provenance fails is a data denial.
            if error.code=='INTERNAL_ERROR' and getattr(uow,'retryable_rollback',True) is False:
                invalid = True
            else:
                raise
        if invalid:
            reject(uow,'INVALID_STATE')

    def prepare(self, case_id):
        """Trusted case identity, never a source bundle or requested status."""
        validate('Id',case_id)
        intent = None
        committed = False
        uow = None
        try:
            uow = self._uow()
            with uow:
                head,state,grant = self.guard._load(uow,case_id,'PROPOSAL')
                key = intent_key(head,state,target(head,state,'PROPOSAL'))
                work_id = stable_id('work',key)
                self.guard.prepare(uow,case_id,head['case_version'],ProposalAccepted,self.clock(),work_id=work_id)
                row = uow.execute(select(t.work).where(t.work.c.work_id==work_id)).mappings().one()
                intent = self._intent(row)
                if intent.key != key:
                    reject(uow,'IDEMPOTENCY_CONFLICT')
                work = self._work(uow,intent)
                if (work['state'] != 'PENDING' or work['epoch'] != 0 or work['claim_id'] is not None
                        or work['claimed_case_version'] is not None or work['lease_expires_at'] is not None):
                    reject(uow)
                self._empty_attempt(uow,intent)
                sealed = dict(work)
                def check():
                    actual = self._work(uow,intent)
                    h,s,g = self._context(uow,intent,actual)
                    if dict(actual) != sealed or h['case_version'] != head['case_version'] or g['revision'] != grant['revision']:
                        reject(uow)
                    self.guard._allowed(uow,h,s,'PROPOSAL')
                uow.before_commit(check)
                uow.commit()
                committed = True
                return intent
        except AcceptanceOutcomeUnknown:
            pass
        except FlowError as error:
            if not committed and self._closed(uow):
                if error.code in DENIAL_CODES and not getattr(uow,'retryable_rollback',False):
                    return self._denied(intent,error.code)
                # This transaction is known to have rolled back. Its initial
                # intent may not exist; a later scan still uses deterministic K.
                return self._retryable(intent,resume=False)
        except Exception:
            if not committed and self._closed(uow):
                return self._retryable(intent,resume=False)
        if intent is None:
            return ProcessingResult('UNKNOWN')
        self._uncertain = intent
        # Resolution never creates a replacement after an ambiguous commit.
        outcome = self.resolve(intent)
        return intent if outcome.status == 'PENDING' else outcome

    def _replay(self, uow, intent, work):
        rows = uow.execute(select(t.events).where(t.events.c.work_id == intent.work_id)).mappings().all()
        if len(rows) != 1:
            reject(uow)
        receipt = rows[0]
        event_type = {'PROPOSAL':ProposalAccepted,'PROPOSAL_FAILED':ProposalFailed}.get(receipt['event_kind'])
        if (event_type is None or receipt['event_id'] != stable_id('event',intent.work_id)
                or receipt['record_id'] != stable_id('source',intent.work_id)
                or receipt['status'] != ('RISK_REVIEW' if event_type is ProposalAccepted else 'ESCALATED')):
            reject(uow)
        claim = LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],
                               work['input_version'],work['generation'],work['authority_revision'])
        event = event_type(receipt['event_id'],claim,receipt['record_id'])
        if self.guard.apply(uow,event,self.clock()) != dict(receipt):
            reject(uow)
        return ProcessingResult('ACCEPTED' if event_type is ProposalAccepted else 'FAILED',intent.work_id)

    def resolve(self, intent):
        """Resolve only the original K/ID; DB/lock uncertainty remains UNKNOWN."""
        try:
            with self._uow(resolve=True) as uow:
                work = self._work(uow,intent)
                if work is None:
                    # A same natural-key row with another ID is not rollback.
                    predicates = [getattr(t.work.c,key) == intent.key[key]
                                  for key in ('case_id','purpose','generation','target_hash')]
                    if uow.execute(select(t.work.c.work_id).where(*predicates)).first():
                        reject(uow,'IDEMPOTENCY_CONFLICT')
                    self._empty_attempt(uow,intent)
                    outcome = ProcessingResult('ROLLED_BACK',intent.work_id)
                elif work['state'] == 'DONE':
                    outcome = self._replay(uow,intent,work)
                elif (work['state'] == 'PENDING' and work['epoch'] == 0 and work['claim_id'] is None
                      and work['claimed_case_version'] is None and work['lease_expires_at'] is None):
                    self._context(uow,intent,work)
                    self._empty_attempt(uow,intent)
                    outcome = ProcessingResult('PENDING',intent.work_id)
                elif work['state'] in {'PAUSED','SUPERSEDED'}:
                    outcome = ProcessingResult('DENIED',intent.work_id,'INVALID_STATE')
                else:
                    reject(uow)
                uow.commit()
            self._uncertain = None
            if outcome.status in {'ACCEPTED','FAILED','DENIED'}:
                self._clear_retry()
            return outcome
        except Exception:
            self._uncertain = intent
            return ProcessingResult('UNKNOWN',intent.work_id)

    def _append(self,uow,head,work,claim,body,now,*,failed):
        invalid = False
        try:
            if failed:
                validate('ProcessingFailure',body,internal=True)
            else:
                finite.validate('HistoricalProposalBundle',body)
        except (FlowError,KeyError,TypeError,UnicodeError,ValueError,RecursionError):
            invalid = True
        if invalid:
            reject(uow,'INVALID_STATE')
        source_id = stable_id('source',work['work_id'])
        kind = 'PROCESSING_FAILURE' if failed else 'PROPOSAL'
        object_id = body['failure_id'] if failed else body['packet']['proposal_id']
        version = 1 if failed else body['packet']['proposal_version']
        if failed:
            raw, source_hash = encode_document(body), digest(body,'history/v1')
            uow.execute(old.processing_failures.insert().values(failure_id=object_id,case_id=head['case_id'],
                input_version=head['input_version'],body=raw,occurred_at=now))
        else:
            raw, source_hash = finite.encode_document(body), finite.digest(body)
        ref = dict(record_id=source_id,kind=kind,object_id=object_id,object_version=version)
        uow.execute(old.history.insert().values(**ref,case_id=head['case_id'],case_version=head['case_version'],
            recorded_sequence=head['history_sequence']+1,recorded_at=now,content_sha256=source_hash,
            retention_state='AVAILABLE',removal_reason=None))
        uow.execute(old.history_contents.insert().values(record_id=source_id,body=raw))
        if not failed:
            uow.execute(finite_tables.encodings.insert().values(record_id=source_id,profile=finite.PROFILE,
                source_content_sha256=source_hash,projected_content_sha256=source_hash,receipt_id=None))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==head['case_id']).values(
            history_sequence=head['history_sequence']+1))
        append_event(uow,head['case_id'],actor=ACTOR,
            event_type='FIXED_PROPOSAL_FAILED' if failed else 'PROPOSAL_ACCEPTED',
            correlation_id=stable_id('event',work['work_id']),
            payload={'synthetic_fixed_proposal':True,'model_called':False,'work_id':work['work_id']},
            object_ids=[object_id],history_refs=[ref],now=now)
        return source_id,source_hash

    def process(self,intent):
        committed = False
        uow = None
        try:
            uow = self._uow()
            with uow:
                work = self._work(uow,intent)
                if work is None:
                    reject(uow)
                if work['state'] == 'DONE':
                    outcome = self._replay(uow,intent,work)
                    uow.commit()
                    committed = True
                    self._clear_retry()
                    return outcome
                self._context(uow,intent,work)
                self._empty_attempt(uow,intent)
                now = self.clock()
                claim = self.guard.claim(uow,intent.work_id,now,lease_seconds=self.lease_seconds)
                if claim is None:
                    reject(uow)
                head,state,_ = self.guard._load(uow,work['case_id'],'PROPOSAL')
                material = self._material(uow,head)
                original_fingerprint = material.fingerprint()
                failed = False
                try:
                    body = self.build(material,work,state['proposal_version']+1,now)
                except ProposalCapacityError:
                    failed = True
                if material.fingerprint() != original_fingerprint or self._material(uow,head).fingerprint() != original_fingerprint:
                    reject(uow)
                if failed:
                    error = FlowError('REQUEST_TOO_LARGE').envelope(stable_id('event',work['work_id']))
                    error['error']['message'] = CAPACITY_MESSAGE
                    body = dict(failure_id=stable_id('failure',work['work_id']),case_id=head['case_id'],
                        input_version=head['input_version'],stage='ASSESSMENT',error=error,occurred_at=timestamp(now))
                source_id,source_hash = self._append(uow,head,work,claim,body,now,failed=failed)
                uow.execute(t.sources.insert().values(record_id=source_id,case_id=head['case_id'],
                    **asdict(claim),source_hash=source_hash,target_record_id=None,slot='PRIMARY',
                    order_projection_id=material.projection_id))
                event_type = ProposalFailed if failed else ProposalAccepted
                event = event_type(stable_id('event',work['work_id']),claim,source_id)
                self.guard.apply(uow,event,now)
                uow.commit()
                committed = True
                outcome = ProcessingResult('FAILED' if failed else 'ACCEPTED',intent.work_id)
            self._clear_retry()
            return outcome
        except AcceptanceOutcomeUnknown:
            pass
        except FlowError as error:
            if not committed and self._closed(uow):
                if error.code in DENIAL_CODES and not getattr(uow,'retryable_rollback',False):
                    return self._denied(intent,error.code)
                return self._retryable(intent)
        except Exception:
            if not committed and self._closed(uow):
                return self._retryable(intent)
        self._uncertain = intent
        return self.resolve(intent)

    def _denied(self,intent,code):
        if code not in DENIAL_CODES:
            return self._retryable(intent)
        self._clear_retry()
        if intent is None:
            return ProcessingResult('DENIED',None,code)
        audit = record_denial(self.engine,intent.key,code,uow_factory=self.audit_uow)
        # A fresh authorized operational pause prevents an endless denial loop.
        # It changes only this still-unaccepted work, never any business source.
        try:
            with self._uow(resolve=True) as uow:
                work = self._work(uow,intent)
                if work is not None and work['state'] == 'PENDING':
                    head,state,grant = self._context(uow,intent,work)
                    self.guard._allowed(uow,head,state,'PROPOSAL')
                    self._empty_attempt(uow,intent)
                    uow.execute(update(t.work).where(t.work.c.work_id==intent.work_id).values(state='PAUSED'))
                    revision = grant['revision']
                    sealed = {**work,'state':'PAUSED'}
                    def recheck():
                        actual = self._work(uow,intent)
                        h,s,g = self._context(uow,intent,actual)
                        self.guard._allowed(uow,h,s,'PROPOSAL')
                        self._empty_attempt(uow,intent)
                        if g['revision'] != revision or h['case_version'] != head['case_version'] or dict(actual) != sealed:
                            reject(uow)
                    uow.before_commit(recheck)
                uow.commit()
        except Exception:
            pass
        return ProcessingResult('DENIED',intent.work_id,code,audit)

    def run_once(self):
        # A retryable rollback never parks durable work forever or spins hot.
        # The delay is local scheduling metadata, not a replacement work identity.
        if self._retry_after is not None and self.clock() < self._retry_after:
            return False
        self._retry_after = None
        if self._retry_intent is not None:
            intent = self._retry_intent
            self._retry_intent = None
            result = self.resolve(intent)
            return bool(self.process(intent)) if result.status=='PENDING' else bool(result)
        if self._uncertain is not None:
            intent = self._uncertain
            result = self.resolve(intent)
            if result.status == 'PENDING':
                return bool(self.process(intent))
            # Proven absence is returned, not automatically replaced in this call.
            return bool(result)
        with self._uow(resolve=True) as uow:
            row = uow.execute(select(old.case_heads).join(old.principals,and_(
                old.principals.c.principal_id==old.case_heads.c.owner_principal_id,
                old.principals.c.store_id==old.case_heads.c.store_id,
                old.principals.c.role=='CUSTOMER',old.principals.c.enabled.is_(True)))
                .join(t.authorities,and_(
                t.authorities.c.store_id==old.case_heads.c.store_id,
                t.authorities.c.component_id==COMPONENT,t.authorities.c.purpose=='PROPOSAL'))
                .outerjoin(t.state,t.state.c.case_id==old.case_heads.c.case_id)
                .outerjoin(t.work,and_(t.work.c.case_id==old.case_heads.c.case_id,
                    t.work.c.component_id==COMPONENT,t.work.c.purpose=='PROPOSAL',
                    t.work.c.generation==t.state.c.generation))
                .where(old.case_heads.c.available.is_(True),old.case_heads.c.status=='POLICY_ASSESSMENT',
                    t.authorities.c.enabled.is_(True),or_(t.work.c.work_id.is_(None),and_(
                        t.work.c.state=='PENDING',t.work.c.authority_revision==t.authorities.c.revision)))
                .order_by(old.case_heads.c.updated_at,old.case_heads.c.case_id).limit(1)).mappings().one_or_none()
            uow.commit()
        if row is None:
            return False
        intent = self.prepare(row['case_id'])
        return bool(self.process(intent)) if type(intent) is Intent else bool(intent)
