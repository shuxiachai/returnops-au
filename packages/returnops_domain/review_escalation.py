"""Private controlled ESCALATE receiver. No default adapter, producer or route.

The server injects trusted code; the caller supplies only case/version/key.
This synthetic adapter contract proves A's receiver, never C or a live model.
Two entries (review, then human manual decision) remain separate transactions.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from sqlalchemy import select, update
from . import customer_tables as old, founder_tables as ft, lifecycle_tables as t
from . import founder_codec as finite
from .audit import append_event
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .lifecycle_events import EscalateReviewAccepted
from .lifecycle_guards import LifecycleGuards
from .lifecycle_state import current, reject
from .manual_target import one
from .review_denial import authorize, record_denial
from .review_sources import (COMPONENT, stable_id, invocation, review_payload,
    accepted_proposal, accepted_review, check_review)
from .wire import validate


@dataclass(frozen=True,repr=False)
class ReviewResult:
    status: str
    receipt: dict | None = None
    safe_code: str | None = None
    audit: str = 'NOT_ATTEMPTED'


class EscalateReviewReceiver:
    def __init__(self,engine,adapter,*,clock=lambda:datetime.now(timezone.utc),
                 uow_factory=CustomerUnitOfWork,recovery_uow=CustomerUnitOfWork,audit_uow=CustomerUnitOfWork):
        if not callable(adapter):
            raise FlowError('VALIDATION_ERROR')
        self.engine,self.adapter,self.clock=engine,adapter,clock
        self.uow_factory,self.recovery_uow,self.audit_uow=uow_factory,recovery_uow,audit_uow
        self.guard=LifecycleGuards(COMPONENT,clock=clock)

    @staticmethod
    def _lookup(uow,head,version,key):
        validate('Version',version);validate('IdempotencyKey',key)
        identity=stable_id('review_work',dict(component=COMPONENT,case_id=head['case_id'],key=key))
        row=uow.execute(select(t.work).where(t.work.c.work_id==identity)).mappings().one_or_none()
        if row is not None and (row['case_id']!=head['case_id'] or row['component_id']!=COMPONENT
                or row['purpose']!='REVIEW' or row['claimed_case_version']!=version
                or row['owner_id']!=head['owner_principal_id'] or row['store_id']!=head['store_id']
                or row['idempotency_key']!=identity):
            reject(uow,'IDEMPOTENCY_CONFLICT')
        return identity,row

    @staticmethod
    def _same_authority(uow,head,grant):
        h,g=authorize(uow,head['case_id'])
        if h['owner_principal_id']!=head['owner_principal_id'] or h['store_id']!=head['store_id'] or dict(g)!=dict(grant):
            reject(uow,'FORBIDDEN')
        return h

    def _replay(self,uow,head,grant,work):
        receipts=uow.execute(select(t.events).where(t.events.c.work_id==work['work_id'])).mappings().all()
        if len(receipts)!=1 or work['state']!='DONE':
            reject(uow)
        receipt=dict(receipts[0])
        seal=accepted_review(uow,head,None,COMPONENT,record_id=receipt['record_id'],current=False)
        if seal['work']!=dict(work) or seal['event']!=receipt:
            reject(uow)
        def check():
            h=self._same_authority(uow,head,grant)
            if accepted_review(uow,h,None,COMPONENT,record_id=receipt['record_id'],current=False)!=seal:
                reject(uow)
            self._same_authority(uow,head,grant)
        uow.before_commit(check)
        return receipt

    def _new(self,uow,head,grant,version,work_id):
        if head['case_version']!=version:
            reject(uow,'STALE_CASE_VERSION')
        state=current(uow,head)
        if state is None:
            reject(uow)
        self.guard._allowed(uow,head,state,'REVIEW')
        proposal=accepted_proposal(uow,head,state,COMPONENT)
        if proposal['event']['case_version']!=head['case_version']:
            reject(uow)
        now=self.clock()
        if now.utcoffset() is None:
            reject(uow)
        self.guard.prepare(uow,head['case_id'],version,EscalateReviewAccepted,now,work_id=work_id)
        uow.execute(update(t.work).where(t.work.c.work_id==work_id).values(idempotency_key=work_id))
        claim=self.guard.claim(uow,work_id,now)
        if claim is None:
            reject(uow)
        work=one(uow,t.work,work_id=work_id)
        request=deepcopy(proposal['body'])
        # Frozen HistoricalProposalBundle allOf references RiskReviewRequest;
        # the existing finite profile explicitly permits this identical shape.
        finite.validate('HistoricalProposalBundle',request)
        context=invocation(work,now)
        review=self.adapter(request,deepcopy(context),stable_id('review',work_id))
        if request!=proposal['body']:
            reject(uow)
        body=dict(review=review,proposal_record_id=proposal['record']['record_id'])
        check_review(uow,body,proposal,work,now)
        record_id=stable_id('review_source',work_id)
        ref=dict(record_id=record_id,kind='REVIEW',object_id=review['review_id'],object_version=1)
        source_hash=finite.digest(body)
        uow.execute(old.history.insert().values(**ref,case_id=head['case_id'],case_version=head['case_version'],
            recorded_sequence=head['history_sequence']+1,recorded_at=now,content_sha256=source_hash,
            retention_state='AVAILABLE',removal_reason=None))
        uow.execute(old.history_contents.insert().values(record_id=record_id,body=finite.encode_document(body)))
        uow.execute(ft.encodings.insert().values(record_id=record_id,profile=finite.PROFILE,
            source_content_sha256=source_hash,projected_content_sha256=source_hash,receipt_id=None))
        uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==head['case_id']).values(history_sequence=head['history_sequence']+1))
        event_id=stable_id('review_event',work_id)
        append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':COMPONENT},
            event_type='RISK_REVIEW_ACCEPTED',correlation_id=event_id,
            payload=review_payload(work,proposal['record'],source_hash),object_ids=[review['review_id']],history_refs=[ref],now=now)
        uow.execute(t.sources.insert().values(record_id=record_id,case_id=head['case_id'],**asdict(claim),
            source_hash=source_hash,target_record_id=proposal['record']['record_id'],slot='PRIMARY',
            order_projection_id=proposal['binding']['order_projection_id']))
        receipt=self.guard.apply(uow,EscalateReviewAccepted(event_id,claim,record_id),now)
        def check():
            h=self._same_authority(uow,head,grant);s=current(uow,h)
            sealed=accepted_review(uow,h,s,COMPONENT)
            if (h['status']!='ESCALATED' or h['case_version']!=version+1
                    or h['input_version']!=head['input_version'] or sealed['proposal']!=proposal
                    or sealed['work']['claim_id']!=claim.claim_id or sealed['work']['epoch']!=claim.epoch
                    or sealed['event']!=receipt or sealed['body']!=body):
                reject(uow)
            final_head=self._same_authority(uow,head,grant)
            final_state=current(uow,final_head)
            if (one(uow,t.work,work_id=work_id)!=sealed['work'] or dict(final_state)!=dict(s)
                    or final_head['status']!='ESCALATED' or final_head['case_version']!=version+1
                    or final_head['input_version']!=head['input_version']
                    or self.clock()>=work['lease_expires_at'] or self.guard.clock()>=work['lease_expires_at']):
                reject(uow)
        uow.before_commit(check)
        return receipt

    def accept(self,case_id,expected_case_version,original_key,correlation_id):
        uow=None;committed=False;code='INTERNAL_ERROR'
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                validate('Id',case_id)
                head,grant=authorize(uow,case_id)
                validate('Id',correlation_id)
                work_id,work=self._lookup(uow,head,expected_case_version,original_key)
                receipt=(self._replay(uow,head,grant,work) if work is not None
                    else self._new(uow,head,grant,expected_case_version,work_id))
                uow.commit();committed=True
            return ReviewResult('ACCEPTED',receipt)
        except AcceptanceOutcomeUnknown:
            return ReviewResult('UNKNOWN')
        except FlowError as error:
            code=error.code
        except Exception:
            pass
        if committed or uow is not None and uow.connection is not None and not uow.connection.closed:
            return ReviewResult('UNKNOWN')
        audit=record_denial(self.engine,case_id,code,self.clock,uow_factory=self.audit_uow)
        return ReviewResult('DENIED',safe_code=code,audit=audit)

    def recover(self,case_id,expected_case_version,original_key):
        try:
            with self.recovery_uow(self.engine,write=True) as uow:
                validate('Id',case_id)
                head,grant=authorize(uow,case_id)
                _,work=self._lookup(uow,head,expected_case_version,original_key)
                if work is None:
                    uow.before_commit(lambda:self._same_authority(uow,head,grant))
                    uow.commit()
                    return ReviewResult('UNKNOWN')
                receipt=self._replay(uow,head,grant,work)
                uow.commit()
            return ReviewResult('ACCEPTED',receipt)
        except FlowError as error:
            return ReviewResult('UNKNOWN',safe_code=error.code)
        except Exception:
            return ReviewResult('UNKNOWN')
