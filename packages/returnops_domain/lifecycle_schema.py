"""Versioned schema checks; 0007's dynamically imported metadata stays frozen.

Runtime only inspects. The explicit 0008 migration owns its ALTER; no grant,
backfill, implicit upgrade, or current DDL mutation happens here.
"""
from sqlalchemy import text, inspect
from . import customer_tables, investigation_tables, founder_tables, lifecycle_tables, storage, scope_audit

LEGACY = '0007_lifecycle_guards'
REVIEW = '0008_review_escalation'
APPROVAL = '0009_preview_approval'
PREPARATION = '0010_execution_preparation'
CURRENT = PREPARATION
APPROVAL_VERSIONS = frozenset({APPROVAL, PREPARATION})
OLD_PURPOSES = ('PROPOSAL', 'REVISION', 'OUTCOME', 'NOTIFICATION', 'EFFECT')
REVIEW_PURPOSES = OLD_PURPOSES + ('REVIEW',)
CURRENT_PURPOSES = REVIEW_PURPOSES + ('APPROVAL', 'EXECUTION')


def _expected(purposes):
    # Exact PostgreSQL17 deparse of this version's frozen DDL. Never normalize
    # literals, casts, operators or logical grouping into an apparent match.
    values=', '.join("'"+p+"'::character varying" for p in purposes)
    states=', '.join("'"+p+"'::character varying" for p in ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED'))
    return ("(((purpose)::text = ANY ((ARRAY["+values+"])::text[])) AND "
        "((state)::text = ANY ((ARRAY["+states+"])::text[])) AND (epoch >= 0))")


def version(connection):
    revisions = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
    if len(revisions) != 1 or revisions[0] not in {LEGACY, REVIEW, APPROVAL, PREPARATION}:
        return None
    names = set(connection.execute(text('SELECT tablename FROM pg_tables WHERE schemaname=current_schema()')).scalars())
    expected = {'alembic_version'}
    for metadata in (storage.metadata, scope_audit.metadata, customer_tables.metadata,
                     investigation_tables.metadata, founder_tables.metadata, lifecycle_tables.metadata):
        expected.update(metadata.tables)
    if revisions[0] in APPROVAL_VERSIONS:
        from .preview_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] == PREPARATION:
        from .execution_preparation_tables import metadata
        expected.update(metadata.tables)
    if names != expected:
        return None
    rows = connection.execute(text("""SELECT pg_get_expr(c.conbin,c.conrelid) AS expression,
        c.convalidated FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_work'
          AND c.conname='ck_lifecycle_work' AND c.contype='c'""")).mappings().all()
    purposes = {LEGACY:OLD_PURPOSES, REVIEW:REVIEW_PURPOSES, APPROVAL:CURRENT_PURPOSES, PREPARATION:CURRENT_PURPOSES}[revisions[0]]
    if len(rows) != 1 or not rows[0]['convalidated'] or rows[0]['expression'] != _expected(purposes):
        return None
    if revisions[0] in APPROVAL_VERSIONS and not _preview_descriptor(connection):
        return None
    if revisions[0] == PREPARATION:
        from .execution_preparation_schema import descriptor
        if not descriptor(connection):
            return None
    return revisions[0]


def _preview_descriptor(connection):
    """Exact new table columns, keys, FK targets and validated CHECK expressions.

    Never strip parentheses/casts/literals to make a counterfeit CHECK match.
    Old 0007/0008 remain independent; neither is silently treated as 0009.
    """
    from .preview_tables import previews
    inspector = inspect(connection)
    actual = inspector.get_columns(previews.name)
    if [(c['name'], str(c['type'].compile(dialect=connection.dialect)), c['nullable'], c.get('default')) for c in actual] != [
            (c.name, str(c.type.compile(dialect=connection.dialect)), c.nullable, None) for c in previews.columns]:
        return False
    if inspector.get_pk_constraint(previews.name)['constrained_columns'] != ['preview_id']:
        return False
    uniques = {c['name']:tuple(c['column_names']) for c in inspector.get_unique_constraints(previews.name)}
    if uniques != {'uq_preview_request':('component_id','store_id','case_id','request_key'),
                   'uq_preview_version':('case_id','post_case_version'),
                   'uq_preview_consumer':('consuming_decision_record_id',)}:
        return False
    foreign = inspector.get_foreign_keys(previews.name)
    expected = {c.name:(tuple(c.column_keys), tuple(e.column.table.name for e in c.elements),
                       tuple(e.column.name for e in c.elements)) for c in previews.foreign_key_constraints}
    if {c['name']:(tuple(c['constrained_columns']), (c['referred_table'],), tuple(c['referred_columns']))
            for c in foreign} != expected or any(c.get('options') for c in foreign):
        return False
    schema = connection.execute(text('SELECT current_schema()')).scalar_one()
    if any(c.get('referred_schema') not in {None, schema} for c in foreign):
        return False
    # SQLAlchemy FK reflection omits convalidated; reflected unique columns
    # alone also omit NULLS NOT DISTINCT semantics. Check physical properties.
    constraints = connection.execute(text("""SELECT c.conname, c.contype, c.convalidated,
        c.condeferrable, c.condeferred FROM pg_constraint c
        JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_action_previews'""")).mappings().all()
    expected_names = set(expected) | set(uniques) | {'lifecycle_action_previews_pkey'} | {
        'ck_preview_transition','ck_preview_body','ck_preview_consumed','ck_preview_expiry',
        *('ck_preview_' + name for name in
          ('input_version','generation','authority_revision','pre_case_version','post_case_version'))}
    if (len(constraints) != len(expected_names) or {c['conname'] for c in constraints} != expected_names
            or any(not c['convalidated'] or c['condeferrable'] or c['condeferred'] for c in constraints)):
        return False
    indexes = connection.execute(text("""SELECT ix.relname AS name, i.indisvalid, i.indisready,
        i.indimmediate, i.indnullsnotdistinct FROM pg_index i
        JOIN pg_class r ON r.oid=i.indrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        JOIN pg_class ix ON ix.oid=i.indexrelid
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_action_previews' AND i.indisunique""")).mappings().all()
    if ({i['name'] for i in indexes} != set(uniques) | {'lifecycle_action_previews_pkey'}
            or any(not i['indisvalid'] or not i['indisready'] or not i['indimmediate']
                   or i['indnullsnotdistinct'] for i in indexes)):
        return False
    checks = {
        'ck_preview_transition':'(post_case_version = (pre_case_version + 1))',
        'ck_preview_body':'(available = (body IS NOT NULL))',
        'ck_preview_consumed':'((consuming_decision_record_id IS NULL) = (consumed_at IS NULL))',
        'ck_preview_expiry':'(expires_at > issued_at)',
    }
    for column in ('input_version','generation','authority_revision','pre_case_version','post_case_version'):
        checks['ck_preview_' + column] = f'(({column} >= 1) AND ({column} <= \'9007199254740991\'::bigint))'
    rows = connection.execute(text("""SELECT c.conname, pg_get_expr(c.conbin,c.conrelid) AS expression,
        c.convalidated FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_action_previews' AND c.contype='c'""")).mappings().all()
    return {r['conname']:r['expression'] for r in rows} == checks and all(r['convalidated'] for r in rows)
