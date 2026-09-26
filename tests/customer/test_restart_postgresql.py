"""Durable work survives actual process loss and application lifespan restart."""
import base64,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
from fastapi.testclient import TestClient
from returnops_api.main import create_app
from returnops_domain import customer_tables as t
from returnops_domain.audit import identifier
from returnops_domain.intake_processor import IntakeProcessor

def child(engine,identities,operation):
    private={'schema':engine._customer_test_schema,'operation':operation,'issuer':identities.auth_config.issuer,
             'audience':identities.auth_config.audience,'key':base64.b64encode(identities.auth_config.signing_key).decode(),
             'token':identities.tokens['customer_a']}
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('process_probe.py'))],input=json.dumps(private).encode(),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,env=os.environ.copy())
    assert result.returncode==0 and result.stdout==b'' and result.stderr==b''

def test_process_loss_after_acceptance_recovers_same_receipt_then_worker_lease(flow_engine,identities):
    child(flow_engine,identities,'create-crash')
    flow=identities.flow();result=flow.create({'original_message':'process synthetic original'},'process-create-key',identifier('corr'))
    assert result.replayed and result.body['status']=='SUBMITTED'
    child(flow_engine,identities,'claim-crash')
    with flow_engine.connect() as c: assert c.execute(select(t.intake_work.c.state)).scalar_one()=='RUNNING'
    worker=IntakeProcessor(flow_engine,clock=lambda:datetime.now(timezone.utc)+timedelta(seconds=60))
    assert worker.run_once()
    assert flow.get_case(result.body['case_id']).body['status']=='AWAITING_INFORMATION'
    with flow_engine.connect() as c:
        assert c.execute(select(func.count()).select_from(t.acceptances)).scalar_one()==1
        assert c.execute(select(func.count()).select_from(t.intake_work)).scalar_one()==1
        assert c.execute(select(t.intake_work.c.claim_epoch)).scalar_one()==2

def test_lifespan_polls_previously_accepted_work_without_get_trigger(flow_engine,identities):
    flow=identities.flow();accepted=flow.create({'original_message':'restart pending'},'restart-key',identifier('corr')).body
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config)):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            with flow_engine.connect() as c: state=c.execute(select(t.intake_work.c.state)).scalar_one()
            if state=='DONE':break
            time.sleep(0.02)
        assert state=='DONE'
    assert flow.get_case(accepted['case_id']).body['case_version']==2
    with TestClient(create_app(engine=flow_engine,auth_config=identities.auth_config)):
        with flow_engine.connect() as c: assert c.execute(select(func.count()).select_from(t.audit)).scalar_one()==2
