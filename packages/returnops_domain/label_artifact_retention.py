"""Write-once ordered retention receipts, without reconstructing removed DTOs.

PDF-only removal has one genuine SERVICE audit and JSON-null trigger fields.
Source withdrawal cites the distinct, already formed original removal audit.
"""
from sqlalchemy import select,update,delete
from . import customer_tables as old,founder_codec as finite
from .audit import append_event,identifier,timestamp
from .canonical import digest,encode_document,decode_document
from .lifecycle_state import reject,MAX_VERSION
from .manual_target import one
from .label_execution_tables import artifact_work
from .label_artifact_tables import controls,claims,artifacts,contents
from .label_artifact_sources import ids,validate_control,source_rows

SERVICE={'kind':'SERVICE','component_id':'retention-v1'}
EVENT='GENERATED_LABEL_ARTIFACT_RETAINED'
SCOPES=['PDF_BYTES','GENERATED_EVIDENCE_BODY']
SOURCE_SCOPES=SCOPES+['OPERATION_BODY','PROPOSAL_BODY','REVIEW_BODY','DECISION_BODY','APPROVAL_BODY',
    'NOTIFICATION_BODY','PREVIEW_BODY','CUSTOMER_RECEIPT_BODY','ORDER_RECEIPT_BODY','ORDER_PROJECTION_BODY',
    'INVESTIGATION_INPUT_REFERENCES','INVESTIGATION_CLARIFICATION_REFERENCES']

def transition_id(work_id,kind):
    return 'laret_'+digest(dict(work_id=work_id,transition_kind=kind),'label-artifact-retention-id/v1')

def _receipt(payload,event):
    value=dict(payload=payload,retention_event_id=event['event_id'],retention_event_hash=event['event_hash'])
    return {**value,'receipt_hash':digest(value,'label-artifact-retention-receipt/v1')}

def _payload(control,row,label,kind,reason,redact,now,trigger=None,previous=None):
    if control['epoch']>=MAX_VERSION:reject_value()
    return dict(profile='label-artifact-retention/v1',transition_id=transition_id(control['work_id'],kind),
        transition_kind=kind,work_id=control['work_id'],completion_id_or_None=None if row is None else row['completion_id'],
        completion_hash_or_None=None if row is None else row['completion_hash'],evidence_id=ids(control['work_id'])['evidence_id'],
        operation_id=label['operation_id'],evidence_record_id_or_None=None if row is None else row['evidence_record_id'],
        result_record_id_or_None=None if row is None else row['result_record_id'],reason=reason,
        retention_state='REDACTED' if redact else 'DELETED',trigger_kind='DIRECT_GENERATED_ARTIFACT_RETENTION' if trigger is None else trigger['trigger_kind'],
        trigger_object_id=ids(control['work_id'])['evidence_id'] if trigger is None else trigger['object_id'],
        trigger_event_id=None if trigger is None else trigger['event']['event_id'],
        trigger_event_hash=None if trigger is None else trigger['event']['event_hash'],
        source_removal=None if trigger is None else trigger['source_removal'],
        cascade_trigger=None if trigger is None else trigger['cascade_trigger'],
        previous_retention_receipt_hash_or_None=None if previous is None else previous['receipt_hash'],
        original_content_sha256_or_None=None if row is None else row['sha256'],original_size_bytes_or_None=None if row is None else row['size_bytes'],
        removed_scopes=SCOPES if kind=='PDF_REMOVED' else SOURCE_SCOPES,prior_control_state=control['state'],
        prior_epoch=control['epoch'],resulting_epoch=control['epoch']+1,prior_active_claim_id_or_None=control['active_claim_id'],
        occurred_at=timestamp(now))

def reject_value():
    from .errors import FlowError
    raise FlowError('INVALID_STATE')

