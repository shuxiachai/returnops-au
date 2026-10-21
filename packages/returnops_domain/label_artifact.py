"""Explicit private T1 claim / T2 original read / T3 atomic PDF and v4 result.

Recover is a pure observation. Unknown commit/close never produces a ticket,
reclaims, renders, retries a write or replaces an original identity.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from secrets import token_hex
from sqlalchemy import select,update
from . import customer_tables as old,lifecycle_tables as life
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .canonical import digest
from .manual_target import one
from .lifecycle_state import reject,MAX_VERSION
from .lifecycle_sources import Sources
from .wire import validate
from .evidence_validation import validate_evidence
from .label_artifact_tables import controls,claims,artifacts,contents,permissions
from .label_artifact_sources import (authorize,verify_original_label_source_0013,capture_current_artifact_context_0013,
    source_hash,binding_hash,profile_hash,claim_hash,current_claim,closure,original_pdf_fields,ids,database_now,FILENAME,COMPONENT)
from .label_pdf_validation import verify_label_pdf
from .label_artifact_history import (evidence_body,result_body,completion_core,origin_payload,append_record,
    certificate,metadata,effect_values,expected_delta)
from .core_label_artifact_mock import CoreLabelArtifactMock,ArtifactTicket

@dataclass(frozen=True,slots=True,repr=False)
class ArtifactCompletionResult:
    status: str
    operation_id: str | None = None
    operation_state: str | None = None
    artifact_work_id: str | None = None
    label_evidence_id: str | None = None
    result_record_id: str | None = None
    content_available: bool | None = None
    safe_code: str | None = None

class LabelArtifactService:
    def __init__(self,engine,authority,*,uow_factory=CustomerUnitOfWork,mock_factory=CoreLabelArtifactMock):
        self.engine,self.authority,self.uow_factory,self.mock_factory=engine,authority,uow_factory,mock_factory

    @staticmethod
    def _request(case_id,work_id,key,correlation):
        for value in (case_id,work_id,correlation):validate('Id',value)
        validate('IdempotencyKey',key)

    @staticmethod
    def _error(error,phase):
        return ArtifactCompletionResult('UNKNOWN' if phase['commit_possible'] or error.code=='INTERNAL_ERROR' else 'DENIED',safe_code=error.code)

    def _observe(self,uow,source,control):
        label=source['label'];work=source['work']
        if control is not None and control['completed_evidence_id'] is not None:
            from .generated_evidence import verify_certificate
            seal=verify_certificate(uow,control['completed_evidence_id'])
            return ArtifactCompletionResult('REPLAYED',label['operation_id'],'SUCCEEDED',work['work_id'],
                seal['row']['evidence_id'],seal['row']['result_record_id'],seal['row']['available'])
        if control is not None and control['state']=='RETAINED' or not label['source_available']:
            return ArtifactCompletionResult('RETAINED',label['operation_id'],'EXECUTING',work['work_id'],content_available=False)
        active=control is not None and control['state']=='RUNNING'
        if active:
            claim=one(uow,claims,claim_id=control['active_claim_id'])
            active=database_now(uow)<claim['lease_expires_at']
        return ArtifactCompletionResult('IN_PROGRESS' if active else 'PENDING',label['operation_id'],'EXECUTING',work['work_id'])

    def _check_final(self,uow,authorization,source,expected,work_id,key,*,ticket=None,post_head=None,lock_rows=True):
        actor,head,grant,permission,bounds=authorization
        target_head=head if post_head is None else post_head
        fresh=authorize(uow,self.authority,head['case_id'],store=True,lock_rows=lock_rows)
        if fresh!=(actor,target_head,grant,permission,bounds):reject(uow)
        verified=verify_original_label_source_0013(uow,actor,target_head,work_id,key)
        if any(verified[n]!=source[n] for n in ('work','label','fact','returned','root')):reject(uow)
        if closure(uow,head['case_id'])!=expected:reject(uow)
        # Complete slow proof/content reads before last live capability/time.
        if authorize(uow,self.authority,head['case_id'],store=True,lock_rows=lock_rows)!=fresh:reject(uow)
        if ticket is not None:
            claim=one(uow,claims,claim_id=ticket.claim_id)
            from .approval_admission_sources import check_session_time
            now=database_now(uow);check_session_time(now,bounds)
            if now>=claim['lease_expires_at']:reject(uow)

    def _final(self,uow,authorization,source,expected,work_id,key,phase,*,ticket=None,post_head=None):
        uow.before_commit(lambda:self._check_final(uow,authorization,source,expected,work_id,key,
            ticket=ticket,post_head=post_head))
        uow.before_commit(lambda:phase.update(commit_possible=True))

    @staticmethod
    def _running_observation_hint(uow,work_id):
        """An uncommitted routing hint, never a ticket or a business outcome."""
        found=uow.execute(select(controls).where(controls.c.work_id==work_id)).mappings().one_or_none()
        if found is None or found['state']!='RUNNING' or found['active_claim_id'] is None:
            return False
        claim=one(uow,claims,claim_id=found['active_claim_id'])
        return database_now(uow)<claim['lease_expires_at']

    @staticmethod
    def _observation_authority_rows(uow,authorization):
        """Fixed read-only tail inputs; no authorization callback or row lock."""
        actor,head,grant,permission,bounds=authorization
        return dict(
            principal=one(uow,old.principals,principal_id=actor.principal_id),
            owner=one(uow,old.principals,principal_id=head['owner_principal_id']),
            session=one(uow,old.sessions,session_id=actor.session_id,principal_id=actor.principal_id),
            head=one(uow,old.case_heads,case_id=head['case_id']),
            grant=one(uow,life.authorities,store_id=head['store_id'],component_id=COMPONENT,purpose='EFFECT'),
            permission=one(uow,permissions,**{column.name:permission[column.name]
                for column in permissions.primary_key.columns}))

    def _observe_running_shared(self,case_id,work_id,key):
        """Fresh shared observation only: no Ticket, write fallback or retry.

        FR-009/010; NFR-002/004/006/009; AH-10/UC-04 governed execution.
        Shared advisory admission is not a raw-connection write sandbox.
        """
        phase={'commit_possible':False}
        try:
            with self.uow_factory(self.engine,write=False) as uow:
                authorization=authorize(uow,self.authority,case_id,store=True,lock_rows=False)
                actor,head,grant,permission,bounds=authorization
                authority_rows=self._observation_authority_rows(uow,authorization)
                before=closure(uow,case_id)
                source=verify_original_label_source_0013(uow,actor,head,work_id,key)
                found=uow.execute(select(controls).where(controls.c.work_id==work_id)).mappings().one_or_none()
                row=None if found is None else dict(found)
                active_claim=(one(uow,claims,claim_id=row['active_claim_id'])
                    if row is not None and row['state']=='RUNNING' and row['active_claim_id'] is not None else None)
                value=self._observe(uow,source,row)
                if value.status=='PENDING':
                    return ArtifactCompletionResult('UNKNOWN')
                self._check_final(uow,authorization,source,before,work_id,key,lock_rows=False)
                # The final raw authorization callback above can mutate this
                # connection. No callback runs after these fixed read checks.
                if self._observation_authority_rows(uow,authorization)!=authority_rows:reject(uow)
                if closure(uow,case_id)!=before:reject(uow)
                current=uow.execute(select(controls).where(controls.c.work_id==work_id)).mappings().one_or_none()
                if (None if current is None else dict(current))!=row:reject(uow)
                if value.status=='IN_PROGRESS':
                    if row is None or row['state']!='RUNNING' or active_claim is None:reject(uow)
                    latest=one(uow,claims,claim_id=row['active_claim_id'])
                    if (latest!=active_claim or latest['claim_id']!=row['active_claim_id']
                            or latest['work_id']!=work_id or latest['epoch']!=row['epoch']):reject(uow)
                from .approval_admission_sources import session_bounds,check_session_time
                if session_bounds(uow,actor)!=bounds:reject(uow,'UNAUTHENTICATED')
                now=database_now(uow);check_session_time(now,bounds)
                if value.status=='IN_PROGRESS' and now>=active_claim['lease_expires_at']:
                    return ArtifactCompletionResult('UNKNOWN')
                phase['commit_possible']=True
                uow.commit()
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return ArtifactCompletionResult('UNKNOWN')

    def complete_label_artifact(self,case_id,artifact_work_id,original_approval_key,correlation_id):
        value=self._claim(case_id,artifact_work_id,original_approval_key,correlation_id)
        if type(value) is ArtifactCompletionResult:return value
        try:reply=self.mock_factory(self.engine).retrieve_original_label(value,self.authority)
        except Exception:return ArtifactCompletionResult('UNKNOWN')
        if reply.status!='FOUND' or type(reply.content) is not bytes:
            if reply.status=='DENIED':self._release(value,reply.safe_code)
            return ArtifactCompletionResult('DENIED' if reply.status=='DENIED' else 'UNKNOWN',safe_code=reply.safe_code)
        return self._complete(value,reply.content,correlation_id)

    def _claim(self,case_id,work_id,key,correlation):
        phase={'commit_possible':False}
        try:
            self._request(case_id,work_id,key,correlation)
            observe_running=False
            with self.uow_factory(self.engine,write=True) as uow:
                authorization=authorize(uow,self.authority,case_id,store=True)
                if self._running_observation_hint(uow,work_id):
                    observe_running=True
                else:
                    actor,head,grant,permission,bounds=authorization
                    source=verify_original_label_source_0013(uow,actor,head,work_id,key)
                    found=uow.execute(select(controls).where(controls.c.work_id==work_id)).mappings().one_or_none()
                    row=None if found is None else dict(found);before=closure(uow,case_id)
                    observed=self._observe(uow,source,row)
                    if observed.status!='PENDING':
                        self._final(uow,authorization,source,before,work_id,key,phase)
                        uow.commit();value=observed
                    else:
                        if not source['label']['confirmation_retained'] or source['root'] is None:reject(uow)
                        additions=[];replacements=[]
                        original=row
                        if row is None:
                            manifest=source_hash(uow,work_id)
                            row=dict(work_id=work_id,source_manifest_hash=manifest,profile_hash=profile_hash(),
                                recovery_binding_hash=binding_hash(work_id,manifest),state='PENDING',epoch=0,
                                active_claim_id=None,completed_evidence_id=None,safe_failure_code=None,source_withdrawal_receipt=None)
                            uow.execute(controls.insert().values(**row));additions.append((controls,row))
                        if row['epoch']>=MAX_VERSION:reject(uow)
                        context=capture_current_artifact_context_0013(uow,head)
                        now=database_now(uow)
                        deadline=min(now+timedelta(seconds=30),datetime.fromtimestamp(bounds[4],timezone.utc))
                        if deadline<=now:reject(uow,'UNAUTHENTICATED')
                        claim=dict(claim_id='laclaim_'+token_hex(16),work_id=work_id,epoch=row['epoch']+1,
                            source_manifest_hash=row['source_manifest_hash'],recovery_binding_hash=row['recovery_binding_hash'],
                            principal_id=actor.principal_id,session_id=actor.session_id,service_authority_revision=grant['revision'],
                            artifact_permission_revision=permission['revision'],**context,issued_at=now,lease_expires_at=deadline)
                        claim['claim_hash']=claim_hash(claim)
                        uow.execute(claims.insert().values(**claim));additions.append((claims,claim))
                        final={**row,'state':'RUNNING','epoch':claim['epoch'],'active_claim_id':claim['claim_id'],'safe_failure_code':None}
                        if uow.execute(update(controls).where(controls.c.work_id==work_id,controls.c.epoch==row['epoch']).values(
                            state='RUNNING',epoch=claim['epoch'],active_claim_id=claim['claim_id'],safe_failure_code=None)).rowcount!=1:reject(uow)
                        if original is None:additions[0]=(controls,final)
                        else:replacements.append((controls,row,final))
                        value=ArtifactTicket(work_id,case_id,key,claim['claim_id'],claim['epoch'],row['recovery_binding_hash'])
                        current_claim(uow,authorization,value)
                        expected=expected_delta(before,additions,replacements,head)
                        self._final(uow,authorization,source,expected,work_id,key,phase,ticket=value)
                        uow.commit()
            # A hint exits the exclusive UoW without commit. Its normal close
            # rolls back even raw callback writes; a close error skips shared.
            if observe_running:
                return self._observe_running_shared(case_id,work_id,key)
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return ArtifactCompletionResult('UNKNOWN')

    def _complete(self,ticket,content,correlation):
        phase={'commit_possible':False}
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                authorization=authorize(uow,self.authority,ticket.case_id,store=True)
                actor,head,grant,permission,bounds=authorization
                source=verify_original_label_source_0013(uow,actor,head,ticket.work_id,ticket.original_key)
                row,claim=current_claim(uow,authorization,ticket)
                before=closure(uow,ticket.case_id)
                try:verify_label_pdf(content,original_pdf_fields(source['fact']))
                except ValueError:reject(uow)
                checked=validate_evidence(content,FILENAME,'application/pdf')
                if checked.content!=content:reject(uow)
                if max(head['history_sequence'],head['audit_sequence'])>MAX_VERSION-2:reject(uow)
                _,confirmed=Sources(uow,head,'operations-label-v1').read(source['label']['confirmation_record_id'],{'OPERATION'})
                now=database_now(uow);stable=ids(ticket.work_id)
                eb=evidence_body(ticket.work_id,ticket.case_id,content,now)
                rb=result_body(confirmed,stable['evidence_id'],source['fact'],now)
                core=completion_core(source['work'],source['label'],claim,eb,rb,head,now)
                er,ee,post,additions=append_record(uow,head,stable['evidence_record_id'],'EVIDENCE',stable['evidence_id'],1,
                    eb,origin_payload(core,'EVIDENCE'),correlation,now)
                rr,re,post,more=append_record(uow,post,stable['result_record_id'],'OPERATION',source['label']['operation_id'],4,
                    rb,origin_payload(core,'RESULT'),correlation,now)
                additions+=more
                meta=metadata(core,certificate(core,ee,re),now)
                body=dict(evidence_id=stable['evidence_id'],body=content)
                effect=effect_values(source['label'],rb,rr,eb['sha256'])
                for table,values in ((artifacts,meta),(contents,body),(life.effects,effect)):
                    uow.execute(table.insert().values(**values));additions.append((table,values))
                final={**row,'state':'DONE','active_claim_id':None,'completed_evidence_id':stable['evidence_id'],'safe_failure_code':None}
                if uow.execute(update(controls).where(controls.c.work_id==ticket.work_id,controls.c.state=='RUNNING',
                    controls.c.epoch==ticket.epoch,controls.c.active_claim_id==ticket.claim_id).values(state='DONE',
                    active_claim_id=None,completed_evidence_id=stable['evidence_id'],safe_failure_code=None)).rowcount!=1:reject(uow)
                expected=expected_delta(before,additions,[(controls,row,final)],post)
                self._final(uow,authorization,source,expected,ticket.work_id,ticket.original_key,phase,ticket=ticket,post_head=post)
                uow.commit()
                value=ArtifactCompletionResult('COMMITTED',source['label']['operation_id'],'SUCCEEDED',ticket.work_id,
                    stable['evidence_id'],stable['result_record_id'],True)
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return ArtifactCompletionResult('UNKNOWN')

    def recover_label_artifact(self,case_id,artifact_work_id,original_approval_key,correlation_id):
        phase={'commit_possible':False}
        try:
            self._request(case_id,artifact_work_id,original_approval_key,correlation_id)
            with self.uow_factory(self.engine,write=False) as uow:
                authorization=authorize(uow,self.authority,case_id,store=False)
                source=verify_original_label_source_0013(uow,authorization[0],authorization[1],artifact_work_id,original_approval_key)
                row=uow.execute(select(controls).where(controls.c.work_id==artifact_work_id)).mappings().one_or_none()
                before=closure(uow,case_id);value=self._observe(uow,source,row)
                fresh=authorize(uow,self.authority,case_id,store=False)
                if fresh!=authorization or closure(uow,case_id)!=before:reject(uow)
                if verify_original_label_source_0013(uow,fresh[0],fresh[1],artifact_work_id,original_approval_key)!=source:reject(uow)
                if authorize(uow,self.authority,case_id,store=False)!=fresh:reject(uow)
                phase['commit_possible']=True;uow.commit()
            return value
        except FlowError as error:return self._error(error,phase)
        except Exception:return ArtifactCompletionResult('UNKNOWN')

    def _release(self,ticket,safe_code):
        phase={'commit_possible':False}
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                authorization=authorize(uow,self.authority,ticket.case_id,store=True)
                source=verify_original_label_source_0013(uow,authorization[0],authorization[1],ticket.work_id,ticket.original_key)
                row,_=current_claim(uow,authorization,ticket);before=closure(uow,ticket.case_id)
                final={**row,'state':'PENDING','active_claim_id':None,'safe_failure_code':'ARTIFACT_UNAVAILABLE'}
                uow.execute(update(controls).where(controls.c.work_id==ticket.work_id,controls.c.active_claim_id==ticket.claim_id).values(
                    state='PENDING',active_claim_id=None,safe_failure_code='ARTIFACT_UNAVAILABLE'))
                self._final(uow,authorization,source,expected_delta(before,[],[(controls,row,final)],authorization[1]),
                    ticket.work_id,ticket.original_key,phase,ticket=ticket)
                uow.commit()
        except Exception:return
