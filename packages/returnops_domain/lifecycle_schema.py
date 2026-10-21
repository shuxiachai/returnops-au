"""Versioned schema checks; 0007's dynamically imported metadata stays frozen.

Runtime only inspects. The explicit 0008 migration owns its ALTER; no grant,
backfill, implicit upgrade, or current DDL mutation happens here.
"""
from sqlalchemy import text, String, BigInteger, DateTime, LargeBinary, Boolean
from . import customer_tables, investigation_tables, founder_tables, lifecycle_tables, storage, scope_audit

LEGACY = '0007_lifecycle_guards'
REVIEW = '0008_review_escalation'
APPROVAL = '0009_preview_approval'
PREPARATION = '0010_execution_preparation'
EXECUTION = '0011_return_execution'
LABEL = '0012_label_execution'
ARTIFACT = '0013_label_artifact_result'
NOTIFICATION = '0014_notification_delivery'
CURRENT = NOTIFICATION
ARTIFACT_VERSIONS = frozenset({ARTIFACT, NOTIFICATION})
LABEL_VERSIONS = frozenset({LABEL, *ARTIFACT_VERSIONS})
EXECUTION_VERSIONS = frozenset({EXECUTION, *LABEL_VERSIONS})
PREPARATION_VERSIONS = frozenset({PREPARATION, *EXECUTION_VERSIONS})
APPROVAL_VERSIONS = frozenset({APPROVAL, *PREPARATION_VERSIONS})
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
    if len(revisions) != 1 or revisions[0] not in {LEGACY, REVIEW, *APPROVAL_VERSIONS}:
        return None
    names = set(connection.execute(text('SELECT tablename FROM pg_tables WHERE schemaname=current_schema()')).scalars())
    expected = {'alembic_version'}
    for metadata in (storage.metadata, scope_audit.metadata, customer_tables.metadata,
                     investigation_tables.metadata, founder_tables.metadata, lifecycle_tables.metadata):
        expected.update(metadata.tables)
    if revisions[0] in APPROVAL_VERSIONS:
        from .preview_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] in PREPARATION_VERSIONS:
        from .execution_preparation_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] in EXECUTION_VERSIONS:
        from .return_execution_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] in LABEL_VERSIONS:
        from .label_execution_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] in ARTIFACT_VERSIONS:
        from .label_artifact_tables import metadata
        expected.update(metadata.tables)
    if revisions[0] == NOTIFICATION:
        from .notification_tables import metadata
        expected.update(metadata.tables)
    if names != expected:
        return None
    rows = connection.execute(text("""SELECT pg_get_expr(c.conbin,c.conrelid) AS expression,
        c.convalidated FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='lifecycle_work'
          AND c.conname='ck_lifecycle_work' AND c.contype='c'""")).mappings().all()
    purposes = {LEGACY:OLD_PURPOSES, REVIEW:REVIEW_PURPOSES,
                **{revision:CURRENT_PURPOSES for revision in APPROVAL_VERSIONS}}[revisions[0]]
    if len(rows) != 1 or not rows[0]['convalidated'] or rows[0]['expression'] != _expected(purposes):
        return None
    if revisions[0] in APPROVAL_VERSIONS and not _preview_descriptor(connection):
        return None
    if revisions[0] in PREPARATION_VERSIONS:
        from .execution_preparation_schema import descriptor
        if not descriptor(connection):
            return None
    if revisions[0] in EXECUTION_VERSIONS:
        from .return_execution_schema import descriptor
        if not descriptor(connection):
            return None
    if revisions[0] in LABEL_VERSIONS:
        from .label_execution_schema import descriptor
        if not descriptor(connection):
            return None
    if revisions[0] in ARTIFACT_VERSIONS:
        from .label_artifact_schema import descriptor
        if not descriptor(connection):
            return None
    if revisions[0] == NOTIFICATION:
        from .notification_schema import descriptor
        if not descriptor(connection):
            return None
    return revisions[0]


