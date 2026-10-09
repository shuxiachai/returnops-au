"""Real PostgreSQL 17 acceptance; requires explicit disposable DB, never skips."""

from dataclasses import asdict, replace
from pathlib import Path
import traceback

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from returnops_domain import DomainValidationError
from returnops_domain.storage import (
    CommitOutcomeUnknown, DuplicateRecordError, InitialRecordUnitOfWork, StorageError,
    case_records, original_statement_contents, original_statement_records,
)


pytestmark = pytest.mark.database
ROOT = Path(__file__).resolve().parents[2]


def assert_absent(engine, bundle):
    # A fresh connection observes committed database state, not identity maps.
    with engine.connect() as connection:
        for table, column, value in (
            (case_records, case_records.c.case_id, bundle.case.case_id),
            (original_statement_records, original_statement_records.c.statement_id, bundle.statement.statement_id),
            (original_statement_contents, original_statement_contents.c.statement_id, bundle.statement.statement_id),
        ):
            assert connection.execute(select(table).where(column == value)).first() is None


def committed(engine, bundle):
    with InitialRecordUnitOfWork(engine) as unit:
        unit.repository.insert_initial_record(bundle)
        unit.commit()


def read(engine, case_id):
    with InitialRecordUnitOfWork(engine) as unit:
        return unit.repository.load_initial_record(case_id)


@pytest.mark.parametrize("reference", [None, "\x00ORDER\r\n\udfff"])
def test_commit_read_independent_connection_preserves_exact_content(pg_engine, bundle_factory, reference):
    bundle = bundle_factory(reference=reference)
    committed(pg_engine, bundle)
    assert read(pg_engine, bundle.case.case_id) == bundle
    assert read(pg_engine, "case_missing") is None
    with pg_engine.connect() as connection:
        content = connection.execute(select(original_statement_contents).where(original_statement_contents.c.statement_id == bundle.statement.statement_id)).mappings().one()
        assert bytes(content["raw_text"]) == bundle.content.raw_text.encode("utf-8", "surrogatepass")
        assert content["original_order_reference"] is None if reference is None else bytes(content["original_order_reference"]) == reference.encode("utf-8", "surrogatepass")


def test_repeat_migration_preserves_committed_data_and_exact_schema(pg_engine, bundle_factory):
    bundle = bundle_factory()
    committed(pg_engine, bundle)
    expected = ['accepted_order_contents', 'accepted_order_projections', 'alembic_version', 'case_heads', 'case_investigation_state', 'case_records', 'customer_acceptances', 'customer_audit_events', 'customer_clarification_sets', 'customer_evidence', 'customer_evidence_contents', 'customer_history_contents', 'customer_history_cursors', 'customer_history_revisions', 'customer_history_snapshots', 'customer_intake_sessions', 'customer_intake_work', 'customer_principals', 'customer_processing_failures', 'customer_receipt_refs', 'customer_receipts', 'customer_scope_audit_events', 'customer_scope_audit_heads', 'customer_sessions', 'discarded_order_invocations', 'founder_history_encodings', 'founder_list_members', 'founder_read_cursors', 'founder_read_snapshots', 'investigation_clarification_inputs', 'investigation_inputs', 'investigation_policy_events', 'investigation_provider_grants', 'investigation_question_groups', 'investigation_services', 'investigation_work', 'order_lookup_blocks', 'order_lookup_contents', 'order_lookup_receipts', 'original_statement_contents', 'original_statement_records']
    expected = sorted(expected + ['case_lifecycle_state', 'lifecycle_authorities', 'lifecycle_work', 'lifecycle_source_bindings', 'lifecycle_event_receipts', 'lifecycle_effect_refs', 'lifecycle_action_previews'])
    for _ in range(2):
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        assert sorted(inspect(pg_engine).get_table_names(schema="public")) == expected
        assert read(pg_engine, bundle.case.case_id) == bundle
    # Accepted versions are historical facts: the FK references case ID only.
    foreign_keys = inspect(pg_engine).get_foreign_keys("original_statement_records")
    assert [(fk["constrained_columns"], fk["referred_columns"]) for fk in foreign_keys] == [(["case_id"], ["case_id"])]


