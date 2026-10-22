"""Exact0014 catalog proof; no implicit upgrade, authority grant or backfill."""
from sqlalchemy import text, BigInteger, Boolean, DateTime, String, LargeBinary
from .execution_preparation_schema import CATALOG
from .notification_tables import metadata, CHECKS


def _ownership(connection):
    """New tables use the existing Domain owner and only its default ACL.

    A migration inheriting wider ALTER DEFAULT PRIVILEGES fails and rolls back.
    This check never changes grants, owners, roles or global default privileges.
    """
    rows = connection.execute(text("""
        SELECT relation.relname AS table_name, relation.relowner AS table_owner,
               original.relowner AS baseline_owner,
               COALESCE(relation.relacl, acldefault('r', relation.relowner))
                   = acldefault('r', relation.relowner) AS owner_only_acl,
               EXISTS (SELECT 1 FROM pg_attribute attribute
                       WHERE attribute.attrelid=relation.oid AND attribute.attnum>0
                         AND NOT attribute.attisdropped AND attribute.attacl IS NOT NULL) AS column_acl
        FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace
        JOIN pg_class original ON original.relnamespace=relation.relnamespace
             AND original.relname='lifecycle_work' AND original.relkind='r'
        WHERE namespace.nspname=current_schema()
          AND relation.relname IN (:control_name, :fact_name)
    """), {'control_name': 'notification_delivery_controls',
           'fact_name': 'core_mock_notification_facts'}).mappings().all()
    return (len(rows) == 2 and {row['table_name'] for row in rows} == set(metadata.tables)
            and all(row['table_owner'] == row['baseline_owner']
                    and row['owner_only_acl'] is True and row['column_acl'] is False for row in rows))


def descriptor(connection):
    if not _ownership(connection):
        return False
    tables = tuple(metadata.tables.values())
    parameters = dict(control_name='notification_delivery_controls',
                      fact_name='core_mock_notification_facts')
    names = set(parameters.values())
    if len(tables) != 2 or {table.name for table in tables} != names:
        return False
    sql = CATALOG.text
    replacements = (
        ('SELECT jsonb_build_object(', "SELECT jsonb_build_object('table_name', r.relname,"),
        ("r.relname='lifecycle_execution_preparations'",
         'r.relname IN (:control_name, :fact_name)'),
        ("'identity', a.attidentity, 'generated', a.attgenerated)",
         "'identity', a.attidentity, 'generated', a.attgenerated, 'collation', (SELECT collname FROM pg_collation WHERE oid=a.attcollation))"),
    )
    for original, replacement in replacements:
        if sql.count(original) != 1:
            return False
        sql = sql.replace(original, replacement, 1)
    # One fresh statement snapshot; no catalog result survives this invocation.
    rows = connection.execute(text(sql), parameters).scalars().all()
    if len(rows) != 2:
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
                    'bigint' if isinstance(column.type, BigInteger) else
                    'boolean' if isinstance(column.type, Boolean) else
                    'bytea' if isinstance(column.type, LargeBinary) else f'character varying({column.type.length})')
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
            expected[constraint.name] = ('f', 'FOREIGN KEY (' + ', '.join(e.parent.name for e in elements)
                + ') REFERENCES ' + elements[0].column.table.name + '('
                + ', '.join(e.column.name for e in elements) + ')')
        actual = row['constraints'] or []
        if (len(actual) != len(expected)
                or {c['name']: (c['type'], c['definition']) for c in actual} != expected
                or any(not c['validated'] or c['deferrable'] or c['deferred'] for c in actual)):
            return False
        quote = connection.dialect.identifier_preparer.quote
        definitions = {name: f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} "
                       f"ON {quote(row['schema'])}.{table.name} USING btree ({', '.join(names)})"
                       for name, (unique, names) in keys.items()}
        indexes = row['indexes'] or []
        if (len(indexes) != len(definitions)
                or {item['name']: item['definition'] for item in indexes} != definitions
                or any(not item['valid'] or not item['ready'] or not item['immediate']
                       or item['nulls_not_distinct'] for item in indexes)):
            return False
    return True
