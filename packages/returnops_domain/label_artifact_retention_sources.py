"""Exact original-policy cascade proof; no new retention target or workflow.

Only immutable identifiers/hashes cross into receipts. Actual original-policy
postconditions are re-read; a caller-provided unavailable flag is not proof.
"""
from sqlalchemy import select
from . import customer_tables as old,lifecycle_tables as life,investigation_tables as inv
from .audit import timestamp
from .canonical import digest,decode_document
from .lifecycle_state import reject
from .manual_target import one
from .label_artifact_sources import source_manifest,source_rows,hash_rows
from .label_execution_tables import controls as labels,artifact_work
from .return_execution_tables import controls as returns
from .preview_tables import previews

DERIVED_KINDS=('PROPOSAL','REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION')
SUBJECT_FIELDS=('record_id','kind','object_id','object_version','case_version','recorded_sequence','recorded_at','content_sha256')
CASCADE_FIELDS={'profile','cascade_profile','subject_kind','original_source_manifest_hash','original_proposal_record_id',
    'acceptance_id','acceptance_fact_hash','intake_work_id','accepted_input_version','acceptance_event_id','acceptance_event_hash',
    'subject_records','removed_record_ids','affected_original_sources_hash'}

def subject_records(uow,case_id,kind,object_id):
    rows=[dict(r) for r in uow.execute(select(old.history).where(old.history.c.case_id==case_id,
        old.history.c.kind==kind,old.history.c.object_id==object_id).order_by(old.history.c.recorded_sequence,old.history.c.record_id)).mappings()]
    if not rows:reject(uow)
    return rows

def record_identity(row):
    return {n:timestamp(row[n]) if n=='recorded_at' else row[n] for n in SUBJECT_FIELDS}

def removal_capture(uow,case_id,kind,object_id):
    records=subject_records(uow,case_id,kind,object_id)
    return dict(subject_kind=kind,subject_records=[record_identity(r) for r in records],
        removed_record_ids=[r['record_id'] for r in records if r['retention_state']=='AVAILABLE'])

def verify_removal(uow,capture,case_id,object_id,trigger,reason,retention_state,*,before=None):
    if type(capture) is not dict or set(capture)!={'subject_kind','subject_records','removed_record_ids'}:reject(uow)
    kind=capture['subject_kind']
    if kind not in {'STATEMENT','EVIDENCE'}:reject(uow)
    rows=subject_records(uow,case_id,kind,object_id)
    identities=[record_identity(r) for r in rows]
    removed=capture['removed_record_ids']
    if (capture['subject_records']!=identities or type(removed) is not list or not removed
            or len(removed)!=len(set(removed)) or removed!=[r['record_id'] for r in rows if r['record_id'] in removed]):reject(uow)
    selected=[r for r in rows if r['record_id'] in removed]
    refs=[{n:r[n] for n in ('record_id','kind','object_id','object_version')} for r in selected]
    if (trigger['history_refs']!=refs[:100] or trigger['object_ids']!=[object_id]
            or trigger['payload_hash']!=digest({'kind':kind,'object_id':object_id,'reason':reason,
                'revision_count':len(removed)},'audit-payload/v1')):reject(uow)
    for row in rows:
        if (row['retention_state']=='AVAILABLE' or uow.execute(select(old.history_contents.c.record_id).where(
                old.history_contents.c.record_id==row['record_id'])).first()):reject(uow)
        if row['record_id'] in removed and (row['retention_state']!=retention_state or row['removal_reason']!=reason):reject(uow)
    if before is not None:
        if capture!=dict(subject_kind=kind,subject_records=[record_identity(r) for r in before],
                removed_record_ids=[r['record_id'] for r in before if r['retention_state']=='AVAILABLE']):reject(uow)
        expected=[{**r,'retention_state':retention_state,'removal_reason':reason} if r['retention_state']=='AVAILABLE' else r for r in before]
        if rows!=expected:reject(uow)

