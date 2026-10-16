"""Separate installed OS processes, observed PG waiters and restart observation."""
from copy import deepcopy
from hashlib import sha256
import json,os,subprocess,sys
from pathlib import Path
from time import monotonic,sleep
from types import SimpleNamespace
import pytest
from sqlalchemy import text
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain import customer_tables as old,founder_codec as finite
from returnops_domain.label_execution_tables import controls,ledger,artifact_work
from label_execution_helpers import ready,service,execute,control,assert_complete,rows,snapshot,evidence
from test_label_execution_late_postgresql import LostResponse
from test_manual_postgresql import installed_manual
from test_return_label_bridge_process_postgresql import preserve_running_on_failure,stop_preserving_children


def installed_proof(installed):
    root=Path(__file__).resolve().parents[2]
    names=['label_execution','label_execution_sources','label_execution_tables','label_execution_schema','label_execution_history',
        'core_label_mock','execution_chain_sources','return_execution_sources','execution_preparation_sources','execution_preparation','lifecycle_schema','lifecycle_state']
    pairs=[('packages/returnops_domain/'+n+'.py','returnops_domain/'+n+'.py') for n in names]
    pairs += [('apps/api/returnops_api/'+n+'.py','returnops_api/'+n+'.py') for n in ('private_label_execution','database')]
    hashes={}
    for source,target in pairs:
        raw=(root/source).read_bytes();assert raw==(installed/target).read_bytes();hashes[source]=sha256(raw).hexdigest()
    assert not (installed/'tests').exists() and not (installed/'label_execution_helpers.py').exists()
    return hashes


def launch(engine,identities,args,installed,tmp_path,index,children,*,mode='execute',signal=False):
    auth=identities.auth_config;marker=tmp_path/f'label-signal-{index}.json'
    config=dict(schema=engine._customer_test_schema,issuer=auth.issuer,audience=auth.audience,signing_key=auth.signing_key.hex(),
        token=identities.tokens['founder'],arguments=args,mode=mode)
    if signal:config['signal']=str(marker)
    command=[sys.executable,'-I','-B','-X','utf8',str(Path(__file__).with_name('label_execution_probe.py')),str(installed)]
    output=tmp_path/f'label-{index}.stdout.bin';error=tmp_path/f'label-{index}.stderr.bin'
    with output.open('xb') as out,error.open('xb') as err:
        proc=subprocess.Popen(command,cwd=tmp_path,env=os.environ.copy(),stdin=subprocess.PIPE,stdout=out,stderr=err)
        child=dict(process=proc,signal=marker,stdout=output,stderr=error,command=command,schema=config['schema'])
        children.append(child)
        # Register ownership first. No credentials/config are written to disk.
        proc.stdin.write(json.dumps(config).encode('utf8'));proc.stdin.close()
    return child


def completed(request,child,children):
    with preserve_running_on_failure(request,children):
        try:child['process'].wait(timeout=60)
        except subprocess.TimeoutExpired:stop_preserving_children(request,children,'label owned process timeout')
        out=child['stdout'].read_bytes();err=child['stderr'].read_bytes()
        assert child['process'].returncode==0 and err==b'',(child['process'].returncode,err.decode('utf8','replace'))
        value=json.loads(out)
        assert all(v==0 for k,v in value['counts'].items() if k not in {'label_dispatch','label_query'})
        return value


def verify_child_sources(value,hashes):
    expected={source.removeprefix('packages/').removeprefix('apps/api/').removesuffix('.py').replace('/','.'):h for source,h in hashes.items()}
    assert value['installed_hashes']==expected


