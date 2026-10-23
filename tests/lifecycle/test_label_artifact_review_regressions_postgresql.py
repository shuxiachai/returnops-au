"""Independent-review F1/F2/F4/F5/F6 regression witnesses, real fenced PG."""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,update,delete
from sqlalchemy.exc import IntegrityError
from returnops_domain import customer_tables as old,lifecycle_tables as life,founder_codec as finite
from returnops_domain.audit import append_event
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.label_artifact_tables import artifacts,contents,controls
from returnops_domain.label_execution_tables import controls as label_controls
from returnops_domain.lifecycle_schema import LABEL,ARTIFACT
from returnops_domain.registry import TrustedRegistry
from label_artifact_helpers import ready,service,customer,complete,recover,claim,rows,snapshot,evidence
from conftest import migrate

def test_LA_P11_real_original_bridge_effect_producer_is_exact_and_replays_without_growth(flow_engine,identities,enabled,request,monkeypatch):
    from return_label_bridge_helpers import ready as bridge_ready,service as bridge_service,accept
    from returnops_domain.return_execution_sources import authorize
    from returnops_domain.return_label_sources import read_source,identity,retained_acceptance
    from returnops_domain.core_return_mock import CoreReturnMock
    from returnops_domain.core_label_mock import CoreLabelMock
    args,_=bridge_ready(flow_engine,identities);caller=bridge_service(flow_engine,identities);calls=[]
    def forbidden(*a,**kw):calls.append('provider invoked');raise AssertionError('Bridge acceptance/replay does not call a provider')
    monkeypatch.setattr(CoreReturnMock,'perform',forbidden);monkeypatch.setattr(CoreLabelMock,'perform',forbidden)
    assert not [r for r in rows(flow_engine,life.work) if r['purpose']=='EFFECT']
    before=snapshot(flow_engine);accepted=accept(caller,args)
    assert accepted.status=='ACCEPTED',asdict(accepted)
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        authorization=authorize(uow,caller.authority,args['case_id'],create=False)
        source=read_source(uow,authorization,args['execution_work_id'],args['original_approval_key'])
        assert source is not None
        ids=identity(authorization[0],authorization[1],source)
        saved=retained_acceptance(uow,authorization[1],source,ids)
        assert saved is not None
        actual=[dict(r) for r in uow.execute(select(life.work).where(life.work.c.case_id==args['case_id'],
            life.work.c.purpose=='EFFECT').order_by(life.work.c.work_id)).mappings()]
        assert actual==[saved['work']] and saved['work']['work_id']==ids['work_id']
        assert saved['work']['state']=='DONE' and saved['work']['epoch']==1
        assert saved['receipt']['event_id']==accepted.event_id and saved['binding']['record_id']==accepted.source_record_id
        uow.commit()
    after=snapshot(flow_engine);replayed=accept(caller,args)
    assert replayed.status=='REPLAYED' and replayed.event_id==accepted.event_id and snapshot(flow_engine)==after and calls==[]
    evidence(request.node.nodeid,accepted=asdict(accepted),replayed=asdict(replayed),provider_calls=calls,
        exact_bridge_work_id=ids['work_id'],before=before,after=after)

