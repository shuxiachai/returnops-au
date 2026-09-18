"""KAN-32 / F.01 rc.3: manual-target artifact and fixture consistency checks.

FR-003/009/011/012, NFR-002/004/006/009; UC-02/03 and shared class/state/sequence.
No API, principal authentication, state transition or provider effect is run.
"""

from copy import deepcopy
import itertools
import unittest

from jsonschema import Draft202012Validator

from test_contract_v1 import OPENAPI, bundle_openapi
from test_contract_v1_rc2 import assert_analytics_fixture, fixture, require, validator


def assert_block_target_fixture(lookup, view, request, record):
    """Test-only oracle for our linked synthetic snapshots, never a runtime guard."""
    for name, value in (("OrderLookupResult", lookup), ("CaseView", view),
                        ("FounderDecisionRequest", request), ("FounderDecisionRecord", record)):
        validator(name).validate(value)
    block = view["order_lookup_block"]
    require(view["status"] == "ESCALATED" and "current_proposal" not in view, "Wrong current decision context")
    for key in ("case_id", "input_version"):
        require(view[key] == block[key] == lookup[key], f"Wrong current {key}")
    for key in ("status", "message"):
        require(block[key] == lookup[key], f"Wrong source {key}")
    require(request["expected_case_version"] == view["case_version"], "Stale case version")
    require(record["case_id"] == view["case_id"], "Wrong decision case")
    require(record["reason"] == request["reason"], "Changed decision reason")
    for value in (request, record):
        require(value["order_lookup_block_id"] == block["block_id"], "Wrong current block target")
        require(value["decision"] == "MANUAL_HANDLING", "Not a manual outcome")


