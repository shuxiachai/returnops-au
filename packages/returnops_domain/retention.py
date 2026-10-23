"""Controlled retention for explicit object IDs, never an HTTP deletion endpoint.

Availability, current bytes, history bodies and receipt copies change together
under the same fence. Acceptance facts, revision identity/order and hashes stay.
Only synthetic data is used by this delivery's tests/demo.
"""
from datetime import datetime,timezone
from sqlalchemy import delete,select,update
from . import customer_tables as t
from .audit import append_event,identifier
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .scope_audit import append_scope_event
from .storage import original_statement_contents
from .wire import validate
from .case_state import retain_content_state
from .investigation_retention import remove_case_payloads

SERVICE={'kind':'SERVICE','component_id':'retention-v1'}

class RetentionService:
    def __init__(self,engine,*,clock=lambda:datetime.now(timezone.utc)):
        self.engine,self.clock=engine,clock

    @staticmethod
    def _receipt_copies(uow,kind,object_id):
        affected=select(t.receipt_refs.c.acceptance_id).where(t.receipt_refs.c.kind==kind,t.receipt_refs.c.object_id==object_id)
        uow.execute(update(t.receipts).where(t.receipts.c.acceptance_id.in_(affected)).values(body=None,available=False))

    def remove(self,kind,object_id,*,reason='RETENTION_POLICY',redact=False):
        if kind not in {'STATEMENT','EVIDENCE'} or reason not in {'RETENTION_POLICY','OWNER_REQUEST'} or type(redact) is not bool:
            raise FlowError('VALIDATION_ERROR')
        validate('Id',object_id)
        with CustomerUnitOfWork(self.engine,write=True) as uow:
            now=self.clock();case_id=None;evidence=None
            from .generated_evidence import is_generated_resource,namespace_active
            artifact_mode=namespace_active(uow)
            if kind=='EVIDENCE' and is_generated_resource(uow,object_id):
                from .label_artifact_retention import remove_pdf
                changed=remove_pdf(uow,object_id,reason,redact,now)
                if changed:
                    from .label_artifact_tables import artifacts
                    from .label_execution_tables import artifact_work
                    case_id=uow.execute(select(artifact_work.c.case_id).join(artifacts,
                        artifacts.c.work_id==artifact_work.c.work_id).where(artifacts.c.evidence_id==object_id)).scalar_one()
                    from .notification_retention import withdraw
                    withdraw(uow,case_id,reason,redact,now)
                uow.commit()
                result=changed
            else:
                result=None
            if result is not None:return result
            record_query=select(t.history).where(t.history.c.kind==kind,t.history.c.object_id==object_id)
            if artifact_mode:record_query=record_query.order_by(t.history.c.recorded_sequence,t.history.c.record_id)
            records=uow.execute(record_query).mappings().all()
            if kind=='EVIDENCE':
                evidence=uow.execute(select(t.evidence).where(t.evidence.c.evidence_id==object_id)).mappings().one_or_none()
                if evidence is None: raise FlowError('NOT_FOUND')
                case_id=evidence['case_id']
            elif not records: raise FlowError('NOT_FOUND')
            else: case_id=records[0]['case_id']
            if any(r['case_id']!=case_id for r in records): raise FlowError('INTERNAL_ERROR')
            prepared=[]
            from .lifecycle_schema import ARTIFACT,version
            if case_id is not None and artifact_mode:
                from .label_artifact_retention import prepare_source_withdrawal
                prepared=prepare_source_withdrawal(uow,case_id,kind,object_id)
            active=[r for r in records if r['retention_state']=='AVAILABLE']
            if not active and (evidence is None or not evidence['available']): uow.commit();return False
            self._receipt_copies(uow,kind,object_id)
            record_ids=[r['record_id'] for r in records]
            if record_ids:
                uow.execute(delete(t.history_contents).where(t.history_contents.c.record_id.in_(record_ids)))
                uow.execute(update(t.history).where(t.history.c.record_id.in_(record_ids),t.history.c.retention_state=='AVAILABLE').values(
                    retention_state='REDACTED' if redact else 'DELETED',removal_reason=reason))
            if kind=='STATEMENT':
                uow.execute(delete(original_statement_contents).where(original_statement_contents.c.statement_id==object_id))
            else:
                uow.execute(delete(t.evidence_contents).where(t.evidence_contents.c.evidence_id==object_id))
                uow.execute(update(t.evidence).where(t.evidence.c.evidence_id==object_id).values(available=False,filename=b'',description=None))
                append_scope_event(uow,'EVIDENCE',object_id,evidence['uploader_id'],evidence['store_id'],action='EVIDENCE_RETAINED_METADATA',
                    actor=SERVICE,payload={'reason':reason,'retention_state':'REDACTED' if redact else 'DELETED'},correlation_id=identifier('corr'),now=now)
            if case_id is not None:
                head=uow.execute(select(t.case_heads).where(t.case_heads.c.case_id==case_id)).mappings().one()
                # A content removal changes the current view but is not new
                # customer input or permission to recreate old accepted content.
                remove_case_payloads(uow,case_id)
                from .lifecycle_state import retain
                retain(uow, head, reason, redact)
                retain_content_state(uow,head,now)
                uow.execute(update(t.intake_work).where(t.intake_work.c.case_id==case_id,t.intake_work.c.state.in_(['PENDING','RUNNING','PAUSED'])).values(
                    state='PAUSED',safe_error='POLICY_OR_CONTENT_UNAVAILABLE'))
                refs=[{'record_id':r['record_id'],'kind':kind,'object_id':object_id,'object_version':r['object_version']} for r in active]
                # One event can reference at most100 revisions; all revisions
                # still get removed atomically, with a minimal object pointer.
                source_event=append_event(uow,case_id,actor=SERVICE,event_type='CUSTOMER_CONTENT_REMOVED',correlation_id=identifier('corr'),
                    payload={'kind':kind,'object_id':object_id,'reason':reason,'revision_count':len(active)},
                    object_ids=[object_id],history_refs=refs[:100],now=now)
                if prepared:
                    from .label_artifact_retention import finish_source_withdrawal
                    finish_source_withdrawal(uow,prepared,kind,object_id,source_event,reason,redact,now)
            uow.commit();return True

    def expire_staged(self,*,limit=20):
        if type(limit) is not int or not 1<=limit<=100: raise FlowError('VALIDATION_ERROR')
        # Selection only; remove rechecks current binding under its own fence.
        with CustomerUnitOfWork(self.engine,write=False) as uow:
            ids=list(uow.execute(select(t.evidence.c.evidence_id).where(t.evidence.c.status=='STAGED',t.evidence.c.available.is_(True),
                t.evidence.c.expires_at<=self.clock()).order_by(t.evidence.c.expires_at,t.evidence.c.evidence_id).limit(limit)).scalars());uow.commit()
        removed=0
        for evidence_id in ids:
            # An expired staged attachment cannot newly bind under CustomerFlow.
            removed+=int(self.remove('EVIDENCE',evidence_id))
        return removed
