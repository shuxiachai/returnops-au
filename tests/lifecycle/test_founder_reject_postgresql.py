"""R1-R8 prepared PostgreSQL REJECT acceptance; collection is not execution."""
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import delete, select, update
from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.audit import identifier
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.reject_denial import COMPONENT, OPERATION
from returnops_domain.registry import TrustedRegistry
from manual_helpers import rows, snapshot, business, evidence, now, provision_outcome
from reject_helpers import ready, provision, service, attempt, assert_rejected, mutate_authority, mutate_source
from test_manual_postgresql import observed, expire_human, UnknownCommit





AUTH = ['human_revoked','human_disabled','human_demoted','human_store','owner','service_missing','service_revoked']
@pytest.mark.parametrize('mode', AUTH)
@pytest.mark.parametrize('phase', ['entry','final'])
def test_R03_independent_current_authorities(flow_engine, identities, enabled, request, mode, phase):
    case, body = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            mutate_authority(uow, identities, case, mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_authority(self, identities, case, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    if phase == 'entry' and mode != 'owner':assert result.audit == 'NOT_RECORDED'
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('mode', ['service_revision','claim','epoch','lease','lease_renewal','authority','generation','human_expiry','lease_expiry'])
def test_R03_final_original_claim(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body = ready(flow_engine, identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if mode == 'human_expiry':expire_human(monkeypatch)
            elif mode == 'lease_expiry':caller.guard.clock = lambda:now()+timedelta(seconds=1000)
            else:mutate_authority(self, identities, case, mode)
            return super().commit()
    caller = service(flow_engine, identities, uow_factory=Changed)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-reject-key', 'reject_correlation')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


SOURCES = ['review_event','proposal_event','review_binding','review_claim','review_generation','review_projection',
    'review_body','proposal_body','order_raw','order_claim','order_available','raw_statement','input','generation','preview','failure','block','missing_review','review_fingerprint','review_ESC','review_version','review_audit','approval','outcome','notification','return','label']
@pytest.mark.parametrize('mode', SOURCES)
@pytest.mark.parametrize('phase', ['entry','final'])
def test_R02_retained_source_chain(flow_engine, identities, enabled, request, mode, phase):
    case, body = ready(flow_engine, identities)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:mutate_source(uow, mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_source(self, mode)
            return super().commit()
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('mode', ['wrong_id','wrong_version','stale','actor','generation','review','grant','failure_target',
    'APPROVE','REQUEST_REVISION','MANUAL_HANDLING','ESCALATED','RISK_REVIEW','NOTIFICATION_PENDING'])
def test_R02_request_and_state_scope(flow_engine, identities, enabled, request, mode):
    case, body = ready(flow_engine, identities)
    if mode == 'wrong_id':body['proposal_id'] = 'wrong_proposal'
    elif mode == 'wrong_version':body['proposal_version'] += 1
    elif mode == 'stale':body['expected_case_version'] -= 1
    elif mode in {'actor','generation','review','grant'}:body[mode] = 'injected'
    elif mode == 'failure_target':
        body.pop('proposal_id'); body.pop('proposal_version'); body['processing_failure_id'] = 'failure_target'
    elif mode in {'APPROVE','REQUEST_REVISION','MANUAL_HANDLING'}:body['decision'] = mode
    else:
        with flow_engine.begin() as c:c.execute(update(old.case_heads).values(status=mode))
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('layer', ['service','guard'])
@pytest.mark.parametrize('mode', ['human_expiry','lease_expiry','human_revoked','service_revision','service_revoked',
    'claim','epoch','owner','generation','lease_renewal'])
def test_R03_after_last_source_read(flow_engine, identities, enabled, request, monkeypatch, layer, mode):
    from returnops_domain import reject_decision, reject_sources
    case, body = ready(flow_engine, identities)
    module = reject_decision if layer == 'service' else reject_sources
    original = module.read_target
    injected = []
    def delayed(uow, head, state, request_body, component, **options):
        value = original(uow, head, state, request_body, component, **options)
        if options.get('original_state') is not None:
            if mode == 'human_expiry':expire_human(monkeypatch)
            elif mode == 'lease_expiry':caller.clock = caller.guard.clock = lambda:now()+timedelta(seconds=1000)
            elif mode == 'raw_statement':mutate_source(uow, mode)
            else:mutate_authority(uow, identities, case, mode)
            injected.append(mode)
        return value
    monkeypatch.setattr(module, 'read_target', delayed)
    caller = service(flow_engine, identities)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'original-reject-key', 'reject_correlation')
    assert injected and result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected)


@pytest.mark.parametrize('phase', ['entry','final'])
@pytest.mark.parametrize('mode', ['review_event','raw_statement','review_binding','missing_review'])
def test_R02_lowlevel_cannot_bypass_source_proof(flow_engine, identities, enabled, request, monkeypatch, phase, mode):
    from returnops_domain import reject_decision
    from returnops_domain.lifecycle_state import current
    case, body = ready(flow_engine, identities)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        h = uow.execute(select(old.case_heads)).mappings().one()
        seal = reject_decision.read_target(uow, h, current(uow,h), body, COMPONENT)
    monkeypatch.setattr(reject_decision, 'read_target', lambda *args, **kwargs:seal)
    if phase == 'entry':
        with CustomerUnitOfWork(flow_engine, write=True) as uow:mutate_source(uow,mode); uow.commit()
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase == 'final':mutate_source(self,mode)
            return super().commit()
    before = snapshot(flow_engine); result = attempt(flow_engine, identities, case, body, uow_factory=Changed)
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), outer_check='bypassed deliberately')






def child_config(engine, identities, case, body):
    c = identities.auth_config
    return dict(case=case,request=body,schema=engine._customer_test_schema,issuer=c.issuer,audience=c.audience,
        signing_key=c.signing_key.hex(),token=identities.tokens['founder'])


@pytest.mark.parametrize('keys', ['same','different'])
def test_R04_independent_process_competition(flow_engine, identities, enabled, request, tmp_path, keys):
    import time
    case,body=ready(flow_engine,identities)
    barrier=tmp_path/'barrier';barrier.mkdir()
    before=snapshot(flow_engine)
    children=[];outputs=[]
    try:
        for index in range(2):
            config={**child_config(flow_engine,identities,case,body),'barrier':str(barrier),'worker':str(index),
                'key':'original-reject-key' if keys=='same' else 'reject-key-'+str(index)}
            path=tmp_path/('synthetic-reject-child-'+str(index)+'.json');path.write_text(json.dumps(config),encoding='utf-8')
            args=[sys.executable,'-B',str(Path(__file__).with_name('reject_process_probe.py')),str(path)]
            children.append(subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=os.environ.copy()))
        deadline=time.monotonic()+30
        while len(list(barrier.glob('ready-*')))!=2:
            assert time.monotonic()<deadline and all(c.poll() is None for c in children), 'Both independent callers must become ready'
            time.sleep(0.01)
        (barrier/'release').write_text('release',encoding='utf-8')
        for child in children:
            out,err=child.communicate(timeout=60)
            assert child.returncode==0 and err==b''
            outputs.append(json.loads(out))
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.communicate(timeout=10)
    assert not any(value for output in outputs for value in output['effects'].values())
    assert sum(x['reject_claims'] for x in outputs)==1
    if keys=='same':
        assert all(x['status']=='ACCEPTED' for x in outputs) and outputs[0]['receipt']==outputs[1]['receipt']
    else:assert sorted(x['status'] for x in outputs)==['ACCEPTED','DENIED']
    assert len([r for r in rows(flow_engine,old.acceptances) if r['operation']==OPERATION])==1
    assert len([r for r in rows(flow_engine,t.events) if r['event_kind']=='OUTCOME'])==1
    assert snapshot(flow_engine)['lifecycle_authorities']==before['lifecycle_authorities']
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),outputs=outputs,independent_processes=2,barrier_ready_count=2,keys=keys)


