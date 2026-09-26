"""Durable deterministic intake processing, separate from accepted HTTP receipts.

Claims and results use separate fenced transactions. Computation holds no DB
lock. HTTP session expiry does not cancel accepted work; current account, case,
source and receipt authority still apply. Two actual compute failures exhaust
this local processor's budget, independently of A2 operation attempts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Event, Thread
from sqlalchemy import and_, or_, select, update
from . import customer_tables as t
from .audit import append_event, identifier, timestamp
from .canonical import decode_document, encode_document
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .history import append_revision, read_revision
from .storage import original_statement_contents, original_statement_records
from .wire import validate

SERVICE = {"kind":"SERVICE", "component_id":"deterministic-intake-v1"}

@dataclass(frozen=True, repr=False)
class Claim:
    work_id: str
    claim_id: str
    epoch: int
    case_version: int
    input_version: int
    remaining: tuple = field(repr=False)
    question_kinds: dict = field(repr=False)
    has_material: bool

@dataclass(frozen=True)
class IntakeResult:
    needs_purchase_context: bool = False

class IntakeProcessor:
    def __init__(self, engine, *, clock=lambda: datetime.now(timezone.utc), lease_seconds=30,
                 retry_seconds=1, max_failures=2, evaluate=None, uow_factory=CustomerUnitOfWork):
        if not 1 <= lease_seconds <= 300 or not 0 <= retry_seconds <= 60 or not 1 <= max_failures <= 5:
            raise FlowError("INTERNAL_ERROR")
        self.engine,self.clock,self.lease_seconds=engine,clock,lease_seconds
        self.retry_seconds,self.max_failures=retry_seconds,max_failures
        self.evaluate=evaluate or self._evaluate
        self.uow_factory=uow_factory

    def _uow(self, write=True):
        return self.uow_factory(self.engine,write=write,lock_timeout_ms=500)

    @staticmethod
    def _evaluate(claim):
        return IntakeResult(not claim.remaining and claim.input_version == 1 and not claim.has_material)

    def _context(self,uow,work):
        """Recheck SERVICE authority and content, never a stored HTTP grant."""
        head=uow.execute(select(t.case_heads).where(t.case_heads.c.case_id==work['case_id'])).mappings().one_or_none()
        session=uow.execute(select(t.intake_sessions).where(t.intake_sessions.c.case_id==work['case_id'])).mappings().one_or_none()
        if head is None or session is None or session['current_work_id']!=work['work_id'] or head['input_version']!=work['input_version'] or session['input_version']!=work['input_version']:
            return 'STALE',None
        principal=uow.execute(select(t.principals).where(t.principals.c.principal_id==work['accepted_principal_id'])).mappings().one_or_none()
        if (not head['available'] or principal is None or not principal['enabled'] or principal['role']!='CUSTOMER'
            or principal['store_id']!=work['accepted_store_id'] or head['owner_principal_id']!=work['accepted_owner_id']
            or head['store_id']!=work['accepted_store_id'] or work['accepted_owner_id']!=work['accepted_principal_id']):
            return 'BLOCKED',None
        fact=uow.execute(select(t.acceptances).where(t.acceptances.c.acceptance_id==work['acceptance_id'])).mappings().one_or_none()
        receipt=uow.execute(select(t.receipts).where(t.receipts.c.acceptance_id==work['acceptance_id'])).mappings().one_or_none()
        if (fact is None or fact['principal_id']!=principal['principal_id'] or fact['store_id']!=head['store_id']
            or fact['resource_kind']!='CASE' or fact['resource_id']!=head['case_id'] or receipt is None
            or not receipt['available'] or receipt['body'] is None): return 'BLOCKED',None
        # Validate every accepted source and all current bound material. A
        # tombstone/corrupt source never becomes an empty, apparently valid input.
        try:
            body=decode_document(receipt['body']); validate('CustomerCaseView',body,internal=True)
            if body['case_id']!=head['case_id'] or body['input_version']!=work['input_version'] or body['case_version']!=work['accepted_case_version']:
                return 'BLOCKED',None
            for ref in decode_document(work['source_refs']):
                row=uow.execute(select(t.history).where(t.history.c.record_id==ref['record_id'],t.history.c.case_id==head['case_id'])).mappings().one_or_none()
                if row is None or row['retention_state']!='AVAILABLE' or any(row[k]!=ref[k] for k in ('kind','object_id','object_version')): return 'BLOCKED',None
                read_revision(uow,row)
            originals=uow.execute(select(original_statement_contents).join(original_statement_records,
                original_statement_contents.c.statement_id==original_statement_records.c.statement_id).where(original_statement_records.c.case_id==head['case_id'])).mappings().all()
            if len(originals)!=1: return 'BLOCKED',None
            original=originals[0]
            raw=bytes(original['raw_text']).decode('utf-8','surrogatepass')
            if not raw.strip(): return 'BLOCKED',None
            reference=original['original_order_reference']
            has_material=reference is not None and bool(bytes(reference).decode('utf-8','surrogatepass').strip())
            rows=uow.execute(select(t.evidence).where(t.evidence.c.case_id==head['case_id'],t.evidence.c.available.is_(True))).mappings().all()
            for row in rows:
                if row['status']!='BOUND' or row['uploader_id']!=principal['principal_id'] or row['store_id']!=head['store_id']: return 'BLOCKED',None
                content=uow.execute(select(t.evidence_contents.c.body).where(t.evidence_contents.c.evidence_id==row['evidence_id'])).scalar_one_or_none()
                if content is None or len(content)!=row['size_bytes'] or sha256(bytes(content)).hexdigest()!=row['sha256']: return 'BLOCKED',None
                has_material=True
            remaining=[]; kinds={}
            if head['current_question_set_id'] is not None:
                questions=uow.execute(select(t.questions).where(t.questions.c.question_set_id==head['current_question_set_id'],t.questions.c.case_id==head['case_id'])).mappings().one_or_none()
                if questions is None or questions['input_version']!=head['input_version']: return 'BLOCKED',None
                remaining=decode_document(questions['questions']); kinds=decode_document(questions['question_kinds'])
                for q in remaining: validate('ClarificationQuestion',q,internal=True)
                if set(kinds)!={q['question_id'] for q in remaining}: return 'BLOCKED',None
        except (FlowError,KeyError,TypeError,UnicodeError,ValueError):
            return 'BLOCKED',None
        return 'CURRENT',(head,session,remaining,kinds,has_material)

    @staticmethod
    def _block(uow,work,state,now):
        uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==work['work_id']).values(
            state='SUPERSEDED' if state=='STALE' else 'PAUSED',safe_error='STALE_INPUT' if state=='STALE' else 'POLICY_OR_CONTENT_UNAVAILABLE',
            completed_at=now if state=='STALE' else None))

    def claim(self):
        claim=None
        try:
            with self._uow() as uow:
                now=self.clock()
                work=uow.execute(select(t.intake_work).where(or_(
                    and_(t.intake_work.c.state=='PENDING',t.intake_work.c.next_attempt_at<=now),
                    and_(t.intake_work.c.state=='RUNNING',t.intake_work.c.lease_expires_at<=now)))
                    .order_by(t.intake_work.c.created_at,t.intake_work.c.work_id).limit(1)).mappings().one_or_none()
                if work is None: uow.commit(); return None
                state,context=self._context(uow,work)
                if state!='CURRENT': self._block(uow,work,state,now); uow.commit(); return None
                head,session,remaining,kinds,material=context
                claim=Claim(work['work_id'],identifier('claim'),work['claim_epoch']+1,head['case_version'],head['input_version'],tuple(remaining),kinds,material)
                uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==work['work_id']).values(
                    state='RUNNING',claim_id=claim.claim_id,claim_epoch=claim.epoch,claimed_at=now,
                    lease_expires_at=now+timedelta(seconds=self.lease_seconds),safe_error=None))
                uow.execute(update(t.intake_sessions).where(t.intake_sessions.c.case_id==head['case_id']).values(
                    status='EVALUATING',updated_at=now,internal_revision=session['internal_revision']+1))
                uow.commit()
                return claim
        except AcceptanceOutcomeUnknown:
            unknown=True
        if unknown and claim is not None and self._claim_current(claim): return claim
        return None

    def _claim_current(self,claim):
        try:
            with self._uow(False) as uow:
                work=uow.execute(select(t.intake_work).where(t.intake_work.c.work_id==claim.work_id)).mappings().one_or_none()
                current=(work is not None and work['state']=='RUNNING' and work['claim_id']==claim.claim_id
                    and work['claim_epoch']==claim.epoch and work['lease_expires_at']>self.clock())
                uow.commit(); return current
        except (FlowError,AcceptanceOutcomeUnknown): return False

    def finish(self,claim,result=None,*,computation_failed=False):
        """Never count transport/DB uncertainty as a compute failure."""
        try:
            with self._uow() as uow:
                now=self.clock()
                work=uow.execute(select(t.intake_work).where(t.intake_work.c.work_id==claim.work_id)).mappings().one_or_none()
                if work is None: uow.commit(); return False
                if work['state'] in {'DONE','FAILED'}: uow.commit(); return True
                if (work['state']!='RUNNING' or work['claim_id']!=claim.claim_id or work['claim_epoch']!=claim.epoch
                    or work['lease_expires_at']<=now): uow.commit(); return False
                state,context=self._context(uow,work)
                if state!='CURRENT': self._block(uow,work,state,now);uow.commit();return False
                head,session,remaining,kinds,material=context
                if head['case_version']!=claim.case_version or head['input_version']!=claim.input_version:
                    self._block(uow,work,'STALE',now);uow.commit();return False
                if computation_failed:
                    failures=work['failure_count']+1
                    if failures<self.max_failures:
                        uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==work['work_id']).values(
                            state='PENDING',failure_count=failures,next_attempt_at=now+timedelta(seconds=self.retry_seconds),safe_error='PROCESSING_EXCEPTION'))
                        uow.commit();return False
                    self._fail(uow,work,head,session,failures,now)
                else:
                    if type(result) is not IntakeResult: raise FlowError('INTERNAL_ERROR')
                    self._succeed(uow,work,head,session,remaining,kinds,result,now)
                # The fence excludes supported concurrent policy/retention writers;
                # fresh clock still prevents a lease expiring during this tx.
                if work['lease_expires_at']<=self.clock(): raise FlowError('INTERNAL_ERROR')
                uow.commit();return True
        except AcceptanceOutcomeUnknown:
            uncertain=True
        if uncertain:
            return self._completed(claim)
        return False

    def _completed(self,claim):
        try:
            with self._uow(False) as uow:
                row=uow.execute(select(t.intake_work).where(t.intake_work.c.work_id==claim.work_id)).mappings().one_or_none()
                done=row is not None and row['state'] in {'DONE','FAILED'} and row['claim_id']==claim.claim_id and row['claim_epoch']==claim.epoch
                uow.commit();return done
        except (FlowError,AcceptanceOutcomeUnknown): return False

    def _succeed(self,uow,work,head,session,remaining,kinds,result,now):
        question_set_id=head['current_question_set_id']; rounds=session['clarification_round']
        if result.needs_purchase_context and not remaining:
            question={'question_id':identifier('question'),'text':'Please provide an order reference or alternative information showing the purchase.',
                      'reason':'Purchase context is needed for further investigation; it has not yet been verified.'}
            remaining=[question]; question_set_id=identifier('questions'); rounds+=1
            uow.execute(t.questions.insert().values(question_set_id=question_set_id,case_id=head['case_id'],input_version=head['input_version'],
                questions=encode_document(remaining),question_kinds=encode_document({question['question_id']:'PURCHASE_CONTEXT'})))
        status='AWAITING_INFORMATION' if remaining else 'UNDER_INVESTIGATION'
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==head['case_id']).values(
            case_version=head['case_version']+1,status=status,updated_at=now,current_question_set_id=question_set_id,current_failure_id=None))
        uow.execute(update(t.intake_sessions).where(t.intake_sessions.c.case_id==head['case_id']).values(
            status='AWAITING_CLARIFICATION' if remaining else 'COMPLETE',clarification_round=rounds,
            internal_revision=session['internal_revision']+1,updated_at=now))
        append_event(uow,head['case_id'],actor=SERVICE,event_type='CUSTOMER_INTAKE_PROCESSED',correlation_id=identifier('corr'),
            payload={'work_id':work['work_id'],'status':status,'input_version':head['input_version']},
            object_ids=[] if question_set_id is None else [question_set_id],history_refs=[],now=now)
        uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==work['work_id']).values(state='DONE',completed_at=now,safe_error=None))

    def _fail(self,uow,work,head,session,failures,now):
        correlation=identifier('corr'); failure_id=identifier('failure')
        error=FlowError().envelope(correlation);error['error']['retryable']=False
        body={'failure_id':failure_id,'case_id':head['case_id'],'input_version':head['input_version'],
              'stage':'COORDINATOR','error':error,'occurred_at':timestamp(now)}
        validate('ProcessingFailure',body,internal=True)
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==head['case_id']).values(case_version=head['case_version']+1,
            status='ESCALATED',updated_at=now,current_failure_id=failure_id,current_question_set_id=None))
        uow.execute(t.processing_failures.insert().values(failure_id=failure_id,case_id=head['case_id'],input_version=head['input_version'],body=encode_document(body),occurred_at=now))
        ref=append_revision(uow,head['case_id'],'PROCESSING_FAILURE',failure_id,1,body,now)
        append_event(uow,head['case_id'],actor=SERVICE,event_type='CUSTOMER_INTAKE_FAILED',correlation_id=correlation,
            payload={'work_id':work['work_id'],'failure_id':failure_id},object_ids=[failure_id],history_refs=[ref],now=now)
        uow.execute(update(t.intake_sessions).where(t.intake_sessions.c.case_id==head['case_id']).values(status='ESCALATED_FAILURE',
            internal_revision=session['internal_revision']+1,updated_at=now))
        uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==work['work_id']).values(state='FAILED',failure_count=failures,
            completed_at=now,safe_error='PROCESSING_EXCEPTION'))

    def run_once(self):
        claim=self.claim()
        if claim is None: return False
        failed=False;result=None
        try: result=self.evaluate(claim)
        except Exception: failed=True
        # Deliberately outside the exception handler: no raw compute exception
        # chain reaches persistence, responses or ordinary worker logs.
        return self.finish(claim,result,computation_failed=failed)

class IntakeWorker:
    """One polling thread, owned and closed by API lifespan; durable DB truth."""
    def __init__(self,processor,poll_seconds=0.5):
        self.processor=processor;self.poll_seconds=poll_seconds
        self._stop=Event();self._wake=Event();self._thread=None
    def start(self):
        if self._thread is not None: raise FlowError('INTERNAL_ERROR')
        self._thread=Thread(target=self._run,name='returnops-intake',daemon=True);self._thread.start()
    def wake(self): self._wake.set()
    def _run(self):
        while not self._stop.is_set():
            try: progressed=self.processor.run_once()
            except Exception: progressed=False
            if not progressed: self._wake.wait(self.poll_seconds);self._wake.clear()
    def stop(self):
        self._stop.set();self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive(): raise FlowError('INTERNAL_ERROR')
