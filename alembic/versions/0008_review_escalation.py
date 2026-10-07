"""REVIEW-only capability CHECK; frozen 0007 metadata remains unchanged."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0008_review_escalation'
down_revision = '0007_lifecycle_guards'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, LEGACY
    if version(connection) != LEGACY:
        raise RuntimeError('REVIEW upgrade requires exact legacy lifecycle schema')
    op.drop_constraint('ck_lifecycle_work', 'lifecycle_work', type_='check')
    # Self-contained frozen DDL: do not import current/legacy metadata here.
    op.create_check_constraint('ck_lifecycle_work', 'lifecycle_work',
        "purpose IN ('PROPOSAL','REVISION','OUTCOME','NOTIFICATION','EFFECT','REVIEW') "
        "AND state IN ('PENDING','RUNNING','DONE','SUPERSEDED','PAUSED') AND epoch >= 0")


def downgrade():
    raise RuntimeError('REVIEW downgrade requires a separately approved data plan')
