"""KAN-23/KAN-24: C1 -> C2 offline contract rehearsal on current main.

FR-006/007/008, NFR-001/002/009; AH-08 -> UC-02 -> MC-ACT/MC-SEQ.
Corpus acceptance, people, review URL, Assessment packet and model replies below
are synthetic TEST FIXTURES, not actual source approval, LLM/Gold results, a
database integration, or Gate 1/2 acceptance. No runtime service is activated.
"""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from experiments.c1_grounding_candidate import admission
from experiments.c1_grounding_candidate.admission import ReviewedGroundingCandidate
from experiments.c1_grounding_candidate.grounding import GroundingError
from experiments.c2_risk_candidate.reviewer import (
    ModelReply, PROMPT_VERSION, RiskReviewError, RiskReviewerCandidate, SYSTEM_PROMPT,
)

ROOT = Path(__file__).resolve().parents[2]
AT = "2026-10-15T06:00:00Z"
DEFS = json.loads((ROOT / "contracts/v1/schemas.json").read_text())["$defs"]
EXAMPLES = json.loads((ROOT / "contracts/v1/examples.json").read_text())["positive"]
BINDINGS = ("case_id", "input_version", "proposal_id", "proposal_version", "corpus_version")
ADMISSION_FLAGS = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
HAS_ADMISSION_FILESYSTEM = all(hasattr(admission.os, flag) for flag in ADMISSION_FLAGS)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def validator(name):
    return Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": DEFS},
                               format_checker=FormatChecker())


class StubReviewerTransport:
    """One cooperative async call, no model/client/provider implementation."""

    def __init__(self, outcome="ESCALATE", *, blocking=True, mode="normal"):
        self.outcome, self.blocking, self.mode = outcome, blocking, mode
        self.calls = []

    async def __call__(self, invocation):
        self.calls.append(invocation)
        if self.mode == "timeout":
            await asyncio.sleep(1)
        if self.mode == "failure":
            raise RuntimeError("synthetic transport failure; not a business review")
        if self.mode == "malformed":
            return ModelReply("not JSON", 0, 0)
        supplied = json.loads(invocation.input_json)
        analysis = {
            "outcome": self.outcome,
            "findings": [],
            "revision_requests": [],
            "questions": [],
            "conflict_assessments": [
                {"index": i, "blocking": self.blocking,
                 "reason": "Synthetic fixture disposition, not a semantic model judgement."}
                for i, _ in enumerate(supplied["retrieval_result"]["conflicts"])
            ],
        }
        if self.mode == "authority":
            analysis["approval_record"] = {"decision": "APPROVE"}
        return ModelReply(json.dumps(analysis), 0, 0)


