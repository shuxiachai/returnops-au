"""R.02 driver demo mode offline checks; no database is used.

DATABASE_URL stays unset, except that one helper sets a fake returnops_f02 URL
inside the test process so the real returnops_api.demo.provision writer can
produce auth.json and sessions.json; its registry and engine are replaced, so no
connection is opened. Covers the identities loader against those real files
(shape validation, token verification, file modes not required), the demo-mode
clean-environment rules, the registry comparison, argument parsing, the fixed
API port, hold() with a fake process, the keep-API order (receipt, hold, stop)
and receipt redaction in demo mode. Demo mode supports the live demo; it is not
CI evidence. docs/08 R.02; FR-009, FR-011; NFR-002/NFR-003/NFR-007.
"""
import base64
from contextlib import contextmanager
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace

import jwt
import pytest

from returnops_api import demo
from returnops_api.customer_config import load_private_auth_config

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools' / 'r02'
sys.path.insert(0, str(TOOLS))
import api_child  # noqa: E402
import demo_identities  # noqa: E402
import driver  # noqa: E402

FAKE_URL = 'postgresql+psycopg://r02demo:r02-demo-distinct-pw@localhost/returnops_f02_r02_demo'
PEOPLE = dict(customer_one='demo_cust_one', customer_two='demo_cust_two', founder='demo_founder')
STORE = 'demo_cups_store'


