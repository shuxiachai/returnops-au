"""Cloud-only 0013→0014 catalog and migration checks (AC13 subset).

The shared fixture requires a disposable PG17 database and isolates each test in
its own schema. These cases do not establish legacy delivery or HOLD behavior.
"""
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text

from conftest import migrate
from label_artifact_helpers import ready, service, complete, snapshot
from returnops_domain.lifecycle_schema import ARTIFACT, NOTIFICATION, version
from returnops_domain.notification_schema import descriptor
from returnops_domain.notification_tables import metadata


def _old_catalog(connection, names):
    """Capture physical definitions and privileges, excluding the revision row."""
    return connection.execute(text("""
        SELECT c.relname, c.relkind, c.relpersistence, c.relowner, c.relacl::text,
          c.relrowsecurity, c.relforcerowsecurity, c.reloptions::text,
          (SELECT jsonb_agg(jsonb_build_array(a.attnum, a.attname,
             format_type(a.atttypid,a.atttypmod), a.attnotnull, a.attidentity,
             a.attgenerated, a.attacl::text, pg_get_expr(d.adbin,d.adrelid)) ORDER BY a.attnum)
           FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
           WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
          (SELECT jsonb_agg(jsonb_build_array(k.conname,k.contype,pg_get_constraintdef(k.oid),
             k.convalidated,k.condeferrable,k.condeferred) ORDER BY k.conname)
           FROM pg_constraint k WHERE k.conrelid=c.oid) AS constraints,
          (SELECT jsonb_agg(pg_get_indexdef(i.indexrelid) ORDER BY i.indexrelid::regclass::text)
           FROM pg_index i WHERE i.indrelid=c.oid) AS indexes
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=current_schema() AND c.relname = ANY(:names)
        ORDER BY c.relname
    """), {'names': list(names)}).mappings().all()


@pytest.mark.parametrize('flow_engine', [ARTIFACT], indirect=True)
def test_0013_upgrade_preserves_existing_catalog_and_rows(flow_engine, identities, enabled):
    args, _ = ready(flow_engine, identities)
    assert complete(service(flow_engine, identities), args).status == 'COMMITTED'
    before = snapshot(flow_engine)
    with flow_engine.connect() as connection:
        assert version(connection) == ARTIFACT
        old_catalog = _old_catalog(connection, before)
    migrate(flow_engine, NOTIFICATION)
    after = snapshot(flow_engine)
    assert set(after) - set(before) == set(metadata.tables)
    assert all(after[name] == [] for name in metadata.tables)
    assert {name: rows for name, rows in before.items() if name != 'alembic_version'} == {
        name: rows for name, rows in after.items()
        if name not in set(metadata.tables) | {'alembic_version'}
    }
    with flow_engine.connect() as connection:
        assert version(connection) == NOTIFICATION
        assert descriptor(connection)
        assert _old_catalog(connection, before) == old_catalog


@pytest.mark.parametrize('fault', ['missing_check', 'nullable', 'default', 'extra_index',
                                   'extra_table_grant', 'column_grant'])
def test_0014_descriptor_rejects_catalog_counterfeits(flow_engine, fault):
    sql = {
        'missing_check': 'ALTER TABLE core_mock_notification_facts DROP CONSTRAINT ck_notification_fact_status',
        'nullable': 'ALTER TABLE notification_delivery_controls ALTER COLUMN intent_core DROP NOT NULL',
        'default': 'ALTER TABLE notification_delivery_controls ALTER COLUMN attempt_count SET DEFAULT 0',
        'extra_index': 'CREATE INDEX counterfeit_notification_index ON core_mock_notification_facts (status)',
        'extra_table_grant': 'GRANT SELECT ON core_mock_notification_facts TO PUBLIC',
        'column_grant': 'GRANT SELECT (status) ON core_mock_notification_facts TO PUBLIC',
    }[fault]
    with flow_engine.begin() as connection:
        assert version(connection) == NOTIFICATION and descriptor(connection)
        connection.execute(text(sql))
        assert descriptor(connection) is False
        assert version(connection) is None


def test_0014_descriptor_rejects_different_owner(flow_engine):
    # Role exists only in the disposable cloud database cluster and is removed
    # after the transactional owner change is rolled back.
    role = 'notification_test_' + uuid4().hex
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        current = connection.execute(text('SELECT current_user')).scalar_one()
        connection.rollback()
        try:
            with connection.begin():
                connection.execute(text('CREATE ROLE ' + quote(role) + ' NOLOGIN'))
                connection.execute(text('GRANT ' + quote(role) + ' TO ' + quote(current)))
            transaction = connection.begin()
            try:
                assert descriptor(connection)
                connection.execute(text('ALTER TABLE core_mock_notification_facts OWNER TO ' + quote(role)))
                assert descriptor(connection) is False
                assert version(connection) is None
            finally:
                transaction.rollback()
        finally:
            with connection.begin():
                connection.execute(text('DROP ROLE IF EXISTS ' + quote(role)))


