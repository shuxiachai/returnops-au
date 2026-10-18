"""Acyclic certificate, two true origins and an exact atomic completion delta."""
from copy import deepcopy
from hashlib import sha256
from sqlalchemy import update
from . import customer_tables as old, founder_tables as founder, founder_codec as finite
from .audit import append_event, timestamp
from .canonical import digest, encode_document
from .label_artifact_sources import COMPONENT,FILENAME,ids,profile_hash
from .label_execution_history import audit_row, expected_delta as original_delta
from .wire import validate

def evidence_body(work_id,case_id,content,now):
    return validate('EvidenceAttachment',dict(evidence_id=ids(work_id)['evidence_id'],case_id=case_id,
        media_type='application/pdf',filename=FILENAME,size_bytes=len(content),sha256=sha256(content).hexdigest(),
        status='BOUND',created_at=timestamp(now),content_path='/v1/evidence/'+ids(work_id)['evidence_id']+'/content'),internal=True)

def result_body(confirmed,evidence_id,fact,now):
    return finite.validate('OperationAttempt',{**deepcopy(confirmed),'status':'SUCCEEDED','updated_at':timestamp(now),
        'result':dict(type='GENERATE_LABEL',provider_label_id=fact['provider_label_id'],parcel_id=fact['parcel_id'],
                      label_evidence_id=evidence_id)})

def completion_core(work,label,claim,evbody,opbody,head,now):
    return dict(profile='label-artifact-completion-core/v1',**ids(work['work_id']),work_id=work['work_id'],
        original_control_id=label['control_id'],original_operation_id=label['operation_id'],
        original_confirmation_record_id=label['confirmation_record_id'],
        original_binding_hash=label['binding_hash'],original_ledger_hash=label['confirmed_ledger_hash'],
        source_manifest_hash=claim['source_manifest_hash'],profile_hash=profile_hash(),
        completion_claim_id=claim['claim_id'],claim_hash=claim['claim_hash'],
        case_id=head['case_id'],store_id=label['store_id'],owner_id=label['owner_id'],
        sha256=evbody['sha256'],size_bytes=evbody['size_bytes'],media_type=evbody['media_type'],filename=evbody['filename'],
        evidence_content_hash=digest(evbody,'history/v1'),result_content_hash=finite.digest(opbody),
        completed_case_version=head['case_version'],completed_at=timestamp(now))

def origin_payload(core,slot):
    return dict(profile='label-artifact-origin/v1',completion_id=core['completion_id'],work_id=core['work_id'],
        evidence_id=core['evidence_id'],operation_id=core['original_operation_id'],slot=slot,
        core_hash=digest(core,'label-artifact-completion-core/v1'))

def append_record(uow,head,record_id,kind,object_id,revision,body,payload,correlation,now):
    ref=dict(record_id=record_id,kind=kind,object_id=object_id,object_version=revision)
    hashed=finite.digest(body) if kind=='OPERATION' else digest(body,'history/v1')
    record=dict(**ref,case_id=head['case_id'],case_version=head['case_version'],recorded_sequence=head['history_sequence']+1,
        recorded_at=now,content_sha256=hashed,retention_state='AVAILABLE',removal_reason=None)
    content=dict(record_id=record_id,body=finite.encode_document(body) if kind=='OPERATION' else encode_document(body))
    additions=[(old.history,record),(old.history_contents,content)]
    if kind=='OPERATION':
        additions.append((founder.encodings,dict(record_id=record_id,profile=finite.PROFILE,
            source_content_sha256=hashed,projected_content_sha256=hashed,receipt_id=None)))
    for table,row in additions:uow.execute(table.insert().values(**row))
    uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==head['case_id']).values(history_sequence=head['history_sequence']+1))
    event=append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':COMPONENT},
        event_type='GENERATED_LABEL_EVIDENCE_BOUND' if kind=='EVIDENCE' else 'OPERATION_REVISION_RECORDED',
        correlation_id=correlation,payload=payload,object_ids=[object_id],history_refs=[ref],now=now)
    additions.append((old.audit,audit_row(head,event)))
    post={**head,'history_sequence':head['history_sequence']+1,'audit_sequence':head['audit_sequence']+1,'audit_head':event['event_hash']}
    return record,event,post,additions

def certificate(core,evidence_event,result_event):
    return dict(profile='label-artifact-completion/v1',core=core,
        evidence_origin={'event_id':evidence_event['event_id'],'event_hash':evidence_event['event_hash']},
        result_origin={'event_id':result_event['event_id'],'event_hash':result_event['event_hash']})

def metadata(core,cert,now):
    fields=('evidence_id','work_id','completion_id','completion_claim_id','source_manifest_hash','profile_hash','sha256',
        'size_bytes','media_type','filename','evidence_record_id','result_record_id','completed_case_version')
    return dict(**{n:core[n] for n in fields},core=encode_document(core),certificate=encode_document(cert),
        core_hash=digest(core,'label-artifact-completion-core/v1'),completion_hash=digest(cert,'label-artifact-completion/v1'),
        evidence_audit_id=cert['evidence_origin']['event_id'],evidence_audit_hash=cert['evidence_origin']['event_hash'],
        result_audit_id=cert['result_origin']['event_id'],result_audit_hash=cert['result_origin']['event_hash'],
        completed_at=now,available=True,retention_state='AVAILABLE',removal_reason=None,
        pdf_retention_receipt=None,source_withdrawal_receipt=None)

def effect_values(label,body,record,sha):
    identity=digest({n:body[n] for n in ('operation_id','case_id','command_id','approval_id','proposal_id',
        'proposal_version','input_version','provider_id','operation_fingerprint','idempotency_key')},'lifecycle-effect/v1')
    return dict(operation_id=label['operation_id'],case_id=label['case_id'],record_id=record['record_id'],object_version=4,
        approval_record_id=label['approval_record_id'],command_id=label['command_id'],input_version=label['input_version'],
        generation=label['generation'],operation_type='GENERATE_LABEL',status='SUCCEEDED',identity_hash=identity,
        artifact_evidence_id=body['result']['label_evidence_id'],artifact_sha256=sha,dispatch_source_record_id=label['dispatch_record_id'])

def expected_delta(before,additions,replacements,post):
    original,=before[old.case_heads.name]
    if any(post[n]!=original[n] for n in original if n not in {'history_sequence','audit_sequence','audit_head'}):
        raise ValueError('Artifact completion changed business state')
    return original_delta(before,additions,replacements,post)