def _provision(tmp_path, monkeypatch, name='identities'):
    """The real demo.provision writer; registry and engine are fakes (no database)."""
    calls = []

    class Registry:
        def __init__(self, engine):
            pass

        def provision(self, principals, sessions):
            calls.append((principals, sessions))

    monkeypatch.setenv('DATABASE_URL', FAKE_URL)
    monkeypatch.setattr(demo, 'build_engine', lambda settings: SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr(demo, 'TrustedRegistry', Registry)
    directory = tmp_path / name
    demo.provision(directory, store=STORE, **PEOPLE)
    monkeypatch.delenv('DATABASE_URL')
    return directory, calls


def _documents(directory):
    return (json.loads((directory / 'auth.json').read_text(encoding='utf-8')),
            json.loads((directory / 'sessions.json').read_text(encoding='utf-8')))


def _rewrite(directory, auth, document):
    (directory / 'auth.json').write_text(json.dumps(auth), encoding='utf-8')
    (directory / 'sessions.json').write_text(json.dumps(document), encoding='utf-8')


def _code(directory):
    with pytest.raises(demo_identities.IdentitiesError) as raised:
        demo_identities.load(directory)
    assert str(raised.value) == raised.value.code  # a safe code, never a value or a path
    return raised.value.code


def _clean(**changes):
    value = dict(case_rows_before=0, driver_principals_before=0, allow_existing_data=False,
                 store_case_rows_before=0, store_investigation_services_before=0,
                 store_lifecycle_authorities_before=0, pending_work_before=0)
    value.update(changes)
    return value


def test_loader_reads_exactly_what_demo_provision_writes(tmp_path, monkeypatch):
    directory, calls = _provision(tmp_path, monkeypatch)
    ids = demo_identities.load(directory)
    (principals, sessions), = calls
    auth, document = _documents(directory)
    assert ids.store_id == STORE and ids.people == PEOPLE
    assert list(ids.principals.values()) == principals == document['principals']
    assert [ids.sessions[name] for name in demo_identities.NAMES] == sessions == document['sessions']
    assert (ids.issuer, ids.audience) == (auth['issuer'], auth['audience'])
    assert ids.signing_key == base64.b64decode(auth['signing_key_base64'])
    assert ids.tokens == {name: document['tokens'][principal] for name, principal in PEOPLE.items()}
    assert ids.expires_at == min(row['expires_at'] for row in sessions) > time.time()
    assert ids.auth_file == (directory / 'auth.json').resolve() and ids.auth_file.is_absolute()
    secrets = ids.secret_values()
    assert set(ids.tokens.values()) <= set(secrets) and auth['signing_key_base64'] in secrets
    assert ids.signing_key.hex() in secrets
    shown = repr(ids)
    assert all(value not in shown for value in secrets)
    # The API child reads the same auth file with the production loader.
    monkeypatch.setenv('RETURNOPS_AUTH_FILE', str(ids.auth_file))
    config = load_private_auth_config()
    assert (config.issuer, config.audience, config.signing_key) == (ids.issuer, ids.audience, ids.signing_key)


def test_loader_does_not_require_private_file_modes(tmp_path, monkeypatch):
    directory, _ = _provision(tmp_path, monkeypatch)
    for name in ('auth.json', 'sessions.json'):
        os.chmod(directory / name, 0o644)
    os.chmod(directory, 0o755)
    assert demo_identities.load(directory).people == PEOPLE
    source = inspect.getsource(demo_identities)
    assert 'st_mode' not in source and 'chmod' not in source and '.stat(' not in source


def _other_key():
    return base64.b64encode(b'r02-demo-other-signing-key-material-0123456789ab').decode('ascii')


MUTATIONS = {
    'auth_extra_member': (lambda a, d: a.update(extra='x'), 'IDENTITIES_MALFORMED'),
    'auth_key_not_base64': (lambda a, d: a.update(signing_key_base64='not base64!'), 'IDENTITIES_MALFORMED'),
    'auth_key_too_short': (lambda a, d: a.update(signing_key_base64=base64.b64encode(b'k' * 16).decode()),
                           'IDENTITIES_KEY_INVALID'),
    'document_extra_member': (lambda a, d: d.update(extra=[]), 'IDENTITIES_MALFORMED'),
    'two_principals': (lambda a, d: d['principals'].pop(1), 'IDENTITIES_MALFORMED'),
    'principal_extra_member': (lambda a, d: d['principals'][0].update(extra=1), 'IDENTITIES_MALFORMED'),
    'invalid_principal_id': (lambda a, d: d['principals'][0].update(principal_id='has space'), 'IDENTITIES_MALFORMED'),
    'two_founders': (lambda a, d: d['principals'][0].update(role='FOUNDER'), 'IDENTITIES_ROLES_INVALID'),
    'two_stores': (lambda a, d: d['principals'][1].update(store_id='other_store'), 'IDENTITIES_ROLES_INVALID'),
    'disabled_principal': (lambda a, d: d['principals'][2].update(enabled=False), 'IDENTITIES_ROLES_INVALID'),
    'revoked_session': (lambda a, d: d['sessions'][0].update(revoked=True), 'IDENTITIES_SESSIONS_INVALID'),
    'session_over_900_seconds': (lambda a, d: d['sessions'][0].update(expires_at=d['sessions'][0]['issued_at'] + 901),
                                 'IDENTITIES_SESSIONS_INVALID'),
    'session_of_unknown_principal': (lambda a, d: d['sessions'][2].update(principal_id='someone_else'),
                                     'IDENTITIES_SESSIONS_INVALID'),
    'missing_token': (lambda a, d: d['tokens'].pop('demo_founder'), 'IDENTITIES_MALFORMED'),
    'swapped_tokens': (lambda a, d: d['tokens'].update(demo_cust_one=d['tokens']['demo_cust_two']),
                       'IDENTITIES_TOKEN_INVALID'),
    'tokens_signed_by_another_key': (lambda a, d: a.update(signing_key_base64=_other_key()), 'IDENTITIES_TOKEN_INVALID'),
    'other_issuer': (lambda a, d: a.update(issuer='returnops-someone-else'), 'IDENTITIES_TOKEN_INVALID'),
    'other_audience': (lambda a, d: a.update(audience='returnops-someone-else'), 'IDENTITIES_TOKEN_INVALID'),
}


@pytest.mark.parametrize('name', sorted(MUTATIONS))
def test_loader_refuses_shapes_demo_provision_never_writes(tmp_path, monkeypatch, name):
    directory, _ = _provision(tmp_path, monkeypatch)
    auth, document = _documents(directory)
    mutate, code = MUTATIONS[name]
    mutate(auth, document)
    _rewrite(directory, auth, document)
    assert _code(directory) == code


def test_loader_refuses_expired_sessions_and_unreadable_files(tmp_path, monkeypatch):
    directory, _ = _provision(tmp_path, monkeypatch)
    auth, document = _documents(directory)
    key, issued = base64.b64decode(auth['signing_key_base64']), int(time.time()) - 1000
    for row in document['sessions']:
        row.update(issued_at=issued, not_before=issued, expires_at=issued + 899)
        document['tokens'][row['principal_id']] = jwt.encode(dict(
            iss=auth['issuer'], aud=auth['audience'], sub=row['principal_id'], jti=row['session_id'], iat=issued,
            nbf=issued, exp=issued + 899), key, algorithm='HS256')
    _rewrite(directory, auth, document)
    assert _code(directory) == 'IDENTITIES_SESSION_EXPIRED'
    assert _code(tmp_path / 'missing') == 'IDENTITIES_DIRECTORY_MISSING'
    other, _ = _provision(tmp_path, monkeypatch, 'other')
    raw = (other / 'sessions.json').read_bytes()
    (other / 'sessions.json').unlink()
    assert _code(other) == 'IDENTITIES_FILE_MISSING'
    (other / 'sessions.json').write_bytes(b'{"principals": [], "principals": [], "sessions": [], "tokens": {}}')
    assert _code(other) == 'IDENTITIES_MALFORMED'
    (other / 'sessions.json').write_bytes(b'\xff\xfe not json')
    assert _code(other) == 'IDENTITIES_MALFORMED'
    (other / 'sessions.json').write_bytes(raw)
    (other / 'auth.json').write_bytes(b' ' * 9000)
    assert _code(other) == 'IDENTITIES_FILE_TOO_LARGE'


def test_clean_environment_rules_default_and_demo():
    default = dict(case_rows_before=0, driver_principals_before=0, allow_existing_data=False)
    assert driver.clean_refusal(default) is None
    assert driver.clean_refusal({**default, 'case_rows_before': 3}) == 'EXISTING_CASE_ROWS'
    assert driver.clean_refusal({**default, 'case_rows_before': 3, 'allow_existing_data': True}) is None
    assert driver.clean_refusal({**default, 'driver_principals_before': 1, 'allow_existing_data': True}) == \
        'DRIVER_IDENTITIES_EXIST'
    # Demo mode: other stores' cases need the explicit flag; the store checks are never relaxed.
    assert driver.clean_refusal(_clean(case_rows_before=5), demo=True) == 'EXISTING_CASE_ROWS'
    assert driver.clean_refusal(_clean(case_rows_before=5, allow_existing_data=True), demo=True) is None
    assert driver.clean_refusal(_clean(driver_principals_before=1, allow_existing_data=True), demo=True) == \
        'DRIVER_IDENTITIES_EXIST'
    for key, code in driver.DEMO_STORE_CHECKS:
        assert driver.clean_refusal(_clean(allow_existing_data=True, **{key: 1}), demo=True) == code
        assert driver.clean_refusal(_clean(allow_existing_data=True, **{key: 1})) is None
    assert [code for _, code in driver.DEMO_STORE_CHECKS] == [
        'STORE_HAS_CASES', 'STORE_INVESTIGATION_CONFIGURED', 'STORE_AUTHORITIES_EXIST', 'FOREIGN_PENDING_WORK']


def test_registered_compares_the_files_with_the_registry_rows(tmp_path, monkeypatch):
    directory, _ = _provision(tmp_path, monkeypatch)
    run = driver.Run(tmp_path / 'out', identities=directory)
    run.load_identities()
    assert (run.store, run.people) == (STORE, PEOPLE)
    principals = [dict(row) for row in run.ids.principals.values()]
    sessions = [dict(row) for row in run.ids.sessions.values()]
    run.rows = lambda table, *where: {'customer_principals': principals, 'customer_sessions': sessions}[table.name]
    run.registered()
    for rows, change in ((principals, dict(store_id='other_store')), (principals, dict(enabled=False)),
                         (sessions, dict(revoked=True)), (sessions, dict(expires_at=1))):
        original = dict(rows[0])
        rows[0].update(change)
        with pytest.raises(driver.Refused) as refused:
            run.registered()
        assert refused.value.code == 'IDENTITIES_NOT_REGISTERED'
        rows[0].clear()
        rows[0].update(original)
    sessions.pop()
    with pytest.raises(driver.Refused):
        run.registered()


def test_argument_parsing(tmp_path):
    args = driver.parse_args(['--output', 'x'])
    assert (args.identities, args.api_port, args.keep_api, args.keep_api_log, args.allow_existing_data) == (
        None, None, False, False, False)
    args = driver.parse_args(['--output', 'x', '--identities', 'ids', '--api-port', '8000', '--keep-api',
                              '--allow-existing-data'])
    assert (args.identities, args.api_port, args.keep_api, args.allow_existing_data) == ('ids', 8000, True, True)
    assert driver.parse_args(['--output', 'x', '--api-port', '65535']).api_port == 65535
    for argv in (['--api-port', '80'], ['--api-port', '65536'], ['--api-port', 'eighty'], ['--keep-api'],
                 ['--identities', 'ids', '--keep-api', '--keep-api-log']):
        with pytest.raises(SystemExit) as stopped:
            driver.parse_args(['--output', 'x', *argv])
        assert stopped.value.code == 2
    shown = driver.parser().format_help()
    assert '--identities' in shown and '--api-port' in shown and '--keep-api' in shown and 'not CI evidence' in shown
    private = tmp_path / 'private'
    for output in (private, private / 'out'):
        assert driver.main(['--output', str(output), '--identities', str(private)]) == 2
    assert not private.exists()
    assert driver.main(['--output', str(tmp_path), '--identities', str(private)]) == 2


def test_refused_demo_run_records_demo_mode_without_secrets(tmp_path, monkeypatch):
    directory, _ = _provision(tmp_path, monkeypatch)
    output = tmp_path / 'demo-output'
    assert driver.main(['--output', str(output), '--identities', str(directory)]) == 2
    content = (output / driver.RECEIPT).read_text(encoding='ascii')
    receipt = json.loads(content)
    assert receipt['result'] == 'REFUSED' and receipt['stop'] == {'code': 'DATABASE_URL_REJECTED', 'step': 0}
    assert receipt['demo_mode'] == dict(enabled=True, evidence=False, identities_source='returnops_api.demo provision',
                                        keep_api=False, api_port=None)
    assert receipt['options'] == dict(keep_api_log=False, allow_existing_data=False, identities=True, keep_api=False)
    assert receipt['identities'] == dict(store_id=STORE, **PEOPLE)
    assert receipt['limitations'] == list(driver.LIMITATIONS + driver.DEMO_LIMITATIONS)
    ids = demo_identities.load(directory)  # the private files are left as they were
    for value in [*ids.secret_values(), 'Bearer', str(directory), json.dumps(str(directory))[1:-1], str(tmp_path)]:
        assert value not in content
    assert sorted(path.name for path in output.iterdir()) == [driver.RECEIPT]
    missing = tmp_path / 'missing-output'
    assert driver.main(['--output', str(missing), '--identities', str(tmp_path / 'nope')]) == 2
    assert json.loads((missing / driver.RECEIPT).read_text(encoding='ascii'))['stop'] == {
        'code': 'IDENTITIES_DIRECTORY_MISSING', 'step': 0}


def test_demo_receipt_with_a_token_or_key_is_replaced(tmp_path, monkeypatch):
    directory, _ = _provision(tmp_path, monkeypatch)
    for leak in (lambda ids: ids.tokens['founder'], lambda ids: ids.signing_key.hex(), lambda ids: ids.signing_key_base64):
        def environment(self, leak=leak):
            self.load_identities()
            self.data['leak'] = leak(self.ids)
            raise driver.Refused('TEST_STOP')

        monkeypatch.setattr(driver.Run, 'environment', environment)
        output = tmp_path / ('leak-' + str(id(leak)))
        output.mkdir()
        assert driver.Run(output, identities=directory).execute() == 'FAILED'
        receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
        assert receipt['stop'] == dict(code='RECEIPT_REDACTION_FAILED', original_result='REFUSED',
                                       original_stop='TEST_STOP')


def test_fixed_port_is_reserved_or_refused():
    port = api_child.reserve_port()
    assert port > 0
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen()
        taken = busy.getsockname()[1]
        with pytest.raises(api_child.ApiChildError) as refused:
            api_child.reserve_port(taken)
        assert str(refused.value) == 'API_PORT_UNAVAILABLE'
    assert api_child.reserve_port(taken) == taken


class _FakeProcess:
    pid = 4242

    def __init__(self, seen):
        self.seen, self.code = seen, None

    def poll(self):
        return self.code

    def terminate(self):
        self.seen.append('terminate')
        self.code = 0

    def wait(self, timeout=None):
        return self.code

    def kill(self):
        self.seen.append('kill')


def test_api_process_uses_the_fixed_port_and_stops_the_child(tmp_path, monkeypatch):
    seen, environments, probes = [], [], []

    def popen(args, *, env, stdout, stderr, creationflags):
        environments.append(env)
        return _FakeProcess(seen)

    class Probe:
        def __init__(self, **options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *failure):
            return False

        def get(self, url):
            probes.append(url)
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(api_child.subprocess, 'Popen', popen)
    monkeypatch.setattr(api_child.httpx, 'Client', Probe)
    port = api_child.reserve_port()
    with api_child.api_process(tmp_path / 'auth.json', tmp_path / 'api.log', port=port) as api:
        assert api.url == 'http://127.0.0.1:' + str(port) and api.process.poll() is None and seen == []
        assert environments[-1]['RETURNOPS_R02_PORT'] == str(port) and probes == [api.url + '/health/ready']
    assert seen == ['terminate']
    with api_child.api_process(tmp_path / 'auth.json', tmp_path / 'api-default.log') as api:
        assert api.url == 'http://127.0.0.1:' + environments[-1]['RETURNOPS_R02_PORT']
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen()
        with pytest.raises(api_child.ApiChildError):
            with api_child.api_process(tmp_path / 'auth.json', tmp_path / 'api-busy.log', port=busy.getsockname()[1]):
                pytest.fail('a busy port must not start a child')
    assert len(environments) == 2


def test_hold_returns_on_exit_or_ctrl_c():
    polls, sleeps = iter([None, None, 0]), []
    api = SimpleNamespace(process=SimpleNamespace(poll=lambda: next(polls)))
    assert api_child.hold(api, sleep=sleeps.append) == 'EXITED' and len(sleeps) == 2

    def interrupt(seconds):
        raise KeyboardInterrupt

    assert api_child.hold(SimpleNamespace(process=SimpleNamespace(poll=lambda: None)), sleep=interrupt) == 'INTERRUPTED'


def _fake_run(monkeypatch, tmp_path, events, outcome):
    """environment/provision/steps replaced; the API child is a fake context with a fake process."""
    def environment(self):
        if self.identities_dir is not None:
            self.load_identities()
        self.record(0, 'environment', 'OK')

    def provision(self):
        self.step_number = 1
        self.private = tmp_path / 'private'
        self.private.mkdir()
        self.locate('<private>', self.private)
        self.auth_file = self.ids.auth_file if self.ids is not None else self.private / 'auth.json'

    @contextmanager
    def api_process(auth_file, log, **options):
        events.append(('start', options))
        process = SimpleNamespace(poll=lambda: None)
        try:
            yield api_child.ApiChild('http://127.0.0.1:8765', 4242, dict(api_child.COMPOSITION), ('PATH',), process)
        finally:
            events.append('stop')

    def customer_create(self):
        self.step_number, self.case = 3, 'case_r02_demo'
        if outcome == 'FAILED':
            raise driver.Stop('API_WORKER_SUSPECTED')
        self.check('demo_check', True)

    monkeypatch.setattr(driver.Run, 'environment', environment)
    monkeypatch.setattr(driver.Run, 'provision', provision)
    monkeypatch.setattr(driver.Run, 'customer_create', customer_create)
    for name in ('processors', 'review_and_preview', 'decisions', 'execution_chain', 'read_back'):
        monkeypatch.setattr(driver.Run, name, lambda self: None)
    monkeypatch.setattr(driver.api_child, 'api_process', api_process)


@pytest.mark.parametrize('outcome', ['PASSED', 'FAILED'])
def test_keep_api_writes_the_receipt_then_holds_then_stops(tmp_path, monkeypatch, capsys, outcome):
    directory, _ = _provision(tmp_path, monkeypatch)
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, outcome)

    def hold(api, **options):
        receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
        events.append(('hold', receipt['result'], (tmp_path / 'private').exists()))
        return 'INTERRUPTED'

    monkeypatch.setattr(driver.api_child, 'hold', hold)
    run = driver.Run(output, identities=directory, api_port=8765, keep_api=True)
    assert run.execute() == outcome
    assert events == [('start', {'port': 8765}), ('hold', outcome, True), 'stop']
    content = (output / driver.RECEIPT).read_text(encoding='ascii')
    receipt = json.loads(content)
    assert receipt['result'] == outcome
    assert receipt['demo_mode']['keep_api'] is True and receipt['demo_mode']['api_port'] == 8765
    assert receipt['options'] == dict(keep_api_log=False, allow_existing_data=False, api_port=8765, identities=True,
                                      keep_api=True)
    assert receipt['limitations'][-1] == driver.KEEP_API_LIMITATION and 'finished_at' in receipt
    assert 'private_directory_removed' not in receipt and not (tmp_path / 'private').exists()
    if outcome == 'FAILED':
        assert receipt['stop'] == dict(code='API_WORKER_SUSPECTED', step=3)
    printed = capsys.readouterr()
    assert 'http://127.0.0.1:8765' in printed.out and 'Ctrl+C' in printed.out and 'case_r02_demo' in printed.out
    for value in [*run.ids.secret_values(), 'Bearer', str(directory)]:
        assert value not in content and value not in printed.out and value not in printed.err


