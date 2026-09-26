"""Add internal pre-case scope chains without altering case AuditEvent contracts."""
from alembic import op
from returnops_domain.fence import acquire_fence
from returnops_domain.scope_audit import metadata
revision = "0004_pre_case_audit"
down_revision = "0003_customer_flow"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    metadata.create_all(connection, checkfirst=False)

def downgrade():
    raise RuntimeError("Scope audit downgrade requires a separately approved data plan")
