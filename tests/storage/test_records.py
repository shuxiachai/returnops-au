"""Domain/codec and exception tests; no PostgreSQL substitute is claimed."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import traceback
from types import SimpleNamespace

from jsonschema import Draft202012Validator, FormatChecker
import pytest
from sqlalchemy.exc import SQLAlchemyError

from returnops_domain import DomainValidationError, InitialRecordBundle, StatementContent
from returnops_domain.storage import CommitOutcomeUnknown, InitialRecordUnitOfWork, StorageError, _decode, _encode


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = json.loads((ROOT / "contracts/v1/schemas.json").read_text(encoding="utf-8"))


def oracle(name, value):
    Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": SCHEMAS["$defs"]}, format_checker=FormatChecker()).validate(value)


def test_original_projection_matches_independent_frozen_schema(bundle_factory):
    bundle = bundle_factory()
    statement = {"statement_id": bundle.statement.statement_id, "kind": bundle.statement.kind, "raw_text": bundle.content.raw_text, "requested_outcome": bundle.content.requested_outcome, "submitted_at": bundle.statement.submitted_at.isoformat().replace("+00:00", "Z")}
    oracle("CustomerStatement", statement)
    oracle("CreateCaseRequest", {"original_message": bundle.content.raw_text, "order_reference": bundle.content.original_order_reference, "requested_outcome": bundle.content.requested_outcome})
    for identity in (bundle.case.case_id, bundle.case.owner_principal_id, bundle.case.store_id):
        oracle("Id", identity)


@pytest.mark.parametrize("raw", ["x", " \r\n\t ", "\x00", "\ud800", "\udfff", "\ud83d\ude00", "🙂", "e\u0301", "漢" * 12000])
def test_private_codec_roundtrips_each_python_codepoint(bundle_factory, raw):
    bundle = bundle_factory(raw_text=raw, reference=raw[:120])
    assert _decode(_encode(bundle.content.raw_text)) == raw
    assert list(_decode(_encode(raw))) == list(raw)


def test_records_are_immutable_and_nested_representations_hide_content(bundle_factory):
    bundle = bundle_factory(raw_text="PRIVATE_BODY", reference="PRIVATE_ORDER")
    for value in (bundle.content, bundle, bundle.case):
        output = str(value) + repr(value)
        assert "PRIVATE_BODY" not in output and "PRIVATE_ORDER" not in output
        assert "UNSPECIFIED" not in output
    with pytest.raises(FrozenInstanceError):
        bundle.content.raw_text = "changed"
    with pytest.raises(FrozenInstanceError):
        bundle.content = StatementContent("statement_other", "changed", "OTHER", None)


@pytest.mark.parametrize("patch", [
    {"case_id": "ab"}, {"case_id": "good_id\n"}, {"owner_principal_id": "ééé"},
    {"store_id": "x" * 81}, {"case_version": True}, {"case_version": 0},
    {"case_version": 2}, {"input_version": 2}, {"status": "APPROVED"},
    {"created_at": "2026-09-26T00:00:00Z"}, {"created_at": datetime(2026, 9, 26)},
])
def test_initial_case_rejects_invalid_internal_values(bundle_factory, patch):
    with pytest.raises(DomainValidationError):
        replace(bundle_factory().case, **patch)


def test_times_are_explicit_aware_utc_and_keep_microseconds(bundle_factory):
    bundle = bundle_factory()
    offset = bundle.case.created_at.astimezone(timezone(timedelta(hours=10)))
    record = replace(bundle.case, created_at=offset, updated_at=offset)
    assert record.created_at == bundle.case.created_at
    assert record.created_at.tzinfo is timezone.utc
    assert record.created_at.microsecond == 456789


@pytest.mark.parametrize("patch", [
    {"raw_text": ""}, {"raw_text": "SECRET_BODY" * 12001}, {"raw_text": ["SECRET_BODY"]},
    {"requested_outcome": "SECRET_BODY"}, {"original_order_reference": ""},
    {"original_order_reference": "SECRET_BODY" * 121},
])
def test_validation_errors_discard_inputs_and_nested_exception_context(bundle_factory, patch):
    with pytest.raises(DomainValidationError) as caught:
        replace(bundle_factory().content, **patch)
    error = caught.value
    assert error.__cause__ is None and error.__context__ is None
    assert "SECRET_BODY" not in str(error) + repr(error)
    # Ordinary formatting does not contain Pydantic msg/input/ctx.
    assert "SECRET_BODY" not in "".join(traceback.format_exception(error))
    assert not hasattr(error, "errors")


@pytest.mark.parametrize("part,patch", [
    ("statement", {"case_id": "case_other"}),
    ("content", {"statement_id": "statement_other"}),
    ("statement", {"submitted_at": datetime(2026, 9, 27, tzinfo=timezone.utc)}),
])
def test_bundle_rejects_mixed_record_links(bundle_factory, part, patch):
    bundle = bundle_factory()
    with pytest.raises(DomainValidationError):
        replace(bundle, **{part: replace(getattr(bundle, part), **patch)})


def test_bundle_revalidates_bypassed_frozen_instance(bundle_factory):
    bundle = bundle_factory()
    object.__setattr__(bundle.case, "case_version", 2)
    with pytest.raises(DomainValidationError):
        bundle.validate()


class CommitFailureConnection:
    closed = False

    def __init__(self, fail_after_commit):
        self.fail_after_commit = fail_after_commit
        self.server_committed = False

    def begin(self):
        return self

    def commit(self):
        self.server_committed = self.fail_after_commit
        raise SQLAlchemyError("PRIVATE_BODY postgresql://user:PRIVATE_DSN@host/db")

    def close(self):
        self.closed = True


@pytest.mark.parametrize("server_committed", [False, True])
def test_commit_uncertainty_is_safe_without_false_rollback_claim(server_committed):
    connection = CommitFailureConnection(server_committed)
    engine = SimpleNamespace(echo=False, hide_parameters=True, pool=SimpleNamespace(echo=False), connect=lambda: connection)
    with pytest.raises(CommitOutcomeUnknown) as caught:
        with InitialRecordUnitOfWork(engine) as unit:
            unit.commit()
    assert connection.server_committed is server_committed
    assert connection.closed
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    rendered = str(caught.value) + repr(caught.value) + "".join(traceback.format_exception(caught.value))
    assert "PRIVATE_BODY" not in rendered and "PRIVATE_DSN" not in rendered
    assert "unknown" in str(caught.value) and "rollback" not in str(caught.value)
    with pytest.raises(StorageError):
        unit.commit()


def test_unknown_content_bytes_are_not_replaced():
    with pytest.raises(UnicodeDecodeError):
        _decode(b"\xff")