def test_ctrl_c_during_the_chain_records_interrupted_and_stops_the_child(tmp_path, monkeypatch, capsys):
    directory, _ = _provision(tmp_path, monkeypatch)
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')

    def customer_create(self):
        self.step_number, self.case = 3, 'case_r02_demo'
        raise KeyboardInterrupt()

    monkeypatch.setattr(driver.Run, 'customer_create', customer_create)
    monkeypatch.setattr(driver.api_child, 'hold', lambda api, **options: pytest.fail('an interrupted run never holds'))
    run = driver.Run(output, identities=directory, api_port=8765, keep_api=False)
    assert run.execute() == 'FAILED'
    assert events == [('start', {'port': 8765}), 'stop']
    receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
    assert receipt['result'] == 'FAILED' and receipt['stop'] == dict(code='INTERRUPTED', step=3)
    assert 'finished_at' in receipt and receipt['private_directory_removed'] is True
    printed = capsys.readouterr()
    for value in [*run.ids.secret_values(), 'Bearer', str(directory)]:
        assert value not in printed.out and value not in printed.err


def test_default_mode_stops_the_child_before_the_receipt_and_never_holds(tmp_path, monkeypatch):
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'FAILED')
    monkeypatch.setattr(driver.api_child, 'hold', lambda api, **options: pytest.fail('default mode never holds'))
    original = driver.Run.publish

    def publish(self):
        events.append('receipt')
        original(self)

    monkeypatch.setattr(driver.Run, 'publish', publish)
    run = driver.Run(output)
    assert run.execute() == 'FAILED'
    assert events == [('start', {}), 'stop', 'receipt']
    receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
    assert 'demo_mode' not in receipt and receipt['limitations'] == list(driver.LIMITATIONS)
    assert receipt['options'] == dict(keep_api_log=False, allow_existing_data=False)
    assert receipt['private_directory_removed'] is True and receipt['stop'] == dict(code='API_WORKER_SUSPECTED', step=3)