def _verify_receipt(uow,raw,control,row,proof,kind,previous=None):
    receipt=decode_document(raw)
    if set(receipt)!={'payload','retention_event_id','retention_event_hash','receipt_hash'}:reject(uow)
    unsigned={n:v for n,v in receipt.items() if n!='receipt_hash'}
    if receipt['receipt_hash']!=digest(unsigned,'label-artifact-retention-receipt/v1'):reject(uow)
    p=receipt['payload'];work,label,_=source_rows(uow,control['work_id'])
    required={'profile','transition_id','transition_kind','work_id','completion_id_or_None','completion_hash_or_None',
        'evidence_id','operation_id','evidence_record_id_or_None','result_record_id_or_None','reason','retention_state',
        'trigger_kind','trigger_object_id','trigger_event_id','trigger_event_hash','previous_retention_receipt_hash_or_None',
        'original_content_sha256_or_None','original_size_bytes_or_None','removed_scopes','prior_control_state','prior_epoch',
        'resulting_epoch','prior_active_claim_id_or_None','occurred_at','source_removal','cascade_trigger'}
    if set(p)!=required:reject(uow)
    fields=dict(profile='label-artifact-retention/v1',transition_id=transition_id(control['work_id'],kind),
        transition_kind=kind,work_id=control['work_id'],evidence_id=ids(control['work_id'])['evidence_id'],operation_id=label['operation_id'],
        completion_id_or_None=None if row is None else row['completion_id'],completion_hash_or_None=None if row is None else row['completion_hash'],
        evidence_record_id_or_None=None if row is None else row['evidence_record_id'],result_record_id_or_None=None if row is None else row['result_record_id'],
        original_content_sha256_or_None=None if row is None else row['sha256'],original_size_bytes_or_None=None if row is None else row['size_bytes'],
        previous_retention_receipt_hash_or_None=None if previous is None else previous['receipt_hash'],
        removed_scopes=SCOPES if kind=='PDF_REMOVED' else SOURCE_SCOPES)
    if (any(p[n]!=v for n,v in fields.items()) or p['reason'] not in {'RETENTION_POLICY','OWNER_REQUEST'}
            or p['retention_state'] not in {'DELETED','REDACTED'} or type(p['prior_epoch']) is not int
            or not 0<=p['prior_epoch']<MAX_VERSION or p['resulting_epoch']!=p['prior_epoch']+1
            or p['resulting_epoch']>control['epoch'] or p['prior_control_state'] not in {'PENDING','RUNNING','DONE','RETAINED'}
            or (p['prior_control_state']=='RUNNING')!=(p['prior_active_claim_id_or_None'] is not None)):reject(uow)
    if p['prior_active_claim_id_or_None'] is not None:
        claim=one(uow,claims,claim_id=p['prior_active_claim_id_or_None'])
        if claim['work_id']!=control['work_id'] or claim['epoch']!=p['prior_epoch']:reject(uow)
    matches=[e for e in proof.events if e['event_id']==receipt['retention_event_id']]
    if len(matches)!=1:reject(uow)
    event=matches[0]
    if (event['event_hash']!=receipt['retention_event_hash'] or event['event_type']!=EVENT or event['actor']!=SERVICE
            or event['case_id']!=label['case_id'] or event['payload_hash']!=digest(p,'audit-payload/v1')
            or event['object_ids']!=[p['evidence_id'],label['operation_id']] or event['history_refs']
            or event['occurred_at']!=p['occurred_at']):reject(uow)
    if kind=='PDF_REMOVED':
        if (row is None or p['trigger_kind']!='DIRECT_GENERATED_ARTIFACT_RETENTION'
                or p['trigger_object_id']!=p['evidence_id'] or p['trigger_event_id'] is not None
                or p['trigger_event_hash'] is not None or p['prior_control_state']!='DONE'
                or p['previous_retention_receipt_hash_or_None'] is not None or p['source_removal'] is not None
                or p['cascade_trigger'] is not None):reject(uow)
    else:
        if p['trigger_kind'] not in {'ORIGINAL_SOURCE_RETENTION','CASE_WIDE_CUSTOMER_CONTENT_RETENTION'} or type(p['trigger_event_id']) is not str or type(p['trigger_event_hash']) is not str:reject(uow)
        triggers=[e for e in proof.events if e['event_id']==p['trigger_event_id']]
        if len(triggers)!=1:reject(uow)
        trigger=triggers[0]
        if (trigger['event_id']==event['event_id'] or trigger['event_hash']!=p['trigger_event_hash']
                or trigger['actor']!=SERVICE or trigger['event_type']!='CUSTOMER_CONTENT_REMOVED'
                or trigger['case_id']!=label['case_id'] or trigger['object_ids']!=[p['trigger_object_id']]
                or proof.events.index(trigger)>=proof.events.index(event)):reject(uow)
        from .label_artifact_sources import source_manifest
        from .label_artifact_retention_sources import verify_removal,later_context,verify_policy_postconditions,CASCADE_FIELDS
        original=source_manifest(uow,control['work_id'])['original_inputs']
        verify_removal(uow,p['source_removal'],label['case_id'],p['trigger_object_id'],trigger,p['reason'],p['retention_state'])
        if p['trigger_kind']=='ORIGINAL_SOURCE_RETENTION':
            if p['cascade_trigger'] is not None or p['trigger_object_id'] not in {r['object_id'] for r in original}:reject(uow)
        else:
            cascade=p['cascade_trigger']
            if type(cascade) is not dict or set(cascade)!=CASCADE_FIELDS:reject(uow)
            if cascade!=later_context(uow,control,p['source_removal']['subject_kind'],p['trigger_object_id'],proof,capture=p['source_removal']):reject(uow)
            accepted=[e for e in proof.events if e['event_id']==cascade['acceptance_event_id']]
            if len(accepted)!=1 or proof.events.index(accepted[0])>=proof.events.index(trigger):reject(uow)
        verify_policy_postconditions(uow,control,generated=row)
        if previous is not None:
            first=[e for e in proof.events if e['event_id']==previous['retention_event_id']]
            if len(first)!=1 or proof.events.index(first[0])>=proof.events.index(event):reject(uow)
    return receipt

