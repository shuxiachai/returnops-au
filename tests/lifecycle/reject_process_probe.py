"""Independent process, real F.03 authority and fenced reject acceptance."""
import json
import os
from pathlib import Path
import sys
if len(sys.argv) > 2:
    sys.path.insert(0, sys.argv[2])
else:
    checkout=Path(__file__).resolve().parents[2]
    sys.path[:0]=[str(checkout/'packages'),str(checkout/'apps/api')]
from sqlalchemy import create_engine
from returnops_api.private_reject import compose_private_reject
from returnops_api.security.authentication import AuthConfig
from returnops_domain.audit import identifier
from dataclasses import asdict

if __name__ == '__main__':
    if len(sys.argv) > 2:
        import returnops_domain.reject_decision as installed_reject
        assert Path(installed_reject.__file__).resolve().is_relative_to(Path(sys.argv[2]).resolve())
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if 'barrier' in config:
        import time
        barrier=Path(config['barrier'])
        (barrier/('ready-'+config['worker'])).write_text('ready',encoding='utf-8')
        deadline=time.monotonic()+30
        while not (barrier/'release').exists():
            if time.monotonic()>=deadline:raise AssertionError('Parent did not release both ready callers')
            time.sleep(0.01)
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
        connect_args={'options':'-c search_path=' + config['schema'] + ' -c statement_timeout=10000'})
    authority = AuthConfig(config['issuer'], config['audience'], bytes.fromhex(config['signing_key']), leeway_seconds=0)
    service = compose_private_reject(engine, authority, 'Bearer ' + config['token'])
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
    reject_claims = [0]
    original_claim = LifecycleGuards.claim
    def claim(self, uow, work_id, *args, **kwargs):
        purpose = uow.execute(select(tables.work.c.purpose).where(tables.work.c.work_id == work_id)).scalar_one()
        if purpose == 'NOTIFICATION': counts['notification_claim'] += 1
        if purpose == 'OUTCOME': reject_claims[0] += 1
        return original_claim(self, uow, work_id, *args, **kwargs)
    LifecycleGuards.claim = claim
    socket.create_connection = outbound
    # Attempts mirror the HTTP client contract (docs/40): a DENIED result whose safe code is
    # INTERNAL_ERROR is answered as 503, retryable, "keep the original request key", so the same
    # key is re-sent, at most twice. This happens when the fence's lock_timeout expires while the
    # other caller still holds it; the acceptance itself wrote nothing, but record_denial may then
    # find the fence free and record a FOUNDER_REJECT_DENIED audit with reason INTERNAL_ERROR
    # (audit RECORDED), as on main CI run 39900838149. Every attempt is recorded with its duration.
    import time as _time
    attempts = []
    max_attempts = int(config.get('max_attempts', 3))
    for attempt in range(1, max_attempts + 1):
        started = _time.monotonic()
        sys.setprofile(profile)
        result = service.accept(config['case'], config['request'], config.get('key', 'original-reject-key'), identifier('corr'))
        sys.setprofile(None)
        attempts.append({'attempt': attempt, 'status': result.status, 'safe_code': result.safe_code,
                         'audit': result.audit, 'duration_ms': round((_time.monotonic() - started) * 1000)})
        retryable_transient = (result.status == 'DENIED' and result.safe_code == 'INTERNAL_ERROR'
                               and result.receipt is None)
        if not retryable_transient:
            break
    assert not any(counts.values())
    print(json.dumps({**asdict(result), 'effects':counts, 'reject_claims':reject_claims[0], 'attempts':attempts}))
    engine.dispose()