# ---------------------------------------------------------------- R02-C-02: isolated cleanup, private raw log

def _logging_api(monkeypatch, tmp_path, events, output, raw):
    """A fake API child that writes raw output to the log path the driver gives it."""
    @contextmanager
    def api_process(auth_file, log, **options):
        assert Path(log).parent == tmp_path / 'private', 'raw child output must go to the private directory'
        assert not (output / driver.API_LOG).exists()
        Path(log).write_bytes(raw)
        events.append(('start', options))
        try:
            yield api_child.ApiChild('http://127.0.0.1:8765', 4242, dict(api_child.COMPOSITION), ('PATH',),
                                     SimpleNamespace(poll=lambda: None))
        finally:
            events.append('stop')
    monkeypatch.setattr(driver.api_child, 'api_process', api_process)


def _raw_log(tmp_path):
    return b'uvicorn started from ' + str(tmp_path / 'private').encode('utf-8') + b'\n'


def test_kept_log_stays_private_until_screened_then_only_the_screened_copy_is_published(tmp_path, monkeypatch):
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _logging_api(monkeypatch, tmp_path, events, output, _raw_log(tmp_path))
    run = driver.Run(output, keep_api_log=True)
    assert run.execute() == 'PASSED'
    published = (output / driver.API_LOG).read_bytes()
    assert b'<private>' in published and str(tmp_path / 'private').encode('utf-8') not in published
    receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
    assert receipt['api_log'] == driver.API_LOG and receipt['private_directory_removed'] is True
    assert 'cleanup_failures' not in receipt and not (tmp_path / 'private').exists()


