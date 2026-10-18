"""Cloud-only isolated wheel child; never run during the local DB pause."""
import json
import os
from pathlib import Path
import socket
import sys
from dataclasses import asdict

sys.path.insert(0,sys.argv[2])
from sqlalchemy import create_engine
from returnops_api.private_approval_admission import compose_private_approval_admission
from returnops_api.security.authentication import AuthConfig
from returnops_domain.lifecycle_guards import LifecycleGuards
import returnops_domain.approval_admission as service_module
import returnops_domain.approval_admission_sources as proof_module
import returnops_api.private_approval_admission as composition_module


if __name__=='__main__':
    installed=Path(sys.argv[2]).resolve()
    for module in (service_module,proof_module,composition_module):
        assert Path(module.__file__).resolve().is_relative_to(installed)
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,echo=False,
        connect_args={'options':'-c search_path='+config['schema']+' -c statement_timeout=10000'})
    auth=AuthConfig(config['issuer'],config['audience'],bytes.fromhex(config['signing_key']),leeway_seconds=0)
    caller=compose_private_approval_admission(engine,auth,'Bearer '+config['token'])
    effects=dict(RETURN=0,LABEL=0,notification_send=0,LLM=0,outbound=0)
    claims=[]
    def no_claim(*args,**kwargs): claims.append('claim'); raise AssertionError('No claim permitted')
    def no_outbound(*args,**kwargs): effects['outbound']+=1; raise AssertionError('No outbound call permitted')
    names={'create_return':'RETURN','generate_label':'LABEL','send_notification':'notification_send',
           'complete':'LLM','generate_completion':'LLM','invoke_model':'LLM'}
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_name in names: effects[names[frame.f_code.co_name]]+=1
    LifecycleGuards.claim=no_claim; socket.create_connection=no_outbound
    arguments=config['arguments']
    sys.setprofile(profile)
    checked=caller.check(**arguments)
    denied=caller.check(**{**arguments,'expected_case_version':arguments['expected_case_version']+1})
    unknown=caller.check(**{**arguments,'original_approval_key':'unknown-original-approval-key'})
    sys.setprofile(None)
    assert not any(effects.values()) and not claims
    print(json.dumps(dict(results=[asdict(result) for result in (checked,denied,unknown)],effects=effects,claims=len(claims))))
    engine.dispose()
