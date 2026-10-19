"""0010 identity-only first-operation sidecar; no parameter copy or dispatch."""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, DateTime,
    CheckConstraint, UniqueConstraint, ForeignKeyConstraint, Index)
from . import customer_tables as old, lifecycle_tables as lifecycle

metadata = MetaData()
IDENTITIES = ('preparation_id', 'case_id', 'approval_execution_work_id',
    'original_approval_acceptance_id', 'operation_id', 'first_operation_record_id', 'origin_audit_event_id')
HASHES = ('request_fingerprint', 'profile_hash', 'binding_hash')


def col(name, kind=None, **options):
    return Column(name, String(80) if kind is None else kind, nullable=False, **options)


preparations = Table('lifecycle_execution_preparations', metadata,
    col('preparation_id', primary_key=True), col('case_id'), col('approval_execution_work_id'),
    col('original_approval_acceptance_id'), col('command_type', String(32)), col('operation_id'),
    col('first_operation_record_id'), col('effect_key', String(128)),
    col('request_fingerprint', String(64)), col('profile_hash', String(64)),
    col('prepared_authority_revision', BigInteger), col('binding_hash', String(64)),
    col('origin_audit_event_id'), col('created_at', DateTime(timezone=True)), col('state', String(16)),
    UniqueConstraint('approval_execution_work_id', 'command_type', name='uq_preparation_command'),
    *(UniqueConstraint(name, name='uq_preparation_' + name) for name in
      ('operation_id', 'first_operation_record_id', 'origin_audit_event_id', 'effect_key')),
    CheckConstraint("command_type = 'CREATE_RETURN'", name='ck_preparation_command'),
    CheckConstraint("state IN ('PENDING','PAUSED','SUPERSEDED')", name='ck_preparation_state'),
    CheckConstraint('prepared_authority_revision BETWEEN 1 AND 9007199254740991',
                    name='ck_preparation_revision'),
)
for name in IDENTITIES:
    preparations.append_constraint(CheckConstraint(
        f"{name} ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{2,79}}$' AND {name} !~ '[^A-Za-z0-9_-]'",
        name='ck_preparation_' + name))
for name in (*HASHES, 'effect_key'):
    pattern = '^[0-9a-f]{64}$' if name in HASHES else '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$'
    forbidden = '[^0-9a-f]' if name in HASHES else '[^A-Za-z0-9_-]'
    preparations.append_constraint(CheckConstraint(
        f"{name} ~ '{pattern}' AND {name} !~ '{forbidden}'", name='ck_preparation_' + name))
for name, parent, target in (
    ('case_id', old.case_heads, 'case_id'),
    ('approval_execution_work_id', lifecycle.work, 'work_id'),
    ('original_approval_acceptance_id', old.acceptances, 'acceptance_id'),
    ('first_operation_record_id', old.history, 'record_id'),
    ('origin_audit_event_id', old.audit, 'event_id'),
):
    preparations.append_constraint(ForeignKeyConstraint([name], [parent.c[target]],
        name='fk_preparation_' + name))
Index('ix_preparation_case', preparations.c.case_id)
