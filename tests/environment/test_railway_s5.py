"""S5 on Railway: tools/railway/start.py runs the R.02 driver inside the service (1 November 2026).

`start.py s5` runs the driver in demo mode against its own fresh database while the demo API
keeps serving; a PASSED receipt and a ready driver API make the run "ready", and only
`start.py s5-show` (new keys first) moves the public address to the driver's API; s5-end, the
end of the shown demo_cups_founder session or the driver ending move it back. A failure never reaches the public address, no status or log line carries a token,
and the image carries exactly what the driver imports. docs/45 S5; FR-009 to FR-012, NFR-001,
NFR-009.
"""
import ast
import importlib.util
import itertools
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('railway_start_s5', ROOT / 'tools' / 'railway' / 'start.py')
start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(start)

SECRET = 'sk-test-not-a-real-key-0123456789'
TOKEN = 'not-a-real-access-key-for-demo-cups'
SERVER = 'postgresql://user:pw@db:5432/railway'
APP = 'postgresql+psycopg://user:pw@db:5432/returnops_f02'


class FakeProcess:
    def __init__(self, args, **kwargs):
        self.args, self.kwargs, self.signals, self.code = args, kwargs, [], None

    def poll(self):
        return self.code

    def send_signal(self, number):
        self.signals.append(number)
        self.code = 0

    def wait(self, timeout=None):
        return self.code

    def terminate(self):
        self.code = -15

    def kill(self):
        self.code = -9


@pytest.fixture
def mode(tmp_path, monkeypatch):
    created, runs, drivers, switches, clock = [], [], [], [], [1000.0]
    monkeypatch.setattr(start, 'recreate_database', lambda server, name: created.append((server, name)))
    monkeypatch.setattr(start, 'free_port', lambda: 8100)

    def run(arguments, **kwargs):
        runs.append((arguments, kwargs))
        if 'provision' in arguments:
            folder = Path(arguments[arguments.index('--private-dir') + 1])
            folder.mkdir(mode=0o700)
            (folder / 'sessions.json').write_text(json.dumps({'tokens': {'demo_cups_founder': TOKEN},
                                                              'sessions': [{'issued_at': 1000, 'expires_at': 1899}]}))
        if 'renew-sessions' in arguments:  # new keys at show time
            folder = Path(arguments[arguments.index('--private-dir') + 1])
            (folder / 'sessions.json').write_text(json.dumps({'tokens': {'demo_cups_founder': TOKEN},
                                                              'sessions': [{'issued_at': int(clock[0]), 'expires_at': int(clock[0]) + 899}]}))
        return subprocess.CompletedProcess(arguments, 0)

    def popen(arguments, **kwargs):
        drivers.append(FakeProcess(arguments, **kwargs))
        return drivers[-1]

    environment = {'PATH': '/usr/bin', 'DATABASE_URL': APP, 'RETURNOPS_MODEL_API_KEY': SECRET,
                   'RETURNOPS_DEMO_PASSWORD': 'not-the-demo-password'}
    root = tmp_path / 's5'
    s5 = start.S5Mode(SERVER, APP, environment, root=root, popen=popen, run=run,
                      ready=lambda driver, port: True, clock=lambda: clock[0])
    start.CHILDREN.clear()
    s5.reset()
    yield SimpleNamespace(s5=s5, root=root, created=created, runs=runs, drivers=drivers, switches=switches,
                          clock=clock, step=lambda: s5.step(switches.append))
    start.CHILDREN.clear()


def ask_for(root, kind, ident):
    (root / f'request-{ident}').write_text(f'{kind} {ident}\n', encoding='ascii')


def status(root):
    return json.loads((root / 'status.json').read_text(encoding='utf-8'))


def receipt(root, **data):
    folder = root / 'run' / 'output'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'run-receipt.json').write_text(json.dumps(data), encoding='utf-8')


