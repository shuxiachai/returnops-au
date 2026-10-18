"""0013 metadata, independent of the frozen customer and 0012 DDL."""
from sqlalchemy import (MetaData, Table, String, BigInteger, Boolean, DateTime,
    LargeBinary, UniqueConstraint, ForeignKeyConstraint)
from . import customer_tables as old
from .label_execution_tables import artifact_work
from .label_execution_tables import col

metadata = MetaData()
CHECKS = {}
NAMESPACE_CHECK = 'ck_customer_evidence_generated_namespace'
GENERATED_PATTERN = '^glabel_[0-9a-f]{64}$'

permissions = Table('label_artifact_permissions', metadata,
    *(col(n, primary_key=True) for n in ('store_id','component_id','provider_id','config_id','pdf_profile_id')),
    col('profile_hash', String(64)), col('revision', BigInteger),
    col('read_existing_enabled', Boolean), col('store_enabled', Boolean))

controls = Table('lifecycle_label_artifact_controls', metadata,
    col('work_id', primary_key=True), col('source_manifest_hash', String(64)),
    col('profile_hash', String(64)), col('recovery_binding_hash', String(64)),
    col('state', String(16)), col('epoch', BigInteger), col('active_claim_id', nullable=True),
    col('completed_evidence_id', nullable=True), col('safe_failure_code', String(32), nullable=True),
    col('source_withdrawal_receipt', LargeBinary, nullable=True),
    ForeignKeyConstraint(['work_id'], [artifact_work.c.work_id], name='fk_lartifact_control_work'))

claims = Table('lifecycle_label_artifact_claims', metadata,
    col('claim_id', primary_key=True), col('work_id'), col('epoch', BigInteger),
    *(col(n, String(64)) for n in ('source_manifest_hash','recovery_binding_hash')),
    col('principal_id'), col('session_id'),
    *(col(n, BigInteger) for n in ('service_authority_revision','artifact_permission_revision',
        'claimed_case_version','claimed_input_version','claimed_generation')),
    col('claimed_head_hash', String(64)), col('claimed_source_snapshot_hash', String(64)),
    col('issued_at', DateTime(timezone=True)), col('lease_expires_at', DateTime(timezone=True)),
    col('claim_hash', String(64)),
    UniqueConstraint('work_id','epoch', name='uq_lartifact_claim_epoch'),
    UniqueConstraint('work_id','claim_id', name='uq_lartifact_claim_pair'),
    ForeignKeyConstraint(['work_id'], [controls.c.work_id], name='fk_lartifact_claim_work'))

artifacts = Table('generated_label_artifacts', metadata,
    col('evidence_id', primary_key=True), col('work_id'), col('completion_id'), col('completion_claim_id'),
    col('core', LargeBinary), col('certificate', LargeBinary),
    *(col(n, String(64)) for n in ('core_hash','completion_hash','source_manifest_hash','profile_hash','sha256')),
    col('size_bytes', BigInteger), col('media_type', String(32)), col('filename', String(80)),
    col('evidence_record_id'), col('result_record_id'), col('evidence_audit_id'), col('result_audit_id'),
    col('evidence_audit_hash', String(64)), col('result_audit_hash', String(64)),
    col('completed_case_version', BigInteger), col('completed_at', DateTime(timezone=True)),
    col('available', Boolean), col('retention_state', String(16)), col('removal_reason', String(32), nullable=True),
    col('pdf_retention_receipt', LargeBinary, nullable=True), col('source_withdrawal_receipt', LargeBinary, nullable=True),
    *(UniqueConstraint(n, name='uq_generated_label_'+n) for n in
      ('work_id','completion_id','evidence_record_id','result_record_id','evidence_audit_id','result_audit_id')),
    UniqueConstraint('work_id','evidence_id', name='uq_generated_label_pair'),
    ForeignKeyConstraint(['work_id'], [controls.c.work_id], name='fk_generated_label_work'),
    ForeignKeyConstraint(['work_id','completion_claim_id'], [claims.c.work_id,claims.c.claim_id], name='fk_generated_label_claim'),
    *(ForeignKeyConstraint([n], [old.history.c.record_id], name='fk_generated_label_'+n)
      for n in ('evidence_record_id','result_record_id')),
    *(ForeignKeyConstraint([n], [old.audit.c.event_id], name='fk_generated_label_'+n)
      for n in ('evidence_audit_id','result_audit_id')))

