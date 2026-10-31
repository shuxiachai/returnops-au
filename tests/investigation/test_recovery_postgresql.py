from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Event,Thread,current_thread
import time
import pytest
from sqlalchemy import select,update,text
from returnops_domain import customer_tables as old, investigation_tables as t
from returnops_domain.audit import identifier,verify_chain
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.investigation_processor import InvestigationProcessor
from returnops_domain.investigation_policy import InvestigationPolicy
from returnops_domain.mock_orders import load_builtin_catalogue
from returnops_domain.order_ports import OrderLookupError
from returnops_domain.registry import TrustedRegistry
from returnops_domain.retention import RetentionService
from test_outcomes_postgresql import admitted,rows

class OneUnknownCommit:
    def __init__(self,*,committed): self.committed=committed;self.armed=True
    def __call__(self,engine,**kwargs):
        owner=self
        class Uow(CustomerUnitOfWork):
            def commit(self):
                if self.write and owner.armed:
                    owner.armed=False
                    if owner.committed: super().commit()
                    else: self.transaction.rollback();self.finished=True
                    raise AcceptanceOutcomeUnknown()
                return super().commit()
        return Uow(engine,**kwargs)

@pytest.mark.parametrize('committed',[True,False])
def test_claim_commit_unknown_resolves_exact_token(flow_engine,identities,enabled,committed):
    admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine,uow_factory=OneUnknownCommit(committed=committed))
    claim=processor.claim()
    assert (claim is not None)==committed
    work=rows(flow_engine,t.work)[0]
    assert work['state']==('RUNNING' if committed else 'PENDING')
    assert work['epoch']==(1 if committed else 0)
    if claim is None: claim=processor.claim()
    assert processor.finish(processor.lookup(claim))
    assert len(rows(flow_engine,t.projections))==1

@pytest.mark.parametrize('committed',[True,False])
def test_result_commit_unknown_reuses_same_observation(flow_engine,identities,enabled,committed):
    admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    processor.uow_factory=OneUnknownCommit(committed=committed)
    assert processor.finish(observation) is committed
    assert len(rows(flow_engine,t.receipts))==(1 if committed else 0)
    assert len(rows(flow_engine,t.projections))==(1 if committed else 0)
    assert processor.finish(observation)
    assert rows(flow_engine,t.receipts)[0]['receipt_id']==claim.invocation_id
    assert len(rows(flow_engine,t.receipts))==len(rows(flow_engine,t.projections))==1
    assert rows(flow_engine,old.case_heads)[0]['input_version']==2

@pytest.mark.parametrize('error',[FlowError('INTERNAL_ERROR'),AcceptanceOutcomeUnknown()])
def test_transient_lookup_failure_retries_instead_of_pausing(flow_engine,identities,enabled,error):
    # 30 October 2026 review: a busy fence or pool during the shared lookup used to
    # pause the work for good, leaving the case in UNDER_INVESTIGATION.
    original,_=admitted(flow_engine,identities)
    now=datetime.now(timezone.utc)
    processor=InvestigationProcessor(flow_engine,clock=lambda:now)
    real=processor.lookup
    def failing(claim): raise error
    processor.lookup=failing
    assert processor.run_once() is False
    work=rows(flow_engine,t.work)[0]
    assert (work['state'],work['safe_reason'],work['failure_count'])==('PENDING','LOOKUP_CONTEXT_UNAVAILABLE',0)
    assert work['next_attempt_at']>now
    assert processor.claim() is None
    processor.lookup=real;now+=timedelta(seconds=2)
    assert processor.run_once()
    assert len(rows(flow_engine,t.receipts))==len(rows(flow_engine,t.projections))==1
    assert identities.flow().get_case(original.body['case_id']).body['status']=='POLICY_ASSESSMENT'
    assert rows(flow_engine,t.discarded)==[] and rows(flow_engine,old.processing_failures)==[]