@pytest.mark.parametrize('committed',[True,False])
@pytest.mark.parametrize('revoked',[True,False])
def test_R05_unknown_and_fresh_recovery(flow_engine,identities,enabled,request,committed,revoked):
    case,body=ready(flow_engine,identities)
    class Unknown(UnknownCommit):actual_commit=committed
    caller=service(flow_engine,identities,uow_factory=Unknown)
    before=snapshot(flow_engine); result=caller.accept(case,body,'original-reject-key','unknown')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED'
    actual=snapshot(flow_engine)
    assert len([r for r in rows(flow_engine,old.acceptances) if r['operation']==OPERATION])==int(committed)
    if not committed:assert actual==before
    if revoked:TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
    recovery_before=snapshot(flow_engine); recovered=caller.recover(case,body,'original-reject-key')
    assert snapshot(flow_engine)==recovery_before and recovered.audit=='NOT_ATTEMPTED'
    assert recovered.status==('ACCEPTED' if committed and not revoked else 'UNKNOWN')
    retry=None
    if not committed and not revoked:
        # Independently completed actual rollback plus every-table equality;
        # recovery's absence alone does not permit this explicit caller action.
        retry=attempt(flow_engine,identities,case,body);assert_rejected(flow_engine,case,body,retry)
    evidence(request.node.nodeid,before=before,actual=actual,result=asdict(result),recovered=asdict(recovered),
        retry=None if retry is None else asdict(retry),completion_proof='actual commit' if committed else 'actual rollback + all table equality')