def test_engine_dispose_failure_does_not_skip_screening_removal_or_receipt(tmp_path, monkeypatch):
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _logging_api(monkeypatch, tmp_path, events, output, _raw_log(tmp_path))
    fake_environment = driver.Run.environment

    def failing_dispose():
        raise RuntimeError('dispose failed: postgresql://user:secret@host/db')

    def environment(self):
        fake_environment(self)
        self.engine = SimpleNamespace(dispose=failing_dispose)
    monkeypatch.setattr(driver.Run, 'environment', environment)
    run = driver.Run(output, keep_api_log=True)
    assert run.execute() == 'PASSED'
    content = (output / driver.RECEIPT).read_text(encoding='ascii')
    receipt = json.loads(content)
    assert receipt['cleanup_failures'] == ['ENGINE_DISPOSE_FAILED'] and 'secret' not in content
    assert receipt['private_directory_removed'] is True and not (tmp_path / 'private').exists()
    assert b'<private>' in (output / driver.API_LOG).read_bytes()


def test_log_screening_failure_withholds_the_log_and_still_cleans_up(tmp_path, monkeypatch):
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _logging_api(monkeypatch, tmp_path, events, output, _raw_log(tmp_path))

    def failing_screen(raw, credentials, locations):
        raise MemoryError()
    monkeypatch.setattr(driver, 'screen_log', failing_screen)
    run = driver.Run(output, keep_api_log=True)
    assert run.execute() == 'PASSED'
    assert (output / driver.API_LOG).read_bytes() == driver.LOG_UNSCREENED
    receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
    assert receipt['api_log'] == 'WITHHELD' and receipt['cleanup_failures'] == ['API_LOG_SCREEN_FAILED']
    assert receipt['private_directory_removed'] is True and not (tmp_path / 'private').exists()


