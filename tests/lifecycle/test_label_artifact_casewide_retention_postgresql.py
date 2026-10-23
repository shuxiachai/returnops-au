"""F3/P10/P17/P18/P19: unchanged old policy over genuine later customer input."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,update,delete
from returnops_domain import customer_tables as old,lifecycle_tables as life,investigation_tables as inv
from returnops_domain.audit import append_event,timestamp
from returnops_domain.canonical import encode_document,decode_document,digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.retention import RetentionService
from returnops_domain.label_artifact_tables import artifacts,controls,contents
from returnops_domain.label_execution_tables import controls as labels
from returnops_domain.storage import original_statement_contents
from label_artifact_helpers import ready,service,customer,complete,recover,claim,rows,snapshot,evidence

def later_input(engine,identities,args,*,upload=False):
    """Protective question placement, followed by real CustomerFlow acceptance."""
    evidence_ids=[]
    if upload:
        from returnops_domain.label_pdf import LabelPdfFields,render_label_pdf
        from returnops_domain.evidence_validation import validate_evidence
        pdf=render_label_pdf(LabelPdfFields('later_customer_label','later_customer_return','later_customer_parcel'))
        staged=customer(engine,identities).stage(validate_evidence(pdf,'later-customer.pdf','application/pdf'),
            'later-evidence-stage-key','later-evidence-stage-correlation')
        evidence_ids=[staged.body['evidence_id']]
    with CustomerUnitOfWork(engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one())
        questions=[dict(question_id=f'later_question_{i}',text='Additional independent customer context.',reason='Protective current input-state fixture.') for i in (1,2)]
        uow.execute(old.questions.insert().values(question_set_id='later_retention_questions',case_id=head['case_id'],input_version=head['input_version'],
            questions=encode_document(questions),question_kinds=encode_document({q['question_id']:'TEXT_RESPONSE' for q in questions})))
        uow.execute(update(old.case_heads).values(status='AWAITING_INFORMATION',current_question_set_id='later_retention_questions'));uow.commit()
    result=customer(engine,identities).clarify(args['case_id'],dict(expected_case_version=head['case_version'],question_set_id='later_retention_questions',
        answers=[dict(question_id=q['question_id'],text='Independent later customer material '+str(i)) for i,q in enumerate(questions)],evidence_ids=evidence_ids),
        'later-retention-acceptance-key','later-retention-acceptance-correlation')
    assert result.status==202
    statements=[r['object_id'] for r in rows(engine,old.history) if r['kind']=='STATEMENT' and r['recorded_sequence']>head['history_sequence']]
    assert len(statements)==2
    return statements,evidence_ids

def test_LA_P08_P11_P17_P19_completed_recovery_uses_current_proof_and_original_bridge_identity(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain.core_return_mock import CoreReturnMock
    from returnops_domain.core_label_mock import CoreLabelMock
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
    from returnops_domain.label_artifact_sources import authorize
    from returnops_domain.label_execution_sources import full_chain
    from returnops_domain.label_artifact_tables import claims
    args,setup=ready(flow_engine,identities);caller=service(flow_engine,identities)
    completed=complete(caller,args);assert completed.status=='COMMITTED',asdict(completed)
    statements,_=later_input(flow_engine,identities,args);calls=[]
    def forbidden(*a,**kw):
        calls.append('claim or provider or artifact retrieval invoked')
        raise AssertionError('Recovery only reads the existing accepted result')
    monkeypatch.setattr(CoreReturnMock,'perform',forbidden);monkeypatch.setattr(CoreLabelMock,'perform',forbidden)
    monkeypatch.setattr(CoreLabelArtifactMock,'retrieve_original_label',forbidden);monkeypatch.setattr(caller,'_claim',forbidden)
    saved_claims=rows(flow_engine,claims);saved_meta=rows(flow_engine,artifacts)[0];observations=[]
    for withdrawn in (False,True):
        if withdrawn:assert RetentionService(flow_engine).remove('STATEMENT',statements[0])
        before=snapshot(flow_engine);observed=recover(caller,args)
        assert asdict(observed)=={**asdict(completed),'status':'REPLAYED','content_available':not withdrawn},asdict(observed)
        # The original N3 caller invokes historical_bridge separately from the
        # 0013 aggregate; exercise that actual full_chain entry as well.
        with CustomerUnitOfWork(flow_engine,write=False) as uow:
            authorization=authorize(uow,caller.authority,args['case_id'],store=False)
            returned,root,bridge=full_chain(uow,authorization[0],authorization[1],
                setup['label_args']['execution_work_id'],args['original_approval_key'])
            assert returned['input_version']==bridge['accepted']['work']['input_version']
            assert returned['input_version']<authorization[1]['input_version']
            assert (root is None)==withdrawn
            uow.commit()
        assert snapshot(flow_engine)==before and rows(flow_engine,claims)==saved_claims and calls==[]
        meta=rows(flow_engine,artifacts)[0]
        assert all(meta[n]==saved_meta[n] for n in ('core','certificate','completion_hash','completed_at'))
        if withdrawn:
            assert not rows(flow_engine,contents)
            removed={meta['evidence_record_id'],meta['result_record_id']}
            assert not [r for r in rows(flow_engine,old.history_contents) if r['record_id'] in removed]
        observations.append(dict(withdrawn=withdrawn,result=asdict(observed),snapshot=before))
    evidence(request.node.nodeid,observations=observations,claim_provider_retrieval_calls=calls)

@pytest.mark.parametrize('fault',['extra_head_key','missing_head_key','audit_head','original_input','control_input','work_input','identity'])
def test_LA_P05_P11_P19_current_proof_cannot_refresh_or_reidentify_original_bridge(flow_engine,identities,enabled,request,fault):
    from returnops_domain.label_artifact_sources import authorize
    from returnops_domain.label_execution_sources import full_chain
    from returnops_domain.return_label_sources import retained_acceptance
    args,setup=ready(flow_engine,identities);caller=service(flow_engine,identities)
    assert complete(caller,args).status=='COMMITTED'
    later_input(flow_engine,identities,args)
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        authorization=authorize(uow,caller.authority,args['case_id'],store=False)
        returned,_,bridge=full_chain(uow,authorization[0],authorization[1],
            setup['label_args']['execution_work_id'],args['original_approval_key'])
        historical={**authorization[1],'input_version':returned['input_version']}
        source=deepcopy(bridge['source']);ids=deepcopy(bridge['ids']);actual_input=authorization[1]['input_version']
        assert historical['input_version']<actual_input
        uow.commit()
    if fault=='extra_head_key':historical['unaccepted_context']='forged'
    elif fault=='missing_head_key':historical.pop('current_failure_id')
    elif fault=='audit_head':historical['audit_head']='0'*64
    elif fault=='original_input':historical['input_version']=actual_input
    elif fault=='control_input':source['control']['input_version']=actual_input
    elif fault=='identity':ids['target_hash']='0'*64
    else:
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            assert uow.execute(update(life.work).where(life.work.c.work_id==ids['work_id']).values(input_version=actual_input)).rowcount==1
            uow.commit()
    before=snapshot(flow_engine)
    with pytest.raises(FlowError) as denied:
        with CustomerUnitOfWork(flow_engine,write=False) as uow:
            retained_acceptance(uow,historical,source,ids)
    assert denied.value.code=='INVALID_STATE' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=denied.value.code,before=before,after=snapshot(flow_engine))

def test_LA_P07_P19_genuine_later_input_still_invalidates_original_artifact_claim(flow_engine,identities,enabled,request):
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
    from returnops_domain.label_artifact_tables import claims
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    port=CoreLabelArtifactMock(flow_engine);reply=port.retrieve_original_label(ticket,caller.authority)
    assert reply.status=='FOUND'
    original_claim=rows(flow_engine,claims)[0]
    later_input(flow_engine,identities,args)
    assert rows(flow_engine,old.case_heads)[0]['input_version']>original_claim['claimed_input_version']
    before=snapshot(flow_engine);late_read=port.retrieve_original_label(ticket,caller.authority)
    late_complete=caller._complete(ticket,reply.content,'old-input-artifact-completion')
    assert late_read.status==late_complete.status=='DENIED'
    assert late_read.content is None and not rows(flow_engine,artifacts) and not rows(flow_engine,contents)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,read_status=late_read.status,completion=asdict(late_complete),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('mode',['claimed','done','pdf_removed','no_control','bound_evidence'])
def test_LA_P10_P17_P18_P19_real_later_customer_removal_keeps_casewide_policy_and_original_success(flow_engine,identities,enabled,request,mode):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=None;completed=None
    if mode=='claimed':ticket=claim(caller,args)
    elif mode!='no_control':
        completed=complete(caller,args);assert completed.status=='COMMITTED'
        if mode=='pdf_removed':assert RetentionService(flow_engine).remove('EVIDENCE',completed.label_evidence_id,reason='OWNER_REQUEST',redact=True)
    statements,uploads=later_input(flow_engine,identities,args,upload=mode=='bound_evidence')
    target=uploads[0] if mode=='bound_evidence' else statements[0];kind='EVIDENCE' if uploads else 'STATEMENT'
    original_bytes=rows(flow_engine,original_statement_contents)
    prior_meta=rows(flow_engine,artifacts);prior_control=rows(flow_engine,controls);before=snapshot(flow_engine)
    assert RetentionService(flow_engine).remove(kind,target)
    after=snapshot(flow_engine);generated_audits=[decode_document(r['body']) for r in rows(flow_engine,old.audit)
        if decode_document(r['body'])['event_type']=='GENERATED_LABEL_ARTIFACT_RETAINED']
    added=len(after[old.audit.name])-len(before[old.audit.name]);assert added==(1 if mode=='no_control' else 2)
    assert rows(flow_engine,original_statement_contents)==original_bytes
    assert len(after['customer_scope_audit_events'])-len(before['customer_scope_audit_events'])==int(mode=='bound_evidence')
    assert not rows(flow_engine,contents)
    if mode=='no_control':
        assert not rows(flow_engine,controls) and not rows(flow_engine,artifacts) and not generated_audits
    else:
        control,=rows(flow_engine,controls);receipt=decode_document(control['source_withdrawal_receipt']);p=receipt['payload']
        assert control['epoch']==prior_control[0]['epoch']+1 and control['state']=='RETAINED' and control['active_claim_id'] is None
        assert p['trigger_kind']=='CASE_WIDE_CUSTOMER_CONTENT_RETENTION' and p['trigger_object_id']==target
        cascade=p['cascade_trigger'];assert cascade['subject_records']==p['source_removal']['subject_records']
        assert cascade['removed_record_ids']==p['source_removal']['removed_record_ids']
        assert cascade['accepted_input_version']>rows(flow_engine,labels)[0]['input_version']
        assert len(generated_audits)==(2 if mode=='pdf_removed' else 1)
        if prior_meta:
            meta,=rows(flow_engine,artifacts)
            assert meta['completion_hash']==prior_meta[0]['completion_hash'] and meta['core']==prior_meta[0]['core'] and meta['certificate']==prior_meta[0]['certificate']
            if mode=='pdf_removed':
                assert meta['pdf_retention_receipt']==prior_meta[0]['pdf_retention_receipt']
                assert p['previous_retention_receipt_hash_or_None']==decode_document(prior_meta[0]['pdf_retention_receipt'])['receipt_hash']
                assert meta['removal_reason']=='OWNER_REQUEST' and meta['retention_state']=='REDACTED'
    observed=recover(caller,args);assert observed.status==('REPLAYED' if prior_meta else 'RETAINED')
    prior=snapshot(flow_engine);assert RetentionService(flow_engine).remove(kind,target) is False;assert snapshot(flow_engine)==prior
    if mode!='no_control':
        # A second lawful later subject still uses the old policy, preserving
        # the first generated source receipt and epoch without another audit.
        saved=rows(flow_engine,controls)[0];first_generated=len(generated_audits);prior=snapshot(flow_engine)
        assert RetentionService(flow_engine).remove('STATEMENT',statements[1],reason='OWNER_REQUEST',redact=True)
        assert rows(flow_engine,controls)[0]==saved
        assert len(rows(flow_engine,old.audit))==len(prior[old.audit.name])+1
        assert len([r for r in rows(flow_engine,old.audit) if decode_document(r['body'])['event_type']=='GENERATED_LABEL_ARTIFACT_RETAINED'])==first_generated
    evidence(request.node.nodeid,mode=mode,protective_question_state=True,actual_customer_acceptance=True,
        result=asdict(observed),before=before,after=after)

@pytest.mark.parametrize('fault',['acceptance_fingerprint','customer_actor','orphan_ref','accepted_version','accepted_owner'])
def test_LA_P05_P10_later_retention_requires_actual_acceptance_and_customer_provenance(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities);assert complete(service(flow_engine,identities),args).status=='COMMITTED'
    statements,_=later_input(flow_engine,identities,args);target=statements[0]
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        record=uow.execute(select(old.history).where(old.history.c.object_id==target)).mappings().one()
        work=uow.execute(select(old.intake_work).where(old.intake_work.c.accepted_case_version==record['case_version'])).mappings().one()
        if fault=='acceptance_fingerprint':uow.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id==work['acceptance_id']).values(fingerprint='0'*64))
        elif fault=='orphan_ref':uow.execute(delete(old.receipt_refs).where(old.receipt_refs.c.acceptance_id==work['acceptance_id'],old.receipt_refs.c.object_id==target))
        elif fault=='accepted_version':uow.execute(update(old.intake_work).where(old.intake_work.c.work_id==work['work_id']).values(input_version=rows(flow_engine,labels)[0]['input_version']))
        elif fault=='accepted_owner':uow.execute(update(old.intake_work).where(old.intake_work.c.work_id==work['work_id']).values(accepted_owner_id=identities.people['customer_b']['principal_id']))
        else:
            # Hostile, self-consistent audit-chain fixture: the human actor is
            # false even though every subsequent chain hash is recomputed.
            previous=None
            for saved in uow.execute(select(old.audit).order_by(old.audit.c.sequence)).mappings():
                event=decode_document(saved['body'])
                if target in event['object_ids'] and event['event_type']=='CUSTOMER_CLARIFICATION_ACCEPTED':event['actor']={'kind':'SERVICE','component_id':'counterfeit_customer'}
                event.pop('event_hash')
                if previous is None:event.pop('previous_event_hash',None)
                else:event['previous_event_hash']=previous
                event['event_hash']=digest({'sequence':saved['sequence'],'event':event},'audit/v1')
                uow.execute(update(old.audit).where(old.audit.c.event_id==saved['event_id']).values(body=encode_document(event),event_hash=event['event_hash']))
                previous=event['event_hash']
            uow.execute(update(old.case_heads).values(audit_head=previous))
        uow.commit()
    before=snapshot(flow_engine)
    with pytest.raises(FlowError):RetentionService(flow_engine).remove('STATEMENT',target)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine),hostile_fixture=True)

@pytest.mark.parametrize('fault',['actor','object','reason','count','refs','same_trigger','late_trigger','pdf_source_capture'])
def test_LA_P10_actual_source_audit_relationship_and_pdf_null_capture_are_exact(flow_engine,identities,enabled,request,monkeypatch,fault):
    from returnops_domain import retention as service_module,label_artifact_retention as module
    args,_=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    statements,_=later_input(flow_engine,identities,args);target=statements[0]
    original=service_module.append_event
    def bad_event(uow,case_id,**kwargs):
        if kwargs['event_type']=='CUSTOMER_CONTENT_REMOVED':
            if fault=='actor':kwargs['actor']={'kind':'SERVICE','component_id':'fake_retention'}
            elif fault=='object':kwargs['object_ids']=['wrong_retained_subject']
            elif fault=='reason':kwargs['payload']={**kwargs['payload'],'reason':'OWNER_REQUEST'}
            elif fault=='count':kwargs['payload']={**kwargs['payload'],'revision_count':kwargs['payload']['revision_count']+1}
            elif fault=='refs':kwargs['history_refs']=[]
        return original(uow,case_id,**kwargs)
    monkeypatch.setattr(service_module,'append_event',bad_event)
    if fault in {'same_trigger','late_trigger','pdf_source_capture'}:
        original_receipt=module._receipt
        def bad_receipt(payload,event):
            changed=deepcopy(payload)
            if fault=='pdf_source_capture':changed['source_removal']={'subject_kind':'EVIDENCE','subject_records':[],'removed_record_ids':[]}
            else:
                changed['trigger_event_id']=event['event_id'] if fault=='same_trigger' else 'nonexistent_future_source_event'
                changed['trigger_event_hash']=event['event_hash']
            return original_receipt(changed,event)
        monkeypatch.setattr(module,'_receipt',bad_receipt)
    before=snapshot(flow_engine)
    with pytest.raises(FlowError):RetentionService(flow_engine).remove('EVIDENCE' if fault=='pdf_source_capture' else 'STATEMENT',
        result.label_evidence_id if fault=='pdf_source_capture' else target)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['label_flag','return_flag','lifecycle_flag','operation_body','preview_body','case_receipt_body','order_receipt_body','projection_body','input_reference','clarification_reference','generated_pdf'])
def test_LA_P10_complete_old_policy_postconditions_are_required(flow_engine,identities,enabled,request,monkeypatch,fault):
    from returnops_domain import label_artifact_retention as module
    from returnops_domain.return_execution_tables import controls as returns
    from returnops_domain.preview_tables import previews
    args,_=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    statements,_=later_input(flow_engine,identities,args);target=statements[0]
    original=module.finish_source_withdrawal;original_save=module._save
    def inject(uow,*a,**kw):
        if fault=='label_flag':uow.execute(update(labels).values(source_available=True))
        elif fault=='return_flag':uow.execute(update(returns).values(result_retained=True))
        elif fault=='lifecycle_flag':uow.execute(update(life.state).values(available=True))
        elif fault=='operation_body':
            record=uow.execute(select(old.history.c.record_id).where(old.history.c.kind=='OPERATION')).scalars().first();uow.execute(old.history_contents.insert().values(record_id=record,body=b'forbidden residual'))
        elif fault=='preview_body':uow.execute(update(previews).values(body=b'forbidden residual',available=True))
        elif fault=='case_receipt_body':uow.execute(update(old.receipts).where(old.receipts.c.acceptance_id.in_(select(old.acceptances.c.acceptance_id).where(old.acceptances.c.resource_kind=='CASE'))).values(body=b'forbidden residual',available=True))
        elif fault=='order_receipt_body':
            rid=uow.execute(select(inv.receipts.c.receipt_id)).scalars().first();uow.execute(inv.receipt_contents.insert().values(receipt_id=rid,body=b'forbidden residual'))
        elif fault=='projection_body':
            pid=uow.execute(select(inv.projections.c.projection_id)).scalars().first();uow.execute(inv.projection_contents.insert().values(projection_id=pid,body=b'forbidden residual'))
        elif fault=='input_reference':uow.execute(update(inv.inputs).values(reference=b'forbidden residual'))
        elif fault=='clarification_reference':
            existing=uow.execute(select(inv.clarification_inputs)).mappings().first()
            if existing is None:
                uow.execute(inv.clarification_inputs.insert().values(case_id=args['case_id'],input_version=2,
                    reference=b'forbidden residual',alternative=False,available=False))
            else:uow.execute(update(inv.clarification_inputs).values(reference=b'forbidden residual'))
        return original(uow,*a,**kw)
    def residual_pdf(uow,*a,**kw):
        receipt=original_save(uow,*a,**kw)
        uow.execute(contents.insert().values(evidence_id=result.label_evidence_id,body=b'forbidden residual'))
        return receipt
    monkeypatch.setattr(module,'finish_source_withdrawal',inject)
    if fault=='generated_pdf':monkeypatch.setattr(module,'_save',residual_pdf)
    before=snapshot(flow_engine)
    with pytest.raises(FlowError):RetentionService(flow_engine).remove('STATEMENT',target)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,before=before,after=snapshot(flow_engine))

def versioned_subject_fixture(engine,identities,args,target,*,mixed):
    """Synthetic versioned-history compatibility, not a new CustomerFlow route.

    Current CustomerFlow emits v1 per subject. This fixture constructs retained
    future-compatible versions with distinct persisted acceptance/intake facts
    and correctly chained customer origins, to exercise the >100 deletion bound.
    """
    from returnops_domain.history import append_revision
    from returnops_domain import idempotency
    with CustomerUnitOfWork(engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one())
        actor=customer(engine,identities).authority(uow.connection,'getSession')
        template=dict(uow.execute(select(old.intake_work).order_by(old.intake_work.c.created_at.desc())).mappings().first())
        existing=uow.execute(select(old.history).where(old.history.c.object_id==target).order_by(old.history.c.object_version.desc())).mappings().first()
        sequence=[];at=datetime.now(timezone.utc)
        for index in range(105):
            now=at+timedelta(microseconds=index+1);case_version=head['case_version']+index+1;input_version=head['input_version']+index+1
            uow.execute(update(old.case_heads).values(case_version=case_version,input_version=input_version))
            uow.execute(update(life.state).values(input_version=input_version))
            body=dict(statement_id=target,kind='CLARIFICATION',raw_text='Synthetic immutable version '+str(index),
                submitted_at=timestamp(now),question_id='compatibility_question')
            ref=append_revision(uow,args['case_id'],'STATEMENT',target,existing['object_version']+index+1,body,now)
            fingerprint=digest({'compatibility_version':index,'case_id':args['case_id']},'request/v1')
            acceptance=idempotency.record_acceptance(uow,actor,'submitClarification',args['case_id'],'compatibility-key-'+str(index),
                fingerprint,'CASE',args['case_id'],202,now)
            work={**template,'work_id':'compatibility_work_'+str(index),'acceptance_id':acceptance,'input_version':input_version,
                'created_at':now,'accepted_case_version':case_version,'source_refs':encode_document([ref]),
                'state':'PENDING','claim_id':None,'claimed_at':None,'lease_expires_at':None,'completed_at':None,
                'claim_epoch':0,'failure_count':0,'next_attempt_at':now,'safe_error':None}
            uow.execute(old.intake_work.insert().values(**work))
            append_event(uow,args['case_id'],actor={'kind':'HUMAN','role':'CUSTOMER','principal_id':actor.principal_id},
                event_type='CUSTOMER_CLARIFICATION_ACCEPTED',correlation_id='compatibility-correlation-'+str(index),
                payload={'acceptance_id':acceptance,'request_fingerprint':fingerprint,'work_id':work['work_id']},
                object_ids=[target],history_refs=[ref],now=now)
            idempotency.record_receipt(uow,acceptance,{'case_id':args['case_id'],'compatibility_fixture':True},[('CASE',args['case_id']),('STATEMENT',target)])
            sequence.append(ref['record_id'])
        if mixed:
            previous=sequence[:5]
            uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id.in_(previous)))
            uow.execute(update(old.history).where(old.history.c.record_id.in_(previous)).values(retention_state='REDACTED',removal_reason='OWNER_REQUEST'))
        uow.commit()

@pytest.mark.parametrize('path',['direct','later'])
@pytest.mark.parametrize('mixed',[False,True])
def test_LA_P10_complete_removal_capture_exceeds_100_refs_and_preserves_prior_tombstones(flow_engine,identities,enabled,request,path,mixed):
    args,_=ready(flow_engine,identities);assert complete(service(flow_engine,identities),args).status=='COMMITTED'
    statements,_=later_input(flow_engine,identities,args)
    target=statements[0] if path=='later' else rows(flow_engine,original_statement_contents)[0]['statement_id']
    versioned_subject_fixture(flow_engine,identities,args,target,mixed=mixed)
    previous=[r for r in rows(flow_engine,old.history) if r['object_id']==target and r['retention_state']!='AVAILABLE']
    before=snapshot(flow_engine);assert RetentionService(flow_engine).remove('STATEMENT',target)
    control,=rows(flow_engine,controls);receipt=decode_document(control['source_withdrawal_receipt']);p=receipt['payload'];capture=p['source_removal']
    assert len(capture['subject_records'])==106 and len(capture['removed_record_ids'])==(101 if mixed else 106)
    trigger=next(decode_document(r['body']) for r in rows(flow_engine,old.audit) if r['event_id']==p['trigger_event_id'])
    assert len(trigger['history_refs'])==100
    assert trigger['payload_hash']==digest({'kind':'STATEMENT','object_id':target,'reason':'RETENTION_POLICY',
        'revision_count':len(capture['removed_record_ids'])},'audit-payload/v1')
    assert p['trigger_kind']==('ORIGINAL_SOURCE_RETENTION' if path=='direct' else 'CASE_WIDE_CUSTOMER_CONTENT_RETENTION')
    current={r['record_id']:r for r in rows(flow_engine,old.history)}
    assert all(current[r['record_id']]==r for r in previous)
    prior=snapshot(flow_engine);assert RetentionService(flow_engine).remove('STATEMENT',target) is False;assert snapshot(flow_engine)==prior
    evidence(request.node.nodeid,path=path,mixed=mixed,synthetic_versioned_history=True,not_new_customer_business_route=True,
        receipt=receipt,before=before,after=prior)

@pytest.mark.parametrize('path',['direct','later'])
@pytest.mark.parametrize('fault',['missing_record','metadata_order','removed_order','extra_removed','cascade_relation'])
def test_LA_P10_captured_source_sets_and_order_cannot_be_forged(flow_engine,identities,enabled,request,monkeypatch,path,fault):
    from returnops_domain import label_artifact_retention as module
    args,_=ready(flow_engine,identities);assert complete(service(flow_engine,identities),args).status=='COMMITTED'
    statements,_=later_input(flow_engine,identities,args)
    target=statements[0] if path=='later' else rows(flow_engine,original_statement_contents)[0]['statement_id']
    versioned_subject_fixture(flow_engine,identities,args,target,mixed=False)
    original=module._payload
    def bad(*a,**kw):
        value=original(*a,**kw);capture=deepcopy(value['source_removal'])
        if fault=='missing_record':capture['subject_records']=capture['subject_records'][:-1]
        elif fault=='metadata_order':capture['subject_records']=list(reversed(capture['subject_records']))
        elif fault=='removed_order':capture['removed_record_ids']=list(reversed(capture['removed_record_ids']))
        elif fault=='extra_removed':capture['removed_record_ids'].append('unrelated_removed_record')
        elif path=='later':value['cascade_trigger']={**value['cascade_trigger'],'removed_record_ids':[]}
        else:value['cascade_trigger']={'profile':'forbidden_direct_cascade'}
        value['source_removal']=capture;return value
    monkeypatch.setattr(module,'_payload',bad);before=snapshot(flow_engine)
    with pytest.raises(FlowError):RetentionService(flow_engine).remove('STATEMENT',target)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,path=path,fault=fault,before=before,after=snapshot(flow_engine),synthetic_versioned_history=True)
