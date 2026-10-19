"""Private CREATE_RETURN control, provider permission and independent mock fact."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0011_return_execution'
down_revision = '0010_execution_preparation'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, PREPARATION
    if version(connection) != PREPARATION:
        raise RuntimeError('Execution upgrade requires exact complete 0010 schema')
    from returnops_domain.return_execution_tables import metadata
    metadata.create_all(connection)


def downgrade():
    raise RuntimeError('Execution downgrade requires a separately approved data and recovery plan')
