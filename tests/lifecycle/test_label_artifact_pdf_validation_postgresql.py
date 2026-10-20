"""P02/P08/P14: verify retained bytes without invoking any renderer alias."""
from dataclasses import asdict
from functools import wraps
from hashlib import sha256
import pytest
from sqlalchemy import select,update
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain.canonical import decode_document,encode_document,digest
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.label_artifact_tables import artifacts,contents,claims
from returnops_domain.label_artifact_history import certificate,origin_payload
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
from returnops_domain.generated_evidence import verify_certificate
from returnops_domain.retention import RetentionService
from label_artifact_helpers import ready,service,customer,complete,recover,claim,rows,snapshot,evidence,pdf_call_counts


def last_evidence_cursor(reader,case_id,evidence_id):
    """Prepare real public pagination before zero-write observation begins."""
    query=dict(kind='EVIDENCE',limit=1);page=reader.history(case_id,query).body;last=None
    while 'next_cursor' in page:
        last=page['next_cursor'];page=reader.history(case_id,{**query,'cursor':last}).body
    assert last is not None and len(page['items'])==1
    assert page['items'][0]['object_id']==evidence_id
    return {**query,'cursor':last}


def test_LA_P02_P08_P14_T3_and_all_retained_reads_use_verifier_not_renderer(flow_engine,identities,enabled,request):
    from returnops_domain import label_pdf as pdf,label_artifact_sources as sources
    # Capture aliases before profiling. A deliberate calibration is separate
    # from all actual business observations, whose renderer counts must be zero.
    aliases=(pdf.render_label_pdf,sources.render_label_pdf,pdf._text_line,pdf._assemble_pdf)
    calibration=[]
    for alias in aliases:
        with pytest.raises(AssertionError,match='Forbidden actual PDF/provider code'):
            with pdf_call_counts() as attempted:
                if alias is pdf.render_label_pdf:alias(pdf.LabelPdfFields('lab','ret','pkg'))
                elif alias is pdf._text_line:alias({}, {}, 'unused',0)
                else:alias({},())
        assert sum(attempted.values())==1
        calibration.append(attempted)
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority)
    assert reply.status=='FOUND'
    with pdf_call_counts() as completion_calls:
        completed=caller._complete(ticket,reply.content,'zero-render-T3')
    assert completed.status=='COMMITTED',asdict(completed)
    assert completion_calls['validation']>0
    assert all(completion_calls[n]==0 for n in ('render','text_line','assembly','expected_pdf','artifact_retrieval','return_provider','label_provider'))
    reader=customer(flow_engine,identities);query=last_evidence_cursor(reader,args['case_id'],completed.label_evidence_id)
    observations=[];original_meta=rows(flow_engine,artifacts)[0];original_claims=rows(flow_engine,claims)
    statement=next(r for r in rows(flow_engine,old.history) if r['kind']=='STATEMENT')['object_id']
    for state in ('available','pdf_removed','source_withdrawn'):
        if state=='pdf_removed':assert RetentionService(flow_engine).remove('EVIDENCE',completed.label_evidence_id)
        elif state=='source_withdrawn':assert RetentionService(flow_engine).remove('STATEMENT',statement)
        before=snapshot(flow_engine)
        with pdf_call_counts(forbid_validation=state!='available',forbid_removed_dto=state=='source_withdrawn') as calls:
            recovered=recover(caller,args);repeated=complete(caller,args)
            assert recovered.status==repeated.status=='REPLAYED'
            assert recovered.content_available==repeated.content_available==(state=='available')
            if state=='available':
                assert reader.download(completed.label_evidence_id).body==(reply.content,'application/pdf')
            else:
                with pytest.raises(FlowError) as denied:reader.download(completed.label_evidence_id)
                assert denied.value.code=='NOT_FOUND'
            page=reader.history(args['case_id'],query)
            assert page.status==200 and len(page.body['items'])==1 and 'next_cursor' not in page.body
            with CustomerUnitOfWork(flow_engine,write=False) as uow:
                seal=verify_certificate(uow,completed.label_evidence_id)
                assert seal['content']==(reply.content if state=='available' else None)
                if state=='source_withdrawn':assert seal['evidence_body'] is seal['result_body'] is None
                uow.commit()
        assert all(calls[n]==0 for n in ('render','text_line','assembly','expected_pdf','artifact_retrieval','return_provider','label_provider'))
        assert (calls['validation']>0)==(state=='available')
        assert snapshot(flow_engine)==before and rows(flow_engine,claims)==original_claims
        meta=rows(flow_engine,artifacts)[0]
        assert all(meta[n]==original_meta[n] for n in ('core','certificate','completion_hash'))
        observations.append(dict(state=state,result=asdict(recovered),actual_code_calls=calls,snapshot=before))
    evidence(request.node.nodeid,alias_guard_calibration=calibration,T3_actual_code_calls=completion_calls,observations=observations)