def verify_retention(uow,row,control,proof):
    if control['state']!='RETAINED' or control['active_claim_id'] is not None:reject(uow)
    first=None
    if row['pdf_retention_receipt'] is not None:first=_verify_receipt(uow,row['pdf_retention_receipt'],control,row,proof,'PDF_REMOVED')
    second=None
    if row['source_withdrawal_receipt'] is not None:
        if control['source_withdrawal_receipt']!=row['source_withdrawal_receipt']:reject(uow)
        second=_verify_receipt(uow,row['source_withdrawal_receipt'],control,row,proof,'ORIGINAL_SOURCE_WITHDRAWN',first)
    elif control['source_withdrawal_receipt'] is not None:reject(uow)
    if first is None and second is None:reject(uow)
    initial=first or second
    if control['epoch']!=(second or first)['payload']['resulting_epoch']:reject(uow)
    if row['removal_reason']!=initial['payload']['reason'] or row['retention_state']!=initial['payload']['retention_state']:reject(uow)
    evidence=one(uow,old.history,record_id=row['evidence_record_id'])
    if evidence['retention_state']!=row['retention_state'] or evidence['removal_reason']!=row['removal_reason']:reject(uow)

def verify_control_retention(uow,control,proof):
    if control['completed_evidence_id'] is not None:return
    if control['state']!='RETAINED' or control['active_claim_id'] is not None or control['source_withdrawal_receipt'] is None:reject(uow)
    receipt=_verify_receipt(uow,control['source_withdrawal_receipt'],control,None,proof,'ORIGINAL_SOURCE_WITHDRAWN')
    if control['epoch']!=receipt['payload']['resulting_epoch']:reject(uow)

def _save(uow,control,row,label,payload,now):
    event=append_event(uow,label['case_id'],actor=SERVICE,event_type=EVENT,correlation_id=identifier('corr'),
        payload=payload,object_ids=[payload['evidence_id'],label['operation_id']],history_refs=[],now=now)
    receipt=_receipt(payload,event);raw=encode_document(receipt)
    slot='pdf_retention_receipt' if payload['transition_kind']=='PDF_REMOVED' else 'source_withdrawal_receipt'
    if row is not None:
        changes={slot:raw}
        if row['available']:
            changes.update(available=False,retention_state=payload['retention_state'],removal_reason=payload['reason'])
            uow.execute(delete(contents).where(contents.c.evidence_id==row['evidence_id']))
            uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id==row['evidence_record_id']))
            uow.execute(update(old.history).where(old.history.c.record_id==row['evidence_record_id'],old.history.c.retention_state=='AVAILABLE').values(
                retention_state=payload['retention_state'],removal_reason=payload['reason']))
        if uow.execute(update(artifacts).where(artifacts.c.evidence_id==row['evidence_id'],getattr(artifacts.c,slot).is_(None)).values(**changes)).rowcount!=1:reject(uow)
    changes=dict(state='RETAINED',epoch=payload['resulting_epoch'],active_claim_id=None,safe_failure_code=None)
    if slot=='source_withdrawal_receipt':changes[slot]=raw
    if uow.execute(update(controls).where(controls.c.work_id==control['work_id'],controls.c.epoch==control['epoch']).values(**changes)).rowcount!=1:reject(uow)
    return receipt

def remove_pdf(uow,evidence_id,reason,redact,now):
    from .generated_evidence import verify_certificate
    seal=verify_certificate(uow,evidence_id);row=seal['row']
    control=one(uow,controls,work_id=row['work_id'])
    if not row['available']:return False
    payload=_payload(control,row,seal['label'],'PDF_REMOVED',reason,redact,now)
    _save(uow,control,row,seal['label'],payload,now)
    verify_certificate(uow,evidence_id)
    return True

