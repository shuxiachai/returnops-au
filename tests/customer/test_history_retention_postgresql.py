"""Real PG snapshots, tombstones, retention copies and atomic audit failures."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import io
import pytest
from PIL import Image
from sqlalchemy import func,select,update
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier,timestamp,verify_chain
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.history import append_revision
from returnops_domain.intake_processor import IntakeProcessor,IntakeResult
from returnops_domain.retention import RetentionService
from returnops_domain.scope_audit import verify_scope_chain
from returnops_domain.storage import original_statement_contents

def png():
    target=io.BytesIO();Image.new('RGB',(1,1)).save(target,format='PNG');return target.getvalue()

def test_history_over100_snapshot_membership_cursor_filter_and_original_retained(flow_engine,identities):
    flow=identities.flow();accepted=flow.create({'original_message':'original'},'create-key',identifier('corr')).body;case=accepted['case_id']
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        for index in range(125):
            statement=identifier('statement');content={'statement_id':statement,'kind':'CLARIFICATION','question_id':'question_internal',
                'raw_text':'internal synthetic revision '+str(index),'submitted_at':timestamp(datetime.now(timezone.utc))}
            append_revision(uow,case,'STATEMENT',statement,1,content,datetime.now(timezone.utc))
        uow.commit()
    view=flow.get_case(case).body;window=view['collection_windows']['statements']
    assert window['total_records']==126 and window['preview_count']==100 and window['truncated']
    assert view['statements'][0]['kind']=='ORIGINAL'
    cursor=window['start_cursor'];records=[]
    while True:
        page=flow.history(case,{'kind':'STATEMENT','cursor':cursor}).body
        records+=page['items']
        assert page['snapshot_id']==window['snapshot_id']
        if 'next_cursor' not in page: break
        cursor=page['next_cursor']
    assert len(records)==126 and len({r['record_id'] for r in records})==126
    assert [r['recorded_sequence'] for r in records]==list(range(1,127))
    # An old snapshot never admits a newer revision.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        statement=identifier('statement');append_revision(uow,case,'STATEMENT',statement,1,
            {'statement_id':statement,'kind':'CLARIFICATION','question_id':'question_internal','raw_text':'later','submitted_at':timestamp(datetime.now(timezone.utc))},datetime.now(timezone.utc));uow.commit()
    first=flow.history(case,{'kind':'STATEMENT','cursor':window['start_cursor']}).body
    assert first['snapshot_id']==window['snapshot_id']
    with pytest.raises(FlowError) as e: flow.history(case,{'kind':'STATEMENT','cursor':window['start_cursor'],'limit':100})
    assert e.value.code=='INVALID_STATE'
    filtered=flow.history(case,{'kind':'STATEMENT','object_id':records[0]['object_id'],'object_version':1}).body
    assert len(filtered['items'])==1

def test_retention_tombstones_old_snapshots_and_invalidates_original_receipt(flow_engine,identities):
    flow=identities.flow();request={'original_message':'private original\x00\ud800'}
    accepted=flow.create(request,'create-key',identifier('corr')).body;case=accepted['case_id'];statement=accepted['statements'][0]['statement_id']
    query={'kind':'STATEMENT','cursor':accepted['collection_windows']['statements']['start_cursor']}
    before=flow.history(case,query).body['items'][0]
    assert RetentionService(flow_engine).remove('STATEMENT',statement,reason='OWNER_REQUEST')
    after=flow.history(case,query).body['items'][0]
    assert after['record_id']==before['record_id'] and after['content_sha256']==before['content_sha256']
    assert after['retention_state']=='DELETED' and 'content' not in after
    current=flow.get_case(case).body
    assert current['statements']==[] and current['collection_windows']['statements']['total_records']==1
    assert current['collection_windows']['statements']['unavailable_count']==1
    for value,code in [(request,'INVALID_STATE'),({'original_message':'changed'},'IDEMPOTENCY_CONFLICT')]:
        with pytest.raises(FlowError) as e: flow.create(value,'create-key',identifier('corr'))
        assert e.value.code==code
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert uow.execute(select(func.count()).select_from(original_statement_contents)).scalar_one()==0
        assert uow.execute(select(func.count()).select_from(t.history_contents)).scalar_one()==0
        assert verify_chain(uow,case);uow.commit()
    assert not IntakeProcessor(flow_engine).run_once()

def test_evidence_removal_prevents_download_replay_and_late_processor(flow_engine,identities):
    flow=identities.flow();material=validate_evidence(png(),'private-name.png','image/png','private-description')
    staged=flow.stage(material,'stage-key',identifier('corr')).body;eid=staged['evidence_id']
    accepted=flow.create({'original_message':'original','evidence_ids':[eid]},'create-key',identifier('corr')).body
    worker=IntakeProcessor(flow_engine);claim=worker.claim()
    assert RetentionService(flow_engine).remove('EVIDENCE',eid,redact=True)
    assert not worker.finish(claim,IntakeResult())
    with pytest.raises(FlowError) as e: flow.download(eid)
    assert e.value.code=='NOT_FOUND'
    with pytest.raises(FlowError) as e: flow.stage(material,'stage-key',identifier('corr'))
    assert e.value.code=='NOT_FOUND'
    with pytest.raises(FlowError) as e: flow.create({'original_message':'original','evidence_ids':[eid]},'create-key',identifier('corr'))
    assert e.value.code=='INVALID_STATE'
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        row=uow.execute(select(t.evidence).where(t.evidence.c.evidence_id==eid)).mappings().one()
        assert row['filename']==b'' and row['description'] is None and not row['available']
        assert uow.execute(select(func.count()).select_from(t.evidence_contents)).scalar_one()==0
        assert verify_scope_chain(uow,'EVIDENCE',eid);assert verify_chain(uow,accepted['case_id']);uow.commit()

def test_audit_failure_rolls_back_all_retention_changes(flow_engine,identities,monkeypatch):
    import returnops_domain.retention as module
    flow=identities.flow();body=flow.create({'original_message':'original'},'create-key',identifier('corr')).body
    def fail(*a,**kw): raise FlowError('INTERNAL_ERROR')
    monkeypatch.setattr(module,'append_event',fail)
    with pytest.raises(FlowError): RetentionService(flow_engine).remove('STATEMENT',body['statements'][0]['statement_id'])
    assert flow.get_case(body['case_id']).body['statements']==body['statements']
    assert flow.create({'original_message':'original'},'create-key',identifier('corr')).body==body
    with flow_engine.connect() as c: assert c.execute(select(t.intake_work.c.state)).scalar_one()=='PENDING'

def test_staged_expiry_and_internal_cleanup_are_atomic_scope_audited(flow_engine,identities):
    now=datetime.now(timezone.utc);flow=identities.flow(clock=lambda:now,staged_ttl=1)
    body=flow.stage(validate_evidence(png(),'file.png','image/png'),'stage-key',identifier('corr')).body
    later=now+timedelta(seconds=2)
    assert RetentionService(flow_engine,clock=lambda:later).expire_staged()==1
    assert RetentionService(flow_engine,clock=lambda:later).expire_staged()==0
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert verify_scope_chain(uow,'EVIDENCE',body['evidence_id']);uow.commit()

def test_snapshot_cursor_expiry_is_not_reissued_for_replay(flow_engine,identities):
    now=datetime.now(timezone.utc);flow=identities.flow(clock=lambda:now,snapshot_ttl=1)
    body=flow.create({'original_message':'original'},'create-key',identifier('corr')).body
    now+=timedelta(seconds=2)
    assert flow.create({'original_message':'original'},'create-key',identifier('corr')).body==body
    with pytest.raises(FlowError) as e: flow.history(body['case_id'],{'kind':'STATEMENT','cursor':body['collection_windows']['statements']['start_cursor']})
    assert e.value.code=='INVALID_STATE'
    fresh=flow.get_case(body['case_id']).body
    assert fresh['collection_windows']['statements']['snapshot_id']!=body['collection_windows']['statements']['snapshot_id']