def test_leaving_without_commit_or_raising_rolls_back_all_three_tables(pg_engine, bundle_factory):
    first = bundle_factory()
    with InitialRecordUnitOfWork(pg_engine) as unit:
        unit.repository.insert_initial_record(first)
        assert unit.repository.load_initial_record(first.case.case_id) == first
    assert_absent(pg_engine, first)
    second = bundle_factory()
    with pytest.raises(RuntimeError, match="synthetic application failure"):
        with InitialRecordUnitOfWork(pg_engine) as unit:
            unit.repository.insert_initial_record(second)
            raise RuntimeError("synthetic application failure")
    assert_absent(pg_engine, second)


@pytest.mark.parametrize("fail_at", [2, 3])
def test_failure_before_later_writes_poison_uow_and_leave_no_remnants(pg_engine, bundle_factory, caplog, fail_at):
    bundle = bundle_factory(raw_text="PRIVATE_BODY", reference="PRIVATE_ORDER")
    insert_count = 0

    def fail(connection, cursor, statement, parameters, context, executemany):
        nonlocal insert_count
        if statement.startswith("INSERT"):
            insert_count += 1
            if insert_count == fail_at:
                raise SQLAlchemyError("PRIVATE_BODY PRIVATE_ORDER postgresql://private:PRIVATE_DSN@host/db")

    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        with InitialRecordUnitOfWork(pg_engine) as unit:
            with pytest.raises(StorageError) as caught:
                unit.repository.insert_initial_record(bundle)
            assert caught.value.__context__ is None and caught.value.__cause__ is None
            output = repr(caught.value) + str(caught.value) + "".join(traceback.format_exception(caught.value)) + caplog.text
            assert all(secret not in output for secret in ("PRIVATE_BODY", "PRIVATE_ORDER", "PRIVATE_DSN"))
            with pytest.raises(StorageError, match="cannot commit"):
                unit.commit()
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert insert_count == fail_at
    assert_absent(pg_engine, bundle)


def test_duplicate_is_safe_conflict_and_not_replay_success(pg_engine, bundle_factory, caplog):
    bundle = bundle_factory(raw_text="PRIVATE_BODY", reference="PRIVATE_ORDER")
    committed(pg_engine, bundle)
    with pytest.raises(DuplicateRecordError) as caught:
        with InitialRecordUnitOfWork(pg_engine) as unit:
            unit.repository.insert_initial_record(bundle)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    output = repr(caught.value) + "".join(traceback.format_exception(caught.value)) + caplog.text
    assert "PRIVATE_BODY" not in output and "PRIVATE_ORDER" not in output
    assert read(pg_engine, bundle.case.case_id) == bundle


@pytest.mark.parametrize("field,value", [
    ("case_id", "x"), ("case_id", "valid_id\n"), ("owner_principal_id", "!invalid"),
    ("store_id", "ééé"), ("case_version", 0), ("case_version", 2),
    ("input_version", 0), ("input_version", 2), ("status", "APPROVED"),
])
def test_database_case_constraints(pg_engine, bundle_factory, field, value):
    values = asdict(bundle_factory().case)
    values[field] = value
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(IntegrityError):
                connection.execute(case_records.insert(), values)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("field,value", [
    ("statement_id", "x"), ("case_id", "case_orphan"), ("kind", "CLARIFICATION"),
    ("object_version", 0), ("object_version", 2), ("accepted_case_version", 0),
    ("accepted_case_version", 2), ("accepted_input_version", 0), ("accepted_input_version", 2),
])
def test_database_statement_constraints(pg_engine, bundle_factory, field, value):
    bundle = bundle_factory()
    values = asdict(bundle.statement)
    values[field] = value
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(case_records.insert(), asdict(bundle.case))
            with pytest.raises(IntegrityError):
                connection.execute(original_statement_records.insert(), values)
        finally:
            transaction.rollback()


