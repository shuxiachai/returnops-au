"""Additive customer-flow relational metadata, separate from immutable 0002 facts."""
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKeyConstraint, Integer, LargeBinary, MetaData, String, Table, UniqueConstraint

metadata = MetaData()
def col(name, kind, **kw): return Column(name, kind, **kw)
def table(name, *columns): return Table(name, metadata, *columns)
def ident(name, **kw): return col(name, String(80), **kw)
def blob(name, **kw): return col(name, LargeBinary, **kw)
def moment(name, **kw): return col(name, DateTime(timezone=True), **kw)
principals = table("customer_principals", ident("principal_id", primary_key=True), ident("store_id", nullable=False), col("role", String(16), nullable=False), col("enabled", Boolean, nullable=False))
sessions = table("customer_sessions", ident("session_id", primary_key=True), ident("principal_id", nullable=False), col("issued_at", BigInteger, nullable=False), col("not_before", BigInteger, nullable=False), col("expires_at", BigInteger, nullable=False), col("revoked", Boolean, nullable=False))
case_heads = table("case_heads", ident("case_id", primary_key=True), ident("owner_principal_id", nullable=False), ident("store_id", nullable=False), col("case_version", BigInteger, nullable=False), col("input_version", BigInteger, nullable=False), col("status", String(32), nullable=False), moment("created_at", nullable=False), moment("updated_at", nullable=False), col("history_sequence", BigInteger, nullable=False), col("audit_sequence", BigInteger, nullable=False), col("audit_head", String(64)), ident("current_question_set_id"), col("available", Boolean, nullable=False))
acceptances = table("customer_acceptances", ident("acceptance_id", primary_key=True), ident("principal_id", nullable=False), ident("store_id", nullable=False), col("method", String(8), nullable=False), col("operation", String(80), nullable=False), col("target", String(80), nullable=False), col("request_key", String(128), nullable=False), col("fingerprint", String(64), nullable=False), col("resource_kind", String(16), nullable=False), ident("resource_id", nullable=False), moment("accepted_at", nullable=False), col("response_status", Integer, nullable=False), UniqueConstraint("principal_id", "method", "operation", "target", "request_key", name="uq_customer_acceptance_scope"))
receipts = table("customer_receipts", ident("acceptance_id", primary_key=True), blob("body"), col("available", Boolean, nullable=False))
receipt_refs = table("customer_receipt_refs", ident("acceptance_id", primary_key=True), col("kind", String(32), primary_key=True), ident("object_id", primary_key=True))
history = table("customer_history_revisions", ident("record_id", primary_key=True), ident("case_id", nullable=False), col("kind", String(32), nullable=False), ident("object_id", nullable=False), col("object_version", BigInteger, nullable=False), col("case_version", BigInteger, nullable=False), col("recorded_sequence", BigInteger, nullable=False), moment("recorded_at", nullable=False), col("content_sha256", String(64), nullable=False), col("retention_state", String(16), nullable=False), col("removal_reason", String(24)), UniqueConstraint("case_id", "recorded_sequence", name="uq_customer_history_sequence"), UniqueConstraint("case_id", "kind", "object_id", "object_version", name="uq_customer_history_revision"))
history_contents = table("customer_history_contents", ident("record_id", primary_key=True), blob("body", nullable=False))
evidence = table("customer_evidence", ident("evidence_id", primary_key=True), ident("uploader_id", nullable=False), ident("store_id", nullable=False), ident("case_id"), blob("filename", nullable=False), blob("description"), col("media_type", String(64), nullable=False), col("size_bytes", BigInteger, nullable=False), col("sha256", String(64), nullable=False), col("status", String(16), nullable=False), moment("created_at", nullable=False), moment("expires_at"), col("available", Boolean, nullable=False))
evidence_contents = table("customer_evidence_contents", ident("evidence_id", primary_key=True), blob("body", nullable=False))
questions = table("customer_clarification_sets", ident("question_set_id", primary_key=True), ident("case_id", nullable=False), col("input_version", BigInteger, nullable=False), blob("questions", nullable=False))
snapshots = table("customer_history_snapshots", ident("snapshot_id", primary_key=True), ident("principal_id", nullable=False), col("role", String(16), nullable=False), ident("store_id", nullable=False), ident("case_id", nullable=False), col("case_version", BigInteger, nullable=False), col("highwater", BigInteger, nullable=False), moment("as_of", nullable=False), moment("expires_at", nullable=False))
cursors = table("customer_history_cursors", col("cursor_hash", String(64), primary_key=True), ident("snapshot_id", nullable=False), col("kind", String(32), nullable=False), col("page_limit", Integer, nullable=False), ident("object_id"), col("object_version", BigInteger), col("last_sequence", BigInteger, nullable=False), ident("last_record_id"))
audit = table("customer_audit_events", ident("event_id", primary_key=True), ident("case_id", nullable=False), col("sequence", BigInteger, nullable=False), col("event_hash", String(64), nullable=False), blob("body", nullable=False), UniqueConstraint("case_id", "sequence", name="uq_customer_audit_sequence"))

# Durable intake work is separate from the immutable acceptance receipt. A
# controlled processor claims it after acceptance; replay never creates work.
intake_sessions = table("customer_intake_sessions", ident("intake_session_id", primary_key=True), ident("case_id", nullable=False, unique=True), col("input_version", BigInteger, nullable=False), col("status", String(32), nullable=False), ident("current_work_id"), moment("updated_at", nullable=False))
intake_work = table("customer_intake_work", ident("work_id", primary_key=True), ident("case_id", nullable=False), ident("acceptance_id", nullable=False, unique=True), col("input_version", BigInteger, nullable=False), col("phase", String(24), nullable=False), col("state", String(24), nullable=False), ident("claim_id"), moment("created_at", nullable=False), moment("claimed_at"), moment("lease_expires_at"), moment("completed_at"))

