"""P07/P13: installed real OS processes and independently observed PG waiters."""
from hashlib import sha256
from contextlib import contextmanager
import json,os,subprocess,sys
from pathlib import Path
from time import monotonic,sleep
import pytest
from sqlalchemy import text
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.label_artifact_tables import claims,artifacts,contents
from label_artifact_helpers import ready,rows,snapshot,evidence
from test_manual_postgresql import installed_manual
from test_return_label_bridge_process_postgresql import preserve_running_on_failure as original_preserve_running_on_failure,stop_preserving_children

# This must fail during collection rather than enter installed_manual's build fallback.
_diagnostic_source=Path(__file__).resolve().parents[2]
if (os.environ.get('ARTIFACT_DIAGNOSTIC_PHASE') not in {'COLLECTION','EXECUTION'}
        or not os.environ.get('MANUAL_INSTALLED_DIR')
        or Path(os.environ['MANUAL_INSTALLED_DIR']).resolve()!=_diagnostic_source.parent/'installed'
        or not Path(os.environ['MANUAL_INSTALLED_DIR']).is_dir()):
    raise RuntimeError('Explicit isolated diagnostic installed target required')

def diagnostic_stage(request,phase):
    request.node._artifact_diagnostic_phase=phase
    request.node._artifact_diagnostic.emit(phase,'checkpoint')

@contextmanager
def preserve_running_on_failure(request,children):
    # Record before the old guard can abort on a live owned child. Also retain
    # the diagnostic schema on an ordinary failed assertion after children exit.
    with original_preserve_running_on_failure(request,children):
        try:yield
        except BaseException as error:
            log=request.node._artifact_diagnostic
            try:
                log.emit(request.node._artifact_diagnostic_phase,'error',error)
                log.close()
            except BaseException:
                try:os.write(2,b'ARTIFACT_DIAGNOSTIC_LOG_FAILURE\n')
                except BaseException:pass
                os._exit(125)
            if children:
                stop_preserving_children(request,children,'diagnostic parent check failed; original acceptance unchanged')
            try:os.write(2,b'ARTIFACT_DIAGNOSTIC_STOP\n')
            except BaseException:pass
            os._exit(124)

def launch(engine,identities,args,installed,tmp_path,index,children,*,mode='complete',signal=False):
    auth=identities.auth_config;marker=tmp_path/f'artifact-signal-{index}.json'
    config=dict(schema=engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,signing_key=auth.signing_key.hex(),
        token=identities.tokens['founder'],arguments=args,mode=mode)
    assert index in (0,1,'restart')
    config['diagnostic_name']=f'artifact-diagnostic-{index}.jsonl'
    if signal:config['signal']=str(marker)
    command=[sys.executable,'-I','-B','-X','utf8',str(Path(__file__).with_name('label_artifact_probe.py')),str(installed)]
    output=tmp_path/f'artifact-{index}.stdout.bin';error=tmp_path/f'artifact-{index}.stderr.bin'
    with output.open('xb') as out,error.open('xb') as err:
        process=subprocess.Popen(command,cwd=tmp_path,env=os.environ.copy(),stdin=subprocess.PIPE,stdout=out,stderr=err)
        child=dict(process=process,signal=marker,stdout=output,stderr=error,command=command,schema=config['schema']);children.append(child)
        process.stdin.write(json.dumps(config).encode('utf8'));process.stdin.close()
    return child

def completed(request,child,children,installed):
    with preserve_running_on_failure(request,children):
        diagnostic_stage(request,'parent.wait-child')
        try:child['process'].wait(timeout=60)
        except subprocess.TimeoutExpired:stop_preserving_children(request,children,'artifact owned process timeout')
        out=child['stdout'].read_bytes();err=child['stderr'].read_bytes()
        diagnostic_stage(request,'parent.child-exit')
        if child['process'].returncode==125:
            diagnostic_stage(request,'parent.child-log-failure')
            raise RuntimeError('Diagnostic child log failure')
        assert child['process'].returncode==0 and err==b'',(child['process'].returncode,err.decode('utf8','replace'))
        diagnostic_stage(request,'parent.child-json')
        value=json.loads(out)
        pdf_counts={'pdf_render','pdf_text_line','pdf_assembly','pdf_expected','pdf_validation'}
        diagnostic_stage(request,'parent.zero-effects')
        assert all(v==0 for k,v in value['counts'].items() if k not in {'artifact_read',*pdf_counts})
        diagnostic_stage(request,'parent.pdf-counts')
        if value['counts']['artifact_read']:
            assert value['counts']['pdf_render']==value['counts']['pdf_assembly']==value['counts']['pdf_expected']==1
            assert value['counts']['pdf_text_line']>0
        else:assert all(value['counts'][name]==0 for name in pdf_counts-{'pdf_validation'})
        root=Path(__file__).resolve().parents[2]
        diagnostic_stage(request,'parent.installed-hashes')
        assert len(value['installed_hashes'])==24
        for module,hashed in value['installed_hashes'].items():
            relative=module.replace('.','/')+'.py';source=root/('apps/api/' if module.startswith('returnops_api.') else 'packages/')/relative
            assert sha256(source.read_bytes()).hexdigest()==hashed
            assert source.read_bytes()==(installed/relative).read_bytes()
        assert not (installed/'tests').exists()
        return value

