"""tools/railway/start.py keeps the previous deployment's data (31 October 2026).

A start keeps the database and restores the private files only when all of them are there,
the application database still holds the demo Founder, and no reset was asked for; any doubt
starts a fresh demonstration, and a database that cannot be read is never wiped. NFR-003,
NFR-004; docs/47 section 7.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools' / 'railway' / 'start.py'
SPEC = importlib.util.spec_from_file_location('railway_start_keep', SCRIPT)
start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(start)

FILES = {'auth.json': b'{"a": 1}\n', 'credentials.json': b'{"b": 2}\n', 'sessions.json': b'{"c": 3}\n',
         'passwords.json': b'{"d": 4}\n'}


def test_only_a_complete_set_on_a_provisioned_database_is_kept():
    assert start.keep_previous(FILES, True, {})
    assert not start.keep_previous(FILES, True, {'RETURNOPS_RESET_ON_START': '1'})
    assert not start.keep_previous(FILES, False, {})
    for missing in start.KEPT_FILES:
        assert not start.keep_previous({k: v for k, v in FILES.items() if k != missing}, True, {})
    assert start.keep_previous({k: v for k, v in FILES.items() if k != 'passwords.json'}, True, {})


def test_private_files_round_trip_with_private_modes(tmp_path):
    folder = tmp_path / 'demo-shop'
    start.write_folder(folder, FILES)
    (folder / 'credentials.json.abc123.tmp').write_bytes(b'half written')
    assert start.read_folder(folder) == FILES
    if os.name == 'posix':
        assert folder.stat().st_mode & 0o777 == 0o700
        assert {(path.stat().st_mode & 0o777) for path in folder.iterdir() if not path.name.endswith('.tmp')} == {0o600}
    before = start.fingerprint(FILES)
    assert start.fingerprint({**FILES, 'credentials.json': b'{"b": 3}\n'}) != before
    for bad in ('../auth.json', 'a/b', '..'):
        with pytest.raises(ValueError):
            start.write_folder(tmp_path / 'other', {bad: b'x'})
    assert start.read_folder(tmp_path / 'missing') == {}


def test_a_kept_start_restores_the_files_and_renews_the_sessions(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(start, 'SHOP', tmp_path / 'demo-shop')
    monkeypatch.setattr(start, 'open_private_store', lambda server: None)
    monkeypatch.setattr(start, 'load_private', lambda server: dict(FILES))
    monkeypatch.setattr(start, 'provisioned', lambda server: True)
    monkeypatch.delenv('RETURNOPS_RESET_ON_START', raising=False)
    monkeypatch.setattr(start.subprocess, 'run', lambda arguments, **kwargs: calls.append(arguments) or subprocess.CompletedProcess(arguments, 0))
    assert start.start_kept('postgresql://server/postgres', {}) is True
    assert start.read_folder(tmp_path / 'demo-shop') == FILES
    assert [call[2:4] for call in calls] == [['alembic', 'upgrade'], ['returnops_api.demo', 'renew-sessions']]

    # A step that fails on the kept data starts a fresh demonstration instead.
    monkeypatch.setattr(start.subprocess, 'run', lambda arguments, **kwargs: subprocess.CompletedProcess(arguments, 1))
    assert start.start_kept('postgresql://server/postgres', {}) is False


def test_doubt_starts_fresh_and_an_unreadable_database_is_never_wiped(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(start, 'SHOP', tmp_path / 'demo-shop')
    monkeypatch.setattr(start, 'open_private_store', lambda server: None)

    def unreadable(server):
        raise psycopg.OperationalError('connection lost')
    monkeypatch.setattr(start, 'load_private', unreadable)
    assert start.start_kept('postgresql://server/postgres', {}, read_seconds=0) is False
    assert 'starting a fresh demonstration' in capsys.readouterr().out

    # A passing hiccup is retried (1 November 2026): the second read finds the kept files.
    reads = []
    def hiccup(server):
        reads.append(server)
        if len(reads) == 1:
            raise psycopg.OperationalError('connection lost')
        return dict(FILES)
    monkeypatch.setattr(start, 'load_private', hiccup)
    monkeypatch.setattr(start.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(start, 'provisioned', lambda server: False)
    assert start.start_kept('postgresql://server/postgres', {}) is False and len(reads) == 2
    assert 'could not be read' not in capsys.readouterr().out

    monkeypatch.setattr(start, 'load_private', lambda server: dict(FILES))
    monkeypatch.setattr(start, 'provisioned', lambda server: False)
    assert start.start_kept('postgresql://server/postgres', {}) is False

    monkeypatch.setattr(start, 'provisioned', unreadable)
    with pytest.raises(SystemExit) as stopped:
        start.start_kept('postgresql://server/postgres', {})
    assert stopped.value.code == 1 and 'nothing was removed' in capsys.readouterr().out


def test_only_forget_data_is_accepted_as_an_argument():
    environment = {**os.environ, 'DATABASE_URL': 'not-a-url', 'PYTHONDONTWRITEBYTECODE': '1'}
    unknown = subprocess.run([sys.executable, '-B', str(SCRIPT), 'wipe'], capture_output=True, text=True, timeout=60, env=environment)
    assert unknown.returncode == 2 and 'usage' in unknown.stdout
    forget = subprocess.run([sys.executable, '-B', str(SCRIPT), 'forget-data'], capture_output=True, text=True, timeout=60, env=environment)
    assert forget.returncode == 1 and 'DATABASE_URL' in forget.stdout and 'not-a-url' not in forget.stdout


@pytest.fixture
def server():
    value = os.environ.get('DATABASE_URL')
    if not value:
        pytest.fail('Real PostgreSQL checks require an explicitly injected DATABASE_URL')
    parts = urlsplit(value)
    url = urlunsplit(('postgresql', parts.netloc, '/postgres', '', ''))
    created = []
    yield url, created
    with psycopg.connect(url, autocommit=True) as connection:
        for name in created:
            connection.execute(start.sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(start.sql.Identifier(name)))


def test_the_private_store_keeps_replaces_and_forgets_on_real_postgresql(server):
    url, created = server
    name = 'returnops_f02_private_' + uuid4().hex[:8]
    created.append(name)
    start.forget_private(url, name)  # no database yet: nothing to do
    start.open_private_store(url, name)
    start.open_private_store(url, name)  # a second start finds it in place
    assert start.load_private(url, name) == {}
    start.save_private(url, FILES, name)
    assert start.load_private(url, name) == FILES
    start.save_private(url, {'auth.json': b'new'}, name)
    assert start.load_private(url, name) == {'auth.json': b'new'}
    start.forget_private(url, name)
    assert start.load_private(url, name) == {}


def test_provisioned_needs_the_enabled_demo_founder_on_real_postgresql(server):
    url, created = server
    name = 'returnops_f02_keep_' + uuid4().hex[:8]
    assert start.provisioned(url, name) is False  # no database
    created.append(name)
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(start.sql.SQL('CREATE DATABASE {}').format(start.sql.Identifier(name)))
    assert start.provisioned(url, name) is False  # no table
    with psycopg.connect(start.on_server(url, name), autocommit=True) as connection:
        connection.execute('CREATE TABLE customer_principals (principal_id text PRIMARY KEY, store_id text, role text, enabled boolean)')
        connection.execute("INSERT INTO customer_principals VALUES ('founder', 'synthetic_au_store', 'FOUNDER', false)")
    assert start.provisioned(url, name) is False  # disabled
    with psycopg.connect(start.on_server(url, name), autocommit=True) as connection:
        connection.execute("UPDATE customer_principals SET enabled = true")
    assert start.provisioned(url, name) is True