def test_R05_absence_remains_unknown(flow_engine,identities,enabled,request):
    case,body=ready(flow_engine,identities); before=snapshot(flow_engine)
    result=service(flow_engine,identities).recover(case,body,'never-observed-key')
    assert result.status=='UNKNOWN' and result.audit=='NOT_ATTEMPTED' and snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),rollback_proof=False)


def test_R05_every_write_and_final_rolls_back(flow_engine,identities,enabled,observed,request):
    case,body=ready(flow_engine,identities); trace=[]
    class Probe(CustomerUnitOfWork):
        def execute(self,statement,parameters=None):
            if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                trace.append(statement.table.name+(' INSERT' if statement.is_insert else ' UPDATE' if statement.is_update else ' DELETE'))
            return super().execute(statement,parameters)
        def commit(self):
            for check in self._commit_checks:check()
            self.poison();raise FlowError('INVALID_STATE')
    before=snapshot(flow_engine); result=attempt(flow_engine,identities,case,body,uow_factory=Probe)
    assert result.status=='DENIED' and len(trace)>=15 and business(snapshot(flow_engine))==business(before)
    results=[]
    for point in range(1,len(trace)+1):
        class Fault(CustomerUnitOfWork):
            writes=0
            def execute(self,statement,parameters=None):
                if not getattr(statement,'is_select',False) and getattr(statement,'table',None) is not None:
                    self.writes+=1
                    if self.writes==point:self.poison();raise RuntimeError('RAW-SENSITIVE-FAULT')
                return super().execute(statement,parameters)
        before=snapshot(flow_engine); result=attempt(flow_engine,identities,case,body,uow_factory=Fault); after=snapshot(flow_engine)
        assert result.status=='DENIED' and business(after)==business(before) and 'RAW-SENSITIVE' not in str(asdict(result))
        results.append(dict(point=point,write=trace[point-1],before=before,after=after,result=asdict(result)))
    evidence(request.node.nodeid,trace=trace,results=results,effects=observed)


@pytest.mark.parametrize('mode',['recorded','revoked','audit_committed_unknown','audit_rolledback_unknown'])
def test_R05_fresh_denial_after_original_closed(flow_engine,identities,enabled,request,mode):
    case,body=ready(flow_engine,identities)
    class Original(CustomerUnitOfWork):
        exited=False
        def __exit__(self,*args):
            result=super().__exit__(*args);type(self).exited=True
            if mode=='revoked':TrustedRegistry(flow_engine).revoke_session(identities.sessions['founder']['session_id'])
            return result
    class Audit(UnknownCommit if 'unknown' in mode else CustomerUnitOfWork):
        actual_commit=mode=='audit_committed_unknown';enters=0
        def __enter__(self):
            assert Original.exited;type(self).enters+=1;return super().__enter__()
    before=snapshot(flow_engine)
    result=attempt(flow_engine,identities,case,{**body,'expected_case_version':body['expected_case_version']-1},uow_factory=Original,audit_uow=Audit)
    after=snapshot(flow_engine)
    assert result.status=='DENIED' and Audit.enters==1
    assert result.audit==('RECORDED' if mode=='recorded' else 'NOT_RECORDED' if mode=='revoked' else 'UNKNOWN')
    assert len(after['customer_audit_events'])-len(before['customer_audit_events'])==int(mode in {'recorded','audit_committed_unknown'})
    if mode!='revoked':assert business(after)==business(before)
    from returnops_domain.canonical import decode_document,digest
    denials=[decode_document(row['body']) for row in rows(flow_engine,old.audit)
        if decode_document(row['body'])['event_type']=='FOUNDER_REJECT_DENIED']
    assert len(denials)==int(mode in {'recorded','audit_committed_unknown'})
    for event in denials:
        assert event['payload_hash']==digest(dict(purpose='OUTCOME',reason='STALE_CASE_VERSION'),'audit-payload/v1')
        assert event['history_refs']==[] and event['object_ids']==[] and 'payload' not in event
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),audit_enters=Audit.enters)






