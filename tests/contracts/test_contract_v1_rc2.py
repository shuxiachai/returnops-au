"""F.01 rc2 artifact regressions and fixture-only consistency oracles.

Traceability: docs/08 F.01 and docs/09; FR-006..012, NFR-001/002/004/006/009;
shared state/class/interaction models. These checks exercise JSON artifacts,
not a server, real principal, provider, LLM, concurrency, or runtime guards.
"""

from copy import deepcopy
from collections import Counter
from datetime import datetime
import hashlib
import unittest

from test_contract_v1 import OPENAPI, POSITIVE, SCHEMAS, pointer, validator


def require(condition, message):
    """Raise in test-only consistency checks, never used by application code."""
    if not condition:
        raise AssertionError(message)


def fixture(name):
    return deepcopy(POSITIVE[name]["value"])


def assert_valid_citation_handoff(request, original_retrieval):
    """Oracle for valid-citation fixtures, not a general risk/approval guard.

    Invalid citations remain expressible so a future reviewer can reject them.
    This oracle checks that our intentionally valid fixture was not corrupted
    or stripped between retrieval, assessment, verification, and risk input.
    """
    validator("RiskReviewRequest").validate(request)
    packet = request["packet"]
    retrieval = request["retrieval_result"]
    verification = request["citation_verification"]
    require(retrieval == original_retrieval, "Full original retrieval, including conflicts, must survive handoff")
    for key in ("case_id", "input_version", "corpus_version"):
        require(retrieval[key] == packet[key], f"Retrieval {key} differs from packet")
    for key in ("case_id", "input_version", "proposal_id", "proposal_version", "corpus_version"):
        require(verification[key] == packet[key], f"Citation verification {key} differs from packet")
    for key in ("case_id", "input_version"):
        require(request["order_lookup"][key] == packet[key], f"Order lookup {key} differs from packet")
    require(request["evidence_matrix"] == packet["evidence_matrix"], "Risk must receive the same evidence matrix")
    statements = {item["statement_id"] for item in request["statements"]}
    evidence = {item["evidence_id"] for item in request["attachments"]}
    require(packet["original_statement_id"] in statements, "Original statement is unavailable")
    for item in request["attachments"]:
        require(item["case_id"] == packet["case_id"] and item["status"] == "BOUND", "Evidence binding differs")
    for criterion in request["evidence_matrix"]:
        require(set(criterion["statement_ids"]) <= statements, "Missing statement reference")
        require(set(criterion["evidence_ids"]) <= evidence, "Missing attachment reference")
    passages = {item["passage_id"]: item for item in retrieval["passages"]}
    require(len(passages) == len(retrieval["passages"]), "Duplicate passage IDs")
    citation_ids = [item["citation_id"] for item in packet["citations"]]
    check_ids = [item["citation_id"] for item in verification["checks"]]
    require(len(citation_ids) == len(set(citation_ids)), "Duplicate citation IDs")
    require(len(check_ids) == len(set(check_ids)), "Duplicate verification IDs")
    require(set(check_ids) == set(citation_ids), "Verification must cover exactly the cited IDs")
    for passage in passages.values():
        require(passage["corpus_version"] == packet["corpus_version"], "Passage corpus differs")
        digest = hashlib.sha256(passage["content"].encode("utf-8")).hexdigest()
        require(digest == passage["content_sha256"], "Passage content hash differs")
    for citation in packet["citations"]:
        require(citation["passage_id"] in passages, "Referenced passage unavailable")
        passage = passages[citation["passage_id"]]
        for key in ("document_id", "source_version", "corpus_version", "content_sha256", "location"):
            require(citation[key] == passage[key], f"Citation {key} differs from passage")


def assert_failure_target_fixture(view, request, record):
    """Cross-object links in a no-proposal example, not principal authentication."""
    for schema, value in (("CaseView", view), ("FounderDecisionRequest", request), ("FounderDecisionRecord", record)):
        validator(schema).validate(value)
    failure = view["processing_failure"]
    require(view["status"] == "ESCALATED" and "current_proposal" not in view, "Wrong no-proposal decision context")
    for key in ("case_id", "input_version"):
        require(view[key] == failure[key], f"Failure {key} does not match current case")
    require(request["expected_case_version"] == view["case_version"], "Stale expected case version")
    require(record["case_id"] == view["case_id"], "Decision belongs to another case")
    for value in (request, record):
        require(value["processing_failure_id"] == failure["failure_id"], "Wrong failure target")
        require(value["decision"] == "MANUAL_HANDLING", "Failure target must not grant execution authority")


