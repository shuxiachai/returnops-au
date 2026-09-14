"""Establish the migration baseline only; no business tables.

F.02 / NFR-006/007, docs/02 infrastructure view. A1.02 remains separate.
"""
revision = "0001_environment"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
