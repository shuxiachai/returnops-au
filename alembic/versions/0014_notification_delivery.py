"""Fresh versioned notification delivery. Existing v1 messages remain HOLD."""
from alembic import op
from returnops_domain.fence import acquire_fence

revision = '0014_notification_delivery'
down_revision = '0013_label_artifact_result'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    acquire_fence(connection, write=True)
    from returnops_domain.lifecycle_schema import version, ARTIFACT
    if version(connection) != ARTIFACT:
        raise RuntimeError('Notification upgrade requires exact complete0013 schema')
    from returnops_domain.notification_tables import metadata
    metadata.create_all(connection)
    from returnops_domain.notification_schema import descriptor
    if not descriptor(connection):
        raise RuntimeError('Notification catalog does not match exact0014 descriptor')
    # Two empty tables only: no prior intent/body/owner/key/attempt/status
    # rewrite; no provider facts, authority grants, control or send backfill.


def downgrade():
    raise RuntimeError('Notification downgrade requires a separately approved data and recovery plan')
