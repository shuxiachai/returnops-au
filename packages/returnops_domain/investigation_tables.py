"""0005-only metadata. Never imported by the frozen 0002-0004 migrations."""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Integer, Boolean,
    DateTime, LargeBinary, CheckConstraint, UniqueConstraint, ForeignKeyConstraint)
from . import customer_tables as old

metadata = MetaData()
def col(name, kind=String(80), **kwargs): return Column(name, kind, **kwargs)
def table(name, *columns): return Table(name, metadata, *columns)
def stamp(name, **kwargs): return col(name, DateTime(timezone=True), **kwargs)
def blob(name, **kwargs): return col(name, LargeBinary, **kwargs)

services = table('investigation_services', col('store_id', primary_key=True), col('service_id', primary_key=True),
    col('provider_id', nullable=False), col('dataset_version', nullable=False), col('provider_version', nullable=False),
    col('dataset_sha256', String(64), nullable=False), col('enabled', Boolean, nullable=False),
    col('revision', BigInteger, nullable=False))
grants = table('investigation_provider_grants', col('store_id', primary_key=True), col('service_id', primary_key=True),
    col('provider_id', primary_key=True), col('can_read', Boolean, nullable=False), col('revision', BigInteger, nullable=False))
policy_events = table('investigation_policy_events', col('event_id', primary_key=True), col('store_id', nullable=False),
    col('sequence', BigInteger, nullable=False), col('event_hash', String(64), nullable=False), blob('body', nullable=False),
    UniqueConstraint('store_id', 'sequence', name='uq_investigation_policy_sequence'))
state = table('case_investigation_state', col('case_id', primary_key=True), col('current_work_id'),
    col('current_projection_id'), col('current_block_id'))
work = table('investigation_work', col('work_id', primary_key=True), col('case_id', nullable=False),
    col('intake_work_id', nullable=False, unique=True), col('acceptance_id', nullable=False),
    col('input_version', BigInteger, nullable=False), col('phase', String(24), nullable=False),
    col('state', String(24), nullable=False), col('owner_id', nullable=False), col('store_id', nullable=False),
    col('service_id', nullable=False), col('claim_id'), col('invocation_id'),
    col('epoch', BigInteger, nullable=False), col('claimed_case_version', BigInteger),
    col('service_signature', String(64)), col('grant_signature', String(64)),
    col('failure_count', Integer, nullable=False), col('safe_reason'),
    stamp('created_at', nullable=False), stamp('next_attempt_at', nullable=False), stamp('lease_expires_at'), stamp('completed_at'),
    UniqueConstraint('case_id', 'input_version', 'phase', name='uq_investigation_generation'),
    CheckConstraint("phase = 'ORDER_LOOKUP' AND epoch >= 0 AND failure_count >= 0 AND state IN ('PENDING','RUNNING','DONE','PAUSED','SUPERSEDED','FAILED')", name='ck_investigation_state'),
    CheckConstraint("state <> 'RUNNING' OR (claim_id IS NOT NULL AND invocation_id IS NOT NULL AND lease_expires_at IS NOT NULL AND epoch > 0)", name='ck_investigation_claim'))
inputs = table('investigation_inputs', col('work_id', primary_key=True), blob('reference'),
    col('available', Boolean, nullable=False), col('alternative', Boolean, nullable=False))
# Answers are already retained as statements; this small input projection is
# removed with them. It is never interpreted as an order snapshot.
clarification_inputs = table('investigation_clarification_inputs', col('case_id', primary_key=True),
    col('input_version', BigInteger, primary_key=True), blob('reference'), col('alternative', Boolean, nullable=False),
    col('available', Boolean, nullable=False))
groups = table('investigation_question_groups', col('question_set_id', primary_key=True),
    col('case_id', nullable=False), col('input_version', BigInteger, nullable=False),
    col('reference_question_id', nullable=False), col('context_question_id', nullable=False))
receipts = table('order_lookup_receipts', col('receipt_id', primary_key=True), col('work_id', nullable=False),
    col('case_id', nullable=False), col('input_version', BigInteger, nullable=False), col('claim_id', nullable=False),
    col('epoch', BigInteger, nullable=False), col('status', String(24), nullable=False),
    col('body_hash', String(64), nullable=False), col('available', Boolean, nullable=False), stamp('recorded_at', nullable=False),
    UniqueConstraint('work_id', 'epoch', name='uq_lookup_attempt_receipt'))
receipt_contents = table('order_lookup_contents', col('receipt_id', primary_key=True), blob('body', nullable=False))
projections = table('accepted_order_projections', col('projection_id', primary_key=True), col('case_id', nullable=False),
    col('receipt_id', nullable=False, unique=True), col('source_input_version', BigInteger, nullable=False),
    col('input_version', BigInteger, nullable=False), col('snapshot_id', nullable=False),
    col('snapshot_version', BigInteger, nullable=False), col('snapshot_hash', String(64), nullable=False),
    col('available', Boolean, nullable=False), stamp('accepted_at', nullable=False),
    UniqueConstraint('case_id', 'snapshot_id', 'snapshot_version', name='uq_accepted_order_snapshot'))
projection_contents = table('accepted_order_contents', col('projection_id', primary_key=True), blob('body', nullable=False))
blocks = table('order_lookup_blocks', col('block_id', primary_key=True), col('case_id', nullable=False),
    col('input_version', BigInteger, nullable=False), col('receipt_id', nullable=False, unique=True), blob('body', nullable=False))
discarded = table('discarded_order_invocations', col('invocation_id', primary_key=True), col('work_id', nullable=False),
    col('claim_id', nullable=False), col('epoch', BigInteger, nullable=False), col('service_signature', String(64), nullable=False),
    col('grant_signature', String(64), nullable=False), col('safe_reason', nullable=False), stamp('discarded_at', nullable=False))
for child, column, parent, parent_column in (
    (state,'case_id',old.case_heads,'case_id'), (work,'case_id',old.case_heads,'case_id'),
    (work,'intake_work_id',old.intake_work,'work_id'), (work,'acceptance_id',old.acceptances,'acceptance_id'),
    (inputs,'work_id',work,'work_id'), (clarification_inputs,'case_id',old.case_heads,'case_id'),
    (groups,'question_set_id',old.questions,'question_set_id'), (receipts,'work_id',work,'work_id'),
    (receipt_contents,'receipt_id',receipts,'receipt_id'), (projections,'receipt_id',receipts,'receipt_id'),
    (projection_contents,'projection_id',projections,'projection_id'), (blocks,'receipt_id',receipts,'receipt_id'),
    (discarded,'work_id',work,'work_id')):
    child.append_constraint(ForeignKeyConstraint([column], [parent.c[parent_column]]))
for item in metadata.tables.values():
    for column in item.columns:
        if column.name.endswith('_id'):
            item.append_constraint(CheckConstraint(f"{column.name} IS NULL OR ({column.name} ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{2,79}}$' AND {column.name} !~ '[^A-Za-z0-9_-]')", name=f'ck_{item.name}_{column.name}'))
        if column.name in {'input_version','source_input_version','snapshot_version','revision'}:
            item.append_constraint(CheckConstraint(f'{column.name} BETWEEN 1 AND 9007199254740991', name=f'ck_{item.name}_{column.name}'))