# One fresh snapshot of every physical fact the preview checks need. It replaces
# the former eleven reflection/text round trips per call; nothing is cached
# across calls. 'type_shadow' mirrors SQLAlchemy 2.0.52 reflection, which lets a
# visible domain/enum named like one of these builtins stand in for the builtin
# and so rejects the table. Every aggregate is COALESCEd so an empty set is [].
PREVIEW_CATALOG = text("""SELECT jsonb_build_object(
  'schema', current_schema(),
  'visible', pg_catalog.pg_table_is_visible(r.oid),
  'type_shadow', EXISTS (SELECT 1 FROM pg_type y WHERE y.typtype IN ('d', 'e')
      AND y.typname IN ('character varying', 'bigint', 'boolean', 'bytea') AND pg_catalog.pg_type_is_visible(y.oid)),
  'columns', COALESCE((SELECT jsonb_agg(jsonb_build_array(a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
      CASE WHEN a.atthasdef AND a.attgenerated = '' THEN pg_get_expr(d.adbin, d.adrelid) END,
      CASE WHEN a.attcollation <> 0 AND a.attcollation <> t.typcollation THEN co.collname END) ORDER BY a.attnum)
      FROM pg_attribute a JOIN pg_type t ON t.oid = a.atttypid
      LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      LEFT JOIN pg_collation co ON co.oid = a.attcollation
      WHERE a.attrelid = r.oid AND a.attnum > 0 AND NOT a.attisdropped), '[]'::jsonb),
  'keys', COALESCE((SELECT jsonb_agg(jsonb_build_array(c.conname, c.contype,
      (SELECT COALESCE(jsonb_agg(ka.attname ORDER BY k.ord), '[]'::jsonb)
         FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
         JOIN pg_attribute ka ON ka.attrelid = r.oid AND ka.attnum = k.attnum
        WHERE k.ord <= i.indnkeyatts)) ORDER BY c.conname)
      FROM pg_constraint c JOIN pg_index i ON i.indexrelid = c.conindid
      WHERE c.conrelid = r.oid AND c.contype IN ('p', 'u')), '[]'::jsonb),
  'foreign', COALESCE((SELECT jsonb_agg(jsonb_build_array(c.conname,
      (SELECT COALESCE(jsonb_agg(fa.attname ORDER BY f.ord), '[]'::jsonb)
         FROM unnest(c.conkey) WITH ORDINALITY AS f(attnum, ord)
         JOIN pg_attribute fa ON fa.attrelid = c.conrelid AND fa.attnum = f.attnum),
      rn.nspname, rr.relname,
      (SELECT COALESCE(jsonb_agg(ta.attname ORDER BY g.ord), '[]'::jsonb)
         FROM unnest(c.confkey) WITH ORDINALITY AS g(attnum, ord)
         JOIN pg_attribute ta ON ta.attrelid = c.confrelid AND ta.attnum = g.attnum),
      c.confupdtype, c.confdeltype, c.confmatchtype, c.condeferrable, c.condeferred) ORDER BY c.conname)
      FROM pg_constraint c JOIN pg_class rr ON rr.oid = c.confrelid
      JOIN pg_namespace rn ON rn.oid = rr.relnamespace
      WHERE c.conrelid = r.oid AND c.contype = 'f'), '[]'::jsonb),
  'constraints', COALESCE((SELECT jsonb_agg(jsonb_build_array(c.conname, c.convalidated, c.condeferrable, c.condeferred))
      FROM pg_constraint c WHERE c.conrelid = r.oid), '[]'::jsonb),
  'unique_indexes', COALESCE((SELECT jsonb_agg(jsonb_build_array(ix.relname, i.indisvalid, i.indisready,
      i.indimmediate, i.indnullsnotdistinct))
      FROM pg_index i JOIN pg_class ix ON ix.oid = i.indexrelid WHERE i.indrelid = r.oid AND i.indisunique), '[]'::jsonb),
  'checks', COALESCE((SELECT jsonb_agg(jsonb_build_array(c.conname, pg_get_expr(c.conbin, c.conrelid), c.convalidated))
      FROM pg_constraint c WHERE c.conrelid = r.oid AND c.contype = 'c'), '[]'::jsonb))
FROM pg_class r JOIN pg_namespace n ON n.oid = r.relnamespace
WHERE n.nspname = current_schema() AND r.relname = 'lifecycle_action_previews'""")


def _preview_format(column):
    """PostgreSQL format_type() text of a frozen preview column, or None if unmapped."""
    kind = type(column.type)
    if kind is String:
        return f'character varying({column.type.length})'
    if kind is BigInteger:
        return 'bigint'
    if kind is DateTime and column.type.timezone:
        return 'timestamp with time zone'
    if kind is LargeBinary:
        return 'bytea'
    if kind is Boolean:
        return 'boolean'
    return None