def prepare_source_withdrawal(uow,case_id,kind,object_id):
    """Capture original proof and exact actual removal identities before writes."""
    from .generated_evidence import verify_certificate
    from .founder_integrity import CaseProof,read_revision
    from .label_artifact_sources import source_manifest
    from .label_artifact_retention_sources import (removal_capture,subject_records,later_context,
        affected_sources,policy_snapshot)
    head=one(uow,old.case_heads,case_id=case_id);proof=CaseProof(uow,head)
    result=[]
    for work in uow.execute(select(artifact_work).where(artifact_work.c.case_id==case_id)).mappings():
        control=uow.execute(select(controls).where(controls.c.work_id==work['work_id'])).mappings().one_or_none()
        if control is None:continue
        control=dict(control);validate_control(uow,control)
        if control['source_withdrawal_receipt'] is not None:
            row=None if control['completed_evidence_id'] is None else one(uow,artifacts,evidence_id=control['completed_evidence_id'])
            if row is None:verify_control_retention(uow,control,proof)
            else:verify_certificate(uow,row['evidence_id'],proof=proof)
            continue
        _,label,_=source_rows(uow,work['work_id'])
        row=None
        if control['completed_evidence_id'] is not None:row=verify_certificate(uow,control['completed_evidence_id'],proof=proof)['row']
        approval=one(uow,old.history,record_id=label['approval_record_id'])
        body=read_revision(uow,approval,proof).get('content')
        if body is None:reject(uow)
        proposals=[r for r in proof.revisions.values() if r['kind']=='PROPOSAL' and r['object_id']==body['scope']['proposal_id'] and r['object_version']==body['scope']['proposal_version']]
        if len(proposals)!=1:reject(uow)
        bundle=read_revision(uow,proposals[0],proof).get('content')
        if bundle is None:reject(uow)
        capture=removal_capture(uow,case_id,kind,object_id)
        if not capture['removed_record_ids']:reject(uow)
        original=source_manifest(uow,control['work_id'])['original_inputs']
        direct=any(r['kind']==kind and r['object_id']==object_id for r in original)
        cascade=None if direct else later_context(uow,control,kind,object_id,proof,capture=capture)
        result.append(dict(control=control,row=row,label=label,source_removal=capture,cascade_trigger=cascade,
            trigger_kind='ORIGINAL_SOURCE_RETENTION' if direct else 'CASE_WIDE_CUSTOMER_CONTENT_RETENTION',
            subject_before=subject_records(uow,case_id,kind,object_id),policy_before=policy_snapshot(uow,case_id),
            affected_sources_hash=affected_sources(uow,control['work_id'])))
    return result

def finish_source_withdrawal(uow,prepared,kind,object_id,event,reason,redact,now):
    from .label_artifact_retention_sources import verify_policy_postconditions,verify_removal,affected_sources
    for context in prepared:
        control,row,label=(context[n] for n in ('control','row','label'))
        state='REDACTED' if redact else 'DELETED'
        if affected_sources(uow,control['work_id'])!=context['affected_sources_hash']:reject(uow)
        verify_removal(uow,context['source_removal'],label['case_id'],object_id,event,reason,state,before=context['subject_before'])
        verify_policy_postconditions(uow,control,before=context['policy_before'],reason=reason,retention_state=state)
        previous=None if row is None or row['pdf_retention_receipt'] is None else decode_document(row['pdf_retention_receipt'])
        trigger=dict(kind=kind,object_id=object_id,event=event,**{n:context[n] for n in ('trigger_kind','source_removal','cascade_trigger')})
        payload=_payload(control,row,label,'ORIGINAL_SOURCE_WITHDRAWN',reason,redact,now,trigger=trigger,previous=previous)
        _save(uow,control,row,label,payload,now)
    if prepared:
        from .founder_integrity import CaseProof
        from .generated_evidence import verify_certificate
        head=one(uow,old.case_heads,case_id=prepared[0]['label']['case_id']);proof=CaseProof(uow,head)
        for context in prepared:
            control,row=context['control'],context['row'];saved=one(uow,controls,work_id=control['work_id'])
            if row is None:verify_control_retention(uow,saved,proof)
            else:verify_certificate(uow,row['evidence_id'],proof=proof)

def invalidate_claims(uow,case_id):
    work_ids=select(artifact_work.c.work_id).where(artifact_work.c.case_id==case_id)
    for row in uow.execute(select(controls).where(controls.c.work_id.in_(work_ids),controls.c.state.in_(['PENDING','RUNNING']))).mappings():
        if row['epoch']>=MAX_VERSION:reject(uow)
        uow.execute(update(controls).where(controls.c.work_id==row['work_id']).values(
            state='PENDING',epoch=row['epoch']+1,active_claim_id=None,safe_failure_code='SOURCE_ADVANCED'))