@pytest.fixture(scope='module')
def installed_reject(tmp_path_factory):
    """Future isolated delivery fixture binds the actual wheel, never an ambient install."""
    import shutil
    from zipfile import ZipFile
    root=Path(__file__).resolve().parents[2]
    build=tmp_path_factory.mktemp('reject-install');source=build/'source';source.mkdir()
    shutil.copy2(root/'pyproject.toml',source/'pyproject.toml')
    for directory in ['packages','apps/api']:
        shutil.copytree(root/directory,source/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.egg-info'))
    environment={**os.environ,'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1'}
    result=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-deps','--no-build-isolation',
        '--wheel-dir',str(build/'wheels'),str(source)],env=environment,cwd=build,capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr.decode('utf-8','replace')
    wheel,=list((build/'wheels').glob('*.whl'));installed=build/'installed'
    result=subprocess.run([sys.executable,'-B','-m','pip','install','--no-deps','--target',str(installed),str(wheel)],
        env=environment,cwd=build,capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr.decode('utf-8','replace')
    modules=['reject_decision.py','reject_denial.py','reject_sources.py','lifecycle_guards.py','pass_review_sources.py','lifecycle_proposal.py']
    pairs={('returnops_domain/'+name):root/'packages/returnops_domain'/name for name in modules}
    pairs['returnops_api/private_reject.py']=root/'apps/api/returnops_api/private_reject.py'
    hashes={}
    with ZipFile(wheel) as archive:
        assert not any(name.startswith('tests/') or 'reject_helpers' in name or 'reject_process_probe' in name for name in archive.namelist())
        for member,original in pairs.items():
            assert original.read_bytes()==archive.read(member)==(installed/member).read_bytes()
            hashes[member]=sha256(archive.read(member)).hexdigest()
    return dict(path=installed,wheel=str(wheel),wheel_sha256=sha256(wheel.read_bytes()).hexdigest(),members=hashes)


@pytest.mark.parametrize('outcome',['PASS','PASS_WITH_WARNING'])
def test_R07_installed_actual_private_call(flow_engine,identities,enabled,request,tmp_path,installed_reject,outcome):
    installed_manual=installed_reject['path']
    case,body=ready(flow_engine,identities,outcome=outcome)
    path=tmp_path/'synthetic-reject-installed.json';path.write_text(json.dumps(child_config(flow_engine,identities,case,body)),encoding='utf-8')
    root=Path(__file__).resolve().parents[2];hashes={}
    modules=['reject_decision.py','reject_denial.py','reject_sources.py','lifecycle_guards.py','pass_review_sources.py','lifecycle_proposal.py']
    for name in modules:
        source=root/'packages/returnops_domain'/name;target=installed_manual/'returnops_domain'/name
        assert source.read_bytes()==target.read_bytes();hashes[name]=sha256(target.read_bytes()).hexdigest()
    assert (root/'apps/api/returnops_api/private_reject.py').read_bytes()==(installed_manual/'returnops_api/private_reject.py').read_bytes()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'reject_helpers.py').exists()
    before=snapshot(flow_engine)
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('reject_process_probe.py')),str(path),str(installed_manual)],
        cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=60)
    assert result.returncode==0 and result.stderr==b''
    output=json.loads(result.stdout)
    assert output['status']=='ACCEPTED' and output['reject_claims']==1 and not any(output['effects'].values())
    after=snapshot(flow_engine);assert after['lifecycle_authorities']==before['lifecycle_authorities']
    assert rows(flow_engine,old.case_heads)[0]['status']=='NOTIFICATION_PENDING' and not rows(flow_engine,t.effects)
    evidence(request.node.nodeid,before=before,after=after,output=output,installed_hashes=hashes,
        wheel_sha256=installed_reject['wheel_sha256'],wheel_members=installed_reject['members'],
        isolated_python=True,cwd=str(tmp_path),review_outcome=outcome)


def test_R07_default_factory_no_grant_or_public_entry(flow_engine,identities,enabled,observed,request):
    from returnops_api.main import create_app
    case,body=ready(flow_engine,identities,grant=False)
    before=snapshot(flow_engine);app=create_app(engine=flow_engine,auth_config=identities.auth_config)
    assert not any('POST' in getattr(r,'methods',set()) and ('decision' in r.path or 'reject' in r.path) for r in app.routes)
    result=attempt(flow_engine,identities,case,body)
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and snapshot(flow_engine)==before
    provision(flow_engine,identities);grants=rows(flow_engine,t.authorities)
    accepted=attempt(flow_engine,identities,case,body);assert_rejected(flow_engine,case,body,accepted)
    assert rows(flow_engine,t.authorities)==grants
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),denied=asdict(result),accepted=asdict(accepted),effects=observed)