def _preview_descriptor(connection):
    """Exact new table columns, keys, FK targets and validated CHECK expressions.

    Never strip parentheses/casts/literals to make a counterfeit CHECK match.
    Old 0007/0008 remain independent; neither is silently treated as 0009.
    The checks below keep their former order and meaning; they now read one
    PREVIEW_CATALOG snapshot instead of reflecting the table piece by piece.
    """
    from .preview_tables import previews
    rows = connection.execute(PREVIEW_CATALOG).scalars().all()
    if len(rows) != 1 or not isinstance(rows[0], dict):
        return False
    catalog = rows[0]
    # A same-named relation earlier in the search path would be what business SQL
    # reaches; reflection used to inspect that one while the text checks read this
    # one. Refuse the split view outright.
    if not catalog['visible'] or catalog['type_shadow']:
        return False
    expected_columns = []
    for c in previews.columns:
        kind = _preview_format(c)
        if kind is None:
            return False
        expected_columns.append([c.name, kind, not c.nullable, None, None])
    if catalog['columns'] != expected_columns:
        return False
    if [columns for _, contype, columns in catalog['keys'] if contype == 'p'] != [['preview_id']]:
        return False
    uniques = {name: tuple(columns) for name, contype, columns in catalog['keys'] if contype == 'u'}
    if uniques != {'uq_preview_request':('component_id','store_id','case_id','request_key'),
                   'uq_preview_version':('case_id','post_case_version'),
                   'uq_preview_consumer':('consuming_decision_record_id',)}:
        return False
    foreign = catalog['foreign']
    expected = {c.name:(tuple(c.column_keys), tuple(e.column.table.name for e in c.elements),
                       tuple(e.column.name for e in c.elements)) for c in previews.foreign_key_constraints}
    # Reflection reported options only for MATCH FULL/PARTIAL, CASCADE/RESTRICT/SET
    # NULL/SET DEFAULT actions, DEFERRABLE or INITIALLY DEFERRED; these are the
    # catalog codes of the default (option-free) foreign key.
    if ({name:(tuple(columns), (table,), tuple(referred)) for name, columns, _, table, referred, *_ in foreign} != expected
            or any(update != 'a' or delete != 'a' or match != 's' or deferrable or deferred
                   for *_, update, delete, match, deferrable, deferred in foreign)):
        return False
    schema = catalog['schema']
    # version() already proved every expected table exists in current_schema(), so a
    # target that reflection would have left unqualified is exactly one living there.
    if any(namespace != schema for _, _, namespace, *_ in foreign):
        return False
    # SQLAlchemy FK reflection omits convalidated; reflected unique columns
    # alone also omit NULLS NOT DISTINCT semantics. Check physical properties.
    constraints = catalog['constraints']
    expected_names = set(expected) | set(uniques) | {'lifecycle_action_previews_pkey'} | {
        'ck_preview_transition','ck_preview_body','ck_preview_consumed','ck_preview_expiry',
        *('ck_preview_' + name for name in
          ('input_version','generation','authority_revision','pre_case_version','post_case_version'))}
    if (len(constraints) != len(expected_names) or {name for name, *_ in constraints} != expected_names
            or any(not validated or deferrable or deferred for _, validated, deferrable, deferred in constraints)):
        return False
    indexes = catalog['unique_indexes']
    if ({name for name, *_ in indexes} != set(uniques) | {'lifecycle_action_previews_pkey'}
            or any(not valid or not ready or not immediate or nulls_not_distinct
                   for _, valid, ready, immediate, nulls_not_distinct in indexes)):
        return False
    checks = {
        'ck_preview_transition':'(post_case_version = (pre_case_version + 1))',
        'ck_preview_body':'(available = (body IS NOT NULL))',
        'ck_preview_consumed':'((consuming_decision_record_id IS NULL) = (consumed_at IS NULL))',
        'ck_preview_expiry':'(expires_at > issued_at)',
    }
    for column in ('input_version','generation','authority_revision','pre_case_version','post_case_version'):
        checks['ck_preview_' + column] = f'(({column} >= 1) AND ({column} <= \'9007199254740991\'::bigint))'
    rows = catalog['checks']
    return {name: expression for name, expression, _ in rows} == checks and all(validated for *_, validated in rows)
