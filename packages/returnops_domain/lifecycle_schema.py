"""Versioned schema checks; 0007's dynamically imported metadata stays frozen.

Runtime only inspects. The explicit 0008 migration owns its ALTER; no grant,
backfill, implicit upgrade, or current DDL mutation happens here.
"""
from sqlalchemy import text
from . import customer_tables, investigation_tables, founder_tables, lifecycle_tables, storage, scope_audit

LEGACY = '0007_lifecycle_guards'
CURRENT = '0008_review_escalation'
OLD_PURPOSES = ('PROPOSAL', 'REVISION', 'OUTCOME', 'NOTIFICATION', 'EFFECT')
CURRENT_PURPOSES = OLD_PURPOSES + ('REVIEW',)


def _expected(purposes):
    # Exact PostgreSQL17 deparse of this version's frozen DDL. Never normalize
    # literals, casts, operators or logical grouping into an apparent match.
    values=', '.join("'"+p+"'::character varying" for p in purposes)
    states=', '.join("'"+p+"'::character varying" for p in ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED'))
    return ("(((purpose)::text = ANY ((ARRAY["+values+"])::text[])) AND "
        "((state)::text = ANY ((ARRAY["+states+"])::text[])) AND (epoch >= 0))")


def version(connection):
    revisions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if len(revisions) != 1 or revisions[0] not in {LEGACY, CURRENT}:
        return None
    names = set(connection.execute(text('SELECT tablename FROM pg_tables WHERE schemaname=current_schema()')).scalars())
    expected = {'alembic_version'}
    for metadata in (storage.metadata, scope_audit.metadata, customer_tables.metadata,
                     investigation_tables.metadata, founder_tables.metadata, lifecycle_tables.metadata):
        expected.update(metadata.tables)
    if names != expected:
        return None
    rows = connection.execute(text("""SELECT pg_get_expr(c.conbin,c.conrelid) AS expression,
        c.convalidated FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_work'
          AND c.conname='ck_lifecycle_work' AND c.contype='c'""")).mappings().all()
    purposes = OLD_PURPOSES if revisions[0] == LEGACY else CURRENT_PURPOSES
    if len(rows) != 1 or not rows[0]['convalidated'] or rows[0]['expression'] != _expected(purposes):
        return None
    return revisions[0]
