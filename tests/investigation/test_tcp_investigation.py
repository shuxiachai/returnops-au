"""Actual loopback HTTP, two independent API processes, and durable restart."""
import base64,json,os,socket,subprocess,sys,time
from contextlib import contextmanager
from pathlib import Path
import httpx
from sqlalchemy import select
from returnops_api.demo import _require_private_output_runtime
from returnops_domain import customer_tables as old, investigation_tables as t
from test_outcomes_postgresql import rows

# Controlled trusted test composition, not an endpoint or production setting.
# The schema fixture belongs only to this test; no shared baseline is mutated.
_CHILD = r"""
import os,re
from sqlalchemy import create_engine
from returnops_api.main import create_app
from returnops_api.customer_config import load_private_auth_config
import uvicorn
schema=os.environ['RETURNOPS_TEST_SCHEMA']
assert re.fullmatch(r'customer_test_[0-9a-f]{32}',schema)
engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,pool_size=4,max_overflow=4,
    connect_args={'options':'-c search_path='+schema+' -c statement_timeout=10000'})
app=create_app(engine=engine,auth_config=load_private_auth_config(),enable_processor=os.environ['RETURNOPS_TEST_WORKERS']=='1')
uvicorn.run(app,host='127.0.0.1',port=int(os.environ['RETURNOPS_TEST_PORT']),access_log=False,log_level='warning')
"""

@contextmanager
def api_process(engine,auth_file,logs,*,workers):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    environment=os.environ.copy()
    environment.update(RETURNOPS_AUTH_FILE=str(auth_file),RETURNOPS_TEST_SCHEMA=engine._customer_test_schema,
        RETURNOPS_TEST_WORKERS='1' if workers else '0',RETURNOPS_TEST_PORT=str(port),PYTHONDONTWRITEBYTECODE='1')
    with logs.open('wb') as output:
        process=subprocess.Popen([sys.executable,'-B','-c',_CHILD],env=environment,stdout=output,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        url='http://127.0.0.1:'+str(port)
        try:
            ready=False;deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if process.poll() is not None: break
                try:
                    response=httpx.get(url+'/health/ready',timeout=1)
                    if response.status_code==200: ready=True;break
                except httpx.RequestError: pass
                time.sleep(.05)
            assert ready,'Owned test API did not become ready'
            yield url,process.pid
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
            assert process.poll() is not None


def await_status(client,case,status):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        response=client.get('/v1/cases/'+case)
        assert response.status_code==200
        body=response.json()
        if body['status']==status: return body
        time.sleep(.05)
    raise AssertionError('Expected bounded investigation status was not reached')


def test_tcp_restart_two_processes_reference_and_alternative(flow_engine,identities,enabled,tmp_path):
    _require_private_output_runtime()
    private=tmp_path/'private';private.mkdir(mode=0o700)
    auth=private/'auth.json'
    auth.write_text(json.dumps({'issuer':identities.auth_config.issuer,'audience':identities.auth_config.audience,
        'signing_key_base64':base64.b64encode(identities.auth_config.signing_key).decode('ascii')}),encoding='utf-8')
    headers={'Authorization':'Bearer '+identities.tokens['customer_a']}
    original_request={'original_message':'preserved TCP customer message'}
    logs=[tmp_path/('api-'+str(i)+'.log') for i in range(3)]
    with api_process(flow_engine,auth,logs[0],workers=False) as (url,first_pid):
        with httpx.Client(base_url=url,headers=headers,timeout=5) as client:
            assert client.get('/v1/session').status_code==200
            response=client.post('/v1/cases',json=original_request,headers={'Idempotency-Key':'tcp-create-key'})
            assert response.status_code==201;original=response.json();case=original['case_id']
            assert (original['status'],original['input_version'])==('SUBMITTED',1)
    assert rows(flow_engine,old.intake_work)[0]['state']=='PENDING'
    assert rows(flow_engine,t.work)==[]
    with api_process(flow_engine,auth,logs[1],workers=True) as (url,second_pid),api_process(flow_engine,auth,logs[2],workers=True) as (other_url,third_pid):
        assert len({first_pid,second_pid,third_pid})==3
        with httpx.Client(base_url=url,headers=headers,timeout=5) as client,httpx.Client(base_url=other_url,headers=headers,timeout=5) as other:
            view=await_status(client,case,'AWAITING_INFORMATION')
            replay=other.post('/v1/cases',json=original_request,headers={'Idempotency-Key':'tcp-create-key'})
            assert replay.status_code==201 and replay.json()==original
            group=next(r for r in rows(flow_engine,t.groups) if r['case_id']==case)
            request={'expected_case_version':view['case_version'],'question_set_id':view['clarification']['question_set_id'],
                'answers':[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],'evidence_ids':[]}
            accepted=other.post('/v1/cases/'+case+'/clarifications',json=request,headers={'Idempotency-Key':'tcp-answer-key'})
            assert accepted.status_code==202;receipt=accepted.json()
            assert (receipt['status'],receipt['input_version'])==('UNDER_INVESTIGATION',2)
            current=await_status(client,case,'POLICY_ASSESSMENT');assert current['input_version']==3
            assert client.post('/v1/cases/'+case+'/clarifications',json=request,headers={'Idempotency-Key':'tcp-answer-key'}).json()==receipt
            assert client.get('/v1/cases/'+case,headers={'Authorization':'Bearer '+identities.tokens['customer_b']}).status_code==404
            assert client.get('/v1/cases/'+case,headers={'Authorization':'Bearer '+identities.tokens['founder']}).status_code==403
            alternative=client.post('/v1/cases',json={'original_message':'alternative evidence case'},headers={'Idempotency-Key':'tcp-alternative-create'}).json()
            alt_case=alternative['case_id'];alt_view=await_status(other,alt_case,'AWAITING_INFORMATION')
            alt_group=next(r for r in rows(flow_engine,t.groups) if r['case_id']==alt_case)
            answer={'expected_case_version':alt_view['case_version'],'question_set_id':alt_view['clarification']['question_set_id'],
                'answers':[{'question_id':alt_group['context_question_id'],'text':'Purchase details for later human verification.'}],'evidence_ids':[]}
            response=client.post('/v1/cases/'+alt_case+'/clarifications',json=answer,headers={'Idempotency-Key':'tcp-alternative-answer'})
            assert response.status_code==202
            deadline=time.monotonic()+10;paused=False
            while time.monotonic()<deadline:
                paused=any(r['case_id']==alt_case and r['input_version']==2 and r['safe_reason']=='ALTERNATIVE_PROOF_REQUIRES_VERIFICATION' for r in rows(flow_engine,t.work))
                if paused: break
                time.sleep(.05)
            assert paused and other.get('/v1/cases/'+alt_case).json()['status']=='UNDER_INVESTIGATION'
    assert len([r for r in rows(flow_engine,t.receipts) if r['case_id']==case])==2
    assert len([r for r in rows(flow_engine,t.projections) if r['case_id']==case])==1
    assert len([r for r in rows(flow_engine,t.projections) if r['case_id']==alt_case])==0
    raw=b''.join(path.read_bytes() for path in logs)
    assert original_request['original_message'].encode() not in raw
    for token in identities.tokens.values(): assert token.encode() not in raw
    assert base64.b64encode(identities.auth_config.signing_key) not in raw