@pytest.mark.parametrize('phase',['entry','final'])
def test_R02_primary_binding_requires_actual_review(flow_engine,identities,enabled,request,monkeypatch,phase):
    from returnops_domain import reject_decision
    case,body=ready(flow_engine,identities)
    proposal=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    original=reject_decision.read_target
    if phase=='entry':
        def wrong(uow,*args,**kwargs):
            value=original(uow,*args,**kwargs)
            return {**value,'record':proposal}
        monkeypatch.setattr(reject_decision,'read_target',wrong)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if phase=='final':
                ids=select(t.work.c.work_id).where(t.work.c.component_id==COMPONENT)
                self.execute(update(t.sources).where(t.sources.c.work_id.in_(ids),t.sources.c.slot=='PRIMARY').values(target_record_id=proposal['record_id']))
            return super().commit()
    before=snapshot(flow_engine);result=attempt(flow_engine,identities,case,body,uow_factory=Changed)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),binding='proposal instead of accepted review')




@pytest.mark.parametrize('mode',['target_hash','event_generation','event_fingerprint','binding_target','claim'])
def test_R06_replay_requires_original_reject_proof(flow_engine,identities,enabled,request,mode):
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','reject');assert_rejected(flow_engine,case,body,accepted)
    with flow_engine.begin() as c:
        if mode=='target_hash':c.execute(update(t.work).where(t.work.c.component_id==COMPONENT).values(target_hash='0'*64))
        elif mode=='claim':c.execute(update(t.work).where(t.work.c.component_id==COMPONENT).values(claim_id='replaced'))
        elif mode=='binding_target':c.execute(update(t.sources).where(t.sources.c.work_id.in_(select(t.work.c.work_id).where(t.work.c.component_id==COMPONENT))).values(target_record_id='absent_review'))
        else:c.execute(update(t.events).where(t.events.c.event_kind=='OUTCOME').values(**({'generation':99} if mode=='event_generation' else {'fingerprint':'0'*64})))
    before=snapshot(flow_engine);result=caller.accept(case,body,'original-reject-key','replay')
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    assert caller.recover(case,body,'original-reject-key').status=='UNKNOWN'
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),corruption=mode)


@pytest.mark.parametrize('outcome', ['PASS', 'PASS_WITH_WARNING'])
def test_R01_actual_pass_human_reject_atomic_pending(flow_engine, identities, enabled, observed, request, outcome):
    from returnops_domain import founder_codec as finite
    from returnops_domain.canonical import decode_document
    case, body = ready(flow_engine, identities, outcome=outcome)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body)
    assert_rejected(flow_engine, case, body, result)
    after = snapshot(flow_engine)
    assert after['lifecycle_authorities'] == before['lifecycle_authorities']
    assert after['case_heads'][0]['input_version'] == before['case_heads'][0]['input_version']
    for field in ('generation','input_version','proposal_version','proposal_record_id','review_record_id'):
        assert after['case_lifecycle_state'][0][field] == before['case_lifecycle_state'][0][field]
    decision, = [r for r in rows(flow_engine, old.history) if r['kind'] == 'DECISION']
    binding = next(r for r in rows(flow_engine, t.sources) if r['record_id'] == decision['record_id'])
    assert binding['target_record_id'] == before['case_lifecycle_state'][0]['review_record_id']
    note, = [r for r in rows(flow_engine, old.history) if r['kind'] == 'NOTIFICATION']
    note_binding = next(r for r in rows(flow_engine,t.sources) if r['record_id'] == note['record_id'])
    assert note_binding['slot']=='NOTIFICATION' and note_binding['target_record_id']==decision['record_id']
    assert (note_binding['work_id'],note_binding['claim_id'],note_binding['epoch']) == (
        binding['work_id'],binding['claim_id'],binding['epoch'])
    documents={r['record_id']:finite.decode_document(r['body']) for r in rows(flow_engine,old.history_contents)
        if r['record_id'] in {decision['record_id'],note['record_id']}}
    assert documents[decision['record_id']]['reason']==body['reason']
    assert documents[decision['record_id']]['principal_id']==identities.people['founder']['principal_id']
    assert documents[note['record_id']]['status']=='PENDING' and documents[note['record_id']]['outcome']=='REJECTED'
    assert documents[note['record_id']]['attempt_count']==0
    fact, = [r for r in rows(flow_engine, old.acceptances) if r['operation']==OPERATION]
    assert fact['response_status']==200
    receipt, = [r for r in rows(flow_engine,old.receipts) if r['acceptance_id']==fact['acceptance_id']]
    assert receipt['available'] and decode_document(receipt['body'])==result.receipt
    audit=[decode_document(r['body']) for r in rows(flow_engine,old.audit)]
    human, = [e for e in audit if e['event_type']=='FOUNDER_DECISION_ACCEPTED']
    assert human['actor']=={'kind':'HUMAN','role':'FOUNDER','principal_id':identities.people['founder']['principal_id']}
    assert all('payload' not in e and body['reason'] not in str(e) for e in audit)
    assert len(after['customer_audit_events'])==len(before['customer_audit_events'])+3
    assert all(r in after['customer_history_revisions'] for r in before['customer_history_revisions'])
    evidence(request.node.nodeid,before=before,after=after,result=asdict(result),effects=observed,review_outcome=outcome)


