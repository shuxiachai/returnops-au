"""Founder read metadata only; never extend live metadata used by migration0003."""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Integer,
                        DateTime, CheckConstraint, UniqueConstraint, ForeignKeyConstraint)
from . import customer_tables as old

metadata = MetaData()

def col(name, kind=String(80), **kwargs):
    return Column(name, kind, **kwargs)

def table(name, *columns):
    return Table(name, metadata, *columns)

snapshots = table('founder_read_snapshots',
    col('snapshot_id', primary_key=True), col('purpose', String(16), nullable=False),
    col('principal_id', nullable=False), col('role', String(16), nullable=False),
    col('store_id', nullable=False), col('case_id'), col('case_version', BigInteger),
    col('highwater', BigInteger, nullable=False), col('anchor_hash', String(64)),
    col('as_of', DateTime(timezone=True), nullable=False),
    col('expires_at', DateTime(timezone=True), nullable=False),
    CheckConstraint("role = 'FOUNDER' AND purpose IN ('LIST','HISTORY','AUDIT')", name='ck_founder_snapshot_scope'),
    CheckConstraint("highwater >= 0 AND expires_at > as_of AND ((purpose = 'LIST' AND case_id IS NULL AND case_version IS NULL) OR (purpose <> 'LIST' AND case_id IS NOT NULL AND case_version >= 1))", name='ck_founder_snapshot_bounds'))

# Explicit columns whitelist the non-personal summary; no body/blob/cache.
members = table('founder_list_members', col('snapshot_id', primary_key=True),
    col('ordinal', BigInteger, primary_key=True), col('case_id', nullable=False),
    col('case_version', BigInteger, nullable=False), col('input_version', BigInteger, nullable=False),
    col('status', String(32), nullable=False), col('created_at', DateTime(timezone=True), nullable=False),
    col('updated_at', DateTime(timezone=True), nullable=False), col('issue_category', String(32), nullable=False),
    UniqueConstraint('snapshot_id', 'case_id', name='uq_founder_list_member'),
    CheckConstraint('ordinal >= 1 AND case_version >= 1 AND input_version >= 1', name='ck_founder_list_versions'))

cursors = table('founder_read_cursors', col('cursor_hash', String(64), primary_key=True),
    col('snapshot_id', nullable=False), col('kind', String(32)), col('page_limit', Integer, nullable=False),
    col('object_id'), col('object_version', BigInteger), col('last_sequence', BigInteger, nullable=False),
    col('last_record_id'),
    CheckConstraint('page_limit BETWEEN 1 AND 100 AND last_sequence >= 0 AND (object_version IS NULL OR (object_id IS NOT NULL AND object_version >= 1))', name='ck_founder_cursor_query'))

encodings = table('founder_history_encodings', col('record_id', primary_key=True),
    col('profile', String(48), nullable=False), col('source_content_sha256', String(64), nullable=False),
    col('projected_content_sha256', String(64), nullable=False), col('receipt_id'),
    CheckConstraint("(profile = 'historical-order-block/v1' AND receipt_id IS NOT NULL) OR (profile IN ('founder-finite/v2','founder-finite/v2-from-v1') AND receipt_id IS NULL)", name='ck_founder_encoding_profile'),
    CheckConstraint("source_content_sha256 ~ '^[0-9a-f]{64}$' AND projected_content_sha256 ~ '^[0-9a-f]{64}$'", name='ck_founder_encoding_hashes'))

for child, column, parent, parent_column in (
    (members, 'snapshot_id', snapshots, 'snapshot_id'),
    (members, 'case_id', old.case_heads, 'case_id'),
    (cursors, 'snapshot_id', snapshots, 'snapshot_id'),
    (encodings, 'record_id', old.history, 'record_id'),
):
    child.append_constraint(ForeignKeyConstraint([column], [parent.c[parent_column]]))
