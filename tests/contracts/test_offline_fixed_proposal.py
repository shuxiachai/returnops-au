"""A1.05 synthetic/offline tests, never runtime acceptance or Risk approval."""
from copy import deepcopy
from hashlib import sha256
import traceback
import unittest

from returnops_domain.founder_codec import digest
from tools.offline_fixed_proposal import (
    INVENTORY_LABEL, OFFLINE_LABEL, OfflinePreparationError, assemble_offline_proposal,
)
from test_contract_v1 import POSITIVE, SCHEMAS, validator
from test_contract_v1_rc4 import assert_proposal_bundle


BODY = b"offline synthetic attachment content; not a real customer image"
IDENTITIES = ("case_id", "input_version", "proposal_id", "proposal_version",
              "corpus_version", "original_statement_id")


def source_fixture():
    """Read the frozen fixture afresh, before constructing a candidate packet."""
    bundle = deepcopy(POSITIVE["history-proposal"]["value"]["content"])
    bundle["statements"].append({
        "statement_id": "stmt-clarification-001", "kind": "CLARIFICATION",
        "raw_text": "Both mugs were chipped when I opened the synthetic parcel.",
        "question_id": "question-arrival-001", "submitted_at": "2026-09-07T02:01:00Z",
    })
    attachment = bundle["attachments"][0]
    attachment["size_bytes"] = len(BODY)
    attachment["sha256"] = sha256(BODY).hexdigest()
    return bundle


def retained(value):
    return {"value": deepcopy(value), "fingerprint": digest(value)}


def inventory_from_sources(sources):
    """Test-only inventory construction from independently retained fixture DTOs.

    Production callers must not bootstrap their inventory from the candidate.
    No source/current/accepted authority is claimed by these synthetic fixtures.
    """
    inventory = {key: sources["packet"][key] for key in IDENTITIES}
    inventory["label"] = INVENTORY_LABEL
    inventory["statements"] = [retained(value) for value in sources["statements"]]
    inventory["attachments"] = [dict(retained(value), content=BODY)
                                for value in sources["attachments"]]
    for name in ("order_lookup", "retrieval_result", "image_observations"):
        if name in sources:
            inventory[name] = retained(sources[name])
    return inventory


def pair():
    # Separate fixture reads make the inventory independent of packet mutation.
    return source_fixture(), inventory_from_sources(source_fixture())


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        yield value
        for item in value:
            yield from walk(item)