def test_a_database_error_inside_the_order_lookup_retries_instead_of_pausing(flow_engine,identities,enabled,monkeypatch):
    # Runtime review (31 October 2026): the resolver and the provider turned a lost
    # connection into CASE_ACCESS_DENIED, which paused the work for good.
    from returnops_domain.investigation_context import DatabaseOrderResolver
    original,_=admitted(flow_engine,identities)
    now=datetime.now(timezone.utc)
    processor=InvestigationProcessor(flow_engine,clock=lambda:now)
    real=DatabaseOrderResolver.resolve;calls=[]
    def flaky(self,case_id,input_version):
        calls.append(case_id)
        if len(calls)==2:
            self.uow.failed=True  # what a lost connection does to the unit of work
            raise OrderLookupError('CASE_ACCESS_DENIED')
        return real(self,case_id,input_version)
    monkeypatch.setattr(DatabaseOrderResolver,'resolve',flaky)
    assert processor.run_once() is False
    work=rows(flow_engine,t.work)[0]
    assert (work['state'],work['safe_reason'],work['failure_count'])==('PENDING','LOOKUP_CONTEXT_UNAVAILABLE',0)
    monkeypatch.setattr(DatabaseOrderResolver,'resolve',real);now+=timedelta(seconds=2)
    assert processor.run_once()
    assert identities.flow().get_case(original.body['case_id']).body['status']=='POLICY_ASSESSMENT'

def test_authority_lookup_failure_still_pauses(flow_engine,identities,enabled):
    admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine)
    def denied(claim): raise OrderLookupError('STALE_INPUT')
    processor.lookup=denied
    assert processor.run_once() is False
    work=rows(flow_engine,t.work)[0]
    assert (work['state'],work['safe_reason'])==('PAUSED','LOOKUP_CONTEXT_UNAVAILABLE')

def test_intake_enqueue_rollback_and_unknown_commit_are_atomic(flow_engine,identities,enabled):
    case=identities.flow().create({'original_message':'original','order_reference':'SYN-1001'},'create-key',identifier('corr')).body['case_id']
    intake=IntakeProcessor(flow_engine);claim=intake.claim();result=intake.evaluate(claim)
    intake.uow_factory=OneUnknownCommit(committed=False)
    assert not intake.finish(claim,result)
    assert rows(flow_engine,t.work)==[] and rows(flow_engine,old.intake_work)[0]['state']=='RUNNING'
    assert rows(flow_engine,old.case_heads)[0]['case_version']==1
    intake.uow_factory=OneUnknownCommit(committed=True)
    assert intake.finish(claim,result)
    assert len(rows(flow_engine,t.work))==1 and rows(flow_engine,old.intake_work)[0]['state']=='DONE'
    assert rows(flow_engine,old.case_heads)[0]['case_version']==2
    assert intake.finish(claim,result) and len(rows(flow_engine,t.work))==1

def test_two_workers_claim_once_and_lease_restart_rejects_late_result(flow_engine,identities,enabled):
    admitted(flow_engine,identities)
    now=datetime.now(timezone.utc)
    processor=InvestigationProcessor(flow_engine,clock=lambda:now,lease_seconds=1)
    with ThreadPoolExecutor(max_workers=2) as pool: claims=list(pool.map(lambda _:processor.claim(),range(2)))
    assert sum(c is not None for c in claims)==1
    first=next(c for c in claims if c is not None);late=processor.lookup(first)
    now+=timedelta(seconds=2)
    restarted=InvestigationProcessor(flow_engine,clock=lambda:now,lease_seconds=10)
    newer=restarted.claim();assert newer.epoch==first.epoch+1
    assert not processor.finish(late)
    assert restarted.finish(restarted.lookup(newer))
    assert len(rows(flow_engine,t.receipts))==len(rows(flow_engine,t.projections))==1
    discarded=rows(flow_engine,t.discarded)[0]
    assert discarded['invocation_id']==first.invocation_id
    assert set(discarded)=={'invocation_id','work_id','claim_id','epoch','service_signature','grant_signature','safe_reason','discarded_at'}

@pytest.mark.parametrize('mutation',['grant','disable','store','retention','service'])
def test_current_authority_or_content_change_rejects_late_result_without_budget(flow_engine,identities,enabled,mutation):
    original,_=admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    if mutation=='grant': enabled.grant('synthetic_au_store','synthetic_commerce',can_read=False)
    elif mutation=='service': enabled.configure('synthetic_au_store',enabled=False)
    elif mutation=='disable': TrustedRegistry(flow_engine).change_principal('synthetic_customer_a',enabled=False)
    elif mutation=='store': TrustedRegistry(flow_engine).change_principal('synthetic_customer_a',store_id='other_store')
    else: RetentionService(flow_engine).remove('STATEMENT',original.body['statements'][0]['statement_id'])
    assert not processor.finish(observation)
    assert rows(flow_engine,t.receipts)==rows(flow_engine,t.projections)==[]
    assert rows(flow_engine,t.work)[0]['failure_count']==0
    assert len(rows(flow_engine,t.discarded))==1
    assert rows(flow_engine,old.processing_failures)==[]

