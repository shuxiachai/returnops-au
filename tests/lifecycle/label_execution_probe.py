"""Out-of-checkout installed call; synthetic auth travels via stdin, never a file."""
from dataclasses import asdict
from functools import partial
from hashlib import sha256
import importlib,json,os,re,socket,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from sqlalchemy import create_engine,event,select,text
from sqlalchemy.engine import make_url
from returnops_api.private_label_execution import compose_private_label_execution
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow,lifecycle_tables as life
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.core_label_mock import CoreLabelMock
from returnops_domain.lifecycle_guards import LifecycleGuards

MODULES=['returnops_domain.label_execution','returnops_domain.label_execution_sources','returnops_domain.label_execution_tables',
    'returnops_domain.label_execution_schema','returnops_domain.label_execution_history','returnops_domain.core_label_mock',
    'returnops_domain.execution_chain_sources','returnops_domain.return_execution_sources','returnops_domain.execution_preparation_sources',
    'returnops_domain.execution_preparation','returnops_domain.lifecycle_schema','returnops_domain.lifecycle_state',
    'returnops_api.private_label_execution','returnops_api.database']


def main():
    installed=Path(sys.argv[1]).resolve();config=json.loads(sys.stdin.buffer.read())
    assert re.fullmatch(r'customer_test_[a-f0-9]{32}',config['schema'])
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    hashes={}
    for name in MODULES:
        path=Path(importlib.import_module(name).__file__).resolve();assert path.is_relative_to(installed)
        hashes[name]=sha256(path.read_bytes()).hexdigest()
    url=make_url(os.environ['DATABASE_URL'])
    assert url.host=='127.0.0.1' and url.port==55433
    if 'ARTIFACT_DATABASE_NAME' in os.environ:
        assert url.database==os.environ['ARTIFACT_DATABASE_NAME']
        assert url.database in ('returnops_f02_a203_artifact_20261016','returnops_f02_a203_artifact_v02_20261016','returnops_f02_a203_artifact_v04_20261018')
        expected_oid=int(os.environ['ARTIFACT_DATABASE_OID'])
    else:
        assert url.database==os.environ['LABEL_DATABASE_NAME']=='returnops_f02_a203_label_main_20261016'
        expected_oid=int(os.environ['LABEL_DATABASE_OID'])
    assert expected_oid>0
    engine=create_engine(url,hide_parameters=True,echo=False,
        connect_args={'connect_timeout':3,'options':'-c search_path='+config['schema']+' -c statement_timeout=15000'})
    def exact_database(connection,record):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),oid,current_setting('server_version_num') FROM pg_database WHERE datname=current_database()")
            name,oid,version=cursor.fetchone()
        connection.rollback();assert (name,oid,int(version))==(url.database,expected_oid,170011)
    event.listen(engine,'connect',exact_database)
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_label_execution(engine,auth,'Bearer '+config['token'],
        uow_factory=partial(customer_uow.CustomerUnitOfWork,lock_timeout_ms=10000))
    counts=dict(return_provider=0,label_dispatch=0,label_query=0,LABEL=0,RETURN=0,notification_send=0,LLM=0,outbound=0,notification_claim=0,effect_claim=0)
    def return_provider(*a,**k):counts['return_provider']+=1;raise AssertionError('No return dispatch/query in label component')
    CoreReturnMock.perform=return_provider
    perform=CoreLabelMock.perform
    def observed_mock(self,ticket,callback):
        counts['label_dispatch' if ticket.kind=='DISPATCH' else 'label_query']+=1
        return perform(self,ticket,callback)
    CoreLabelMock.perform=observed_mock
    claim=LifecycleGuards.claim
    def observed_claim(self,uow,work_id,*args,**kwargs):
        purpose=uow.execute(select(life.work.c.purpose).where(life.work.c.work_id==work_id)).scalar_one()
        if purpose=='NOTIFICATION':counts['notification_claim']+=1
        if purpose=='EFFECT':counts['effect_claim']+=1
        return claim(self,uow,work_id,*args,**kwargs)
    LifecycleGuards.claim=observed_claim
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send','complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names:counts[names[frame.f_code.co_name]]+=1
    def outbound(*a,**k):counts['outbound']+=1;raise AssertionError('No outbound connection')
    socket.create_connection=outbound
    fence=customer_uow.acquire_fence;announced=[]
    def observed_fence(connection,*,write):
        if config.get('signal') and not announced:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one();target=Path(config['signal']);pending=target.with_suffix('.writing')
            with pending.open('x',encoding='utf8') as stream:json.dump(dict(pid=pid,process=os.getpid()),stream)
            pending.replace(target);announced.append(pid)
        return fence(connection,write=write)
    customer_uow.acquire_fence=observed_fence;sys.setprofile(profile)
    try:
        args=config['arguments']
        if config['mode']=='reconcile':result=caller.reconcile_label(**{k:args[k] for k in ('case_id','execution_work_id','original_approval_key','correlation_id')})
        else:assert config['mode']=='execute';result=caller.execute_accepted_label(**args)
    finally:sys.setprofile(None)
    engine.dispose()
    print(json.dumps(dict(result=asdict(result),counts=counts,process=os.getpid(),announced=announced,
        installed_hashes=hashes,cwd=str(Path.cwd().resolve()))))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(probe_error_type=type(error).__name__)),file=sys.stderr)
        raise SystemExit(1) from None
