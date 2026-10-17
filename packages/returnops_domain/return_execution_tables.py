"""0011 private execution control, explicit provider grants and independent ledger.

No legacy metadata is changed. The mock ledger deliberately has no Domain FK:
its durable transaction must not depend on a still-open Domain transaction.
"""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Boolean,
    DateTime, CheckConstraint, UniqueConstraint, ForeignKeyConstraint, Index)
from . import customer_tables as old
from .execution_preparation_tables import preparations

metadata = MetaData()
CHECKS = {}


def col(name, kind=None, *, nullable=False, primary_key=False):
    return Column(name, String(80) if kind is None else kind,
                  nullable=nullable, primary_key=primary_key)


CONTROL_IDS = ('preparation_id', 'case_id', 'store_id', 'owner_id', 'principal_id', 'session_id',
    'execution_work_id', 'approval_record_id', 'approval_acceptance_id', 'operation_id',
    'first_record_id', 'dispatch_record_id', 'dispatch_claim_id', 'command_id', 'approval_id',
    'proposal_id', 'provider_id', 'config_id', 'parcel_id')
CONTROL_HASHES = ('preparation_hash', 'first_body_hash', 'dispatch_body_hash', 'request_fingerprint', 'operation_fingerprint',
    'original_key_hash', 'profile_hash', 'config_hash', 'binding_hash')
CONTROL_NUMBERS = ('input_version', 'generation', 'proposal_version', 'approval_case_version',
    'dispatch_case_version', 'execution_authority_revision', 'provider_revision')
controls = Table('lifecycle_return_execution_controls', metadata,
    *(col(name, primary_key=name == 'preparation_id') for name in CONTROL_IDS),
    col('effect_key', String(128)), *(col(name, String(64)) for name in CONTROL_HASHES),
    *(col(name, BigInteger) for name in CONTROL_NUMBERS),
    col('dispatch_at', DateTime(timezone=True)), col('dispatch_deadline', DateTime(timezone=True)),
    col('dispatch_audit_id'), col('status', String(16)),
    col('query_epoch', BigInteger), col('query_claim_id', nullable=True),
    col('query_lease_until', DateTime(timezone=True), nullable=True),
    col('result_record_id', nullable=True), col('result_audit_id', nullable=True),
    col('confirmed_ledger_hash', String(64), nullable=True),
    col('confirmed_provider_operation_id', nullable=True),
    col('confirmed_effect_status', String(16), nullable=True), col('confirmation_audit_id', nullable=True),
    col('result_retained', Boolean), col('source_available', Boolean),
    *(UniqueConstraint(name, name='uq_return_control_' + name) for name in
      ('execution_work_id', 'operation_id', 'effect_key', 'dispatch_record_id', 'dispatch_audit_id')),
)
for name, parent, target in (
    ('preparation_id', preparations, 'preparation_id'), ('case_id', old.case_heads, 'case_id'),
    ('first_record_id', old.history, 'record_id'), ('dispatch_record_id', old.history, 'record_id'),
    ('dispatch_audit_id', old.audit, 'event_id'), ('result_record_id', old.history, 'record_id'),
    ('result_audit_id', old.audit, 'event_id'),
    ('confirmation_audit_id', old.audit, 'event_id'),
):
    controls.append_constraint(ForeignKeyConstraint([name], [parent.c[target]], name='fk_return_control_' + name))
Index('ix_return_control_case', controls.c.case_id)

permissions = Table('return_provider_permissions', metadata,
    *(col(name, primary_key=True) for name in ('store_id', 'component_id', 'provider_id', 'config_id', 'command_type')),
    col('config_hash', String(64)), col('revision', BigInteger),
    col('create_enabled', Boolean), col('query_enabled', Boolean))

ledger = Table('core_mock_return_ledger', metadata,
    col('effect_key', String(128), primary_key=True), col('store_id'), col('provider_id'), col('config_id'),
    col('config_hash', String(64)), col('operation_id'), col('dispatch_record_id'),
    col('dispatch_binding_hash', String(64)), col('operation_fingerprint', String(64)),
    col('provider_operation_id'), col('parcel_id'), col('status', String(16)),
    col('provider_return_id', nullable=True), col('error_code', String(32), nullable=True),
    col('accepted_at', DateTime(timezone=True)), col('fact_hash', String(64)),
    UniqueConstraint('provider_operation_id', name='uq_mock_return_provider_operation'),
    UniqueConstraint('operation_id', name='uq_mock_return_operation'),
    UniqueConstraint('provider_return_id', name='uq_mock_return_result'))


def check(table, name, sql, expected):
    table.append_constraint(CheckConstraint(sql, name=name))
    CHECKS.setdefault(table.name, {})[name] = expected


def enum(table, prefix, name, values):
    sql = name + ' IN (' + ','.join("'" + value + "'" for value in values) + ')'
    expression = "((" + name + ")::text = ANY ((ARRAY[" + ', '.join(
        "'" + value + "'::character varying" for value in values) + "])::text[]))"
    check(table, prefix + name, sql, expression)


for table, prefix in ((controls, 'ck_return_control_'), (permissions, 'ck_return_permission_'), (ledger, 'ck_mock_return_')):
    for column in table.columns:
        name = column.name
        if isinstance(column.type, String) and (name.endswith('_id') or name.endswith('_hash') or name.endswith('_fingerprint') or name == 'effect_key'):
            hashed = name.endswith('_hash') or name.endswith('_fingerprint')
            pattern = '^[0-9a-f]{64}$' if hashed else '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$' if name == 'effect_key' else '^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$'
            forbidden = '[^0-9a-f]' if hashed else '[^A-Za-z0-9_-]'
            sql = f"{name} ~ '{pattern}' AND {name} !~ '{forbidden}'"
            expression = f"((({name})::text ~ '{pattern}'::text) AND (({name})::text !~ '{forbidden}'::text))"
            # PostgreSQL CHECK permits NULL; nullable columns retain that rule.
            check(table, prefix + name, sql, expression)
        if isinstance(column.type, BigInteger):
            minimum = 0 if name == 'query_epoch' else 1
            check(table, prefix + name, f'{name} BETWEEN {minimum} AND 9007199254740991',
                  f"(({name} >= {minimum}) AND ({name} <= '9007199254740991'::bigint))")
enum(controls, 'ck_return_control_', 'status', ('EXECUTING', 'SUCCEEDED', 'FAILED'))
enum(controls, 'ck_return_control_', 'confirmed_effect_status', ('SUCCEEDED', 'FAILED'))
enum(ledger, 'ck_mock_return_', 'status', ('SUCCEEDED', 'FAILED'))
check(permissions, 'ck_return_permission_command', "command_type = 'CREATE_RETURN'",
      "((command_type)::text = 'CREATE_RETURN'::text)")
check(controls, 'ck_return_control_deadline', 'dispatch_deadline > dispatch_at', '(dispatch_deadline > dispatch_at)')
check(controls, 'ck_return_control_query', '(query_claim_id IS NULL) = (query_lease_until IS NULL)',
      '((query_claim_id IS NULL) = (query_lease_until IS NULL))')
check(ledger, 'ck_mock_return_result', "(status = 'SUCCEEDED') = (provider_return_id IS NOT NULL)",
      "(((status)::text = 'SUCCEEDED'::text) = (provider_return_id IS NOT NULL))")
check(ledger, 'ck_mock_return_error', "(status = 'FAILED') = (error_code IS NOT NULL)",
      "(((status)::text = 'FAILED'::text) = (error_code IS NOT NULL))")