@pytest.mark.parametrize('flow_engine', [ARTIFACT], indirect=True)
def test_0014_inherited_schema_default_grant_rolls_back_migration(flow_engine):
    schema = flow_engine._customer_test_schema
    with flow_engine.begin() as connection:
        quote = connection.dialect.identifier_preparer.quote
        connection.execute(text('ALTER DEFAULT PRIVILEGES IN SCHEMA ' + quote(schema)
                                + ' GRANT SELECT ON TABLES TO PUBLIC'))
        assert version(connection) == ARTIFACT
    before = snapshot(flow_engine)
    with pytest.raises(RuntimeError, match='Notification catalog does not match exact0014 descriptor'):
        migrate(flow_engine, NOTIFICATION)
    assert snapshot(flow_engine) == before
    assert not set(metadata.tables) & set(inspect(flow_engine).get_table_names())
    with flow_engine.connect() as connection:
        assert version(connection) == ARTIFACT


# C12 cloud-only additions for artifact prerequisites and notification catalog batching.
def _c12_pg_descriptor(kind):
    from returnops_domain import label_artifact_schema, notification_schema
    return {'artifact': label_artifact_schema.descriptor, 'notification': notification_schema.descriptor}[kind]


class _C12NotificationCatalogConnection:
    def __init__(self, connection, *, fail_step=None):
        self.connection = connection
        self.calls = []
        self.fail_step = fail_step
        self.errors = []

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, statement, parameters=None):
        sql = str(statement)
        if 'SELECT jsonb_build_object(' in sql:
            step = 'structural'
        elif 'relation.relowner AS table_owner' in sql:
            step = 'ownership'
        else:
            assert "r.relname='customer_evidence'" in sql
            step = 'namespace'
        self.calls.append((step, sql, dict(parameters or {})))
        if self.fail_step == step:
            try:
                return self.connection.execute(text('SELECT 1 / 0'))
            except Exception as error:
                self.errors.append(error)
                raise
        return self.connection.execute(statement, parameters) if parameters else self.connection.execute(statement)


@pytest.mark.parametrize('flow_engine,kind,expected_revision', [
    ('0013_label_artifact_result', 'artifact', '0013_label_artifact_result'),
    ('0014_notification_delivery', 'artifact', '0014_notification_delivery'),
    ('0014_notification_delivery', 'notification', '0014_notification_delivery'),
], indirect=['flow_engine'])
def test_C12_artifact_and_notification_supported_versions_keep_two_ordered_queries(flow_engine, kind, expected_revision):
    with flow_engine.connect() as connection:
        assert version(connection) == expected_revision
        observed = _C12NotificationCatalogConnection(connection)
        assert _c12_pg_descriptor(kind)(observed) is True
        expected_steps = ['structural', 'namespace'] if kind == 'artifact' else ['ownership', 'structural']
        assert [c[0] for c in observed.calls] == expected_steps
        _, sql, parameters = next(c for c in observed.calls if c[0] == 'structural')
        expected = (dict(permission_name='label_artifact_permissions', control_name='lifecycle_label_artifact_controls',
                         claim_name='lifecycle_label_artifact_claims', artifact_name='generated_label_artifacts',
                         content_name='generated_label_artifact_contents') if kind == 'artifact' else
                    dict(control_name='notification_delivery_controls', fact_name='core_mock_notification_facts'))
        assert parameters == expected
        assert 'n.nspname=current_schema()' in sql and "'table_name', r.relname" in sql


