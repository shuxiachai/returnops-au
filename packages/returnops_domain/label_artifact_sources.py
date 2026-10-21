"""Current artifact capability and immutable original-label identities.

Historical business authorization is independently proved by the 0013 aggregate.
Saved grants and the old create-label permission never authorize this component.
"""
from datetime import datetime
from hashlib import sha256
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import digest,decode_document
from .lifecycle_schema import ARTIFACT, ARTIFACT_VERSIONS, version
from .lifecycle_sources import authority
from .lifecycle_state import reject, MAX_VERSION
from .manual_target import one
from .approval_admission_sources import session_bounds, check_session_time
from .label_execution_tables import controls as labels, ledger, artifact_work
from .label_execution_sources import database_now, CONFIG, control_identity, verify_fact
from .label_artifact_tables import permissions, controls, claims, artifacts, contents
from .label_pdf import PDF_PROFILE_ID, MAX_PDF_BYTES, LabelPdfFields, pdf_profile_spec, render_label_pdf

COMPONENT = 'operations-label-artifact-v1'
FILENAME = 'simulated-return-label.pdf'

def profile_hash():
    return digest(canonical_rows(pdf_profile_spec()), 'label-artifact-pdf-profile/v1')

def ids(work_id):
    return {name:prefix+digest({'artifact_work_id':work_id}, domain) for name,prefix,domain in (
        ('evidence_id','glabel_','label-artifact-identity/v1'),
        ('completion_id','lac_','label-artifact-completion-id/v1'),
        ('evidence_record_id','lae_','label-artifact-evidence-record/v1'),
        ('result_record_id','lar_','label-artifact-result-record/v1'))}

def canonical_rows(value):
    if isinstance(value,datetime): return timestamp(value)
    if isinstance(value,(bytes,bytearray,memoryview)): return {'bytes_sha256':sha256(bytes(value)).hexdigest(),'size':len(value)}
    if isinstance(value,dict): return {str(k):canonical_rows(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [canonical_rows(v) for v in value]
    return value

def hash_rows(value, domain):
    return digest(canonical_rows(value),domain)

def authorize(uow, callback, case_id, *, store, lock_rows=True):
    if type(lock_rows) is not bool or (not lock_rows and getattr(uow, 'write', None) is not False):
        reject(uow)
    if version(uow.connection) not in ARTIFACT_VERSIONS: reject(uow)
    actor=callback(uow.connection,'getSession')
    if actor.role!='FOUNDER': reject(uow,'FORBIDDEN')
    if callback(uow.connection,'getFounderCase',case_id)!=actor: reject(uow,'UNAUTHENTICATED')
    head=one(uow,old.case_heads,case_id=case_id)
    if not head['available'] or head['store_id']!=actor.store_id: reject(uow,'NOT_FOUND')
    grant=dict(authority(uow,head,COMPONENT,'EFFECT',lock_rows=lock_rows))
    p=uow.execute(select(permissions).where(permissions.c.store_id==head['store_id'],
        permissions.c.component_id==COMPONENT,permissions.c.provider_id==CONFIG['provider_id'],
        permissions.c.config_id==CONFIG['config_id'],permissions.c.pdf_profile_id==PDF_PROFILE_ID)).mappings().one_or_none()
    if p is None or p['profile_hash']!=profile_hash() or not p['read_existing_enabled'] or store and not p['store_enabled']:
        reject(uow,'FORBIDDEN')
    bounds=session_bounds(uow,actor);check_session_time(database_now(uow),bounds)
    return actor,head,grant,dict(p),bounds

def source_rows(uow, work_id):
    work=one(uow,artifact_work,work_id=work_id)
    label=one(uow,labels,control_id=work['control_id'])
    fact=one(uow,ledger,effect_key=label['effect_key'])
    verify_fact(uow,label,fact)
    if (work['case_id']!=label['case_id'] or work['operation_id']!=label['operation_id']
            or fact['status']!='SUCCEEDED' or label['confirmed_effect_status']!='SUCCEEDED'
            or work['confirmed_ledger_hash']!=fact['fact_hash'] or label['confirmed_ledger_hash']!=fact['fact_hash']
            or work['provider_label_id']!=fact['provider_label_id'] or work['parcel_id']!=fact['parcel_id']
            or work['confirmation_record_id']!=label['confirmation_record_id']
            or work['binding_hash']!=label['binding_hash']): reject(uow)
    return work,label,fact

def verify_original_statement_physical(uow,case_id):
    """Check the real immutable storage source, not only its history copy.

    The stable result contains identity/metadata only. A lawful tombstone
    requires absence of both physical and history bytes and is never decoded.
    """
    from .storage import case_records,original_statement_records,original_statement_contents
    original=one(uow,original_statement_records,case_id=case_id)
    initial=one(uow,case_records,case_id=case_id)
    head=one(uow,old.case_heads,case_id=case_id)
    history=uow.execute(select(old.history).where(old.history.c.case_id==case_id,
        old.history.c.kind=='STATEMENT',old.history.c.object_id==original['statement_id'],
        old.history.c.object_version==1)).mappings().one_or_none()
    if (history is None or original['kind']!='ORIGINAL' or original['object_version']!=1
            or original['accepted_case_version']!=history['case_version']
            or original['accepted_case_version']!=initial['case_version']
            or original['accepted_input_version']!=initial['input_version']
            or original['submitted_at']!=history['recorded_at']
            or initial['owner_principal_id']!=head['owner_principal_id'] or initial['store_id']!=head['store_id']):reject(uow)
    content=uow.execute(select(original_statement_contents).where(
        original_statement_contents.c.statement_id==original['statement_id'])).mappings().one_or_none()
    raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==history['record_id'])).scalar_one_or_none()
    if history['retention_state']=='AVAILABLE':
        if content is None or raw is None:reject(uow)
        body=decode_document(raw)
        if (digest(body,'history/v1')!=history['content_sha256'] or body!=dict(statement_id=original['statement_id'],
                kind='ORIGINAL',raw_text=bytes(content['raw_text']).decode('utf-8','surrogatepass'),
                requested_outcome=content['requested_outcome'],submitted_at=timestamp(original['submitted_at']))):reject(uow)
    elif content is not None or raw is not None:reject(uow)
    return dict(statement_id=original['statement_id'],record_hash=hash_rows(original,'label-artifact-original-statement-metadata/v1'),
        initial_case_hash=hash_rows(initial,'label-artifact-initial-case/v1'),history_record_id=history['record_id'],
        history_content_hash=history['content_sha256'])

