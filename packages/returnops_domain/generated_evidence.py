"""Typed generated-output resolver and nonrecursive immutable certificate proof.

The reserved namespace never falls back to customer uploads. This verifier
reads actual rows; it accepts neither a caller-supplied manifest nor grant.
"""
from dataclasses import dataclass
from hashlib import sha256
import re
from sqlalchemy import select,text,or_
from . import customer_tables as old,founder_tables as founder,founder_codec as finite,lifecycle_tables as life
from .canonical import digest,decode_document
from .audit import timestamp
from .errors import FlowError
from .lifecycle_state import reject
from .lifecycle_schema import ARTIFACT, ARTIFACT_VERSIONS,version
from .label_artifact_tables import artifacts,contents,controls,claims,GENERATED_PATTERN
from .manual_target import one

def is_generated_id(value):
    return type(value) is str and re.fullmatch(GENERATED_PATTERN,value,re.ASCII) is not None

def namespace_active(uow):
    """The reserved namespace starts at exact0013, never retroactively at0012."""
    from .lifecycle_schema import LEGACY,REVIEW,APPROVAL_VERSIONS
    from .lifecycle_state import LEGACY_REVISIONS
    connection=uow if hasattr(uow,'dialect') else uow.connection
    revisions=connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if len(revisions)==1 and revisions[0] in (set(LEGACY_REVISIONS)|{LEGACY,REVIEW,*APPROVAL_VERSIONS})-ARTIFACT_VERSIONS:
        return False
    if len(revisions)==1 and revisions[0] in ARTIFACT_VERSIONS and version(connection)==revisions[0]:return True
    if hasattr(uow,'poison'):uow.poison()
    raise FlowError('INVALID_STATE')

def is_generated_resource(uow,value):
    return is_generated_id(value) and namespace_active(uow)

@dataclass(frozen=True,slots=True,repr=False)
class GeneratedEvidenceScope:
    evidence_id: str
    case_id: str
    store_id: str
    owner_id: str
    available: bool

def scope_hint(uow,evidence_id):
    """Untrusted routing metadata for F.03; never a content/provenance grant.

    Missing identities return None. The authorized caller must invoke resolve
    before using this resource, and compare that proof to the authorized scope.
    """
    from .label_execution_tables import artifact_work,controls as labels
    if not is_generated_resource(uow,evidence_id):return None
    row=uow.execute(select(artifacts.c.evidence_id,labels.c.case_id,labels.c.store_id,
        labels.c.owner_id,artifacts.c.available).join(artifact_work,artifacts.c.work_id==artifact_work.c.work_id)
        .join(labels,artifact_work.c.control_id==labels.c.control_id).where(artifacts.c.evidence_id==evidence_id,
            artifact_work.c.case_id==labels.c.case_id,artifact_work.c.operation_id==labels.c.operation_id)).mappings().one_or_none()
    return None if row is None else GeneratedEvidenceScope(**dict(row))

@dataclass(frozen=True,slots=True,repr=False)
class GeneratedEvidenceSnapshot:
    evidence_id: str
    case_id: str
    store_id: str
    owner_id: str
    available: bool
    media_type: str
    content: bytes | None

def _body(uow,record,finite_body=False):
    raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==record['record_id'])).scalar_one_or_none()
    if record['retention_state']=='AVAILABLE':
        if raw is None:reject(uow)
        body=finite.decode_document(raw) if finite_body else decode_document(raw)
        if (finite.digest(body) if finite_body else digest(body,'history/v1'))!=record['content_sha256']:reject(uow)
        return body
    if raw is not None:reject(uow)
    return None

