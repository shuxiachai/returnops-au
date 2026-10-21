"""G7/G9/G11: actual separate processes, PG fence waits and installed sources."""
from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic,sleep
import pytest
from sqlalchemy import text
from returnops_domain import customer_tables as old,lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.return_execution_tables import controls,ledger
from return_label_bridge_helpers import ready,accepted_rows,rows,snapshot,evidence
from test_manual_postgresql import installed_manual
import label_artifact_binding as database_binding


def installed_proof(installed):
    root=Path(__file__).resolve().parents[2]
    names=['return_label_bridge.py','return_label_sources.py','return_execution_sources.py',
        'execution_preparation_sources.py','approval_admission_sources.py']
    pairs=[('packages/returnops_domain/'+name,'returnops_domain/'+name) for name in names]
    pairs.append(('apps/api/returnops_api/private_return_label_bridge.py','returnops_api/private_return_label_bridge.py'))
    hashes={}
    for source,target in pairs:
        raw=(root/source).read_bytes();assert raw==(installed/target).read_bytes();hashes[source]=sha256(raw).hexdigest()
    assert not (installed/'tests').exists() and not (installed/'return_label_bridge_helpers.py').exists()
    return hashes


def verify_child_sources(value,hashes):
    expected={source.removeprefix('packages/').removeprefix('apps/api/').removesuffix('.py').replace('/','.'):h for source,h in hashes.items()}
    assert value['installed_hashes']==expected


def launch(engine,identities,arguments,installed,tmp_path,index,children,mode='accept',signal=False):
    auth=identities.auth_config;marker=tmp_path/f'bridge-signal-{index}.json'
    raw=os.environ['DATABASE_URL'];assert database_binding.target_url(raw,component='bridge')==engine.url
    with engine.connect() as connection:
        identity=database_binding.observe(connection.exec_driver_sql,engine._customer_test_schema)
    binding=database_binding.parent_binding(raw,engine.url,engine._customer_test_schema,identity,os.environ,component='bridge')
    config=dict(schema=engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,
        signing_key=auth.signing_key.hex(),token=identities.tokens['founder'],arguments=arguments,mode=mode,database_binding=binding)
    if signal:config['signal']=str(marker)
    command=[sys.executable,'-I','-B','-X','utf8',str(Path(__file__).with_name('return_label_bridge_probe.py')),str(installed)]
    output=tmp_path/f'bridge-{index}.stdout.bin';error=tmp_path/f'bridge-{index}.stderr.bin'
    with output.open('xb') as out,error.open('xb') as err:
        process=subprocess.Popen(command,cwd=tmp_path,env=os.environ.copy(),stdin=subprocess.PIPE,stdout=out,stderr=err)
        child=dict(process=process,signal=marker,stdout=output,stderr=error,command=command,schema=config['schema'])
        # Register ownership before closing parent streams or any further I/O.
        children.append(child)
        process.stdin.write(json.dumps(config).encode('utf8'));process.stdin.close()
    return child


def stop_preserving_children(request,children,reason):
    try:
        saved=[dict(pid=item['process'].pid,poll=item['process'].poll(),command=item['command'],schema=item['schema'])
            for item in children]
        emergency=dict(stopped=True,reason=reason,pytest_process=os.getpid(),owned_children=saved,
            streams_final=False,no_kill=True,no_retry=True,schema_retained=True)
        # This writable directory was exercised before Popen. Record identities
        # locally even when the optional MANUAL_EVIDENCE_DIR hook is disabled.
        folder=children[0]['stdout'].parent
        with (folder/'bridge-emergency.json').open('x',encoding='utf8') as stream:json.dump(emergency,stream)
        for item,row in zip(children,saved):
            for name in ('stdout','stderr'):
                data=item[name].read_bytes();sample=item[name].with_suffix('.sample.bin')
                with sample.open('xb') as stream:stream.write(data)
                row[name+'_sample']=dict(path=str(sample),size=len(data),sha256=sha256(data).hexdigest())
        with (folder/'bridge-emergency-samples.json').open('x',encoding='utf8') as stream:json.dump(emergency,stream)
        evidence(request.node.nodeid,**emergency)
    except BaseException as error:
        # A storage failure cannot fall through to fixture schema teardown.
        # Exception messages may contain sensitive paths/data, so log type only.
        try:sys.stderr.write(json.dumps(dict(bridge_emergency_evidence_error=type(error).__name__,exit_code=124))+'\n')
        except BaseException:pass
    finally:
        try:sys.stdout.flush();sys.stderr.flush()
        except BaseException:pass
        # Exit only the current pytest child. Never kill its owned processes.
        # The outer executor must treat124 as incomplete, with retained schema.
        os._exit(124)