def test_interrupted_run_never_leaves_the_raw_log_in_the_output(tmp_path, monkeypatch):
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _logging_api(monkeypatch, tmp_path, events, output, _raw_log(tmp_path))

    def customer_create(self):
        self.step_number = 3
        raise KeyboardInterrupt()
    monkeypatch.setattr(driver.Run, 'customer_create', customer_create)
    run = driver.Run(output, keep_api_log=True)
    assert run.execute() == 'FAILED'
    receipt = json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))
    assert receipt['stop'] == dict(code='INTERRUPTED', step=3)
    published = (output / driver.API_LOG).read_bytes()
    assert str(tmp_path / 'private').encode('utf-8') not in published and not (tmp_path / 'private').exists()


# ---------------------------------------------------------------- R02-C-03: an unwritable receipt is never success

def _unwritable_receipt(monkeypatch):
    def write_receipt(path, data, forbidden):
        raise OSError('disk full while writing postgresql://user:secret@localhost/returnops_f02')
    monkeypatch.setattr(driver, 'write_receipt', write_receipt)


def test_unwritable_receipt_fails_the_cli_without_pointing_to_a_receipt(tmp_path, monkeypatch, capsys):
    output, events = tmp_path / 'out', []
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _unwritable_receipt(monkeypatch)
    assert driver.main(['--output', str(output)]) == 1
    printed = capsys.readouterr()
    assert printed.out.strip().splitlines()[-1] == 'R.02 driver result: FAILED (the run receipt could not be written).'
    assert 'PASSED' not in printed.out and 'secret' not in printed.out + printed.err
    assert 'R.02: the run receipt could not be written.' in printed.err
    assert not (output / driver.RECEIPT).exists() and not (tmp_path / 'private').exists()
    assert events == [('start', {}), 'stop']


def test_unwritable_receipt_in_keep_api_mode_never_holds_and_fails(tmp_path, monkeypatch, capsys):
    directory, _ = _provision(tmp_path, monkeypatch)
    output, events = tmp_path / 'out', []
    output.mkdir()
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    _unwritable_receipt(monkeypatch)
    monkeypatch.setattr(driver.api_child, 'hold', lambda api, **options: pytest.fail('no hold without a receipt'))
    run = driver.Run(output, identities=directory, api_port=8765, keep_api=True)
    assert run.execute() == 'FAILED' and run.receipt_written is False
    assert events == [('start', {'port': 8765}), 'stop'] and not (output / driver.RECEIPT).exists()
    printed = capsys.readouterr()
    assert 'secret' not in printed.out + printed.err and 'Ctrl+C' not in printed.out


def test_written_receipt_still_reports_the_business_result(tmp_path, monkeypatch, capsys):
    output, events = tmp_path / 'out', []
    _fake_run(monkeypatch, tmp_path, events, 'PASSED')
    assert driver.main(['--output', str(output)]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == 'R.02 driver result: PASSED (see run-receipt.json).'
    assert json.loads((output / driver.RECEIPT).read_text(encoding='ascii'))['result'] == 'PASSED'