def affected_sources(uow,work_id):
    work,label,_=source_rows(uow,work_id);manifest=source_manifest(uow,work_id)
    proposal=[r for r in manifest['records'] if r['kind']=='PROPOSAL']
    if len(proposal)!=1:reject(uow)
    binding=one(uow,life.sources,record_id=proposal[0]['record_id'])
    projection=one(uow,inv.projections,projection_id=binding['order_projection_id'])
    receipt=one(uow,inv.receipts,receipt_id=projection['receipt_id'])
    returned=one(uow,returns,preparation_id=label['return_preparation_id'])
    value=dict(profile='existing-casewide-derived-content/v1',work_id=work_id,
        source_manifest=manifest,return_control_id=returned['preparation_id'],label_control_id=label['control_id'],
        projection={n:projection[n] for n in ('projection_id','case_id','receipt_id','snapshot_id','snapshot_version','snapshot_hash','input_version','source_input_version')},
        investigation_receipt={n:receipt[n] for n in ('receipt_id','case_id','work_id','input_version','body_hash')})
    return hash_rows(value,'label-artifact-affected-original-sources/v1')

def later_context(uow,control,kind,object_id,proof,*,capture=None):
    """Rebuild real later acceptance even after its bodies have been removed."""
    from .execution_artifact_chain_sources import _customer_acceptance
    from .generated_evidence import is_generated_resource
    _,label,_=source_rows(uow,control['work_id']);head=proof.head
    if kind not in {'STATEMENT','EVIDENCE'} or kind=='EVIDENCE' and is_generated_resource(uow,object_id):reject(uow)
    manifest=source_manifest(uow,control['work_id'])
    if object_id in {r['object_id'] for r in manifest['original_inputs']}:reject(uow)
    proposal=[r for r in manifest['records'] if r['kind']=='PROPOSAL']
    if len(proposal)!=1:reject(uow)
    proposal_row=one(uow,old.history,record_id=proposal[0]['record_id'])
    records=subject_records(uow,head['case_id'],kind,object_id)
    expected_actor={'kind':'HUMAN','role':'CUSTOMER','principal_id':head['owner_principal_id']}
    proven=[]
    for record in records:
        fact=_customer_acceptance(uow,head,proof,record);origin=proof.origin(record)
        intake=one(uow,old.intake_work,acceptance_id=fact['acceptance_id']);refs=decode_document(intake['source_refs'])
        if (origin['event_type']!='CUSTOMER_CLARIFICATION_ACCEPTED' or origin['actor']!=expected_actor
                or fact['operation']!='submitClarification' or fact['target']!=head['case_id'] or fact['response_status']!=202
                or intake['case_id']!=head['case_id'] or intake['accepted_principal_id']!=head['owner_principal_id']
                or intake['accepted_owner_id']!=head['owner_principal_id'] or intake['accepted_store_id']!=head['store_id']
                or intake['input_version']<=label['input_version'] or intake['created_at']!=fact['accepted_at']
                or intake['accepted_case_version']!=origin['case_version'] or origin['occurred_at']!=timestamp(fact['accepted_at'])
                or origin['payload_hash']!=digest({'acceptance_id':fact['acceptance_id'],'request_fingerprint':fact['fingerprint'],
                    'work_id':intake['work_id']},'audit-payload/v1') or origin['history_refs']!=refs
                or origin['object_ids']!=[r['object_id'] for r in refs]
                or record['recorded_sequence']<=proposal_row['recorded_sequence'] or record['case_version']!=intake['accepted_case_version']):reject(uow)
        for ref in refs:
            row=proof.revisions.get(ref['record_id'])
            if row is None or row['kind'] not in {'STATEMENT','EVIDENCE'} or proof.origin(row)!=origin:reject(uow)
            if row['kind']=='EVIDENCE' and is_generated_resource(uow,row['object_id']):reject(uow)
        proven.append((fact,origin,intake))
    fact,origin,intake=proven[0]
    if kind=='EVIDENCE':
        customer=one(uow,old.evidence,evidence_id=object_id)
        if (customer['status']!='BOUND' or customer['case_id']!=head['case_id'] or customer['store_id']!=head['store_id']
                or customer['uploader_id']!=head['owner_principal_id']):reject(uow)
    removal=removal_capture(uow,head['case_id'],kind,object_id) if capture is None else capture
    expected=dict(profile='accepted-later-input-casewide-retention/v1',cascade_profile='existing-casewide-derived-content/v1',
        subject_kind=kind,original_source_manifest_hash=control['source_manifest_hash'],original_proposal_record_id=proposal_row['record_id'],
        acceptance_id=fact['acceptance_id'],acceptance_fact_hash=hash_rows(fact,'label-artifact-later-acceptance/v1'),
        intake_work_id=intake['work_id'],accepted_input_version=intake['input_version'],acceptance_event_id=origin['event_id'],
        acceptance_event_hash=origin['event_hash'],subject_records=[record_identity(r) for r in records],
        removed_record_ids=removal['removed_record_ids'],affected_original_sources_hash=affected_sources(uow,control['work_id']))
    return expected

