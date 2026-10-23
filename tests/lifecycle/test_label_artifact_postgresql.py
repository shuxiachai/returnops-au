"""P01/P02/P04–P06/P11/P12/P14/P15/P19 actual artifact service boundaries."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import io
import pytest
from sqlalchemy import select,update,delete
from returnops_domain import customer_tables as old,lifecycle_tables as life,founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.canonical import decode_document,digest
from returnops_domain.label_artifact_tables import controls,claims,artifacts,contents,permissions
from returnops_domain.label_artifact_sources import COMPONENT
from returnops_domain.label_execution_tables import ledger,permissions as creation_permissions
from returnops_domain.generated_evidence import verify_certificate,partition_evidence
from returnops_domain.founder_integrity import CaseProof
from returnops_domain.registry import TrustedRegistry
from label_artifact_helpers import ready,service,customer,complete,recover,assert_delta,rows,snapshot,evidence,claim

def test_LA_P01_P02_P06_P15_exact_success_wire_pdf_partition_and_acyclic_receipt(flow_engine,identities,enabled,request):
    from pypdf import PdfReader
    args,_=ready(flow_engine,identities);before=snapshot(flow_engine)
    result=complete(service(flow_engine,identities),args);after=assert_delta(flow_engine,before,result)
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        seal=verify_certificate(uow,result.label_evidence_id)
        head=seal['head'];proof=CaseProof(uow,head);inputs,outputs=partition_evidence(uow,proof)
        assert len(outputs)==1 and outputs[0]['object_id']==result.label_evidence_id
        assert {r['object_id'] for r in inputs}=={r['evidence_id'] for r in before[old.evidence.name]}
        rb=seal['result_body'];fact=seal['fact'];core=seal['core']
        assert rb['result']==dict(type='GENERATE_LABEL',provider_label_id=fact['provider_label_id'],parcel_id=fact['parcel_id'],label_evidence_id=result.label_evidence_id)
        assert rb['attempt_count']==1 and rb['case_version']==seal['label']['dispatch_case_version']
        assert set(core).isdisjoint({'completion_hash','certificate','available','retention_state','pdf_retention_receipt','source_withdrawal_receipt'})
        assert core['evidence_content_hash']==seal['evidence_record']['content_sha256']
        assert digest(seal['certificate'],'label-artifact-completion/v1')==seal['row']['completion_hash']
        pdf=seal['content'];uow.commit()
    reader=PdfReader(io.BytesIO(pdf),strict=True)
    assert len(reader.pages)==1 and pdf.startswith(b'%PDF-') and len(pdf)<=65536
    text=reader.pages[0].extract_text();assert 'SIMULATED' in text and 'NOT VALID FOR POSTAGE' in text
    for name in ('customer_a','founder'):
        downloaded=customer(flow_engine,identities,name).download(result.label_evidence_id)
        assert downloaded.body==(pdf,'application/pdf')
    caller=service(flow_engine,identities);prior=snapshot(flow_engine)
    assert complete(caller,args).status==recover(caller,args).status=='REPLAYED' and snapshot(flow_engine)==prior
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        actor=customer(flow_engine,identities).authority(uow.connection,'getSession')
        with pytest.raises(FlowError):customer(flow_engine,identities)._eligible_evidence(uow,actor,[result.label_evidence_id],seal['row']['completed_at'])
    evidence(request.node.nodeid,result=asdict(result),before=before,after=after,pdf_sha256=sha256(pdf).hexdigest())

@pytest.mark.parametrize('fault',['anonymous','customer','wrong_key','wrong_case','wrong_principal','missing_grants','read_disabled','store_disabled','service_disabled','session_revoked','profile_hash'])
def test_LA_P04_current_independent_authority_denies_no_claim(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities,grants=fault!='missing_grants');name='founder'
    if fault=='anonymous':name=None
    elif fault=='customer':name='customer_a'
    elif fault=='wrong_key':args['original_approval_key']='different-original-approval-key'
    elif fault=='wrong_case':args['case_id']='other_case_identity'
    elif fault=='wrong_principal':
        # F.03 identity is real; the original approval principal remains fixed.
        TrustedRegistry(flow_engine).change_principal(identities.people['customer_b']['principal_id'],role='FOUNDER')
        name='customer_b'
    elif fault=='session_revoked':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    elif fault in {'read_disabled','store_disabled','service_disabled','profile_hash'}:
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            statement=(update(life.authorities).where(life.authorities.c.component_id==COMPONENT).values(enabled=False,revision=2)
                if fault=='service_disabled' else update(permissions).values(**({'read_existing_enabled':False,'revision':2} if fault=='read_disabled'
                else {'store_enabled':False,'revision':2} if fault=='store_disabled' else {'profile_hash':'0'*64})))
            assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities,name),args)
    assert result.status=='DENIED' and snapshot(flow_engine)==before and rows(flow_engine,controls)==[]
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

def test_LA_P04_old_creation_disabled_and_expired_approval_do_not_authorize_or_block_artifact(flow_engine,identities,enabled,monkeypatch,request):
    from returnops_domain import label_artifact_sources as sources,label_artifact as service_module
    from returnops_domain.preview_tables import previews
    args,_=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        uow.execute(update(creation_permissions).values(create_enabled=False,query_enabled=False,revision=2))
        expires=uow.execute(select(previews.c.expires_at).where(previews.c.consuming_decision_record_id.is_not(None))).scalar_one()
        uow.commit()
    future=expires+timedelta(seconds=1)
    monkeypatch.setattr(sources,'database_now',lambda uow:future);monkeypatch.setattr(service_module,'database_now',lambda uow:future)
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities),args)
    assert_delta(flow_engine,before,result)
    evidence(request.node.nodeid,result=asdict(result),before=before,after=snapshot(flow_engine),expired_original_preview=True)

@pytest.mark.parametrize('fault',['confirmation_body','ledger_hash','approval_body','proposal_body','bridge_event','artifact_work_binding'])
def test_LA_P05_full_original_sources_fail_closed(flow_engine,identities,enabled,request,fault):
    from returnops_domain.label_execution_tables import artifact_work
    args,_=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if fault=='ledger_hash':statement=update(ledger).values(fact_hash='0'*64)
        elif fault=='artifact_work_binding':statement=update(artifact_work).values(binding_hash='0'*64)
        elif fault=='bridge_event':statement=update(life.events).where(life.events.c.event_kind=='RETURN_SOURCE').values(fingerprint='0'*64)
        else:
            kind={'confirmation_body':'OPERATION','approval_body':'APPROVAL','proposal_body':'PROPOSAL'}[fault]
            target=uow.execute(select(old.history.c.record_id).where(old.history.c.kind==kind).order_by(old.history.c.recorded_sequence.desc())).scalars().first()
            statement=update(old.history_contents).where(old.history_contents.c.record_id==target).values(body=b'corrupt-original-source')
        assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities),args)
    assert result.status==('UNKNOWN' if fault.endswith('_body') else 'DENIED') and snapshot(flow_engine)==before and not rows(flow_engine,artifacts)
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('fault',['missing_body','changed_body','missing_certificate','changed_certificate','missing_effect'])
def test_LA_P14_corruption_is_not_retention_or_repair(flow_engine,identities,enabled,request,fault):
    args,_=ready(flow_engine,identities);first=complete(service(flow_engine,identities),args);assert first.status=='COMMITTED'
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        statement=(delete(life.effects).where(life.effects.c.operation_type=='GENERATE_LABEL') if fault=='missing_effect' else delete(contents) if fault=='missing_body' else update(contents).values(body=b'%PDF-corrupt') if fault=='changed_body'
            else update(artifacts).values(certificate=b'' if fault=='missing_certificate' else b'counterfeit'))
        assert uow.execute(statement).rowcount==1;uow.commit()
    before=snapshot(flow_engine);result=recover(service(flow_engine,identities),args)
    assert result.status==('UNKNOWN' if fault.endswith('certificate') else 'DENIED') and snapshot(flow_engine)==before
    with pytest.raises(FlowError):customer(flow_engine,identities).download(first.label_evidence_id)
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,fault=fault,result=asdict(result),before=before,after=snapshot(flow_engine))

def test_LA_P11_original_N1_N2_bridge_N3_replay_reports_v4_without_provider(flow_engine,identities,enabled,monkeypatch,request):
    from preparation_helpers import service as prepare
    from create_return_execution_helpers import service as returns,reconcile as return_reconcile
    from return_label_bridge_helpers import service as bridge,accept
    from label_execution_helpers import service as labels,execute,reconcile
    from returnops_domain.core_label_mock import CoreLabelMock
    from returnops_domain.core_return_mock import CoreReturnMock
    args,setup=ready(flow_engine,identities);result=complete(service(flow_engine,identities),args);assert result.status=='COMMITTED'
    def forbidden(*a,**k):raise AssertionError('Replay must not create or query a provider')
    monkeypatch.setattr(CoreLabelMock,'perform',forbidden);monkeypatch.setattr(CoreReturnMock,'perform',forbidden)
    before=snapshot(flow_engine);up=setup['upstream']
    results=[prepare(flow_engine,identities).prepare(**up['upstream']),return_reconcile(returns(flow_engine,identities),up['upstream']),
        accept(bridge(flow_engine,identities),up['bridge_arguments']),execute(labels(flow_engine,identities),setup['label_args']),
        reconcile(labels(flow_engine,identities),setup['label_args'])]
    assert all(r.status=='REPLAYED' for r in results) and all(r.operation_state=='SUCCEEDED' for r in results[-2:])
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,results=[asdict(r) for r in results],before=before,after=snapshot(flow_engine))

@pytest.mark.parametrize('status',['NOTIFICATION_PENDING','COMPLETED'])
def test_LA_P12_historical_terminal_fixture_preserves_all_business_pointers(flow_engine,identities,enabled,request,status):
    from returnops_domain.lifecycle_state import invalidate
    args,_=ready(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one());invalidate(uow,head)
        uow.execute(update(old.case_heads).values(case_version=head['case_version']+1,status=status))
        uow.execute(update(life.state).values(outcome='MANUAL_HANDLED',notification_id='existing_notification_identity',
            notification_hash='a'*64,notification_work_id='existing_notification_work'))
        uow.commit()
    before=snapshot(flow_engine);result=complete(service(flow_engine,identities),args);assert_delta(flow_engine,before,result)
    after=snapshot(flow_engine)
    assert after[life.state.name]==before[life.state.name]
    evidence(request.node.nodeid,protective_fixture=True,not_a_new_terminal_business_route=True,result=asdict(result),before=before,after=after)

@pytest.mark.parametrize('claim_first',[False,True])
def test_LA_P19_genuine_later_customer_acceptance_is_separate_from_original_bundle(flow_engine,identities,enabled,request,claim_first):
    from returnops_domain.canonical import encode_document
    from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
    args,_=ready(flow_engine,identities);caller=service(flow_engine,identities);ticket=None;reply=None
    if claim_first:
        ticket=claim(caller,args);reply=CoreLabelArtifactMock(flow_engine).retrieve_original_label(ticket,caller.authority);assert reply.status=='FOUND'
    # Protective placement into an existing CustomerFlow input state. The
    # actual subsequent statement/acceptance/audit comes from the real API.
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        head=dict(uow.execute(select(old.case_heads)).mappings().one())
        question=dict(question_id='later_source_question',text='Provide additional context.',reason='Protective fixture for independent later input.')
        uow.execute(old.questions.insert().values(question_set_id='later_source_questions',case_id=args['case_id'],
            input_version=head['input_version'],questions=encode_document([question]),question_kinds=encode_document({'later_source_question':'TEXT_RESPONSE'})))
        uow.execute(update(old.case_heads).values(status='AWAITING_INFORMATION',current_question_set_id='later_source_questions'))
        uow.commit()
    body=dict(expected_case_version=head['case_version'],question_set_id='later_source_questions',
        answers=[dict(question_id='later_source_question',text='An independent later customer clarification.')],evidence_ids=[])
    accepted=customer(flow_engine,identities).clarify(args['case_id'],body,'later-source-key','later-source-correlation')
    assert accepted.status==202
    before=snapshot(flow_engine)
    if claim_first:
        assert caller._complete(ticket,reply.content,'old-input-claim').status=='DENIED' and snapshot(flow_engine)==before
    result=complete(caller,args);assert result.status=='COMMITTED'
    assert rows(flow_engine,old.case_heads)[0]['input_version']==head['input_version']+1
    evidence(request.node.nodeid,protective_input_state=True,actual_customer_acceptance=True,claim_first=claim_first,
        result=asdict(result),before=before,after=snapshot(flow_engine))
