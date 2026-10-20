"""Offline rejection/transport checks for installed label and bridge probes.

Issue81/KAN-15; FR-009/010/011, NFR-002/004/006/008; UC-04,
governed-execution sequence and OperationAttempt state model. No DB fixtures.
"""
import ast
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import psycopg
import pytest
import sqlalchemy
from sqlalchemy.engine import make_url

LIFECYCLE = Path(__file__).parents[1] / 'lifecycle'
SPEC = importlib.util.spec_from_file_location('remaining_probe_binding', LIFECYCLE / 'label_artifact_binding.py')
binding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(binding)
SCHEMA = 'customer_test_' + 'a' * 32
CI = 'postgresql+psycopg://returnops_ci:private-synthetic@localhost:5432/returnops_f02_ci'
COMPONENTS = ('label', 'bridge')
FILES = {'label': ('label_execution_probe.py', 'test_label_execution_process_postgresql.py'),
         'bridge': ('return_label_bridge_probe.py', 'test_return_label_bridge_process_postgresql.py')}


@pytest.fixture(autouse=True)
def no_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline check attempted network, engine or real child')
    for target, name in ((sqlalchemy, 'create_engine'), (sqlalchemy.engine.create, 'create_engine'),
                         (psycopg, 'connect'), (socket, 'create_connection'),
                         (socket.socket, 'connect'), (subprocess, 'Popen')):
        monkeypatch.setattr(target, name, forbidden)


def fixture(component, database=None):
    raw = CI if database is None else 'postgresql+psycopg://historical_role:private@127.0.0.1:55433/' + database
    url = make_url(raw)
    identity = dict(database=url.database, oid=16384, role=url.username, session_role=url.username,
                    server_port=5432, pg_version=170011, schema=SCHEMA, revisions=[binding.REVISION])
    prefix = 'ARTIFACT' if database in binding.LEGACY_NAMES else ('LABEL' if database == binding.LABEL_NAME else 'BRIDGE')
    env = {} if database is None else {prefix + '_DATABASE_NAME': database, prefix + '_DATABASE_OID': '16384'}
    return raw, url, identity, env


PROFILES = [(component, name) for component in COMPONENTS
            for name in [None, *sorted(binding.COMPONENT_NAMES[component])]]


@pytest.mark.parametrize('component,database', PROFILES)
def test_exact_original_component_targets_and_ci(component, database):
    raw, url, identity, env = fixture(component, database)
    approved = binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)
    assert set(approved) == binding.BINDING_KEYS | {'component'}
    assert approved['component'] == component
    assert binding.child_binding(raw, approved, SCHEMA, env, component=component) == url
    binding.live_identity(approved, deepcopy(identity))
    assert 'private' not in json.dumps(approved) and raw not in json.dumps(approved)


@pytest.mark.parametrize('component', COMPONENTS)
@pytest.mark.parametrize('change', ['remote', 'port', 'driver', 'database', 'query', 'user', 'missing-port', 'fragment'])
def test_unapproved_ci_tuple_rejected(component, change):
    raw = {'remote': CI.replace('localhost', 'remote.invalid'), 'port': CI.replace(':5432/', ':55433/'),
           'driver': CI.replace('+psycopg', ''), 'database': CI.replace('returnops_f02_ci', 'other'),
           'query': CI + '?host=remote.invalid', 'user': CI.replace('returnops_ci:', 'other:'),
           'missing-port': CI.replace(':5432/', '/'), 'fragment': CI + '#fragment'}[change]
    with pytest.raises(AssertionError):
        binding.target_url(raw, component=component)


@pytest.mark.parametrize('component', COMPONENTS)
@pytest.mark.parametrize('change', ['component', 'component-missing', 'extra', 'format', 'fingerprint',
                                   'schema', 'oid', 'role', 'session-role', 'port', 'version', 'head', 'multi-head'])
