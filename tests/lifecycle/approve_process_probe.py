"""Future isolated-wheel probe for AP20; do not run under the local DB pause."""
import json
import os
import socket
from dataclasses import asdict
from pathlib import Path
import sys

if len(sys.argv) > 2:
    sys.path.insert(0, sys.argv[2])

from sqlalchemy import create_engine, select
from returnops_api.private_approve import compose_private_approve
from returnops_api.private_preview import compose_private_preview
from returnops_api.security.authentication import AuthConfig
from returnops_domain import lifecycle_tables as lifecycle
from returnops_domain.lifecycle_guards import LifecycleGuards


if __name__ == '__main__':
    import returnops_domain.approve_decision, returnops_domain.preview_service
    for module in (returnops_domain.approve_decision, returnops_domain.preview_service):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[2]).resolve())
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
        connect_args={'options':'-c search_path=' + config['schema'] + ' -c statement_timeout=10000'})
    authority = AuthConfig(config['issuer'], config['audience'], bytes.fromhex(config['signing_key']), leeway_seconds=0)
    caller = compose_private_approve(engine, authority, 'Bearer ' + config['token'])
    effects = dict(RETURN=0, LABEL=0, notification_send=0, LLM=0, outbound=0, execution_claim=0)
    claims = dict(APPROVAL=0, EXECUTION=0)
    names = {'create_return':'RETURN', 'generate_label':'LABEL', 'send_notification':'notification_send',
        'complete':'LLM', 'generate_completion':'LLM', 'invoke_model':'LLM'}
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_name in names:
            effects[names[frame.f_code.co_name]] += 1
    def outbound(*args, **kwargs):
        effects['outbound'] += 1
        raise AssertionError('No outbound effect is permitted')
    original_claim = LifecycleGuards.claim
    def claim(guard, uow, work_id, *args, **kwargs):
        purpose = uow.execute(select(lifecycle.work.c.purpose).where(lifecycle.work.c.work_id == work_id)).scalar_one()
        if purpose in claims: claims[purpose] += 1
        if purpose == 'EXECUTION': effects['execution_claim'] += 1
        return original_claim(guard, uow, work_id, *args, **kwargs)
    LifecycleGuards.claim = claim
    socket.create_connection = outbound
    sys.setprofile(profile)
    preview_result = compose_private_preview(engine).accept(config['case'], config['preview_version'],
        'installed-preview-key', config['correlation_id'])
    assert preview_result.status == 'ACCEPTED'
    action = preview_result.receipt['action_preview']
    request = {**config['request'], 'preview_id':action['preview_id'], 'scope_fingerprint':action['scope_fingerprint']}
    result = caller.accept(config['case'], request, config['key'], config['correlation_id'])
    sys.setprofile(None)
    assert not any(effects.values())
    print(json.dumps({**asdict(result), 'preview_result':asdict(preview_result), 'effects':effects, 'claims':claims}, default=str))
    engine.dispose()
