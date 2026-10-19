"""Real cross-process fence/concurrency/restart plus installed-byte proof."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
import pytest
from sqlalchemy import text
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.execution_preparation import PreparationResult
from manual_helpers import evidence, snapshot
from preparation_helpers import ready, assert_delta
from test_manual_postgresql import installed_manual


@pytest.mark.parametrize('different',[False,True])
def test_EP_G4_G8_G9_installed_real_process_race_and_restart(flow_engine,identities,enabled,request,tmp_path,installed_manual,different):
    arguments,_=ready(flow_engine,identities); root=Path(__file__).resolve().parents[2]; hashes={}
    names=['execution_preparation.py','execution_preparation_sources.py','execution_preparation_tables.py',
           'execution_preparation_schema.py','approval_admission_sources.py','approve_sources.py','lifecycle_schema.py']
    pairs=[('packages/returnops_domain/'+name,'returnops_domain/'+name) for name in names]
    pairs.append(('apps/api/returnops_api/private_execution_preparation.py','returnops_api/private_execution_preparation.py'))
    for source,target in pairs:
        content=(root/source).read_bytes(); assert content==(installed_manual/target).read_bytes()
        hashes[source]=sha256(content).hexdigest()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'preparation_helpers.py').exists()
    auth=identities.auth_config
    common=dict(schema=flow_engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,
        signing_key=auth.signing_key.hex(),token=identities.tokens['founder'])
    child=Path(__file__).with_name('preparation_installed_probe.py'); processes=[]; signals=[]
    before=snapshot(flow_engine); overlap=None
    try:
        with CustomerUnitOfWork(flow_engine,write=True) as holder:
            holder_pid=holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            for index in range(2):
                call=deepcopy(arguments)
                if different and index==1: call['candidate_command']['parameters']['line_items'][0]['quantity']+=1
                signal=tmp_path/f'preparation-signal-{index}.json'; signals.append(signal)
                config=tmp_path/f'preparation-child-{index}.json'
                config.write_text(json.dumps(dict(**common,arguments=call,signal=str(signal))),encoding='utf-8')
                processes.append(subprocess.Popen([sys.executable,'-I','-B',str(child),str(config),str(installed_manual)],
                    cwd=tmp_path,env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.PIPE))
            deadline=monotonic()+3
            while not all(path.exists() and path.stat().st_size for path in signals):
                assert monotonic()<deadline, 'Both installed processes must announce the real fence entry'
                assert all(process.poll() is None for process in processes)
                sleep(.01)
            announced=[json.loads(path.read_text(encoding='utf-8')) for path in signals]
            pids=[entry['pid'] for entry in announced]
            assert len(set(pids))==2 and holder_pid not in pids
            waiting=[]
            while len(waiting)!=2:
                with flow_engine.connect() as observer:
                    waiting=[dict(row) for row in observer.execute(text(
                        "SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity "
                        "WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),
                        dict(a=pids[0],b=pids[1])).mappings()]
                assert monotonic()<deadline, 'Two real advisory waiters are required'
                if len(waiting)!=2: sleep(.01)
            assert all(holder_pid in row['blockers'] for row in waiting)
            overlap=dict(holder_backend=holder_pid,announced=announced,waiting=waiting)
            holder.commit()
        results=[]
        for process in processes:
            stdout,stderr=process.communicate(timeout=30)
            assert process.returncode==0 and stderr==b''
            results.append(json.loads(stdout))
        statuses=sorted(value['result']['status'] for value in results)
        assert statuses==(['DENIED','PREPARED'] if different else ['PREPARED','REPLAYED'])
        prepared,=[value['result'] for value in results if value['result']['status']=='PREPARED']
        after,_,_=assert_delta(flow_engine,before,PreparationResult(**prepared),arguments)
        for value in results: assert not any(value['effects'].values())
        if not different:
            assert len({value['result']['preparation_id'] for value in results})==1
        # A third new OS process uses the same durable identity after both exit.
        config=tmp_path/'preparation-restart.json'
        config.write_text(json.dumps(dict(**common,arguments=arguments)),encoding='utf-8')
        completed=subprocess.run([sys.executable,'-I','-B',str(child),str(config),str(installed_manual)],
            cwd=tmp_path,env=os.environ.copy(),capture_output=True,timeout=30)
        assert completed.returncode==0 and completed.stderr==b''
        restarted=json.loads(completed.stdout)
        assert restarted['result']=={**prepared,'status':'REPLAYED'} and not any(restarted['effects'].values())
        assert restarted['process'] not in {value['process'] for value in results} and snapshot(flow_engine)==after
        evidence(request.node.nodeid,different_parameters=different,before=before,after=after,
            overlap=overlap,results=results,restarted=restarted,installed_hashes=hashes,
            installed_outside_checkout=True,isolated_python=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill(); process.communicate(timeout=10)
