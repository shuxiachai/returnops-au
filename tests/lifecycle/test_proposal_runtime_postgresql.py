"""Actual fixed runtime over real customer/order input; no future producer fixture."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
import subprocess
import sys
from pypdf import PdfWriter
import pytest
from sqlalchemy import inspect, select, text, update, delete, event as sqlalchemy_event
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain import customer_tables as old, investigation_tables as investigation, lifecycle_tables as t
from returnops_domain import founder_codec as finite
from returnops_domain.audit import append_event, identifier, timestamp
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown, FlowError
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.fixed_proposal import build_fixed_proposal, CAPACITY_MESSAGE, ProposalCapacityError
from returnops_domain.founder_service import FounderQueries
from returnops_domain.history import append_revision
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.lifecycle_events import LifecycleClaim, ProposalAccepted
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.proposal_policy import COMPONENT, FixedProposalPolicy, stable_id
from returnops_domain.proposal_processor import FixedProposalProcessor, Intent, _ProposalUnitOfWork
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService


def now():return datetime.now(timezone.utc)


def rows(engine,table):
    with engine.connect() as connection:return list(connection.execute(select(table)).mappings())


def founder(engine,identities,name='founder'):
    return FounderQueries(engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens[name]))


def ready(engine,identities,*,reference='SYN-1001',evidence_ids=None,grant=True):
    request={'original_message':'  retained synthetic original\x00\ud800  ','requested_outcome':'RETURN'}
    if reference is not None:request['order_reference']=reference
    if evidence_ids is not None:request['evidence_ids']=evidence_ids
    case=identities.flow().create(request,identifier('create'),identifier('corr')).body['case_id']
    assert IntakeProcessor(engine).run_once()
    assert InvestigationProcessor(engine).run_once()
    if grant:FixedProposalPolicy(engine).grant('synthetic_au_store',synthetic_demo=True,enabled=True)
    return case


def saved_bundle(engine):
    record=next(row for row in rows(engine,old.history) if row['kind']=='PROPOSAL')
    raw=next(row['body'] for row in rows(engine,old.history_contents) if row['record_id']==record['record_id'])
    return finite.decode_document(raw)


def fingerprints(engine):
    with engine.connect() as connection:
        return {name:sha256(repr(sorted((tuple(row) for row in connection.execute(text('SELECT * FROM "'+name+'"'))),key=repr)).encode('utf-8','surrogatepass')).hexdigest()
                for name in inspect(connection).get_table_names() if not name.startswith('founder_')}


def add_retained_clarifications(engine,identities,case,count):
    """Explicit historical capacity fixture; runtime production remains real."""
    with CustomerUnitOfWork(engine,write=True) as uow:
        for number in range(count):
            at=now();statement=identifier('retained_statement')
            body=dict(statement_id=statement,kind='CLARIFICATION',question_id='synthetic-capacity-question',
                      raw_text='Complete retained historical clarification '+str(number),submitted_at=timestamp(at))
            ref=append_revision(uow,case,'STATEMENT',statement,1,body,at)
            append_event(uow,case,actor={'kind':'HUMAN','role':'CUSTOMER','principal_id':identities.people['customer_a']['principal_id']},
                event_type='CUSTOMER_CLARIFICATION_ACCEPTED',correlation_id=identifier('corr'),
                payload={'explicit_capacity_fixture':True},object_ids=[statement],history_refs=[ref],now=at)
        uow.commit()


def test_actual_order_to_fixed_packet_and_founder_four_reads(flow_engine,identities,enabled):
    case=ready(flow_engine,identities)
    order_receipts=rows(flow_engine,investigation.receipts);order_bytes=rows(flow_engine,investigation.receipt_contents)
    accepted=rows(flow_engine,old.receipts)
    worker=FixedProposalProcessor(flow_engine)
    assert worker.run_once() and not worker.run_once()
    bundle=saved_bundle(flow_engine);state=rows(flow_engine,t.state)[0]
    assert bundle['statements'][0]['raw_text']=='  retained synthetic original\x00\ud800  '
    assert bundle['packet']['original_statement_id']==bundle['statements'][0]['statement_id']
    assert bundle['order_lookup']['input_version']==2 and order_receipts[0]['input_version']==1
    assert rows(flow_engine,investigation.receipts)==order_receipts and rows(flow_engine,investigation.receipt_contents)==order_bytes
    assert rows(flow_engine,old.receipts)==accepted
    assert rows(flow_engine,t.sources)[0]['order_projection_id']==rows(flow_engine,investigation.projections)[0]['projection_id']
    assert state['proposal_record_id']==rows(flow_engine,t.events)[0]['record_id']
    assert rows(flow_engine,t.work)[0]['state']=='DONE'
    assert {row['purpose'] for row in rows(flow_engine,t.authorities)}=={'PROPOSAL'}
    assert not any(row['kind'] in {'REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION'} for row in rows(flow_engine,old.history))
    before=fingerprints(flow_engine);reader=founder(flow_engine,identities)
    detail=reader.read('getFounderCase',case).body
    assert detail['status']=='RISK_REVIEW' and detail['current_proposal']==bundle['packet']
    assert detail['cited_passages']==bundle['retrieval_result']['passages']
    reader.read('listFounderCases');reader.read('listFounderCaseHistory',case,{'kind':'PROPOSAL'});reader.read('listCaseAudit',case)
    assert fingerprints(flow_engine)==before
    with pytest.raises(FlowError) as denied:founder(flow_engine,identities,'customer_a').read('getFounderCase',case)
    assert denied.value.code=='FORBIDDEN'


def test_real_clarification_is_preserved_and_original_order_receipts_do_not_change(flow_engine,identities,enabled):
    case=ready(flow_engine,identities,reference=None)
    view=identities.flow().get_case(case).body;group=rows(flow_engine,investigation.groups)[0]
    identities.flow().clarify(case,dict(expected_case_version=view['case_version'],question_set_id=view['clarification']['question_set_id'],
        answers=[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],evidence_ids=[]),identifier('clarify'),identifier('corr'))
    assert IntakeProcessor(flow_engine).run_once() and InvestigationProcessor(flow_engine).run_once()
    previous=rows(flow_engine,investigation.receipt_contents)
    assert FixedProposalProcessor(flow_engine).run_once()
    body=saved_bundle(flow_engine)
    assert len(body['statements'])==2 and {item['kind'] for item in body['statements']}=={'ORIGINAL','CLARIFICATION'}
    assert next(item for item in body['statements'] if item['kind']=='CLARIFICATION')['raw_text']=='SYN-1001'
    assert rows(flow_engine,investigation.receipt_contents)==previous


@pytest.mark.parametrize('count,expected',[ (99,'ACCEPTED'),(100,'FAILED') ])
def test_actual_retained_capacity_boundary_and_failure_target(flow_engine,identities,enabled,count,expected):
    case=ready(flow_engine,identities);add_retained_clarifications(flow_engine,identities,case,count)
    original=rows(flow_engine,old.history);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    result=worker.process(intent)
    assert result.status==expected
    assert rows(flow_engine,old.history)[:len(original)]==original
    detail=founder(flow_engine,identities).read('getFounderCase',case).body
    if expected=='ACCEPTED':
        assert len(saved_bundle(flow_engine)['statements'])==100 and detail['status']=='RISK_REVIEW'
    else:
        assert detail['status']=='ESCALATED' and 'current_proposal' not in detail
        failure=detail['processing_failure']
        assert failure['stage']=='ASSESSMENT' and failure['error']['error']['code']=='REQUEST_TOO_LARGE'
        assert failure['error']['error']['retryable'] is False and failure['error']['error']['message']==CAPACITY_MESSAGE
        assert rows(flow_engine,t.events)[0]['event_kind']=='PROPOSAL_FAILED'
        assert not any(row['kind']=='PROPOSAL' for row in rows(flow_engine,old.history))
        assert worker.process(intent).status=='FAILED'
        work=rows(flow_engine,t.work)[0];receipt=rows(flow_engine,t.events)[0]
        claim=LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],work['input_version'],work['generation'],work['authority_revision'])
        with CustomerUnitOfWork(flow_engine,write=True) as uow:
            with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,ProposalAccepted(receipt['event_id'],claim,receipt['record_id']),now())


@pytest.mark.parametrize('mutation',['omit_statement','statement','order','citation_hash','citation_location','passage'])
def test_real_processor_rejects_complete_source_or_citation_tampering(flow_engine,identities,enabled,mutation):
    case=ready(flow_engine,identities);before=rows(flow_engine,old.history)
    def tampered(*args):
        body=build_fixed_proposal(*args)
        if mutation=='omit_statement':body['statements']=[]
        elif mutation=='statement':body['statements'][0]['raw_text']='fabricated source'
        elif mutation=='order':body['order_lookup']['snapshot']['order_id']='fabricated-order'
        elif mutation=='citation_hash':body['packet']['citations'][0]['content_sha256']='f'*64
        elif mutation=='citation_location':body['packet']['citations'][0]['location']='wrong-location'
        else:body['retrieval_result']['passages'][0]['content']+='tampered'
        return body
    worker=FixedProposalProcessor(flow_engine,build=tampered);intent=worker.prepare(case)
    result=worker.process(intent)
    assert result.status=='DENIED' and rows(flow_engine,old.history)==before
    assert rows(flow_engine,t.events)==[] and rows(flow_engine,t.sources)==[]
    assert rows(flow_engine,t.work)[0]['state']=='PAUSED'
    assert rows(flow_engine,old.case_heads)[0]['status']=='POLICY_ASSESSMENT'


@pytest.mark.parametrize('mutation',['omit','bytes','metadata'])
def test_actual_attachment_metadata_and_bytes_are_required(flow_engine,identities,enabled,mutation):
    pdf=PdfWriter();pdf.add_blank_page(width=100,height=100);buffer=BytesIO();pdf.write(buffer)
    accepted=identities.flow().stage(validate_evidence(buffer.getvalue(),'proof.pdf','application/pdf'),identifier('upload'),identifier('corr'))
    evidence=accepted.body['evidence_id'];case=ready(flow_engine,identities,evidence_ids=[evidence])
    worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case);before=rows(flow_engine,old.history)
    if mutation=='bytes':
        with flow_engine.begin() as connection:connection.execute(update(old.evidence_contents).where(old.evidence_contents.c.evidence_id==evidence).values(body=b'corrupt'))
    else:
        def tampered(*args):
            body=build_fixed_proposal(*args)
            if mutation=='omit':
                body['attachments']=[]
                body['evidence_matrix'][0]['evidence_ids']=[];body['packet']['evidence_matrix'][0]['evidence_ids']=[]
            else:body['attachments'][0]['filename']='changed.pdf'
            return body
        worker.build=tampered
    assert worker.process(intent).status=='DENIED'
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]


def test_explicit_grant_required_no_startup_or_processor_grant(flow_engine,identities,enabled):
    ready(flow_engine,identities,grant=False)
    worker=FixedProposalProcessor(flow_engine)
    assert not worker.run_once() and rows(flow_engine,t.authorities)==[] and rows(flow_engine,t.work)==[]
    with pytest.raises(FlowError):FixedProposalPolicy(flow_engine).grant('synthetic_au_store',synthetic_demo=False,enabled=True)


@pytest.mark.parametrize('revocation',['grant','owner','retention'])
def test_current_authority_or_retention_loss_prevents_new_packet_and_denial_audit(flow_engine,identities,enabled,revocation):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    if revocation=='grant':FixedProposalPolicy(flow_engine).grant('synthetic_au_store',synthetic_demo=True,enabled=False)
    elif revocation=='owner':TrustedRegistry(flow_engine).change_principal(identities.people['customer_a']['principal_id'],enabled=False)
    else:RetentionService(flow_engine).remove('STATEMENT',rows(flow_engine,old.history)[0]['object_id'])
    before=len(rows(flow_engine,old.audit));result=worker.process(intent)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED'
    assert len(rows(flow_engine,old.audit))==before and rows(flow_engine,t.events)==[]
    assert not any(row['kind']=='PROPOSAL' for row in rows(flow_engine,old.history))


def test_two_workers_share_stable_intent_and_one_source_receipt(flow_engine,identities,enabled):
    from threading import Event, Lock, local
    from manual_helpers import evidence
    from returnops_domain.proposal_processor import ProcessingResult
    case=ready(flow_engine,identities)
    prepare_held=Event();release_prepare=Event();process_held=Event();release_process=Event()
    context=local();capture_lock=Lock();sqlstates=[];attempt_results={};terminal_results={};snapshots={}
    checked={'prepare_same_intent':False,'prepare_recovery_no_growth':False,
             'process_recovery_no_growth':False,'both_accepted':False,'unique_work_event_source':False}
    def summary(value):
        return dict(type=type(value).__name__,status=getattr(value,'status',None),
            work_id=getattr(value,'work_id',None),safe_code=getattr(value,'safe_code',None),
            audit=getattr(value,'audit',None))
    def diagnostics():
        with capture_lock:states=list(sqlstates)
        return dict(attempt_results=dict(attempt_results),terminal_results=dict(terminal_results),
            sqlstates=states,checked=dict(checked),all_table_fingerprints=dict(snapshots))
    def capture_error(error_context):
        state=getattr(error_context.original_exception,'sqlstate',None)
        state=state if type(state) is str and len(state)==5 and state.isalnum() else 'UNAVAILABLE'
        compiled=getattr(getattr(error_context,'execution_context',None),'compiled',None)
        statement=getattr(compiled,'statement',None)
        is_fence=getattr(statement,'text',None)=='SELECT pg_advisory_xact_lock(:key)'
        with capture_lock:sqlstates.append(dict(phase=getattr(context,'phase','UNASSIGNED'),
            worker=getattr(context,'worker',None),sqlstate=state,exclusive_fence_statement=is_fence))
    def in_phase(phase,worker,operation,*args):
        context.phase=phase;context.worker=worker
        return operation(*args)
    def all_tables():
        with flow_engine.connect() as connection:
            names=sorted(inspect(connection).get_table_names())
            result={}
            for name in names:
                assert name.replace('_','').isalnum()
                values=connection.execute(text('SELECT * FROM "'+name+'"')).all()
                result[name]=sha256(repr(sorted((tuple(row) for row in values),key=repr)).encode(
                    'utf-8','surrogatepass')).hexdigest()
            return result
    def observe_uows(worker,observed):
        original=worker._uow
        def factory(*,resolve=False):
            value=original(resolve=resolve)
            observed.append(value)
            return value
        worker._uow=factory
    def assert_closed_rollback(observed):
        assert len(observed)==1,diagnostics()
        uow=observed[0]
        assert type(uow) is _ProposalUnitOfWork and uow.lock_timeout_ms==500,diagnostics()
        assert uow.finished and uow.connection is not None and uow.connection.closed,diagnostics()
        assert uow.transaction is not None and not uow.transaction.is_active,diagnostics()
    class HoldPrepareCommit(_ProposalUnitOfWork):
        def commit(self):
            assert self.lock_timeout_ms==500
            prepare_held.set()
            assert release_prepare.wait(timeout=10),'Prepare winner release handshake timed out'
            super().commit()
    def hold_build(*args):
        process_held.set()
        assert release_process.wait(timeout=10),'Process winner release handshake timed out'
        return build_fixed_proposal(*args)
    prepare_a=FixedProposalProcessor(flow_engine,uow_factory=HoldPrepareCommit)
    prepare_b=FixedProposalProcessor(flow_engine)
    prepare_uows=[];observe_uows(prepare_b,prepare_uows)
    sqlalchemy_event.listen(flow_engine,'handle_error',capture_error)
    try:
        snapshots['before_prepare']=all_tables()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(in_phase,'prepare',0,prepare_a.prepare,case)
            try:
                assert prepare_held.wait(timeout=10),'Prepare winner did not hold its actual transaction fence'
                second=pool.submit(in_phase,'prepare',1,prepare_b.prepare,case)
                prepare_loser=second.result(timeout=10)
                attempt_results['prepare_loser']=summary(prepare_loser)
                assert type(prepare_loser) is ProcessingResult,diagnostics()
                assert (prepare_loser.status,prepare_loser.work_id,prepare_loser.safe_code,prepare_loser.audit)==(
                    'RETRYABLE',None,'INTERNAL_ERROR','NOT_ATTEMPTED'),diagnostics()
                assert_closed_rollback(prepare_uows)
                assert sqlstates==[dict(phase='prepare',worker=1,sqlstate='55P03',exclusive_fence_statement=True)],diagnostics()
                snapshots['after_prepare_loser_while_winner_uncommitted']=all_tables()
                assert snapshots['after_prepare_loser_while_winner_uncommitted']==snapshots['before_prepare'],diagnostics()
            finally:
                release_prepare.set()
            prepare_winner=first.result(timeout=10)
        attempt_results['prepare_winner']=summary(prepare_winner)
        assert type(prepare_winner) is Intent,diagnostics()
        snapshots['before_prepare_recovery']=all_tables()
        recovered_intent=in_phase('prepare-recovery',1,prepare_b.prepare,case)
        terminal_results['prepare_recovery']=summary(recovered_intent)
        assert type(recovered_intent) is Intent,diagnostics()
        intents=[prepare_winner,recovered_intent]
        same_intent=intents[0]==intents[1]
        assert same_intent,diagnostics()
        assert intents[0].work_id==intents[1].work_id
        checked['prepare_same_intent']=True
        snapshots['after_prepare_recovery']=all_tables()
        assert snapshots['after_prepare_recovery']==snapshots['before_prepare_recovery'],diagnostics()
        checked['prepare_recovery_no_growth']=True
        process_a=FixedProposalProcessor(flow_engine,build=hold_build)
        process_b=FixedProposalProcessor(flow_engine)
        process_uows=[];observe_uows(process_b,process_uows)
        snapshots['before_process']=all_tables()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(in_phase,'process',0,process_a.process,intents[0])
            try:
                assert process_held.wait(timeout=10),'Process winner did not hold its actual transaction fence'
                second=pool.submit(in_phase,'process',1,process_b.process,intents[1])
                process_loser=second.result(timeout=10)
                attempt_results['process_loser']=summary(process_loser)
                assert type(process_loser) is ProcessingResult,diagnostics()
                assert (process_loser.status,process_loser.work_id,process_loser.safe_code,process_loser.audit)==(
                    'RETRYABLE',intents[1].work_id,'INTERNAL_ERROR','NOT_ATTEMPTED'),diagnostics()
                assert_closed_rollback(process_uows)
                assert sqlstates==[
                    dict(phase='prepare',worker=1,sqlstate='55P03',exclusive_fence_statement=True),
                    dict(phase='process',worker=1,sqlstate='55P03',exclusive_fence_statement=True)],diagnostics()
                snapshots['after_process_loser_while_winner_uncommitted']=all_tables()
                assert snapshots['after_process_loser_while_winner_uncommitted']==snapshots['before_process'],diagnostics()
            finally:
                release_process.set()
            process_winner=first.result(timeout=10)
        attempt_results['process_winner']=summary(process_winner)
        assert type(process_winner) is ProcessingResult and process_winner.status=='ACCEPTED',diagnostics()
        assert process_winner.work_id==intents[0].work_id,diagnostics()
        snapshots['before_process_resolution']=all_tables()
        recovered=in_phase('process-resolution',1,process_b.resolve,intents[1])
        terminal_results['process_winner']=summary(process_winner)
        terminal_results['process_resolution']=summary(recovered)
        assert type(recovered) is ProcessingResult and recovered.work_id==intents[1].work_id,diagnostics()
        results=[process_winner,recovered]
        assert all(result.status=='ACCEPTED' for result in results)
        checked['both_accepted']=True
        snapshots['after_process_resolution']=all_tables()
        assert snapshots['after_process_resolution']==snapshots['before_process_resolution'],diagnostics()
        checked['process_recovery_no_growth']=True
        assert len(rows(flow_engine,t.work))==len(rows(flow_engine,t.events))==len(rows(flow_engine,t.sources))==1
        work=rows(flow_engine,t.work)[0];receipt=rows(flow_engine,t.events)[0];source=rows(flow_engine,t.sources)[0]
        assert work['work_id']==intents[0].work_id and work['state']=='DONE' and work['epoch']==1,diagnostics()
        assert receipt['event_id']==stable_id('event',intents[0].work_id),diagnostics()
        assert receipt['record_id']==source['record_id']==stable_id('source',intents[0].work_id),diagnostics()
        assert receipt['work_id']==source['work_id']==intents[0].work_id,diagnostics()
        checked['unique_work_event_source']=True
    finally:
        release_prepare.set();release_process.set()
        sqlalchemy_event.remove(flow_engine,'handle_error',capture_error)
        evidence('tests/lifecycle/test_proposal_runtime_postgresql.py::test_two_workers_share_stable_intent_and_one_source_receipt',
            contract_scope='DETERMINISTIC_REAL_FENCE_TIMEOUT_AND_EXPLICIT_SAME_IDENTITY_RECOVERY',
            default_clock_and500ms_unchanged=True,unknown_or_denied_never_retried=True,**diagnostics())


@pytest.mark.parametrize('actual_commit',[True,False])
def test_unknown_business_commit_resolves_exact_intent_without_new_ids(flow_engine,identities,enabled,actual_commit):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    class LostAcknowledgement(CustomerUnitOfWork):
        def commit(self):
            if actual_commit:super().commit()
            else:self.transaction.rollback();self.finished=True
            raise AcceptanceOutcomeUnknown()
    worker.uow_factory=LostAcknowledgement
    audit_before=len(rows(flow_engine,old.audit));result=worker.process(intent)
    assert result.status==('ACCEPTED' if actual_commit else 'PENDING')
    assert result.work_id==intent.work_id
    if not actual_commit:
        assert len(rows(flow_engine,old.audit))==audit_before and rows(flow_engine,t.events)==[]
        assert FixedProposalProcessor(flow_engine).process(intent).status=='ACCEPTED'
    assert len(rows(flow_engine,t.events))==1 and rows(flow_engine,t.events)[0]['event_id']==stable_id('event',intent.work_id)
    assert rows(flow_engine,t.events)[0]['record_id']==stable_id('source',intent.work_id)


@pytest.mark.parametrize('actual_commit',[True,False])
def test_unknown_initial_intent_never_invents_replacement_identity(flow_engine,identities,enabled,actual_commit):
    case=ready(flow_engine,identities)
    class LostAcknowledgement(CustomerUnitOfWork):
        def commit(self):
            if actual_commit:super().commit()
            else:self.transaction.rollback();self.finished=True
            raise AcceptanceOutcomeUnknown()
    result=FixedProposalProcessor(flow_engine,uow_factory=LostAcknowledgement).prepare(case)
    assert (type(result) is Intent) if actual_commit else result.status=='ROLLED_BACK'
    assert rows(flow_engine,t.events)==[]
    recovered=FixedProposalProcessor(flow_engine).prepare(case)
    assert recovered.work_id==result.work_id and len(rows(flow_engine,t.work))==1


def test_unknown_resolution_failure_stays_unknown_and_never_audits_denial(flow_engine,identities,enabled):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    class LostAcknowledgement(CustomerUnitOfWork):
        def commit(self):super().commit();raise AcceptanceOutcomeUnknown()
    class CannotResolve(CustomerUnitOfWork):
        def __enter__(self):raise FlowError('INTERNAL_ERROR')
    worker.uow_factory=LostAcknowledgement;worker.resolve_uow=CannotResolve
    assert worker.process(intent).status=='UNKNOWN' and worker._uncertain==intent
    assert worker.run_once() is False
    assert len(rows(flow_engine,t.events))==1
    worker.resolve_uow=CustomerUnitOfWork
    assert worker.resolve(intent).status=='ACCEPTED'
    assert not any(decode_document(row['body'])['event_type']=='LIFECYCLE_GUARD_DENIED' for row in rows(flow_engine,old.audit))


def test_expiring_lease_rolls_back_source_claim_and_current_pointer(flow_engine,identities,enabled):
    case=ready(flow_engine,identities);clock=[now()]
    def slow(*args):
        body=build_fixed_proposal(*args);clock[0]+=timedelta(seconds=301);return body
    worker=FixedProposalProcessor(flow_engine,clock=lambda:clock[0],build=slow);intent=worker.prepare(case)
    before=rows(flow_engine,old.history)
    assert worker.process(intent).status=='DENIED'
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]
    assert rows(flow_engine,t.work)[0]['epoch']==0 and rows(flow_engine,t.state)[0]['proposal_record_id'] is None


@pytest.mark.parametrize('mutation',['grant','owner','source','generation','claim','input'])
def test_commit_boundary_rechecks_fenced_sources_and_authority(flow_engine,identities,enabled,mutation):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    before=rows(flow_engine,old.history)
    class MutatingCommit(CustomerUnitOfWork):
        def commit(self):
            if mutation=='grant':self.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
            elif mutation=='owner':self.execute(update(old.principals).where(old.principals.c.principal_id==identities.people['customer_a']['principal_id']).values(enabled=False))
            elif mutation=='source':self.execute(update(t.sources).values(order_projection_id=None))
            elif mutation=='generation':self.execute(update(t.state).values(generation=t.state.c.generation+1))
            elif mutation=='input':
                self.execute(update(old.case_heads).values(input_version=old.case_heads.c.input_version+1))
                self.execute(update(t.state).values(input_version=t.state.c.input_version+1))
            else:self.execute(update(t.work).where(t.work.c.work_id==intent.work_id).values(epoch=t.work.c.epoch+1))
            super().commit()
    worker.uow_factory=MutatingCommit
    assert worker.process(intent).status=='DENIED'
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]
    assert rows(flow_engine,t.state)[0]['proposal_record_id'] is None


@pytest.mark.parametrize('mutation',['projection','projection_hash','receipt_bytes'])
def test_missing_or_corrupt_accepted_order_material_is_not_rebuilt(flow_engine,identities,enabled,mutation):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    before=rows(flow_engine,old.history)
    with flow_engine.begin() as connection:
        if mutation=='projection':connection.execute(update(investigation.state).values(current_projection_id=None))
        elif mutation=='projection_hash':connection.execute(update(investigation.projections).values(snapshot_hash='0'*64))
        else:connection.execute(delete(investigation.receipt_contents))
    assert worker.process(intent).status=='DENIED'
    assert rows(flow_engine,old.history)==before and rows(flow_engine,t.events)==[]


@pytest.mark.parametrize('mode',['uncited_conflict','no_match'])
def test_complete_synthetic_retrieval_is_preserved_without_a_risk_result(flow_engine,identities,enabled,mode):
    case=ready(flow_engine,identities);captured=[]
    def complete(*args):
        body=build_fixed_proposal(*args)
        body['retrieval_result']['conflicts']=['Synthetic unresolved conflict remains unreviewed.']
        if mode=='uncited_conflict':
            passage=deepcopy(body['retrieval_result']['passages'][0]);passage['passage_id']='uncited-synthetic-passage'
            body['retrieval_result']['passages'].append(passage)
        else:
            body['retrieval_result'].update(status='NO_MATCH',passages=[])
            body['packet']['citations']=[];body['citation_verification']['checks']=[]
        captured.append(deepcopy(body['retrieval_result']))
        return body
    worker=FixedProposalProcessor(flow_engine,build=complete);intent=worker.prepare(case)
    assert worker.process(intent).status=='ACCEPTED'
    assert saved_bundle(flow_engine)['retrieval_result']==captured[0]
    assert rows(flow_engine,t.state)[0]['review_record_id'] is None


def test_claimed_capacity_failure_requires_independent_actual_overflow(flow_engine,identities,enabled):
    case=ready(flow_engine,identities);before=rows(flow_engine,old.history)
    def false_capacity(*args):raise ProposalCapacityError()
    worker=FixedProposalProcessor(flow_engine,build=false_capacity);intent=worker.prepare(case)
    assert worker.process(intent).status=='DENIED'
    assert rows(flow_engine,old.history)==before and rows(flow_engine,old.processing_failures)==[]
    assert rows(flow_engine,old.case_heads)[0]['status']=='POLICY_ASSESSMENT'


def test_raw_concurrent_authority_change_cannot_cross_real_acceptance_lock(flow_engine,identities,enabled):
    from sqlalchemy.exc import DBAPIError
    case=ready(flow_engine,identities);observed=[]
    def revoke():
        with flow_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='100ms'"))
            try:connection.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
            except DBAPIError as error:
                assert getattr(error.orig,'sqlstate',None)=='55P03'
                return 'locked'
        raise AssertionError('Concurrent raw authority writer crossed acceptance')
    def while_locked(*args):
        with ThreadPoolExecutor(max_workers=1) as pool:observed.append(pool.submit(revoke).result(timeout=5))
        return build_fixed_proposal(*args)
    worker=FixedProposalProcessor(flow_engine,build=while_locked);intent=worker.prepare(case)
    assert worker.process(intent).status=='ACCEPTED' and observed==['locked']
    assert rows(flow_engine,t.authorities)[0]['enabled'] is True


def test_retention_tombstones_actual_saved_packet_without_reconstruction(flow_engine,identities,enabled):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    assert worker.process(intent).status=='ACCEPTED'
    original=next(row for row in rows(flow_engine,old.history) if row['kind']=='STATEMENT')
    proposal=next(row for row in rows(flow_engine,old.history) if row['kind']=='PROPOSAL')
    RetentionService(flow_engine).remove('STATEMENT',original['object_id'])
    assert not any(row['record_id']==proposal['record_id'] for row in rows(flow_engine,old.history_contents))
    after=next(row for row in rows(flow_engine,old.history) if row['record_id']==proposal['record_id'])
    assert after['content_sha256']==proposal['content_sha256'] and after['retention_state']=='DELETED'
    assert 'current_proposal' not in founder(flow_engine,identities).read('getFounderCase',case).body
    assert not worker.run_once() and len(rows(flow_engine,t.events))==1


def test_new_interpreter_resolves_and_replays_persisted_work(flow_engine,identities,enabled,tmp_path):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    assert worker.process(intent).status=='ACCEPTED'
    request=tmp_path/'intent.json';request.write_text(json.dumps(asdict(intent)))
    child="""
