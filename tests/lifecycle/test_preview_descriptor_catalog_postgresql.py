"""PREVIEW_CATALOG decides exactly like the former reflection-based preview check.

legacy_preview_descriptor below is a verbatim copy of the body that
lifecycle_schema._preview_descriptor had at PR head 98d0c47 (eleven reflection
and text round trips per call). Every variant applies DDL on one connection,
runs both implementations under savepoints, asserts the documented pair of
outcomes, rolls back and asserts that both accept the restored schema again.
The new implementation never accepts what the legacy one rejected or failed on.
Traceability: FR-009/FR-010 pre-decision schema guard; NFR-002 fail-closed;
NFR-004/NFR-005 shorter in-transaction checks; M-A exact-scope sequence.
"""
from types import SimpleNamespace
import pytest
from sqlalchemy import inspect, text
from returnops_domain.lifecycle_schema import _preview_descriptor, version, NOTIFICATION
from returnops_domain.preview_tables import previews

TABLE = previews.name


def legacy_preview_descriptor(connection):
    from returnops_domain.preview_tables import previews
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


def _replace_fk(suffix):
    return [f'ALTER TABLE {TABLE} DROP CONSTRAINT fk_preview_case_id',
            f'ALTER TABLE {TABLE} ADD CONSTRAINT fk_preview_case_id FOREIGN KEY (case_id) REFERENCES case_heads(case_id) {suffix}']


def _replace_check(definition):
    return [f'ALTER TABLE {TABLE} DROP CONSTRAINT ck_preview_expiry',
            f'ALTER TABLE {TABLE} ADD CONSTRAINT ck_preview_expiry CHECK {definition}']


FOREIGN_KEYS = tuple(constraint.name for constraint in previews.foreign_key_constraints)
UNIQUES = ('uq_preview_request', 'uq_preview_version', 'uq_preview_consumer')


def _search_path(schema):
    # pg_catalog is searched first unless listed. Its builtins are named bool,
    # int8 and varchar, so user types called "boolean", "bigint" or "character
    # varying" on the test schema are visible either way; only a user "bytea"
    # needs pg_catalog listed after the schema, as a misconfigured deployment could.
    return f'SET LOCAL search_path TO {schema}, pg_catalog'