contents = Table('generated_label_artifact_contents', metadata,
    col('evidence_id', primary_key=True), col('body', LargeBinary),
    ForeignKeyConstraint(['evidence_id'], [artifacts.c.evidence_id], name='fk_generated_label_body'))

controls.append_constraint(ForeignKeyConstraint(['work_id','active_claim_id'],
    [claims.c.work_id,claims.c.claim_id], name='fk_lartifact_active_claim', use_alter=True))
controls.append_constraint(ForeignKeyConstraint(['work_id','completed_evidence_id'],
    [artifacts.c.work_id,artifacts.c.evidence_id], name='fk_lartifact_completed', use_alter=True))

def check(table, name, sql, expected):
    from sqlalchemy import CheckConstraint
    table.append_constraint(CheckConstraint(sql, name=name))
    CHECKS.setdefault(table.name,{})[name] = expected

def enum(table, prefix, name, values):
    sql = name + ' IN (' + ','.join("'" + v + "'" for v in values) + ')'
    expression = "((" + name + ")::text = ANY ((ARRAY[" + ', '.join(
        "'" + v + "'::character varying" for v in values) + "])::text[]))"
    check(table, prefix + name, sql, expression)

for table, prefix in ((permissions,'ck_lartp_'),(controls,'ck_lartc_'),(claims,'ck_lartq_'),
                       (artifacts,'ck_larta_'),(contents,'ck_lartb_')):
    CHECKS.setdefault(table.name,{})
    for column in table.columns:
        n=column.name
        if isinstance(column.type,String) and (n.endswith('_id') or n.endswith('_hash') or n=='sha256'):
            hashed=n.endswith('_hash') or n=='sha256'
            pattern='^[0-9a-f]{64}$' if hashed else GENERATED_PATTERN if n in {'evidence_id','completed_evidence_id'} else '^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$'
            forbidden='[^0-9a-f]' if hashed else '[^A-Za-z0-9_-]'
            check(table,prefix+n,f"{n} ~ '{pattern}' AND {n} !~ '{forbidden}'",
                f"((({n})::text ~ '{pattern}'::text) AND (({n})::text !~ '{forbidden}'::text))")
        if isinstance(column.type,BigInteger):
            minimum=0 if n=='epoch' and table is controls else 1
            maximum=65536 if n=='size_bytes' else 9007199254740991
            literal=str(maximum) if maximum==65536 else "'9007199254740991'::bigint"
            check(table,prefix+n,f'{n} BETWEEN {minimum} AND {maximum}',f'(({n} >= {minimum}) AND ({n} <= {literal}))')
enum(controls,'ck_lartc_','state',('PENDING','RUNNING','DONE','RETAINED'))
enum(artifacts,'ck_larta_','retention_state',('AVAILABLE','DELETED','REDACTED'))
enum(artifacts,'ck_larta_','removal_reason',('RETENTION_POLICY','OWNER_REQUEST'))
check(claims,'ck_lartq_deadline','lease_expires_at > issued_at','(lease_expires_at > issued_at)')
check(controls,'ck_lartc_active',"(state = 'RUNNING') = (active_claim_id IS NOT NULL)","(((state)::text = 'RUNNING'::text) = (active_claim_id IS NOT NULL))")
check(controls,'ck_lartc_done',"state <> 'DONE' OR completed_evidence_id IS NOT NULL","(((state)::text <> 'DONE'::text) OR (completed_evidence_id IS NOT NULL))")
check(artifacts,'ck_larta_available',"available = (retention_state = 'AVAILABLE')","(available = ((retention_state)::text = 'AVAILABLE'::text))")
check(artifacts,'ck_larta_reason','available = (removal_reason IS NULL)','(available = (removal_reason IS NULL))')
check(artifacts,'ck_larta_type',"media_type = 'application/pdf'","((media_type)::text = 'application/pdf'::text)")