@pytest.mark.parametrize('mode', ['missing','customer','expired','foreign_case'])
def test_R03_entry_identity_never_borrows_review_grant(flow_engine, identities, enabled, request, monkeypatch, mode):
    case,body=ready(flow_engine,identities)
    caller=service(flow_engine,identities,None if mode=='missing' else 'customer_a' if mode=='customer' else 'founder')
    if mode=='expired':expire_human(monkeypatch)
    elif mode=='foreign_case':
        with flow_engine.begin() as c:c.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(store_id='other_store'))
    before=snapshot(flow_engine);result=caller.accept(case,body,'original-reject-key','authority')
    assert result.status=='DENIED' and result.audit=='NOT_RECORDED' and result.receipt is None
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result))


@pytest.mark.parametrize('other', ['manual','revision'])
@pytest.mark.parametrize('first', ['reject','other'])
def test_R04_cross_decision_same_key_both_orders(flow_engine, identities, enabled, observed, request, other, first):
    from manual_helpers import service as manual
    from revision_helpers import ready as revision_ready, service as revision, provision as provision_revision
    if first=='reject':
        case,body=ready(flow_engine,identities)
    else:
        case,body=revision_ready(flow_engine,identities)
        provision(flow_engine,identities)
    provision_outcome(flow_engine,identities);provision_revision(flow_engine,identities)
    callers={'reject':service(flow_engine,identities),'other':manual(flow_engine,identities) if other=='manual' else revision(flow_engine,identities)}
    bodies={'reject':{**body,'decision':'REJECT'},'other':{**body,'decision':'MANUAL_HANDLING' if other=='manual' else 'REQUEST_REVISION'}}
    second='other' if first=='reject' else 'reject'
    accepted=callers[first].accept(case,bodies[first],'cross-decision-key','first')
    assert accepted.status=='ACCEPTED'
    before=snapshot(flow_engine)
    conflict=callers[second].accept(case,bodies[second],'cross-decision-key','conflict')
    late=callers[second].accept(case,bodies[second],'different-decision-key','late')
    assert conflict.status=='DENIED' and conflict.safe_code=='IDEMPOTENCY_CONFLICT' and late.status=='DENIED'
    assert business(snapshot(flow_engine))==business(before)
    assert len([r for r in rows(flow_engine,old.history) if r['kind']=='DECISION'])==1
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),first=asdict(accepted),conflict=asdict(conflict),late=asdict(late),effects=observed)


def test_R04_exact_replay_and_changed_request_conflicts(flow_engine, identities, enabled, observed, request):
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','first');assert_rejected(flow_engine,case,body,accepted)
    before=snapshot(flow_engine)
    replay=caller.accept(case,body,'original-reject-key','replay');recovered=caller.recover(case,body,'original-reject-key')
    assert replay.receipt==recovered.receipt==accepted.receipt and snapshot(flow_engine)==before
    for field,value in [('reason','changed'),('expected_case_version',body['expected_case_version']+1),
            ('proposal_id','changed'),('proposal_version',body['proposal_version']+1)]:
        result=caller.accept(case,{**body,field:value},'original-reject-key','conflict')
        assert result.status=='DENIED' and result.safe_code=='IDEMPOTENCY_CONFLICT'
    replacement=caller.accept(case,{**body,'expected_case_version':body['expected_case_version']+1},'replacement-key','late')
    assert replacement.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),accepted=asdict(accepted),replacement=asdict(replacement),effects=observed)