def source_manifest(uow, work_id):
    work,label,fact=source_rows(uow,work_id)
    from .return_execution_tables import controls as returns
    returned=one(uow,returns,preparation_id=label['return_preparation_id'])
    names=('first_record_id','dispatch_record_id','confirmation_record_id','return_record_id','approval_record_id')
    records=[one(uow,old.history,record_id=label[n]) for n in names]
    if any(r['case_id']!=label['case_id'] for r in records): reject(uow)
    acceptance=one(uow,old.acceptances,acceptance_id=label['approval_acceptance_id'])
    proposal=uow.execute(select(old.history).where(old.history.c.case_id==label['case_id'],
        old.history.c.kind=='PROPOSAL',old.history.c.object_id==label['proposal_id'],
        old.history.c.object_version==label['proposal_version'])).mappings().one_or_none()
    if proposal is None:reject(uow)
    approval_binding=one(uow,life.sources,record_id=label['approval_record_id'])
    review=one(uow,old.history,record_id=approval_binding['target_record_id'])
    approval=records[-1]
    decision=uow.execute(select(old.history).where(old.history.c.case_id==label['case_id'],
        old.history.c.recorded_sequence==approval['recorded_sequence']-1,old.history.c.kind=='DECISION')).mappings().one_or_none()
    if decision is None or review['kind']!='REVIEW':reject(uow)
    records.extend([dict(proposal),dict(review),dict(decision),
        one(uow,old.history,record_id=returned['first_record_id']),
        one(uow,old.history,record_id=returned['dispatch_record_id'])])
    inputs=list(uow.execute(select(old.history).where(old.history.c.case_id==label['case_id'],
        old.history.c.kind.in_(['STATEMENT','EVIDENCE']),old.history.c.recorded_sequence<proposal['recorded_sequence'])
        .order_by(old.history.c.recorded_sequence)).mappings())
    records.extend(dict(r) for r in inputs)
    all_ids={r['record_id'] for r in records}
    events=[]
    for saved in uow.execute(select(old.audit).where(old.audit.c.case_id==label['case_id']).order_by(old.audit.c.sequence)).mappings():
        event=decode_document(saved['body'])
        if (event['event_type'] in {'CUSTOMER_CASE_ACCEPTED','CUSTOMER_CLARIFICATION_ACCEPTED','PROPOSAL_ACCEPTED',
                'RISK_REVIEW_ACCEPTED','FOUNDER_DECISION_ACCEPTED','FOUNDER_APPROVAL_ISSUED','OPERATION_REVISION_RECORDED'}
                and any(ref['record_id'] in all_ids for ref in event['history_refs'])):
            events.append({'event_id':saved['event_id'],'event_hash':saved['event_hash']})
    source_facts=[]
    for record in (proposal,review,approval):
        binding=one(uow,life.sources,record_id=record['record_id'])
        receipt=one(uow,life.events,record_id=record['record_id'])
        producer=one(uow,life.work,work_id=binding['work_id'])
        source_facts.append({'binding':hash_rows(binding,'label-artifact-original-binding/v1'),
            'receipt':hash_rows(receipt,'label-artifact-original-receipt/v1'),
            'producer':hash_rows(producer,'label-artifact-original-producer/v1')})
    return dict(profile='label-artifact-original-source/v1',work_id=work_id,
        original_statement=verify_original_statement_physical(uow,label['case_id']),
        label_binding_hash=label['binding_hash'],return_binding_hash=returned['binding_hash'],
        confirmation_audit_id=label['confirmation_audit_id'],label_ledger_hash=fact['fact_hash'],
        approval_acceptance_hash=hash_rows(acceptance,'label-artifact-original-acceptance/v1'),
        origins=events,accepted_source_facts=source_facts,
        original_inputs=[{n:r[n] for n in ('record_id','kind','object_id','object_version','content_sha256')} for r in inputs],
        records=[{n:r[n] for n in ('record_id','case_id','kind','object_id','object_version','case_version','content_sha256')}
                 for r in records])

