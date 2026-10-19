"""RE G5/G6 actual OS processes/backends, installed wheel and durable restart."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import monotonic, sleep
import pytest
from sqlalchemy import text
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain import customer_tables as old
from returnops_domain.return_execution_tables import ledger
from create_return_execution_helpers import ready, control, successes, rows, snapshot, evidence
from test_manual_postgresql import installed_manual

NAMES = ['return_execution.py', 'return_execution_sources.py', 'return_execution_history.py',
    'return_execution_tables.py', 'return_execution_schema.py', 'core_return_mock.py',
    'lifecycle_schema.py', 'lifecycle_state.py', 'execution_preparation.py']


def installed_proof(installed):
    root = Path(__file__).resolve().parents[2]
    pairs = [('packages/returnops_domain/' + name, 'returnops_domain/' + name) for name in NAMES]
    pairs.append(('apps/api/returnops_api/private_return_execution.py', 'returnops_api/private_return_execution.py'))
    result = {}
    for source, target in pairs:
        raw = (root / source).read_bytes()
        assert raw == (installed / target).read_bytes()
        result[source] = sha256(raw).hexdigest()
    assert not (installed / 'tests').exists() and not (installed / 'create_return_execution_helpers.py').exists()
    return result


def configuration(engine, identities, arguments):
    auth = identities.auth_config
    return dict(schema=engine._customer_test_schema, issuer=auth.issuer, audience=auth.audience,
        signing_key=auth.signing_key.hex(), token=identities.tokens['founder'], arguments=arguments)


def command(path, installed):
    return [sys.executable, '-I', '-B', str(Path(__file__).with_name('create_return_execution_probe.py')), str(path), str(installed)]


@pytest.mark.parametrize('changed', ['same', 'command', 'provider', 'original_key'])
def test_RE_G5_installed_processes_really_overlap_and_cannot_duplicate_effect(flow_engine, identities, enabled, request, tmp_path, installed_manual, changed):
    arguments, _ = ready(flow_engine, identities); hashes = installed_proof(installed_manual)
    processes = []; signals = []; overlap = None
    try:
        with CustomerUnitOfWork(flow_engine, write=True) as holder:
            holder_pid = holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            for index in range(2):
                values = deepcopy(arguments)
                if index == 1 and changed == 'command': values['candidate_command']['parameters']['line_items'][0]['quantity'] += 1
                if index == 1 and changed == 'provider': values['candidate_command']['provider_id'] = 'provider_replacement'
                if index == 1 and changed == 'original_key': values['original_approval_key'] = 'replacement-key'
                signal = tmp_path / f'return-signal-{index}.json'; signals.append(signal)
                path = tmp_path / f'return-race-{index}.json'
                path.write_text(json.dumps({**configuration(flow_engine, identities, values), 'signal': str(signal)}), encoding='utf8')
                processes.append(subprocess.Popen(command(path, installed_manual), cwd=tmp_path, env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            deadline = monotonic() + 3
            while not all(path.exists() and path.stat().st_size for path in signals):
                assert monotonic() < deadline and all(process.poll() is None for process in processes)
                sleep(.01)
            announced = [json.loads(path.read_bytes()) for path in signals]; pids = [row['pid'] for row in announced]
            assert len(set(pids)) == 2 and holder_pid not in pids
            waiting = []
            while len(waiting) != 2:
                with flow_engine.connect() as observer:
                    waiting = [dict(row) for row in observer.execute(text("SELECT pid,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid IN (:a,:b) AND wait_event_type='Lock' AND wait_event='advisory'"), dict(a=pids[0], b=pids[1])).mappings()]
                assert monotonic() < deadline
                if len(waiting) != 2: sleep(.01)
            assert all(holder_pid in row['blockers'] for row in waiting)
            overlap = dict(holder=holder_pid, announced=announced, waiting=waiting)
            holder.commit()
        result = []
        for process in processes:
            out, err = process.communicate(timeout=60)
            assert process.returncode == 0 and err == b''
            result.append(json.loads(out))
        assert len(successes(flow_engine)) == len(rows(flow_engine, ledger)) == 1
        assert control(flow_engine)['status'] == 'SUCCEEDED'
        assert sum(row['counts']['create'] for row in result) == 1
        assert sum(row['result']['status'] == 'COMMITTED' for row in result) == 1
        other, = [row for row in result if row['result']['status'] != 'COMMITTED']
        assert other['result']['status'] in ({'IN_PROGRESS', 'REPLAYED'} if changed == 'same' else {'UNKNOWN', 'DENIED'} if changed == 'original_key' else {'DENIED'})
        assert all(row['counts']['query'] == 0 for row in result)
        evidence(request.node.nodeid, changed=changed, overlap=overlap, results=result, installed_hashes=hashes, after=snapshot(flow_engine))
    finally:
        for process in processes:
            if process.poll() is None: process.kill(); process.communicate(timeout=10)


@pytest.mark.parametrize('initial', ['pending', 'crash_before_mock', 'effect_then_crash'])
def test_RE_G6_new_process_restart_uses_original_identity_without_blind_create(flow_engine, identities, enabled, request, tmp_path, installed_manual, initial):
    arguments, _ = ready(flow_engine, identities); hashes = installed_proof(installed_manual)
    config = configuration(flow_engine, identities, arguments); marker = None
    if initial != 'pending':
        path = tmp_path / 'return-first.json'; marker_path = tmp_path / 'return-crash-marker.json'
        path.write_text(json.dumps({**config, 'mode': initial, 'marker': str(marker_path)}), encoding='utf8')
        first = subprocess.run(command(path, installed_manual), cwd=tmp_path, env=os.environ.copy(), capture_output=True, timeout=60)
        assert first.returncode == 0 and first.stdout == first.stderr == b''
        marker = json.loads(marker_path.read_bytes())
        assert marker['confirmed_T1_closed'] is True and marker['counts']['create'] == (initial == 'effect_then_crash')
        assert control(flow_engine)['status'] == 'EXECUTING'
    before = snapshot(flow_engine)
    restart = tmp_path / 'return-restart.json'
    restart.write_text(json.dumps({**config, 'mode': 'execute' if initial == 'pending' else 'query'}), encoding='utf8')
    completed = subprocess.run(command(restart, installed_manual), cwd=tmp_path, env=os.environ.copy(), capture_output=True, timeout=60)
    assert completed.returncode == 0 and completed.stderr == b''
    result = json.loads(completed.stdout)
    assert marker is None or marker['process'] != result['process']
    assert result['counts']['create'] == (initial == 'pending')
    assert result['counts']['query'] == (initial != 'pending')
    if initial == 'crash_before_mock':
        assert result['result']['status'] == 'UNKNOWN' and successes(flow_engine) == []
        assert control(flow_engine)['status'] == 'EXECUTING'
        assert len([row for row in rows(flow_engine, old.history) if row['kind'] == 'OPERATION']) == 2
    else:
        assert result['result']['status'] == 'COMMITTED' and len(successes(flow_engine)) == 1
        assert control(flow_engine)['status'] == 'SUCCEEDED'
    evidence(request.node.nodeid, initial=initial, crash_marker=marker, restarted=result, installed_hashes=hashes,
        before=before, after=snapshot(flow_engine), original_identity_only=True)
