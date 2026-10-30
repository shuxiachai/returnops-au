from pathlib import Path
import hashlib
import math
import traceback
import pytest
from returnops_domain.canonical import canonical_bytes, decode_document, digest, encode_document
from returnops_domain.errors import FlowError
from returnops_domain.wire import create_request, clarification_request, validate

@pytest.mark.parametrize("value", [None, True, False, 0, -12, "", " a\x00\n\ud800e\u0301 ", "\U0001f600", "\ud83d\ude00", [1, False, "x"], {"z": [2], "a": "\udfff"}], ids=["null","true","false","zero","negative","empty","special","astral","surrogate-pair","array","map"])
def test_private_codec_round_trips_without_python_codepoint_loss(value):
    assert decode_document(encode_document(value)) == value

def test_private_hash_is_typed_ordered_and_domain_separated():
    assert digest(True, "request/v1") != digest(1, "request/v1")
    assert digest("\U0001f600", "request/v1") != digest("\ud83d\ude00", "request/v1")
    assert digest([1, 2], "request/v1") != digest([2, 1], "request/v1")
    assert digest({"a": 1, "b": 2}, "request/v1") == digest({"b": 2, "a": 1}, "request/v1")
    assert digest("same", "request/v1") != digest("same", "history/v1")

@pytest.mark.parametrize("value", [1.0, float("nan"), {1: "key"}, object()], ids=["float","nan","non-string-key","object"])
def test_codec_rejects_values_without_a_wire_canonical_definition(value):
    with pytest.raises(FlowError): canonical_bytes(value, "request/v1")

def test_corrupt_retained_document_is_a_safe_failure():
    with pytest.raises(FlowError) as error: decode_document(encode_document("private-marker") + b"trailing")
    assert "private-marker" not in str(error.value)
    assert error.value.__cause__ is None and error.value.__context__ is None

def test_packaged_schema_is_exact_frozen_resource():
    import returnops_domain
    package = Path(returnops_domain.__file__).parent / "schemas_v1.json"
    oracle = Path(__file__).resolve().parents[2] / "contracts/v1/schemas.json"
    assert package.read_bytes() == oracle.read_bytes()

@pytest.mark.parametrize("raw", ["x" * 12000, " \n\x00\ud800e\u0301\U0001f600 "], ids=["maximum","special"])
def test_create_defaults_preserve_exact_decoded_text_and_detach_collections(raw):
    request = {"original_message": raw}
    result = create_request(request)
    assert result == {"original_message": raw, "requested_outcome": "UNSPECIFIED", "evidence_ids": []}
    result["evidence_ids"].append("ev_001")
    assert "evidence_ids" not in request and create_request(request)["evidence_ids"] == []

@pytest.mark.parametrize("value", [{"original_message": " \n "}, {"original_message": "x" * 12001}, {"original_message": "private-value", "private-key": "private-extra"}, {"original_message": "a", "evidence_ids": ["ev_001", "ev_001"]}], ids=["blank","oversize","unknown","duplicate-evidence"])
def test_invalid_dto_errors_do_not_retain_payload_or_validation_exception(value):
    try: create_request(value)
    except FlowError as error:
        output = str(error) + "".join(traceback.format_exception(error))
        for marker in ("private-value", "private-key", "private-extra"):
            assert marker not in output
        assert error.__cause__ is None and error.__context__ is None
    else: pytest.fail("Invalid request accepted")

@pytest.mark.parametrize("value", [
    {"original_message": chr(0x200B) * 2},
    {"original_message": chr(0x2060) + " " + chr(0xFEFF)},
    {"original_message": "cups arrived chipped", "order_reference": "   "},
    {"original_message": "cups arrived chipped", "order_reference": chr(0x200B)},
], ids=["zero-width", "word-joiner-and-bom", "blank-reference", "invisible-reference"])
def test_invisible_statement_or_reference_is_blank(value):
    # 31 October 2026 review: str.strip() keeps format characters, so these passed.
    with pytest.raises(FlowError): create_request(value)

def test_clarification_answer_of_invisible_characters_is_blank():
    body = {"expected_case_version": 1, "question_set_id": "qs_001", "evidence_ids": [],
            "answers": [{"question_id": "q_001", "text": chr(0x200B) + chr(0x200D)}]}
    with pytest.raises(FlowError): clarification_request(body)
    body["answers"][0]["text"] = chr(0x200B) + "SYN-1001"
    assert clarification_request(body)["answers"][0]["text"] == chr(0x200B) + "SYN-1001"

def test_clarification_requires_a_real_answer_or_evidence_and_unique_questions():
    body = {"expected_case_version": 1, "question_set_id": "qs_001", "answers": [], "evidence_ids": []}
    with pytest.raises(FlowError): clarification_request(body)
    body["answers"] = [{"question_id": "q_001", "text": "answer"}] * 2
    with pytest.raises(FlowError): clarification_request(body)

@pytest.mark.parametrize("number", ["1", "1.0", "1e0", "10e-1", "9007199254740991.0"])
def test_frozen_integral_json_numbers_normalize_exactly(number):
    from returnops_domain.wire import decode_json_document, clarification_request, _validator
    import json
    raw=('{"expected_case_version":'+number+',"question_set_id":"question_set","answers":[],"evidence_ids":["evidence_one"]}').encode()
    oracle=json.loads(raw)
    assert _validator("ClarificationRequest").is_valid(oracle)
    normalized=clarification_request(decode_json_document(raw))
    assert type(normalized["expected_case_version"]) is int
    from decimal import Decimal
    assert normalized["expected_case_version"]==int(Decimal(number))

@pytest.mark.parametrize("number", ["true", "1.5", "NaN", "Infinity", "9007199254740992", "9007199254740991.00000000001", "1e999999", "1e999999999999999999999999999999999"])
def test_invalid_or_out_of_range_json_versions_never_round_into_valid_value(number):
    from returnops_domain.wire import decode_json_document, clarification_request
    raw=('{"expected_case_version":'+number+',"question_set_id":"question_set","answers":[],"evidence_ids":["evidence_one"]}').encode()
    with pytest.raises(FlowError): clarification_request(decode_json_document(raw))
