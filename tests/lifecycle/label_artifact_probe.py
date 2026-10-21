"""Owned installed process; exact new database and no source checkout imports."""
from dataclasses import asdict
from functools import partial
from hashlib import sha256
import importlib,importlib.util,json,os,re,socket,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from sqlalchemy import create_engine,event,text
from returnops_api.private_label_artifact import compose_private_label_artifact
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.core_label_mock import CoreLabelMock
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock

MODULES=['returnops_domain.'+n for n in ('label_artifact','label_artifact_sources','label_artifact_tables','label_artifact_schema',
    'label_artifact_history','label_artifact_retention','label_artifact_retention_sources','generated_evidence','core_label_artifact_mock','label_pdf','label_pdf_validation',
    'execution_artifact_chain_sources','lifecycle_schema','lifecycle_state','founder_integrity','history','customer_service',
    'label_execution_sources','return_execution_sources','return_label_sources','execution_preparation_sources')]+[
    'returnops_api.private_label_artifact','returnops_api.customer_authority','returnops_api.database']


def main():
    installed=Path(sys.argv[1]).resolve();config=json.loads(sys.stdin.buffer.read())
    assert re.fullmatch(r'customer_test_[a-f0-9]{32}',config['schema'])
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    hashes={}
    for name in MODULES:
        path=Path(importlib.import_module(name).__file__).resolve();assert path.is_relative_to(installed)
        hashes[name]=sha256(path.read_bytes()).hexdigest()
    spec=importlib.util.spec_from_file_location('label_artifact_binding',Path(__file__).resolve().with_name('label_artifact_binding.py'))
    database_binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(database_binding)
    binding=config['database_binding']
    url=database_binding.child_binding(os.environ['DATABASE_URL'],binding,config['schema'],os.environ)
    engine=create_engine(url,hide_parameters=True,echo=False,connect_args={
        'connect_timeout':3,'options':'-c search_path='+config['schema']+' -c statement_timeout=15000'})
    def exact_database(connection,record):
        try:
            with connection.cursor() as cursor:
                identity=database_binding.observe(cursor.execute,config['schema'])
            database_binding.live_identity(binding,identity)
        finally:connection.rollback()
    event.listen(engine,'connect',exact_database)
    with engine.connect():pass
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_label_artifact(engine,auth,'Bearer '+config['token'],
        uow_factory=partial(customer_uow.CustomerUnitOfWork,lock_timeout_ms=10000))
    counts=dict(return_provider=0,label_provider=0,artifact_read=0,outbound=0,notification_send=0,LLM=0)
    def forbidden_return(*a,**k):counts['return_provider']+=1;raise AssertionError('No provider creation or query')
    def forbidden_label(*a,**k):counts['label_provider']+=1;raise AssertionError('No provider creation or query')
    CoreReturnMock.perform=forbidden_return;CoreLabelMock.perform=forbidden_label
    original=CoreLabelArtifactMock.retrieve_original_label
    def observed(self,*a,**k):counts['artifact_read']+=1;return original(self,*a,**k)
    CoreLabelArtifactMock.retrieve_original_label=observed
    def outbound(*a,**k):counts['outbound']+=1;raise AssertionError('No outbound connection')
    socket.create_connection=outbound
    from returnops_domain import label_pdf as pdf,label_pdf_validation as validation,label_artifact_sources as sources
    # Code identity observes preexisting import aliases. Only ordinary T2 may render.
    pdf_codes={function.__code__:name for name,function in dict(pdf_render=pdf.render_label_pdf,
        pdf_text_line=pdf._text_line,pdf_assembly=pdf._assemble_pdf,pdf_expected=sources.expected_pdf,
        pdf_validation=validation.verify_label_pdf).items()}
    counts.update({name:0 for name in pdf_codes.values()})
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in pdf_codes:
            name=pdf_codes[frame.f_code];counts[name]+=1
            if config['mode']=='recover' and name!='pdf_validation':raise AssertionError('Recovery executed renderer code')
        if event=='call' and frame.f_code.co_name in {'send_notification','invoke_model','generate_completion'}:
            counts['notification_send' if frame.f_code.co_name=='send_notification' else 'LLM']+=1
    fence=customer_uow.acquire_fence;announced=[]
    def observed_fence(connection,*,write):
        if config.get('signal') and not announced:
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one();target=Path(config['signal']);pending=target.with_suffix('.writing')
            with pending.open('x',encoding='utf8') as stream:json.dump(dict(pid=pid,process=os.getpid()),stream)
            pending.replace(target);announced.append(pid)
        return fence(connection,write=write)
    customer_uow.acquire_fence=observed_fence;sys.setprofile(profile)
    try:
        if config['mode']=='complete':result=caller.complete_label_artifact(**config['arguments'])
        else:assert config['mode']=='recover';result=caller.recover_label_artifact(**config['arguments'])
    finally:sys.setprofile(None)
    engine.dispose()
    print(json.dumps(dict(result=asdict(result),counts=counts,process=os.getpid(),announced=announced,installed_hashes=hashes)))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(probe_error_type=type(error).__name__)),file=sys.stderr)
        raise SystemExit(1) from None