class ContractV1Rc3Tests(unittest.TestCase):
    def test_both_order_block_sources_have_linked_manual_examples(self):
        for suffix, status in (("conflict", "CONFLICT"), ("authority-denied", "AUTHORITY_DENIED")):
            with self.subTest(status=status):
                view = fixture("founder-blocked-view-" + suffix)
                self.assertEqual(view["order_lookup_block"], fixture("order-lookup-block-" + suffix))
                assert_block_target_fixture(
                    fixture("order-" + status.lower()), view,
                    fixture("founder-manual-block-" + suffix), fixture("manual-block-record-" + suffix),
                )

    def test_wrong_current_source_and_target_links_are_detected_by_fixture_oracle(self):
        for owner, field, value in (
            ("block", "case_id", "case-another-001"), ("block", "input_version", 99),
            ("block", "status", "AUTHORITY_DENIED"), ("block", "message", "Unrelated lookup outcome."),
            ("lookup", "case_id", "case-another-001"), ("lookup", "input_version", 99),
            ("view", "status", "MANUAL_HANDLED"),
            ("request", "expected_case_version", 99), ("request", "order_lookup_block_id", "old-block-001"),
            ("record", "case_id", "case-another-001"), ("record", "order_lookup_block_id", "old-block-001"),
            ("record", "reason", "Changed after acceptance."),
        ):
            lookup = fixture("order-conflict")
            view = fixture("founder-blocked-view-conflict")
            request = fixture("founder-manual-block-conflict")
            record = fixture("manual-block-record-conflict")
            changed = {"lookup": lookup, "view": view, "block": view["order_lookup_block"],
                       "request": request, "record": record}[owner]
            changed[field] = value
            with self.subTest(owner=owner, field=field):
                # These are deliberately schema-valid mismatches: the oracle only
                # demonstrates fixture consistency, not a server rejecting them.
                for name, obj in (("OrderLookupResult", lookup), ("CaseView", view),
                                  ("FounderDecisionRequest", request), ("FounderDecisionRecord", record)):
                    validator(name).validate(obj)
                with self.assertRaises(AssertionError):
                    assert_block_target_fixture(lookup, view, request, record)

    def test_order_block_cannot_disguise_clarification_technical_error_or_risk(self):
        block = fixture("order-lookup-block-conflict")
        for status in ("MATCHED", "NOT_FOUND", "PROVIDER_FAILURE", "ESCALATE", "PASS"):
            with self.subTest(status=status):
                self.assertFalse(validator("OrderLookupBlock").is_valid({**block, "status": status}))
        for field, value in (("error", fixture("processing-failure")["error"]),
                             ("snapshot", fixture("risk-review-request")["order_lookup"]["snapshot"]),
                             ("approval_id", "approval-demo-001")):
            with self.subTest(field=field):
                self.assertFalse(validator("OrderLookupBlock").is_valid({**block, field: value}))
        self.assertFalse(validator("ProcessingFailure").is_valid(block))

    def test_decision_targets_are_exhaustively_exclusive_and_complete(self):
        target_fields = [
            {"proposal_id": "proposal-demo-001", "proposal_version": 1},
            {"processing_failure_id": "failure-demo-001"},
            {"order_lookup_block_id": "lookup-block-conflict"},
        ]
        for schema, name in (("FounderDecisionRequest", "founder-manual-block-conflict"),
                             ("FounderDecisionRecord", "manual-block-record-conflict")):
            base = fixture(name)
            del base["order_lookup_block_id"]
            for mask in itertools.product((False, True), repeat=3):
                value = deepcopy(base)
                for chosen, fields in zip(mask, target_fields):
                    if chosen:
                        value.update(fields)
                with self.subTest(schema=schema, targets=mask):
                    self.assertEqual(validator(schema).is_valid(value), sum(mask) == 1)
            for incomplete in ({"proposal_id": "proposal-demo-001"}, {"proposal_version": 1}):
                for target in ({}, target_fields[1], target_fields[2]):
                    self.assertFalse(validator(schema).is_valid({**base, **target, **incomplete}))

    def test_non_proposal_targets_never_accept_other_decisions_or_authority_fields(self):
        for schema, names in (
            ("FounderDecisionRequest", ("founder-manual-block-conflict", "founder-manual-no-proposal")),
            ("FounderDecisionRecord", ("manual-block-record-conflict", "manual-no-proposal-record")),
        ):
            for name in names:
                base = fixture(name)
                for decision in ("APPROVE", "REJECT", "REQUEST_REVISION"):
                    changed = {**base, "decision": decision}
                    if decision == "APPROVE":
                        if schema.endswith("Request"):
                            changed.update(preview_id="preview-demo-001", scope_fingerprint="a" * 64)
                        else:
                            changed["approval_id"] = "approval-demo-001"
                    with self.subTest(schema=schema, fixture=name, decision=decision):
                        self.assertFalse(validator(schema).is_valid(changed))
                for field, value in (("preview_id", "preview-demo-001"), ("scope_fingerprint", "a" * 64),
                                     ("approval_id", "approval-demo-001"), ("command", "CREATE_RETURN")):
                    with self.subTest(schema=schema, fixture=name, injected=field):
                        self.assertFalse(validator(schema).is_valid({**base, field: value}))

    def test_current_view_requires_one_real_non_proposal_cause_and_preserves_history(self):
        base = fixture("founder-blocked-view-conflict")
        block = base.pop("order_lookup_block")
        self.assertFalse(validator("CaseView").is_valid(base))
        for target in ({"order_lookup_block": block}, {"processing_failure": fixture("processing-failure")}):
            validator("CaseView").validate({**base, **target})
        self.assertFalse(validator("CaseView").is_valid({
            **base, "order_lookup_block": block, "processing_failure": fixture("processing-failure"),
        }))
        ready = fixture("founder-review-ready-view")
        validator("CaseView").validate(ready)
        self.assertFalse(validator("CaseView").is_valid({**ready, "order_lookup_block": block}))
        for field in ("current_proposal", "current_review", "action_preview"):
            self.assertFalse(validator("CaseView").is_valid({**base, "order_lookup_block": block, field: ready[field]}))
        # A current target is not permission to erase historical unknown effects.
        historical = {**base, "order_lookup_block": block, "operations": [fixture("operation-unknown")]}
        validator("CaseView").validate(historical)
        self.assertEqual(historical["operations"][0]["status"], "UNKNOWN")

    def test_resolved_block_remains_visible_through_notification_and_manual_terminal(self):
        view = fixture("founder-blocked-view-conflict")
        view["decisions"] = [fixture("manual-block-record-conflict")]
        for status in ("NOTIFICATION_PENDING", "NOTIFICATION_FAILED", "MANUAL_HANDLED"):
            with self.subTest(status=status):
                # Shape snapshots only; the application must prove outcome/notification transitions.
                validator("CaseView").validate({**view, "status": status})

    def test_http_idempotency_parameter_uses_shared_rule_and_rejects_bad_boundaries(self):
        header = OPENAPI["components"]["parameters"]["IdempotencyKey"]["schema"]
        self.assertEqual(header, {"$ref": "./schemas.json#/$defs/IdempotencyKey"})
        bundled = bundle_openapi()
        http = Draft202012Validator({
            **bundled["components"]["parameters"]["IdempotencyKey"]["schema"],
            "components": bundled["components"],
        })
        shared = validator("IdempotencyKey")
        for value in ("a" * 8, "a" * 128, "Ab09._:-"):
            http.validate(value)
            shared.validate(value)
        for value in ("a" * 7, "a" * 129, *["request-key-001" + ch for ch in ("\n", "\r", "\r\n", "\u2028", "\u2029", " ", "/", "中")]):
            with self.subTest(value=repr(value)):
                self.assertFalse(http.is_valid(value))
                self.assertFalse(shared.is_valid(value))

    def test_business_block_without_review_ready_measurement_is_not_a_technical_failure(self):
        for suffix in ("conflict", "authority-denied"):
            view = fixture("founder-blocked-view-" + suffix)
            block = view["order_lookup_block"]
            # Expected category in the synthetic fixture, not a production classifier.
            row = {"case_id": view["case_id"], "created_at": view["created_at"],
                   "input_version": view["input_version"], "reviews": [],
                   "statuses": [(block["occurred_at"], "ESCALATED")],
                   "latency": ("UNMEASURED", None)}
            snapshot = fixture("analytics-empty")
            snapshot.update(as_of="2026-09-07T02:02:00Z", case_count=1,
                            cases_by_status=[{"status": "ESCALATED", "count": 1}],
                            cases_without_current_review=1)
            snapshot["proposal_latency"]["unmeasured_count"] = 1
            with self.subTest(block=suffix):
                assert_analytics_fixture(snapshot, [row])
                changed = deepcopy(snapshot)
                changed["proposal_latency"].update(unmeasured_count=0, failed_count=1)
                # Denominator and schema still agree; source-aware fixture checking
                # is needed to detect the incorrect business/technical classification.
                validator("AnalyticsSnapshot").validate(changed)
                with self.assertRaisesRegex(AssertionError, "Wrong failed_count"):
                    assert_analytics_fixture(changed, [row])


if __name__ == "__main__":
    unittest.main()