@pytest.mark.parametrize('changed', ['FAILED','PENDING','SENT'])
def test_R06_later_notification_does_not_replace_original_receipt(flow_engine,identities,enabled,request,changed):
    from reject_helpers import provision_notification
    from synthetic_sources import notify
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','reject');assert_rejected(flow_engine,case,body,accepted)
    original=rows(flow_engine,t.state)[0]['notification_record_id']
    provision_notification(flow_engine,identities)
    for status in ['FAILED','PENDING','SENT']:
        notify(flow_engine,identities,case,status,component=COMPONENT)
        if status==changed:break
    before=snapshot(flow_engine)
    assert rows(flow_engine,t.state)[0]['notification_record_id']!=original
    replay=caller.accept(case,body,'original-reject-key','replay');recovery=caller.recover(case,body,'original-reject-key')
    assert replay.status==recovery.status=='ACCEPTED' and replay.receipt==recovery.receipt==accepted.receipt
    assert snapshot(flow_engine)==before
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),accepted=asdict(accepted),replay=asdict(replay),later_notification=changed)


@pytest.mark.parametrize('removed', ['STATEMENT','EVIDENCE'])
def test_R06_retention_never_reconstructs_reject(flow_engine,identities,enabled,request,removed):
    from returnops_domain.retention import RetentionService
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','reject');assert_rejected(flow_engine,case,body,accepted)
    before=snapshot(flow_engine)
    oid=next(r['object_id'] for r in rows(flow_engine,old.history) if r['kind']==removed)
    assert RetentionService(flow_engine).remove(removed,oid)
    retained=snapshot(flow_engine)
    replay=caller.accept(case,body,'original-reject-key','retained');recovery=caller.recover(case,body,'original-reject-key')
    assert replay.status=='DENIED' and recovery.status=='UNKNOWN' and snapshot(flow_engine)==retained
    derived={r['record_id'] for r in rows(flow_engine,old.history) if r['kind'] in {'PROPOSAL','REVIEW','DECISION','NOTIFICATION'}}
    assert not any(r['record_id'] in derived for r in rows(flow_engine,old.history_contents))
    assert all(r['body'] is None for r in rows(flow_engine,old.receipts) if not r['available'])
    evidence(request.node.nodeid,before=before,retained=retained,replay=asdict(replay),recovery=asdict(recovery))


@pytest.mark.parametrize('mode', ['receipt_missing','receipt_unavailable','receipt_body','original_note_missing',
    'original_note_binding','original_note_body','decision_body','acceptance_time'])
def test_R06_missing_original_data_never_rebuilt(flow_engine,identities,enabled,request,mode):
    from datetime import timedelta
    from reject_helpers import provision_notification
    from synthetic_sources import notify
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','reject');assert_rejected(flow_engine,case,body,accepted)
    initial=rows(flow_engine,t.state)[0]
    fact=next(r for r in rows(flow_engine,old.acceptances) if r['operation']==OPERATION)
    # A valid later note exists, so reading current state would wrongly hide a
    # deleted/corrupted original note. Replay must follow the original binding.
    provision_notification(flow_engine,identities);notify(flow_engine,identities,case,'SENT',component=COMPONENT)
    with flow_engine.begin() as c:
        if mode=='receipt_missing':c.execute(delete(old.receipts).where(old.receipts.c.acceptance_id==fact['acceptance_id']))
        elif mode=='receipt_unavailable':c.execute(update(old.receipts).where(old.receipts.c.acceptance_id==fact['acceptance_id']).values(available=False,body=None))
        elif mode=='receipt_body':c.execute(update(old.receipts).where(old.receipts.c.acceptance_id==fact['acceptance_id']).values(body=b'{}'))
        elif mode=='original_note_missing':c.execute(delete(old.history_contents).where(old.history_contents.c.record_id==initial['notification_record_id']))
        elif mode=='original_note_binding':c.execute(delete(t.sources).where(t.sources.c.record_id==initial['notification_record_id']))
        elif mode=='original_note_body':c.execute(update(old.history_contents).where(old.history_contents.c.record_id==initial['notification_record_id']).values(body=b'{}'))
        elif mode=='decision_body':c.execute(update(old.history_contents).where(old.history_contents.c.record_id==initial['outcome_record_id']).values(body=b'{}'))
        else:c.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id==fact['acceptance_id']).values(accepted_at=fact['accepted_at']+timedelta(seconds=1)))
    before=snapshot(flow_engine)
    replay=caller.accept(case,body,'original-reject-key','missing');recovery=caller.recover(case,body,'original-reject-key')
    assert replay.status=='DENIED' and recovery.status=='UNKNOWN' and business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),replay=asdict(replay),recovery=asdict(recovery),corruption=mode)