def test_a_passed_run_uses_its_own_database_and_is_shown_until_s5_end(mode, capsys):
    ask_for(mode.root, 's5', 'abc123')
    mode.step()
    assert status(mode.root)['state'] == 'running' and status(mode.root)['request'] == 'abc123'
    assert mode.created == [(SERVER, 'returnops_f02_s5')]
    (migrate, _), (provision, _) = mode.runs
    assert migrate[-3:] == ['alembic', 'upgrade', 'head']
    assert provision[provision.index('--store') + 1] == 'demo_cups_store'
    assert provision[provision.index('--founder') + 1] == 'demo_cups_founder'
    assert not {'--order-investigation', '--fixed-proposal', '--founder-manual'} & set(provision)
    driver = mode.drivers[0]
    for kwargs in [kwargs for _, kwargs in mode.runs] + [driver.kwargs]:
        # Only the database URL changes, to the S5 database; no model key and no demo password.
        assert kwargs['env']['DATABASE_URL'] == 'postgresql+psycopg://user:pw@db:5432/returnops_f02_s5'
        assert not any(name.startswith('RETURNOPS_') for name in kwargs['env'])
    run_dir = mode.root / 'run'
    assert driver.args[1:] == ['-B', str(start.DRIVER), '--output', str(run_dir / 'output'),
                               '--identities', str(run_dir / 'identities'), '--api-port', '8100', '--keep-api']
    assert driver in start.CHILDREN

    mode.step()  # no receipt yet: the public address keeps showing the demonstration
    assert mode.switches == []
    receipt(mode.root, result='PASSED', case_id='case_1')
    mode.step()
    # Ready, not shown: the run is made before the demonstration (1 November 2026).
    ready = status(mode.root)
    assert mode.switches == [] and (ready['state'], ready['result'], ready['case_id']) == ('ready', 'PASSED', 'case_1')
    mode.clock[0] = 5000  # a ready run waits however long the demonstration takes to reach S5
    mode.step()
    assert status(mode.root)['state'] == 'ready' and driver.signals == []

    ask_for(mode.root, 's5-show', 'show1')
    mode.step()
    renew = mode.runs[-1]
    assert renew[0][-3:] == ['renew-sessions', '--private-dir', str(run_dir / 'identities')]
    assert renew[1]['env']['DATABASE_URL'].endswith('/returnops_f02_s5')
    assert not any(name.startswith('RETURNOPS_') for name in renew[1]['env'])
    assert mode.switches == [8100]
    shown = status(mode.root)
    assert (shown['state'], shown['case_id'], shown['expires_at'], shown['answered']['show1']) == ('passed', 'case_1', 5899, 'shown')

    ask_for(mode.root, 's5-show', 'show2')  # shown again: the keys are copied once more
    mode.step()
    assert status(mode.root)['answered']['show2'] == 'shown' and mode.switches == [8100]

    ask_for(mode.root, 's5', 'def456')  # a second run waits for this one
    mode.step()
    assert status(mode.root)['answered']['def456'] == 'busy' and len(mode.drivers) == 1

    ask_for(mode.root, 's5-end', 'ghi789')
    mode.step()
    assert mode.switches == [8100, 8000] and driver.signals == [signal.SIGINT]
    assert driver not in start.CHILDREN
    ended = status(mode.root)
    assert ended['state'] == 'ended' and ended['answered']['ghi789'] == 'ended' and ended['case_id'] == 'case_1'
    assert not (run_dir / 'identities').exists() and (run_dir / 'output' / 'run-receipt.json').exists()

    ask_for(mode.root, 's5-end', 'jkl012')
    mode.step()
    assert status(mode.root)['answered']['jkl012'] == 'idle' and mode.switches == [8100, 8000]
    written = (mode.root / 'status.json').read_text(encoding='utf-8') + capsys.readouterr().out
    assert TOKEN not in written and SECRET not in written and 'pw@' not in written


@pytest.mark.parametrize('data', [{'result': 'REFUSED', 'stop': {'code': 'STORE_HAS_CASES', 'step': 0}},
                                  {'result': 'FAILED', 'case_id': 'case_2', 'stop': {'code': 'UNEXPECTED_ERROR'}}])
