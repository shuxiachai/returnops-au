"""F.01 artifact checks, NOT runtime authorization/provider safety tests.

Traceability: docs/09-interface-contract-v1.md, docs/08 F.01;
FR-001..012 / NFR-001..004,006..009; shared class and interaction models.
No server, database, provider, live LLM, or Gold evaluation is exercised.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "v1"


def read_json(name):
    return json.loads((CONTRACT / name).read_text(encoding="utf-8"))


SCHEMAS = read_json("schemas.json")
OPENAPI = read_json("openapi.json")
EXAMPLES = read_json("examples.json")
POSITIVE = {item["name"]: item for item in EXAMPLES["positive"]}


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def pointer(document, fragment):
    if fragment in ("", "#"):
        return document
    if not fragment.startswith("#/"):
        raise AssertionError(f"Unsupported reference: {fragment}")
    result = document
    for part in fragment[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def bundle_openapi():
    """Bundle ONLY the two allowlisted local documents; never fetch a URL."""
    result = deepcopy(OPENAPI)
    result["components"]["schemas"] = deepcopy(SCHEMAS["$defs"])
    for node in nodes(result):
        value = node.get("$ref", "")
        for prefix in ("./schemas.json#/$defs/", "#/$defs/"):
            if value.startswith(prefix):
                node["$ref"] = "#/components/schemas/" + value[len(prefix):]
                break
    return result


def validator(name):
    # The registry root intentionally has no instance constraints. Always select
    # a named definition and enable format checking, including UTC timestamps.
    if name not in SCHEMAS["$defs"]:
        raise AssertionError(f"Unknown schema: {name}")
    return Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": SCHEMAS["$defs"]},
        format_checker=FormatChecker(),
    )


def canonical_scope_bytes(scope):
    """Test oracle for the restricted ASCII/integer scope format, not an auth guard."""
    validator("ApprovalScope").validate(scope)
    return json.dumps(
        scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("ascii")


def scope_hash(scope):
    return hashlib.sha256(canonical_scope_bytes(scope)).hexdigest()


class ContractV1Tests(unittest.TestCase):
    def test_schema_and_all_definitions_are_valid(self):
        Draft202012Validator.check_schema(SCHEMAS)
        for name in SCHEMAS["$defs"]:
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(
                    {"$ref": f"#/$defs/{name}", "$defs": SCHEMAS["$defs"]}
                )

    def test_references_resolve_offline(self):
        for document in (SCHEMAS, OPENAPI):
            for node in nodes(document):
                if "$ref" not in node:
                    continue
                value = node["$ref"]
                with self.subTest(ref=value):
                    if value.startswith("./schemas.json#"):
                        pointer(SCHEMAS, value[len("./schemas.json"):])
                    else:
                        self.assertTrue(value.startswith("#/"), value)
                        pointer(document, value)

    def test_openapi_31_specification(self):
        validate(bundle_openapi())
        self.assertEqual(OPENAPI["openapi"], "3.1.0")
        self.assertEqual(OPENAPI["info"]["version"], EXAMPLES["contract_version"])

    def test_positive_examples(self):
        for example in EXAMPLES["positive"]:
            with self.subTest(example=example["name"]):
                validator(example["schema"]).validate(example["value"])

    def test_negative_examples_are_rejected(self):
        for example in EXAMPLES["negative"]:
            with self.subTest(example=example["name"]):
                self.assertTrue(example["reason"])
                self.assertFalse(
                    validator(example["schema"]).is_valid(example["value"]),
                    f"Negative fixture was accepted: {example['name']}",
                )

    def test_example_names_are_unique(self):
        entries = EXAMPLES["positive"] + EXAMPLES["negative"] + EXAMPLES["runtime_guards"]
        self.assertEqual(len(entries), len({item["name"] for item in entries}))

    def test_runtime_scenarios_are_shape_valid_not_executed(self):
        # These scenarios describe future A2/F03 acceptance tests. Validating
        # their shape proves neither HTTP behavior nor zero provider effects.
        for item in EXAMPLES["runtime_guards"]:
            with self.subTest(scenario=item["name"]):
                validator(item["request_schema"]).validate(item["request"])
                validator("ErrorEnvelope").validate(item["error"])
                self.assertTrue(item["precondition"])
                self.assertIn(item["http_status"], (403, 409))
                self.assertEqual(item["expected_provider_effects"], 0)

    def test_frozen_business_enums(self):
        expected = {
            "IssueCategory": {"FAULTY_OR_QUALITY_ISSUE", "WRONG_ITEM", "CHANGE_OF_MIND", "UNCLEAR", "OUT_OF_SCOPE"},
            "AssessmentStatus": {"SUPPORTED", "MISSING_INFORMATION", "CONFLICTING", "UNCERTAIN", "OUT_OF_SCOPE"},
            "RiskOutcome": {"PASS", "PASS_WITH_WARNING", "REVISE", "NEEDS_INFORMATION", "ESCALATE"},
            "FounderDecision": {"APPROVE", "REJECT", "REQUEST_REVISION", "MANUAL_HANDLING"},
        }
        for name, values in expected.items():
            with self.subTest(enum=name):
                self.assertEqual(set(SCHEMAS["$defs"][name]["enum"]), values)
        risk_examples = {x["value"]["outcome"] for x in EXAMPLES["positive"] if x["schema"] == "RiskReview"}
        self.assertEqual(risk_examples, expected["RiskOutcome"])
        decisions = {x["value"]["decision"] for x in EXAMPLES["positive"] if x["schema"] == "FounderDecisionRequest"}
        self.assertEqual(decisions, expected["FounderDecision"])

    def test_public_operations_declare_authority_and_request_rules(self):
        self.assertEqual(OPENAPI["security"], [{"bearerAuth": []}])
        operations = []
        for path, item in OPENAPI["paths"].items():
            for method in ("get", "post"):
                if method not in item:
                    continue
                operation = item[method]
                operations.append(operation["operationId"])
                with self.subTest(path=path, method=method):
                    self.assertEqual(operation.get("security", OPENAPI["security"]), [{"bearerAuth": []}])
                    self.assertEqual(operation["x-owner"], "A")
                    self.assertTrue(operation["x-requirements"])
                    self.assertTrue(operation["x-consumers"])
                    if "/founder/" in path:
                        self.assertEqual(operation["x-roles"], ["FOUNDER"])
                    if method == "post":
                        params = [pointer(OPENAPI, p["$ref"]) if "$ref" in p else p for p in operation.get("parameters", [])]
                        key = next(p for p in params if p["name"] == "Idempotency-Key")
                        self.assertTrue(key["required"])
                        self.assertEqual(key["in"], "header")
                        if "{" in path:
                            dto = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
                            self.assertIn("expected_case_version", SCHEMAS["$defs"][dto]["required"])
                    for response in operation["responses"].values():
                        resolved = pointer(OPENAPI, response["$ref"]) if "$ref" in response else response
                        self.assertIn("X-Correlation-ID", resolved["headers"])
        self.assertEqual(len(operations), len(set(operations)))
        self.assertEqual(set(operations), {
            "getSession", "stageEvidence", "getEvidenceContent", "createCase",
            "getCustomerCase", "submitClarification", "listFounderCases",
            "getFounderCase", "recordFounderDecision", "reconcileOperation",
            "retryNotification", "listCaseAudit", "getFounderAnalytics",
            "listFounderCaseHistory", "listCustomerCaseHistory",
        })
        self.assertFalse(any(re.search(r"/(dispatch|execute|agents|risk)(/|$)", p) for p in OPENAPI["paths"]))

    def test_openapi_fixture_request_response_bindings(self):
        bindings = [
            ("/v1/session", "get", "200", "customer-session"),
            ("/v1/evidence", "post", "201", "staged-photo"),
            ("/v1/cases", "post", "request", "customer-create"),
            ("/v1/cases", "post", "201", "customer-submitted-view"),
            ("/v1/cases/{case_id}", "get", "200", "customer-submitted-view"),
            ("/v1/cases/{case_id}/clarifications", "post", "request", "customer-clarification"),
            ("/v1/founder/cases", "get", "200", "case-list"),
            ("/v1/founder/cases/{case_id}", "get", "200", "founder-review-ready-view"),
            ("/v1/founder/cases/{case_id}", "get", "200", "founder-no-proposal-view"),
            ("/v1/founder/cases/{case_id}/decisions", "post", "request", "founder-approve"),
            ("/v1/founder/cases/{case_id}/decisions", "post", "request", "founder-manual-no-proposal"),
            ("/v1/founder/cases/{case_id}/decisions", "post", "202", "decision-accepted"),
            ("/v1/founder/cases/{case_id}/decisions", "post", "202", "manual-no-proposal-receipt"),
            ("/v1/founder/operations/{operation_id}/reconcile", "post", "202", "operation-reconciling"),
            ("/v1/founder/notifications/{notification_id}/retry", "post", "202", "notification-retry-accepted"),
            ("/v1/founder/cases/{case_id}/audit", "get", "200", "empty-audit-page"),
            ("/v1/founder/analytics", "get", "200", "analytics-empty"),
            ("/v1/founder/analytics", "get", "200", "analytics-windowed"),
        ]
        bundled = bundle_openapi()
        for path, method, response, fixture in bindings:
            with self.subTest(path=path, response=response):
                operation = bundled["paths"][path][method]
                owner = operation["requestBody"] if response == "request" else operation["responses"][response]
                schema = deepcopy(owner["content"]["application/json"]["schema"])
                schema["components"] = bundled["components"]
                Draft202012Validator(schema, format_checker=FormatChecker()).validate(POSITIVE[fixture]["value"])

    def test_current_founder_fixture_links(self):
        view = POSITIVE["founder-review-ready-view"]["value"]
        packet, review = view["current_proposal"], view["current_review"]
        self.assertEqual(packet["case_id"], view["case_id"])
        self.assertEqual(packet["input_version"], view["input_version"])
        self.assertEqual(packet["original_statement_id"], view["statements"][0]["statement_id"])
        for key in ("case_id", "input_version", "proposal_id", "proposal_version", "corpus_version"):
            self.assertEqual(packet[key], review[key])
        self.assertEqual(view["action_preview"]["scope"]["review_id"], review["review_id"])
        for evidence in view["evidence"]:
            self.assertEqual(evidence["case_id"], view["case_id"])
            self.assertEqual(evidence["status"], "BOUND")
        for citation in packet["citations"]:
            passage = next(p for p in view["cited_passages"] if p["passage_id"] == citation["passage_id"])
            for key in ("document_id", "source_version", "corpus_version", "content_sha256", "location"):
                self.assertEqual(citation[key], passage[key])
            self.assertEqual(hashlib.sha256(passage["content"].encode("utf-8")).hexdigest(), passage["content_sha256"])
        risk_input = POSITIVE["risk-review-request"]["value"]
        self.assertEqual(risk_input["order_lookup"]["snapshot"], view["order_snapshot"])
        self.assertEqual(risk_input["attachments"], view["evidence"])

    def test_scope_fixture_fingerprint_and_multi_item_single_parcel(self):
        preview = POSITIVE["action-preview"]["value"]
        approval = POSITIVE["approval-record"]["value"]
        scope = preview["scope"]
        self.assertEqual(scope, approval["scope"])
        self.assertEqual(scope_hash(scope), preview["scope_fingerprint"])
        self.assertEqual(preview["scope_fingerprint"], approval["scope_fingerprint"])
        self.assertEqual(preview["scope_fingerprint"], POSITIVE["founder-approve"]["value"]["scope_fingerprint"])
        create, label = scope["commands"]
        self.assertEqual(create["parameters"]["parcel_id"], scope["parcel_id"])
        self.assertEqual(label["parameters"]["parcel_id"], scope["parcel_id"])
        self.assertEqual(label["parameters"]["return_command_id"], create["command_id"])
        selected = create["parameters"]["line_items"]
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({x["line_item_id"] for x in selected}), len(selected))
        order = POSITIVE["matched-order"]["value"]["snapshot"]
        for selection in selected:
            item = next(x for x in order["line_items"] if x["line_item_id"] == selection["line_item_id"])
            self.assertLessEqual(selection["quantity"], item["quantity"])
        changed = deepcopy(scope)
        changed["proposal_version"] += 1
        self.assertNotEqual(scope_hash(changed), preview["scope_fingerprint"])
        changed = deepcopy(scope)
        changed["commands"][0]["parameters"]["line_items"][0]["quantity"] += 1
        self.assertNotEqual(scope_hash(changed), preview["scope_fingerprint"])
        self.assertEqual(scope_hash(dict(reversed(list(scope.items())))), preview["scope_fingerprint"])

    def test_operation_fixture_fingerprint(self):
        approval = POSITIVE["approval-record"]["value"]
        value = {
            "approval_id": approval["approval_id"],
            "scope_fingerprint": approval["scope_fingerprint"],
            "command": approval["scope"]["commands"][0],
        }
        digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
        for name in ("operation-unknown", "operation-reconciling", "operation-success"):
            self.assertEqual(POSITIVE[name]["value"]["operation_fingerprint"], digest)
            self.assertEqual(POSITIVE[name]["value"]["idempotency_key"], "operation-return-key-001")

    def test_formats_are_really_enforced(self):
        self.assertFalse(validator("Timestamp").is_valid("2026-02-30T00:00:00Z"))
        self.assertFalse(validator("Timestamp").is_valid("2026-09-07T02:00:00+00:00"))
        self.assertTrue(validator("Timestamp").is_valid("2026-09-07T02:00:00Z"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
