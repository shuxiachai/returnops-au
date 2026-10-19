"""Installed frozen v1 DTO validation; resource is packaged, never repo-relative."""
from __future__ import annotations
from copy import deepcopy
from functools import lru_cache
from decimal import Decimal, DecimalException
from math import isfinite
from importlib.resources import files
import json
from jsonschema import Draft202012Validator, FormatChecker
from .canonical import canonical_bytes
from .errors import FlowError

_DEFS = json.loads(files("returnops_domain").joinpath("schemas_v1.json").read_text(encoding="utf-8"))["$defs"]

@lru_cache(maxsize=64)
def _validator(name: str):
    if name not in _DEFS: raise FlowError("INTERNAL_ERROR")
    return Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": _DEFS}, format_checker=FormatChecker())

def validate(name: str, value: object, *, internal: bool = False):
    # JSON Schema integer is a mathematical value, including 1.0 / 1e0.
    # HTTP uses Decimal to avoid losing digits before this normalization; bool
    # stays a distinct JSON value and is rejected by integer schema fields.
    if not internal: value = normalize_json_numbers(value)
    canonical_bytes(value, "validation/v1")
    if next(_validator(name).iter_errors(value), None) is not None:
        raise FlowError("INTERNAL_ERROR" if internal else "VALIDATION_ERROR")
    return deepcopy(value)

def create_request(value: object) -> dict:
    result = validate("CreateCaseRequest", value)
    if not result["original_message"].strip(): raise FlowError("VALIDATION_ERROR")
    result.setdefault("requested_outcome", "UNSPECIFIED")
    result.setdefault("evidence_ids", [])
    return result

def clarification_request(value: object) -> dict:
    result = validate("ClarificationRequest", value)
    ids = [answer["question_id"] for answer in result["answers"]]
    if len(set(ids)) != len(ids) or any(not answer["text"].strip() for answer in result["answers"]):
        raise FlowError("VALIDATION_ERROR")
    return result

def normalize_json_numbers(value, depth=0):
    if depth > 64: raise FlowError("VALIDATION_ERROR")
    if type(value) is float:
        if not isfinite(value) or not value.is_integer(): raise FlowError("VALIDATION_ERROR")
        return int(value)
    if type(value) is Decimal:
        if not value.is_finite() or value.adjusted() > 18 or value != value.to_integral_value():
            raise FlowError("VALIDATION_ERROR")
        return int(value)
    if type(value) is list: return [normalize_json_numbers(v,depth+1) for v in value]
    if type(value) is dict: return {k:normalize_json_numbers(v,depth+1) for k,v in value.items()}
    return value

def decode_json_document(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError("Duplicate JSON member")
            result[key]=value
        return result
    def invalid_constant(_): raise ValueError("Invalid JSON constant")
    failed=False
    try:
        value=json.loads(raw.decode("utf-8"),parse_float=Decimal,parse_int=int,
                         parse_constant=invalid_constant,object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError,DecimalException): failed=True
    if failed: raise FlowError("VALIDATION_ERROR") from None
    return normalize_json_numbers(value)
