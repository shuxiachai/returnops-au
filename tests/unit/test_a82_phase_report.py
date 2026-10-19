"""Offline proof parsing/storage tests, not execution of the PostgreSQL case."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


driver = load('tested_a82_driver', 'tools/a82_diagnostic/run.py')


def records():
    return [dict(event='collection', count=1, exact_node=True)] + [
        dict(event='report', exact_node=True, phase=phase, outcome='passed', xfail=False)
        for phase in ('setup', 'call', 'teardown')
    ] + [dict(event='session', exitstatus=0)]


def save(path, values):
    path.write_text(''.join(json.dumps(item) + '\n' for item in values), encoding='utf8')


def test_exact_phase_proof(tmp_path):
    path = tmp_path / 'phase-report.jsonl'; save(path, records())
    proof = driver.phase_proof(path, tmp_path, 0, 0)
    assert proof['single_node_passed'] and proof['collected'] == 1
    assert proof['phases'] == dict(setup='passed', call='passed', teardown='passed')
    assert proof['skipped'] == proof['xfail'] == 0 and driver.diagnostic_exit(0, proof) == 0


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate', 'wrong-order', 'wrong-node',
    'extra-node', 'skip', 'xfail', 'xpass', 'failed-setup', 'failed-teardown', 'session-failure',
    'extra-field', 'bool-count', 'integer-exact-node', 'bool-exit', 'non-object', 'secret'])
def test_nonpassing_or_ambiguous_reports_fail_closed(tmp_path, change):
    values = records()
    if change == 'missing': values.pop()
    elif change == 'extra': values.append(values[-1])
    elif change == 'duplicate': values[2] = deepcopy(values[1])
    elif change == 'wrong-order': values[1], values[2] = values[2], values[1]
    elif change == 'wrong-node': values[2]['exact_node'] = False
    elif change == 'extra-node': values[0]['count'] = 2
    elif change == 'skip': values[2]['outcome'] = 'skipped'
    elif change == 'xfail': values[2].update(outcome='skipped', xfail=True)
    elif change == 'xpass': values[2]['xfail'] = True
    elif change == 'failed-setup': values[1]['outcome'] = 'failed'
    elif change == 'failed-teardown': values[3]['outcome'] = 'failed'
    elif change == 'session-failure': values[-1]['exitstatus'] = 1
    elif change == 'extra-field': values[2]['unexpected'] = 'private'
    elif change == 'bool-count': values[0]['count'] = True
    elif change == 'integer-exact-node': values[0]['exact_node'] = 1
    elif change == 'bool-exit': values[-1]['exitstatus'] = False
    elif change == 'non-object': values[2] = []
    elif change == 'secret': values[2]['outcome'] = 'DO_NOT_EXPORT_THIS'
    path = tmp_path / 'phase-report.jsonl'; save(path, values)
    proof = driver.phase_proof(path, tmp_path, 0, 0)
    assert not proof['single_node_passed'] and driver.diagnostic_exit(0, proof) == 126
    assert 'DO_NOT_EXPORT_THIS' not in json.dumps(proof)


@pytest.mark.parametrize('code,poll', [(124, None), (124, 124), (125, None), (1, 1), (0, None), (True, 0)])
def test_phase_proof_requires_actual_process_success(tmp_path, code, poll):
    path = tmp_path / 'phase-report.jsonl'; save(path, records())
    proof = driver.phase_proof(path, tmp_path, code, poll)
    assert not proof['single_node_passed']
    assert driver.diagnostic_exit(code, proof) == (code if code != 0 else 126)


@pytest.mark.parametrize('raw', [b'{', b'x' * 4097, b'x' * (driver.LIMIT + 1), b'\xff\n'],
                         ids=['malformed', 'oversize-proof', 'oversize-sample', 'invalid-utf8'])
def test_malformed_partial_oversize_or_invalid_encoding_rejected(tmp_path, raw):
    path = tmp_path / 'phase-report.jsonl'; path.write_bytes(raw)
    proof = driver.phase_proof(path, tmp_path, 0, 0)
    assert not proof['single_node_passed']


def test_missing_and_outside_report_remain_nonpassing(tmp_path):
    path = tmp_path / 'missing.jsonl'
    assert not driver.phase_proof(path, tmp_path, 0, 0)['single_node_passed']
    path.write_text('private')
    other = tmp_path / 'other'; other.mkdir()
    assert not driver.phase_proof(path, other, 0, 0)['single_node_passed']
    assert not driver.phase_proof(other, tmp_path, 0, 0)['single_node_passed']


def test_plugin_storage_failure_does_not_raise_or_overwrite(tmp_path, monkeypatch):
    plugin = load('tested_a82_plugin', 'tools/a82_diagnostic/phase_report.py')
    path = tmp_path / 'phase-report.jsonl'; path.write_text('preserved')
    monkeypatch.setenv('A82_REPORT_PATH', str(path))
    session = SimpleNamespace(items=[SimpleNamespace(nodeid=plugin.NODE)])
    plugin.pytest_sessionstart(session); plugin.pytest_collection_finish(session)
    plugin.pytest_sessionfinish(session, 0)
    assert path.read_text() == 'preserved' and plugin._descriptor is None


def test_plugin_live_descriptor_write_failure_disables_proof(tmp_path, monkeypatch):
    plugin = load('tested_a82_plugin_write_failure', 'tools/a82_diagnostic/phase_report.py')
    path = tmp_path / 'phase-report.jsonl'; monkeypatch.setenv('A82_REPORT_PATH', str(path))
    session = SimpleNamespace(items=[SimpleNamespace(nodeid=plugin.NODE)])
    plugin.pytest_sessionstart(session)
    assert plugin._descriptor is not None
    def fail(*args): raise OSError('SECRET')
    monkeypatch.setattr(plugin.os, 'write', fail)
    plugin.pytest_collection_finish(session); plugin.pytest_sessionfinish(session, 0)
    assert plugin._descriptor is None and path.read_bytes() == b''


def test_plugin_record_limit_and_sanitization(tmp_path, monkeypatch):
    plugin = load('tested_a82_plugin_limit', 'tools/a82_diagnostic/phase_report.py')
    path = tmp_path / 'phase-report.jsonl'; monkeypatch.setenv('A82_REPORT_PATH', str(path))
    session = SimpleNamespace(items=[SimpleNamespace(nodeid='SECRET')])
    plugin.pytest_sessionstart(session); plugin.pytest_collection_finish(session)
    report = SimpleNamespace(nodeid='SECRET', when='SECRET', outcome='SECRET')
    for _ in range(10): plugin.pytest_runtest_logreport(report)
    plugin.pytest_sessionfinish(session, 0)
    raw = path.read_bytes()
    assert len(raw.splitlines()) == 5 and b'SECRET' not in raw
    assert not driver.phase_proof(path, tmp_path, 0, 0)['single_node_passed']
