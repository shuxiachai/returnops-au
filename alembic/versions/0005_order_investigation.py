"""Explicit future-only investigation work; preserve all accepted legacy records."""
from alembic import op
from returnops_domain.fence import acquire_fence
from returnops_domain.investigation_tables import metadata
revision = '0005_order_investigation'
down_revision = '0004_pre_case_audit'
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    metadata.create_all(connection, checkfirst=False)

def downgrade():
    raise RuntimeError('Investigation downgrade requires a separately approved data plan')