@pytest.mark.parametrize('fault',['missing_input','extra_generated','wrong_case'])
def test_LA_P05_P06_P11_original_approval_receipt_refs_are_exact_not_subset(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities)
    label,=rows(flow_engine,label_controls)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        key=label['approval_acceptance_id']
        if fault=='missing_input':
            ref=uow.execute(select(old.receipt_refs).where(old.receipt_refs.c.acceptance_id==key,old.receipt_refs.c.kind=='EVIDENCE')).mappings().first()
            assert ref is not None
            changed=uow.execute(delete(old.receipt_refs).where(old.receipt_refs.c.acceptance_id==key,
                old.receipt_refs.c.kind==ref['kind'],old.receipt_refs.c.object_id==ref['object_id']))
        elif fault=='extra_generated':
            injected=dict(acceptance_id=key,kind='EVIDENCE',object_id='glabel_'+'c'*64)
            previous_refs=[dict(row) for row in uow.execute(select(old.receipt_refs)).mappings()]
            ref_key=lambda row:(row['acceptance_id'],row['kind'],row['object_id'])
            expected_refs=sorted([*previous_refs,injected],key=ref_key)
            changed=uow.execute(old.receipt_refs.insert().values(**injected).returning(*old.receipt_refs.c))
            assert dict(changed.mappings().one())==injected
        else:changed=uow.execute(update(old.receipt_refs).where(old.receipt_refs.c.acceptance_id==key,old.receipt_refs.c.kind=='CASE').values(object_id='foreign_case_identity'))
        if fault!='extra_generated':assert changed.rowcount==1
        uow.commit()
    before=snapshot(flow_engine)
    if fault=='extra_generated':assert sorted(before[old.receipt_refs.name],key=ref_key)==expected_refs
    result=complete(service(flow_engine,identities),args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before and not rows(flow_engine,artifacts)
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['missing_content','missing_metadata','raw_text','requested_outcome','object_version','accepted_input','submitted_at','statement_id'])
def test_LA_P05_actual_original_statement_storage_cannot_be_replaced_by_history_copy(flow_engine,identities,enabled,request,fault):
    from returnops_domain.storage import original_statement_records as records,original_statement_contents as content
    args,_=ready(flow_engine,identities)
    if fault in {'object_version','accepted_input','statement_id'}:
        before=snapshot(flow_engine)
        values={'object_version':2} if fault=='object_version' else {'accepted_input_version':2} if fault=='accepted_input' else {'statement_id':'wrong_physical_statement'}
        with pytest.raises(IntegrityError) as denied:
            with flow_engine.begin() as connection:connection.execute(update(records).values(**values))
        assert denied.value.orig.diag.constraint_name and snapshot(flow_engine)==before
        evidence(request.node.nodeid,fault=fault,enforced_by='existing0002 database constraint',before=before,after=snapshot(flow_engine))
        return
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if fault=='missing_content':statement=delete(content)
        elif fault=='missing_metadata':
            assert uow.execute(delete(content)).rowcount==1
            statement=delete(records)
        elif fault=='raw_text':statement=update(content).values(raw_text=b'Changed real source despite unchanged historical copy.')
        elif fault=='requested_outcome':statement=update(content).values(requested_outcome='REFUND')
        elif fault=='object_version':statement=update(records).values(object_version=2)
        elif fault=='accepted_input':statement=update(records).values(accepted_input_version=2)
        elif fault=='submitted_at':statement=update(records).values(submitted_at=datetime(2000,1,1,tzinfo=timezone.utc))
        else:statement=update(records).values(statement_id='wrong_physical_statement')
        assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities),args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['fake_generated_history','extra_generated_origin','extra_operation','extra_effect','extra_effect_producer'])
def test_LA_P06_P11_full_generated_history_origin_operation_effect_and_producer_inventory(flow_engine,identities,enabled,request,fault):
    from returnops_domain.label_artifact_history import append_record
    args,_=ready(flow_engine,identities);first=complete(service(flow_engine,identities),args);assert first.status=='COMMITTED'
    meta,=rows(flow_engine,artifacts)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one());now=datetime.now(timezone.utc)
        if fault=='extra_effect':
            value=dict(uow.execute(select(life.effects)).mappings().first());value['operation_id']='extra_operation_effect'
            uow.execute(life.effects.insert().values(**value))
        elif fault=='extra_effect_producer':
            state=uow.execute(select(life.state)).mappings().one()
            uow.execute(life.work.insert().values(work_id='extra_effect_producer',case_id=head['case_id'],component_id='unregistered_effect_producer',
                store_id=head['store_id'],owner_id=head['owner_principal_id'],purpose='EFFECT',input_version=head['input_version'],generation=state['generation'],
                target_hash='f'*64,target_record_id=None,state='PENDING',claim_id=None,epoch=0,claimed_case_version=None,authority_revision=None,
                idempotency_key='extra_effect_producer',lease_expires_at=None,created_at=now))
        elif fault=='extra_generated_origin':
            record=uow.execute(select(old.history).where(old.history.c.record_id==meta['evidence_record_id'])).mappings().one()
            ref={n:record[n] for n in ('record_id','kind','object_id','object_version')}
            append_event(uow,head['case_id'],actor={'kind':'SERVICE','component_id':'operations-label-artifact-v1'},event_type='GENERATED_LABEL_EVIDENCE_BOUND',
                correlation_id='extra_generated_origin',payload={'forged':True},object_ids=[record['object_id']],history_refs=[ref],now=record['recorded_at'])
        else:
            target=meta['evidence_record_id'] if fault=='fake_generated_history' else meta['result_record_id']
            raw=uow.execute(select(old.history_contents.c.body).where(old.history_contents.c.record_id==target)).scalar_one()
            if fault=='fake_generated_history':
                body=decode_document(raw);body.update(evidence_id='glabel_'+'d'*64,content_path='/v1/evidence/glabel_'+'d'*64+'/content')
                kind='EVIDENCE';object_id=body['evidence_id']
            else:
                body=finite.decode_document(raw);body.update(operation_id='extra_original_operation');kind='OPERATION';object_id=body['operation_id']
            append_record(uow,head,'extra_history_record',kind,object_id,1,body,{'forged':True},'extra_history_origin',now)
        uow.commit()
    before=snapshot(flow_engine);result=recover(service(flow_engine,identities),args)
    # Duplicate genuine-name origins are CaseProof corruption (503); exact
    # union and absent certificate failures are explicit INVALID_STATE (409).
    expected='UNKNOWN' if fault=='extra_generated_origin' else 'DENIED'
    assert result.status==expected and snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('target',['missing','other_customer','other_store','corrupt_body','corrupt_certificate','owner','founder','anonymous'])
