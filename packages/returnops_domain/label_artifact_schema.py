"""Exact 0013 table catalog and the sole customer namespace alteration."""
from sqlalchemy import text, BigInteger, Boolean, DateTime, String, LargeBinary
from .execution_preparation_schema import CATALOG
from .label_artifact_tables import metadata, CHECKS, NAMESPACE_CHECK, GENERATED_PATTERN


def descriptor(connection):
    tables = tuple(metadata.tables.values())
    parameters = dict(permission_name='label_artifact_permissions',
                      control_name='lifecycle_label_artifact_controls',
                      claim_name='lifecycle_label_artifact_claims',
                      artifact_name='generated_label_artifacts',
                      content_name='generated_label_artifact_contents')
    names = set(parameters.values())
    if len(tables) != 5 or {table.name for table in tables} != names:
        return False
    sql = CATALOG.text
    replacements = (
        ('SELECT jsonb_build_object(', "SELECT jsonb_build_object('table_name', r.relname,"),
        ("r.relname='lifecycle_execution_preparations'",
         'r.relname IN (:permission_name, :control_name, :claim_name, :artifact_name, :content_name)'),
        ("'identity', a.attidentity, 'generated', a.attgenerated)",
         "'identity', a.attidentity, 'generated', a.attgenerated, 'collation', (SELECT collname FROM pg_collation WHERE oid=a.attcollation))"),
    )
    for original, replacement in replacements:
        if sql.count(original) != 1:
            return False
        sql = sql.replace(original, replacement, 1)
    # One fresh statement snapshot; no catalog result survives this invocation.
    rows = connection.execute(text(sql), parameters).scalars().all()
    if len(rows) != 5:
        return False
    found = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('table_name'), str):
            return False
        name = row['table_name']
        if name in found or name not in names:
            return False
        found.add(name)
    if found != names:
        return False
    by_name = {row['table_name']: row for row in rows}
    for table in tables:
        row = by_name[table.name]
        if any(row[key] != value for key, value in dict(kind='r', persistence='p', rls=False,
                force_rls=False, options=None, triggers=0).items()):
            return False
        columns = []
        for column in table.columns:
            kind = ('timestamp with time zone' if isinstance(column.type, DateTime) else
                    'bigint' if isinstance(column.type, BigInteger) else 'boolean' if isinstance(column.type, Boolean)
                    else 'bytea' if isinstance(column.type, LargeBinary) else f'character varying({column.type.length})')
            columns.append(dict(name=column.name, type=kind, notnull=not column.nullable,
                                default=None, identity='', generated='',
                                collation='default' if isinstance(column.type, String) else None))
        if row['columns'] != columns:
            return False
        expected = {table.name + '_pkey': ('p', 'PRIMARY KEY (' + ', '.join(c.name for c in table.primary_key) + ')')}
        expected.update({name: ('c', expression) for name, expression in CHECKS[table.name].items()})
        keys = {table.name + '_pkey': (True, tuple(c.name for c in table.primary_key))}
        for constraint in table.constraints:
            if constraint.__class__.__name__ == 'UniqueConstraint':
                names = tuple(c.name for c in constraint.columns)
                expected[constraint.name] = ('u', 'UNIQUE (' + ', '.join(names) + ')')
                keys[constraint.name] = (True, names)
        for constraint in table.foreign_key_constraints:
            elements = list(constraint.elements)
            parents = ', '.join(element.parent.name for element in elements)
            targets = ', '.join(element.column.name for element in elements)
            expected[constraint.name] = ('f', f'FOREIGN KEY ({parents}) REFERENCES '
                                        f'{elements[0].column.table.name}({targets})')
        constraints = row['constraints'] or []
        if (len(constraints) != len(expected) or
                {c['name']: (c['type'], c['definition']) for c in constraints} != expected or
                any(not c['validated'] or c['deferrable'] or c['deferred'] for c in constraints)):
            return False
        keys.update({index.name: (index.unique, tuple(c.name for c in index.columns)) for index in table.indexes})
        quote = connection.dialect.identifier_preparer.quote
        definitions = {name: f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON {quote(row['schema'])}.{table.name} "
                       f"USING btree ({', '.join(names)})" for name, (unique, names) in keys.items()}
        indexes = row['indexes'] or []
        if (len(indexes) != len(definitions) or {i['name']: i['definition'] for i in indexes} != definitions or
                any(not i['valid'] or not i['ready'] or not i['immediate'] or i['nulls_not_distinct'] for i in indexes)):
            return False
    rows = connection.execute(text("""SELECT c.conname,c.contype,c.convalidated,c.condeferrable,c.condeferred,
        pg_get_expr(c.conbin,c.conrelid) AS expression FROM pg_constraint c
        JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace
        WHERE n.nspname=current_schema() AND r.relname='customer_evidence' AND c.contype='c'""")).mappings().all()
    from .customer_tables import evidence
    names = {c.name for c in evidence.constraints if c.__class__.__name__ == 'CheckConstraint'} | {NAMESPACE_CHECK}
    if {r['conname'] for r in rows} != names or any(not r['convalidated'] or r['condeferrable'] or r['condeferred'] for r in rows):
        return False
    row, = [r for r in rows if r['conname'] == NAMESPACE_CHECK]
    return row['expression'] == "((evidence_id)::text !~ '^glabel_[0-9a-f]{64}$'::text)"