def exact_process_delta(engine,args,winner,before,mode):
    after=snapshot(engine);row=control(engine);prior_head,=before[old.case_heads.name];head,=after[old.case_heads.name]
    count=3 if mode=='execute' else 1
    record_ids=[row['first_record_id'],row['dispatch_record_id'],row['confirmation_record_id']]
    audit_ids=[row['first_audit_id'],row['dispatch_audit_id'],row['confirmation_audit_id']]
    new_records=record_ids if mode=='execute' else record_ids[-1:]
    new_audits=audit_ids if mode=='execute' else audit_ids[-1:]
    for name,key,expected in ((old.history.name,'record_id',new_records),(old.history_contents.name,'record_id',new_records),
            ('founder_history_encodings','record_id',new_records),(old.audit.name,'event_id',new_audits)):
        previous={r[key]:r for r in before[name]};current={r[key]:r for r in after[name]}
        assert {k:current[k] for k in previous}==previous
        assert set(current)-set(previous)==set(expected) and len(after[name])==len(before[name])+count
    history=sorted((r for r in rows(engine,old.history) if r['object_id']==row['operation_id']),key=lambda r:r['object_version'])
    assert [r['record_id'] for r in history]==record_ids and [r['object_version'] for r in history]==[1,2,3]
    assert [r['recorded_sequence'] for r in history]==list(range(history[0]['recorded_sequence'],history[0]['recorded_sequence']+3))
    bodies=[finite.decode_document(next(r['body'] for r in rows(engine,old.history_contents) if r['record_id']==h['record_id'])) for h in history]
    assert [b['attempt_count'] for b in bodies]==[1,1,1] and [b['status'] for b in bodies]==['PENDING','EXECUTING','EXECUTING']
    assert [b['case_version'] for b in bodies]==[args['expected_case_version'],args['expected_case_version']+1,args['expected_case_version']+1]
    assert all('result' not in b for b in bodies)
    assert row['pre_dispatch_case_version']==args['expected_case_version'] and row['dispatch_case_version']==args['expected_case_version']+1
    assert row['confirmation_case_version']==head['case_version'] and row['query_epoch']==(0 if mode=='execute' else 1)
    audit=next(r for r in after[old.audit.name] if r['event_id']==row['confirmation_audit_id'])
    expected_head={**prior_head,'history_sequence':prior_head['history_sequence']+count,
        'audit_sequence':prior_head['audit_sequence']+count,'audit_head':audit['event_hash']}
    if mode=='execute':
        assert_complete(engine,args,SimpleNamespace(**winner['result']),before)
        expected_head.update(case_version=prior_head['case_version']+1,updated_at=row['dispatch_at'].isoformat())
    else:
        assert {n for n in before if before[n]!=after[n]}=={old.case_heads.name,old.history.name,old.history_contents.name,
            old.audit.name,'founder_history_encodings',controls.name,artifact_work.name}
        assert after[ledger.name]==before[ledger.name] and before[artifact_work.name]==[] and len(after[artifact_work.name])==1
        prior_control,=before[controls.name];current_control,=after[controls.name]
        allowed={'query_epoch','query_claim_id','query_lease_until','confirmation_record_id','confirmation_audit_id','confirmation_case_version',
            'confirmed_ledger_hash','confirmed_provider_operation_id','confirmed_provider_label_id','confirmed_effect_status','confirmation_retained'}
        assert {k:v for k,v in prior_control.items() if k not in allowed}=={k:v for k,v in current_control.items() if k not in allowed}
    assert head==expected_head
    work,=rows(engine,artifact_work);fact,=rows(engine,ledger)
    assert work['state']=='PENDING' and work['epoch']==0 and work['control_id']==row['control_id'] and work['case_id']==args['case_id']
    assert work['confirmed_ledger_hash']==fact['fact_hash']==row['confirmed_ledger_hash']
    assert work['confirmation_record_id']==row['confirmation_record_id'] and work['confirmation_case_version']==head['case_version']
    assert all(work[k] is None for k in ('claim_id','lease_expires_at','claimed_case_version','authority_revision'))
    return after


