"""Cloud-only installed notification process; no production startup entry."""
from dataclasses import asdict
from functools import partial
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys

sys.path.insert(0,sys.argv[1])
from sqlalchemy import create_engine,event,text
from returnops_api.private_notification import compose_private_notification
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow
from returnops_domain.notification_mock import CoreMockNotification
from returnops_domain.core_return_mock import CoreReturnMock
from returnops_domain.core_label_mock import CoreLabelMock
from returnops_domain.core_label_artifact_mock import CoreLabelArtifactMock
from returnops_domain import label_pdf,label_artifact_sources


def main():
    installed=Path(sys.argv[1]).resolve()
    config=json.loads(sys.stdin.buffer.read())
    assert re.fullmatch(r'customer_test_[a-f0-9]{32}',config['schema'])
    assert config['mode'] in {'send','reconcile'}
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    path=Path(__file__).with_name('label_artifact_binding.py')
    spec=importlib.util.spec_from_file_location('notification_probe_binding',path)
    binding_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding_module)
    binding=config['database_binding']
    url=binding_module.child_binding(os.environ['DATABASE_URL'],binding,config['schema'],os.environ)
    engine=create_engine(url,hide_parameters=True,echo=False,connect_args={
        'connect_timeout':3,'options':'-c search_path='+config['schema']+' -c statement_timeout=30000'})
    def bound(connection,record):
        try:
            with connection.cursor() as cursor:
                identity=binding_module.observe(cursor.execute,config['schema'])
            binding_module.live_identity(binding,identity)
        finally:
            connection.rollback()
    event.listen(engine,'connect',bound)
    with engine.connect():pass
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    factory=partial(customer_uow.CustomerUnitOfWork,lock_timeout_ms=10000)
    caller=compose_private_notification(engine,auth,'Bearer '+config['token'],uow_factory=factory,
        mock=CoreMockNotification(engine,uow_factory=factory))
    functions=dict(send=CoreMockNotification.deliver,query=CoreMockNotification.query,
        insert=CoreMockNotification._insert,return_provider=CoreReturnMock.perform,
        label_provider=CoreLabelMock.perform,artifact_retrieve=CoreLabelArtifactMock.retrieve_original_label,
        render=label_pdf.render_label_pdf,text_line=label_pdf._text_line,assembly=label_pdf._assemble_pdf,
        expected_pdf=label_artifact_sources.expected_pdf)
    codes={fn.__code__:name for name,fn in functions.items()}
    counts={name:0 for name in functions}
    forbidden={'return_provider','label_provider','artifact_retrieve','render','text_line','assembly','expected_pdf'}
    if config['mode']=='reconcile':forbidden|={'send','insert'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code in codes:
            name=codes[frame.f_code];counts[name]+=1
            if name in forbidden:raise AssertionError('Forbidden notification process effect: '+name)
    def outbound(*args,**kwargs):
        raise AssertionError('No outbound socket API')
    socket.create_connection=outbound
    acquire=customer_uow.acquire_fence;announced=[]
    def observed(connection,*,write):
        if config.get('signal') and not announced:
            target=Path(config['signal']).resolve()
            assert target.parent==Path.cwd().resolve()
            pid=connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            pending=target.with_suffix('.writing')
            with pending.open('x',encoding='utf-8') as stream:
                json.dump(dict(pid=pid,process=os.getpid()),stream)
            pending.replace(target);announced.append(pid)
        return acquire(connection,write=write)
    customer_uow.acquire_fence=observed
    sys.setprofile(profile)
    try:
        result=(caller.send(config['work_id']) if config['mode']=='send'
                else caller.reconcile(config['work_id']))
    finally:
        sys.setprofile(None)
    hashes={}
    for name,module in sorted(sys.modules.items()):
        if (name=='returnops_api' or name.startswith('returnops_api.')
                or name=='returnops_domain' or name.startswith('returnops_domain.')):
            file=Path(module.__file__).resolve()
            assert file.is_relative_to(installed)
            hashes[name]=sha256(file.read_bytes()).hexdigest()
    engine.dispose()
    print(json.dumps(dict(result=asdict(result),counts=counts,process=os.getpid(),
        announced=announced,installed_hashes=hashes,binding_helper_sha256=sha256(path.read_bytes()).hexdigest())))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(probe_error_type=type(error).__name__)),file=sys.stderr)
        raise SystemExit(1) from None
