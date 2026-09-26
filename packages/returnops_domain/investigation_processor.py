"""Durable order investigation: exclusive claim, shared lookup, exclusive accept.

Only a typed PROVIDER_FAILURE spends the provider budget. Runtime composition
loads one immutable synthetic catalogue; query inputs never select authority.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, and_, or_
from . import customer_tables as old, investigation_tables as t
from .audit import identifier, timestamp, append_event
from .canonical import encode_document, decode_document, digest
from .case_state import transition
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .history import append_revision
from .investigation_admission import issue_questions
from .investigation_context import InvestigationClaim, DatabaseOrderResolver, context, claimed
from .investigation_policy import ACTOR, SERVICE_ID
from .mock_orders import MockOrderProvider, load_builtin_catalogue
from .order_ports import OrderLookupError
from .wire import validate

@dataclass(frozen=True, slots=True, repr=False)
class LookupObservation:
    claim: InvestigationClaim
    body: bytes = field(repr=False)
    body_hash: str

class InvestigationProcessor:
    def __init__(self,engine,*,catalogue=None,clock=lambda:datetime.now(timezone.utc),lease_seconds=30,
                 retry_seconds=1,max_failures=2,uow_factory=CustomerUnitOfWork):
        if not 1<=lease_seconds<=300 or not 0<=retry_seconds<=60 or not 1<=max_failures<=5: raise FlowError()
        self.engine,self.catalogue,self.clock=engine,catalogue or load_builtin_catalogue(),clock
        self.lease_seconds,self.retry_seconds,self.max_failures=lease_seconds,retry_seconds,max_failures
        self.uow_factory=uow_factory
        self._pending_observation=None

    def _uow(self,write=True): return self.uow_factory(self.engine,write=write,lock_timeout_ms=500)

    @staticmethod
    def _pause(uow,work,reason,now):
        uow.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(
            state='SUPERSEDED' if reason=='STALE_INPUT' else 'PAUSED',safe_reason=reason,
            completed_at=now if reason=='STALE_INPUT' else None))

    def claim(self):
        result=None
        try:
            with self._uow() as uow:
                now=self.clock()
                work=uow.execute(select(t.work).where(or_(and_(t.work.c.state=='PENDING',t.work.c.next_attempt_at<=now),
                    and_(t.work.c.state=='RUNNING',t.work.c.lease_expires_at<=now)))
                    .order_by(t.work.c.created_at,t.work.c.work_id).limit(1)).mappings().one_or_none()
                if work is None: uow.commit();return None
                reason,current=context(uow,work,self.catalogue.metadata)
                if reason: self._pause(uow,work,reason,now);uow.commit();return None
                head,policy,grant,material,signatures=current
                result=InvestigationClaim(work['work_id'],identifier('claim'),identifier('lookup'),work['epoch']+1,
                    head['case_version'],head['input_version'],*signatures)
                uow.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(state='RUNNING',claim_id=result.claim_id,
                    invocation_id=result.invocation_id,epoch=result.epoch,claimed_case_version=result.case_version,
                    service_signature=result.service_signature,grant_signature=result.grant_signature,
                    lease_expires_at=now+timedelta(seconds=self.lease_seconds),safe_reason=None))
                uow.commit();return result
        except AcceptanceOutcomeUnknown:
            pass
        if result is not None:
            try:
                with self._uow(False) as uow:
                    row=uow.execute(select(t.work).where(t.work.c.work_id==result.work_id)).mappings().one_or_none()
                    confirmed=claimed(row,result,self.clock());uow.commit()
                    return result if confirmed else None
            except (FlowError,AcceptanceOutcomeUnknown): pass
        return None

    def lookup(self,claim):
        """The only provider invocation. No writes or exclusive fence upgrade."""
        with self._uow(False) as uow:
            resolver=DatabaseOrderResolver(uow,claim,self.catalogue.metadata,self.clock)
            work=uow.execute(select(t.work).where(t.work.c.work_id==claim.work_id)).mappings().one_or_none()
            if not claimed(work,claim,self.clock()): raise OrderLookupError('STALE_INPUT')
            # Recheck authority before reading the private candidate reference.
            resolver.resolve(work['case_id'],claim.input_version)
            row=uow.execute(select(t.inputs).where(t.inputs.c.work_id==claim.work_id)).mappings().one()
            request={'case_id':work['case_id'],'input_version':claim.input_version}
            if row['reference'] is not None: request['order_reference']=bytes(row['reference']).decode('utf-8','surrogatepass')
            result=MockOrderProvider(resolver,self.catalogue,service_id=SERVICE_ID).lookup(request)
            resolver.resolve(work['case_id'],claim.input_version)
            body={'request':request,'result':result,
                'catalogue':{key:getattr(self.catalogue.metadata,key) for key in ('format_version','provider_id','dataset_version','provider_version','dataset_sha256')},
                'service_signature':claim.service_signature,'grant_signature':claim.grant_signature}
            observation=LookupObservation(claim,encode_document(body),digest(body,'order-receipt/v1'))
            uow.commit();return observation

    def _discard(self,uow,claim,reason,now):
        if uow.execute(select(t.discarded.c.invocation_id).where(t.discarded.c.invocation_id==claim.invocation_id)).first() is None:
            uow.execute(t.discarded.insert().values(invocation_id=claim.invocation_id,work_id=claim.work_id,claim_id=claim.claim_id,
                epoch=claim.epoch,service_signature=claim.service_signature,grant_signature=claim.grant_signature,
                safe_reason=reason,discarded_at=now))

    def finish(self,observation):
        if type(observation) is not LookupObservation or type(observation.body) is not bytes: raise FlowError()
        claim=observation.claim;body=decode_document(observation.body)
        if digest(body,'order-receipt/v1')!=observation.body_hash: raise FlowError()
        expected_metadata={key:getattr(self.catalogue.metadata,key) for key in ('format_version','provider_id','dataset_version','provider_version','dataset_sha256')}
        if (body.get('catalogue')!=expected_metadata or body.get('service_signature')!=claim.service_signature
                or body.get('grant_signature')!=claim.grant_signature): raise FlowError()
        request=validate('OrderLookupRequest',body['request'],internal=True)
        result=validate('OrderLookupResult',body['result'],internal=True)
        if request['case_id']!=result['case_id'] or request['input_version']!=result['input_version'] or request['input_version']!=claim.input_version:
            raise FlowError()
        try:
            with self._uow() as uow:
                now=self.clock()
                receipt=uow.execute(select(t.receipts).where(t.receipts.c.receipt_id==claim.invocation_id)).mappings().one_or_none()
                if receipt is not None:
                    same=self._same_receipt(receipt,observation);uow.commit();return self._settled(observation,same)
                work=uow.execute(select(t.work).where(t.work.c.work_id==claim.work_id)).mappings().one_or_none()
                if work is None: uow.commit();return self._settled(observation,False)
                if not claimed(work,claim,now): self._discard(uow,claim,'CLAIM_EXPIRED_OR_REPLACED',now);uow.commit();return self._settled(observation,False)
                reason,current=context(uow,work,self.catalogue.metadata)
                if reason is None:
                    head,policy,grant,material,signatures=current
                    if signatures!=(claim.service_signature,claim.grant_signature): reason='AUTHORITY_CHANGED'
                    elif head['case_version']!=claim.case_version: reason='STALE_INPUT'
                if reason:
                    self._pause(uow,work,reason,now);self._discard(uow,claim,reason,now);uow.commit();return self._settled(observation,False)
                if result['case_id']!=work['case_id']: raise FlowError()
                expected={'case_id':work['case_id'],'input_version':work['input_version']}
                if material['reference'] is not None: expected['order_reference']=bytes(material['reference']).decode('utf-8','surrogatepass')
                if request!=expected: raise FlowError()
                uow.execute(t.receipts.insert().values(receipt_id=claim.invocation_id,work_id=work['work_id'],case_id=head['case_id'],
                    input_version=claim.input_version,claim_id=claim.claim_id,epoch=claim.epoch,status=result['status'],
                    body_hash=observation.body_hash,available=True,recorded_at=now))
                uow.execute(t.receipt_contents.insert().values(receipt_id=claim.invocation_id,body=observation.body))
                self._accept(uow,work,head,result,now)
                if work['lease_expires_at']<=self.clock(): raise FlowError()
                uow.commit();return self._settled(observation,True)
        except AcceptanceOutcomeUnknown:
            self._pending_observation=observation
        # Keep the original observation for a caller retry. A missing fact means
        # unresolved/not committed, never a new invocation or new provider call.
        try:
            with self._uow(False) as uow:
                receipt=uow.execute(select(t.receipts).where(t.receipts.c.receipt_id==claim.invocation_id)).mappings().one_or_none()
                confirmed=receipt is not None and self._same_receipt(receipt,observation);uow.commit()
                return self._settled(observation,True) if confirmed else False
        except (FlowError,AcceptanceOutcomeUnknown): return False

    def _settled(self,observation,value):
        if self._pending_observation is observation: self._pending_observation=None
        return value

    @staticmethod
    def _same_receipt(receipt,observation):
        claim=observation.claim;body=decode_document(observation.body)
        return (receipt['case_id']==body['request']['case_id'] and receipt['status']==body['result']['status']
            and receipt['work_id']==claim.work_id and receipt['claim_id']==claim.claim_id and receipt['epoch']==claim.epoch
            and receipt['input_version']==claim.input_version and receipt['body_hash']==observation.body_hash)

    def _accept(self,uow,work,head,result,now):
        status=result['status'];objects=[work['invocation_id']];refs=[]
        if status=='MATCHED':
            snapshot=result['snapshot']
            if snapshot['provider_id']!=self.catalogue.metadata.provider_id: raise FlowError()
            snapshot_hash=digest(snapshot,'accepted-order/v1')
            existing=uow.execute(select(t.projections).where(t.projections.c.case_id==head['case_id'],
                t.projections.c.snapshot_id==snapshot['snapshot_id'],t.projections.c.snapshot_version==snapshot['snapshot_version'])).mappings().one_or_none()
            if existing is not None:
                if existing['snapshot_hash']!=snapshot_hash or not existing['available']: raise FlowError()
                raw=uow.execute(select(t.projection_contents.c.body).where(t.projection_contents.c.projection_id==existing['projection_id'])).scalar_one_or_none()
                if raw is None or decode_document(raw)!=snapshot: raise FlowError()
                projection_id=existing['projection_id'];delta=0
            else:
                projection_id=identifier('projection');delta=1
                uow.execute(t.projections.insert().values(projection_id=projection_id,case_id=head['case_id'],receipt_id=work['invocation_id'],
                    source_input_version=head['input_version'],input_version=head['input_version']+1,snapshot_id=snapshot['snapshot_id'],
                    snapshot_version=snapshot['snapshot_version'],snapshot_hash=snapshot_hash,available=True,accepted_at=now))
                uow.execute(t.projection_contents.insert().values(projection_id=projection_id,body=encode_document(snapshot)))
            transition(uow,head,'ORDER_MATCHED','POLICY_ASSESSMENT',now,input_delta=delta)
            uow.execute(update(t.state).where(t.state.c.case_id==head['case_id']).values(current_projection_id=projection_id,current_block_id=None))
            objects.append(projection_id)
        elif status=='NOT_FOUND':
            question_set_id=issue_questions(uow,head,now)
            transition(uow,head,'ORDER_NOT_FOUND','AWAITING_INFORMATION',now,question_set_id=question_set_id)
            session=uow.execute(select(old.intake_sessions).where(old.intake_sessions.c.case_id==head['case_id'])).mappings().one()
            uow.execute(update(old.intake_sessions).where(old.intake_sessions.c.case_id==head['case_id']).values(
                status='AWAITING_CLARIFICATION',clarification_round=session['clarification_round']+1,
                internal_revision=session['internal_revision']+1,updated_at=now))
            objects.append(question_set_id)
        elif status in {'CONFLICT','AUTHORITY_DENIED'}:
            block_id=identifier('block')
            body={'block_id':block_id,'case_id':head['case_id'],'input_version':head['input_version'],
                'status':status,'message':result['message'],'occurred_at':timestamp(now)}
            validate('OrderLookupBlock',body,internal=True)
            transition(uow,head,'ORDER_BLOCKED','ESCALATED',now)
            uow.execute(t.blocks.insert().values(block_id=block_id,case_id=head['case_id'],input_version=head['input_version'],
                receipt_id=work['invocation_id'],body=encode_document(body)))
            uow.execute(update(t.state).where(t.state.c.case_id==head['case_id']).values(current_block_id=block_id,current_projection_id=None))
            refs.append(append_revision(uow,head['case_id'],'ORDER_LOOKUP_BLOCK',block_id,1,body,now));objects.append(block_id)
        elif status=='PROVIDER_FAILURE':
            failures=work['failure_count']+1
            if failures<self.max_failures:
                uow.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(state='PENDING',failure_count=failures,
                    next_attempt_at=now+timedelta(seconds=self.retry_seconds),safe_reason='PROVIDER_FAILURE'))
                append_event(uow,head['case_id'],actor=ACTOR,event_type='ORDER_LOOKUP_RETRY_RECORDED',correlation_id=identifier('corr'),
                    payload={'work_id':work['work_id'],'receipt_id':work['invocation_id'],'failure_count':failures},
                    object_ids=objects,history_refs=[],now=now)
                return
            failure_id=identifier('failure');correlation=identifier('corr')
            error=FlowError().envelope(correlation);error['error']['retryable']=False
            body={'failure_id':failure_id,'case_id':head['case_id'],'input_version':head['input_version'],
                'stage':'ORDER_LOOKUP','error':error,'occurred_at':timestamp(now)}
            validate('ProcessingFailure',body,internal=True)
            transition(uow,head,'ORDER_FAILED','ESCALATED',now,failure_id=failure_id)
            uow.execute(old.processing_failures.insert().values(failure_id=failure_id,case_id=head['case_id'],input_version=head['input_version'],
                body=encode_document(body),occurred_at=now))
            refs.append(append_revision(uow,head['case_id'],'PROCESSING_FAILURE',failure_id,1,body,now));objects.append(failure_id)
            uow.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(failure_count=failures))
        else: raise FlowError()
        append_event(uow,head['case_id'],actor=ACTOR,event_type='ORDER_INVESTIGATION_ACCEPTED',correlation_id=identifier('corr'),
            payload={'work_id':work['work_id'],'receipt_id':work['invocation_id'],'source_input_version':work['input_version'],'status':status},
            object_ids=objects,history_refs=refs,now=now)
        uow.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(
            state='FAILED' if status=='PROVIDER_FAILURE' else 'DONE',completed_at=now,safe_reason=None))

    def run_once(self):
        if self._pending_observation is not None: return self.finish(self._pending_observation)
        claim=self.claim()
        if claim is None: return False
        observation=None
        try:
            observation=self.lookup(claim)
        except (OrderLookupError,FlowError,AcceptanceOutcomeUnknown):
            pass
        if observation is None:
            # Authority/DB/lease failures are not technical provider outcomes.
            with self._uow() as uow:
                work=uow.execute(select(t.work).where(t.work.c.work_id==claim.work_id)).mappings().one_or_none()
                if claimed(work,claim,self.clock()): self._pause(uow,work,'LOOKUP_CONTEXT_UNAVAILABLE',self.clock())
                uow.commit();return False
        return self.finish(observation)