def test_R06_founder_reads_preserve_pending_business(flow_engine,identities,enabled,request):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case,body=ready(flow_engine,identities,outcome='PASS_WITH_WARNING')
    accepted=attempt(flow_engine,identities,case,body);assert_rejected(flow_engine,case,body,accepted)
    reader=FounderQueries(flow_engine,CurrentRequestAuthority(identities.auth_config,'Bearer '+identities.tokens['founder']))
    before=snapshot(flow_engine);detail=reader.read('getFounderCase',case).body
    assert detail['current_review']['outcome']=='PASS_WITH_WARNING' and detail['current_review']['findings']
    for kind in ['PROPOSAL','REVIEW','DECISION','NOTIFICATION']:reader.read('listFounderCaseHistory',case,{'kind':kind})
    reader.read('listCaseAudit',case);after=snapshot(flow_engine)
    assert {k:v for k,v in before.items() if not k.startswith('founder_')}=={k:v for k,v in after.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid,before=before,after=after,detail=detail)


@pytest.mark.parametrize('operation',['accept','recover'])
def test_R06_replay_final_source_read_rechecks_exact_schema(flow_engine,identities,enabled,request,monkeypatch,operation):
    from sqlalchemy import text
    from returnops_domain import reject_decision
    case,body=ready(flow_engine,identities);caller=service(flow_engine,identities)
    accepted=caller.accept(case,body,'original-reject-key','first');assert_rejected(flow_engine,case,body,accepted)
    original=reject_decision.accepted_reject;calls=[]
    def after_proof(uow,*args,**options):
        seal=original(uow,*args,**options);calls.append('proof')
        if len(calls)==2:
            # Transaction-local corruption after the final expensive proof,
            # never a migration and rolled back with the denied replay.
            uow.execute(text("UPDATE alembic_version SET version_num = '0007_lifecycle_guards'"))
        return seal
    monkeypatch.setattr(reject_decision,'accepted_reject',after_proof)
    before=snapshot(flow_engine)
    result=(caller.accept(case,body,'original-reject-key','replay') if operation=='accept'
        else caller.recover(case,body,'original-reject-key'))
    assert len(calls)==2 and result.status==('DENIED' if operation=='accept' else 'UNKNOWN')
    assert business(snapshot(flow_engine))==business(before)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),after_final_proof_schema_change=True)


@pytest.mark.parametrize('flow_engine',['0007_lifecycle_guards'],indirect=True)
def test_R08_exact_0007_positive_guard_is_not_new_reject_service(flow_engine,identities,enabled,request):
    from synthetic_sources import ready as legacy_ready, proposal, outcome, notify
    original=legacy_ready(flow_engine,identities);case=original['case_id'];proposal(flow_engine,identities,case)
    with flow_engine.begin() as c:c.execute(update(old.case_heads).where(old.case_heads.c.case_id==case).values(status='AWAITING_APPROVAL'))
    provision(flow_engine,identities)
    head=rows(flow_engine,old.case_heads)[0]
    target=next(r for r in rows(flow_engine,old.history) if r['kind']=='PROPOSAL')
    body=dict(expected_case_version=head['case_version'],decision='REJECT',reason='Exact legacy boundary.',
        proposal_id=target['object_id'],proposal_version=target['object_version'])
    before=snapshot(flow_engine);result=attempt(flow_engine,identities,case,body)
    assert result.status=='DENIED' and business(snapshot(flow_engine))==business(before)
    # Preserve the original exact0007 fixture's positive behavior explicitly;
    # this does not certify modern acceptance with an empty review pointer.
    outcome(flow_engine,identities,case,decision='REJECT',fixture_prepare=False)
    assert notify(flow_engine,identities,case,'FAILED')[1]['status']=='NOTIFICATION_FAILED'
    assert notify(flow_engine,identities,case,'PENDING')[1]['status']=='NOTIFICATION_PENDING'
    assert notify(flow_engine,identities,case,'SENT')[1]['status']=='REJECTED'
    assert not rows(flow_engine,t.effects)
    evidence(request.node.nodeid,before=before,after=snapshot(flow_engine),result=asdict(result),schema='0007_lifecycle_guards',legacy_fixture=True)