@pytest.mark.parametrize('kind,table_name', [
    ('artifact', 'label_artifact_permissions'), ('artifact', 'lifecycle_label_artifact_controls'),
    ('artifact', 'lifecycle_label_artifact_claims'), ('artifact', 'generated_label_artifacts'),
    ('artifact', 'generated_label_artifact_contents'), ('notification', 'notification_delivery_controls'),
    ('notification', 'core_mock_notification_facts'),
])
def test_C12_artifact_and_notification_reread_each_table_after_ddl_and_rollback(flow_engine, kind, table_name):
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        transaction = connection.begin()
        observed = _C12NotificationCatalogConnection(connection)
        check = _c12_pg_descriptor(kind)
        try:
            assert version(connection) == NOTIFICATION
            assert check(observed) is True
            connection.execute(text('ALTER TABLE ' + quote(table_name) + ' ADD COLUMN c12_unexpected integer'))
            assert check(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert check(observed) is True and version(connection) == NOTIFICATION
        expected = (['structural', 'namespace', 'structural', 'structural', 'namespace'] if kind == 'artifact'
                    else ['ownership', 'structural'] * 3)
        assert [c[0] for c in observed.calls] == expected


@pytest.mark.parametrize('kind,table_name', [
    ('artifact', 'label_artifact_permissions'), ('artifact', 'lifecycle_label_artifact_controls'),
    ('artifact', 'lifecycle_label_artifact_claims'), ('artifact', 'generated_label_artifacts'),
    ('artifact', 'generated_label_artifact_contents'), ('notification', 'notification_delivery_controls'),
    ('notification', 'core_mock_notification_facts'),
])
def test_C12_artifact_and_notification_do_not_borrow_same_named_foreign_schema_tables(flow_engine, kind, table_name):
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        current_schema = quote(flow_engine._customer_test_schema)
        shadow = quote('c12_shadow_' + uuid4().hex)
        transaction = connection.begin()
        check = _c12_pg_descriptor(kind)
        observed = _C12NotificationCatalogConnection(connection)
        try:
            assert check(observed) is True
            connection.execute(text('CREATE SCHEMA ' + shadow))
            connection.execute(text('CREATE TABLE ' + shadow + '.' + quote(table_name) +
                                    ' (LIKE ' + current_schema + '.' + quote(table_name) + ' INCLUDING ALL)'))
            connection.execute(text('SET LOCAL search_path TO ' + current_schema + ', ' + shadow))
            connection.execute(text('ALTER TABLE ' + current_schema + '.' + quote(table_name) +
                                    ' RENAME TO c12_displaced_relation'))
            assert check(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert check(observed) is True
        expected = (['structural', 'namespace', 'structural', 'structural', 'namespace'] if kind == 'artifact'
                    else ['ownership', 'structural', 'ownership', 'ownership', 'structural'])
        assert [c[0] for c in observed.calls] == expected


def test_C12_artifact_still_rechecks_namespace_after_all_structural_tables(flow_engine):
    from returnops_domain.label_artifact_tables import NAMESPACE_CHECK
    with flow_engine.connect() as connection:
        transaction = connection.begin()
        quote = connection.dialect.identifier_preparer.quote
        observed = _C12NotificationCatalogConnection(connection)
        check = _c12_pg_descriptor('artifact')
        try:
            assert check(observed) is True
            connection.execute(text('ALTER TABLE customer_evidence DROP CONSTRAINT ' + quote(NAMESPACE_CHECK)))
            assert check(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert check(observed) is True
        assert [c[0] for c in observed.calls] == ['structural', 'namespace'] * 3


@pytest.mark.parametrize('grant', ['GRANT SELECT ON core_mock_notification_facts TO PUBLIC',
                                  'GRANT SELECT (status) ON core_mock_notification_facts TO PUBLIC'])
def test_C12_notification_original_acl_check_precedes_any_structural_batch(flow_engine, grant):
    with flow_engine.connect() as connection:
        transaction = connection.begin()
        observed = _C12NotificationCatalogConnection(connection)
        try:
            assert descriptor(observed) is True
            connection.execute(text(grant))
            assert descriptor(observed) is False and version(connection) is None
        finally:
            transaction.rollback()
        assert descriptor(observed) is True
        assert [c[0] for c in observed.calls] == ['ownership', 'structural', 'ownership', 'ownership', 'structural']


@pytest.mark.parametrize('kind,step', [('artifact', 'structural'), ('artifact', 'namespace'),
                                      ('notification', 'ownership'), ('notification', 'structural')])
def test_C12_artifact_and_notification_propagate_real_driver_errors_without_retry(flow_engine, kind, step):
    from sqlalchemy.exc import DBAPIError
    before = snapshot(flow_engine)
    with flow_engine.connect() as connection:
        transaction = connection.begin()
        observed = _C12NotificationCatalogConnection(connection, fail_step=step)
        check = _c12_pg_descriptor(kind)
        try:
            with pytest.raises(DBAPIError) as caught:
                check(observed)
            assert len(observed.errors) == 1 and caught.value is observed.errors[0]
            assert getattr(caught.value.orig, 'sqlstate', None) == '22012'
            expected = ['structural', 'namespace'] if kind == 'artifact' else ['ownership', 'structural']
            assert [c[0] for c in observed.calls] == expected[:expected.index(step) + 1]
        finally:
            transaction.rollback()
        observed.fail_step = None
        observed.calls.clear()
        assert check(observed) is True
        assert [c[0] for c in observed.calls] == expected
    assert snapshot(flow_engine) == before
