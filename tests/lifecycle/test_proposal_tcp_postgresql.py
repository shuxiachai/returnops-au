"""Real HTTP acceptance and opt-in background production across API restart."""
import base64
from contextlib import contextmanager
import json
import os
import socket
import subprocess
import sys
import time
import httpx
from returnops_api.demo import _require_private_output_runtime
from returnops_domain import customer_tables as old, investigation_tables as investigation, lifecycle_tables as t
from returnops_domain.proposal_policy import FixedProposalPolicy
from test_proposal_runtime_postgresql import rows, fingerprints

CHILD = """
import os,re
from sqlalchemy import create_engine
from returnops_api.main import create_app
from returnops_api.customer_config import load_private_auth_config
import uvicorn
schema=os.environ['RETURNOPS_TEST_SCHEMA']
assert re.fullmatch(r'customer_test_[0-9a-f]{32}',schema)
engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,pool_size=8,max_overflow=4,
    connect_args={'options':'-c search_path='+schema+' -c statement_timeout=10000'})
app=create_app(engine=engine,auth_config=load_private_auth_config(),enable_processor=True)
uvicorn.run(app,host='127.0.0.1',port=int(os.environ['RETURNOPS_TEST_PORT']),access_log=False,log_level='warning')
"""


@contextmanager
def server(engine,auth,log,*,enabled):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    env=os.environ.copy()
    env.update(RETURNOPS_AUTH_FILE=str(auth),RETURNOPS_TEST_SCHEMA=engine._customer_test_schema,
        RETURNOPS_TEST_PORT=str(port),RETURNOPS_FIXED_PROPOSAL_DEMO='1' if enabled else '0',PYTHONDONTWRITEBYTECODE='1')
    with log.open('wb') as output:
        process=subprocess.Popen([sys.executable,'-B','-c',CHILD],env=env,stdout=output,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        url='http://127.0.0.1:'+str(port)
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                assert process.poll() is None,'Owned API exited before readiness'
                try:
                    if httpx.get(url+'/health/ready',timeout=1).status_code==200:break
                except httpx.RequestError:pass
                time.sleep(.1)
            else:raise AssertionError('Owned API did not become ready')
            yield url,process.pid
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            assert process.poll() is not None


def await_status(client,case,status):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        response=client.get('/v1/founder/cases/'+case)
        assert response.status_code==200
        value=response.json()
        if value['status']==status:return value
        time.sleep(.1)
    raise AssertionError('Owned real worker did not reach the expected bounded state')


def test_http_clarification_to_actual_worker_packet_and_restart(flow_engine,identities,enabled,tmp_path):
    _require_private_output_runtime()
    FixedProposalPolicy(flow_engine).grant('synthetic_au_store',synthetic_demo=True,enabled=True)
    private=tmp_path/'private';private.mkdir(mode=0o700)
    auth=private/'auth.json'
    auth.write_text(json.dumps(dict(issuer=identities.auth_config.issuer,audience=identities.auth_config.audience,
        signing_key_base64=base64.b64encode(identities.auth_config.signing_key).decode('ascii'))),encoding='utf-8')
    customer={'Authorization':'Bearer '+identities.tokens['customer_a']}
    founder={'Authorization':'Bearer '+identities.tokens['founder']}
    first_log=tmp_path/'fixed-api-first.log';second_log=tmp_path/'fixed-api-second.log'
    with server(flow_engine,auth,first_log,enabled=False) as (url,first_pid):
        with httpx.Client(base_url=url,headers=founder,timeout=10) as client:
            response=client.post('/v1/cases',json={'original_message':'Complete synthetic HTTP original'},
                headers={**customer,'Idempotency-Key':'fixed-http-create'})
            assert response.status_code==201
            original_receipt=response.json();case=original_receipt['case_id']
            await_status(client,case,'AWAITING_INFORMATION')
            view=client.get('/v1/cases/'+case,headers=customer).json()
            group=rows(flow_engine,investigation.groups)[0]
            clarification=dict(expected_case_version=view['case_version'],question_set_id=view['clarification']['question_set_id'],
                answers=[{'question_id':group['reference_question_id'],'text':'SYN-1001'}],evidence_ids=[])
            response=client.post('/v1/cases/'+case+'/clarifications',json=clarification,
                headers={**customer,'Idempotency-Key':'fixed-http-clarify'})
            assert response.status_code==202
            await_status(client,case,'POLICY_ASSESSMENT')
            assert rows(flow_engine,t.work)==[] and rows(flow_engine,t.events)==[]
    receipt_bytes=rows(flow_engine,old.receipts);order_bytes=rows(flow_engine,investigation.receipt_contents)
    with server(flow_engine,auth,second_log,enabled=True) as (url,second_pid):
        assert first_pid!=second_pid
        with httpx.Client(base_url=url,headers=founder,timeout=10) as client:
            detail=await_status(client,case,'RISK_REVIEW')
            assert detail['current_proposal']['model_run']['model_id']=='fixture-no-live-model'
            assert detail['current_proposal']['input_version']==detail['input_version']
            assert detail['current_proposal']['recommended_action']=='REFER_FOR_MANUAL_HANDLING'
            before=fingerprints(flow_engine)
            routes=['/v1/founder/cases','/v1/founder/cases/'+case,
                '/v1/founder/cases/'+case+'/history?kind=PROPOSAL','/v1/founder/cases/'+case+'/audit']
            for route in routes:
                assert client.get(route).status_code==200
                assert client.get(route,headers=customer).status_code==403
            assert fingerprints(flow_engine)==before
            history=client.get(routes[2]).json()['items']
            assert len(history)==1 and len(history[0]['content']['statements'])==2
            assert history[0]['content']['statements'][0]['raw_text']=='Complete synthetic HTTP original'
            assert rows(flow_engine,old.receipts)==receipt_bytes and rows(flow_engine,investigation.receipt_contents)==order_bytes
    assert len(rows(flow_engine,t.events))==1
    assert not any(row['kind'] in {'REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION'} for row in rows(flow_engine,old.history))
    logs=first_log.read_bytes()+second_log.read_bytes()
    assert b'Complete synthetic HTTP original' not in logs
    assert all(token.encode() not in logs for token in identities.tokens.values())
    assert base64.b64encode(identities.auth_config.signing_key) not in logs