def source_hash(uow, work_id):
    return digest(source_manifest(uow,work_id),'label-artifact-source-manifest/v1')

def binding_hash(work_id, manifest_hash):
    return digest(dict(work_id=work_id,source_manifest_hash=manifest_hash,profile_hash=profile_hash()),
                  'label-artifact-recovery-binding/v1')

def claim_hash(row):
    return hash_rows({n:v for n,v in row.items() if n!='claim_hash'},'label-artifact-claim/v1')

def closure(uow, case_id):
    from .label_execution_sources import closure as original_closure
    result=original_closure(uow,case_id)
    work_ids=select(artifact_work.c.work_id).where(artifact_work.c.case_id==case_id)
    evidence_ids=select(artifacts.c.evidence_id).where(artifacts.c.work_id.in_(work_ids))
    for table,predicate in ((controls,controls.c.work_id.in_(work_ids)),(claims,claims.c.work_id.in_(work_ids)),
        (artifacts,artifacts.c.work_id.in_(work_ids)),(contents,contents.c.evidence_id.in_(evidence_ids))):
        result[table.name]=[dict(r) for r in uow.execute(select(table).where(predicate).order_by(*table.primary_key.columns)).mappings()]
    return result

def capture_current_artifact_context_0013(uow, head):
    from .label_execution_sources import closure as original_closure
    state=one(uow,life.state,case_id=head['case_id'])
    return dict(claimed_case_version=head['case_version'],claimed_input_version=head['input_version'],
        claimed_generation=state['generation'],claimed_head_hash=hash_rows(head,'label-artifact-current-head/v1'),
        claimed_source_snapshot_hash=hash_rows(original_closure(uow,head['case_id']),'label-artifact-current-source/v1'))

def verify_original_label_source_0013(uow, actor, head, work_id, original_key):
    work,label,fact=source_rows(uow,work_id)
    control_identity(uow,actor,head,label,original_key)
    from .execution_artifact_chain_sources import return_continuation
    from .return_execution_tables import controls as returns
    returned=one(uow,returns,execution_work_id=label['execution_work_id'])
    root=return_continuation(uow,actor,head,returned,original_key)
    return dict(work=work,label=label,fact=fact,returned=returned,root=root)

def validate_control(uow, row):
    expected_hash=source_hash(uow,row['work_id'])
    if (row['source_manifest_hash']!=expected_hash or row['profile_hash']!=profile_hash()
            or row['recovery_binding_hash']!=binding_hash(row['work_id'],expected_hash)):
        reject(uow)
    if (row['state'] in {'PENDING','RUNNING'} and (row['completed_evidence_id'] is not None or row['source_withdrawal_receipt'] is not None)
            or row['state']=='DONE' and (row['completed_evidence_id'] is None or row['source_withdrawal_receipt'] is not None)
            or row['state']=='RETAINED' and row['completed_evidence_id'] is None and row['source_withdrawal_receipt'] is None):
        reject(uow)

def current_claim(uow, authorization, ticket, *, compare_context=True):
    actor,head,grant,permission,bounds=authorization
    row=one(uow,controls,work_id=ticket.work_id)
    validate_control(uow,row)
    claim=one(uow,claims,claim_id=ticket.claim_id)
    if (row['state']!='RUNNING' or row['active_claim_id']!=ticket.claim_id or row['epoch']!=ticket.epoch
            or row['source_withdrawal_receipt'] is not None or row['completed_evidence_id'] is not None
            or claim['work_id']!=ticket.work_id or claim['epoch']!=ticket.epoch
            or claim['claim_hash']!=claim_hash(claim) or claim['principal_id']!=actor.principal_id
            or claim['session_id']!=actor.session_id or claim['service_authority_revision']!=grant['revision']
            or claim['artifact_permission_revision']!=permission['revision']
            or claim['source_manifest_hash']!=row['source_manifest_hash']
            or claim['recovery_binding_hash']!=row['recovery_binding_hash']
            or ticket.recovery_binding_hash!=row['recovery_binding_hash']): reject(uow)
    if compare_context:
        expected=capture_current_artifact_context_0013(uow,head)
        if any(claim[n]!=v for n,v in expected.items()): reject(uow)
    now=database_now(uow);check_session_time(now,bounds)
    if now>=claim['lease_expires_at']: reject(uow)
    return row,claim

def original_pdf_fields(fact):
    """Original immutable ledger identifiers; no bytes, rendering or caching."""
    return LabelPdfFields(fact['provider_label_id'],fact['provider_return_id'],fact['parcel_id'])

def expected_pdf(fact):
    # The explicitly authorized T2 retrieval is the only production caller.
    value=render_label_pdf(original_pdf_fields(fact))
    if type(value) is not bytes or not 1<=len(value)<=MAX_PDF_BYTES: raise ValueError('Invalid fixed PDF profile')
    return value
