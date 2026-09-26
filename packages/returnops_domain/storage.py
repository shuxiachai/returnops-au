"""A1.02 trusted internal PostgreSQL storage, with explicit transaction commit.

No create service, identity checking, deduplication, retries, transitions, audit
policy or retention/deletion API. Historical accepted versions are facts, not
foreign keys to mutable case versions. Personal strings use private codec v1:
Python UTF-8 with surrogatepass; this is not a wire/fingerprint/audit codec.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from sqlalchemy import Column, DateTime, Integer, LargeBinary, MetaData, String, Table, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .records import DomainValidationError, InitialCaseRecord, InitialRecordBundle, OriginalStatementRecord, StatementContent


class StorageError(RuntimeError):
    """A safe internal failure, never an HTTP error or a retry instruction."""


class DuplicateRecordError(StorageError):
    """Insert conflicted; it is not an idempotent successful acceptance."""


class CommitOutcomeUnknown(StorageError):
    """Commit acknowledgement failed; do not claim rollback or retry creation."""


metadata = MetaData()
case_records = Table(
    "case_records", metadata,
    Column("case_id", String(80), primary_key=True),
    Column("owner_principal_id", String(80), nullable=False),
    Column("store_id", String(80), nullable=False),
    Column("case_version", Integer, nullable=False),
    Column("input_version", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
original_statement_records = Table(
    "original_statement_records", metadata,
    Column("statement_id", String(80), primary_key=True),
    Column("case_id", String(80), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("object_version", Integer, nullable=False),
    Column("accepted_case_version", Integer, nullable=False),
    Column("accepted_input_version", Integer, nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
)
original_statement_contents = Table(
    "original_statement_contents", metadata,
    Column("statement_id", String(80), primary_key=True),
    Column("raw_text", LargeBinary, nullable=False),
    Column("requested_outcome", String(16), nullable=False),
    Column("original_order_reference", LargeBinary, nullable=True),
)


def _encode(value: str) -> bytes:
    return value.encode("utf-8", errors="surrogatepass")


def _decode(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogatepass")


class InitialRecordRepository:
    """Uses a caller-owned, active transaction; never commits or rolls back."""

    def __init__(self, connection: Connection, on_failure: Callable[[], None]) -> None:
        self._connection = connection
        self._on_failure = on_failure

    def _check_active(self) -> None:
        if self._connection.closed or not self._connection.in_transaction():
            raise StorageError("Initial storage requires an active transaction")

    def insert_initial_record(self, bundle: InitialRecordBundle) -> None:
        self._check_active()
        if type(bundle) is not InitialRecordBundle:
            self._on_failure()
            raise DomainValidationError("Initial bundle type is invalid")
        failure = None
        try:
            bundle.validate()
            self._connection.execute(case_records.insert(), asdict(bundle.case))
            self._connection.execute(original_statement_records.insert(), asdict(bundle.statement))
            self._connection.execute(original_statement_contents.insert(), {
                "statement_id": bundle.content.statement_id,
                "raw_text": _encode(bundle.content.raw_text),
                "requested_outcome": bundle.content.requested_outcome,
                "original_order_reference": None if bundle.content.original_order_reference is None else _encode(bundle.content.original_order_reference),
            })
        except DomainValidationError:
            self._on_failure()
            raise
        except IntegrityError as error:
            failure = "duplicate" if getattr(error.orig, "sqlstate", None) == "23505" else "storage"
        except SQLAlchemyError:
            failure = "storage"
        if failure is not None:
            self._on_failure()
            if failure == "duplicate":
                raise DuplicateRecordError("Initial record already exists") from None
            raise StorageError("Initial record write failed") from None

    def load_initial_record(self, case_id: str) -> InitialRecordBundle | None:
        self._check_active()
        # Validate through the same scalar schema, without exposing query input.
        if not isinstance(case_id, str) or not 3 <= len(case_id) <= 80 or not case_id.isascii() or not case_id[0].isalnum() or any(not (c.isalnum() or c in "_-") for c in case_id):
            raise DomainValidationError("Initial record identifier is invalid")
        failure = False
        try:
            case = self._connection.execute(select(case_records).where(case_records.c.case_id == case_id)).mappings().one_or_none()
            if case is None:
                return None
            statement = self._connection.execute(select(original_statement_records).where(original_statement_records.c.case_id == case_id)).mappings().one_or_none()
            if statement is None:
                raise StorageError("Initial record is incomplete or invalid")
            content = self._connection.execute(select(original_statement_contents).where(original_statement_contents.c.statement_id == statement["statement_id"])).mappings().one_or_none()
            if content is None:
                raise StorageError("Initial record is incomplete or invalid")
            return InitialRecordBundle(
                InitialCaseRecord(**case), OriginalStatementRecord(**statement),
                StatementContent(
                    statement_id=content["statement_id"], raw_text=_decode(content["raw_text"]),
                    requested_outcome=content["requested_outcome"],
                    original_order_reference=None if content["original_order_reference"] is None else _decode(content["original_order_reference"]),
                ),
            )
        except (SQLAlchemyError, UnicodeError, DomainValidationError):
            failure = True
        except StorageError:
            failure = True
        if failure:
            self._on_failure()
            raise StorageError("Initial record read failed or content is unavailable") from None
        return None


class InitialRecordUnitOfWork:
    """One connection/transaction. Exiting without explicit commit rolls back.

    Any failed repository operation poisons this UoW even when its caller catches
    the error. Commit acknowledgement failures are always outcome-unknown.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._connection: Connection | None = None
        self._transaction = None
        self._failed = False
        self._finished = False
        self._entered = False
        self.repository: InitialRecordRepository

    def _mark_failed(self) -> None:
        self._failed = True

    def __enter__(self) -> InitialRecordUnitOfWork:
        if self._entered or self._engine.echo or self._engine.pool.echo or not self._engine.hide_parameters:
            raise StorageError("Initial storage requires a fresh UoW and private SQL diagnostics")
        self._entered = True
        failed = False
        try:
            self._connection = self._engine.connect()
            self._transaction = self._connection.begin()
        except SQLAlchemyError:
            failed = True
        if failed:
            self._close_safely()
            raise StorageError("Initial storage connection failed") from None
        self.repository = InitialRecordRepository(self._connection, self._mark_failed)
        return self

    def commit(self) -> None:
        if self._transaction is None or self._finished or self._failed:
            raise StorageError("Initial storage transaction cannot commit")
        failed = False
        try:
            self._transaction.commit()
        except SQLAlchemyError:
            failed = True
        self._finished = True
        if failed:
            self._failed = True
            raise CommitOutcomeUnknown("Commit outcome is unknown; do not automatically retry") from None

    def _close_safely(self) -> bool:
        failed = False
        if self._connection is not None:
            try:
                self._connection.close()
            except SQLAlchemyError:
                failed = True
        return not failed

    def __exit__(self, exc_type, exc, traceback) -> bool:
        # close() rolls back uncommitted work. Cleanup after an uncertain commit
        # makes no assertion about whether the server committed the transaction.
        closed = self._close_safely()
        self._finished = True
        if not closed and exc_type is None:
            raise StorageError("Initial storage cleanup failed") from None
        return False
