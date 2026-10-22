"""Cloud-only AC08 installed process barriers; execution evidence is required."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic,sleep
import pytest
from sqlalchemy import text
from returnops_domain import lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.notification_tables import controls,facts
from notification_helpers import ready,service,rows,snapshot,evidence
from test_manual_postgresql import installed_manual
from test_notification_delivery_postgresql import LostReply
from test_return_label_bridge_process_postgresql import preserve_running_on_failure,stop_preserving_children
import label_artifact_binding as database_binding


def launch(engine,identities,work_id,installed,tmp_path,index,children,mode):
    auth=identities.auth_config;signal=tmp_path/f'notification-{index}.json'
    raw=os.environ['DATABASE_URL'];assert database_binding.target_url(raw)==engine.url
    with engine.connect() as connection:
        identity=database_binding.observe(connection.exec_driver_sql,engine._customer_test_schema)
    binding=database_binding.parent_binding(raw,engine.url,engine._customer_test_schema,identity,os.environ)
    config=dict(schema=engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,
        signing_key=auth.signing_key.hex(),token=identities.tokens['founder'],work_id=work_id,
        mode=mode,database_binding=binding,signal=str(signal))
    command=[sys.executable,'-I','-B','-X','utf8',str(Path(__file__).with_name('notification_process_probe.py')),str(installed)]
    stdout=tmp_path/f'notification-{index}.stdout.bin';stderr=tmp_path/f'notification-{index}.stderr.bin'
    with stdout.open('xb') as out,stderr.open('xb') as err:
        child=subprocess.Popen(command,cwd=tmp_path,env=os.environ.copy(),stdin=subprocess.PIPE,stdout=out,stderr=err)
        entry=dict(process=child,signal=signal,stdout=stdout,stderr=stderr,command=command,
                   schema=config['schema']);children.append(entry)
        child.stdin.write(json.dumps(config).encode('utf-8'));child.stdin.close()
    return entry


def result(request,child,children,installed):
    with preserve_running_on_failure(request,children):
        try:child['process'].wait(timeout=90)
        except subprocess.TimeoutExpired:stop_preserving_children(request,children,'notification owned-process timeout')
        stdout=child['stdout'].read_bytes();stderr=child['stderr'].read_bytes()
        assert child['process'].returncode==0 and stderr==b'',(child['process'].returncode,stderr)
        value=json.loads(stdout);root=Path(__file__).resolve().parents[2]
        assert 'returnops_domain.notification_service' in value['installed_hashes']
        for module,expected in value['installed_hashes'].items():
            relative=module.replace('.','/')
            candidates=[relative+'.py',relative+'/__init__.py']
            selected=[name for name in candidates if (installed/name).is_file()]
            assert len(selected)==1
            name=selected[0];source=root/('apps/api/' if module.startswith('returnops_api') else 'packages/')/name
            assert sha256(source.read_bytes()).hexdigest()==expected
            assert source.read_bytes()==(installed/name).read_bytes()
        assert value['binding_helper_sha256']==sha256(Path(database_binding.__file__).read_bytes()).hexdigest()
        assert not (installed/'tests').exists()
        assert all(value['counts'][name]==0 for name in
            ('return_provider','label_provider','artifact_retrieve','render','text_line','assembly','expected_pdf'))
        return value


@pytest.mark.parametrize('mode',['send','reconcile'])
def test_two_installed_processes_contend_on_observed_fence_without_double_effect(
        flow_engine,identities,enabled,request,tmp_path,installed_manual,mode):
    setup=ready(flow_engine,identities);children=[]
    if mode=='reconcile':
        assert service(flow_engine,identities,mock=LostReply(flow_engine)).send(setup['work_id']).status=='UNKNOWN'
        assert len(rows(flow_engine,facts))==1
    before=snapshot(flow_engine)
    with preserve_running_on_failure(request,children):
        with CustomerUnitOfWork(flow_engine,write=True,lock_timeout_ms=10000) as holder:
            holder_pid=holder.execute(text('SELECT pg_backend_pid()')).scalar_one()
            for index in range(2):
                launch(flow_engine,identities,setup['work_id'],installed_manual,tmp_path,index,children,mode)
            deadline=monotonic()+8
            while not all(child['signal'].exists() for child in children):
                if monotonic()>=deadline or not all(child['process'].poll() is None for child in children):
                    stop_preserving_children(request,children,'notification signal timeout/early exit')
                sleep(.02)
            pids=[json.loads(child['signal'].read_bytes())['pid'] for child in children]
            assert len(set(pids))==2;waiting=[]
            while len(waiting)!=2:
                with flow_engine.connect() as observer:
                    waiting=[dict(row) for row in observer.execute(text(
                        "SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers "
                        "FROM pg_stat_activity WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),
                        dict(a=pids[0],b=pids[1])).mappings()]
                if monotonic()>=deadline:stop_preserving_children(request,children,'notification waiter timeout')
                if len(waiting)!=2:sleep(.02)
            assert all(holder_pid in row['blockers'] for row in waiting)
            holder.commit()
        completed=[result(request,child,children,installed_manual) for child in children]
        assert len({item['process'] for item in completed})==2
        assert any(item['result']['status']=='SENT' for item in completed)
        assert all(item['result']['status'] in {'SENT','UNKNOWN'} for item in completed)
        assert sum(item['counts']['insert'] for item in completed)==int(mode=='send')
        assert sum(item['counts']['send'] for item in completed)==int(mode=='send')
        control=rows(flow_engine,controls)[0]
        assert control['attempt_count']==1 and control['state']=='SENT'
        assert len(rows(flow_engine,facts))==1
        events=[row for row in rows(flow_engine,life.events) if row['event_kind']=='NOTIFICATION']
        assert len(events)==2
        frozen=snapshot(flow_engine)
        restarted=result(request,launch(flow_engine,identities,setup['work_id'],installed_manual,
            tmp_path,'restart',children,'reconcile'),children,installed_manual)
        assert restarted['result']['status']=='SENT'
        assert restarted['counts']['send']==restarted['counts']['insert']==0
        assert snapshot(flow_engine)==frozen
        evidence(request.node.nodeid,holder_pid=holder_pid,actual_waiters=waiting,
            installed_processes=completed,restarted=restarted,before=before,after=frozen)
