"""F.05 read metadata; existing facts/history/audit remain byte-for-byte intact."""
from alembic import op
from returnops_domain.fence import acquire_fence
from returnops_domain.founder_tables import metadata
from returnops_domain.founder_integrity import register_existing_block_encodings

revision = '0006_founder_reads'
down_revision = '0005_order_investigation'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    metadata.create_all(connection, checkfirst=False)
    register_existing_block_encodings(connection)


def downgrade():
    raise RuntimeError('Founder read downgrade requires a separately approved data plan')
