"""Pure preparation functions for the frozen v1 intake contract.

This module is an experiment, not an API, persistence, authorization, or case
creation implementation.  Callers supply both statement identifiers and UTC
timestamps; the functions neither generate nor interpret either value.
"""

from __future__ import annotations

from copy import deepcopy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError


class ContractValidationError(ValueError):
    """Raised when a value is outside the frozen contract or intake rule."""


_ROOT = Path(__file__).resolve().parents[2]
_SCHEMAS = json.loads((_ROOT / "contracts" / "v1" / "schemas.json").read_text(encoding="utf-8"))


def _validator(definition: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": _SCHEMAS["$defs"]},
        format_checker=FormatChecker(),
    )


_CREATE_CASE_REQUEST = _validator("CreateCaseRequest")
_CUSTOMER_STATEMENT = _validator("CustomerStatement")


_DIAGNOSTIC_FIELDS = frozenset({
    "original_message", "order_reference", "requested_outcome", "evidence_ids",
    "statement_id", "kind", "raw_text", "submitted_at", "question_id",
})
_DIAGNOSTIC_RULES = frozenset({
    "type", "required", "additionalProperties", "minLength", "maxLength",
    "enum", "pattern", "format", "minItems", "maxItems", "uniqueItems",
})


def _validate(validator: Draft202012Validator, value: object, label: str) -> None:
    try:
        validator.validate(value)
    except ValidationError as error:
        # Never expose jsonschema's message, instance, schema, or unknown keys.
        field = error.absolute_path[0] if error.absolute_path else "object"
        field = field if field in _DIAGNOSTIC_FIELDS else "object"
        rule = error.validator if error.validator in _DIAGNOSTIC_RULES else "schema"
        diagnostic = f"{label} is not valid: {field} ({rule})"
    else:
        return

    # Raise after leaving the handler so the raw validation error is not retained
    # as exception context or rendered by an ordinary formatted traceback.
    raise ContractValidationError(diagnostic) from None


def validate_create_case_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy a request with the contract's two documented defaults.

    This does not authorize a caller, create a case, bind evidence, or change
    the request text.  Whitespace-only messages are rejected as the documented
    supplementary domain rule; JSON Schema validity and this rule are distinct.
    """
    if not isinstance(request, Mapping):
        raise ContractValidationError("CreateCaseRequest must be an object")

    normalized = deepcopy(dict(request))
    _validate(_CREATE_CASE_REQUEST, normalized, "CreateCaseRequest")

    # This is intentionally after schema validation and does not alter raw text.
    if normalized["original_message"].strip() == "":
        raise ContractValidationError("original_message must not be whitespace-only")

    normalized.setdefault("requested_outcome", "UNSPECIFIED")
    normalized.setdefault("evidence_ids", [])
    return normalized


def project_original_statement(
    request: Mapping[str, Any], *, statement_id: str, submitted_at: str
) -> dict[str, Any]:
    """Project one nonpersistent ORIGINAL statement from a valid request.

    The supplied ID and timestamp are schema-validated only.  They are not
    authorization claims, generated values, or evidence of persisted state.
    """
    normalized = validate_create_case_request(request)
    statement = {
        "statement_id": deepcopy(statement_id),
        "kind": "ORIGINAL",
        "raw_text": deepcopy(normalized["original_message"]),
        "requested_outcome": deepcopy(normalized["requested_outcome"]),
        "submitted_at": deepcopy(submitted_at),
    }
    _validate(_CUSTOMER_STATEMENT, statement, "CustomerStatement")
    return statement
