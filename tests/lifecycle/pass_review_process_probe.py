"""Explicit external synthetic adapter caller; independent process or wheel."""
import json,os,socket,sys,time
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
if len(sys.argv)>2:sys.path.insert(0,sys.argv[2])
sys.path.insert(1,str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine,select
from returnops_api.private_pass_review import compose_private_pass_review
from returnops_domain import lifecycle_tables as t
from returnops_domain.lifecycle_guards import LifecycleGuards
from pass_review_helpers import ControlledPassReviewer


def publish_ready(path, payload):
    """Expose the ready marker only after its complete JSON is closed."""
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x', encoding='utf8') as stream:
        json.dump(payload, stream)
    os.replace(temporary, path)


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'options':'-c search_path='+config['schema']+' -c statement_timeout=10000',
                      'application_name':config.get('application_name','synthetic-pass-installed')})
    counts=dict(RETURN=0,LABEL=0,notification_send=0,LLM=0,outbound=0,notification_claim=0)
    claims=dict(REVIEW=0)
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send',
           'complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names:counts[names[frame.f_code.co_name]]+=1
    def outbound(*args,**kwargs):counts['outbound']+=1;raise AssertionError('Outbound business effects forbidden')
    original=LifecycleGuards.claim
    def claim(self,uow,work_id,*args,**kwargs):
        purpose=uow.execute(select(t.work.c.purpose).where(t.work.c.work_id==work_id)).scalar_one()
        if purpose=='NOTIFICATION':counts['notification_claim']+=1
        elif purpose=='REVIEW':claims['REVIEW']+=1
        return original(self,uow,work_id,*args,**kwargs)
    LifecycleGuards.claim=claim;socket.create_connection=outbound;sys.setprofile(profile)
    modules={}
    for name in ['returnops_api.private_pass_review','returnops_domain.pass_review','returnops_domain.pass_review_sources',
                 'returnops_domain.pass_review_denial','returnops_domain.pass_scenario','returnops_domain.lifecycle_events',
                 'returnops_domain.lifecycle_guards','returnops_domain.lifecycle_projection']:
        module=__import__(name,fromlist=['__file__']);path=Path(module.__file__).resolve()
        if len(sys.argv)>2:assert path.is_relative_to(Path(sys.argv[2]).resolve())
        modules[name]=dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest())
    if config.get('component')=='ESC':
        from returnops_api.private_review import compose_private_review
        from controlled_escalate_reviewer import ControlledReviewer
        adapter=ControlledReviewer();caller=compose_private_review(engine,adapter)
    else:
        adapter=ControlledPassReviewer(config.get('outcome','PASS'));caller=compose_private_pass_review(engine,adapter)
    if 'ready_path' in config:
        publish_ready(Path(config['ready_path']),dict(pid=os.getpid(),case=config['case'],version=config['version'],
            key=config.get('key','original-review-key'),application_name=config['application_name']))
        deadline=time.monotonic()+30
        while not Path(config['release_path']).exists():
            assert time.monotonic()<deadline,'Parent did not release prepared child'
            time.sleep(0.01)
    result=caller.accept(config['case'],config['version'],config.get('key','original-review-key'),'child_pass')
    sys.setprofile(None)
    assert not any(counts.values())
    print(json.dumps(dict(result=asdict(result),effects=counts,claims=claims,adapter_calls=len(adapter.calls),modules=modules),default=str))
    engine.dispose()