def expanded_handoff(count):
    """Synthetic DTO-size boundary fixture; not count new Gold scenarios."""
    request = fixture("risk-review-request")
    request.pop("passages", None)
    retrieval = fixture("retrieval-result")
    passage_template = retrieval["passages"][0]
    citation_template = request["packet"]["citations"][0]
    check_template = request["citation_verification"]["checks"][0]
    retrieval["passages"] = []
    request["packet"]["citations"] = []
    request["citation_verification"]["checks"] = []
    for index in range(count):
        passage = deepcopy(passage_template)
        passage["passage_id"] = f"passage-capacity-{index:03d}"
        passage["location"] = f"synthetic-section-{index}"
        passage["content"] = f"Synthetic boundary-test passage number {index}; not real guidance."
        passage["content_sha256"] = hashlib.sha256(passage["content"].encode("utf-8")).hexdigest()
        citation = deepcopy(citation_template)
        citation["citation_id"] = f"citation-capacity-{index:03d}"
        for key in ("passage_id", "document_id", "source_version", "corpus_version", "content_sha256", "location"):
            citation[key] = passage[key]
        check = deepcopy(check_template)
        check["citation_id"] = citation["citation_id"]
        retrieval["passages"].append(passage)
        request["packet"]["citations"].append(citation)
        request["citation_verification"]["checks"].append(check)
    request["retrieval_result"] = retrieval
    return request


