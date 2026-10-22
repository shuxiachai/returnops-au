"""0014 fresh notification controls and independent CORE_MOCK sending facts.

A2.06 / FR-009..012 / AH-10 and the independent-notification sequence.
Both tables start empty. Existing notification rows are never backfilled.
"""
from sqlalchemy import (MetaData, Table, Column, String, BigInteger, Boolean,
                        DateTime, LargeBinary, CheckConstraint, UniqueConstraint,
                        ForeignKeyConstraint)
from . import customer_tables as old, lifecycle_tables as life

metadata = MetaData()
CHECKS = {}


def col(name, kind=None, **options):
    return Column(name, kind if kind is not None else String(80),
                  nullable=options.pop('nullable', False), **options)


controls = Table('notification_delivery_controls', metadata,
    col('notification_work_id', primary_key=True),
    *(col(name) for name in ('case_id', 'store_id', 'owner_id', 'notification_id',
                            'outcome_record_id', 'initial_notification_record_id',
                            'outcome_event_id', 'producer_id')),
    col('outcome', String(24)), col('profile', String(80)), col('channel', String(16)),
    *(col(name, String(64)) for name in ('profile_hash', 'payload_hash', 'source_hash', 'intent_hash')),
    col('intent_core', LargeBinary), col('source_manifest', LargeBinary, nullable=True),
    col('logical_key', String(128)),
    col('input_version', BigInteger), col('generation', BigInteger),
    col('created_at', DateTime(timezone=True)), col('available', Boolean),
    col('state', String(24)), col('attempt_count', BigInteger),
    col('reservation_id', nullable=True), col('reservation_claim_id', nullable=True),
    col('reservation_epoch', BigInteger, nullable=True),
    col('reservation_case_version', BigInteger, nullable=True),
    col('reservation_authority_revision', BigInteger, nullable=True),
    col('reservation_at', DateTime(timezone=True), nullable=True),
    col('reservation_deadline', DateTime(timezone=True), nullable=True),
    col('reservation_core', LargeBinary, nullable=True),
    col('reservation_hash', String(64), nullable=True),
    col('reservation_record_id', nullable=True), col('reservation_event_id', nullable=True),
    col('accepted_fact_id', nullable=True), col('accepted_record_id', nullable=True),
    col('accepted_event_id', nullable=True),
    col('retry_record_id', nullable=True), col('retry_event_id', nullable=True),
    col('retry_authorization', LargeBinary, nullable=True),
    UniqueConstraint('notification_id', name='uq_notification_control_notification'),
    UniqueConstraint('case_id', 'outcome_record_id', name='uq_notification_control_outcome'),
    UniqueConstraint('logical_key', name='uq_notification_control_key'),
    ForeignKeyConstraint(['notification_work_id'], [life.work.c.work_id], name='fk_notification_control_work'),
    ForeignKeyConstraint(['case_id'], [old.case_heads.c.case_id], name='fk_notification_control_case'),
    ForeignKeyConstraint(['initial_notification_record_id'], [old.history.c.record_id],
                         name='fk_notification_control_initial'),
    ForeignKeyConstraint(['outcome_record_id'], [old.history.c.record_id], name='fk_notification_control_outcome'))

# No Domain FK: a real committed T2 mock fact survives Domain T3 rollback.
# A nullable success_work_id gives ordinary NULLS DISTINCT uniqueness, allowing
# several independently proven no-effect attempts but at most one SENT effect.
facts = Table('core_mock_notification_facts', metadata,
    col('fact_id', primary_key=True),
    *(col(name) for name in ('notification_work_id', 'notification_id', 'case_id',
                            'store_id', 'owner_id', 'reservation_id')),
    col('logical_key', String(128)), col('outcome', String(24)),
    col('profile', String(80)), col('channel', String(16)),
    *(col(name, String(64)) for name in ('profile_hash', 'payload_hash', 'intent_hash', 'reservation_hash')),
    col('reservation_core', LargeBinary), col('attempt_count', BigInteger),
    col('status', String(24)), col('success_work_id', nullable=True),
    col('accepted_at', DateTime(timezone=True)), col('fact_hash', String(64)),
    UniqueConstraint('notification_work_id', 'attempt_count', name='uq_notification_fact_attempt'),
    UniqueConstraint('reservation_id', name='uq_notification_fact_reservation'),
    UniqueConstraint('success_work_id', name='uq_notification_fact_success'))


def check(table, name, sql, expected):
    table.append_constraint(CheckConstraint(sql, name=name))
    CHECKS.setdefault(table.name, {})[name] = expected


def enum(table, prefix, name, values):
    check(table, prefix + name, name + ' IN (' + ','.join("'" + value + "'" for value in values) + ')',
          "((" + name + ")::text = ANY ((ARRAY[" + ', '.join(
              "'" + value + "'::character varying" for value in values) + "])::text[]))")


for table, prefix in ((controls, 'ck_notification_control_'), (facts, 'ck_notification_fact_')):
    for column in table.columns:
        name = column.name
        if isinstance(column.type, String) and (name.endswith('_id') or name.endswith('_hash') or name == 'logical_key'):
            hashed = name.endswith('_hash')
            pattern = ('^[0-9a-f]{64}$' if hashed else '^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$'
                       if name == 'logical_key' else '^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$')
            forbidden = '[^0-9a-f]' if hashed else '[^A-Za-z0-9_-]'
            check(table, prefix + name, f"{name} ~ '{pattern}' AND {name} !~ '{forbidden}'",
                  f"((({name})::text ~ '{pattern}'::text) AND (({name})::text !~ '{forbidden}'::text))")
        if isinstance(column.type, BigInteger):
            minimum = 0 if table is controls and name == 'attempt_count' else 1
            check(table, prefix + name, f'{name} BETWEEN {minimum} AND 9007199254740991',
                  f"(({name} >= {minimum}) AND ({name} <= '9007199254740991'::bigint))")
    enum(table, prefix, 'outcome', ('RETURN_CREATED', 'REJECTED', 'MANUAL_HANDLED'))
    enum(table, prefix, 'profile', ('return-created-mock/v2', 'rejected-mock/v2', 'manual-handled-mock/v2'))
    check(table, prefix + 'channel', "channel = 'CORE_MOCK'", "((channel)::text = 'CORE_MOCK'::text)")
enum(controls, 'ck_notification_control_', 'state',
     ('READY', 'RESERVED', 'UNKNOWN', 'NO_EFFECT_FAILED', 'SENT', 'RETAINED'))
enum(facts, 'ck_notification_fact_', 'status', ('SENT', 'NO_EFFECT_FAILED'))
check(controls, 'ck_notification_control_source',
      'available = (source_manifest IS NOT NULL)', '(available = (source_manifest IS NOT NULL))')
check(controls, 'ck_notification_control_deadline',
      'reservation_deadline > reservation_at', '(reservation_deadline > reservation_at)')
check(controls, 'ck_notification_control_reservation',
      '(attempt_count = 0) = (reservation_id IS NULL)', '((attempt_count = 0) = (reservation_id IS NULL))')
check(facts, 'ck_notification_fact_success',
      "(status = 'SENT') = (success_work_id IS NOT NULL)",
      "(((status)::text = 'SENT'::text) = (success_work_id IS NOT NULL))")
check(facts, 'ck_notification_fact_success_identity',
      'success_work_id IS NULL OR success_work_id = notification_work_id',
      '((success_work_id IS NULL) OR ((success_work_id)::text = (notification_work_id)::text))')