def forge_profile_bytes(engine,kind):
    """Hostile fixture synchronizes every retained hash except fixed PDF meaning.

    The production verifier must be reached: a stale certificate or an unsigned
    changed body is not a witness for the fixed-profile validation boundary.
    """
    from returnops_domain.label_execution_tables import ledger
    with CustomerUnitOfWork(engine,write=True) as uow:
        meta=dict(uow.execute(select(artifacts)).mappings().one())
        raw=bytes(uow.execute(select(contents.c.body)).scalar_one())
        fact=uow.execute(select(ledger)).mappings().one()
        if kind=='watermark':
            old_token='SIMULATED'.encode('cp1252').hex().upper().encode('ascii')
            new_token='XIMULATED'.encode('cp1252').hex().upper().encode('ascii')
        elif kind=='original_label_id':
            field=fact['provider_label_id'][:40]
            old_token=field.encode('ascii').hex().upper().encode('ascii')
            new_token=(('X' if field[0]!='X' else 'Y')+field[1:]).encode('ascii').hex().upper().encode('ascii')
        elif kind=='font':old_token,new_token=b'/BaseFont /Helvetica',b'/BaseFont /Courier  '
        elif kind=='coordinate':old_token,new_token=b'1 0 0 1 56 734 Tm',b'1 0 0 1 57 734 Tm'
        else:old_token,new_token=b'> Tj\nET',b'> XX\nET'
        assert old_token in raw and len(old_token)==len(new_token)
        forged=raw.replace(old_token,new_token,1);assert len(forged)==len(raw) and forged!=raw
        hashed=sha256(forged).hexdigest()
        er=uow.execute(select(old.history_contents).where(old.history_contents.c.record_id==meta['evidence_record_id'])).mappings().one()
        eb=decode_document(er['body']);eb['sha256']=hashed
        evidence_hash=digest(eb,'history/v1')
        uow.execute(update(contents).values(body=forged))
        uow.execute(update(old.history_contents).where(old.history_contents.c.record_id==meta['evidence_record_id']).values(body=encode_document(eb)))
        uow.execute(update(old.history).where(old.history.c.record_id==meta['evidence_record_id']).values(content_sha256=evidence_hash))
        core=decode_document(meta['core']);core.update(sha256=hashed,evidence_content_hash=evidence_hash)
        origins={};previous=None
        for saved in uow.execute(select(old.audit).order_by(old.audit.c.sequence)).mappings():
            event=decode_document(saved['body']);event.pop('event_hash')
            if saved['event_id'] in {meta['evidence_audit_id'],meta['result_audit_id']}:
                slot='EVIDENCE' if saved['event_id']==meta['evidence_audit_id'] else 'RESULT'
                event['payload_hash']=digest(origin_payload(core,slot),'audit-payload/v1')
            if previous is None:event.pop('previous_event_hash',None)
            else:event['previous_event_hash']=previous
            event['event_hash']=digest({'sequence':saved['sequence'],'event':event},'audit/v1')
            uow.execute(update(old.audit).where(old.audit.c.event_id==saved['event_id']).values(body=encode_document(event),event_hash=event['event_hash']))
            previous=event['event_hash'];origins[saved['event_id']]=event
        cert=certificate(core,origins[meta['evidence_audit_id']],origins[meta['result_audit_id']])
        uow.execute(update(artifacts).values(sha256=hashed,core=encode_document(core),core_hash=digest(core,'label-artifact-completion-core/v1'),
            certificate=encode_document(cert),completion_hash=digest(cert,'label-artifact-completion/v1'),
            evidence_audit_hash=cert['evidence_origin']['event_hash'],result_audit_hash=cert['result_origin']['event_hash']))
        uow.execute(update(life.effects).where(life.effects.c.artifact_evidence_id==meta['evidence_id']).values(artifact_sha256=hashed))
        uow.execute(update(old.case_heads).values(audit_head=previous));uow.commit()
    return dict(original_sha256=sha256(raw).hexdigest(),forged_sha256=hashed,
        evidence_content_hash=evidence_hash,completion_hash=digest(cert,'label-artifact-completion/v1'))