# name: (legacy outcome(s), new outcome, DDL builder). Outcomes are True/False or
# the class name of the exception the legacy path raises (new never raises here).
# Builders receive quoted identifiers: n.schema is the test schema, n.shadow a
# sibling schema name derived from it.
VARIANTS = {
    # Legitimate schema and the known gaps both implementations accept alike.
    'baseline': ((True,), True, lambda n:[]),
    'unique_include': ((True,), True, lambda n:[
        f'ALTER TABLE {TABLE} DROP CONSTRAINT uq_preview_version',
        f'ALTER TABLE {TABLE} ADD CONSTRAINT uq_preview_version UNIQUE (case_id, post_case_version) INCLUDE (available)']),
    'extra_nonunique_index': ((True,), True, lambda n:[f'CREATE INDEX ix_preview_extra ON {TABLE} (case_id)']),
    'identity_column': ((True,), True, lambda n:[
        f'ALTER TABLE {TABLE} ALTER COLUMN generation ADD GENERATED ALWAYS AS IDENTITY']),
    'enum_boolean_not_visible': ((True,), True, lambda n: [
        f'CREATE SCHEMA {n.shadow}', f'CREATE TYPE {n.shadow}."boolean" AS ENUM (\'a\')']),
    # Counterfeits both implementations reject.
    'nullable': ((False,), False, lambda n:[f'ALTER TABLE {TABLE} ALTER COLUMN removal_reason SET NOT NULL']),
    'type': ((False,), False, lambda n:[f'ALTER TABLE {TABLE} ALTER COLUMN removal_reason TYPE varchar(33)']),
    'default': ((False,), False, lambda n:[f'ALTER TABLE {TABLE} ALTER COLUMN available SET DEFAULT false']),
    'collation': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} ALTER COLUMN request_key TYPE varchar(128) COLLATE "C"']),
    'extra_column': ((False,), False, lambda n:[f'ALTER TABLE {TABLE} ADD COLUMN c_preview_extra integer']),
    'extra_unique': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} ADD CONSTRAINT uq_preview_extra UNIQUE (audit_event_id)']),
    'unique_nulls_not_distinct': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} DROP CONSTRAINT uq_preview_consumer',
        f'ALTER TABLE {TABLE} ADD CONSTRAINT uq_preview_consumer UNIQUE NULLS NOT DISTINCT (consuming_decision_record_id)']),
    'fk_not_valid': ((False,), False, lambda n:_replace_fk('NOT VALID')),
    'fk_cascade': ((False,), False, lambda n:_replace_fk('ON DELETE CASCADE')),
    'fk_restrict': ((False,), False, lambda n:_replace_fk('ON UPDATE RESTRICT')),
    'fk_deferrable': ((False,), False, lambda n:_replace_fk('DEFERRABLE')),
    'fk_match_full': ((False,), False, lambda n:_replace_fk('MATCH FULL')),
    'fk_other_schema': ((False,), False, lambda n:[
        f'CREATE SCHEMA {n.shadow}',
        f'CREATE TABLE {n.shadow}.case_heads (case_id character varying(80) PRIMARY KEY)',
        f'ALTER TABLE {TABLE} DROP CONSTRAINT fk_preview_case_id',
        f'ALTER TABLE {TABLE} ADD CONSTRAINT fk_preview_case_id FOREIGN KEY (case_id) REFERENCES {n.shadow}.case_heads(case_id)']),
    'check_changed': ((False,), False, lambda n:_replace_check('(expires_at >= issued_at)')),
    'check_not_valid': ((False,), False, lambda n:_replace_check('(expires_at > issued_at) NOT VALID')),
    'check_missing': ((False,), False, lambda n:[f'ALTER TABLE {TABLE} DROP CONSTRAINT ck_preview_expiry']),
    'extra_check': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} ADD CONSTRAINT ck_preview_extra CHECK (generation >= 0)']),
    'pk_missing': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} DROP CONSTRAINT fk_preview_previous_preview_id',
        f'ALTER TABLE {TABLE} DROP CONSTRAINT lifecycle_action_previews_pkey']),
    'no_foreign_keys': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} DROP CONSTRAINT {name}' for name in FOREIGN_KEYS]),
    'no_keys': ((False,), False, lambda n:[
        f'ALTER TABLE {TABLE} DROP CONSTRAINT fk_preview_previous_preview_id',
        f'ALTER TABLE {TABLE} DROP CONSTRAINT lifecycle_action_previews_pkey',
        *(f'ALTER TABLE {TABLE} DROP CONSTRAINT {name}' for name in UNIQUES)]),
    'temp_table_shadow': ((False,), False, lambda n:[
        f'CREATE TEMP TABLE {TABLE} (LIKE {n.schema}.{TABLE} INCLUDING ALL)']),
    'enum_boolean_visible': ((False,), False, lambda n:[
        _search_path(n.schema), f'CREATE TYPE {n.schema}."boolean" AS ENUM (\'a\')']),
    'domain_bytea_retyped_column': ((False,), False, lambda n:[
        _search_path(n.schema), f'CREATE DOMAIN {n.schema}.bytea AS text',
        f'ALTER TABLE {TABLE} ALTER COLUMN body TYPE {n.schema}.bytea USING encode(body, \'hex\')']),
    # States where the legacy path raised; the new path answers False instead.
    'missing_table': (('NoSuchTableError',), False, lambda n:[f'DROP TABLE {TABLE}']),
    'domain_bytea_visible': ((False, 'CompileError'), False, lambda n:[
        _search_path(n.schema), f'CREATE DOMAIN {n.schema}.bytea AS text']),
    'domain_bigint_self_named': (('RecursionError',), False, lambda n:[
        _search_path(n.schema), f'CREATE DOMAIN {n.schema}.bigint AS bigint']),
}


def _outcome(function, connection):
    try:
        with connection.begin_nested():
            return function(connection)
    except Exception as error:  # the pair of outcomes, not the traceback, is the assertion
        return type(error).__name__


@pytest.mark.parametrize('variant', sorted(VARIANTS))
def test_PC01_preview_catalog_matches_legacy_reflection_decision(flow_engine, variant):
    legacy_expected, new_expected, ddl = VARIANTS[variant]
    schema = flow_engine._customer_test_schema
    with flow_engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        names = SimpleNamespace(schema=quote(schema), shadow=quote(schema + '_shadow'))
        # Begin before the first statement: SQLAlchemy 2.0 autobegins on execute,
        # after which an explicit begin() raises InvalidRequestError.
        transaction = connection.begin()
        try:
            assert version(connection) == NOTIFICATION
            for statement in ddl(names):
                connection.execute(text(statement))
            legacy = _outcome(legacy_preview_descriptor, connection)
            current = _outcome(_preview_descriptor, connection)
        finally:
            transaction.rollback()
        assert current == new_expected, (variant, legacy, current)
        assert legacy in legacy_expected, (variant, legacy, current)
        # Fail-closed invariant for every variant, independent of the table above.
        assert not (current is True and legacy is not True), (variant, legacy, current)
        # Rolled-back DDL leaves the next call on the same connection accepting again.
        assert legacy_preview_descriptor(connection) is True and _preview_descriptor(connection) is True
        assert version(connection) == NOTIFICATION


def test_PC02_preview_catalog_is_one_statement_without_parameters(flow_engine):
    from returnops_domain.lifecycle_schema import PREVIEW_CATALOG
    statements = []
    with flow_engine.connect() as connection:
        class Observed:
            def __getattr__(self, name):
                return getattr(connection, name)

            def execute(self, statement, parameters=None):
                statements.append((str(statement), parameters))
                return connection.execute(statement) if parameters is None else connection.execute(statement, parameters)
        assert _preview_descriptor(Observed()) is True
    assert len(statements) == 1 and statements[0] == (PREVIEW_CATALOG.text, None)
    assert not PREVIEW_CATALOG.text.startswith("SELECT jsonb_build_object('table_name', r.relname,")
