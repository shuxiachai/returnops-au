"""Generated mock label PDF/result; no capability grants or data backfill."""
from alembic import op
from sqlalchemy import text
from returnops_domain.fence import acquire_fence

revision = '0013_label_artifact_result'
down_revision = '0012_label_execution'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    connection.execute(text('LOCK TABLE customer_evidence IN ACCESS EXCLUSIVE MODE'))
    from returnops_domain.lifecycle_schema import version, LABEL
    if version(connection) != LABEL:
        raise RuntimeError('Artifact upgrade requires exact complete 0012 schema')
    from returnops_domain.label_artifact_tables import metadata, GENERATED_PATTERN, NAMESPACE_CHECK
    if connection.execute(text('SELECT 1 FROM customer_evidence WHERE evidence_id ~ :pattern LIMIT 1'),
                          {'pattern':GENERATED_PATTERN}).first():
        raise RuntimeError('Reserved generated evidence namespace is occupied')
    metadata.create_all(connection)
    op.create_check_constraint(NAMESPACE_CHECK, 'customer_evidence',
                               "evidence_id !~ '^glabel_[0-9a-f]{64}$'")
    from returnops_domain.label_artifact_schema import descriptor
    if not descriptor(connection):
        raise RuntimeError('Artifact catalog does not match the exact 0013 descriptor')

def downgrade():
    raise RuntimeError('Artifact downgrade requires a separately approved data and recovery plan')