def test_LA_P07_P13_two_actual_installed_processes_one_claim_and_completion(flow_engine,identities,enabled,request,tmp_path,installed_manual):
    request.node._artifact_diagnostic=flow_engine._artifact_diagnostic
    request.node._artifact_diagnostic_phase='parent.ready'
    children=[]
    with preserve_running_on_failure(request,children):
        diagnostic_stage(request,'parent.ready')
        args,_=ready(flow_engine,identities)
        diagnostic_stage(request,'parent.snapshot')
        before=snapshot(flow_engine)
        diagnostic_stage(request,'parent.holder')
        with CustomerUnitOfWork(flow_engine,write=True,lock_timeout_ms=10000) as holder:
            # Catch body failures before CustomerUnitOfWork.__exit__ can close
            # the active holder transaction. The production UoW is unchanged.
            with preserve_running_on_failure(request,children):
                holder_pid=holder.execute(text('SELECT pg_backend_pid()')).scalar_one()
                diagnostic_stage(request,'parent.launch')
                for i in range(2):launch(flow_engine,identities,args,installed_manual,tmp_path,i,children,signal=True)
                deadline=monotonic()+8
                diagnostic_stage(request,'parent.signals')
                while not all(c['signal'].exists() for c in children):
                    if monotonic()>=deadline or not all(c['process'].poll() is None for c in children):
                        stop_preserving_children(request,children,'artifact signal timeout or early exit')
                    sleep(.02)
                announced=[json.loads(c['signal'].read_bytes()) for c in children];pids=[r['pid'] for r in announced]
                assert len(set(pids))==2;waiting=[]
                diagnostic_stage(request,'parent.waiters')
                while len(waiting)!=2:
                    with flow_engine.connect() as observer:
                        with preserve_running_on_failure(request,children):
                            waiting=[dict(r) for r in observer.execute(text("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),dict(a=pids[0],b=pids[1])).mappings()]
                    if monotonic()>=deadline:stop_preserving_children(request,children,'artifact actual waiter timeout')
                    if len(waiting)!=2:sleep(.02)
                assert all(holder_pid in r['blockers'] for r in waiting)
                diagnostic_stage(request,'parent.release-holder')
                holder.commit()
        results=[completed(request,c,children,installed_manual) for c in children]
        diagnostic_stage(request,'parent.distinct-processes')
        assert len({r['process'] for r in results})==2
        diagnostic_stage(request,'parent.one-completion')
        assert sum(r['result']['status']=='COMMITTED' for r in results)==1
        diagnostic_stage(request,'parent.result-statuses')
        assert all(r['result']['status'] in {'COMMITTED','REPLAYED','IN_PROGRESS'} for r in results)
        diagnostic_stage(request,'parent.one-read')
        assert sum(r['counts']['artifact_read'] for r in results)==1
        diagnostic_stage(request,'parent.one-claim-artifact-content')
        assert len(rows(flow_engine,claims))==len(rows(flow_engine,artifacts))==len(rows(flow_engine,contents))==1
        diagnostic_stage(request,'parent.before-restart')
        prior=snapshot(flow_engine)
        diagnostic_stage(request,'parent.restart')
        restart=completed(request,launch(flow_engine,identities,args,installed_manual,tmp_path,'restart',children,mode='recover'),children,installed_manual)
        diagnostic_stage(request,'parent.restart-result')
        assert restart['result']['status']=='REPLAYED' and restart['counts']['artifact_read']==0 and snapshot(flow_engine)==prior
        diagnostic_stage(request,'parent.restart-validation')
        assert restart['counts']['pdf_validation']>0
        assert all(restart['counts'][name]==0 for name in ('pdf_render','pdf_text_line','pdf_assembly','pdf_expected'))
        diagnostic_stage(request,'parent.evidence')
        evidence(request.node.nodeid,holder_pid=holder_pid,actual_waiters=waiting,results=results,restarted=restart,before=before,after=prior)
        flow_engine._artifact_diagnostic.emit('parent.complete','return')
        flow_engine._artifact_diagnostic_call_succeeded=True
