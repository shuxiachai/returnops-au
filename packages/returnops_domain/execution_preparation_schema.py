"""Exact 0010 sidecar descriptor in one bounded catalog read, without caching."""
from sqlalchemy import text
from .execution_preparation_tables import preparations, IDENTITIES, HASHES

CATALOG = text("""SELECT jsonb_build_object(
  'schema', n.nspname, 'kind', r.relkind, 'persistence', r.relpersistence,
  'rls', r.relrowsecurity, 'force_rls', r.relforcerowsecurity, 'options', r.reloptions,
  'triggers', (SELECT count(*) FROM pg_trigger t WHERE t.tgrelid=r.oid AND NOT t.tgisinternal),
  'columns', (SELECT jsonb_agg(jsonb_build_object('name', a.attname,
      'type', format_type(a.atttypid,a.atttypmod), 'notnull', a.attnotnull,
      'default', pg_get_expr(d.adbin,d.adrelid), 'identity', a.attidentity, 'generated', a.attgenerated)
      ORDER BY a.attnum) FROM pg_attribute a LEFT JOIN pg_attrdef d
      ON d.adrelid=a.attrelid AND d.adnum=a.attnum
      WHERE a.attrelid=r.oid AND a.attnum>0 AND NOT a.attisdropped),
  'constraints', (SELECT jsonb_agg(jsonb_build_object('name', c.conname, 'type', c.contype,
      'definition', CASE WHEN c.contype='c' THEN pg_get_expr(c.conbin,c.conrelid)
                        ELSE pg_get_constraintdef(c.oid) END,
      'validated', c.convalidated, 'deferrable', c.condeferrable, 'deferred', c.condeferred)
      ORDER BY c.conname) FROM pg_constraint c WHERE c.conrelid=r.oid),
  'indexes', (SELECT jsonb_agg(jsonb_build_object('name', ix.relname,
      'definition', pg_get_indexdef(i.indexrelid), 'valid', i.indisvalid,
      'ready', i.indisready, 'immediate', i.indimmediate, 'nulls_not_distinct', i.indnullsnotdistinct)
      ORDER BY ix.relname) FROM pg_index i JOIN pg_class ix ON ix.oid=i.indexrelid WHERE i.indrelid=r.oid)
) FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace
WHERE n.nspname=current_schema() AND r.relname='lifecycle_execution_preparations'""")


def expected_constraints():
    result = {'lifecycle_execution_preparations_pkey': ('p', 'PRIMARY KEY (preparation_id)'),
        'uq_preparation_command': ('u', 'UNIQUE (approval_execution_work_id, command_type)'),
        'ck_preparation_command': ('c', "((command_type)::text = 'CREATE_RETURN'::text)"),
        'ck_preparation_state': ('c', "((state)::text = ANY ((ARRAY['PENDING'::character varying, 'PAUSED'::character varying, 'SUPERSEDED'::character varying])::text[]))"),
        'ck_preparation_revision': ('c', "((prepared_authority_revision >= 1) AND (prepared_authority_revision <= '9007199254740991'::bigint))")}
    for name in ('operation_id', 'first_operation_record_id', 'origin_audit_event_id', 'effect_key'):
        result['uq_preparation_' + name] = ('u', 'UNIQUE (' + name + ')')
    for name in (*IDENTITIES, *HASHES, 'effect_key'):
        pattern = ('^[0-9a-f]{64}$' if name in HASHES else
            '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$' if name == 'effect_key' else
            '^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$')
        forbidden = '[^0-9a-f]' if name in HASHES else '[^A-Za-z0-9_-]'
        result['ck_preparation_' + name] = ('c',
            f"((({name})::text ~ '{pattern}'::text) AND (({name})::text !~ '{forbidden}'::text))")
    for constraint in preparations.foreign_key_constraints:
        element, = constraint.elements
        result[constraint.name] = ('f', f'FOREIGN KEY ({element.parent.name}) REFERENCES '
            f'{element.column.table.name}({element.column.name})')
    return result


def descriptor(connection):
    rows = connection.execute(CATALOG).scalars().all()
    if len(rows) != 1:
        return False
    row = rows[0]
    if any(row[key] != value for key, value in dict(kind='r', persistence='p', rls=False,
            force_rls=False, options=None, triggers=0).items()):
        return False
    columns = []
    for column in preparations.columns:
        kind = ('timestamp with time zone' if column.name == 'created_at' else
            'bigint' if column.name == 'prepared_authority_revision' else
            f'character varying({column.type.length})')
        columns.append(dict(name=column.name, type=kind, notnull=True, default=None, identity='', generated=''))
    if row['columns'] != columns:
        return False
    expected = expected_constraints()
    constraints = row['constraints'] or []
    if (len(constraints) != len(expected) or
            {c['name']:(c['type'], c['definition']) for c in constraints} != expected or
            any(not c['validated'] or c['deferrable'] or c['deferred'] for c in constraints)):
        return False
    indexes = row['indexes'] or []
    keys = {'lifecycle_execution_preparations_pkey': ('preparation_id',),
        'uq_preparation_command': ('approval_execution_work_id', 'command_type'),
        'ix_preparation_case': ('case_id',)}
    keys.update({'uq_preparation_' + name:(name,) for name in
        ('operation_id', 'first_operation_record_id', 'origin_audit_event_id', 'effect_key')})
    quote = connection.dialect.identifier_preparer.quote
    definitions = {name:f"CREATE {'UNIQUE ' if name != 'ix_preparation_case' else ''}INDEX {name} "
        f"ON {quote(row['schema'])}.lifecycle_execution_preparations USING btree ({', '.join(columns)})"
        for name, columns in keys.items()}
    return (len(indexes) == len(definitions) and
        {i['name']:i['definition'] for i in indexes} == definitions and
        all(i['valid'] and i['ready'] and i['immediate'] and not i['nulls_not_distinct'] for i in indexes))
