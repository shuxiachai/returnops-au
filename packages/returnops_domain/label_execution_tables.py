"""0012 label-only control, provider permission, independent fact and artifact intent.

Nothing is added to previous metadata: old dynamically imported DDL is frozen.
"""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Boolean,
    DateTime, CheckConstraint, UniqueConstraint, ForeignKeyConstraint, Index)
from . import customer_tables as old

metadata = MetaData()
CHECKS = {}


def col(name, kind=None, *, nullable=False, primary_key=False):
    return Column(name, String(80) if kind is None else kind, nullable=nullable, primary_key=primary_key)


CONTROL_IDS = ('control_id', 'case_id', 'store_id', 'owner_id', 'principal_id', 'session_id',
    'execution_work_id', 'approval_record_id', 'approval_acceptance_id', 'bridge_event_id',
    'bridge_work_id', 'return_preparation_id', 'return_operation_id', 'return_record_id',
    'provider_return_id', 'operation_id', 'first_record_id', 'dispatch_record_id',
    'dispatch_claim_id', 'command_id', 'return_command_id', 'approval_id', 'proposal_id',
    'provider_id', 'config_id', 'parcel_id')
CONTROL_HASHES = ('bridge_target_hash', 'bridge_receipt_hash', 'return_result_hash', 'return_ledger_hash',
    'first_body_hash', 'dispatch_body_hash', 'command_hash', 'operation_fingerprint',
    'original_key_hash', 'profile_hash', 'config_hash', 'binding_hash')
CONTROL_NUMBERS = ('input_version', 'generation', 'proposal_version', 'pre_dispatch_case_version',
    'dispatch_case_version', 'execution_authority_revision', 'effect_authority_revision',
    'provider_revision', 'return_authority_revision', 'return_provider_revision')
controls = Table('lifecycle_label_execution_controls', metadata,
    *(col(name, primary_key=name == 'control_id') for name in CONTROL_IDS),
    col('effect_key', String(128)), *(col(name, String(64)) for name in CONTROL_HASHES),
    *(col(name, BigInteger) for name in CONTROL_NUMBERS),
    col('dispatch_at', DateTime(timezone=True)), col('dispatch_deadline', DateTime(timezone=True)),
    col('first_audit_id'), col('dispatch_audit_id'), col('status', String(16)),
    col('query_epoch', BigInteger), col('query_claim_id', nullable=True),
    col('query_lease_until', DateTime(timezone=True), nullable=True),
    col('confirmation_record_id', nullable=True), col('confirmation_audit_id', nullable=True),
    col('confirmation_case_version', BigInteger, nullable=True),
    col('confirmed_ledger_hash', String(64), nullable=True),
    col('confirmed_provider_operation_id', nullable=True), col('confirmed_provider_label_id', nullable=True),
    col('confirmed_effect_status', String(16), nullable=True),
    col('confirmation_retained', Boolean), col('source_available', Boolean),
    *(UniqueConstraint(name, name='uq_label_control_' + name) for name in
      ('case_id', 'execution_work_id', 'bridge_event_id', 'operation_id', 'effect_key',
       'first_record_id', 'dispatch_record_id', 'dispatch_audit_id')),
    UniqueConstraint('control_id', 'case_id', name='uq_label_control_case_pair'))
for name, parent, target in (
    ('case_id', old.case_heads, 'case_id'), ('first_record_id', old.history, 'record_id'),
    ('dispatch_record_id', old.history, 'record_id'), ('return_record_id', old.history, 'record_id'),
    ('first_audit_id', old.audit, 'event_id'), ('dispatch_audit_id', old.audit, 'event_id'),
    ('confirmation_record_id', old.history, 'record_id'), ('confirmation_audit_id', old.audit, 'event_id'),
):
    controls.append_constraint(ForeignKeyConstraint([name], [parent.c[target]], name='fk_label_control_' + name))

permissions = Table('label_provider_permissions', metadata,
    *(col(name, primary_key=True) for name in ('store_id', 'component_id', 'provider_id', 'config_id', 'command_type')),
    col('config_hash', String(64)), col('revision', BigInteger), col('create_enabled', Boolean), col('query_enabled', Boolean))

ledger = Table('core_mock_label_ledger', metadata,
    col('effect_key', String(128), primary_key=True), col('case_id'), col('store_id'), col('provider_id'), col('config_id'),
    col('config_hash', String(64)), col('operation_id'), col('dispatch_record_id'),
    col('dispatch_binding_hash', String(64)), col('operation_fingerprint', String(64)),
    col('command_hash', String(64)), col('return_ledger_hash', String(64)),
    col('provider_operation_id'), col('provider_return_id'), col('parcel_id'), col('status', String(16)),
    col('provider_label_id', nullable=True), col('error_code', String(32), nullable=True),
    col('accepted_at', DateTime(timezone=True)), col('fact_hash', String(64)),
    UniqueConstraint('operation_id', name='uq_mock_label_operation'),
    UniqueConstraint('provider_operation_id', name='uq_mock_label_provider_operation'),
    UniqueConstraint('provider_label_id', name='uq_mock_label_result'))

