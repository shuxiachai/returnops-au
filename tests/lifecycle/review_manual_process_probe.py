"""Independent actual child invocation; controlled fixture lives outside wheel."""
import json,os,socket,sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
if len(sys.argv)>2:sys.path.insert(0,sys.argv[2])
sys.path.insert(1,str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine,select
from returnops_api.private_review import compose_private_review
from returnops_api.private_manual import compose_private_manual
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_tables as old,lifecycle_tables as t
from returnops_domain.lifecycle_guards import LifecycleGuards
from controlled_escalate_reviewer import ControlledReviewer


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'options':'-c search_path='+config['schema']+' -c statement_timeout=10000'})
    counts=dict(RETURN=0,LABEL=0,notification_send=0,LLM=0,outbound=0,notification_claim=0)
    claims=dict(REVIEW=0,OUTCOME=0)
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send',
        'complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names:counts[names[frame.f_code.co_name]]+=1
    def outbound(*args,**kwargs):
        counts['outbound']+=1;raise AssertionError('No outbound business effect permitted')
    original=LifecycleGuards.claim
    def claim(self,uow,work_id,*args,**kwargs):
        purpose=uow.execute(select(t.work.c.purpose).where(t.work.c.work_id==work_id)).scalar_one()
        if purpose=='NOTIFICATION':counts['notification_claim']+=1
        elif purpose in claims:claims[purpose]+=1
        return original(self,uow,work_id,*args,**kwargs)
    LifecycleGuards.claim=claim;socket.create_connection=outbound;sys.setprofile(profile)
    modules={}
    for name in ['returnops_api.private_review','returnops_api.private_manual','returnops_domain.review_escalation',
        'returnops_domain.review_sources','returnops_domain.review_denial','returnops_domain.lifecycle_schema',
        'returnops_domain.manual_decision','returnops_domain.manual_target','returnops_domain.lifecycle_guards']:
        module=__import__(name,fromlist=['__file__']);path=Path(module.__file__).resolve()
        if len(sys.argv)>2:assert path.is_relative_to(Path(sys.argv[2]).resolve())
        modules[name]=dict(path=str(path),sha256=sha256(path.read_bytes()).hexdigest())
    # Same-key re-send rule (tests/lifecycle/same_key_retry.py), loaded from its exact file so that
    # the installed-package runs (python -I) keep the test directory off sys.path.
    import importlib.util
    _spec = importlib.util.spec_from_file_location('same_key_retry', Path(__file__).with_name('same_key_retry.py'))
    same_key_retry = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(same_key_retry)
    results={};attempts={};adapter=ControlledReviewer()
    if config['entry'] in {'review','both'}:
        result=compose_private_review(engine,adapter).accept(config['case'],config['version'],'original-review-key','child_review')
        results['review']=asdict(result)
    if config['entry'] in {'manual','both'}:
        authority=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
        manual=compose_private_manual(engine,authority,'Bearer '+config['token'])
        result,attempts['manual']=same_key_retry.accept_with_same_key_retries(
            lambda: manual.accept(config['case'],config['request'],'original-manual-key','child_manual'))
        results['manual']=asdict(result)
    sys.setprofile(None)
    assert not any(counts.values())
    print(json.dumps(dict(results=results,effects=counts,claims=claims,adapter_calls=len(adapter.calls),modules=modules,
        attempts=attempts),default=str))
    engine.dispose()
