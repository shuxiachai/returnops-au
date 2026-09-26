"""A1.01 immutable initial metadata and separately held personal content.

Trusted callers supply identity, IDs, versions and aware datetimes. These are
not CreateCaseRequest DTOs or authority checks. No clock, IDs or defaults are
generated here. The frozen wire schema remains an independent test oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError


class DomainValidationError(ValueError):
    """Static diagnostics only; never retain input-bearing validation errors."""


Identifier = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$")]
InitialVersion = Annotated[StrictInt, Field(ge=1, le=1)]
Outcome = Literal["REFUND", "REPLACEMENT", "REPAIR", "RETURN", "INFORMATION", "UNSPECIFIED", "OTHER"]


class _Schema(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)


class _CaseSchema(_Schema):
    case_id: Identifier
    owner_principal_id: Identifier
    store_id: Identifier
    case_version: InitialVersion
    input_version: InitialVersion
    status: Literal["SUBMITTED"]
    created_at: datetime
    updated_at: datetime


class _StatementSchema(_Schema):
    statement_id: Identifier
    case_id: Identifier
    kind: Literal["ORIGINAL"]
    object_version: InitialVersion
    accepted_case_version: InitialVersion
    accepted_input_version: InitialVersion
    submitted_at: datetime


class _ContentSchema(_Schema):
    statement_id: Identifier
    raw_text: Annotated[StrictStr, Field(min_length=1, max_length=12000)]
    requested_outcome: Outcome
    original_order_reference: Annotated[StrictStr, Field(min_length=1, max_length=120)] | None


def _validate(record: object, schema: type[_Schema]) -> None:
    values = {item.name: getattr(record, item.name) for item in fields(record)}
    try:
        schema.model_validate(values)
    except ValidationError:
        failed = True
    else:
        failed = False
    if failed:
        raise DomainValidationError("Initial record fields are invalid") from None
    # Python's '$' admits a final newline; use the same exact end as wire Id.
    for name, value in values.items():
        if name.endswith("_id") and (not value or not value[-1].isascii() or not (value[-1].isalnum() or value[-1] in "_-")):
            raise DomainValidationError("Initial record identifier is invalid")
    for name, value in values.items():
        if isinstance(value, datetime):
            try:
                normalized = value.astimezone(timezone.utc) if value.utcoffset() is not None else None
            except (ValueError, OverflowError):
                normalized = None
            if normalized is None:
                raise DomainValidationError("Initial record time must be timezone aware")
            object.__setattr__(record, name, normalized)


@dataclass(frozen=True)
class InitialCaseRecord:
    case_id: str
    owner_principal_id: str = field(repr=False)
    store_id: str = field(repr=False)
    case_version: int
    input_version: int
    status: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        _validate(self, _CaseSchema)
        if self.created_at != self.updated_at:
            raise DomainValidationError("Initial record timestamps must match")


@dataclass(frozen=True)
class OriginalStatementRecord:
    statement_id: str
    case_id: str
    kind: str
    object_version: int
    accepted_case_version: int
    accepted_input_version: int
    submitted_at: datetime

    def __post_init__(self) -> None:
        _validate(self, _StatementSchema)


@dataclass(frozen=True)
class StatementContent:
    statement_id: str
    raw_text: str = field(repr=False)
    requested_outcome: str = field(repr=False)
    original_order_reference: str | None = field(repr=False)

    def __post_init__(self) -> None:
        _validate(self, _ContentSchema)


@dataclass(frozen=True)
class InitialRecordBundle:
    case: InitialCaseRecord
    statement: OriginalStatementRecord
    content: StatementContent = field(repr=False)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        # Revalidate even frozen instances at the storage boundary: object-level
        # bypasses or deserialisation must not create invalid/link-mixed writes.
        for value, expected in ((self.case, InitialCaseRecord), (self.statement, OriginalStatementRecord), (self.content, StatementContent)):
            if type(value) is not expected:
                raise DomainValidationError("Initial bundle record type is invalid")
            value.__post_init__()
        if (
            self.statement.case_id != self.case.case_id
            or self.content.statement_id != self.statement.statement_id
            or self.statement.accepted_case_version != self.case.case_version
            or self.statement.accepted_input_version != self.case.input_version
            or self.statement.submitted_at != self.case.created_at
        ):
            raise DomainValidationError("Initial bundle links or versions do not match")