def test_a_failed_or_refused_run_never_reaches_the_public_address(mode, data):
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    receipt(mode.root, **data)
    mode.step()
    failed = status(mode.root)
    assert mode.switches == [] and mode.drivers[0].signals == [signal.SIGINT]
    assert (failed['state'], failed['result'], failed['code']) == ('failed', data['result'], data['stop']['code'])
    assert not (mode.root / 'run' / 'identities').exists()


def test_a_driver_api_that_does_not_answer_is_not_shown(mode):
    mode.s5.ready = lambda driver, port: False
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    receipt(mode.root, result='PASSED', case_id='case_1')
    mode.step()
    assert mode.switches == [] and status(mode.root)['code'] == 'S5_API_NOT_READY'


def test_the_driver_ending_or_its_key_expiring_shows_the_demonstration_again(mode):
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    mode.drivers[0].code = 1  # ended before any receipt
    mode.step()
    assert status(mode.root)['state'] == 'failed' and status(mode.root)['code'] == 'DRIVER_ENDED'
    assert mode.switches == []

    ask_for(mode.root, 's5', 'r2')
    mode.step()
    receipt(mode.root, result='PASSED', case_id='case_2')
    mode.step()
    ask_for(mode.root, 's5-show', 'show')
    mode.step()
    mode.clock[0] = 1899 + start.S5_GRACE_SECONDS  # the shown key's session has just ended
    mode.step()
    assert mode.switches == [8100] and status(mode.root)['state'] == 'passed'
    mode.clock[0] += 1
    mode.step()
    assert mode.switches == [8100, 8000] and status(mode.root)['state'] == 'ended'

    ask_for(mode.root, 's5', 'r3')
    mode.step()
    receipt(mode.root, result='PASSED', case_id='case_3')
    mode.step()
    mode.drivers[2].code = 0  # the driver ended while ready: nothing was shown
    mode.step()
    assert mode.switches == [8100, 8000] and status(mode.root)['state'] == 'ended'

    ask_for(mode.root, 's5', 'r4')
    mode.step()
    receipt(mode.root, result='PASSED', case_id='case_4')
    mode.step()
    ask_for(mode.root, 's5-show', 'show4')
    mode.step()
    mode.drivers[3].code = 0  # the driver ended while shown
    mode.step()
    assert mode.switches == [8100, 8000, 8100, 8000] and status(mode.root)['state'] == 'ended'


def test_only_a_ready_run_is_shown_and_a_failed_renewal_shows_nothing(mode):
    ask_for(mode.root, 's5-show', 'none')
    mode.step()
    assert status(mode.root)['answered']['none'] == 'idle' and mode.switches == []
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    ask_for(mode.root, 's5-show', 'early')  # still running
    mode.step()
    assert status(mode.root)['answered']['early'] == 'not-ready' and mode.switches == []
    receipt(mode.root, result='PASSED', case_id='case_1')
    mode.step()
    mode.s5.run = lambda arguments, **kwargs: subprocess.CompletedProcess(arguments, 1)
    ask_for(mode.root, 's5-show', 'broken')
    mode.step()
    failed = status(mode.root)
    assert (failed['state'], failed['code'], failed['answered']['broken']) == ('failed', 'S5_RENEW', 'failed')
    assert mode.switches == [] and mode.drivers[0].signals == [signal.SIGINT]


@pytest.mark.parametrize('failing, code', [('alembic', 'S5_MIGRATION'), ('provision', 'S5_PROVISION')])
def test_a_failed_preparation_starts_no_driver(mode, failing, code):
    mode.s5.run = lambda arguments, **kwargs: subprocess.CompletedProcess(arguments, 1 if failing in arguments else 0)
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    assert mode.drivers == [] and mode.switches == []
    assert status(mode.root)['state'] == 'failed' and status(mode.root)['code'] == code


