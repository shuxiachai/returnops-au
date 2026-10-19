"""Customer flow additions; preserve immutable 0002 records and import provenance."""
from alembic import op
from returnops_domain.customer_tables import metadata, CUSTOMER_TABLES
from returnops_domain.fence import acquire_fence
from returnops_domain.legacy_import import import_legacy

revision = "0003_customer_flow"
down_revision = "0002_initial_records"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    metadata.create_all(connection, tables=CUSTOMER_TABLES, checkfirst=False)
    import_legacy(connection)

def downgrade():
    raise RuntimeError("Customer-flow downgrade requires a separately approved data plan")