def test_LA_P02_P08_P14_T3_fixed_profile_failure_is_safe_and_writes_nothing(flow_engine,identities,enabled,request):
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    content=reply.content.replace(b'1 0 0 1 56 734 Tm',b'1 0 0 1 57 734 Tm',1)
    assert content!=reply.content and len(content)==len(reply.content)
    before=snapshot(flow_engine)
    with pdf_call_counts() as calls:result=caller._complete(ticket,content,'invalid-profile-T3')
    assert result.status=='DENIED' and result.safe_code=='INVALID_STATE' and calls['validation']==1
    assert all(calls[n]==0 for n in ('render','text_line','assembly','expected_pdf','artifact_retrieval','return_provider','label_provider'))
    assert snapshot(flow_engine)==before and not rows(flow_engine,artifacts) and not rows(flow_engine,contents)
    evidence(request.node.nodeid,result=asdict(result),actual_code_calls=calls,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('fault',['watermark','original_label_id','font','coordinate','unknown_operator'])
def test_LA_P02_P08_P14_self_consistent_pdf_forgery_reaches_fixed_profile_rejection(flow_engine,identities,enabled,request,monkeypatch,fault):
    from returnops_domain import label_pdf_validation as validation
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities)
    result=complete(caller,args);assert result.status=='COMMITTED'
    forged=forge_profile_bytes(flow_engine,fault);before=snapshot(flow_engine)
    actual_verifier=validation.verify_label_pdf;profile_rejections=[]
    @wraps(actual_verifier)
    def witnessed_validation(content,fields):
        try:return actual_verifier(content,fields)
        except ValueError as error:
            assert str(error)=='Invalid fixed-profile label PDF'
            profile_rejections.append(sha256(content).hexdigest())
            raise
    monkeypatch.setattr(validation,'verify_label_pdf',witnessed_validation)
    with pdf_call_counts() as calls:
        denied=recover(caller,args)
    assert denied.status=='DENIED' and denied.safe_code=='INVALID_STATE',asdict(denied)
    assert calls['validation']>0 and profile_rejections==[forged['forged_sha256']]*calls['validation']
    assert all(calls[n]==0 for n in ('render','text_line','assembly','expected_pdf','artifact_retrieval','return_provider','label_provider'))
    assert snapshot(flow_engine)==before
    reader=customer(flow_engine,identities)
    for action in ('download','history'):
        rejection_count=len(profile_rejections)
        with pdf_call_counts() as read_calls:
            with pytest.raises(FlowError) as refusal:
                if action=='download':reader.download(result.label_evidence_id)
                else:reader.history(args['case_id'],dict(kind='EVIDENCE',limit=20))
        assert refusal.value.code=='INVALID_STATE' and read_calls['validation']>0
        assert profile_rejections[rejection_count:]==[forged['forged_sha256']]*read_calls['validation']
        assert all(read_calls[n]==0 for n in ('render','text_line','assembly','expected_pdf','artifact_retrieval','return_provider','label_provider'))
        assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,self_consistent_forgery=forged,result=asdict(denied),
        actual_code_calls=calls,actual_fixed_verifier_rejected_hashes=profile_rejections,before_corrupted=before,after=snapshot(flow_engine))