def verify_certificate(uow,evidence_id,*,proof=None):
    from .label_artifact_sources import (ids,profile_hash,source_rows,source_hash,validate_control,
        claim_hash,COMPONENT,original_pdf_fields,FILENAME,MAX_PDF_BYTES)
    from .label_pdf_validation import verify_label_pdf
    from .label_artifact_history import (origin_payload,completion_core,certificate,evidence_body,result_body)
    if not is_generated_id(evidence_id) or version(uow.connection) not in ARTIFACT_VERSIONS:reject(uow)
    if uow.execute(select(old.evidence.c.evidence_id).where(old.evidence.c.evidence_id==evidence_id)).first():reject(uow)
    row=one(uow,artifacts,evidence_id=evidence_id)
    work,label,fact=source_rows(uow,row['work_id']);control=one(uow,controls,work_id=row['work_id'])
    validate_control(uow,control)
    claim=one(uow,claims,claim_id=row['completion_claim_id'])
    if (row['evidence_id']!=ids(row['work_id'])['evidence_id'] or control['completed_evidence_id']!=evidence_id
            or control['state'] not in {'DONE','RETAINED'} or control['active_claim_id'] is not None
            or claim['work_id']!=row['work_id'] or claim['claim_hash']!=claim_hash(claim)
            or claim['principal_id']!=label['principal_id'] or claim['source_manifest_hash']!=row['source_manifest_hash']
            or claim['recovery_binding_hash']!=control['recovery_binding_hash']
            or not claim['issued_at']<=row['completed_at']<claim['lease_expires_at']):reject(uow)
    core=decode_document(row['core']);cert=decode_document(row['certificate'])
    if (row['core_hash']!=digest(core,'label-artifact-completion-core/v1')
            or row['completion_hash']!=digest(cert,'label-artifact-completion/v1')
            or core.get('profile')!='label-artifact-completion-core/v1'
            or cert!={'profile':'label-artifact-completion/v1','core':core,
                'evidence_origin':{'event_id':row['evidence_audit_id'],'event_hash':row['evidence_audit_hash']},
                'result_origin':{'event_id':row['result_audit_id'],'event_hash':row['result_audit_hash']}}):reject(uow)
    head=one(uow,old.case_heads,case_id=label['case_id'])
    if proof is None:
        from .founder_integrity import CaseProof
        proof=CaseProof(uow,head)
    if proof.head!=head:reject(uow)
    erecord=one(uow,old.history,record_id=row['evidence_record_id'])
    rrecord=one(uow,old.history,record_id=row['result_record_id'])
    for record,kind,object_id,revision in ((erecord,'EVIDENCE',evidence_id,1),(rrecord,'OPERATION',label['operation_id'],4)):
        if (record['case_id']!=head['case_id'] or record['kind']!=kind or record['object_id']!=object_id
                or record['object_version']!=revision or record['case_version']!=row['completed_case_version']
                or record['recorded_at']!=row['completed_at']):reject(uow)
    if (rrecord['recorded_sequence']!=erecord['recorded_sequence']+1
            or row['completed_case_version']!=claim['claimed_case_version'] or row['completed_case_version']>head['case_version']):reject(uow)
    events=[]
    for record,slot,name in ((erecord,'EVIDENCE','evidence'),(rrecord,'RESULT','result')):
        found=[e for e in proof.events if e['event_id']==row[name+'_audit_id']]
        if len(found)!=1:reject(uow)
        event=found[0];ref={n:record[n] for n in ('record_id','kind','object_id','object_version')}
        if (event['event_hash']!=row[name+'_audit_hash'] or event['actor']!={'kind':'SERVICE','component_id':COMPONENT}
                or event['event_type']!=('GENERATED_LABEL_EVIDENCE_BOUND' if slot=='EVIDENCE' else 'OPERATION_REVISION_RECORDED')
                or event['history_refs']!=[ref] or event['object_ids']!=[record['object_id']]
                or event['case_version']!=row['completed_case_version'] or event['occurred_at']!=timestamp(row['completed_at'])
                or event['payload_hash']!=digest(origin_payload(core,slot),'audit-payload/v1')):reject(uow)
        events.append(event)
    if proof.events.index(events[1])!=proof.events.index(events[0])+1 or events[0]['correlation_id']!=events[1]['correlation_id']:reject(uow)
    eb=_body(uow,erecord);rb=_body(uow,rrecord,True)
    encoding=one(uow,founder.encodings,record_id=rrecord['record_id'])
    if encoding!=dict(record_id=rrecord['record_id'],profile=finite.PROFILE,source_content_sha256=rrecord['content_sha256'],
        projected_content_sha256=rrecord['content_sha256'],receipt_id=None):reject(uow)
    if uow.execute(select(founder.encodings.c.record_id).where(founder.encodings.c.record_id==erecord['record_id'])).first():reject(uow)
    immutable={n:row[n] for n in ('evidence_id','work_id','completion_id','completion_claim_id','source_manifest_hash','profile_hash',
        'sha256','size_bytes','media_type','filename','evidence_record_id','result_record_id','completed_case_version')}
    expected_core=dict(profile='label-artifact-completion-core/v1',**immutable,
        original_control_id=label['control_id'],original_operation_id=label['operation_id'],
        original_confirmation_record_id=label['confirmation_record_id'],original_binding_hash=label['binding_hash'],
        original_ledger_hash=fact['fact_hash'],claim_hash=claim['claim_hash'],case_id=label['case_id'],
        store_id=label['store_id'],owner_id=label['owner_id'],evidence_content_hash=erecord['content_sha256'],
        result_content_hash=rrecord['content_sha256'],completed_at=timestamp(row['completed_at']))
    if (core!=expected_core or any(row[n]!=v for n,v in ids(row['work_id']).items())
            or row['source_manifest_hash']!=source_hash(uow,row['work_id']) or row['profile_hash']!=profile_hash()
            or row['media_type']!='application/pdf' or row['filename']!=FILENAME):reject(uow)
    raw=uow.execute(select(contents.c.body).where(contents.c.evidence_id==evidence_id)).scalar_one_or_none()
    if row['available']:
        if (row['retention_state']!='AVAILABLE' or row['removal_reason'] is not None
                or control['state']!='DONE' or row['pdf_retention_receipt'] is not None
                or row['source_withdrawal_receipt'] is not None or control['source_withdrawal_receipt'] is not None
                or not label['source_available'] or not label['confirmation_retained']
                or raw is None or eb is None or rb is None or not 1<=len(raw)<=MAX_PDF_BYTES
                or len(raw)!=row['size_bytes'] or sha256(bytes(raw)).hexdigest()!=row['sha256']):
            reject(uow)
        try:verify_label_pdf(bytes(raw),original_pdf_fields(fact))
        except ValueError:reject(uow)
    else:
        if raw is not None or eb is not None or row['retention_state']=='AVAILABLE':reject(uow)
        from .label_artifact_retention import verify_retention
        verify_retention(uow,row,control,proof)
    if row['source_withdrawal_receipt'] is None:
        confirmed=one(uow,old.history,record_id=label['confirmation_record_id'])
        cb=_body(uow,confirmed,True)
        if cb is None or rb!=result_body(cb,evidence_id,fact,row['completed_at']):reject(uow)
        if row['available'] and eb!=evidence_body(work['work_id'],label['case_id'],bytes(raw),row['completed_at']):reject(uow)
    elif rb is not None:reject(uow)
    from .label_artifact_history import effect_values
    effect_identity={n:label[n] for n in ('operation_id','case_id','command_id','approval_id','proposal_id',
        'proposal_version','input_version','provider_id','operation_fingerprint')}
    effect_identity.update(idempotency_key=label['effect_key'],status='SUCCEEDED',result={'label_evidence_id':evidence_id})
    if one(uow,life.effects,operation_id=label['operation_id'])!=effect_values(label,effect_identity,rrecord,row['sha256']):reject(uow)
    record_ids=[erecord['record_id'],rrecord['record_id']]
    if (uow.execute(select(life.sources.c.record_id).where(life.sources.c.record_id.in_(record_ids))).first()
            or uow.execute(select(life.events.c.event_id).where(life.events.c.record_id.in_(record_ids))).first()):reject(uow)
    return dict(row=row,core=core,certificate=cert,work=work,label=label,fact=fact,claim=claim,
        evidence_record=erecord,result_record=rrecord,evidence_body=eb,result_body=rb,
        content=None if raw is None else bytes(raw),head=head)

def resolve(uow,evidence_id):
    seal=verify_certificate(uow,evidence_id)
    row,label=seal['row'],seal['label']
    return GeneratedEvidenceSnapshot(evidence_id,label['case_id'],label['store_id'],label['owner_id'],
        row['available'],row['media_type'],seal['content'])

def validate_generated_origin(uow,proof,record,event):
    if not is_generated_id(record['object_id']):reject(uow)
    seal=verify_certificate(uow,record['object_id'],proof=proof)
    if seal['evidence_record']!=record or event['event_id']!=seal['row']['evidence_audit_id']:reject(uow)

def partition_evidence(uow,proof):
    generated=[];customer=[]
    for record in proof.revisions.values():
        if record['kind']!='EVIDENCE':continue
        if is_generated_resource(uow,record['object_id']):
            seal=verify_certificate(uow,record['object_id'],proof=proof)
            if seal['evidence_record']!=record:reject(uow)
            generated.append(record)
        else:
            origin=proof.origin(record)
            if origin['event_type'] not in {'CUSTOMER_CASE_ACCEPTED','CUSTOMER_CLARIFICATION_ACCEPTED'}:reject(uow)
            customer.append(record)
    return customer,generated