class OfflineFixedProposalTests(unittest.TestCase):
    def assert_rejected(self, bundle, inventory):
        before = deepcopy((bundle, inventory))
        with self.assertRaises(OfflinePreparationError):
            assemble_offline_proposal(bundle, inventory)
        self.assertEqual((bundle, inventory), before)

    def assert_sanitized_failure(self, bundle, inventory, marker):
        before = deepcopy((bundle, inventory))
        try:
            assemble_offline_proposal(bundle, inventory)
        except OfflinePreparationError as error:
            message = "Invalid or incomplete offline preparation material."
            self.assertEqual(str(error), message)
            self.assertEqual(error.args, (message,))
            self.assertEqual(repr(error), f"OfflinePreparationError({message!r})")
            self.assertIsNone(error.__cause__)
            self.assertIsNone(error.__context__)
            formatted = "".join(traceback.format_exception(error))
            self.assertIn(message, formatted)
            self.assertNotIn(marker, formatted)
            self.assertNotIn("UnicodeEncodeError", formatted)
            self.assertNotIn("KeyError", formatted)
        else:
            self.fail("Malformed retained material must be rejected.")
        self.assertEqual((bundle, inventory), before)

    def test_unicode_failure_discards_source_exception_without_mutating_inputs(self):
        bundle, inventory = pair()
        marker = "private-synthetic-unicode-source-marker"
        bundle["retrieval_result"]["passages"][0]["content"] = marker + "\ud800"
        inventory["retrieval_result"] = retained(bundle["retrieval_result"])
        # The finite DTO codec accepts the surrogate; strict passage UTF-8
        # hashing fails with an exception whose .object retains the full text.
        self.assert_sanitized_failure(bundle, inventory, marker)

    def test_nested_inventory_failure_discards_context_without_mutating_inputs(self):
        bundle, inventory = pair()
        marker = "private-synthetic-nested-source-marker"
        inventory["statements"][0] = retained({"raw_text": marker})
        self.assert_sanitized_failure(bundle, inventory, marker)

    def test_complete_bundle_uses_existing_oracle_and_has_no_input_aliases(self):
        bundle, inventory = pair()
        before = deepcopy((bundle, inventory))
        result = assemble_offline_proposal(bundle, inventory)
        self.assertEqual(result, {"label": OFFLINE_LABEL, "bundle": bundle})
        record = deepcopy(POSITIVE["history-proposal"]["value"])
        record["content"] = result["bundle"]
        assert_proposal_bundle(record)
        validator("HistoricalProposalBundle").validate(result["bundle"])
        input_ids = {id(node) for value in (bundle, inventory) for node in walk(value)}
        self.assertFalse(input_ids & {id(node) for node in walk(result)})
        result["bundle"]["statements"][0]["raw_text"] = "changed output"
        result["bundle"]["packet"]["conditions"].append("changed output")
        result["bundle"]["order_lookup"]["snapshot"]["line_items"][0]["quantity"] = 2
        self.assertEqual((bundle, inventory), before)

    def test_original_outcome_and_text_remain_separate_from_suggestions(self):
        bundle, inventory = pair()
        bundle["packet"]["recommended_action"] = "REQUEST_INFORMATION"
        bundle["packet"]["unresolved_questions"] = ["Which mug has the larger chip?"]
        result = assemble_offline_proposal(bundle, inventory)["bundle"]
        self.assertEqual(result["statements"][0], inventory["statements"][0]["value"])
        self.assertEqual(result["statements"][0]["requested_outcome"], "RETURN")
        self.assertEqual(result["packet"]["recommended_action"], "REQUEST_INFORMATION")

    def test_missing_or_changed_original_clarification_and_attachment_reject(self):
        for name, index in (("statements", 0), ("statements", 1), ("attachments", 0)):
            for change in ("omit", "alter"):
                with self.subTest(name=name, index=index, change=change):
                    bundle, inventory = pair()
                    if change == "omit":
                        bundle[name].pop(index)
                    elif name == "statements":
                        bundle[name][index]["raw_text"] += " invented text"
                    else:
                        bundle[name][index]["filename"] = "altered.jpg"
                    self.assert_rejected(bundle, inventory)

    def test_original_requested_outcome_cannot_be_rewritten_or_removed(self):
        for change in ("rewrite", "remove"):
            with self.subTest(change=change):
                bundle, inventory = pair()
                if change == "rewrite":
                    bundle["statements"][0]["requested_outcome"] = "REFUND"
                else:
                    del bundle["statements"][0]["requested_outcome"]
                self.assert_rejected(bundle, inventory)

    def test_unreferenced_retained_sources_cannot_be_omitted(self):
        bundle, inventory = pair()
        self.assertNotIn(bundle["statements"][1]["statement_id"],
                         bundle["evidence_matrix"][0]["statement_ids"])
        bundle["statements"].pop()
        self.assert_rejected(bundle, inventory)

    def test_duplicate_statement_attachment_citation_check_and_passage_ids_reject(self):
        paths = (("statements",), ("attachments",), ("packet", "citations"),
                 ("citation_verification", "checks"), ("retrieval_result", "passages"))
        for parts in paths:
            with self.subTest(parts=parts):
                bundle, inventory = pair()
                target = bundle
                for part in parts:
                    target = target[part]
                target.append(deepcopy(target[0]))
                self.assert_rejected(bundle, inventory)
        bundle, inventory = pair()
        inventory["statements"].append(deepcopy(inventory["statements"][0]))
        self.assert_rejected(bundle, inventory)

    def test_inventory_identity_changes_cannot_be_self_attested_by_bundle(self):
        for key in IDENTITIES:
            with self.subTest(key=key):
                bundle, inventory = pair()
                inventory[key] = 2 if key.endswith("version") and key != "corpus_version" else "different-id"
                self.assert_rejected(bundle, inventory)

    def test_boolean_inventory_identity_cannot_equal_a_numeric_version(self):
        for key in ("input_version", "proposal_version"):
            with self.subTest(key=key):
                bundle, inventory = pair()
                inventory[key] = True
                self.assert_rejected(bundle, inventory)

    def test_boolean_inventory_material_cannot_equal_numeric_source_fields(self):
        paths = (("input_version",), ("snapshot", "snapshot_version"),
                 ("snapshot", "line_items", 0, "quantity"))
        for parts in paths:
            with self.subTest(parts=parts):
                bundle, inventory = pair()
                order = inventory["order_lookup"]["value"]
                target = order
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = True
                inventory["order_lookup"] = retained(order)
                self.assert_rejected(bundle, inventory)

    def test_legal_integral_numeric_normalization_preserves_complete_sources(self):
        bundle, inventory = pair()
        inventory["input_version"] = 1.0
        inventory["proposal_version"] = 1.0
        order = inventory["order_lookup"]["value"]
        order["input_version"] = 1.0
        order["snapshot"]["snapshot_version"] = 1.0
        order["snapshot"]["line_items"][0]["quantity"] = 1.0
        inventory["order_lookup"] = retained(order)
        attachment = inventory["attachments"][0]["value"]
        attachment["size_bytes"] = float(attachment["size_bytes"])
        inventory["attachments"][0] = dict(retained(attachment), content=BODY)
        before = deepcopy((bundle, inventory))
        result = assemble_offline_proposal(bundle, inventory)
        self.assertEqual(result["bundle"], bundle)
        self.assertEqual((bundle, inventory), before)
        self.assertIs(type(inventory["order_lookup"]["value"]["input_version"]), float)
        self.assertIs(type(result["bundle"]["order_lookup"]["input_version"]), int)

    def test_source_case_input_corpus_and_verification_proposal_must_match(self):
        for name, keys in (("order_lookup", ("case_id", "input_version")),
                           ("retrieval_result", ("case_id", "input_version", "corpus_version")),
                           ("citation_verification", ("case_id", "input_version", "corpus_version",
                                                       "proposal_id", "proposal_version"))):
            for key in keys:
                with self.subTest(name=name, key=key):
                    bundle, inventory = pair()
                    bundle[name][key] = 2 if type(bundle[name][key]) is int else "different-id"
                    self.assert_rejected(bundle, inventory)

    def test_order_input_is_never_rewritten_into_candidate_input(self):
        bundle, inventory = pair()
        bundle["order_lookup"]["input_version"] = 2
        inventory["order_lookup"] = retained(bundle["order_lookup"])
        self.assert_rejected(bundle, inventory)

    def test_citation_exact_content_and_all_provenance_fields_are_required(self):
        for key in ("passage_id", "document_id", "source_version", "corpus_version",
                    "content_sha256", "location"):
            with self.subTest(key=key):
                bundle, inventory = pair()
                bundle["packet"]["citations"][0][key] = "b" * 64 if key == "content_sha256" else "different-value"
                self.assert_rejected(bundle, inventory)
        bundle, inventory = pair()
        bundle["retrieval_result"]["passages"][0]["content"] += " altered bytes"
        inventory["retrieval_result"] = retained(bundle["retrieval_result"])
        self.assert_rejected(bundle, inventory)
        bundle, inventory = pair()
        del bundle["retrieval_result"]["passages"][0]["content"]
        self.assert_rejected(bundle, inventory)

    def test_verification_must_cover_exact_citations_and_be_valid(self):
        for change in ("missing", "wrong_id", "invalid"):
            with self.subTest(change=change):
                bundle, inventory = pair()
                checks = bundle["citation_verification"]["checks"]
                if change == "missing":
                    checks.clear()
                elif change == "wrong_id":
                    checks[0]["citation_id"] = "another-citation"
                else:
                    checks[0]["result"] = "HASH_MISMATCH"
                self.assert_rejected(bundle, inventory)

    def test_fingerprints_and_retained_attachment_bytes_are_checked(self):
        for change in ("fingerprint", "missing_bytes", "bytes", "length", "metadata"):
            with self.subTest(change=change):
                bundle, inventory = pair()
                entry = inventory["attachments"][0]
                if change == "fingerprint":
                    entry["fingerprint"] = "0" * 64
                elif change == "missing_bytes":
                    del entry["content"]
                elif change == "bytes":
                    entry["content"] = b"x" * len(BODY)
                elif change == "length":
                    entry["content"] = BODY + b"x"
                else:
                    entry["value"]["filename"] = "altered.jpg"
                self.assert_rejected(bundle, inventory)

    def test_full_no_match_conflict_questions_and_conditions_are_preserved(self):
        bundle = source_fixture()
        bundle["retrieval_result"].update(status="NO_MATCH", passages=[], conflicts=["Unresolved synthetic source conflict."])
        bundle["packet"]["citations"] = []
        bundle["citation_verification"]["checks"] = []
        bundle["packet"]["unresolved_questions"] = ["A full unresolved question must survive."]
        bundle["packet"]["conditions"] += ["Independent review is required."]
        inventory = inventory_from_sources(deepcopy(bundle))
        result = assemble_offline_proposal(bundle, inventory)["bundle"]
        self.assertEqual(result, bundle)
        bundle["retrieval_result"]["conflicts"] = []
        self.assert_rejected(bundle, inventory)

    def test_complete_business_missing_and_conflicting_do_not_create_authority(self):
        for status in ("MISSING", "CONFLICTING"):
            with self.subTest(status=status):
                bundle, inventory = pair()
                for matrix in (bundle["evidence_matrix"], bundle["packet"]["evidence_matrix"]):
                    matrix[0]["status"] = status
                bundle["packet"]["unresolved_questions"] = ["A missing business fact remains unresolved."]
                result = assemble_offline_proposal(bundle, inventory)
                self.assertEqual(result["label"], OFFLINE_LABEL)
                self.assertEqual(result["bundle"], bundle)
                self.assertEqual(set(result), {"label", "bundle"})
                forbidden = {"approval", "approval_id", "command", "tool_command", "risk_review", "current_proposal_id"}
                self.assertFalse(any(forbidden & node.keys() for node in walk(result) if isinstance(node, dict)))

    def test_fixture_metadata_and_synthetic_material_are_required(self):
        for key, value in (("provider_id", "provider-live"), ("model_id", "live-model"),
                           ("input_tokens", 1), ("output_tokens", 1)):
            with self.subTest(key=key):
                bundle, inventory = pair()
                bundle["packet"]["model_run"][key] = value
                self.assert_rejected(bundle, inventory)
        bundle, inventory = pair()
        inventory["label"] = "CURRENT_AUTHORIZED_SOURCE"
        self.assert_rejected(bundle, inventory)
        bundle, inventory = pair()
        bundle["retrieval_result"]["passages"][0]["is_synthetic"] = False
        inventory["retrieval_result"] = retained(bundle["retrieval_result"])
        self.assert_rejected(bundle, inventory)

    def test_unknown_fields_cannot_add_approval_or_inventory_authority(self):
        for target, key in (("packet", "approval_id"), ("bundle", "tool_command"), ("inventory", "authorized")):
            with self.subTest(target=target):
                bundle, inventory = pair()
                value = bundle["packet"] if target == "packet" else inventory if target == "inventory" else bundle
                value[key] = "fake-authority"
                self.assert_rejected(bundle, inventory)

    def test_optional_observations_are_complete_and_not_invented(self):
        bundle = source_fixture()
        bundle["image_observations"] = {
            "case_id": bundle["packet"]["case_id"], "input_version": 1,
            "component_version": "offline-fixture-v1",
            "observations": [{"evidence_id": bundle["attachments"][0]["evidence_id"],
                              "visible_observations": ["Synthetic visible chip."],
                              "limitations": ["Fixture; no image model executed."], "confidence": 0.5}],
        }
        inventory = inventory_from_sources(deepcopy(bundle))
        self.assertEqual(assemble_offline_proposal(bundle, inventory)["bundle"], bundle)
        del bundle["image_observations"]
        self.assert_rejected(bundle, inventory)

    def test_schema_text_capacity_accepts_exact_boundary_and_never_truncates(self):
        cases = (("statement", SCHEMAS["$defs"]["CustomerStatement"]["properties"]["raw_text"]["maxLength"]),
                 ("passage", SCHEMAS["$defs"]["PolicyPassage"]["properties"]["content"]["maxLength"]))
        for kind, limit in cases:
            for extra in (0, 1):
                with self.subTest(kind=kind, extra=extra):
                    bundle = source_fixture()
                    if kind == "statement":
                        bundle["statements"][0]["raw_text"] = "x" * (limit + extra)
                    else:
                        passage = bundle["retrieval_result"]["passages"][0]
                        passage["content"] = "x" * (limit + extra)
                        passage["content_sha256"] = sha256(passage["content"].encode()).hexdigest()
                        bundle["packet"]["citations"][0]["content_sha256"] = passage["content_sha256"]
                    inventory = inventory_from_sources(deepcopy(bundle))
                    if extra:
                        self.assert_rejected(bundle, inventory)
                    else:
                        self.assertEqual(assemble_offline_proposal(bundle, inventory)["bundle"], bundle)

    def test_schema_array_capacity_accepts_boundary_and_rejects_overflow(self):
        cases = (("statements", "RiskReviewRequest"), ("attachments", "RiskReviewRequest"),
                 ("passages", "RetrievalResult"), ("conflicts", "RetrievalResult"),
                 ("citations", "DecisionPacket"), ("evidence_matrix", "DecisionPacket"),
                 ("conditions", "DecisionPacket"), ("alternatives", "DecisionPacket"),
                 ("unresolved_questions", "DecisionPacket"))
        for field, definition in cases:
            limit = SCHEMAS["$defs"][definition]["properties"][field]["maxItems"]
            for extra in (0, 1):
                with self.subTest(field=field, extra=extra):
                    bundle = source_fixture()
                    count = limit + extra
                    if field == "statements":
                        clarification = bundle["statements"][1]
                        bundle[field] = [bundle[field][0]] + [dict(clarification, statement_id=f"clarification-{i}") for i in range(count - 1)]
                    elif field == "attachments":
                        item = bundle[field][0]
                        bundle[field] = [dict(item, evidence_id=f"evidence-{i}", content_path=f"/v1/evidence/evidence-{i}/content") for i in range(count)]
                        for matrix in (bundle["evidence_matrix"], bundle["packet"]["evidence_matrix"]):
                            matrix[0]["evidence_ids"] = ["evidence-0"]
                    elif field == "passages":
                        item = bundle["retrieval_result"][field][0]
                        bundle["retrieval_result"][field] = [dict(item, passage_id=f"passage-{i}") for i in range(count)]
                        bundle["packet"]["citations"][0]["passage_id"] = "passage-0"
                    elif field == "citations":
                        item = bundle["packet"][field][0]
                        check = bundle["citation_verification"]["checks"][0]
                        bundle["packet"][field] = [dict(item, citation_id=f"citation-{i}") for i in range(count)]
                        bundle["citation_verification"]["checks"] = [dict(check, citation_id=f"citation-{i}") for i in range(count)]
                    elif field == "evidence_matrix":
                        item = bundle["packet"][field][0]
                        bundle["packet"][field] = [dict(item, criterion_id=f"criterion-{i}") for i in range(count)]
                        bundle[field] = deepcopy(bundle["packet"][field])
                    else:
                        target = bundle["retrieval_result"] if field == "conflicts" else bundle["packet"]
                        target[field] = [f"Full fixture entry {i}." for i in range(count)]
                    inventory = inventory_from_sources(deepcopy(bundle))
                    if extra:
                        self.assert_rejected(bundle, inventory)
                    else:
                        self.assertEqual(assemble_offline_proposal(bundle, inventory)["bundle"], bundle)


if __name__ == "__main__":
    unittest.main()