artifact_work = Table('lifecycle_label_artifact_work', metadata,
    col('work_id', primary_key=True), col('control_id'), col('case_id'), col('operation_id'),
    col('provider_label_id'), col('parcel_id'), col('confirmation_record_id'),
    col('confirmation_case_version', BigInteger), col('confirmed_ledger_hash', String(64)),
    col('binding_hash', String(64)), col('state', String(16)), col('epoch', BigInteger),
    col('claim_id', nullable=True), col('lease_expires_at', DateTime(timezone=True), nullable=True),
    col('claimed_case_version', BigInteger, nullable=True), col('authority_revision', BigInteger, nullable=True),
    col('created_at', DateTime(timezone=True)),
    UniqueConstraint('control_id', name='uq_label_artifact_control'),
    UniqueConstraint('case_id', name='uq_label_artifact_case'),
    ForeignKeyConstraint(['control_id', 'case_id'], [controls.c.control_id, controls.c.case_id], name='fk_label_artifact_control_case'),
    ForeignKeyConstraint(['confirmation_record_id'], [old.history.c.record_id], name='fk_label_artifact_confirmation'))


def check(table, name, sql, expected):
    table.append_constraint(CheckConstraint(sql, name=name))
    CHECKS.setdefault(table.name, {})[name] = expected


def enum(table, prefix, name, values):
    sql = name + ' IN (' + ','.join("'" + v + "'" for v in values) + ')'
    expression = "((" + name + ")::text = ANY ((ARRAY[" + ', '.join(
        "'" + v + "'::character varying" for v in values) + "])::text[]))"
    check(table, prefix + name, sql, expression)


for table, prefix in ((controls, 'ck_label_control_'), (permissions, 'ck_label_permission_'),
                      (ledger, 'ck_mock_label_'), (artifact_work, 'ck_label_artifact_')):
    for column in table.columns:
        name = column.name
        if isinstance(column.type, String) and (name.endswith('_id') or name.endswith('_hash') or name.endswith('_fingerprint') or name == 'effect_key'):
            hashed = name.endswith('_hash') or name.endswith('_fingerprint')
            pattern = '^[0-9a-f]{64}$' if hashed else '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$' if name == 'effect_key' else '^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$'
            forbidden = '[^0-9a-f]' if hashed else '[^A-Za-z0-9_-]'
            check(table, prefix + name, f"{name} ~ '{pattern}' AND {name} !~ '{forbidden}'",
                  f"((({name})::text ~ '{pattern}'::text) AND (({name})::text !~ '{forbidden}'::text))")
        if isinstance(column.type, BigInteger):
            minimum = 0 if name in {'query_epoch', 'epoch'} else 1
            check(table, prefix + name, f'{name} BETWEEN {minimum} AND 9007199254740991',
                  f"(({name} >= {minimum}) AND ({name} <= '9007199254740991'::bigint))")
enum(controls, 'ck_label_control_', 'status', ('EXECUTING', 'FAILED'))
enum(controls, 'ck_label_control_', 'confirmed_effect_status', ('SUCCEEDED', 'FAILED'))
enum(ledger, 'ck_mock_label_', 'status', ('SUCCEEDED', 'FAILED'))
enum(artifact_work, 'ck_label_artifact_', 'state', ('PENDING', 'PAUSED'))
check(permissions, 'ck_label_permission_command', "command_type = 'GENERATE_LABEL'", "((command_type)::text = 'GENERATE_LABEL'::text)")
check(controls, 'ck_label_control_deadline', 'dispatch_deadline > dispatch_at', '(dispatch_deadline > dispatch_at)')
check(controls, 'ck_label_control_query', '(query_claim_id IS NULL) = (query_lease_until IS NULL)', '((query_claim_id IS NULL) = (query_lease_until IS NULL))')
check(controls, 'ck_label_control_version', 'dispatch_case_version = pre_dispatch_case_version + 1', '(dispatch_case_version = (pre_dispatch_case_version + 1))')
check(ledger, 'ck_mock_label_result', "(status = 'SUCCEEDED') = (provider_label_id IS NOT NULL)", "(((status)::text = 'SUCCEEDED'::text) = (provider_label_id IS NOT NULL))")
check(ledger, 'ck_mock_label_error', "(status = 'FAILED') = (error_code IS NOT NULL)", "(((status)::text = 'FAILED'::text) = (error_code IS NOT NULL))")
check(artifact_work, 'ck_label_artifact_unclaimed',
      'epoch = 0 AND claim_id IS NULL AND lease_expires_at IS NULL AND claimed_case_version IS NULL AND authority_revision IS NULL',
      '((epoch = 0) AND (claim_id IS NULL) AND (lease_expires_at IS NULL) AND (claimed_case_version IS NULL) AND (authority_revision IS NULL))')
