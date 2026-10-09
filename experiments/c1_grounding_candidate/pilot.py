"""Public synthetic development pilot for FR-006/007; no acceptance claims.

Run from the source checkout with:
    python -m experiments.c1_grounding_candidate.pilot

Only a JSON report is written to stdout. No network, LLM, Gold data, operation,
database, or runtime API is used. The fixed clock is a test input, not run time.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import unittest

from .grounding import GroundingCandidate


DATA_DIR = Path(__file__).resolve().parent / "data"
FIXED_CLOCK = "2026-10-09T00:00:00Z"
TOP_K = 2
OUTCOMES = (
    "VALID", "NOT_FOUND", "VERSION_MISMATCH", "HASH_MISMATCH", "LOCATION_MISMATCH"
)
CITATION_KEYS = (
    "passage_id", "document_id", "source_version", "corpus_version",
    "content_sha256", "location",
)


def _validate_fixture_maps(corpus: dict, pilot: dict) -> None:
    """Fixture report keys must be unambiguous before building keyed counts."""
    messages = [entry["message"] for entry in corpus["conflicts"]]
    if len(messages) != len(set(messages)):
        raise ValueError("Ambiguous pilot conflict messages")
    fixtures = pilot["citation_fixtures"]
    ids = [fixture["fixture_id"] for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate pilot citation fixture IDs")
    if any(fixture["expected_result"] not in OUTCOMES for fixture in fixtures):
        raise ValueError("Invalid pilot citation expected outcome")


def _load_inputs():
    """Reject changed bytes until their provenance manifest is updated explicitly."""
    manifest = json.loads((DATA_DIR / "manifest.json").read_bytes())
    raw_files = {name: (DATA_DIR / name).read_bytes()
                 for name in ("corpus.json", "pilot_queries.json")}
    digests = {name: sha256(raw).hexdigest() for name, raw in raw_files.items()}
    for name, digest in digests.items():
        if digest != manifest["files"][name]["sha256"]:
            raise ValueError(f"Raw file digest mismatch: {name}")
    corpus = json.loads(raw_files["corpus.json"])
    pilot = json.loads(raw_files["pilot_queries.json"])
    if not (corpus["corpus_version"] == pilot["corpus_version"]
            == manifest["corpus_version"] == "synthetic-pilot-v1"):
        raise ValueError("Corpus version mismatch")
    if pilot["pilot_version"] != manifest["pilot_version"]:
        raise ValueError("Pilot version mismatch")
    if (pilot["dataset_role"] != "PUBLIC_DEVELOPMENT_PILOT_NOT_GOLD"
            or not all(item["is_synthetic"] is True for item in (corpus, pilot, manifest))
            or not all(item["review_status"] == "PENDING_HUMAN_REVIEW"
                       for item in (corpus, pilot, manifest))
            or manifest["human_approval"] is not False):
        raise ValueError("Synthetic development boundary mismatch")
    _validate_fixture_maps(corpus, pilot)
    passage_ids = {entry["passage"]["passage_id"] for entry in corpus["passages"]}
    conflict_ids = {entry["conflict_id"] for entry in corpus["conflicts"]}
    query_ids = [row["query_id"] for row in pilot["queries"]]
    if not 10 <= len(query_ids) <= 12 or len(query_ids) != len(set(query_ids)):
        raise ValueError("Pilot query identity or count mismatch")
    for row in pilot["queries"]:
        expected = row["expected_passage_ids"]
        conflicts = row["expected_conflict_ids"]
        if (not set(expected).issubset(passage_ids)
                or len(expected) != len(set(expected))
                or not set(conflicts).issubset(conflict_ids)
                or len(conflicts) != len(set(conflicts))
                or row["expected_status"] != ("MATCHED" if expected else "NO_MATCH")):
            raise ValueError("Invalid pilot relevance labels")
    return raw_files, digests, corpus, pilot, manifest


def _recall(relevant_retrieved: int, expected_relevant: int) -> dict:
    return {
        "relevant_retrieved_count": relevant_retrieved,
        "expected_relevant_count": expected_relevant,
        "recall": relevant_retrieved / expected_relevant if expected_relevant else None,
    }


def _handoff_example(candidate: GroundingCandidate, request: dict, result: dict) -> dict:
    citations = [{
        **{key: passage[key] for key in CITATION_KEYS},
        "citation_id": f"synthetic-handoff-citation-{index}",
    } for index, passage in enumerate(result["passages"], start=1)]
    verification_request = {
        **{key: request[key] for key in ("case_id", "input_version", "corpus_version")},
        "proposal_id": "synthetic-handoff-proposal", "proposal_version": 1,
        "citations": citations,
    }
    return {
        "scope": "Offline contract-shaped C1 handoff example only. No C2 result, current-case authority, runtime integration, actual proposal or execution authority exists. Conflicts are preserved unchanged for a future consumer; citation validity does not resolve them.",
        "retrieval_request": request,
        "retrieval_result": result,
        "citation_verification_request": verification_request,
        "citation_verification_result": candidate.verify_citations(verification_request),
    }


def run_pilot() -> dict:
    raw_files, digests, corpus, pilot, manifest = _load_inputs()
    candidate = GroundingCandidate.from_bytes(
        raw_files["corpus.json"], top_k=TOP_K, clock=lambda: FIXED_CLOCK
    )
    # An in-memory probe uses the same passages and retrieval API, suppressing
    # only conflict expansion. Its bytes are never stored as the canonical corpus.
    seed_probe_raw = json.dumps({**corpus, "conflicts": []}, ensure_ascii=False,
                                sort_keys=True).encode("utf-8")
    seed_probe = GroundingCandidate.from_bytes(
        seed_probe_raw, top_k=TOP_K, clock=lambda: FIXED_CLOCK
    )
    conflict_messages = {entry["message"]: entry["conflict_id"]
                         for entry in corpus["conflicts"]}
    rows = []
    for row in pilot["queries"]:
        request = {
            "case_id": row["query_id"], "input_version": 1,
            "query": row["query"], "issue_category": row["issue_category"],
            "corpus_version": corpus["corpus_version"],
        }
        result = candidate.retrieve(request)
        if not rows:
            handoff = _handoff_example(candidate, request, result)
        seeds = seed_probe.retrieve(request)
        seed_ids = [passage["passage_id"] for passage in seeds["passages"]]
        returned_ids = [passage["passage_id"] for passage in result["passages"]]
        expected = set(row["expected_passage_ids"])
        actual_conflicts = [conflict_messages[message] for message in result["conflicts"]]
        rows.append({
            **row,
            "actual_status": result["status"],
            "status_matches_expected": result["status"] == row["expected_status"],
            "ranked_seed_passage_ids": seed_ids,
            "ranked_seed_count": len(seed_ids),
            "ranked_recall_at_k": _recall(len(expected.intersection(seed_ids)), len(expected)),
            "returned_passage_ids": returned_ids,
            "returned_count": len(returned_ids),
            "conflict_added_passage_ids": [pid for pid in returned_ids if pid not in seed_ids],
            "returned_set_recall": _recall(len(expected.intersection(returned_ids)), len(expected)),
            "missing_expected_passage_ids": sorted(expected.difference(returned_ids)),
            "unexpected_returned_passage_ids": sorted(set(returned_ids).difference(expected)),
            "actual_conflict_ids": actual_conflicts,
            "actual_conflict_messages": result["conflicts"],
            "conflicts_match_expected": set(actual_conflicts) == set(row["expected_conflict_ids"]),
            "retrieved_at": result["retrieved_at"],
        })
    passages = {entry["passage"]["passage_id"]: entry["passage"]
                for entry in corpus["passages"]}
    citations = []
    for fixture in pilot["citation_fixtures"]:
        passage = passages[fixture["passage_id"]]
        citations.append({
            **{key: passage[key] for key in CITATION_KEYS},
            **fixture["overrides"], "citation_id": fixture["fixture_id"],
        })
    verification = candidate.verify_citations({
        "case_id": "synthetic-pilot-citations", "input_version": 1,
        "proposal_id": "synthetic-pilot-proposal", "proposal_version": 1,
        "corpus_version": corpus["corpus_version"], "citations": citations,
    })
    checks = {check["citation_id"]: check for check in verification["checks"]}
    citation_rows = [{
        "fixture_id": fixture["fixture_id"],
        "citation": citation,
        "expected_result": fixture["expected_result"],
        "actual_result": checks[fixture["fixture_id"]]["result"],
        "matches_expected": checks[fixture["fixture_id"]]["result"] == fixture["expected_result"],
    } for fixture, citation in zip(pilot["citation_fixtures"], citations)]
    observed_counts = Counter(row["actual_result"] for row in citation_rows)
    expected_counts = Counter(row["expected_result"] for row in citation_rows)
    expected_total = sum(len(row["expected_passage_ids"]) for row in rows)
    seed_relevant_total = sum(row["ranked_recall_at_k"]["relevant_retrieved_count"] for row in rows)
    returned_relevant_total = sum(row["returned_set_recall"]["relevant_retrieved_count"] for row in rows)
    return {
        "report_type": "SYNTHETIC_OFFLINE_DEVELOPMENT_PILOT",
        "pilot_version": pilot["pilot_version"],
        "corpus_version": corpus["corpus_version"],
        "dataset_role": pilot["dataset_role"],
        "provenance_label": manifest["provenance_label"],
        "review_status": manifest["review_status"],
        "human_approval": False,
        "formal_performance_claim": False,
        "limitations": manifest["provenance_notes"],
        "runtime": {"python_version": platform.python_version(),
                    "python_implementation": platform.python_implementation()},
        "hashes": {"corpus_sha256": digests["corpus.json"],
                   "pilot_sha256": digests["pilot_queries.json"]},
        "configuration": {
            "top_k": TOP_K,
            "retrieval_clock_mode": "FIXED_TEST_CLOCK_NOT_EXECUTION_TIME",
            "fixed_retrieval_time": FIXED_CLOCK,
            "ranked_seed_method": "Same retrieval API over in-memory identical passages with conflicts=[]; not a persisted corpus generation.",
            "ranked_recall_at_k_definition": "Sum of relevant ranked seeds divided by sum of expected relevant passages; micro Recall@2 before conflict expansion.",
            "returned_set_recall_definition": "Sum of relevant passages actually returned divided by sum of expected relevant passages; includes conflict expansion and is not Recall@k.",
            "empty_relevance_rule": "Per-query recall is null for zero expected relevant passages; report NO_MATCH checks separately.",
        },
        "retrieval_summary": {
            "query_count": len(rows),
            "queries_with_expected_relevance": sum(bool(row["expected_passage_ids"]) for row in rows),
            "expected_no_match_count": sum(row["expected_status"] == "NO_MATCH" for row in rows),
            "actual_no_match_count": sum(row["actual_status"] == "NO_MATCH" for row in rows),
            "correct_no_match_count": sum(row["expected_status"] == row["actual_status"] == "NO_MATCH" for row in rows),
            "status_mismatch_count": sum(not row["status_matches_expected"] for row in rows),
            "conflict_mismatch_count": sum(not row["conflicts_match_expected"] for row in rows),
            "ranked_seed_total_count": sum(row["ranked_seed_count"] for row in rows),
            "returned_total_count": sum(row["returned_count"] for row in rows),
            "returned_count_exceeds_k_query_count": sum(row["returned_count"] > TOP_K for row in rows),
            "ranked_recall_at_k": _recall(seed_relevant_total, expected_total),
            "returned_set_recall": _recall(returned_relevant_total, expected_total),
            "queries_missing_expected_passages": [row["query_id"] for row in rows if row["missing_expected_passage_ids"]],
        },
        "retrieval_results": rows,
        "handoff_example": handoff,
        "citation_summary": {
            "check_count": len(citation_rows),
            "expected_outcome_counts": {outcome: expected_counts[outcome] for outcome in OUTCOMES},
            "actual_outcome_counts": {outcome: observed_counts[outcome] for outcome in OUTCOMES},
            "exact_outcome_match_count": sum(row["matches_expected"] for row in citation_rows),
            "exact_outcome_mismatch_count": sum(not row["matches_expected"] for row in citation_rows),
            "valid_fixture_count": expected_counts["VALID"],
            "valid_accepted_count": sum(row["expected_result"] == row["actual_result"] == "VALID" for row in citation_rows),
            "invalid_fixture_count": len(citation_rows) - expected_counts["VALID"],
            "invalid_rejected_count": sum(row["expected_result"] != "VALID" and row["actual_result"] != "VALID" for row in citation_rows),
            "invalid_accepted_count": sum(row["expected_result"] != "VALID" and row["actual_result"] == "VALID" for row in citation_rows),
            "checked_at": verification["checked_at"],
            "scope": "Identity/version/hash/location checks only; no claim-support or legal-correctness score.",
        },
        "citation_results": citation_rows,
    }


class PilotReportTests(unittest.TestCase):
    """Reporting regressions; relevance misses are results, not test failures."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_pilot()

    def test_recall_denominators_use_expected_labels(self):
        rows = self.report["retrieval_results"]
        expected = sum(len(row["expected_passage_ids"]) for row in rows)
        for key in ("ranked_recall_at_k", "returned_set_recall"):
            summary = self.report["retrieval_summary"][key]
            self.assertEqual(summary["expected_relevant_count"], expected)
            self.assertEqual(summary["relevant_retrieved_count"],
                             sum(row[key]["relevant_retrieved_count"] for row in rows))
        for row in rows:
            if not row["expected_passage_ids"]:
                self.assertIsNone(row["ranked_recall_at_k"]["recall"])
                self.assertIsNone(row["returned_set_recall"]["recall"])

    def test_ranked_seed_and_expanded_return_are_separate(self):
        rows = self.report["retrieval_results"]
        self.assertTrue(all(row["ranked_seed_count"] <= TOP_K for row in rows))
        self.assertTrue(any(row["returned_count"] > TOP_K for row in rows))
        self.assertTrue(any(row["missing_expected_passage_ids"] for row in rows))

    def test_all_citation_outcomes_are_counted(self):
        summary = self.report["citation_summary"]
        self.assertEqual(set(summary["actual_outcome_counts"]), set(OUTCOMES))
        self.assertTrue(all(summary["actual_outcome_counts"].values()))
        self.assertEqual(summary["exact_outcome_mismatch_count"], 0)
        self.assertEqual(summary["valid_fixture_count"] + summary["invalid_fixture_count"],
                         summary["check_count"])

    def test_fixed_clock_and_hashes_are_reported(self):
        self.assertTrue(all(row["retrieved_at"] == FIXED_CLOCK
                            for row in self.report["retrieval_results"]))
        self.assertEqual(self.report["citation_summary"]["checked_at"], FIXED_CLOCK)
        self.assertEqual(self.report["hashes"]["corpus_sha256"],
                         sha256((DATA_DIR / "corpus.json").read_bytes()).hexdigest())
        self.assertEqual(self.report["hashes"]["pilot_sha256"],
                         sha256((DATA_DIR / "pilot_queries.json").read_bytes()).hexdigest())

    def test_handoff_contracts_bindings_citations_and_conflicts(self):
        from jsonschema import Draft202012Validator, FormatChecker

        definitions = json.loads(
            (Path(__file__).resolve().parents[2] / "contracts/v1/schemas.json")
            .read_bytes()
        )["$defs"]
        handoff = self.report["handoff_example"]
        dto_names = {
            "retrieval_request": "RetrievalRequest",
            "retrieval_result": "RetrievalResult",
            "citation_verification_request": "CitationVerificationRequest",
            "citation_verification_result": "CitationVerificationResult",
        }
        for key, name in dto_names.items():
            validator = Draft202012Validator(
                {"$ref": f"#/$defs/{name}", "$defs": definitions},
                format_checker=FormatChecker(),
            )
            validator.validate(handoff[key])
        request = handoff["retrieval_request"]
        result = handoff["retrieval_result"]
        citation_request = handoff["citation_verification_request"]
        citation_result = handoff["citation_verification_result"]
        self.assertEqual(request["case_id"], self.report["retrieval_results"][0]["query_id"])
        for key in ("case_id", "input_version", "corpus_version"):
            self.assertEqual({handoff[name][key] for name in dto_names}, {request[key]})
        for key in ("proposal_id", "proposal_version"):
            self.assertEqual(citation_request[key], citation_result[key])
        self.assertEqual(result["conflicts"],
                         self.report["retrieval_results"][0]["actual_conflict_messages"])
        self.assertEqual(len(citation_request["citations"]), len(result["passages"]))
        for citation, passage in zip(citation_request["citations"], result["passages"]):
            self.assertEqual({key: citation[key] for key in CITATION_KEYS},
                             {key: passage[key] for key in CITATION_KEYS})
        self.assertEqual([check["citation_id"] for check in citation_result["checks"]],
                         [citation["citation_id"] for citation in citation_request["citations"]])
        self.assertTrue(all(check["result"] == "VALID" for check in citation_result["checks"]))

    def test_ambiguous_fixture_counts_are_rejected(self):
        _, _, original_corpus, original_pilot, _ = _load_inputs()
        for mutation, error in (
            ("duplicate_citation_id", "Duplicate pilot citation fixture IDs"),
            ("invalid_citation_outcome", "Invalid pilot citation expected outcome"),
            ("duplicate_conflict_message", "Ambiguous pilot conflict messages"),
        ):
            with self.subTest(mutation=mutation):
                corpus = json.loads(json.dumps(original_corpus))
                pilot = json.loads(json.dumps(original_pilot))
                if mutation == "duplicate_citation_id":
                    pilot["citation_fixtures"][1]["fixture_id"] = pilot["citation_fixtures"][0]["fixture_id"]
                elif mutation == "invalid_citation_outcome":
                    pilot["citation_fixtures"][0]["expected_result"] = "UNDEFINED_RESULT"
                else:
                    corpus["conflicts"][1]["message"] = corpus["conflicts"][0]["message"]
                with self.assertRaisesRegex(ValueError, error):
                    _validate_fixture_maps(corpus, pilot)


def main() -> None:
    json.dump(run_pilot(), sys.stdout, indent=2, ensure_ascii=False, allow_nan=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
