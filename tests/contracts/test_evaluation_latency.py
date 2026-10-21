"""Public invented event arithmetic, not real model or Gold performance."""
from copy import deepcopy
from decimal import Inexact, InvalidOperation, ROUND_DOWN, ROUND_UP, Rounded, localcontext
import unittest

from experiments.evaluation_candidate import DATA_ROLE
from experiments.evaluation_candidate.latency import summarize_stub_proposal_latency


def stamp(second=0, fraction=""):
    return f"2026-10-17T00:00:{second:02d}{fraction}Z"


def ready(case_id="a", seconds=10):
    return {"case_id": case_id, "status": "REVIEW_READY", "accepted_complete_at": stamp(),
            "stored_review_ready_at": stamp(seconds), "excluded_waits": []}


def failed(case_id="a"):
    return {"case_id": case_id, "status": "FAILED", "accepted_complete_at": None,
            "stored_review_ready_at": None, "excluded_waits": []}


def wait(left, right, kind="HUMAN"):
    return {"kind": kind, "start_at": stamp(left), "end_at": stamp(right)}


def summarize(expected, observed):
    return summarize_stub_proposal_latency(data_role=DATA_ROLE,
                                           expected_case_ids=expected, observations=observed)


class EvaluationLatencyTests(unittest.TestCase):
    def test_linear_percentiles_and_raw_coverage_are_explicit(self):
        result = summarize(["a", "b"], [ready("a", 10), ready("b", 20)])
        self.assertEqual(result["p50_seconds"], 15)
        self.assertEqual(result["p95_seconds"], 19.5)
        self.assertEqual(result["sample_coverage"], {"numerator": 2, "denominator": 2, "value": 1})
        self.assertEqual(result["percentile_method"], "LINEAR_INCLUSIVE_TYPE_7")
        self.assertFalse(result["formal_performance_claim"])
        self.assertFalse(result["target_acceptance_assessed"])

    def test_union_of_nested_overlapping_adjacent_and_duplicate_waits(self):
        row = ready(seconds=50)
        row["excluded_waits"] = [wait(10, 20), wait(15, 30, "PHYSICAL"), wait(12, 18),
                                 wait(30, 35), wait(10, 20), wait(40, 45)]
        result = summarize(["a"], [row])
        sample = result["per_case"][0]
        self.assertEqual(sample["wall_interval_seconds"], 50)
        self.assertEqual(sample["excluded_wait_seconds"], 30)
        self.assertEqual(sample["proposal_latency_seconds"], 20)

    def test_machine_retry_and_model_work_cannot_be_excluded(self):
        for kind in ("MODEL", "RETRY", "NETWORK", "MACHINE", None, True):
            row = ready()
            row["excluded_waits"] = [wait(1, 3, kind)]
            with self.subTest(kind=kind):
                self.assertEqual(summarize(["a"], [row])["dispositions"]["INVALID"], 1)

    def test_failure_missing_and_invalid_cases_do_not_become_zero_samples(self):
        result = summarize(["a", "b", "c", "d"], [ready(), failed("b"), {"case_id": "c"}])
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["sample_coverage"]["denominator"], 4)
        self.assertEqual(result["p95_seconds"], 10)
        self.assertTrue(result["conditional_on_available_review_ready_samples"])
        for sample in result["per_case"][1:]:
            self.assertIsNone(sample["proposal_latency_seconds"])
        self.assertEqual(result["dispositions"], {"REVIEW_READY": 1, "FAILED": 1,
                                                 "MISSING": 1, "DUPLICATE": 0, "INVALID": 1})

    def test_duplicate_never_wins_and_extras_are_reported(self):
        result = summarize(["a"], [ready(), ready(seconds=1), ready("extra"), None, {"case_id": ""}])
        self.assertEqual(result["dispositions"]["DUPLICATE"], 1)
        self.assertEqual(result["duplicate_case_ids"], ["a"])
        self.assertEqual(result["extra_case_ids"], ["extra"])
        self.assertEqual(result["extra_observation_row_count"], 1)
        self.assertEqual(result["unidentifiable_observation_row_count"], 2)
        self.assertIsNone(result["p95_seconds"])
        self.assertFalse(result["run_structure_valid"])

    def test_empty_and_failure_only_runs_have_null_percentiles(self):
        for expected, observed in (([], []), (["a"], [failed()]), (["a"], [])):
            with self.subTest(expected=expected, observed=observed):
                result = summarize(expected, observed)
                self.assertEqual(result["sample_count"], 0)
                self.assertIsNone(result["p50_seconds"])
                self.assertIsNone(result["p95_seconds"])
                self.assertFalse(result["target_acceptance_assessed"])
        self.assertIsNone(summarize([], [])["sample_coverage"]["value"])

    def test_zero_and_microsecond_duration_are_valid_but_not_target_acceptance(self):
        row = ready(seconds=0)
        self.assertEqual(summarize(["a"], [row])["p95_seconds"], 0)
        row.update(accepted_complete_at=stamp(0, ".000001"),
                   stored_review_ready_at=stamp(0, ".000003"))
        result = summarize(["a"], [row])
        self.assertEqual(result["p50_seconds"], .000002)
        self.assertFalse(result["target_acceptance_assessed"])

    def test_decimal_context_cannot_change_rounding_precision_or_traps(self):
        half = [ready("a", 0), {**ready("b", 0), "stored_review_ready_at": stamp(0, ".000001")}]
        odd_half = [{**ready("a", 0), "stored_review_ready_at": stamp(0, ".000001")},
                    {**ready("b", 0), "stored_review_ready_at": stamp(0, ".000002")}]
        normal = [ready("a", 10), ready("b", 20)]
        for rounding in (ROUND_UP, ROUND_DOWN):
            for precision in (1, 3, 50):
                with self.subTest(rounding=rounding, precision=precision), localcontext() as context:
                    context.rounding, context.prec = rounding, precision
                    for signal in (Inexact, InvalidOperation, Rounded):
                        context.traps[signal] = True
                    self.assertEqual(summarize(["a", "b"], half)["p50_seconds"], 0)
                    self.assertEqual(summarize(["a", "b"], odd_half)["p50_seconds"], .000002)
                    result = summarize(["a", "b"], normal)
                    self.assertEqual(result["p50_seconds"], 15)
                    self.assertEqual(result["p95_seconds"], 19.5)

    def test_failed_shape_cannot_hide_a_completion_or_wait(self):
        for key, value in (("stored_review_ready_at", stamp(10)), ("accepted_complete_at", stamp()),
                           ("excluded_waits", [wait(1, 2)]), ("excluded_waits", None)):
            row = failed()
            row[key] = value
            with self.subTest(key=key):
                self.assertEqual(summarize(["a"], [row])["dispositions"]["INVALID"], 1)

    def test_non_utc_naive_invalid_dates_bool_and_precision_are_rejected(self):
        values = [True, False, 0, None, "2026-10-17T00:00:00", "2026-10-17T00:00:00+00:00",
                  "2026-10-17T11:00:00+11:00", "2026-10-17T00:00:00+99:99", "2026-02-30T00:00:00Z",
                  "2026-10-17T00:00:60Z", "2026-10-17T00:00:00.1234567Z", "2026-10-17T00:00:00Z\n"]
        for value in values:
            row = ready()
            row["accepted_complete_at"] = value
            with self.subTest(value=value):
                self.assertEqual(summarize(["a"], [row])["dispositions"]["INVALID"], 1)

    def test_reverse_endpoints_and_outside_reverse_waits_are_invalid(self):
        rows = [{**ready(), "accepted_complete_at": stamp(20)}]
        for interval in (wait(3, 2), wait(0, 11),
                         {"kind": "HUMAN", "start_at": "2026-10-16T23:59:59Z", "end_at": stamp(2)}):
            rows.append({**ready(), "excluded_waits": [interval]})
        for row in rows:
            self.assertEqual(summarize(["a"], [row])["dispositions"]["INVALID"], 1)

    def test_waits_may_cover_entire_interval_or_zero_time(self):
        for intervals, expected in (([wait(0, 10)], 0), ([wait(2, 2)], 10)):
            result = summarize(["a"], [{**ready(), "excluded_waits": intervals}])
            self.assertEqual(result["p50_seconds"], expected)

    def test_malformed_rows_or_excess_wait_count_are_invalid(self):
        rows = [{**ready(), "unexpected": "ignored?"}, {**ready(), "status": []},
                {**ready(), "excluded_waits": "not-list"},
                {**ready(), "excluded_waits": [wait(1, 2)] * 101},
                {**ready(), "excluded_waits": [{**wait(1, 2), "extra": 1}]}]
        for row in rows:
            self.assertEqual(summarize(["a"], [row])["dispositions"]["INVALID"], 1)

    def test_invalid_scope_nonfinite_and_capacity_reject_whole_manifest(self):
        with self.assertRaises(ValueError):
            summarize_stub_proposal_latency(data_role="GOLD", expected_case_ids=[], observations=[])
        for expected, observed in ((["a", "a"], []), (["a"] * 101, []),
                                    (["a"], [ready()] * 101),
                                    (["a"], [{**ready(), "accepted_complete_at": float("nan")}]),
                                    (["a"], [{**ready(), "accepted_complete_at": float("inf")}]),
                                    (["a"], [{**ready(), "extra": "x" * (2 * 1024 * 1024)}])):
            with self.subTest(count=len(expected)), self.assertRaises(ValueError) as caught:
                summarize(expected, observed)
            self.assertIsNone(caught.exception.__context__)

    def test_inputs_unchanged_and_observation_order_does_not_change_statistics(self):
        expected, observed = ["a", "b"], [ready("b", 20), ready("a", 10)]
        before = deepcopy((expected, observed))
        result = summarize(expected, observed)
        self.assertEqual((expected, observed), before)
        self.assertEqual(result["per_case"][0]["case_id"], "a")
        self.assertEqual(result["p95_seconds"], summarize(expected, observed[::-1])["p95_seconds"])


if __name__ == "__main__":
    unittest.main()
