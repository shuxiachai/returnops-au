"""0009-only preview metadata. Never imported into frozen 0007 metadata.

The body is erasable; the acceptance/key/version/source identity is retained.
Neither this table nor its migration creates a capability or an execution.
"""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Boolean,
    DateTime, LargeBinary, CheckConstraint, UniqueConstraint, ForeignKeyConstraint)
from . import customer_tables as old, investigation_tables as investigation, lifecycle_tables as lifecycle

metadata = MetaData()


def col(name, kind=None, **options):
    return Column(name, String(80) if kind is None else kind, **options)


previews = Table('lifecycle_action_previews', metadata,
    col('preview_id', primary_key=True), col('case_id', nullable=False),
    col('component_id', nullable=False), col('store_id', nullable=False), col('owner_id', nullable=False),
    col('input_version', BigInteger, nullable=False), col('generation', BigInteger, nullable=False),
    col('proposal_record_id', nullable=False), col('proposal_hash', String(64), nullable=False),
    col('review_record_id', nullable=False), col('review_hash', String(64), nullable=False),
    col('review_event_id', nullable=False), col('review_event_hash', String(64), nullable=False),
    col('order_projection_id', nullable=False), col('order_hash', String(64), nullable=False),
    col('profile_version', nullable=False), col('profile_hash', String(64), nullable=False),
    col('authority_revision', BigInteger, nullable=False),
    col('pre_case_version', BigInteger, nullable=False), col('post_case_version', BigInteger, nullable=False),
    col('previous_preview_id'), col('issued_at', DateTime(timezone=True), nullable=False),
    col('expires_at', DateTime(timezone=True), nullable=False),
    col('audit_event_id', nullable=False), col('audit_hash', String(64), nullable=False),
    col('body_hash', String(64), nullable=False), col('body', LargeBinary),
    col('available', Boolean, nullable=False), col('removal_reason', String(32)),
    col('request_key', String(128), nullable=False), col('request_fingerprint', String(64), nullable=False),
    col('consuming_decision_record_id'), col('consumed_at', DateTime(timezone=True)),
    UniqueConstraint('component_id', 'store_id', 'case_id', 'request_key', name='uq_preview_request'),
    UniqueConstraint('case_id', 'post_case_version', name='uq_preview_version'),
    UniqueConstraint('consuming_decision_record_id', name='uq_preview_consumer'),
    CheckConstraint('post_case_version = pre_case_version + 1', name='ck_preview_transition'),
    CheckConstraint('available = (body IS NOT NULL)', name='ck_preview_body'),
    CheckConstraint('(consuming_decision_record_id IS NULL) = (consumed_at IS NULL)', name='ck_preview_consumed'),
    CheckConstraint('expires_at > issued_at', name='ck_preview_expiry'),
)

for column in ('input_version', 'generation', 'authority_revision', 'pre_case_version', 'post_case_version'):
    previews.append_constraint(CheckConstraint(
        f'{column} BETWEEN 1 AND 9007199254740991', name='ck_preview_' + column))

for column, parent, parent_column in (
    ('case_id', old.case_heads, 'case_id'),
    ('proposal_record_id', old.history, 'record_id'),
    ('review_record_id', old.history, 'record_id'),
    ('review_event_id', lifecycle.events, 'event_id'),
    ('order_projection_id', investigation.projections, 'projection_id'),
    ('audit_event_id', old.audit, 'event_id'),
    ('consuming_decision_record_id', old.history, 'record_id'),
    ('previous_preview_id', previews, 'preview_id'),
):
    previews.append_constraint(ForeignKeyConstraint([column], [parent.c[parent_column]],
        name='fk_preview_' + column))