def test_child_rejects_binding_tamper_before_connection(component, change):
    raw, url, identity, env = fixture(component)
    value = binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)
    value = deepcopy(value)
    if change == 'component': value['component'] = 'bridge' if component == 'label' else 'label'
    elif change == 'component-missing': del value['component']
    elif change == 'extra': value['extra'] = True
    elif change == 'format': value['format'] = True
    elif change == 'fingerprint': value['url_sha256'] = '0' * 64
    elif change == 'schema': value['schema'] = 'public'
    else:
        field, content = {'oid': ('oid', True), 'role': ('role', 'other'),
            'session-role': ('session_role', 'other'), 'port': ('server_port', 5440),
            'version': ('pg_version', 170010), 'head': ('revisions', ['0012_label_execution']),
            'multi-head': ('revisions', [binding.REVISION, binding.REVISION])}[change]
        value['identity'][field] = content
    with pytest.raises(AssertionError):
        binding.child_binding(raw, value, SCHEMA, env, component=component)


@pytest.mark.parametrize('component', COMPONENTS)
@pytest.mark.parametrize('field,value', [('database', 'other'), ('oid', 0), ('oid', True),
    ('role', 'other'), ('session_role', 'other'), ('pg_version', 180000), ('server_port', True),
    ('schema', 'public'), ('revisions', []), ('revisions', ['0011_return_execution']),
    ('revisions', ['0012_label_execution'])])
def test_parent_rejects_wrong_observed_identity(component, field, value):
    raw, url, identity, env = fixture(component)
    identity[field] = value
    with pytest.raises(AssertionError):
        binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)


@pytest.mark.parametrize('component,database', [(c, n) for c, n in PROFILES if n is not None])
@pytest.mark.parametrize('change', ['name', 'oid', 'missing', 'higher-priority'])
def test_original_legacy_env_priority_and_identity_remain_required(component, database, change):
    raw, url, identity, env = fixture(component, database)
    prefix = next(key.removesuffix('_DATABASE_NAME') for key in env if key.endswith('_DATABASE_NAME'))
    if change == 'name': env[prefix + '_DATABASE_NAME'] = 'wrong'
    elif change == 'oid': env[prefix + '_DATABASE_OID'] = '16385'
    elif change == 'missing': del env[prefix + '_DATABASE_OID']
    else:
        # ARTIFACT presence takes precedence even if its value is empty/wrong.
        env['ARTIFACT_DATABASE_NAME'] = ''
        env['ARTIFACT_DATABASE_OID'] = '16384'
    with pytest.raises(AssertionError):
        binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)


@pytest.mark.parametrize('component,prefix', [('label', 'ARTIFACT'), ('label', 'LABEL'),
    ('bridge', 'ARTIFACT'), ('bridge', 'LABEL'), ('bridge', 'BRIDGE')])
@pytest.mark.parametrize('suffix', ['_DATABASE_NAME', '_DATABASE_OID'])
def test_ci_rejects_legacy_override_presence(component, prefix, suffix):
    raw, url, identity, env = fixture(component)
    env[prefix + suffix] = ''
    with pytest.raises(AssertionError):
        binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)


def extracted(path, name, namespace, *, nested=False):
    parsed = ast.parse(path.read_bytes())
    body = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'main').body if nested else parsed.body
    function = next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


@pytest.mark.parametrize('component', COMPONENTS)
@pytest.mark.parametrize('field,value', [('oid', 16385), ('role', 'other'), ('server_port', 5440),
    ('pg_version', 170012), ('schema', 'public'), ('revisions', [])])
def test_real_probe_connect_callback_rechecks_each_connection_and_rolls_back(component, field, value):
    raw, url, identity, env = fixture(component)
    approved = binding.parent_binding(raw, url, SCHEMA, identity, env, component=component)
    observed = deepcopy(identity)
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql):
            self.revisions = 'version_num' in sql
            return self
        def fetchone(self): return tuple(observed[key] for key in binding.IDENTITY_KEYS)
        def fetchall(self): return [(r,) for r in observed['revisions']]
    class Connection:
        rollbacks = 0
        def cursor(self): return Cursor()
        def rollback(self): self.rollbacks += 1
    callback = extracted(LIFECYCLE / FILES[component][0], 'exact_database',
        dict(database_binding=binding, binding=approved, config={'schema': SCHEMA}), nested=True)
    first = Connection(); callback(first, None); assert first.rollbacks == 1
    observed[field] = value
    second = Connection()
    with pytest.raises(AssertionError): callback(second, None)
    assert second.rollbacks == 1


