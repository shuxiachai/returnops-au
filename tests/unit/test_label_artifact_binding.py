"""Pure offline rejection coverage; no project fixtures, engines or DB access."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket

import psycopg
import pytest
import sqlalchemy
from sqlalchemy.engine import make_url

SPEC = importlib.util.spec_from_file_location(
    'tested_label_artifact_binding', Path(__file__).parents[1] / 'lifecycle/label_artifact_binding.py')
binding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(binding)
SCHEMA = 'customer_test_' + 'a' * 32
PASSWORD = 'never-export-this'
CI = 'postgresql+psycopg://returnops_ci:' + PASSWORD + '@localhost:5432/returnops_f02_ci'
LEGACY = sorted(binding.LEGACY_NAMES)


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline checks attempted a connection or engine')
    monkeypatch.setattr(sqlalchemy, 'create_engine', forbidden)
    monkeypatch.setattr(sqlalchemy.engine.create, 'create_engine', forbidden)
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


def fixture(raw=CI):
    url = make_url(raw)
    identity = dict(database=url.database, oid=16384, role=url.username,
                    session_role=url.username, server_port=5432, pg_version=170011,
                    schema=SCHEMA, revisions=[binding.REVISION])
    env = {} if url.database == 'returnops_f02_ci' else dict(
        ARTIFACT_DATABASE_NAME=url.database, ARTIFACT_DATABASE_OID='16384')
    return url, identity, env


@pytest.mark.parametrize('database', [None, *LEGACY])
def test_exact_supported_profiles(database):
    raw = CI if database is None else (
        'postgresql+psycopg://returnops_ci:' + PASSWORD + '@127.0.0.1:55433/' + database)
    url, identity, env = fixture(raw)
    value = binding.parent_binding(raw, url, SCHEMA, identity, env)
    assert binding.child_binding(raw, value, SCHEMA, env) == url
    binding.live_identity(value, deepcopy(identity))
    assert PASSWORD not in json.dumps(value) and raw not in json.dumps(value)


@pytest.mark.parametrize('database', LEGACY[:2])
def test_historical_role_and_internal_port_scope_preserved(database):
    raw = 'postgresql+psycopg://historical_role:private@127.0.0.1:55433/' + database
    url, identity, env = fixture(raw)
    identity['server_port'] = 5440
    env['ARTIFACT_DATABASE_OID'] = '00016384'
    value = binding.parent_binding(raw, url, SCHEMA, identity, env)
    assert binding.child_binding(raw, value, SCHEMA, env) == url
    binding.live_identity(value, deepcopy(identity))


@pytest.mark.parametrize('raw', [
    CI.replace('postgresql+psycopg', 'postgresql'), CI.replace('localhost', 'remote.invalid'),
    CI.replace('localhost', '127.0.0.1'), CI.replace(':5432/', ':55433/'),
    CI.replace(':5432/', '/'), CI.replace('returnops_f02_ci', 'returnops_f02_other'),
    CI.replace('returnops_ci:', 'other:'), CI.replace('returnops_ci:', ':'),
    CI + '?host=remote.invalid', CI + '?options=-csearch_path=public', CI + '#fragment',
    CI + '?', CI + '#', CI + '\n', '', 'not-a-url', None,
    'postgresql+psycopg://user:pw@127.0.0.1:55433/returnops_f02_ci',
    'postgresql+psycopg://user:pw@localhost:5432/' + LEGACY[0],
])
def test_unapproved_urls_rejected_before_observation(raw):
    with pytest.raises(AssertionError):
        binding.target_url(raw)


@pytest.mark.parametrize('field,value', [
    ('database', 'returnops_f02_other'), ('oid', 0), ('oid', -1), ('oid', True), ('oid', '16384'),
    ('role', 'other'), ('session_role', 'other'), ('server_port', 5440), ('server_port', 0),
    ('server_port', 65536), ('server_port', True), ('server_port', '5432'),
    ('pg_version', 170010), ('pg_version', 180000), ('pg_version', '170011'),
    ('schema', 'public'), ('schema', 'customer_test_' + 'b' * 32),
    ('revisions', []), ('revisions', [binding.REVISION, binding.REVISION]),
    ('revisions', ['0012_generated_evidence']), ('revisions', binding.REVISION),
])
def test_parent_observed_identity_must_match(field, value):
    url, identity, env = fixture()
    identity[field] = value
    with pytest.raises(AssertionError):
        binding.parent_binding(CI, url, SCHEMA, identity, env)


@pytest.mark.parametrize('raw', [CI.replace(PASSWORD, 'changed-password'),
    CI.replace('localhost', '127.0.0.1')])
def test_parent_environment_cannot_differ_from_fixture_engine(raw):
    url, identity, env = fixture()
    with pytest.raises(AssertionError):
        binding.parent_binding(raw, url, SCHEMA, identity, env)


@pytest.mark.parametrize('change', ['missing', 'extra', 'format-bool', 'format-version', 'profile',
    'schema', 'fingerprint', 'identity-extra', 'identity-missing', 'oid', 'role', 'port', 'version', 'head'])
def test_private_config_tamper_rejected(change):
    url, identity, env = fixture()
    value = binding.parent_binding(CI, url, SCHEMA, identity, env)
    value = deepcopy(value)
    if change == 'missing': del value['profile']
    elif change == 'extra': value['unexpected'] = True
    elif change == 'format-bool': value['format'] = True
    elif change == 'format-version': value['format'] = 2
    elif change == 'profile': value['profile'] = 'arbitrary'
    elif change == 'schema': value['schema'] = 'customer_test_' + 'b' * 32
    elif change == 'fingerprint': value['url_sha256'] = '0' * 64
    elif change == 'identity-extra': value['identity']['unexpected'] = True
    elif change == 'identity-missing': del value['identity']['role']
    elif change == 'oid': value['identity']['oid'] = False
    elif change == 'role': value['identity']['session_role'] = 'other'
    elif change == 'port': value['identity']['server_port'] = 5440
    elif change == 'version': value['identity']['pg_version'] = 180000
    elif change == 'head': value['identity']['revisions'] = []
    with pytest.raises(AssertionError):
        binding.child_binding(CI, value, SCHEMA, env)


def test_child_password_change_rejected_before_connection():
    url, identity, env = fixture()
    value = binding.parent_binding(CI, url, SCHEMA, identity, env)
    with pytest.raises(AssertionError):
        binding.child_binding(CI.replace(PASSWORD, 'changed-password'), value, SCHEMA, env)


@pytest.mark.parametrize('field,value', [
    ('database', 'other'), ('oid', 16385), ('oid', True), ('role', 'other'), ('session_role', 'other'),
    ('server_port', 5440), ('pg_version', 170012), ('schema', 'public'), ('revisions', []),
])
def test_each_child_live_identity_difference_rejected(field, value):
    url, identity, env = fixture()
    approved = binding.parent_binding(CI, url, SCHEMA, identity, env)
    observed = deepcopy(identity); observed[field] = value
    with pytest.raises(AssertionError):
        binding.live_identity(approved, observed)


@pytest.mark.parametrize('env', [
    {'ARTIFACT_DATABASE_NAME': ''}, {'ARTIFACT_DATABASE_OID': ''},
    {'ARTIFACT_DATABASE_NAME': 'returnops_f02_ci', 'ARTIFACT_DATABASE_OID': '16384'},
])
def test_ci_does_not_accept_legacy_environment_overrides(env):
    url, identity, _ = fixture()
    with pytest.raises(AssertionError):
        binding.parent_binding(CI, url, SCHEMA, identity, env)


@pytest.mark.parametrize('change', ['missing-name', 'missing-oid', 'both-missing', 'wrong-name',
    'wrong-oid', 'zero-oid', 'negative-oid', 'malformed-oid', 'bool-oid'])
def test_original_legacy_environment_bindings_remain_required(change):
    raw = 'postgresql+psycopg://user:pw@127.0.0.1:55433/' + LEGACY[0]
    url, identity, env = fixture(raw)
    if change == 'missing-name': del env['ARTIFACT_DATABASE_NAME']
    elif change == 'missing-oid': del env['ARTIFACT_DATABASE_OID']
    elif change == 'both-missing': env.clear()
    elif change == 'wrong-name': env['ARTIFACT_DATABASE_NAME'] = LEGACY[1]
    else:
        env['ARTIFACT_DATABASE_OID'] = {'wrong-oid': '16385', 'zero-oid': '0',
            'negative-oid': '-1', 'malformed-oid': '16384x', 'bool-oid': True}[change]
    with pytest.raises(AssertionError):
        binding.parent_binding(raw, url, SCHEMA, identity, env)


def test_observation_reads_only_catalog_and_exact_validated_schema():
    _, identity, _ = fixture(); calls = []
    class Result:
        def fetchone(self): return tuple(identity[key] for key in binding.IDENTITY_KEYS)
        def fetchall(self): return [(binding.REVISION,)]
    def execute(sql):
        calls.append(sql)
        return Result()
    assert binding.observe(execute, SCHEMA) == identity
    assert calls == [binding.IDENTITY_SQL,
        'SELECT version_num FROM ' + SCHEMA + '.alembic_version ORDER BY version_num']


@pytest.mark.parametrize('schema', ['public', 'customer_test_x', SCHEMA + ';SELECT 1', None])
def test_invalid_schema_never_reaches_query(schema):
    def forbidden(sql): raise RuntimeError('query unexpectedly executed')
    with pytest.raises(AssertionError): binding.observe(forbidden, schema)