def test_only_one_original_statement_per_case(pg_engine, bundle_factory):
    bundle = bundle_factory()
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(case_records.insert(), asdict(bundle.case))
            connection.execute(original_statement_records.insert(), asdict(bundle.statement))
            values = asdict(bundle.statement)
            values["statement_id"] = "statement_another"
            with pytest.raises(IntegrityError):
                connection.execute(original_statement_records.insert(), values)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("patch", [
    {"statement_id": "statement_orphan"}, {"raw_text": b""},
    {"raw_text": b"x" * 48001}, {"original_order_reference": b""},
    {"original_order_reference": b"x" * 481}, {"requested_outcome": "INVALID"},
])
def test_database_content_constraints(pg_engine, bundle_factory, patch):
    bundle = bundle_factory()
    values = {"statement_id": bundle.statement.statement_id, "raw_text": b"original", "requested_outcome": "OTHER", "original_order_reference": None}
    values.update(patch)
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(case_records.insert(), asdict(bundle.case))
            connection.execute(original_statement_records.insert(), asdict(bundle.statement))
            with pytest.raises(IntegrityError):
                connection.execute(original_statement_contents.insert(), values)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("content", [None, b"\xff"])
def test_missing_or_corrupt_content_is_explicit_failure_not_empty_or_tombstone(pg_engine, bundle_factory, content):
    bundle = bundle_factory()
    with InitialRecordUnitOfWork(pg_engine) as unit:
        connection = unit._connection
        connection.execute(case_records.insert(), asdict(bundle.case))
        connection.execute(original_statement_records.insert(), asdict(bundle.statement))
        if content is not None:
            connection.execute(original_statement_contents.insert(), {"statement_id": bundle.statement.statement_id, "raw_text": content, "requested_outcome": "OTHER"})
        with pytest.raises(StorageError) as caught:
            unit.repository.load_initial_record(bundle.case.case_id)
        assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert_absent(pg_engine, bundle)


def test_invalid_bundle_bypass_is_rejected_before_any_insert(pg_engine, bundle_factory):
    bundle = bundle_factory()
    object.__setattr__(bundle.statement, "case_id", "case_other")
    with InitialRecordUnitOfWork(pg_engine) as unit:
        with pytest.raises(DomainValidationError):
            unit.repository.insert_initial_record(bundle)
        with pytest.raises(StorageError):
            unit.commit()
    assert_absent(pg_engine, bundle)


@pytest.mark.parametrize("server_committed", [False, True])
def test_real_commit_acknowledgement_failure_never_retries_or_claims_rollback(pg_engine, bundle_factory, monkeypatch, server_committed):
    bundle = bundle_factory()
    with pytest.raises(CommitOutcomeUnknown) as caught:
        with InitialRecordUnitOfWork(pg_engine) as unit:
            unit.repository.insert_initial_record(bundle)
            transaction_type = type(unit._transaction)
            original_commit = transaction_type.commit

            def lost_ack(transaction):
                if transaction is unit._transaction:
                    if server_committed:
                        original_commit(transaction)
                    raise SQLAlchemyError("PRIVATE_BODY PRIVATE_DSN")
                return original_commit(transaction)

            with monkeypatch.context() as scoped:
                scoped.setattr(transaction_type, "commit", lost_ack)
                unit.commit()
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "unknown" in str(caught.value)
    if server_committed:
        assert read(pg_engine, bundle.case.case_id) == bundle
    else:
        assert_absent(pg_engine, bundle)


def test_caught_invalid_read_prevents_commit_of_pending_valid_inserts(pg_engine, bundle_factory):
    bundle = bundle_factory()
    with InitialRecordUnitOfWork(pg_engine) as unit:
        unit.repository.insert_initial_record(bundle)
        with pytest.raises(DomainValidationError):
            unit.repository.load_initial_record("x")
        with pytest.raises(StorageError, match="cannot commit"):
            unit.commit()
    assert_absent(pg_engine, bundle)
