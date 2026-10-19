"""Private first-operation identity sidecar; no grant, backfill, claim or effect."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0010_execution_preparation'
down_revision = '0009_preview_approval'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, APPROVAL
    if version(connection) != APPROVAL:
        raise RuntimeError('Preparation upgrade requires exact 0009 approval schema')
    from returnops_domain.execution_preparation_tables import metadata
    metadata.create_all(connection)


def downgrade():
    raise RuntimeError('Preparation downgrade requires a separately approved data plan')