def test_no_database_or_no_free_port_starts_no_driver(mode, monkeypatch):
    def refuse(server, name):
        raise psycopg.OperationalError('connection to postgresql://user:pw@db failed')
    monkeypatch.setattr(start, 'recreate_database', refuse)
    ask_for(mode.root, 's5', 'r1')
    mode.step()
    assert status(mode.root)['code'] == 'S5_DATABASE' and mode.runs == []
    monkeypatch.setattr(start, 'recreate_database', lambda server, name: None)
    monkeypatch.setattr(start, 'free_port', lambda: None)
    ask_for(mode.root, 's5', 'r2')
    mode.step()
    assert status(mode.root)['code'] == 'S5_NO_FREE_PORT' and mode.drivers == []


def test_an_unexpected_error_stops_s5_and_the_demonstration_keeps_running(mode, capsys):
    def broken(arguments, **kwargs):
        raise RuntimeError('postgresql://user:pw@db/returnops_f02_s5')
    mode.s5.run = broken
    ask_for(mode.root, 's5', 'r1')
    mode.step()  # does not raise
    assert status(mode.root)['state'] == 'failed' and status(mode.root)['code'] == 'S5_INTERNAL'
    assert 'pw@' not in capsys.readouterr().out


def test_a_malformed_request_is_dropped(mode):
    for name, text in (('request-abc', 's5'), ('request-abc', 'wipe abc'), ('request-x', 's5 ../x'),
                       ('request-' + 'a' * 33, 's5 ' + 'a' * 33), ('request-a', 's5 a b'), ('request-other', 's5 abc')):
        (mode.root / name).write_text(text, encoding='ascii')
        mode.step()
        assert not (mode.root / name).exists()
    assert mode.drivers == [] and status(mode.root)['state'] == 'idle'


def test_requests_made_while_the_loop_is_busy_are_all_answered_in_order(mode):
    # Each client writes its own file (S5 review, 1 November 2026): an end asked for while a
    # start waits is not lost.
    ask_for(mode.root, 's5-end', 'first')
    ask_for(mode.root, 's5', 'second')
    os.utime(mode.root / 'request-first', (1, 1))
    mode.step()
    assert status(mode.root)['answered']['first'] == 'idle' and mode.drivers == []
    mode.step()
    assert status(mode.root)['request'] == 'second' and len(mode.drivers) == 1
    assert list(mode.root.glob('request-*')) == []


def test_a_switch_that_fails_half_way_is_switched_back(mode):
    def switch(port):
        mode.switches.append(port)
        if port != 8000:
            raise OSError('caddy did not start')
    ask_for(mode.root, 's5', 'r1')
    mode.s5.step(switch)
    receipt(mode.root, result='PASSED', case_id='case_1')
    mode.s5.step(switch)
    ask_for(mode.root, 's5-show', 'show')
    mode.s5.step(switch)
    assert mode.switches == [8100, 8000] and status(mode.root)['code'] == 'S5_INTERNAL'


def client(root, kind, answers):
    """start.ask() against a stand-in container: each sleep() writes the next status."""
    calls = iter(answers)
    now = [0.0]

    def sleep(_):
        newest = max(root.glob('request-*'), key=lambda path: path.stat().st_mtime_ns)
        ident = newest.read_text(encoding='ascii').split()[1]
        start.write_small(root / 'status.json', json.dumps(next(calls)(ident)))

    def clock():
        now[0] += 1
        return now[0]

    return start.ask(kind, root=root, wait=50, clock=clock, sleep=sleep)