@unittest.skipUnless(
    HAS_ADMISSION_FILESYSTEM,
    "exact-byte admission needs O_DIRECTORY, O_NOFOLLOW and O_NONBLOCK; unsupported hosts fail closed",
)
class CHandoffRehearsalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="returnops-c-handoff-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.corpus = json.loads(
            (ROOT / "experiments/c1_grounding_candidate/data/corpus.json").read_bytes())
        # Separate the old pilot's null-version courtesy source identity. Only
        # this temporary fixture changes; the repository corpus stays untouched.
        for entry in self.corpus["passages"]:
            if entry["passage"]["source_version"] is None:
                entry["passage"]["document_id"] = "synthetic-courtesy-document"
        raw = encoded(self.corpus)
        self.manifest = {
            "format_version": 1, "corpus_file": "corpus.json",
            "corpus_sha256": sha256(raw).hexdigest(),
            "corpus_version": self.corpus["corpus_version"],
            "review": {
                "status": "APPROVED_EXACT_BYTES", "author": "synthetic-author",
                "reviewer": "synthetic-reviewer", "reviewed_at": AT,
                # Deliberately fabricated fixture; never fetched or cited as approval.
                "evidence_uri": "https://github.com/shuxiachai/returnops-au/pull/1#pullrequestreview-1",
            },
            "coverage": {
                "issue_categories": ["FAULTY_OR_QUALITY_ISSUE", "WRONG_ITEM", "CHANGE_OF_MIND"],
                "conflicts_reviewed": True,
            },
            "passages": [{key: entry["passage"][key]
                          for key in ("passage_id", "content_sha256")}
                         for entry in self.corpus["passages"]],
        }
        (self.directory / "corpus.json").write_bytes(raw)
        self.write_manifest()

    def write_manifest(self):
        raw = encoded(self.manifest)
        (self.directory / "admission-manifest.json").write_bytes(raw)
        self.pin = sha256(raw).hexdigest()

    def handoff(self, *, category="FAULTY_OR_QUALITY_ISSUE", query="paper receipt"):
        grounding = ReviewedGroundingCandidate.from_directory(
            self.directory, trusted_manifest_sha256=self.pin, top_k=1, clock=lambda: AT)
        request = deepcopy(next(item["value"] for item in EXAMPLES
                                if item["name"] == "risk-review-request"))
        packet = request["packet"]
        packet["corpus_version"] = self.corpus["corpus_version"]
        packet["facts"]["issue_category"] = category
        original = grounding.retrieve({
            "case_id": packet["case_id"], "input_version": packet["input_version"],
            "corpus_version": packet["corpus_version"], "issue_category": category,
            "query": query,
        })
        self.assertTrue(original["passages"])
        # A fixed Assessment stand-in cites just one passage. C2 must still
        # receive all original passages and registered conflicts, including
        # conflict counterparts not cited by the Assessment stand-in.
        passage = original["passages"][0]
        packet["citations"] = [{
            "citation_id": "citation-handoff-test",
            **{key: passage[key] for key in (
                "passage_id", "document_id", "source_version", "corpus_version",
                "content_sha256", "location")},
        }]
        request["retrieval_result"] = deepcopy(original)
        request["citation_verification"] = grounding.verify_citations({
            **{key: packet[key] for key in BINDINGS}, "citations": packet["citations"],
        })
        self.assertTrue(validator("RiskReviewRequest").is_valid(request))
        return request, deepcopy(packet), original

    async def review(self, request, current, original, transport):
        candidate = RiskReviewerCandidate(
            transport, provider_id="provider-handoff-stub", model_id="no-live-model-stub",
            clock=lambda: AT, timeout_seconds=0.01 if transport.mode == "timeout" else 1,
        )
        return await candidate.review(request, current_packet=current, original_retrieval=original,
                                      review_id="review-handoff-test", run_id="run-risk-handoff-test")

    def assert_non_executable(self, review):
        self.assertTrue(validator("RiskReview").is_valid(review))
        self.assertFalse(validator("ApprovalRecord").is_valid(review))
        self.assertFalse(validator("CommandSpec").is_valid(review))
        self.assertFalse({"approval", "approval_id", "commands", "case_status"} & review.keys())

    async def test_admission_retrieval_citations_and_full_source_review_compose(self):
        request, current, original = self.handoff()
        before = deepcopy(request)
        self.assertGreater(len(original["passages"]), 1)  # Conflict closure exceeds top_k=1.
        self.assertTrue(original["conflicts"])
        self.assertEqual({check["result"] for check in request["citation_verification"]["checks"]}, {"VALID"})
        transport = StubReviewerTransport()
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            review = await self.review(request, current, original, transport)
        self.assertEqual(review["outcome"], "ESCALATE")
        self.assertEqual(request, before)
        self.assertEqual(len(transport.calls), 1)
        invocation = transport.calls[0]
        self.assertEqual(json.loads(invocation.input_json)["retrieval_result"], original)
        self.assertEqual(invocation.system_prompt, SYSTEM_PROMPT)
        self.assertEqual(invocation.prompt_version, PROMPT_VERSION)
        self.assertNotEqual(review["model_run"]["run_id"], current["model_run"]["run_id"])
        for conflict in original["conflicts"]:
            self.assertTrue(any(conflict in finding["message"] for finding in review["findings"]))
        self.assert_non_executable(review)

    async def test_no_conflict_stub_pass_is_a_review_not_an_approval(self):
        request, current, original = self.handoff(category="WRONG_ITEM", query="SKU")
        self.assertEqual(original["conflicts"], [])
        review = await self.review(request, current, original, StubReviewerTransport("PASS"))
        self.assertEqual(review["outcome"], "PASS")
        self.assert_non_executable(review)

    async def test_pending_fixture_corpus_stops_before_retrieval_or_model(self):
        self.manifest["review"].update(status="PENDING_EXACT_BYTES_REVIEW", reviewer=None,
                                       reviewed_at=None, evidence_uri=None)
        self.write_manifest()
        transport = StubReviewerTransport()
        with self.assertRaisesRegex(GroundingError, "UNREVIEWED_CORPUS"):
            request, current, original = self.handoff()
            await self.review(request, current, original, transport)
        self.assertEqual(transport.calls, [])

    async def test_original_source_substitution_and_omission_stop_before_model(self):
        for mutation in ("uncited_passage", "conflict", "self_consistent_replacement"):
            with self.subTest(mutation=mutation):
                request, current, original = self.handoff()
                if mutation == "uncited_passage":
                    request["retrieval_result"]["passages"].pop()
                elif mutation == "conflict":
                    request["retrieval_result"]["conflicts"].clear()
                else:
                    passage = request["retrieval_result"]["passages"][0]
                    passage["content"] += " SYNTHETIC injected replacement."
                    passage["content_sha256"] = sha256(passage["content"].encode()).hexdigest()
                    request["packet"]["citations"][0]["content_sha256"] = passage["content_sha256"]
                    current = deepcopy(request["packet"])
                transport = StubReviewerTransport()
                with self.assertRaisesRegex(RiskReviewError, "RETRIEVAL_CHANGED"):
                    await self.review(request, current, original, transport)
                self.assertEqual(transport.calls, [])

    async def test_new_proposal_and_input_versions_reject_old_handoff(self):
        for field in ("proposal_version", "input_version"):
            with self.subTest(field=field):
                request, current, original = self.handoff()
                current[field] += 1
                transport = StubReviewerTransport()
                with self.assertRaisesRegex(RiskReviewError, "STALE_PACKET"):
                    await self.review(request, current, original, transport)
                self.assertEqual(transport.calls, [])

    async def test_real_c1_citation_failure_cannot_be_promoted_to_pass(self):
        request, current, original = self.handoff(category="WRONG_ITEM", query="SKU")
        request["packet"]["citations"][0]["location"] = "synthetic-nonexistent-location"
        current = deepcopy(request["packet"])
        grounding = ReviewedGroundingCandidate.from_directory(
            self.directory, trusted_manifest_sha256=self.pin, clock=lambda: AT)
        request["citation_verification"] = grounding.verify_citations({
            **{key: current[key] for key in BINDINGS}, "citations": current["citations"],
        })
        self.assertEqual(request["citation_verification"]["checks"][0]["result"], "LOCATION_MISMATCH")
        transport = StubReviewerTransport("PASS")
        with self.assertRaisesRegex(RiskReviewError, "UNSAFE_MODEL_OUTPUT"):
            await self.review(request, current, original, transport)
        self.assertEqual(len(transport.calls), 1)

    async def test_material_conflict_cannot_be_hidden_by_passing_stub(self):
        for outcome in ("PASS", "PASS_WITH_WARNING"):
            with self.subTest(outcome=outcome):
                request, current, original = self.handoff()
                transport = StubReviewerTransport(outcome, blocking=True)
                with self.assertRaisesRegex(RiskReviewError, "UNSAFE_MODEL_OUTPUT"):
                    await self.review(request, current, original, transport)
                self.assertEqual(len(transport.calls), 1)

    async def test_nonblocking_conflict_still_has_visible_warning(self):
        request, current, original = self.handoff()
        review = await self.review(request, current, original,
                                   StubReviewerTransport("PASS_WITH_WARNING", blocking=False))
        self.assertEqual(review["outcome"], "PASS_WITH_WARNING")
        self.assertTrue(all(item["severity"] == "WARNING" for item in review["findings"]))
        self.assert_non_executable(review)

    async def test_transport_errors_return_no_review_or_retry(self):
        for mode, code in (("malformed", "INVALID_MODEL_OUTPUT"), ("authority", "INVALID_MODEL_OUTPUT"),
                           ("failure", "MODEL_FAILURE"), ("timeout", "MODEL_TIMEOUT")):
            with self.subTest(mode=mode):
                request, current, original = self.handoff()
                transport = StubReviewerTransport(mode=mode)
                with self.assertRaisesRegex(RiskReviewError, code):
                    await self.review(request, current, original, transport)
                self.assertEqual(len(transport.calls), 1)


class CHandoffUnsupportedFilesystemTests(unittest.TestCase):
    def test_missing_admission_capabilities_refuse_before_any_file_open(self):
        # Runs even on native unsupported hosts. Supply the other capability
        # names only to isolate each missing flag; no OS call may use them.
        for missing in [(flag,) for flag in ADMISSION_FLAGS] + [ADMISSION_FLAGS]:
            with self.subTest(missing=missing), patch.dict(
                admission.os.__dict__, {flag: 1 for flag in ADMISSION_FLAGS},
            ):
                for flag in missing:
                    delattr(admission.os, flag)
                with patch.object(admission.os, "open", side_effect=AssertionError("File I/O forbidden")) as opened:
                    with self.assertRaises(GroundingError) as caught:
                        ReviewedGroundingCandidate.from_directory(
                            "synthetic-path-never-opened", trusted_manifest_sha256="a" * 64,
                        )
                self.assertEqual(caught.exception.code, "UNSUPPORTED_FILESYSTEM")
                self.assertIsNone(caught.exception.__cause__)
                self.assertIsNone(caught.exception.__context__)
                opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