@pytest.mark.parametrize('mode,changed',[('execute','same'),('execute','original_key'),('execute','expected_version'),('reconcile','same')])
def test_LE_G6_G11_installed_two_processes_observe_actual_PG_fence_and_one_effect(flow_engine,identities,enabled,request,tmp_path,installed_manual,mode,changed):
    args,_=ready(flow_engine,identities);hashes=installed_proof(installed_manual);children=[]
    if mode=='reconcile':assert execute(service(flow_engine,identities,mock_factory=LostResponse),args).status=='UNKNOWN'
    before=snapshot(flow_engine)
    with preserve_running_on_failure(request,children):
        with CustomerUnitOfWork(flow_engine,write=True) as holder:
            holder_pid=holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            for i in range(2):
                values=deepcopy(args)
                if i==1 and changed=='original_key':values['original_approval_key']='replacement-original-key'
                if i==1 and changed=='expected_version':values['expected_case_version']+=1
                launch(flow_engine,identities,values,installed_manual,tmp_path,i,children,mode=mode,signal=True)
            deadline=monotonic()+8
            while not all(c['signal'].exists() and c['signal'].stat().st_size for c in children):
                if monotonic()>=deadline:stop_preserving_children(request,children,'label signal timeout')
                if not all(c['process'].poll() is None for c in children):stop_preserving_children(request,children,'label child exited before wait observation')
                sleep(.02)
            announced=[json.loads(c['signal'].read_bytes()) for c in children];pids=[r['pid'] for r in announced]
            assert len(set(pids))==2 and holder_pid not in pids
            waiting=[]
            while len(waiting)!=2:
                with flow_engine.connect() as observer:
                    waiting=[dict(r) for r in observer.execute(text("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"),dict(a=pids[0],b=pids[1])).mappings()]
                if monotonic()>=deadline:stop_preserving_children(request,children,'label actual waiter timeout')
                if len(waiting)!=2:sleep(.02)
            assert all(holder_pid in r['blockers'] for r in waiting);holder.commit()
        results=[completed(request,c,children) for c in children]
        for result in results:verify_child_sources(result,hashes)
        assert len({r['process'] for r in results})==2
        winners=[r for r in results if r['result']['status']=='COMMITTED'];assert len(winners)==1,results
        other=next(r for r in results if r is not winners[0])
        if changed!='same':assert other['result']['status']=='DENIED'
        else:
            # The second transaction may observe the reserved or confirmed
            # state. Its exact disclosed confirmation determines its status.
            assert other['result']['status']==('UNKNOWN' if other['result']['confirmation_record_id'] is None else 'REPLAYED')
            assert other['counts']['label_dispatch']==other['counts']['label_query']==0
        assert sum(r['counts']['label_dispatch'] for r in results)==(mode=='execute')
        assert sum(r['counts']['label_query'] for r in results)==(mode=='reconcile')
        assert len(rows(flow_engine,ledger))==len(rows(flow_engine,artifact_work))==1
        assert control(flow_engine)['confirmed_effect_status']=='SUCCEEDED'
        after=exact_process_delta(flow_engine,args,winners[0],before,mode)
        evidence(request.node.nodeid,mode=mode,changed=changed,holder_pid=holder_pid,announced=announced,actual_waiters=waiting,
            results=results,installed_hashes=hashes,before=before,after=after)


@pytest.mark.parametrize('initial',['absent','confirmed'])
def test_LE_G8_G11_new_installed_process_observation_is_readonly(flow_engine,identities,enabled,request,tmp_path,installed_manual,initial):
    args,_=ready(flow_engine,identities);hashes=installed_proof(installed_manual);children=[];first=None
    with preserve_running_on_failure(request,children):
        if initial=='confirmed':
            first=completed(request,launch(flow_engine,identities,args,installed_manual,tmp_path,'first',children),children)
            verify_child_sources(first,hashes)
            assert first['result']['status']=='COMMITTED' and first['counts']['label_dispatch']==1
        before=snapshot(flow_engine)
        result=completed(request,launch(flow_engine,identities,args,installed_manual,tmp_path,'restart',children,mode='reconcile'),children)
        verify_child_sources(result,hashes)
        assert result['result']['status']==('UNKNOWN' if initial=='absent' else 'REPLAYED')
        assert result['counts']['label_dispatch']==result['counts']['label_query']==0 and snapshot(flow_engine)==before
        if first is not None:
            assert first['process']!=result['process'] and first['result']['operation_id']==result['result']['operation_id']
        evidence(request.node.nodeid,initial=initial,first=first,restarted=result,installed_hashes=hashes,before=before,after=snapshot(flow_engine))
