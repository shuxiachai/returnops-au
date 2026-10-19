"""Test-only parent/child DB identity binding; never creates an engine.

Issue81/KAN-15, A2.03/A2.04; FR-009/010, NFR-002/004/006/008;
UC-04 and the governed-execution sequence/OperationAttempt state model.
The private stdin transport is trusted test orchestration, not a signature.
"""
from hashlib import sha256
import re

from sqlalchemy.engine import make_url


LEGACY_NAMES = frozenset((
    'returnops_f02_a203_artifact_20261016',
    'returnops_f02_a203_artifact_v02_20261016',
    'returnops_f02_a203_artifact_v04_20261018',
))
REVISION = '0013_label_artifact_result'
IDENTITY_SQL = (
    "SELECT current_database(), oid, current_user, session_user, inet_server_port(), "
    "current_setting('server_version_num')::integer, current_schema() "
    'FROM pg_database WHERE datname=current_database()'
)
IDENTITY_KEYS = ('database', 'oid', 'role', 'session_role', 'server_port', 'pg_version', 'schema')
BINDING_KEYS = {'format', 'profile', 'url_sha256', 'schema', 'identity'}


def validate_schema(schema):
    assert type(schema) is str and re.fullmatch(r'customer_test_[a-f0-9]{32}', schema)


def target_url(raw):
    """Only the known CI target and the original three legacy targets exist."""
    assert type(raw) is str and raw and not any(c in raw for c in '?\r\n\t#')
    try:
        url = make_url(raw)
        assert url.drivername == 'postgresql+psycopg' and not url.query
        assert type(url.username) is str and url.username
        if (url.host, url.port, url.database) == ('localhost', 5432, 'returnops_f02_ci'):
            assert url.username == 'returnops_ci'
        else:
            assert url.host == '127.0.0.1' and url.port == 55433 and url.database in LEGACY_NAMES
    except Exception:
        raise AssertionError('Unapproved probe database target') from None
    return url


def observe(execute, schema):
    """Read identity and this exact fixture schema's revision; acquire no fence."""
    validate_schema(schema)
    row = execute(IDENTITY_SQL).fetchone()
    assert row is not None and len(row) == len(IDENTITY_KEYS)
    identity = dict(zip(IDENTITY_KEYS, row))
    identity['revisions'] = [item[0] for item in execute(
        'SELECT version_num FROM ' + schema + '.alembic_version ORDER BY version_num'
    ).fetchall()]
    return identity


def _validate_identity(url, schema, identity):
    validate_schema(schema)
    assert type(identity) is dict and set(identity) == {*IDENTITY_KEYS, 'revisions'}
    assert identity['database'] == url.database
    assert type(identity['oid']) is int and identity['oid'] > 0
    assert identity['role'] == identity['session_role'] == url.username
    assert type(identity['server_port']) is int and 1 <= identity['server_port'] <= 65535
    # The older local harness did not pin its internal server port or role.
    # Keep that scope while binding both actual values to the parent observation.
    if url.database in ('returnops_f02_ci', 'returnops_f02_a203_artifact_v04_20261018'):
        assert identity['server_port'] == 5432
    assert type(identity['pg_version']) is int and identity['pg_version'] == 170011
    assert identity['schema'] == schema
    assert type(identity['revisions']) is list and identity['revisions'] == [REVISION]


def _environment(url, identity, environment):
    keys = ('ARTIFACT_DATABASE_NAME', 'ARTIFACT_DATABASE_OID')
    if url.database == 'returnops_f02_ci':
        assert all(key not in environment for key in keys)
    else:
        assert environment.get(keys[0]) == url.database
        raw_oid = environment.get(keys[1])
        assert type(raw_oid) is str and re.fullmatch(r'[0-9]{1,10}', raw_oid)
        assert int(raw_oid) == identity['oid']


def _fingerprint(url):
    # This includes credentials but the digest stays in the private config pipe.
    return sha256(url.render_as_string(hide_password=False).encode('utf8')).hexdigest()


def parent_binding(raw, engine_url, schema, identity, environment):
    url = target_url(raw)
    assert url == engine_url
    _validate_identity(url, schema, identity)
    _environment(url, identity, environment)
    return dict(format=1, profile='ci' if url.database == 'returnops_f02_ci' else 'legacy',
                url_sha256=_fingerprint(url), schema=schema, identity=identity)


def child_binding(raw, binding, schema, environment):
    url = target_url(raw)
    assert type(binding) is dict and set(binding) == BINDING_KEYS
    assert type(binding['format']) is int and binding['format'] == 1
    assert binding['profile'] == ('ci' if url.database == 'returnops_f02_ci' else 'legacy')
    assert binding['schema'] == schema
    assert type(binding['url_sha256']) is str and binding['url_sha256'] == _fingerprint(url)
    _validate_identity(url, schema, binding['identity'])
    _environment(url, binding['identity'], environment)
    return url


def live_identity(binding, identity):
    """A child connection must reproduce the already-validated parent identity."""
    assert type(identity) is dict and set(identity) == {*IDENTITY_KEYS, 'revisions'}
    # Exact types matter: True must not compare equal to an integer OID/port.
    assert all(type(identity[key]) is type(value) for key, value in binding['identity'].items())
    assert identity == binding['identity']