intake_sessions.append_column(col("clarification_round", BigInteger, nullable=False))
intake_sessions.append_column(col("internal_revision", BigInteger, nullable=False))
for name, kind, nullable in (
    ("accepted_case_version", BigInteger, False), ("accepted_principal_id", String(80), False),
    ("accepted_owner_id", String(80), False), ("accepted_store_id", String(80), False),
    ("processor_version", String(80), False), ("source_refs", LargeBinary, False),
    ("claim_epoch", BigInteger, False), ("failure_count", Integer, False),
    ("next_attempt_at", DateTime(timezone=True), False), ("safe_error", String(80), True),
): intake_work.append_column(col(name, kind, nullable=nullable))
intake_work.append_constraint(UniqueConstraint("case_id", "input_version", "phase", name="uq_customer_intake_generation"))
questions.append_column(blob("question_kinds", nullable=False))
case_heads.append_column(ident("current_failure_id"))
processing_failures = table("customer_processing_failures", ident("failure_id", primary_key=True), ident("case_id", nullable=False), col("input_version", BigInteger, nullable=False), blob("body", nullable=False), moment("occurred_at", nullable=False))

# This reference-only stub never creates or alters the frozen 0002 table.
legacy_cases = Table("case_records", metadata, ident("case_id", primary_key=True))
CUSTOMER_TABLES = [value for name, value in metadata.tables.items() if name != "case_records"]
for child, column, parent, parent_column in (
    (sessions, "principal_id", principals, "principal_id"),
    (case_heads, "case_id", legacy_cases, "case_id"),
    (receipts, "acceptance_id", acceptances, "acceptance_id"),
    (receipt_refs, "acceptance_id", acceptances, "acceptance_id"),
    (history, "case_id", case_heads, "case_id"),
    (history_contents, "record_id", history, "record_id"),
    (evidence, "case_id", case_heads, "case_id"),
    (evidence_contents, "evidence_id", evidence, "evidence_id"),
    (questions, "case_id", case_heads, "case_id"),
    (snapshots, "case_id", case_heads, "case_id"),
    (cursors, "snapshot_id", snapshots, "snapshot_id"),
    (audit, "case_id", case_heads, "case_id"),
    (intake_sessions, "case_id", case_heads, "case_id"),
    (intake_work, "case_id", case_heads, "case_id"),
    (intake_work, "acceptance_id", acceptances, "acceptance_id"),
    (processing_failures, "case_id", case_heads, "case_id"),
):
    child.append_constraint(ForeignKeyConstraint([column], [parent.c[parent_column]]))

for table_ in CUSTOMER_TABLES:
    for column in table_.columns:
        if column.name.endswith("_id") and column.name not in {"acceptance_id"}:
            table_.append_constraint(CheckConstraint(
                f"{column.name} IS NULL OR ({column.name} ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{2,79}}$' AND {column.name} !~ '[^A-Za-z0-9_-]')",
                name=f"ck_{table_.name}_{column.name}",
            ))
        if column.name in {"case_version", "input_version", "object_version"}:
            table_.append_constraint(CheckConstraint(f"{column.name} IS NULL OR {column.name} BETWEEN 1 AND 9007199254740991", name=f"ck_{table_.name}_{column.name}_range"))
principals.append_constraint(CheckConstraint("role IN ('CUSTOMER','FOUNDER')", name="ck_customer_role"))
sessions.append_constraint(CheckConstraint("issued_at >= 0 AND issued_at <= not_before AND not_before < expires_at AND expires_at - issued_at <= 900", name="ck_customer_session_window"))
case_heads.append_constraint(CheckConstraint("history_sequence >= 0 AND audit_sequence >= 0", name="ck_customer_head_sequences"))
evidence.append_constraint(CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="ck_customer_evidence_size"))
evidence.append_constraint(CheckConstraint("(status = 'STAGED' AND case_id IS NULL AND expires_at IS NOT NULL) OR (status = 'BOUND' AND case_id IS NOT NULL AND expires_at IS NULL)", name="ck_customer_evidence_binding"))
receipts.append_constraint(CheckConstraint("(available AND body IS NOT NULL) OR (NOT available AND body IS NULL)", name="ck_customer_receipt_availability"))
history.append_constraint(CheckConstraint("(retention_state = 'AVAILABLE' AND removal_reason IS NULL) OR (retention_state IN ('REDACTED','DELETED') AND removal_reason IN ('RETENTION_POLICY','OWNER_REQUEST'))", name="ck_customer_history_retention"))
cursors.append_constraint(CheckConstraint("page_limit BETWEEN 1 AND 100 AND last_sequence >= 0 AND (object_version IS NULL OR object_id IS NOT NULL)", name="ck_customer_cursor_query"))

intake_sessions.append_constraint(CheckConstraint("clarification_round >= 0 AND internal_revision >= 1 AND status IN ('SUBMITTED','EVALUATING','AWAITING_CLARIFICATION','CLARIFICATION_RECEIVED','COMPLETE','ESCALATED_FAILURE')", name="ck_customer_intake_session_state"))
intake_work.append_constraint(CheckConstraint("phase = 'INTAKE' AND failure_count >= 0 AND claim_epoch >= 0 AND accepted_case_version >= 1 AND state IN ('PENDING','RUNNING','DONE','PAUSED','SUPERSEDED','FAILED')", name="ck_customer_intake_work_state"))
intake_work.append_constraint(CheckConstraint("state <> 'RUNNING' OR (claim_id IS NOT NULL AND lease_expires_at IS NOT NULL AND claim_epoch > 0)", name="ck_customer_intake_claim"))
