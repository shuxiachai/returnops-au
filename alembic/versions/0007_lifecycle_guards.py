"""A1.03 reference and claim metadata; no source-body or old-state rewrites."""
from alembic import op
from returnops_domain.fence import acquire_fence
from returnops_domain.lifecycle_tables import metadata

revision = '0007_lifecycle_guards'
down_revision = '0006_founder_reads'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    metadata.create_all(connection, checkfirst=False)


def downgrade():
    raise RuntimeError('Lifecycle downgrade requires a separately approved data plan')
