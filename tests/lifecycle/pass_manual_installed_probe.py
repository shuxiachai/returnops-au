"""Installed isolated private PASS-manual call with module-byte evidence."""
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import socket
import sys

if len(sys.argv) > 2:
    sys.path.insert(0, sys.argv[2])

from sqlalchemy import create_engine, select
from returnops_api.private_manual import compose_private_manual
from returnops_api.security.authentication import AuthConfig
from returnops_domain import lifecycle_tables as tables
from returnops_domain.lifecycle_guards import LifecycleGuards


if __name__ == '__main__':
    installed = Path(sys.argv[2]).resolve()
    names = ['manual_decision', 'manual_target', 'pass_manual_sources', 'manual_denial',
        'lifecycle_guards', 'preview_sources', 'pass_review_sources', 'lifecycle_proposal']
    module_hashes = {}
    for name in names:
        module = importlib.import_module('returnops_domain.' + name)
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(installed)
        module_hashes[name + '.py'] = sha256(path.read_bytes()).hexdigest()
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
        connect_args={'options':'-c search_path=' + config['schema'] + ' -c statement_timeout=10000'})
    auth = AuthConfig(config['issuer'], config['audience'], bytes.fromhex(config['signing_key']), leeway_seconds=0)
    at = datetime.fromisoformat(config['at'])
    caller = compose_private_manual(engine, auth, 'Bearer ' + config['token'], clock=lambda:at)
    counts = dict(RETURN=0, LABEL=0, notification_send=0, LLM=0, outbound=0, notification_claim=0, execution_claim=0)
    functions = {'create_return':'RETURN', 'generate_label':'LABEL', 'send_notification':'notification_send',
        'complete':'LLM', 'generate_completion':'LLM', 'invoke_model':'LLM'}
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_name in functions:
            counts[functions[frame.f_code.co_name]] += 1
    def outbound(*args, **kwargs):
        counts['outbound'] += 1
        raise AssertionError('No outbound effect is permitted')
    outcome_claims = [0]
    original = LifecycleGuards.claim
    def claim(self, uow, work_id, *args, **kwargs):
        purpose = uow.execute(select(tables.work.c.purpose).where(tables.work.c.work_id == work_id)).scalar_one()
        if purpose == 'OUTCOME':
            outcome_claims[0] += 1
        if purpose == 'NOTIFICATION':
            counts['notification_claim'] += 1
        if purpose == 'EXECUTION':
            counts['execution_claim'] += 1
        return original(self, uow, work_id, *args, **kwargs)
    LifecycleGuards.claim = claim
    socket.create_connection = outbound
    sys.setprofile(profile)
    result = caller.accept(config['case'], config['request'], 'pass-manual-key', 'installed_pass_manual')
    sys.setprofile(None)
    assert not any(counts.values())
    print(json.dumps({**asdict(result), 'effects':counts, 'outcome_claims':outcome_claims[0], 'module_hashes':module_hashes}))
    engine.dispose()