def policy_snapshot(uow,case_id):
    return [dict(r) for r in uow.execute(select(old.history).where(old.history.c.case_id==case_id,
        old.history.c.kind.in_(DERIVED_KINDS)).order_by(old.history.c.recorded_sequence)).mappings()]

def verify_policy_postconditions(uow,control,*,before=None,reason=None,retention_state=None,generated=None):
    """The existing deletion policy must really have run, not only flag flips."""
    work,label,_=source_rows(uow,control['work_id']);case_id=label['case_id']
    returned=one(uow,returns,preparation_id=label['return_preparation_id'])
    if (returned['source_available'] or returned['result_retained'] or returned['query_claim_id'] is not None or returned['query_lease_until'] is not None
            or label['source_available'] or label['confirmation_retained'] or label['query_claim_id'] is not None or label['query_lease_until'] is not None
            or work['state']!='PAUSED'):reject(uow)
    state=one(uow,life.state,case_id=case_id)
    if state['available'] or any(state[n] is not None for n in ('proposal_record_id','review_record_id','preview_id','approval_record_id')):reject(uow)
    records=policy_snapshot(uow,case_id)
    for row in records:
        if row['retention_state']=='AVAILABLE' or uow.execute(select(old.history_contents.c.record_id).where(old.history_contents.c.record_id==row['record_id'])).first():reject(uow)
    if before is not None:
        expected=[{**r,'retention_state':retention_state,'removal_reason':reason} if r['retention_state']=='AVAILABLE' else r for r in before]
        if records!=expected:reject(uow)
    if uow.execute(select(previews.c.preview_id).where(previews.c.case_id==case_id,
        (previews.c.available.is_(True))|(previews.c.body.is_not(None)))).first():reject(uow)
    acceptance_ids=select(old.acceptances.c.acceptance_id).where(old.acceptances.c.resource_kind=='CASE',old.acceptances.c.resource_id==case_id)
    if uow.execute(select(old.receipts.c.acceptance_id).where(old.receipts.c.acceptance_id.in_(acceptance_ids),
        (old.receipts.c.available.is_(True))|(old.receipts.c.body.is_not(None)))).first():reject(uow)
    receipt_ids=select(inv.receipts.c.receipt_id).where(inv.receipts.c.case_id==case_id)
    projection_ids=select(inv.projections.c.projection_id).where(inv.projections.c.case_id==case_id)
    work_ids=select(inv.work.c.work_id).where(inv.work.c.case_id==case_id)
    for table,column,ids in ((inv.receipt_contents,'receipt_id',receipt_ids),(inv.projection_contents,'projection_id',projection_ids)):
        if uow.execute(select(getattr(table.c,column)).where(getattr(table.c,column).in_(ids))).first():reject(uow)
    for table in (inv.receipts,inv.projections):
        if uow.execute(select(table).where(table.c.case_id==case_id,table.c.available.is_(True))).first():reject(uow)
    if (uow.execute(select(inv.inputs).where(inv.inputs.c.work_id.in_(work_ids),(inv.inputs.c.available.is_(True))|(inv.inputs.c.reference.is_not(None)))).first()
            or uow.execute(select(inv.clarification_inputs).where(inv.clarification_inputs.c.case_id==case_id,
                (inv.clarification_inputs.c.available.is_(True))|(inv.clarification_inputs.c.reference.is_not(None)))).first()
            or uow.execute(select(inv.work.c.work_id).where(inv.work.c.case_id==case_id,inv.work.c.state.in_(['PENDING','RUNNING']))).first()):reject(uow)
    investigation=one(uow,inv.state,case_id=case_id)
    if investigation['current_projection_id'] is not None:reject(uow)
    if generated is not None:
        from .label_artifact_tables import contents
        if (generated['available'] or uow.execute(select(contents.c.evidence_id).where(contents.c.evidence_id==generated['evidence_id'])).first()
                or uow.execute(select(old.history_contents.c.record_id).where(old.history_contents.c.record_id.in_(
                    [generated['evidence_record_id'],generated['result_record_id']]))).first()):reject(uow)