def test_LA_P04_P14_generated_download_authorizes_scope_before_certificate_and_never_falls_back(flow_engine,identities,enabled,request,monkeypatch,target):
    from returnops_domain import generated_evidence as generated
    from returnops_domain.customer_service import CustomerFlow
    from returnops_api.customer_authority import CurrentRequestAuthority
    args,_=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    evidence_id=result.label_evidence_id;name='customer_a'
    if target=='missing':evidence_id='glabel_'+'e'*64
    elif target in {'other_customer','other_store'}:name='customer_b'
    elif target=='founder':name='founder'
    if target=='other_store':TrustedRegistry(flow_engine).change_principal(identities.people['customer_b']['principal_id'],store_id='foreign_store_scope')
    if target in {'corrupt_body','corrupt_certificate'}:
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            uow.execute(update(contents).values(body=b'corrupt') if target=='corrupt_body' else update(artifacts).values(certificate=b'corrupt'))
            uow.commit()
    calls=[];original=generated.resolve
    def observed(*a,**kw):calls.append('authorized full certificate');return original(*a,**kw)
    monkeypatch.setattr(generated,'resolve',observed);before=snapshot(flow_engine)
    caller=CustomerFlow(flow_engine,CurrentRequestAuthority(identities.auth_config,None)) if target=='anonymous' else customer(flow_engine,identities,name)
    if target in {'owner','founder'}:
        assert caller.download(evidence_id).status==200 and calls
    else:
        with pytest.raises(FlowError) as failure:caller.download(evidence_id)
        expected={'anonymous':401,'missing':404,'other_customer':404,'other_store':404,'corrupt_body':409,'corrupt_certificate':503}[target]
        assert failure.value.status==expected
        assert bool(calls)==(target in {'corrupt_body','corrupt_certificate'})
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,target=target,certificate_reads=len(calls),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('flow_engine',[LABEL],indirect=True)
def test_LA_P03_P11_0012_reserved_pattern_customer_evidence_survives_rejected_upgrade(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain import customer_service as module
    from returnops_domain.evidence_validation import validate_evidence
    from returnops_domain.label_pdf import LabelPdfFields,render_label_pdf
    from returnops_domain.retention import RetentionService
    original=module.identifier;reserved='glabel_'+'a'*64
    monkeypatch.setattr(module,'identifier',lambda prefix:reserved if prefix=='evidence' else original(prefix))
    pdf=render_label_pdf(LabelPdfFields('legacy_label_identity','legacy_return_identity','legacy_parcel_identity'))
    staged=customer(flow_engine,identities).stage(validate_evidence(pdf,'legacy.pdf','application/pdf'),'legacy-upload-key','legacy-upload-correlation')
    assert staged.body['evidence_id']==reserved
    before=snapshot(flow_engine)
    with pytest.raises(RuntimeError,match='namespace is occupied'):migrate(flow_engine,ARTIFACT)
    assert snapshot(flow_engine)==before
    assert customer(flow_engine,identities).download(reserved).body==(pdf,'application/pdf')
    created=customer(flow_engine,identities).create(dict(original_message='A legal existing0012 customer attachment.',evidence_ids=[reserved]),
        'legacy-case-key','legacy-case-correlation')
    case=created.body['case_id'];assert created.body['evidence'][0]['evidence_id']==reserved
    assert customer(flow_engine,identities).history(case,{'kind':'EVIDENCE'}).body['items'][0]['content']['evidence_id']==reserved
    assert customer(flow_engine,identities,'founder').download(reserved).body==(pdf,'application/pdf')
    assert RetentionService(flow_engine).remove('EVIDENCE',reserved)
    with pytest.raises(FlowError) as unavailable:customer(flow_engine,identities).download(reserved)
    assert unavailable.value.status==404
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),old0012_legal_customer_namespace=True)

def test_LA_P07_session_expiry_after_final_slow_source_read_rolls_back_completion(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain import label_artifact as module,label_artifact_sources as sources
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=claim(caller,args)
    reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    deadline=datetime.fromtimestamp(identities.sessions['founder']['expires_at'],timezone.utc)
    original=module.closure;original_check=sources.check_session_time;seen=[]
    def check(now,bounds):
        if now==deadline:seen.append('fresh session time after slow read')
        return original_check(now,bounds)
    def slow(uow,case_id):
        saved=original(uow,case_id)
        if saved[artifacts.name]:
            monkeypatch.setattr(sources,'database_now',lambda u:deadline)
            monkeypatch.setattr(module,'database_now',lambda u:deadline)
        return saved
    monkeypatch.setattr(sources,'check_session_time',check);monkeypatch.setattr(module,'closure',slow)
    before=snapshot(flow_engine);result=caller._complete(ticket,reply.content,'last-read-session-expiry')
    assert result.status=='DENIED' and seen and snapshot(flow_engine)==before
    evidence(request.node.nodeid,result=asdict(result),final_session_checks=seen,before=before,after=snapshot(flow_engine))
