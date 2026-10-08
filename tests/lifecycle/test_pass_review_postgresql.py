"""Private synthetic PASS receiver: actual PostgreSQL acceptance and denial."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import json,os,subprocess,sys,time
from pathlib import Path
import pytest
from sqlalchemy import delete,select,text,update
from returnops_domain import customer_tables as old,lifecycle_tables as t,investigation_tables as inv
from returnops_domain import founder_codec as finite
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import AcceptanceOutcomeUnknown,FlowError
from returnops_domain.lifecycle_state import installed
from returnops_domain.lifecycle_schema import version as schema_version,CURRENT,LEGACY
from returnops_domain.lifecycle_events import PassReviewAccepted,EscalateReviewAccepted,LifecycleClaim
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain.pass_review_sources import COMPONENT
from returnops_api.database import readiness
from pass_review_helpers import ControlledPassReviewer,ready_pass,receiver,build_positive,provision_review
from manual_helpers import rows,snapshot,business,evidence,now
from test_manual_postgresql import UnknownCommit,observed,installed_manual
from test_proposal_runtime_postgresql import founder


def attempt(engine,case,version,**options):
    return receiver(engine,**options).accept(case,version,'original-review-key','pass_correlation')


@pytest.fixture
def race_context(request):
    """Own only this race schema; never clean it while an owned writer is unknown.

    Existing shared fixtures stay unchanged. On any test exit, drain every
    launched child and independently confirm its DB sessions disappeared.
    An unconfirmed child/session preserves the schema and records UNKNOWN.
    """
    from types import SimpleNamespace
    from uuid import uuid4
    from sqlalchemy import create_engine
    from returnops_api.settings import require_environment_database
    from conftest import shared
    raw=os.environ['DATABASE_URL'];require_environment_database(raw)
    schema='customer_test_'+uuid4().hex
    control=create_engine(raw,hide_parameters=True,echo=False)
    with control.begin() as connection:
        assert 170000<=int(connection.execute(text('SHOW server_version_num')).scalar_one())<180000
        assert connection.execute(text('SELECT count(*) FROM pg_namespace WHERE nspname=:name'),{'name':schema}).scalar_one()==0
        connection.execute(text('CREATE SCHEMA '+schema))
    engine=create_engine(raw,hide_parameters=True,echo=False,pool_size=8,max_overflow=4,
        connect_args={'connect_timeout':3,'options':'-c search_path='+schema+' -c statement_timeout=10000'})
    engine._customer_test_schema=schema
    context=SimpleNamespace(engine=engine,identities=None,processes=[],application_names=[])
    confirmed=False;child_results=[];remaining=[];error=None
    try:
        shared.migrate(engine)
        context.identities=shared.identities.__wrapped__(engine)
        shared.enabled.__wrapped__(engine,context.identities)
        yield context
    finally:
        try:
            for process in context.processes:
                try:
                    out,err=process.communicate(timeout=60)
                    child_results.append(dict(pid=process.pid,returncode=process.returncode,completion='CONFIRMED',
                        stdout_sha256=__import__('hashlib').sha256(out).hexdigest(),stderr_sha256=__import__('hashlib').sha256(err).hexdigest()))
                except subprocess.TimeoutExpired:
                    child_results.append(dict(pid=process.pid,returncode=process.poll(),completion='UNKNOWN',terminated=False))
            # No kill, guessed rollback, or DROP while a child remains unknown.
            if all(r['completion']=='CONFIRMED' for r in child_results):
                deadline=time.monotonic()+5
                while True:
                    with control.connect() as connection:
                        remaining=[dict(r) for r in connection.execute(text('SELECT pid,application_name,state FROM pg_stat_activity WHERE application_name = ANY(:names)'),
                            {'names':context.application_names}).mappings()] if context.application_names else []
                    if not remaining:confirmed=True;break
                    if time.monotonic()>=deadline:break
                    time.sleep(0.01)
        except BaseException as exc:error=type(exc).__name__
        finally:
            engine.dispose()
            if confirmed:
                with control.begin() as connection:connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
            control.dispose()
            evidence(request.node.nodeid+'::child_cleanup',schema=schema,children=child_results,remaining_sessions=remaining,
                error=error,cleanup='DROPPED_AFTER_CONFIRMED_CHILD_AND_SESSION_EXIT' if confirmed else 'PRESERVED_UNKNOWN_WRITER_NO_CLEANUP')
        assert confirmed,'Owned child/session completion UNKNOWN; preserved isolated schema, no cleanup or retry'


@pytest.mark.parametrize('outcome',['PASS','PASS_WITH_WARNING'])
def test_PSE01_02_03_10_full_actual_chain_and_readonly_warning(flow_engine,identities,enabled,request,observed,outcome):
    case,version=ready_pass(flow_engine,identities);adapter=ControlledPassReviewer(outcome)
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='ACCEPTED',(result.status,result.safe_code,result.audit)
    head=rows(flow_engine,old.case_heads)[0];state=rows(flow_engine,t.state)[0]
    assert head['status']=='AWAITING_APPROVAL' and head['case_version']==version+1
    assert head['input_version']==before['case_heads'][0]['input_version']
    for field in ['generation','input_version','proposal_record_id','proposal_version']:
        assert state[field]==before['case_lifecycle_state'][0][field]
    raw=next(r['body'] for r in rows(flow_engine,old.history_contents) if r['record_id']==state['proposal_record_id'])
    assert adapter.calls==[finite.decode_document(raw)]
    assert len(adapter.calls[0]['attachments'])==1 and len(adapter.calls[0]['order_lookup']['snapshot']['line_items'])==2
    assert len(rows(flow_engine,inv.receipts))==1 and len(rows(flow_engine,inv.projections))==1
    assert result.receipt['event_kind']=='REVIEW_PASS' and result.receipt['status']=='AWAITING_APPROVAL'
    assert {w['purpose'] for w in rows(flow_engine,t.work)}=={'PROPOSAL','REVIEW'}
    assert not any(r['kind'] in {'DECISION','APPROVAL','OPERATION','NOTIFICATION'} for r in rows(flow_engine,old.history))
    assert not rows(flow_engine,t.effects)
    assert all(state[field] is None for field in ['preview_id','approval_record_id','outcome_record_id','outcome','notification_work_id'])
    reader=founder(flow_engine,identities);detail=reader.read('getFounderCase',case).body
    assert detail['current_review']['outcome']==outcome
    warning=detail['current_review']['findings'];assert bool(warning)==(outcome=='PASS_WITH_WARNING')
    reader.read('listFounderCaseHistory',case,{'kind':'REVIEW'});reader.read('listCaseAudit',case)
    read_before=snapshot(flow_engine)
    again=reader.read('getFounderCase',case).body
    reader.read('listFounderCaseHistory',case,{'kind':'REVIEW'});reader.read('listCaseAudit',case)
    read_after=snapshot(flow_engine)
    assert again['current_review']==detail['current_review']
    assert {k:v for k,v in read_after.items() if not k.startswith('founder_')}=={k:v for k,v in read_before.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),effects=observed,
        adapter_input=adapter.calls[0],founder_review=detail['current_review'])


@pytest.mark.parametrize('mode',['pass_warning','warning_empty','block','questions','revision','unknown','ESCALATE','REVISE',
    'review_id','reviewed_at','run_id','role','provider_id','model_id','prompt_version','started_at','finished_at','input_tokens','output_tokens',
    'missing_model','extra_model','trace_wire','trace_context','changed_context','changed_input','citation','evidence','duplicate_finding',
    'case_id','proposal_id','proposal_version','input_version','corpus_version'])
def test_PSE02_03_exact_output_context_and_frozen_semantics(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    def mutate(body,source,context):
        finding=dict(finding_id='info',severity='INFO',category='LOW_CONFIDENCE',message='Synthetic information.',citation_ids=[],evidence_ids=[])
        if mode=='pass_warning':body['findings']=[{**finding,'severity':'WARNING'}]
        elif mode=='warning_empty':body['outcome']='PASS_WITH_WARNING'
        elif mode=='block':body['findings']=[{**finding,'severity':'BLOCK'}]
        elif mode=='questions':body['questions']=[dict(question_id='q',text='Unexpected question',reason='Unexpected')]
        elif mode=='revision':body['revision_requests']=['Unexpected revision']
        elif mode in {'unknown','ESCALATE','REVISE'}:body['outcome']=mode
        elif mode in {'review_id','reviewed_at','case_id','proposal_id','proposal_version','input_version','corpus_version'}:
            body[mode]=99 if mode.endswith('_version') and mode!='corpus_version' else '2020-01-01T00:00:00Z' if mode=='reviewed_at' else 'forged'
        elif mode in {'run_id','role','provider_id','model_id','prompt_version','started_at','finished_at','input_tokens','output_tokens'}:
            body['model_run'][mode]=1 if mode.endswith('_tokens') else '2020-01-01T00:00:00Z' if mode.endswith('_at') else 'forged'
        elif mode=='missing_model':del body['model_run']['run_id']
        elif mode=='extra_model':body['model_run']['trace_id']='unfrozen'
        elif mode=='trace_wire':body['trace_id']='unfrozen'
        elif mode=='trace_context':context['trace_id']='changed'
        elif mode=='changed_context':context['run_id']='changed'
        elif mode=='changed_input':source['statements'][0]['raw_text']='changed'
        elif mode in {'citation','evidence'}:body['findings']=[{**finding,mode+'_ids':['outside_packet']}]
        else:body['findings']=[finding,deepcopy(finding)]
    adapter=ControlledPassReviewer(mutate=mutate);before=snapshot(flow_engine)
    result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before) and len(adapter.calls)==1
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),mutation=mode)


@pytest.mark.parametrize('mode',['default','wrong_message','missing_matrix','uncertain','manual','empty_lines','conflict','changed_policy','model'])
def test_PSE03_narrow_positive_family_cannot_relabel_default(flow_engine,identities,enabled,request,mode):
    from returnops_domain.fixed_proposal import build_fixed_proposal
    def builder(*args):
        body=(build_fixed_proposal if mode=='default' else build_positive)(*args)
        if mode=='missing_matrix':body['packet']['evidence_matrix'][0]['status']='MISSING';body['evidence_matrix'][0]['status']='MISSING'
        elif mode=='uncertain':body['packet']['facts']['assessment_status']='UNCERTAIN'
        elif mode=='manual':body['packet']['recommended_action']='REFER_FOR_MANUAL_HANDLING'
        elif mode=='empty_lines':body['packet']['facts']['line_items']=[]
        elif mode=='conflict':body['packet']['unresolved_questions']=['Unresolved material conflict']
        elif mode=='changed_policy':body['packet']['conditions']=['Different conditions']
        elif mode=='model':body['packet']['model_run']['prompt_version']='another_builder'
        return body
    options={'builder':builder}
    if mode=='wrong_message':options['message']='Unrelated synthetic material, not the cups family.'
    case,version=ready_pass(flow_engine,identities,**options);adapter=ControlledPassReviewer();before=snapshot(flow_engine)
    result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and not adapter.calls and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),mutation=mode)


@pytest.mark.parametrize('mode',['missing','ESC','HUMAN','OUTCOME','REVISION'])
def test_PSE05_no_borrowed_component_or_purpose(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities,grant=False)
    if mode!='missing':
        with flow_engine.begin() as c:
            if mode=='ESC':component,purpose='controlled-escalate-review-v1','REVIEW'
            else:component,purpose=COMPONENT,mode
            c.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],component_id=component,purpose=purpose,revision=1,enabled=True))
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('direction',['pass_as_ESC','ESC_as_pass'])
def test_PSE06_event_fingerprint_and_lowlevel_replay_isolation(flow_engine,identities,enabled,request,direction):
    if direction=='pass_as_ESC':
        case,version=ready_pass(flow_engine,identities);accepted=attempt(flow_engine,case,version);component=COMPONENT;wrong=EscalateReviewAccepted
    else:
        from controlled_escalate_reviewer import ready_review,receiver as esc_receiver
        from returnops_domain.review_sources import COMPONENT as ESC_COMPONENT
        case,version=ready_review(flow_engine,identities);accepted=esc_receiver(flow_engine).accept(case,version,'original-review-key','esc_corr');component=ESC_COMPONENT;wrong=PassReviewAccepted
    assert accepted.status=='ACCEPTED'
    work=next(r for r in rows(flow_engine,t.work) if r['purpose']=='REVIEW')
    claim=LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],work['input_version'],work['generation'],work['authority_revision'])
    before=snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):LifecycleGuards(component).apply(uow,wrong(accepted.receipt['event_id'],claim,accepted.receipt['record_id']),now())
        with pytest.raises(FlowError):uow.commit()
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),event=accepted.receipt,direction=direction)


@pytest.mark.parametrize('mode',['event','work_component','event_status','binding','audit'])
def test_PSE04_06_10_current_and_replay_require_full_proof(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities);accepted=attempt(flow_engine,case,version);assert accepted.status=='ACCEPTED'
    record=accepted.receipt['record_id']
    with flow_engine.begin() as c:
        if mode=='event':c.execute(update(t.events).where(t.events.c.record_id==record).values(event_kind='REVIEW'))
        elif mode=='event_status':c.execute(update(t.events).where(t.events.c.record_id==record).values(status='ESCALATED'))
        elif mode=='work_component':c.execute(update(t.work).where(t.work.c.work_id==accepted.receipt['work_id']).values(component_id='controlled-escalate-review-v1'))
        elif mode=='binding':c.execute(update(t.sources).where(t.sources.c.record_id==record).values(target_record_id=None))
        else:c.execute(update(old.audit).values(body=b'{}'))
    before=snapshot(flow_engine)
    with pytest.raises(FlowError):founder(flow_engine,identities).read('getFounderCase',case)
    assert business(snapshot(flow_engine))==business(before)
    caller=receiver(flow_engine);result=caller.accept(case,version,'original-review-key','replay')
    assert result.status=='DENIED' and caller.recover(case,version,'original-review-key').status=='UNKNOWN'
    assert business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


def test_PSE07_exact_key_and_no_replacement_intent(flow_engine,identities,enabled,request):
    case,version=ready_pass(flow_engine,identities);adapter=ControlledPassReviewer();caller=receiver(flow_engine,adapter)
    result=caller.accept(case,version,'original-review-key','corr');assert result.status=='ACCEPTED'
    before=snapshot(flow_engine)
    assert caller.accept(case,version,'original-review-key','new_corr').receipt==result.receipt
    assert caller.recover(case,version,'original-review-key').receipt==result.receipt
    assert snapshot(flow_engine)==before and len(adapter.calls)==1
    assert caller.accept(case,version+1,'original-review-key','corr').safe_code=='IDEMPOTENCY_CONFLICT'
    assert caller.accept(case,version+1,'replacement-key','corr').status=='DENIED'
    assert business(snapshot(flow_engine))==business(before) and len(adapter.calls)==1
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),adapter_calls=1)


@pytest.mark.parametrize('missing',[False,True])
def test_PSE06_07_lower_original_replay_never_reconstructs_state(flow_engine,identities,enabled,request,missing):
    case,version=ready_pass(flow_engine,identities);accepted=attempt(flow_engine,case,version)
    assert accepted.status=='ACCEPTED'
    work=next(w for w in rows(flow_engine,t.work) if w['purpose']=='REVIEW')
    claim=LifecycleClaim(work['work_id'],work['claim_id'],work['epoch'],work['claimed_case_version'],work['input_version'],work['generation'],work['authority_revision'])
    event=PassReviewAccepted(accepted.receipt['event_id'],claim,accepted.receipt['record_id'])
    if missing:
        with flow_engine.begin() as connection:connection.execute(delete(t.state).where(t.state.c.case_id==case))
    before=snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        if missing:
            with pytest.raises(FlowError):LifecycleGuards(COMPONENT).apply(uow,event,now())
            with pytest.raises(FlowError):uow.commit()
        else:
            assert LifecycleGuards(COMPONENT).apply(uow,event,now())==accepted.receipt
            uow.commit()
    assert snapshot(flow_engine)==before
    assert bool(rows(flow_engine,t.state)) is not missing
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),original_receipt=accepted.receipt,missing_sidecar=missing)


@pytest.mark.parametrize('committed',[False,True])
@pytest.mark.parametrize('revoked',[False,True])
def test_PSE09_unknown_actual_commit_or_rollback(flow_engine,identities,enabled,request,committed,revoked):
    class Unknown(UnknownCommit):actual_commit=committed
    case,version=ready_pass(flow_engine,identities);adapter=ControlledPassReviewer();caller=receiver(flow_engine,adapter,uow_factory=Unknown)
    before=snapshot(flow_engine);result=caller.accept(case,version,'original-review-key','corr')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED'
    actual=snapshot(flow_engine)
    assert len([r for r in rows(flow_engine,t.events) if r['event_kind']=='REVIEW_PASS'])==int(committed)
    if not committed:assert actual==before
    if revoked:
        with flow_engine.begin() as c:c.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
    fresh_before=snapshot(flow_engine);recovered=caller.recover(case,version,'original-review-key')
    assert snapshot(flow_engine)==fresh_before and len(adapter.calls)==1
    assert recovered.status==('ACCEPTED' if committed and not revoked else 'UNKNOWN')
    evidence(request.node.nodeid,before=before,actual=actual,result=asdict(result),recovered=asdict(recovered),actual_transaction='COMMIT' if committed else 'ROLLBACK')


def test_PSE09_absence_is_not_rollback(flow_engine,identities,enabled,request):
    case,version=ready_pass(flow_engine,identities);adapter=ControlledPassReviewer();before=snapshot(flow_engine)
    result=receiver(flow_engine,adapter).recover(case,version,'original-review-key')
    assert result.status=='UNKNOWN' and not adapter.calls and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


def test_PSE08_every_write_and_final_failure_is_atomic(flow_engine,identities,enabled,request,observed):
    case,version=ready_pass(flow_engine,identities);trace=[]
    class Probe(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                trace.append(statement.table.name+(' INSERT' if statement.is_insert else ' UPDATE' if statement.is_update else ' DELETE'))
            return super().execute(statement,parameters)
        def commit(self):
            for check in self._commit_checks:check()
            self.poison();raise FlowError('INVALID_STATE')
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,uow_factory=Probe)
    assert result.status=='DENIED' and len(trace)>=10 and business(snapshot(flow_engine))==business(before)
    results=[]
    for point in range(1,len(trace)+1):
        class Fault(CustomerUnitOfWork):
            writes=0
            def execute(self,statement,parameters=None):
                if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                    self.writes+=1
                    if self.writes==point:self.poison();raise RuntimeError('RAW-CONTENT-MUST-NOT-ESCAPE')
                return super().execute(statement,parameters)
        original=snapshot(flow_engine);result=attempt(flow_engine,case,version,uow_factory=Fault);after=snapshot(flow_engine)
        assert result.status=='DENIED' and business(original)==business(after) and 'RAW-CONTENT' not in str(asdict(result))
        results.append(dict(point=point,statement=trace[point-1],before=original,after=after,result=asdict(result)))
    evidence(request.node.nodeid,before=before,trace=trace,faults=results,effects=observed)


@pytest.mark.parametrize('mode',['recorded','revoked','audit_committed_unknown','audit_rolledback_unknown'])
def test_PSE08_09_fresh_denial_after_original_uow_closed(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    class Original(CustomerUnitOfWork):
        exited=False
        def __exit__(self,*args):
            value=super().__exit__(*args);type(self).exited=True
            if mode=='revoked':
                with flow_engine.begin() as c:c.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(enabled=False))
            return value
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit=mode=='audit_committed_unknown';enters=0
        def __enter__(self):
            assert Original.exited;type(self).enters+=1;return super().__enter__()
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version-1,uow_factory=Original,audit_uow=Audit);after=snapshot(flow_engine)
    assert result.status=='DENIED' and Audit.enters==1
    assert result.audit==('RECORDED' if mode=='recorded' else 'NOT_RECORDED' if mode=='revoked' else 'UNKNOWN')
    assert len(after['customer_audit_events'])-len(before['customer_audit_events'])==int(mode in {'recorded','audit_committed_unknown'})
    if mode!='revoked':assert business(after)==business(before)
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result))


@pytest.mark.parametrize('removed',['STATEMENT','EVIDENCE'])
def test_PSE10_retention_never_reconstructs_deleted_material(flow_engine,identities,enabled,request,removed):
    from returnops_domain.retention import RetentionService
    case,version=ready_pass(flow_engine,identities);caller=receiver(flow_engine)
    assert caller.accept(case,version,'original-review-key','corr').status=='ACCEPTED'
    object_id=next(r['object_id'] for r in rows(flow_engine,old.history) if r['kind']==removed)
    RetentionService(flow_engine).remove(removed,object_id);before=snapshot(flow_engine)
    assert caller.accept(case,version,'original-review-key','corr').status=='DENIED'
    assert caller.recover(case,version,'original-review-key').status=='UNKNOWN' and snapshot(flow_engine)==before
    record_ids={r['record_id'] for r in rows(flow_engine,old.history) if r['kind'] in {'PROPOSAL','REVIEW'}}
    assert not any(r['record_id'] in record_ids for r in rows(flow_engine,old.history_contents))
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine))


@pytest.mark.parametrize('mode',['same_key','different_key','PASS_ESC'])
def test_PSE07_independent_process_competition(race_context,request,tmp_path,mode):
    flow_engine,identities=race_context.engine,race_context.identities
    case,version=ready_pass(flow_engine,identities)
    if mode=='PASS_ESC':
        from controlled_escalate_reviewer import provision_review as provision_esc
        provision_esc(flow_engine,identities)
    configs=[dict(case=case,version=version,schema=flow_engine._customer_test_schema) for _ in range(2)]
    if mode=='different_key':configs[1]['key']='another-key'
    if mode=='PASS_ESC':configs[1]['component']='ESC'
    processes=race_context.processes;before=snapshot(flow_engine)
    for number,config in enumerate(configs):
        config.update(application_name='pass-race-'+str(os.getpid())+'-'+str(number),
            ready_path=str(tmp_path/('ready-'+str(number)+'.json')),release_path=str(tmp_path/'release'))
        race_context.application_names.append(config['application_name'])
        path=tmp_path/('child-'+str(number)+'.json');path.write_text(json.dumps(config),encoding='utf8')
        args=[sys.executable,'-B',str(Path(__file__).with_name('pass_review_process_probe.py')),str(path)]
        processes.append(subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=os.environ.copy(),cwd=tmp_path))
    deadline=time.monotonic()+30
    while not all(Path(c['ready_path']).exists() for c in configs):
        assert time.monotonic()<deadline and all(p.poll() is None for p in processes),'Both prepared children required'
        time.sleep(0.01)
    ready=[json.loads(Path(c['ready_path']).read_text()) for c in configs]
    assert len({r['pid'] for r in ready})==2 and all(r['case']==case and r['version']==version for r in ready)
    # Hold the actual same global transaction fence until both independent
    # PostgreSQL sessions are demonstrably waiting for it. Timing alone is
    # never used as evidence of overlapping attempts.
    waiting=[]
    with CustomerUnitOfWork(flow_engine,write=True) as holder:
        holder_pid=holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
        (tmp_path/'release').write_text('Release both prepared original-target attempts',encoding='utf8')
        deadline=time.monotonic()+3
        while len(waiting)!=2:
            with flow_engine.connect() as observer:
                waiting=[dict(r) for r in observer.execute(text("SELECT pid,application_name,wait_event_type,wait_event FROM pg_stat_activity WHERE application_name IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),
                    dict(a=configs[0]['application_name'],b=configs[1]['application_name'])).mappings()]
            assert time.monotonic()<deadline,'Both actual blocked advisory-lock attempts must be observed'
            if len(waiting)!=2:time.sleep(0.01)
        assert len({r['pid'] for r in waiting})==2 and all(r['pid']!=holder_pid for r in waiting)
        holder.commit()
    outputs=[]
    for process in processes:
        out,err=process.communicate(timeout=60)
        assert process.returncode==0 and err==b''
        outputs.append(json.loads(out))
    statuses=sorted(o['result']['status'] for o in outputs)
    assert statuses==(['ACCEPTED','ACCEPTED'] if mode=='same_key' else ['ACCEPTED','DENIED'])
    if mode=='same_key':assert outputs[0]['result']['receipt']==outputs[1]['result']['receipt']
    assert sum(o['claims']['REVIEW'] for o in outputs)==1 and sum(o['adapter_calls'] for o in outputs)==1
    assert len([e for e in rows(flow_engine,t.events) if e['event_kind'] in {'REVIEW','REVIEW_PASS'}])==1
    assert len([w for w in rows(flow_engine,t.work) if w['purpose']=='REVIEW'])==1
    assert all(not any(o['effects'].values()) for o in outputs)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),outputs=outputs,actual_processes=2,
        child_ready=ready,held_fence_backend_pid=holder_pid,overlapping_postgresql_waiters=waiting)


def test_PSE07_existing_other_component_work_not_taken_over(flow_engine,identities,enabled,request):
    from controlled_escalate_reviewer import provision_review as provision_esc
    from returnops_domain.review_sources import COMPONENT as ESC_COMPONENT
    case,version=ready_pass(flow_engine,identities);provision_esc(flow_engine,identities)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        LifecycleGuards(ESC_COMPONENT).prepare(uow,case,version,EscalateReviewAccepted,now());uow.commit()
    before=snapshot(flow_engine);adapter=ControlledPassReviewer();result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and not adapter.calls and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


def test_PSE04_lower_guard_independently_revalidates_output(flow_engine,identities,enabled,request,monkeypatch):
    from returnops_domain import pass_review
    case,version=ready_pass(flow_engine,identities)
    monkeypatch.setattr(pass_review,'check_review',lambda *a:None)
    adapter=ControlledPassReviewer(mutate=lambda body,*a:body['model_run'].update(provider_id='forged'))
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and len(adapter.calls)==1 and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),bypassed='outer check only; real lower guard active')


@pytest.mark.parametrize('mode',['work_claim','binding_projection','raw_customer_source'])
def test_PSE04_lower_guard_rechecks_actual_source_after_outer_read(flow_engine,identities,enabled,request,monkeypatch,mode):
    from returnops_domain.storage import original_statement_contents
    case,version=ready_pass(flow_engine,identities);caller=receiver(flow_engine);original=caller.guard.apply;injected=[]
    def changed(uow,event,at):
        assert type(event) is PassReviewAccepted
        # This call site occurs after the receiver read the complete accepted
        # proposal and staged the review. Change real source rows in that same
        # transaction before the independent low-level read.
        proposal=next(r for r in uow.execute(select(old.history)).mappings() if r['kind']=='PROPOSAL')
        if mode=='work_claim':uow.execute(update(t.work).where(t.work.c.purpose=='PROPOSAL').values(claim_id='changed_original_claim'))
        elif mode=='binding_projection':uow.execute(update(t.sources).where(t.sources.c.record_id==proposal['record_id']).values(order_projection_id=None))
        else:uow.execute(update(original_statement_contents).values(raw_text=b'changed after outer validation'))
        injected.append(mode)
        return original(uow,event,at)
    monkeypatch.setattr(caller.guard,'apply',changed)
    before=snapshot(flow_engine);result=caller.accept(case,version,'original-review-key','lower_proof')
    assert injected==[mode] and result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),injected=injected)


@pytest.mark.parametrize('mode',['grant_disabled','grant_revision','claim','epoch','owner','store','lease_clock'])
def test_PSE05_lower_final_source_read_rechecks_current_fence(flow_engine,identities,enabled,request,monkeypatch,mode):
    from returnops_domain import pass_review_sources
    case,version=ready_pass(flow_engine,identities);caller=receiver(flow_engine);original=pass_review_sources.accepted_review;injected=[]
    def changed(uow,*args,**kwargs):
        seal=original(uow,*args,**kwargs)
        if not injected:
            injected.append(mode)
            if mode.startswith('grant_'):uow.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(
                **({'enabled':False} if mode=='grant_disabled' else {'revision':2})))
            elif mode in {'claim','epoch'}:uow.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(
                **({'claim_id':'changed_final_claim'} if mode=='claim' else {'epoch':99})))
            elif mode in {'owner','store'}:uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(
                **({'owner_principal_id':'changed_owner'} if mode=='owner' else {'store_id':'changed_store'})))
            else:caller.guard.clock=lambda:now()+timedelta(seconds=1000)
        return seal
    # The receiver holds its imported original alias; this patch is selected
    # specifically by the lower guard's before_commit runtime import.
    monkeypatch.setattr(pass_review_sources,'accepted_review',changed)
    before=snapshot(flow_engine);result=caller.accept(case,version,'original-review-key','final_fence')
    assert injected==[mode] and result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),injected=injected)


@pytest.mark.parametrize('flow_engine',[LEGACY],indirect=True)
def test_PSE12_exact_0007_not_new_pass_execution(flow_engine,identities,enabled,request):
    case,version=ready_pass(flow_engine,identities,grant=False)
    before=snapshot(flow_engine);adapter=ControlledPassReviewer();result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and snapshot(flow_engine)==before and not adapter.calls
    with flow_engine.connect() as connection:assert schema_version(connection)==LEGACY
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),legacy_compatibility_only=True)


@pytest.mark.parametrize('outcome',['PASS','PASS_WITH_WARNING'])
def test_PSE11_installed_wheel_outside_checkout_actual_invocation(flow_engine,identities,enabled,request,tmp_path,installed_manual,outcome):
    from hashlib import sha256
    case,version=ready_pass(flow_engine,identities);root=Path(__file__).resolve().parents[2]
    path=tmp_path/'installed-config.json';path.write_text(json.dumps(dict(case=case,version=version,schema=flow_engine._customer_test_schema,outcome=outcome)),encoding='utf8')
    hashes={}
    for name in ['pass_review.py','pass_review_sources.py','pass_review_denial.py','pass_scenario.py','lifecycle_events.py','lifecycle_guards.py','lifecycle_projection.py']:
        source=root/'packages/returnops_domain'/name;installed=installed_manual/'returnops_domain'/name
        assert source.read_bytes()==installed.read_bytes();hashes[name]=sha256(installed.read_bytes()).hexdigest()
    assert (root/'apps/api/returnops_api/private_pass_review.py').read_bytes()==(installed_manual/'returnops_api/private_pass_review.py').read_bytes()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'pass_review_helpers.py').exists()
    before=snapshot(flow_engine)
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('pass_review_process_probe.py')),str(path),str(installed_manual)],
        cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=60)
    assert result.returncode==0 and result.stderr==b''
    output=json.loads(result.stdout)
    assert output['result']['status']=='ACCEPTED' and output['result']['receipt']['event_kind']=='REVIEW_PASS'
    assert output['claims']==dict(REVIEW=1) and output['adapter_calls']==1 and not any(output['effects'].values())
    assert rows(flow_engine,old.case_heads)[0]['status']=='AWAITING_APPROVAL'
    assert not rows(flow_engine,t.effects) and not any(r['kind'] in {'DECISION','APPROVAL','OPERATION','NOTIFICATION'} for r in rows(flow_engine,old.history))
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),output=output,installed_hashes=hashes,caller_cwd=str(tmp_path),isolated_python=True)


@pytest.mark.parametrize('mode',['event','binding','work_claim','work_epoch','work_generation','projection','audit','raw_source','bundle','owner','store'])
def test_PSE04_accepted_proposal_requires_actual_records(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    work=next(r for r in rows(flow_engine,t.work) if r['purpose']=='PROPOSAL')
    with flow_engine.begin() as c:
        if mode=='event':c.execute(delete(t.events).where(t.events.c.work_id==work['work_id']))
        elif mode=='binding':c.execute(delete(t.sources).where(t.sources.c.record_id==proposal['record_id']))
        elif mode in {'work_claim','work_epoch','work_generation','owner','store'}:
            key={'work_claim':'claim_id','work_epoch':'epoch','work_generation':'generation','owner':'owner_id','store':'store_id'}[mode]
            c.execute(update(t.work).where(t.work.c.work_id==work['work_id']).values(**{key:99 if mode in {'work_epoch','work_generation'} else 'wrong_identity'}))
        elif mode=='projection':c.execute(update(t.sources).where(t.sources.c.record_id==proposal['record_id']).values(order_projection_id=None))
        elif mode=='audit':c.execute(update(old.audit).values(body=b'{}'))
        elif mode=='raw_source':
            from returnops_domain.storage import original_statement_contents
            c.execute(update(original_statement_contents).values(raw_text=b'corrupted source'))
        else:c.execute(update(old.history_contents).where(old.history_contents.c.record_id==proposal['record_id']).values(body=b'{}'))
    adapter=ControlledPassReviewer();before=snapshot(flow_engine);result=attempt(flow_engine,case,version,adapter=adapter)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    assert not adapter.calls
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))



@pytest.mark.parametrize('mode',['missing','disabled','wrong_component','owner_disabled','wrong_owner_store'])
def test_PSE05_review_authority_entry(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    with flow_engine.begin() as c:
        q=t.authorities.c.component_id==COMPONENT
        if mode=='missing':c.execute(delete(t.authorities).where(q))
        elif mode=='disabled':c.execute(update(t.authorities).where(q).values(enabled=False))
        elif mode=='wrong_component':c.execute(update(t.authorities).where(q).values(component_id='wrong_component'))
        else:c.execute(update(old.principals).where(old.principals.c.principal_id==identities.people['customer_a']['principal_id']).values(
            **({'enabled':False} if mode=='owner_disabled' else {'store_id':'wrong_store'})))
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))



@pytest.mark.parametrize('mode',['grant_revision','grant_disabled','claim','epoch','lease','owner'])
def test_PSE05_original_claim_and_authority_final(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode.startswith('grant_'):self.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(
                **({'revision':2} if mode=='grant_revision' else {'enabled':False})))
            elif mode=='owner':self.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(owner_principal_id='wrong_owner'))
            else:self.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(**{
                {'claim':'claim_id','epoch':'epoch','lease':'lease_expires_at'}[mode]:
                'replacement_claim' if mode=='claim' else 8 if mode=='epoch' else now()-timedelta(seconds=1)}))
            return super().commit()
    before=snapshot(flow_engine);result=attempt(flow_engine,case,version,uow_factory=Changed)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))



@pytest.mark.parametrize('mode',['expired','grant_revision','claim','owner'])
def test_PSE05_slow_source_validation_expires_original_lease(flow_engine,identities,enabled,request,monkeypatch,mode):
    from returnops_domain import pass_review
    case,version=ready_pass(flow_engine,identities);caller=receiver(flow_engine)
    original=pass_review.accepted_review
    def delayed(*args,**kwargs):
        result=original(*args,**kwargs)
        uow=args[0]
        if mode=='expired':caller.clock=lambda:now()+timedelta(seconds=1000)
        elif mode=='grant_revision':uow.execute(update(t.authorities).where(t.authorities.c.component_id==COMPONENT).values(revision=2))
        elif mode=='claim':uow.execute(update(t.work).where(t.work.c.purpose=='REVIEW').values(claim_id='replacement_claim'))
        else:uow.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(owner_principal_id='changed_owner'))
        return result
    monkeypatch.setattr(pass_review,'accepted_review',delayed)
    before=snapshot(flow_engine);result=caller.accept(case,version,'original-review-key','review_correlation')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),delay='after final complete-source validation')



@pytest.mark.parametrize('mode',['old_stamp_new_check','new_stamp_old_check','partial','missing','unknown','multiple','extra_table','unvalidated',
    'literal_space','literal_parenthesis','literal_cast'])
def test_PSE12_corrupt_schema_fails_closed(flow_engine,identities,enabled,request,mode):
    case,version=ready_pass(flow_engine,identities)
    with flow_engine.begin() as c:
        if mode=='old_stamp_new_check':c.execute(text("UPDATE alembic_version SET version_num='0007_lifecycle_guards'"))
        elif mode in {'new_stamp_old_check','unvalidated','literal_space','literal_parenthesis','literal_cast'}:
            c.execute(text('ALTER TABLE lifecycle_work DROP CONSTRAINT ck_lifecycle_work'))
            last={'literal_space':'RE VIEW','literal_parenthesis':'RE(VIEW)','literal_cast':'RE::textVIEW'}.get(mode,'REVIEW')
            expression="purpose IN ('PROPOSAL','REVISION','OUTCOME','NOTIFICATION','EFFECT'"+(", '"+last+"')" if mode!='new_stamp_old_check' else ')')+" AND state IN ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED') AND epoch >= 0"
            c.execute(text('ALTER TABLE lifecycle_work ADD CONSTRAINT ck_lifecycle_work CHECK ('+expression+')'+(' NOT VALID' if mode=='unvalidated' else '')))
        elif mode in {'partial','missing'}:
            c.execute(text('DROP TABLE lifecycle_authorities' if mode=='partial' else 'ALTER TABLE lifecycle_work DROP CONSTRAINT ck_lifecycle_work'))
        elif mode=='unknown':c.execute(text("UPDATE alembic_version SET version_num='unknown_revision'"))
        elif mode=='multiple':c.execute(text("INSERT INTO alembic_version VALUES ('unknown_revision')"))
        else:c.execute(text('CREATE TABLE unexpected_business_table (id integer)'))
    before=snapshot(flow_engine)
    assert not readiness(flow_engine)
    with CustomerUnitOfWork(flow_engine,write=True) as uow:
        with pytest.raises(FlowError):installed(uow)
    result=attempt(flow_engine,case,version)
    assert result.status=='DENIED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))