def test_explicit_resume_after_regrant_never_reopens_accepted_escalation(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    enabled.grant('synthetic_au_store','synthetic_commerce',can_read=False)
    assert not processor.finish(observation)
    enabled.grant('synthetic_au_store','synthetic_commerce',can_read=True)
    assert not processor.run_once()
    enabled.resume(claim.work_id,expected_input_version=1)
    assert processor.run_once()
    second,_=admitted(flow_engine,identities,'SYN-CONFLICT',key='conflict-key')
    assert processor.run_once()
    conflict=next(w for w in rows(flow_engine,t.work) if w['case_id']==second.body['case_id'])
    enabled.grant('synthetic_au_store','synthetic_commerce',can_read=True)
    with pytest.raises(FlowError): enabled.resume(conflict['work_id'],expected_input_version=1)
    assert identities.flow().get_case(second.body['case_id']).body['status']=='ESCALATED'
    assert len(rows(flow_engine,t.blocks))==1 and enabled.verify('synthetic_au_store')

def test_retention_removes_all_personal_derivatives_without_resurrection(flow_engine,identities,enabled):
    original,_=admitted(flow_engine,identities)
    processor=InvestigationProcessor(flow_engine);claim=processor.claim();observation=processor.lookup(claim)
    assert processor.finish(observation)
    case=original.body['case_id'];statement=original.body['statements'][0]['statement_id']
    assert RetentionService(flow_engine).remove('STATEMENT',statement)
    view=identities.flow().get_case(case).body
    assert (view['status'],view['input_version'],view['case_version'])==('POLICY_ASSESSMENT',2,4)
    assert rows(flow_engine,t.receipt_contents)==rows(flow_engine,t.projection_contents)==[]
    assert not rows(flow_engine,t.receipts)[0]['available'] and not rows(flow_engine,t.projections)[0]['available']
    assert rows(flow_engine,t.inputs)[0]['reference'] is None and not rows(flow_engine,t.inputs)[0]['available']
    assert rows(flow_engine,t.state)[0]['current_projection_id'] is None
    assert processor.finish(observation)  # original acceptance fact, no body restore
    assert rows(flow_engine,t.receipt_contents)==rows(flow_engine,t.projection_contents)==[]
    assert not processor.run_once()
    assert rows(flow_engine,t.work)[0]['state']=='DONE'
    with pytest.raises(FlowError): enabled.resume(claim.work_id,expected_input_version=2)
    with CustomerUnitOfWork(flow_engine,write=False) as uow:
        assert verify_chain(uow,case);uow.commit()

def test_shared_lookup_fence_blocks_real_grant_writer(flow_engine,identities,enabled,monkeypatch):
    admitted(flow_engine,identities)
    entered=Event();release=Event();writer_started=Event();pids=[];outputs=[];errors=[]
    builtin=load_builtin_catalogue()
    class BlockingSource:
        metadata=builtin.metadata
        def read_matches(self,*args):
            entered.set();assert release.wait(5)
            return builtin.read_matches(*args)
    import returnops_domain.customer_uow as uow_module
    original_fence=uow_module.acquire_fence
    def observed(connection,*,write):
        if current_thread().name=='policy-writer':
            pids.append(connection.execute(text('SELECT pg_backend_pid()')).scalar_one());writer_started.set()
        return original_fence(connection,write=write)
    monkeypatch.setattr(uow_module,'acquire_fence',observed)
    processor=InvestigationProcessor(flow_engine,catalogue=BlockingSource());claim=processor.claim()
    def lookup():
        try: outputs.append(processor.lookup(claim))
        except BaseException as error: errors.append(type(error).__name__)
    def revoke():
        try: enabled.grant('synthetic_au_store','synthetic_commerce',can_read=False)
        except BaseException as error: errors.append(type(error).__name__)
    reader=Thread(target=lookup);writer=Thread(target=revoke,name='policy-writer')
    reader.start();assert entered.wait(5);writer.start();assert writer_started.wait(5)
    try:
        blocked=False;deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            with flow_engine.connect() as connection:
                blocked=bool(connection.execute(text("SELECT EXISTS(SELECT1 FROM pg_locks WHERE pid=:pid AND locktype='advisory' AND NOT granted)".replace('SELECT1','SELECT 1')),{'pid':pids[0]}).scalar_one())
            if blocked: break
            time.sleep(0.01)
        assert blocked and writer.is_alive()
    finally:
        release.set();reader.join(5);writer.join(5)
    assert not reader.is_alive() and not writer.is_alive() and not errors
    assert len(outputs)==1 and not processor.finish(outputs[0])
    assert rows(flow_engine,t.receipts)==[] and rows(flow_engine,t.work)[0]['failure_count']==0