def completed(request,child,all_children):
    with preserve_running_on_failure(request,all_children):
        try:child['process'].wait(timeout=60)
        except subprocess.TimeoutExpired:stop_preserving_children(request,all_children,'owned process timeout')
        out=child['stdout'].read_bytes();err=child['stderr'].read_bytes()
        assert child['process'].returncode==0 and err==b'',(child['process'].returncode,err.decode('utf8','replace'))
        result=json.loads(out)
        assert all(count==0 for name,count in result['counts'].items() if name!='effect_claim')
        return result


@contextmanager
def preserve_running_on_failure(request,children):
    try:yield
    except BaseException:
        if any(item['process'].poll() is None for item in children):
            stop_preserving_children(request,children,'parent assertion or observation failed with an owned child still running')
        raise


@pytest.mark.parametrize('changed',['same','original_key','expected_version'])
def test_RB_G7_G11_installed_processes_wait_on_actual_pg_fence(flow_engine,identities,enabled,request,tmp_path,installed_manual,changed):
    arguments,_=ready(flow_engine,identities);hashes=installed_proof(installed_manual);before=snapshot(flow_engine)
    children=[]
    with preserve_running_on_failure(request,children):
        with CustomerUnitOfWork(flow_engine,write=True) as holder:
            holder_pid=holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            for index in range(2):
                values=deepcopy(arguments)
                if index==1 and changed=='original_key':values['original_approval_key']='replacement-original-key'
                if index==1 and changed=='expected_version':values['expected_case_version']+=1
                launch(flow_engine,identities,values,installed_manual,tmp_path,index,children,signal=True)
            deadline=monotonic()+8
            while not all(item['signal'].exists() and item['signal'].stat().st_size for item in children):
                if monotonic()>=deadline:stop_preserving_children(request,children,'fence signal timeout')
                if not all(item['process'].poll() is None for item in children):
                    stop_preserving_children(request,children,'owned child exited before observed fence wait')
                sleep(.02)
            announced=[json.loads(item['signal'].read_bytes()) for item in children];pids=[item['pid'] for item in announced]
            assert len(set(pids))==2 and holder_pid not in pids
            waiting=[]
            while len(waiting)!=2:
                with flow_engine.connect() as observer:
                    waiting=[dict(row) for row in observer.execute(text("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),dict(a=pids[0],b=pids[1])).mappings()]
                if monotonic()>=deadline:stop_preserving_children(request,children,'actual advisory waiter timeout')
                if len(waiting)!=2:sleep(.02)
            assert all(holder_pid in row['blockers'] for row in waiting);holder.commit()
        results=[completed(request,item,children) for item in children]
        for result in results:verify_child_sources(result,hashes)
        assert len({row['process'] for row in results})==2
        assert sorted(row['result']['status'] for row in results)==(['ACCEPTED','REPLAYED'] if changed=='same' else ['ACCEPTED','DENIED'])
        assert sum(row['counts']['effect_claim'] for row in results)==1 and len(accepted_rows(flow_engine))==1
        after=snapshot(flow_engine)
        assert rows(flow_engine,old.case_heads)[0]['case_version']==arguments['expected_case_version']+1
        assert after[controls.name]==before[controls.name] and after[ledger.name]==before[ledger.name]
        assert after[old.history.name]==before[old.history.name]
        assert {name for name in before if before[name]!=after[name]}=={
            old.case_heads.name,old.audit.name,life.work.name,life.sources.name,life.events.name}
        evidence(request.node.nodeid,changed=changed,holder=holder_pid,announced=announced,actual_waiters=waiting,
            results=results,installed_hashes=hashes,before=before,after=after)


@pytest.mark.parametrize('initial',['absent','accepted'])
def test_RB_G9_G11_new_process_recovery_is_readonly(flow_engine,identities,enabled,request,tmp_path,installed_manual,initial):
    arguments,_=ready(flow_engine,identities);hashes=installed_proof(installed_manual);children=[];first=None
    with preserve_running_on_failure(request,children):
        if initial=='accepted':
            child=launch(flow_engine,identities,arguments,installed_manual,tmp_path,'accept',children)
            first=completed(request,child,children);assert first['result']['status']=='ACCEPTED' and first['counts']['effect_claim']==1
            verify_child_sources(first,hashes)
        before=snapshot(flow_engine)
        child=launch(flow_engine,identities,arguments,installed_manual,tmp_path,'restart',children,mode='recover')
        result=completed(request,child,children)
        verify_child_sources(result,hashes)
        assert result['result']['status']==('UNKNOWN' if initial=='absent' else 'REPLAYED')
        assert result['counts']['effect_claim']==0 and snapshot(flow_engine)==before
        if first is not None:
            assert first['process']!=result['process'] and first['result']['event_id']==result['result']['event_id']
            assert first['result']['label_context']==result['result']['label_context']
        else:assert result['result']['label_context'] is None and accepted_rows(flow_engine)==[]
        evidence(request.node.nodeid,initial=initial,first=first,restarted=result,installed_hashes=hashes,before=before,after=snapshot(flow_engine))


class ControlledProcessMetadata:
    """No OS child or PG connection: failure-path metadata only."""
    def __init__(self,pid,returncode):self.pid,self.returncode=pid,returncode
    def poll(self):return self.returncode
    def wait(self,timeout):
        assert timeout==60 and self.returncode==0
        return self.returncode


class ControlledPreservedExit(BaseException):pass


def controlled_child(tmp_path,index,payload,returncode):
    out=tmp_path/f'controlled-{index}.stdout.bin';err=tmp_path/f'controlled-{index}.stderr.bin'
    out.write_bytes(payload);err.write_bytes(b'')
    return dict(process=ControlledProcessMetadata(40000+index,returncode),stdout=out,stderr=err,
        command=['controlled-metadata-only'],schema='customer_test_'+'a'*32)


@pytest.mark.parametrize('fault,error_type',[('json',json.JSONDecodeError),('key',KeyError),('counter',AssertionError)])
@pytest.mark.parametrize('peer_running',[False,True])
def test_RB_offline_process_guard_result_failures(request,tmp_path,monkeypatch,fault,error_type,peer_running):
    payload={'json':b'{','key':b'{}','counter':b'{"counts":{"provider":1}}'}[fault]
    first=controlled_child(tmp_path,1,payload,0)
    peer=controlled_child(tmp_path,2,b'',None if peer_running else 0)
    children=[first,peer];stops=[]
    def preserved(request,children,reason):
        stops.append(dict(pids=[item['process'].pid for item in children],reason=reason))
        raise ControlledPreservedExit()
    monkeypatch.setattr(sys.modules[__name__],'stop_preserving_children',preserved)
    with pytest.raises(ControlledPreservedExit if peer_running else error_type):completed(request,first,children)
    assert len(stops)==int(peer_running)
    if peer_running:assert stops[0]['pids']==[40001,40002] and peer['process'].poll() is None


@pytest.mark.parametrize('fault',['sample','evidence','optional_evidence_absent'])
def test_RB_offline_process_guard_evidence_failure_still_exits(request,tmp_path,monkeypatch,fault):
    child=controlled_child(tmp_path,3,b'partial-child-output',None);exits=[]
    def controlled_exit(code):
        exits.append(code);raise ControlledPreservedExit()
    def optional_evidence(*args,**kwargs):
        if fault=='evidence':raise OSError('controlled evidence write failure')
    monkeypatch.setattr(os,'_exit',controlled_exit)
    monkeypatch.setattr(sys.modules[__name__],'evidence',optional_evidence)
    original=Path.read_bytes
    if fault=='sample':
        def failed_sample(path):
            if path==child['stdout']:raise OSError('controlled sample read failure')
            return original(path)
        monkeypatch.setattr(Path,'read_bytes',failed_sample)
    with pytest.raises(ControlledPreservedExit):stop_preserving_children(request,[child],'controlled failure-path probe')
    assert exits==[124] and child['process'].poll() is None
    emergency=json.loads((tmp_path/'bridge-emergency.json').read_bytes())
    assert emergency['owned_children'][0]['pid']==40003
    assert emergency['owned_children'][0]['schema']==child['schema']
    assert emergency['owned_children'][0]['command']==['controlled-metadata-only']
    assert emergency['streams_final'] is False and emergency['schema_retained'] is True
    if fault!='sample':
        saved=json.loads((tmp_path/'bridge-emergency-samples.json').read_bytes())
        sample=saved['owned_children'][0]['stdout_sample']
        assert Path(sample['path']).read_bytes()==b'partial-child-output'
        assert sample['sha256']==sha256(b'partial-child-output').hexdigest()