import json,os,re,sys
from sqlalchemy import create_engine
from returnops_domain.proposal_processor import FixedProposalProcessor,Intent
schema=sys.argv[1]
assert re.fullmatch(r'customer_test_[0-9a-f]{32}',schema)
engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,connect_args={'options':'-c search_path='+schema})
try:
    intent=Intent(**json.load(open(sys.argv[2])))
    processor=FixedProposalProcessor(engine)
    assert processor.resolve(intent).status=='ACCEPTED'
    assert processor.process(intent).status=='ACCEPTED'
    print('PASS exact persistent fixed-proposal receipt after restart')
finally:engine.dispose()
"""
    result=subprocess.run([sys.executable,'-B','-c',child,flow_engine._customer_test_schema,str(request)],capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr.decode('utf-8',errors='replace')
    assert b'PASS exact persistent' in result.stdout and len(rows(flow_engine,t.events))==1


@pytest.mark.parametrize('failure_point',['statement','commit_check'])
def test_one_real_statement_timeout_rolls_back_then_recovers_same_intent(flow_engine,identities,enabled,failure_point):
    case=ready(flow_engine,identities);clock=[now()]
    worker=FixedProposalProcessor(flow_engine,clock=lambda:clock[0]);intent=worker.prepare(case)
    before=fingerprints(flow_engine);fired=[False];sqlstates=[]
    def capture(context):
        if context.statement=='SELECT pg_sleep(0.1)':
            sqlstates.append(getattr(context.original_exception,'sqlstate',None))
    class TimeoutOnce(_ProposalUnitOfWork):
        def timeout(self):
            fired[0]=True
            super().execute(text("SET LOCAL statement_timeout='10ms'"))
            super().execute(text('SELECT pg_sleep(0.1)'))
        def execute(self,statement,parameters=None):
            if failure_point=='statement' and not fired[0]:self.timeout()
            return super().execute(statement,parameters)
        def before_commit(self,check):
            def first_check():
                if failure_point=='commit_check' and not fired[0]:self.timeout()
                return check()
            super().before_commit(first_check)
    worker.uow_factory=TimeoutOnce
    sqlalchemy_event.listen(flow_engine,'handle_error',capture)
    try:
        result=worker.process(intent)
        assert sqlstates==['57014'] and result.status=='RETRYABLE' and result.audit=='NOT_ATTEMPTED'
        assert fingerprints(flow_engine)==before
        assert rows(flow_engine,t.work)[0]['state']=='PENDING' and rows(flow_engine,t.work)[0]['epoch']==0
        assert worker.run_once() is False
        clock[0]+=timedelta(seconds=1)
        assert worker.run_once() is True
    finally:sqlalchemy_event.remove(flow_engine,'handle_error',capture)
    assert len(rows(flow_engine,t.work))==len(rows(flow_engine,t.events))==1
    assert rows(flow_engine,t.work)[0]['work_id']==intent.work_id and rows(flow_engine,t.work)[0]['state']=='DONE'
    assert rows(flow_engine,t.events)[0]['record_id']==stable_id('source',intent.work_id)
    assert rows(flow_engine,t.events)[0]['event_id']==stable_id('event',intent.work_id)
    assert not any(decode_document(row['body'])['event_type']=='LIFECYCLE_GUARD_DENIED' for row in rows(flow_engine,old.audit))


def test_done_replay_acknowledged_commit_then_close_error_resolves_original_receipt(flow_engine,identities,enabled):
    case=ready(flow_engine,identities);worker=FixedProposalProcessor(flow_engine);intent=worker.prepare(case)
    assert worker.process(intent).status=='ACCEPTED'
    before=fingerprints(flow_engine);closed=[0]
    class ClosedAfterCommittedError(CustomerUnitOfWork):
        def __exit__(self,kind,value,trace):
            result=super().__exit__(kind,value,trace)
            if kind is None and self.finished and self.connection.closed:
                closed[0]+=1
                raise FlowError('INTERNAL_ERROR')
            return result
    worker.uow_factory=ClosedAfterCommittedError
    result=worker.process(intent)
    assert closed==[1] and result.status=='ACCEPTED' and result.audit=='NOT_ATTEMPTED'
    assert fingerprints(flow_engine)==before
    assert rows(flow_engine,t.work)[0]['state']=='DONE' and len(rows(flow_engine,t.events))==1
