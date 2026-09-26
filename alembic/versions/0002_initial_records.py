"""A1.02 initial records and separately held personal statement content.

The existing environment revision is retained. No transitions or deletion
policy are implemented. This migration remains confined to disposable DBs.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_initial_records"
down_revision = "0001_environment"
branch_labels = None
depends_on = None


def _id_check(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{name} ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{2,79}}$' AND {name} !~ '[^A-Za-z0-9_-]'", name=f"ck_{name}_format")


def upgrade() -> None:
    op.create_table(
        "case_records",
        sa.Column("case_id", sa.String(80), primary_key=True),
        sa.Column("owner_principal_id", sa.String(80), nullable=False),
        sa.Column("store_id", sa.String(80), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _id_check("case_id"), _id_check("owner_principal_id"), _id_check("store_id"),
        sa.CheckConstraint("case_version = 1 AND input_version = 1", name="ck_case_initial_versions"),
        sa.CheckConstraint("status = 'SUBMITTED'", name="ck_case_initial_status"),
        sa.CheckConstraint("created_at = updated_at", name="ck_case_initial_time"),
    )
    op.create_table(
        "original_statement_records",
        sa.Column("statement_id", sa.String(80), primary_key=True),
        sa.Column("case_id", sa.String(80), sa.ForeignKey("case_records.case_id"), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("object_version", sa.Integer(), nullable=False),
        sa.Column("accepted_case_version", sa.Integer(), nullable=False),
        sa.Column("accepted_input_version", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        _id_check("statement_id"),
        sa.CheckConstraint("kind = 'ORIGINAL'", name="ck_statement_original_kind"),
        sa.CheckConstraint("object_version = 1 AND accepted_case_version = 1 AND accepted_input_version = 1", name="ck_statement_initial_versions"),
    )
    op.create_table(
        "original_statement_contents",
        sa.Column("statement_id", sa.String(80), sa.ForeignKey("original_statement_records.statement_id"), primary_key=True),
        sa.Column("raw_text", sa.LargeBinary(), nullable=False),
        sa.Column("requested_outcome", sa.String(16), nullable=False),
        sa.Column("original_order_reference", sa.LargeBinary(), nullable=True),
        # Byte bounds are defence in depth. Exact codepoint lengths and the
        # reversible surrogatepass codec are validated by the internal domain.
        sa.CheckConstraint("octet_length(raw_text) BETWEEN 1 AND 48000", name="ck_content_raw_bytes"),
        sa.CheckConstraint("original_order_reference IS NULL OR octet_length(original_order_reference) BETWEEN 1 AND 480", name="ck_content_order_bytes"),
        sa.CheckConstraint("requested_outcome IN ('REFUND', 'REPLACEMENT', 'REPAIR', 'RETURN', 'INFORMATION', 'UNSPECIFIED', 'OTHER')", name="ck_content_outcome"),
    )


def downgrade() -> None:
    # An automatic downgrade must not destroy accepted records or their content.
    raise RuntimeError("Initial record downgrade requires a separately approved data plan")
