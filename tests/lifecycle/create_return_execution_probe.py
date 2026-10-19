"""Installed actual-process probe; invoked only by cloud PostgreSQL tests."""
from dataclasses import asdict
import importlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[2])
from sqlalchemy import create_engine, text
from returnops_api.private_return_execution import compose_private_return_execution
from returnops_api.security.authentication import AuthConfig
from returnops_domain import customer_uow
from returnops_domain.core_return_mock import CoreReturnMock, Ticket


if __name__ == '__main__':
    installed = Path(sys.argv[2]).resolve()
    modules = ['returnops_domain.return_execution', 'returnops_domain.return_execution_sources',
        'returnops_domain.return_execution_history', 'returnops_domain.return_execution_tables',
        'returnops_domain.return_execution_schema', 'returnops_domain.core_return_mock', 'returnops_api.private_return_execution']
    for name in modules:
        assert Path(importlib.import_module(name).__file__).resolve().is_relative_to(installed)
    assert not Path.cwd().resolve().is_relative_to(Path(__file__).resolve().parents[2])
    config = json.loads(Path(sys.argv[1]).read_bytes())
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True, echo=False,
        connect_args={'options': '-c search_path=' + config['schema'] + ' -c statement_timeout=10000'})
    auth = AuthConfig(config['issuer'], config['audience'], bytes.fromhex(config['signing_key']), leeway_seconds=0)
    counts = {'create': 0, 'query': 0}
    class Observed(CoreReturnMock):
        def perform(self, ticket, callback):
            counts['create' if ticket.kind == 'DISPATCH' else 'query'] += 1
            return super().perform(ticket, callback)
    caller = compose_private_return_execution(engine, auth, 'Bearer ' + config['token'], mock_factory=Observed)
    fence = customer_uow.acquire_fence; announced = []
    def observed_fence(connection, *, write):
        if config.get('signal') and not announced:
            pid = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            target = Path(config['signal']); pending = target.with_suffix('.writing')
            with pending.open('x', encoding='utf8') as stream:
                json.dump(dict(pid=pid, process=os.getpid()), stream)
            pending.replace(target); announced.append(pid)
        return fence(connection, write=write)
    customer_uow.acquire_fence = observed_fence
    mode = config.get('mode', 'execute'); arguments = config['arguments']
    if mode in {'crash_before_mock', 'effect_then_crash'}:
        ticket = caller._reserve(*(arguments[key] for key in ('case_id', 'expected_case_version', 'execution_work_id',
            'original_approval_key', 'candidate_command', 'correlation_id')))
        assert type(ticket) is Ticket
        if mode == 'effect_then_crash':
            reply = Observed(engine).perform(ticket, caller.authority)
            assert reply.status == 'FOUND' and reply.fact['status'] == 'SUCCEEDED'
        marker = dict(process=os.getpid(), mode=mode, preparation_id=ticket.preparation_id,
                      counts=counts, confirmed_T1_closed=True)
        with Path(config['marker']).open('x', encoding='utf8') as stream:
            json.dump(marker, stream); stream.flush(); os.fsync(stream.fileno())
        os._exit(0)
    if mode == 'query':
        result = caller.reconcile_create_return(**{key: arguments[key] for key in
            ('case_id', 'execution_work_id', 'original_approval_key', 'correlation_id')})
    else:
        result = caller.execute_prepared_create_return(**arguments)
    print(json.dumps(dict(result=asdict(result), counts=counts, process=os.getpid(), announced=announced)))
    engine.dispose()