@pytest.mark.parametrize('component', COMPONENTS)
@pytest.mark.parametrize('pipe_failure', [False, True])
def test_actual_launch_owns_child_before_private_stdin_and_preserves_failures(component, pipe_failure, tmp_path, monkeypatch):
    raw, url, identity, env = fixture(component)
    monkeypatch.setenv('DATABASE_URL', raw)
    for key in ('ARTIFACT_DATABASE_NAME', 'ARTIFACT_DATABASE_OID', 'LABEL_DATABASE_NAME',
                'LABEL_DATABASE_OID', 'BRIDGE_DATABASE_NAME', 'BRIDGE_DATABASE_OID'):
        monkeypatch.delenv(key, raising=False)
    children, captured, stops = [], [], []
    class Result:
        def fetchone(self): return tuple(identity[k] for k in binding.IDENTITY_KEYS)
        def fetchall(self): return [(binding.REVISION,)]
    class Engine:
        _customer_test_schema = SCHEMA
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def connect(self): return self
        def exec_driver_sql(self, sql): return Result()
    engine = Engine(); engine.url = url
    class Pipe:
        def write(self, data):
            assert len(children) == 1 and children[0]['process'] is process
            captured.append(json.loads(data))
            if pipe_failure: raise OSError('controlled private pipe failure')
        def close(self): captured.append('closed')
    process = SimpleNamespace(stdin=Pipe(), poll=lambda: None, pid=40001)
    def popen(command, **kwargs):
        assert kwargs['stdin'] == subprocess.PIPE
        assert command[-1] == str(tmp_path / 'installed') and len(command) == 7
        return process
    class Preserved(BaseException): pass
    def preserve_stop(request, owned, reason):
        stops.append([child['process'].pid for child in owned])
        raise Preserved()
    namespace = dict(__file__=str(LIFECYCLE / FILES[component][1]), Path=Path,
        os=os, json=json, sys=sys, database_binding=binding,
        subprocess=SimpleNamespace(Popen=popen, PIPE=subprocess.PIPE))
    launch = extracted(LIFECYCLE / FILES[component][1], 'launch', namespace)
    guard = extracted(LIFECYCLE / FILES['bridge'][1], 'preserve_running_on_failure',
                      dict(contextmanager=contextmanager, stop_preserving_children=preserve_stop))
    identities = SimpleNamespace(auth_config=SimpleNamespace(issuer='synthetic', audience='synthetic',
        signing_key=b'private-key'), tokens={'founder': 'private-token'})
    def invoke():
        with guard(None, children):
            return launch(engine, identities, {}, tmp_path / 'installed', tmp_path, 0, children)
    if pipe_failure:
        with pytest.raises(Preserved): invoke()
        assert stops == [[40001]] and process.poll() is None
    else:
        assert invoke() is children[0] and captured[-1] == 'closed' and not stops
    assert captured[0]['database_binding']['component'] == component
    assert captured[0]['token'] == 'private-token'
    assert not list(tmp_path.glob('*config*'))
    assert all(path.read_bytes() == b'' for path in tmp_path.glob('*.bin'))


def test_bridge_returned_source_hashes_are_checked():
    verify = extracted(LIFECYCLE / FILES['bridge'][1], 'verify_child_sources', {})
    hashes = {'packages/returnops_domain/return_label_bridge.py': 'a' * 64}
    verify({'installed_hashes': {'returnops_domain.return_label_bridge': 'a' * 64}}, hashes)
    with pytest.raises(AssertionError):
        verify({'installed_hashes': {'returnops_domain.return_label_bridge': 'b' * 64}}, hashes)


def test_artifact_contract_and_component_isolation():
    raw, url, identity, env = fixture('label')
    artifact = binding.parent_binding(raw, url, SCHEMA, identity, env)
    assert set(artifact) == binding.BINDING_KEYS
    with pytest.raises(AssertionError): binding.child_binding(raw, artifact, SCHEMA, env, component='label')
    label = binding.parent_binding(raw, url, SCHEMA, identity, env, component='label')
    with pytest.raises(AssertionError): binding.child_binding(raw, label, SCHEMA, env)
    with pytest.raises(AssertionError): binding.target_url(raw, component='unknown')
    bridge = fixture('bridge', binding.BRIDGE_NAME)[0]
    with pytest.raises(AssertionError): binding.target_url(bridge, component='label')
