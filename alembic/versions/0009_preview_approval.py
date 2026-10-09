"""Private preview and APPROVAL/EXECUTION intents, without grants or backfill."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0009_preview_approval'
down_revision = '0008_review_escalation'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, REVIEW
    if version(connection) != REVIEW:
        raise RuntimeError('Preview upgrade requires exact 0008 lifecycle schema')
    from returnops_domain.preview_tables import metadata
    metadata.create_all(connection)
    op.drop_constraint('ck_lifecycle_work', 'lifecycle_work', type_='check')
    op.create_check_constraint('ck_lifecycle_work', 'lifecycle_work',
        "purpose IN ('PROPOSAL','REVISION','OUTCOME','NOTIFICATION','EFFECT','REVIEW','APPROVAL','EXECUTION') "
        "AND state IN ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED') AND epoch >= 0")


def downgrade():
    raise RuntimeError('Preview downgrade requires a separately approved data plan')
