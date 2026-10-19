"""0007-only internal lifecycle metadata; immutable bodies stay in history.

All tables start empty. No production producer or authority is registered by
the migration. Source bindings contain identities/hashes, never message text.
"""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Boolean,
                        DateTime, CheckConstraint, UniqueConstraint, ForeignKeyConstraint)
from . import customer_tables as old, investigation_tables as investigation

metadata = MetaData()


def col(name, kind=String(80), **kw):
    return Column(name, kind, **kw)


def table(name, *columns):
    return Table(name, metadata, *columns)


state = table('case_lifecycle_state', col('case_id', primary_key=True),
    col('input_version', BigInteger, nullable=False), col('generation', BigInteger, nullable=False),
    col('proposal_version', BigInteger, nullable=False), col('proposal_record_id'),
    col('review_record_id'), col('preview_id'), col('approval_record_id'),
    col('outcome_record_id'), col('outcome', String(24)), col('notification_id', unique=True),
    col('notification_record_id'), col('notification_hash', String(64)),
    col('notification_work_id'),
    col('return_record_id'), col('label_record_id'),
    col('available', Boolean, nullable=False),
    CheckConstraint('generation >= 1 AND proposal_version >= 0', name='ck_lifecycle_generation'),
    CheckConstraint("outcome IS NULL OR outcome IN ('RETURN_CREATED','REJECTED','MANUAL_HANDLED')", name='ck_lifecycle_outcome'))

authorities = table('lifecycle_authorities', col('store_id', primary_key=True),
    col('component_id', primary_key=True), col('purpose', String(32), primary_key=True), col('enabled', Boolean, nullable=False),
    col('revision', BigInteger, nullable=False))

work = table('lifecycle_work', col('work_id', primary_key=True), col('case_id', nullable=False),
    col('component_id', nullable=False), col('store_id', nullable=False), col('owner_id', nullable=False),
    col('purpose', String(32), nullable=False), col('input_version', BigInteger, nullable=False),
    col('generation', BigInteger, nullable=False), col('target_hash', String(64), nullable=False), col('target_record_id'),
    col('state', String(16), nullable=False), col('claim_id'), col('epoch', BigInteger, nullable=False),
    col('claimed_case_version', BigInteger), col('authority_revision', BigInteger),
    col('idempotency_key', String(128), unique=True),
    col('lease_expires_at', DateTime(timezone=True)), col('created_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('case_id', 'purpose', 'generation', 'target_hash', name='uq_lifecycle_work_target'),
    CheckConstraint("purpose IN ('PROPOSAL','REVISION','OUTCOME','NOTIFICATION','EFFECT') AND state IN ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED') AND epoch >= 0", name='ck_lifecycle_work'),
    CheckConstraint("state <> 'RUNNING' OR (claim_id IS NOT NULL AND claimed_case_version IS NOT NULL AND lease_expires_at IS NOT NULL AND epoch > 0)", name='ck_lifecycle_claim'))

sources = table('lifecycle_source_bindings', col('record_id', primary_key=True),
    col('case_id', nullable=False), col('work_id', nullable=False), col('claim_id', nullable=False),
    col('epoch', BigInteger, nullable=False), col('generation', BigInteger, nullable=False),
    col('input_version', BigInteger, nullable=False), col('case_version', BigInteger, nullable=False),
    col('source_hash', String(64), nullable=False), col('authority_revision', BigInteger, nullable=False),
    col('target_record_id'), col('slot', String(16), nullable=False),
    col('dispatch_source_record_id'), col('provider_operation_id'), col('artifact_evidence_id'), col('artifact_sha256', String(64)),
    col('order_projection_id'),
    UniqueConstraint('work_id', 'epoch', 'slot', name='uq_lifecycle_source_slot'),
    CheckConstraint("slot IN ('PRIMARY','NOTIFICATION')", name='ck_lifecycle_source_slot'))

events = table('lifecycle_event_receipts', col('event_id', primary_key=True),
    col('case_id', nullable=False), col('work_id', nullable=False), col('record_id', nullable=False, unique=True),
    col('fingerprint', String(64), nullable=False), col('event_kind', String(32), nullable=False),
    col('source_id', nullable=False), col('case_version', BigInteger, nullable=False),
    col('source_hash', String(64), nullable=False), col('source_audit_event_id', nullable=False),
    col('pre_case_version', BigInteger, nullable=False), col('pre_input_version', BigInteger, nullable=False),
    col('pre_generation', BigInteger, nullable=False),
    col('input_version', BigInteger, nullable=False), col('generation', BigInteger, nullable=False),
    col('status', String(32), nullable=False), col('accepted_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('case_id','event_kind','source_id',name='uq_lifecycle_accepted_source'))

# An operation's latest saved revision is a historical effect fact. Keeping it
# here neither creates an operation nor authorizes dispatch/re-dispatch.
effects = table('lifecycle_effect_refs', col('operation_id', primary_key=True),
    col('case_id', nullable=False), col('record_id', nullable=False), col('object_version', BigInteger, nullable=False),
    col('approval_record_id', nullable=False), col('command_id', nullable=False),
    col('input_version', BigInteger, nullable=False), col('generation', BigInteger, nullable=False),
    col('operation_type', String(24), nullable=False), col('status', String(24), nullable=False),
    col('identity_hash', String(64), nullable=False), col('artifact_evidence_id'),
    col('artifact_sha256', String(64)), col('dispatch_source_record_id'))

for child, column, parent, parent_column in (
    (state, 'case_id', old.case_heads, 'case_id'),
    (work, 'case_id', old.case_heads, 'case_id'),
    (sources, 'record_id', old.history, 'record_id'), (sources, 'work_id', work, 'work_id'),
    (sources, 'order_projection_id', investigation.projections, 'projection_id'),
    (events, 'work_id', work, 'work_id'), (events, 'record_id', old.history, 'record_id'),
    (effects, 'record_id', old.history, 'record_id'),
):
    child.append_constraint(ForeignKeyConstraint([column], [parent.c[parent_column]]))

for item in metadata.tables.values():
    for column in item.columns:
        if column.name.endswith('_id'):
            item.append_constraint(CheckConstraint(
                f"{column.name} IS NULL OR ({column.name} ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{2,79}}$' AND {column.name} !~ '[^A-Za-z0-9_-]')",
                name=f'ck_{item.name}_{column.name}'))
        if column.name in {'input_version', 'case_version', 'generation', 'revision', 'authority_revision', 'object_version'}:
            item.append_constraint(CheckConstraint(f'{column.name} BETWEEN 1 AND 9007199254740991', name=f'ck_{item.name}_{column.name}'))
