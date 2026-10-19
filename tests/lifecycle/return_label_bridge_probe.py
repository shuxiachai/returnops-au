"""Private installed-wheel process; configuration contains synthetic test auth."""
from dataclasses import asdict
from functools import partial
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys

sys.path.insert(0,sys.argv[2])
from sqlalchemy import create_engine,event,select,text
from sqlalchemy.engine import make_url
from returnops_api.private_return_label_bridge import compose_private_return_label_bridge
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow,lifecycle_tables as life
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.lifecycle_guards import LifecycleGuards


def main():
    installed=Path(sys.argv[2]).resolve();config=json.loads(Path(sys.argv[1]).read_bytes())
    assert re.fullmatch(r'customer_test_[a-f0-9]{32}',config['schema'])
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    modules=['returnops_domain.return_label_bridge','returnops_domain.return_label_sources',
        'returnops_api.private_return_label_bridge','returnops_domain.return_execution_sources',
        'returnops_domain.execution_preparation_sources','returnops_domain.approval_admission_sources']
    hashes={}
    for name in modules:
        path=Path(importlib.import_module(name).__file__).resolve();assert path.is_relative_to(installed)
        hashes[name]=sha256(path.read_bytes()).hexdigest()
    url=make_url(os.environ['DATABASE_URL'])
    assert url.host=='127.0.0.1' and url.port==55433
    if 'ARTIFACT_DATABASE_NAME' in os.environ:
        assert url.database==os.environ['ARTIFACT_DATABASE_NAME']
        assert url.database in ('returnops_f02_a203_artifact_20261016','returnops_f02_a203_artifact_v02_20261016','returnops_f02_a203_artifact_v04_20261018')
        expected_oid=int(os.environ['ARTIFACT_DATABASE_OID'])
    elif 'LABEL_DATABASE_NAME' in os.environ:
        assert url.database==os.environ['LABEL_DATABASE_NAME']=='returnops_f02_a203_label_main_20261016'
        expected_oid=int(os.environ['LABEL_DATABASE_OID'])
    else:
        assert url.database==os.environ['BRIDGE_DATABASE_NAME']=='returnops_f02_a203_return_label_bridge_20261015'
        expected_oid=int(os.environ['BRIDGE_DATABASE_OID'])
    assert expected_oid>0
    engine=create_engine(url,hide_parameters=True,echo=False,
        connect_args={'connect_timeout':3,'options':'-c search_path='+config['schema']+' -c statement_timeout=15000'})
    def exact_database(connection,record):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),oid,current_setting('server_version_num') FROM pg_database WHERE datname=current_database()")
            database,oid,version=cursor.fetchone()
        connection.rollback()
        assert (database,oid,int(version))==(url.database,expected_oid,170011)
    event.listen(engine,'connect',exact_database)
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_return_label_bridge(engine,auth,'Bearer '+config['token'],
        uow_factory=partial(customer_uow.CustomerUnitOfWork,lock_timeout_ms=10000))
    counts=dict(provider=0,LABEL=0,RETURN=0,notification_send=0,LLM=0,outbound=0,notification_claim=0,effect_claim=0)
    def provider(*args,**kwargs):
        counts['provider']+=1;raise AssertionError('Unexpected provider call')
    CoreReturnMock.perform=provider
    claim=LifecycleGuards.claim
    def observed_claim(self,uow,work_id,*args,**kwargs):
        purpose=uow.execute(select(life.work.c.purpose).where(life.work.c.work_id==work_id)).scalar_one()
        if purpose=='NOTIFICATION':counts['notification_claim']+=1
        if purpose=='EFFECT':counts['effect_claim']+=1
        return claim(self,uow,work_id,*args,**kwargs)
    LifecycleGuards.claim=observed_claim
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send',
        'complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names:counts[names[frame.f_code.co_name]]+=1
    def outbound(*args,**kwargs):
        counts['outbound']+=1;raise AssertionError('Unexpected outbound connection')
    socket.create_connection=outbound
    fence=customer_uow.acquire_fence;announced=[]
    def observed_fence(connection,*,write):
        if config.get('signal') and not announced:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            target=Path(config['signal']);pending=target.with_suffix('.writing')
            with pending.open('x',encoding='utf8') as stream:json.dump(dict(pid=pid,process=os.getpid()),stream)
            pending.replace(target);announced.append(pid)
        return fence(connection,write=write)
    customer_uow.acquire_fence=observed_fence
    sys.setprofile(profile)
    try:
        arguments=config['arguments']
        if config['mode']=='recover':
            result=caller.recover_return_source(**{key:arguments[key] for key in
                ('case_id','execution_work_id','original_approval_key','correlation_id')})
        else:
            assert config['mode']=='accept';result=caller.accept_return_source(**arguments)
    finally:sys.setprofile(None)
    engine.dispose()
    print(json.dumps(dict(result=asdict(result),counts=counts,process=os.getpid(),announced=announced,
        installed_hashes=hashes,cwd=str(Path.cwd().resolve()))))


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never serialize exception messages/URLs/config/tokens to child streams.
        print(json.dumps(dict(probe_error_type=type(error).__name__)),file=sys.stderr)
        raise SystemExit(1) from None