def test_the_client_follows_its_own_request_and_exits_with_the_result(tmp_path, capsys):
    root = tmp_path / 's5'
    assert start.ask('s5', root=root) == 1  # an older deployment without S5
    assert 'does not answer S5 requests' in capsys.readouterr().out
    root.mkdir()
    start.write_small(root / 'status.json', json.dumps({'state': 'idle'}))
    ready = [lambda i: {'request': i, 'state': 'starting'}, lambda i: {'request': i, 'state': 'running'},
             lambda i: {'request': i, 'state': 'ready', 'case_id': 'case_1'}]
    assert client(root, 's5', ready) == 0
    out = capsys.readouterr().out
    assert 'driver result PASSED, case case_1; ready' in out and 'running in demo mode' in out
    shown = [lambda i: {'request': 'first', 'state': 'passed', 'case_id': 'case_1', 'expires_at': 1899, 'answered': {i: 'shown'}}]
    assert client(root, 's5-show', shown) == 0 and 'shows the S5 case case_1' in capsys.readouterr().out
    for answer in ('not-ready', 'idle', 'failed'):
        refused_show = [lambda i, answer=answer: {'request': 'first', 'state': 'running', 'answered': {i: answer}}]
        assert client(root, 's5-show', refused_show) == 1
    busy_ready = [lambda i: {'request': 'first', 'state': 'ready', 'case_id': 'case_1', 'answered': {i: 'busy'}}]
    assert client(root, 's5', busy_ready) == 0 and 'already ready (case case_1)' in capsys.readouterr().out
    refused = [lambda i: {'request': i, 'state': 'failed', 'result': 'REFUSED', 'code': 'STORE_HAS_CASES'}]
    assert client(root, 's5', refused) == 1 and 'REFUSED (STORE_HAS_CASES)' in capsys.readouterr().out
    busy_passed = [lambda i: {'request': 'first', 'state': 'passed', 'case_id': 'case_1', 'answered': {i: 'busy'}}]
    assert client(root, 's5', busy_passed) == 0 and 'already shown (case case_1)' in capsys.readouterr().out
    # A run already under way (its own window closed) is followed to its result.
    busy_running = [lambda i: {'request': 'first', 'state': 'running', 'answered': {i: 'busy'}},
                    lambda i: {'request': 'first', 'state': 'running', 'answered': {i: 'busy'}},
                    lambda i: {'request': 'first', 'state': 'ready', 'case_id': 'case_9', 'answered': {i: 'busy'}}]
    assert client(root, 's5', busy_running) == 0
    out = capsys.readouterr().out
    assert 'under way; following it' in out and 'PASSED, case case_9' in out
    busy_failing = [lambda i: {'request': 'first', 'state': 'running', 'answered': {i: 'busy'}},
                    lambda i: {'request': 'first', 'state': 'failed', 'result': 'FAILED', 'code': 'X', 'answered': {i: 'busy'}}]
    assert client(root, 's5', busy_failing) == 1
    ended = [lambda i: {'request': 'first', 'state': 'ended', 'answered': {i: 'ended'}}]
    assert client(root, 's5-end', ended) == 0 and 'shows the demonstration again' in capsys.readouterr().out
    silent = itertools.repeat(lambda i: {'request': 'first', 'state': 'running'})
    assert client(root, 's5', silent) == 1 and 'no answer within 50 s' in capsys.readouterr().out
    # A long run still prints now and then, so an idle railway ssh session stays open.
    long_run = itertools.chain([lambda i: {'request': i, 'state': 'running'}] * 20,
                               [lambda i: {'request': i, 'state': 'ready', 'case_id': 'case_2'}])
    assert client(root, 's5', long_run) == 0 and 'still running' in capsys.readouterr().out
    requests = sorted(root.glob('request-*'))
    words = requests[0].read_text(encoding='ascii').split()
    assert words[0] == 's5' and words[1].isalnum() and requests[0].name == 'request-' + words[1]
    if os.name == 'posix':  # railway ssh runs as root: the container's user must read the file
        assert requests[0].stat().st_mode & 0o777 == 0o644
        assert (root / 'status.json').stat().st_mode & 0o777 == 0o600


