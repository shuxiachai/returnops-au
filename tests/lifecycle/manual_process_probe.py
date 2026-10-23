"""Independent process, real F.03 authority and fenced manual acceptance."""
import json
import os
from pathlib import Path
import sys
if len(sys.argv) > 2:
    sys.path.insert(0, sys.argv[2])
from sqlalchemy import create_engine
from returnops_api.private_manual import compose_private_manual
from returnops_api.security.authentication import AuthConfig
from returnops_domain.audit import identifier
from dataclasses import asdict

if __name__ == '__main__':
    if len(sys.argv) > 2:
        import returnops_domain.manual_decision as installed_manual
        assert Path(installed_manual.__file__).resolve().is_relative_to(Path(sys.argv[2]).resolve())
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
        connect_args={'options':'-c search_path=' + config['schema'] + ' -c statement_timeout=10000'})
    authority = AuthConfig(config['issuer'], config['audience'], bytes.fromhex(config['signing_key']), leeway_seconds=0)
    service = compose_private_manual(engine, authority, 'Bearer ' + config['token'])
    from sqlalchemy import select
    from returnops_domain import lifecycle_tables as tables
    from returnops_domain.lifecycle_guards import LifecycleGuards
    import socket
    counts = dict(RETURN=0, LABEL=0, notification_send=0, LLM=0, outbound=0, notification_claim=0)
    names = {'create_return':'RETURN', 'generate_label':'LABEL', 'send_notification':'notification_send',
             'complete':'LLM', 'generate_completion':'LLM', 'invoke_model':'LLM'}
    def profile(frame, event, arg):
        if event == 'call' and frame.f_code.co_name in names:
            counts[names[frame.f_code.co_name]] += 1
    def outbound(*args, **kwargs):
        counts['outbound'] += 1
        raise AssertionError('No outbound effect is permitted')
    original_claim = LifecycleGuards.claim
    def claim(self, uow, work_id, *args, **kwargs):
        purpose = uow.execute(select(tables.work.c.purpose).where(tables.work.c.work_id == work_id)).scalar_one()
        if purpose == 'NOTIFICATION': counts['notification_claim'] += 1
        return original_claim(self, uow, work_id, *args, **kwargs)
    LifecycleGuards.claim = claim
    socket.create_connection = outbound
    # Same-key re-send rule (tests/lifecycle/same_key_retry.py), loaded from its exact file so that
    # the installed-package runs (python -I) keep the test directory off sys.path.
    import importlib.util
    _spec = importlib.util.spec_from_file_location('same_key_retry', Path(__file__).with_name('same_key_retry.py'))
    same_key_retry = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(same_key_retry)
    sys.setprofile(profile)
    try:
        result, attempts = same_key_retry.accept_with_same_key_retries(
            lambda: service.accept(config['case'], config['request'], 'original-manual-key', identifier('corr')))
    finally:
        sys.setprofile(None)
    assert not any(counts.values())
    print(json.dumps({**asdict(result), 'effects':counts, 'attempts':attempts}))
    engine.dispose()
