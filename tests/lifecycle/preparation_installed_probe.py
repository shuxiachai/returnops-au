"""Actual isolated installed caller/process probe, invoked only by cloud PG tests."""
import json
import os
from pathlib import Path
import socket
import sys
from dataclasses import asdict

sys.path.insert(0,sys.argv[2])
from sqlalchemy import create_engine, text
from returnops_api.private_execution_preparation import compose_private_execution_preparation
from returnops_api.security.authentication import AuthConfig
from returnops_domain.lifecycle_guards import LifecycleGuards
from returnops_domain import customer_uow
import returnops_domain.execution_preparation as service_module
import returnops_domain.execution_preparation_sources as proof_module
import returnops_domain.execution_preparation_tables as table_module
import returnops_domain.execution_preparation_schema as schema_module
import returnops_api.private_execution_preparation as composition_module


if __name__=='__main__':
    installed=Path(sys.argv[2]).resolve()
    for module in (service_module,proof_module,table_module,schema_module,composition_module):
        assert Path(module.__file__).resolve().is_relative_to(installed)
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'options':'-c search_path='+config['schema']+' -c statement_timeout=10000'})
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_execution_preparation(engine,auth,'Bearer '+config['token'])
    effects=dict(RETURN=0,LABEL=0,notification_send=0,LLM=0,outbound=0,claims=0)
    def no_claim(*args,**kwargs): effects['claims']+=1; raise AssertionError('No claim permitted')
    def no_outbound(*args,**kwargs): effects['outbound']+=1; raise AssertionError('No outbound call permitted')
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send',
           'complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names: effects[names[frame.f_code.co_name]]+=1
    original_fence=customer_uow.acquire_fence
    announced=[]
    def fence(connection,*,write):
        if config.get('signal') and not announced:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            signal=Path(config['signal']); pending=signal.with_suffix('.writing')
            with pending.open('x',encoding='utf-8') as output:
                json.dump(dict(pid=pid,process=os.getpid()),output)
            pending.replace(signal)
            announced.append(pid)
        return original_fence(connection,write=write)
    customer_uow.acquire_fence=fence
    LifecycleGuards.claim=no_claim; socket.create_connection=no_outbound
    sys.setprofile(profile)
    result=caller.prepare(**config['arguments'])
    sys.setprofile(None)
    assert not any(effects.values())
    print(json.dumps(dict(result=asdict(result),effects=effects,backend=announced,process=os.getpid())))
    engine.dispose()
