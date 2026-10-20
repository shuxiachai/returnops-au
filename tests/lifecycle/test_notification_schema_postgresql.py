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