def utc(value):
    validator("Timestamp").validate(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_analytics_query_interval(query):
    """Schema checks format; chronological ordering is an explicit fixture oracle."""
    validator("AnalyticsQuery").validate(query)
    if "created_from" in query and "created_before" in query:
        require(utc(query["created_from"]) < utc(query["created_before"]), "Analytics interval must be non-empty and ordered")


def analytics_rows():
    """Small explanatory records, NOT a new API DTO or evaluation dataset."""
    start = "2026-09-06T00:00:00Z"
    rows = [
        {"case_id": "cohort-one", "created_at": start, "input_version": 1,
         "proposal_id": "proposal-one", "proposal_version": 1,
         "statuses": [(start, "SUBMITTED"), ("2026-09-06T01:00:00Z", "COMPLETED"),
                      ("2026-09-08T00:00:00Z", "ESCALATED")],
         "reviews": [{"proposal_id": "proposal-one", "proposal_version": 1, "input_version": 1,
                      "outcome": "PASS", "reviewed_at": "2026-09-06T00:30:00Z"}],
         "latency": ("MEASURED", 1200)},
        {"case_id": "cohort-two", "created_at": "2026-09-06T12:00:00Z", "input_version": 2,
         "proposal_id": "proposal-two", "proposal_version": 2,
         "statuses": [("2026-09-06T12:00:00Z", "SUBMITTED"), ("2026-09-06T13:00:00Z", "ESCALATED")],
         "reviews": [{"proposal_id": "proposal-two", "proposal_version": 1, "input_version": 1,
                      "outcome": "PASS", "reviewed_at": "2026-09-06T12:30:00Z"}],
         "latency": ("FAILED", None)},
        {"case_id": "cohort-three", "created_at": "2026-09-06T23:59:59Z", "input_version": 1,
         "statuses": [("2026-09-06T23:59:59Z", "AWAITING_INFORMATION")],
         "reviews": [], "latency": ("UNMEASURED", None)},
        {"case_id": "upper-bound-excluded", "created_at": "2026-09-07T00:00:00Z", "input_version": 1,
         "statuses": [("2026-09-07T00:00:00Z", "SUBMITTED")],
         "reviews": [], "latency": ("UNMEASURED", None)},
        {"case_id": "before-window-excluded", "created_at": "2026-09-05T23:59:59Z", "input_version": 1,
         "statuses": [("2026-09-05T23:59:59Z", "SUBMITTED")],
         "reviews": [], "latency": ("UNMEASURED", None)},
    ]
    rows.append(deepcopy(rows[0]))  # A duplicate joined row must not double-count a case.
    return rows


def assert_analytics_fixture(snapshot, rows=None):
    """Fixture arithmetic/cohort oracle, not a query implementation or live measurement."""
    validator("AnalyticsSnapshot").validate(snapshot)
    query = snapshot["filters"]
    assert_analytics_query_interval(query)
    count = snapshot["case_count"]
    latency = snapshot["proposal_latency"]
    status_counts = {item["status"]: item["count"] for item in snapshot["cases_by_status"]}
    risk_counts = {item["outcome"]: item["count"] for item in snapshot["current_risk_counts"]}
    require(len(status_counts) == len(snapshot["cases_by_status"]), "Duplicate status buckets")
    require(len(risk_counts) == len(snapshot["current_risk_counts"]), "Duplicate risk buckets")
    require(sum(status_counts.values()) == count, "Status buckets must sum to case_count")
    require(sum(risk_counts.values()) + snapshot["cases_without_current_review"] == count, "Risk denominator differs")
    require(sum(latency[key] for key in ("sample_count", "failed_count", "unmeasured_count")) == count, "Latency denominator differs")
    if latency["sample_count"]:
        require(latency["p50_ms"] <= latency["p95_ms"], "Percentile ordering differs")
    if rows is None:
        return
    as_of = utc(snapshot["as_of"])
    unique = {}
    for row in rows:
        require(row["case_id"] not in unique or unique[row["case_id"]] == row, "Conflicting duplicate fixture row")
        unique[row["case_id"]] = row
    selected = []
    for row in unique.values():
        created = utc(row["created_at"])
        if created > as_of or ("created_from" in query and created < utc(query["created_from"])):
            continue
        if "created_before" in query and created >= utc(query["created_before"]):
            continue
        visible_states = [(utc(at), status) for at, status in row["statuses"] if utc(at) <= as_of]
        require(bool(visible_states), "No state at as_of in explanatory row")
        status = max(visible_states)[1]
        if "status" not in query or query["status"] == status:
            selected.append((row, status))
    require(len(selected) == count, "Created-at/status cohort differs")
    require(dict(Counter(status for _, status in selected)) == status_counts, "Status is not evaluated at as_of")
    expected_risks = []
    for row, _ in selected:
        reviews = [review for review in row["reviews"]
                   if utc(review["reviewed_at"]) <= as_of
                   and all(review[key] == row.get(key) for key in ("proposal_id", "proposal_version", "input_version"))]
        if reviews:
            expected_risks.append(max(reviews, key=lambda review: utc(review["reviewed_at"]))["outcome"])
    require(dict(Counter(expected_risks)) == risk_counts, "Only current proposal/input reviews count")
    require(count - len(expected_risks) == snapshot["cases_without_current_review"], "No-current-review count differs")
    kinds = Counter(row["latency"][0] for row, _ in selected)
    for kind, field in (("MEASURED", "sample_count"), ("FAILED", "failed_count"), ("UNMEASURED", "unmeasured_count")):
        require(kinds[kind] == latency[field], f"Wrong {field} for the same created-at cohort")
    values = [row["latency"][1] for row, _ in selected if row["latency"][0] == "MEASURED"]
    if len(values) == 1:
        # Avoid inventing a multi-sample percentile interpolation convention.
        require(latency["p50_ms"] == latency["p95_ms"] == values[0], "Single-sample percentile differs")


class ContractV1Rc2Tests(unittest.TestCase):
    def test_identifier_patterns_reject_illegal_characters_at_every_position(self):
        legal = {"Id": "case-001", "IdempotencyKey": "request-key-001", "Hash": "a" * 64}
        for name, value in legal.items():
            for bad in ("\n", "\r", "\r\n", " ", "/", "é", "中", "\u2028", "\u2029"):
                for position in (0, len(value) // 2, len(value)):
                    changed = value[:position] + bad + value[position:]
                    with self.subTest(schema=name, bad=repr(bad), position=position):
                        self.assertFalse(validator(name).is_valid(changed))

    def test_identifier_patterns_accept_minimum_maximum_and_reject_outside_bounds(self):
        for name, minimum, maximum, character in (
            ("Id", 3, 80, "a"), ("IdempotencyKey", 8, 128, "a"), ("Hash", 64, 64, "a")
        ):
            for length in (minimum, maximum):
                with self.subTest(schema=name, legal_length=length):
                    validator(name).validate(character * length)
            for length in (minimum - 1, maximum + 1):
                with self.subTest(schema=name, illegal_length=length):
                    self.assertFalse(validator(name).is_valid(character * length))
        validator("Id").validate("A0_-z")
        validator("IdempotencyKey").validate("Ab09._:-")
        validator("Hash").validate("0123456789abcdef" * 4)
        self.assertFalse(validator("Id").is_valid("_ab"))
        self.assertFalse(validator("Hash").is_valid("A" * 64))

    def test_other_strict_end_anchors_reject_line_terminators_but_preserve_multiline_statements(self):
        timestamp = "2026-09-07T02:00:00Z"
        # Shape-only audit example; these dummy hashes do not prove a valid audit chain.
        audit = {
            "event_id": "event-anchor-001", "case_id": "case-demo-001", "case_version": 1,
            "correlation_id": "correlation-demo-001", "actor_type": "DOMAIN_SERVICE",
            "event_type": "CASE_CREATED", "occurred_at": timestamp, "object_ids": [],
            "component_version": "fixture-v1", "payload_hash": "a" * 64, "event_hash": "b" * 64,
        }
        for name, field, value in (
            ("Timestamp", None, timestamp),
            ("EvidenceAttachment", "content_path", fixture("staged-photo")),
            ("ApprovalScope", "allowlist_version", fixture("approval-record")["scope"]),
            ("AuditEvent", "event_type", audit),
        ):
            validator(name).validate(value)
            for suffix in ("\n", "\r\n", "\r", "\u2028", "\u2029"):
                changed = deepcopy(value)
                if field is None:
                    changed += suffix
                else:
                    changed[field] += suffix
                with self.subTest(schema=name, field=field, suffix=repr(suffix)):
                    self.assertFalse(validator(name).is_valid(changed))
        raw_text = "First line.\n第二行。\r\nThird line.\rFourth line.\u2028Fifth line.\u2029Last line.\n"
        create = {**fixture("customer-create"), "original_message": raw_text}
        statement = {**fixture("risk-review-request")["statements"][0], "raw_text": raw_text}
        validator("CreateCaseRequest").validate(create)
        validator("CustomerStatement").validate(statement)
        self.assertEqual(create["original_message"], statement["raw_text"])

    def test_risk_input_requires_the_complete_retrieval_result(self):
        request = deepcopy(POSITIVE["risk-review-request"]["value"])
        request.pop("passages", None)
        request["retrieval_result"] = deepcopy(POSITIVE["retrieval-result"]["value"])
        validator("RiskReviewRequest").validate(request)
        missing = deepcopy(request)
        del missing["retrieval_result"]["conflicts"]
        self.assertFalse(validator("RiskReviewRequest").is_valid(missing))
        old_shape = deepcopy(request)
        old_shape["passages"] = old_shape.pop("retrieval_result")["passages"]
        self.assertFalse(validator("RiskReviewRequest").is_valid(old_shape))

    def test_21_and_100_citations_survive_each_declared_handoff(self):
        for count in (21, 100):
            request = expanded_handoff(count)
            check_request = fixture("citation-check-request")
            check_request["citations"] = deepcopy(request["packet"]["citations"])
            view = fixture("founder-review-ready-view")
            view["current_proposal"] = deepcopy(request["packet"])
            view["cited_passages"] = deepcopy(request["retrieval_result"]["passages"])
            for name, value in (
                ("RetrievalResult", request["retrieval_result"]),
                ("DecisionPacket", request["packet"]),
                ("CitationVerificationRequest", check_request),
                ("CitationVerificationResult", request["citation_verification"]),
                ("RiskReviewRequest", request), ("CaseView", view),
            ):
                with self.subTest(count=count, schema=name):
                    validator(name).validate(value)
            assert_valid_citation_handoff(request, request["retrieval_result"])

    def test_101_items_are_rejected_at_every_citation_passage_boundary(self):
        request = expanded_handoff(101)
        check_request = fixture("citation-check-request")
        check_request["citations"] = deepcopy(request["packet"]["citations"])
        view = fixture("founder-review-ready-view")
        view["cited_passages"] = deepcopy(request["retrieval_result"]["passages"])
        for name, value in (
            ("RetrievalResult", request["retrieval_result"]),
            ("DecisionPacket", request["packet"]),
            ("CitationVerificationRequest", check_request),
            ("CitationVerificationResult", request["citation_verification"]),
            ("RiskReviewRequest", request), ("CaseView", view),
        ):
            with self.subTest(schema=name):
                self.assertFalse(validator(name).is_valid(value))

    def test_uncited_conflict_context_is_preserved_not_just_cited_passages(self):
        request = expanded_handoff(2)
        original = deepcopy(request["retrieval_result"])
        for passage, content in zip(original["passages"], (
            "Synthetic store policy A permits this test return.",
            "Synthetic store policy B prohibits this test return.",
        )):
            passage["content"] = content
            passage["content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        original["conflicts"] = ["Synthetic source A and source B disagree on the return condition."]
        request["retrieval_result"] = deepcopy(original)
        # Assessment cites only A; Risk must still receive B and the conflict.
        request["packet"]["citations"] = request["packet"]["citations"][:1]
        request["packet"]["citations"][0]["content_sha256"] = original["passages"][0]["content_sha256"]
        request["citation_verification"]["checks"] = request["citation_verification"]["checks"][:1]
        assert_valid_citation_handoff(request, original)
        for drop in ("conflicts", "uncited_passage"):
            changed = deepcopy(request)
            if drop == "conflicts":
                changed["retrieval_result"]["conflicts"] = []
            else:
                changed["retrieval_result"]["passages"].pop()
            with self.subTest(drop=drop):
                # Shape-valid data loss needs a cross-object/origin check later.
                validator("RiskReviewRequest").validate(changed)
                with self.assertRaises(AssertionError):
                    assert_valid_citation_handoff(changed, original)

    def test_fixture_oracle_detects_shape_valid_version_and_reference_mismatches(self):
        original = fixture("retrieval-result")
        request = fixture("risk-review-request")
        assert_valid_citation_handoff(request, original)
        changes = [
            ("retrieval_case", ("retrieval_result", "case_id"), "case-other-001"),
            ("retrieval_input", ("retrieval_result", "input_version"), 99),
            ("retrieval_corpus", ("retrieval_result", "corpus_version"), "different-corpus"),
            ("check_case", ("citation_verification", "case_id"), "case-other-001"),
            ("check_input", ("citation_verification", "input_version"), 99),
            ("check_proposal", ("citation_verification", "proposal_id"), "proposal-other-001"),
            ("check_version", ("citation_verification", "proposal_version"), 99),
            ("check_corpus", ("citation_verification", "corpus_version"), "different-corpus"),
            ("order_case", ("order_lookup", "case_id"), "case-other-001"),
            ("order_input", ("order_lookup", "input_version"), 99),
            ("missing_statement", ("packet", "original_statement_id"), "stmt-absent-001"),
            ("missing_passage", ("packet", "citations", 0, "passage_id"), "passage-absent-001"),
            ("source_version", ("packet", "citations", 0, "source_version"), "different-source"),
            ("source_document", ("packet", "citations", 0, "document_id"), "document-other-001"),
            ("citation_corpus", ("packet", "citations", 0, "corpus_version"), "different-corpus"),
            ("citation_hash", ("packet", "citations", 0, "content_sha256"), "b" * 64),
            ("citation_location", ("packet", "citations", 0, "location"), "wrong-section"),
            ("check_reference", ("citation_verification", "checks", 0, "citation_id"), "citation-absent-001"),
            ("attachment_case", ("attachments", 0, "case_id"), "case-other-001"),
        ]
        for name, path, value in changes:
            changed = deepcopy(request)
            owner = changed
            for part in path[:-1]:
                owner = owner[part]
            owner[path[-1]] = value
            with self.subTest(change=name):
                validator("RiskReviewRequest").validate(changed)
                with self.assertRaises(AssertionError):
                    assert_valid_citation_handoff(changed, original)
        corrupt_origin = deepcopy(original)
        corrupt_origin["passages"][0]["content"] += " Altered without updating the stored hash."
        changed = deepcopy(request)
        changed["retrieval_result"] = deepcopy(corrupt_origin)
        validator("RiskReviewRequest").validate(changed)
        with self.assertRaises(AssertionError):
            assert_valid_citation_handoff(changed, corrupt_origin)

    def test_citation_oracle_rejects_duplicate_citation_and_check_ids(self):
        request = expanded_handoff(2)
        original = deepcopy(request["retrieval_result"])
        assert_valid_citation_handoff(request, original)
        for owner, field, message in (("packet", "citations", "Duplicate citation IDs"),
                                      ("citation_verification", "checks", "Duplicate verification IDs")):
            changed = deepcopy(request)
            changed[owner][field][1]["citation_id"] = changed[owner][field][0]["citation_id"]
            with self.subTest(duplicate_in=field):
                validator("RiskReviewRequest").validate(changed)
                with self.assertRaisesRegex(AssertionError, message):
                    assert_valid_citation_handoff(changed, original)

    def test_no_proposal_processing_failure_has_a_manual_decision_chain(self):
        failure = fixture("processing-failure")
        view = fixture("founder-no-proposal-view")
        request = fixture("founder-manual-no-proposal")
        record = fixture("manual-no-proposal-record")
        receipt = fixture("manual-no-proposal-receipt")
        notification = fixture("manual-no-proposal-notification")
        for schema, value in (("ProcessingFailure", failure), ("CaseView", view),
                              ("FounderDecisionRequest", request), ("FounderDecisionRecord", record),
                              ("DecisionReceipt", receipt), ("NotificationRecord", notification)):
            validator(schema).validate(value)
        self.assertEqual(view["status"], "ESCALATED")
        self.assertEqual(view["processing_failure"], failure)
        for key in ("case_id", "input_version"):
            self.assertEqual(view[key], failure[key])
        self.assertEqual(request["expected_case_version"], view["case_version"])
        self.assertEqual(request["processing_failure_id"], failure["failure_id"])
        self.assertEqual(record["processing_failure_id"], failure["failure_id"])
        self.assertEqual(record["case_id"], view["case_id"])
        self.assertEqual(record["decision_id"], receipt["decision_id"])
        self.assertEqual(receipt["case_id"], notification["case_id"])
        self.assertEqual(notification["case_id"], view["case_id"])
        for value in (request, record, receipt):
            self.assertEqual(value["decision"], "MANUAL_HANDLING")
            self.assertNotIn("approval_id", value)
        self.assertEqual(notification["outcome"], "MANUAL_HANDLED")
        for field in ("current_proposal", "current_review", "action_preview"):
            self.assertNotIn(field, view)
        assert_failure_target_fixture(view, request, record)

    def test_no_proposal_fixture_oracle_detects_stale_and_cross_case_failure_targets(self):
        view = fixture("founder-no-proposal-view")
        request = fixture("founder-manual-no-proposal")
        record = fixture("manual-no-proposal-record")
        for part, key, value in (
            ("failure", "case_id", "case-other-001"),
            ("failure", "input_version", 99),
            ("request", "processing_failure_id", "failure-other-001"),
            ("request", "expected_case_version", 99),
            ("record", "processing_failure_id", "failure-other-001"),
            ("record", "case_id", "case-other-001"),
        ):
            changed_view, changed_request, changed_record = deepcopy((view, request, record))
            target = {"failure": changed_view["processing_failure"], "request": changed_request, "record": changed_record}[part]
            target[key] = value
            with self.subTest(part=part, field=key):
                for schema, changed in (("CaseView", changed_view), ("FounderDecisionRequest", changed_request),
                                        ("FounderDecisionRecord", changed_record)):
                    validator(schema).validate(changed)
                with self.assertRaises(AssertionError):
                    assert_failure_target_fixture(changed_view, changed_request, changed_record)

    def test_processing_failure_stage_and_required_context_are_strict(self):
        value = fixture("processing-failure")
        for stage in ("COORDINATOR", "ORDER_LOOKUP", "RETRIEVAL", "ASSESSMENT", "RISK_REVIEW"):
            with self.subTest(stage=stage):
                validator("ProcessingFailure").validate({**value, "stage": stage})
        self.assertFalse(validator("ProcessingFailure").is_valid({**value, "stage": "OPERATIONS"}))
        for field in ("failure_id", "case_id", "input_version", "stage", "error", "occurred_at"):
            changed = deepcopy(value)
            del changed[field]
            with self.subTest(missing=field):
                self.assertFalse(validator("ProcessingFailure").is_valid(changed))

    def test_no_proposal_case_cannot_offer_a_review_or_action_preview(self):
        view = fixture("founder-no-proposal-view")
        missing_failure = deepcopy(view)
        del missing_failure["processing_failure"]
        self.assertFalse(validator("CaseView").is_valid(missing_failure))
        for field, source in (("current_review", "risk-pass"), ("action_preview", "action-preview")):
            with self.subTest(field=field):
                self.assertFalse(validator("CaseView").is_valid({**view, field: fixture(source)}))
        submitted = deepcopy(missing_failure)
        submitted["status"] = "SUBMITTED"
        validator("CaseView").validate(submitted)
        customer_view = fixture("customer-submitted-view")
        customer_view["processing_failure"] = fixture("processing-failure")
        self.assertFalse(validator("CustomerCaseView").is_valid(customer_view))

    def test_failure_target_only_allows_manual_handling_without_execution_authority(self):
        for schema, name in (("FounderDecisionRequest", "founder-manual-no-proposal"),
                             ("FounderDecisionRecord", "manual-no-proposal-record")):
            value = fixture(name)
            for decision in ("APPROVE", "REJECT", "REQUEST_REVISION"):
                with self.subTest(schema=schema, decision=decision):
                    changed = {**value, "decision": decision}
                    if decision == "APPROVE":
                        if schema == "FounderDecisionRequest":
                            changed.update(preview_id="preview-fake-001", scope_fingerprint="a" * 64)
                        else:
                            changed["approval_id"] = "approval-fake-001"
                    self.assertFalse(validator(schema).is_valid(changed))
            for field, extra in (("preview_id", "preview-fake-001"), ("scope_fingerprint", "a" * 64),
                                 ("approval_id", "approval-fake-001"), ("scope", fixture("approval-record")["scope"])):
                with self.subTest(schema=schema, extra=field):
                    self.assertFalse(validator(schema).is_valid({**value, field: extra}))

    def test_founder_target_union_rejects_double_missing_and_half_targets(self):
        for schema, failure_name, proposal_name in (
            ("FounderDecisionRequest", "founder-manual-no-proposal", "founder-manual_handling"),
            ("FounderDecisionRecord", "manual-no-proposal-record", "founder-decision-record"),
        ):
            failure = fixture(failure_name)
            for addition in ({"proposal_id": "proposal-other-001"}, {"proposal_version": 1},
                             {"proposal_id": "proposal-other-001", "proposal_version": 1}):
                with self.subTest(schema=schema, double_target=addition):
                    self.assertFalse(validator(schema).is_valid({**failure, **addition}))
            missing = deepcopy(failure)
            del missing["processing_failure_id"]
            self.assertFalse(validator(schema).is_valid(missing))
            for field in ("proposal_id", "proposal_version"):
                proposal = fixture(proposal_name)
                del proposal[field]
                with self.subTest(schema=schema, half_target=field):
                    self.assertFalse(validator(schema).is_valid(proposal))
        for name in ("founder-manual-no-proposal", "founder-approve"):
            for field, value in (("principal_id", "principal-fake-001"), ("role", "FOUNDER"),
                                 ("approved_by", "principal-fake-001")):
                with self.subTest(fixture=name, forged_field=field):
                    self.assertFalse(validator("FounderDecisionRequest").is_valid({**fixture(name), field: value}))

    def test_analytics_query_formats_and_snapshot_required_denominators(self):
        query = fixture("analytics-query-window")
        assert_analytics_query_interval(query)
        for value in ({}, {"created_from": query["created_from"]}, {"created_before": query["created_before"]},
                      {**query, "status": "COMPLETED"}):
            validator("AnalyticsQuery").validate(value)
        for value in ({**query, "status": "NOT_A_CASE_STATUS"}, {**query, "created_from": "2026-02-30T00:00:00Z"},
                      {**query, "created_before": "2026-09-07"}, {**query, "unknown_filter": "all"}):
            self.assertFalse(validator("AnalyticsQuery").is_valid(value))
        for name in ("analytics-empty", "analytics-windowed"):
            snapshot = fixture(name)
            assert_analytics_fixture(snapshot)
            missing_filters = deepcopy(snapshot)
            del missing_filters["filters"]
            self.assertFalse(validator("AnalyticsSnapshot").is_valid(missing_filters))
            del snapshot["proposal_latency"]["unmeasured_count"]
            self.assertFalse(validator("AnalyticsSnapshot").is_valid(snapshot))

    def test_public_analytics_query_parameters_use_the_shared_field_schemas(self):
        operation = OPENAPI["paths"]["/v1/founder/analytics"]["get"]
        parameters = [pointer(OPENAPI, item["$ref"]) if "$ref" in item else item
                      for item in operation.get("parameters", [])]
        query_parameters = {item["name"]: item for item in parameters if item["in"] == "query"}
        properties = SCHEMAS["$defs"]["AnalyticsQuery"]["properties"]
        self.assertEqual(set(query_parameters), set(properties))
        for name, parameter in query_parameters.items():
            with self.subTest(parameter=name):
                self.assertFalse(parameter.get("required", False))
                self.assertEqual(parameter["schema"]["$ref"].split("#", 1)[1],
                                 properties[name]["$ref"].split("#", 1)[1])
        self.assertIn("422", operation["responses"])

    def test_analytics_interval_ordering_is_an_oracle_not_a_schema_claim(self):
        query = fixture("analytics-query-window")
        for lower in (query["created_before"], "2026-09-08T00:00:00Z"):
            changed = {**query, "created_from": lower}
            validator("AnalyticsQuery").validate(changed)
            with self.assertRaises(AssertionError):
                assert_analytics_query_interval(changed)

    def test_analytics_cohort_is_created_at_half_open_and_current_at_as_of(self):
        snapshot = fixture("analytics-windowed")
        self.assertEqual(snapshot["filters"], fixture("analytics-query-window"))
        assert_analytics_fixture(snapshot, analytics_rows())
        selected = deepcopy(snapshot)
        selected["filters"]["status"] = "COMPLETED"
        selected["case_count"] = 1
        selected["cases_by_status"] = [{"status": "COMPLETED", "count": 1}]
        selected["cases_without_current_review"] = 0
        selected["proposal_latency"].update(failed_count=0, unmeasured_count=0)
        assert_analytics_fixture(selected, analytics_rows())

    def test_business_escalation_with_review_ready_measurement_remains_a_latency_sample(self):
        rows = analytics_rows()
        for row in rows:
            if row["case_id"] == "cohort-one":
                # A stored review-ready packet can require manual handling;
                # its measured episode is not a technical processing failure.
                row["statuses"][1] = ("2026-09-06T01:00:00Z", "ESCALATED")
                row["reviews"][0]["outcome"] = "ESCALATE"
                self.assertEqual(row["latency"], ("MEASURED", 1200))
        snapshot = fixture("analytics-windowed")
        snapshot["cases_by_status"] = [{"status": "ESCALATED", "count": 2},
                                       {"status": "AWAITING_INFORMATION", "count": 1}]
        snapshot["current_risk_counts"] = [{"outcome": "ESCALATE", "count": 1}]
        assert_analytics_fixture(snapshot, rows)
        misclassified = deepcopy(snapshot)
        misclassified["proposal_latency"].update(sample_count=0, failed_count=2)
        del misclassified["proposal_latency"]["p50_ms"]
        del misclassified["proposal_latency"]["p95_ms"]
        validator("AnalyticsSnapshot").validate(misclassified)
        with self.assertRaisesRegex(AssertionError, "Wrong sample_count"):
            assert_analytics_fixture(misclassified, rows)

    def test_analytics_oracle_rejects_shape_valid_arithmetic_and_cohort_mutations(self):
        base = fixture("analytics-windowed")
        mutations = []
        for field in ("sample_count", "failed_count", "unmeasured_count"):
            changed = deepcopy(base)
            changed["proposal_latency"][field] += 1
            mutations.append((field, changed))
        for field in ("case_count", "cases_without_current_review"):
            changed = deepcopy(base)
            changed[field] += 1
            mutations.append((field, changed))
        for field in ("cases_by_status", "current_risk_counts"):
            changed = deepcopy(base)
            changed[field][0]["count"] += 1
            mutations.append((field, changed))
            changed = deepcopy(base)
            changed[field].append(deepcopy(changed[field][0]))
            mutations.append((f"duplicate_{field}", changed))
        changed = deepcopy(base)
        changed["proposal_latency"].update(failed_count=0, unmeasured_count=2)
        mutations.append(("same_total_wrong_latency_cohort", changed))
        changed = deepcopy(base)
        changed["current_risk_counts"][0]["count"] = 2
        changed["cases_without_current_review"] = 1
        mutations.append(("historical_pass_counted_as_current", changed))
        changed = deepcopy(base)
        changed["filters"]["created_from"] = "2026-09-06T00:00:01Z"
        mutations.append(("lower_boundary_excluded", changed))
        changed = deepcopy(base)
        changed["filters"]["created_before"] = "2026-09-07T00:00:01Z"
        mutations.append(("upper_boundary_included", changed))
        changed = deepcopy(base)
        changed["filters"]["status"] = "COMPLETED"
        mutations.append(("filter_not_applied_to_denominators", changed))
        changed = deepcopy(base)
        changed["as_of"] = "2026-09-08T01:00:00Z"
        mutations.append(("wrong_status_at_as_of", changed))
        for name, changed in mutations:
            with self.subTest(change=name):
                validator("AnalyticsSnapshot").validate(changed)
                with self.assertRaises(AssertionError):
                    assert_analytics_fixture(changed, analytics_rows())


if __name__ == "__main__":
    unittest.main(verbosity=2)