def test_the_command_line_accepts_s5_s5_show_and_s5_end_only():
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    script = str(ROOT / 'tools' / 'railway' / 'start.py')
    for kind in ('s5', 's5-show', 's5-end'):  # no /app/private/s5 outside the image
        answer = subprocess.run([sys.executable, '-B', script, kind], capture_output=True, text=True, timeout=60, env=environment)
        assert answer.returncode == 1 and 'does not answer S5 requests' in answer.stdout
    unknown = subprocess.run([sys.executable, '-B', script, 's5', 'now'], capture_output=True, text=True, timeout=60, env=environment)
    assert unknown.returncode == 2 and 'usage' in unknown.stdout


def test_a_free_port_is_one_a_plain_bind_accepts():
    with socket.socket() as holder:
        holder.bind(('127.0.0.1', 0))
        holder.listen()
        assert start.free_port(holder.getsockname()[1], 1) is None
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    assert start.free_port(port, 1) == port


def test_caddy_is_started_and_restarted_towards_the_chosen_api_port():
    started = []

    def popen(arguments, **kwargs):
        started.append(FakeProcess(arguments, **kwargs))
        return started[-1]

    start.CHILDREN.clear()
    proxy = start.Proxy(popen=popen)
    proxy.start()
    assert started[0].kwargs['env']['RETURNOPS_API_PORT'] == '8000'
    proxy.switch(8000)  # already there
    assert len(started) == 1
    proxy.switch(8101)
    assert started[0].signals == [signal.SIGTERM] and started[1].kwargs['env']['RETURNOPS_API_PORT'] == '8101'
    assert start.CHILDREN == [started[1]]
    start.CHILDREN.clear()
    caddy = (ROOT / 'tools' / 'railway' / 'Caddyfile').read_text(encoding='utf-8')
    assert caddy.count('reverse_proxy 127.0.0.1:{$RETURNOPS_API_PORT:8000}') == 2
    assert 'reverse_proxy 127.0.0.1:8000' not in caddy and 'grace_period 5s' in caddy


def lock_blocks(path):
    blocks, name = {}, None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith((' ', '#')):
            name = line.split('==')[0].lower()
            blocks[name] = [line]
        elif name and line.startswith('    --hash='):
            blocks[name].append(line)
        else:
            name = None
    return blocks


# Top-level module of each package the driver imports -> its distribution in the locks.
DISTRIBUTIONS = {'httpx': 'httpx', 'jwt': 'pyjwt', 'pypdf': 'pypdf', 'sqlalchemy': 'sqlalchemy',
                 'uvicorn': 'uvicorn', 'psycopg': 'psycopg'}


def test_the_image_carries_the_driver_and_exactly_the_packages_it_adds():
    dockerfile = (ROOT / 'tools' / 'railway' / 'Dockerfile').read_text(encoding='utf-8')
    assert 'COPY tools/r02/*.py ./tools/r02/' in dockerfile
    assert '-r requirements.lock -r r02-requirements.lock' in dockerfile
    ignored = (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
    assert {'!tools/r02/', '!tools/r02/*.py', '!tools/railway/r02-requirements.lock'} <= set(ignored)
    runtime = lock_blocks(ROOT / 'requirements.lock')
    dev = lock_blocks(ROOT / 'requirements-dev.lock')
    extra = lock_blocks(ROOT / 'tools' / 'railway' / 'r02-requirements.lock')
    assert set(extra) == {'certifi', 'httpcore', 'httpx'} and not set(extra) & set(runtime)
    for name, block in extra.items():
        assert block == dev[name] and len(block) > 1  # copied unchanged, hashes included
    local = {path.stem for path in (ROOT / 'tools' / 'r02').glob('*.py')}
    found = set()
    for path in (ROOT / 'tools' / 'r02').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            found |= {name.split('.')[0] for name in names}
    found = {name for name in found if name not in sys.stdlib_module_names and name not in local
             and not name.startswith('returnops_') and name != '__future__'}
    assert found <= set(DISTRIBUTIONS), sorted(found - set(DISTRIBUTIONS))
    assert {DISTRIBUTIONS[name] for name in found} <= set(runtime) | set(extra)
