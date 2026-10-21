"""Private SQL label fact and artifact-only pending intent; no grants/backfill."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0012_label_execution'
down_revision = '0011_return_execution'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, EXECUTION
    if version(connection) != EXECUTION:
        raise RuntimeError('Label upgrade requires exact complete 0011 schema')
    from returnops_domain.label_execution_tables import metadata
    metadata.create_all(connection)


def downgrade():
    raise RuntimeError('Label downgrade requires a separately approved data and recovery plan')
