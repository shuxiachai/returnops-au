"""Public invented scorer fixtures only; not Gold labels or model evaluation."""
import copy
from decimal import Inexact, Rounded, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_UP, localcontext
import unittest

from experiments.evaluation_candidate import DATA_ROLE, score_stub_run


def reference(case_id="synthetic-case", positive=False):
    return {"case_id": case_id, "escalation_expected": positive,
            "acceptable_outcomes": ["ESCALATE"] if positive else ["PASS", "PASS_WITH_WARNING"],
            "required_field_ids": ["synthetic-fact"]}


def result(case_id="synthetic-case", outcome="PASS"):
    return {"case_id": case_id, "status": "SUCCEEDED", "risk_outcome": outcome,
            "present_field_ids": ["synthetic-fact"], "retrieved_passage_ids": [],
            "input_tokens": None, "output_tokens": None, "estimated_cost": None}


def score(expected, observed, configuration="B4_OFFLINE_STUB"):
    return score_stub_run(configuration=configuration, data_role=DATA_ROLE,
                          expectations=expected, observations=observed)


class EvaluationPreparationTests(unittest.TestCase):
    def test_counts_cover_all_expected_cases_and_outcomes(self):
        expected = [reference("positive", True), reference("negative"), reference("missed", True)]
        report = score(expected, [result("positive", "ESCALATE"), result("negative")])
        self.assertEqual(report["completion"], {"numerator": 2, "denominator": 3, "value": 2/3})
        self.assertEqual(report["completion_aware_escalation_recall"], {"numerator": 1, "denominator": 2, "value": .5})
        self.assertEqual(report["escalation_confusion"]["UNSCORED_POSITIVE"], 1)
        self.assertEqual(report["dispositions"]["MISSING"], 1)
        self.assertFalse(report["run_structure_valid"])

    def test_missing_negative_does_not_improve_specificity(self):
        report = score([reference()], [])
        self.assertEqual(report["completion_aware_specificity"]["value"], 0)
        self.assertEqual(report["escalation_confusion"]["TN"], 0)
        self.assertEqual(report["escalation_confusion"]["UNSCORED_NEGATIVE"], 1)

    def test_false_positive_and_false_negative_have_raw_counts(self):
        report = score([reference("p", True), reference("n")], [result("p"), result("n", "ESCALATE")])
        self.assertEqual(report["escalation_confusion"]["FP"], 1)
        self.assertEqual(report["escalation_confusion"]["FN"], 1)
        self.assertEqual(report["acceptable_outcome_agreement"]["numerator"], 0)

    def test_duplicate_output_never_wins_and_extras_are_reported(self):
        report = score([reference()], [result(), result(outcome="ESCALATE"), result("extra")])
        self.assertEqual(report["dispositions"]["DUPLICATE"], 1)
        self.assertEqual(report["extra_case_ids"], ["extra"])
        self.assertEqual(report["extra_observation_row_count"], 1)
        self.assertEqual(report["acceptable_outcome_agreement"]["numerator"], 0)
        self.assertIsNone(report["usage_on_expected_cases"]["input_tokens"]["total"])

    def test_duplicate_expectations_rejected(self):
        with self.assertRaises(ValueError):
            score([reference(), reference()], [result()])

    def test_failed_output_is_not_success_but_usage_is_preserved(self):
        failed = {**result(), "status": "FAILED", "risk_outcome": None,
                  "present_field_ids": [], "input_tokens": 4, "output_tokens": 0,
                  "estimated_cost": "0.010"}
        report = score([reference()], [failed])
        self.assertEqual(report["dispositions"]["FAILED"], 1)
        self.assertEqual(report["completion"]["value"], 0)
        self.assertEqual(report["usage_on_expected_cases"]["input_tokens"]["total"], 4)
        self.assertEqual(report["usage_on_expected_cases"]["estimated_cost"]["total"], "0.010")

    def test_failed_output_cannot_also_be_a_pass(self):
        report = score([reference()], [{**result(), "status": "FAILED"}])
        self.assertEqual(report["dispositions"]["INVALID"], 1)

    def test_unknown_usage_remains_null_and_known_subtotal_is_explicit(self):
        report = score([reference("a"), reference("b")],
                       [{**result("a"), "input_tokens": 3, "estimated_cost": "0.10"}, result("b")])
        for key in ("input_tokens", "estimated_cost"):
            self.assertIsNone(report["usage_on_expected_cases"][key]["total"])
            self.assertEqual(report["usage_on_expected_cases"][key]["unknown_case_count"], 1)
        self.assertEqual(report["usage_on_expected_cases"]["input_tokens"]["known_subtotal"], 3)
        self.assertEqual(report["usage_on_expected_cases"]["estimated_cost"]["known_subtotal"], "0.10")

    def test_cost_sum_is_exact_under_low_precision_rounding_and_traps(self):
        expected = [reference("a"), reference("b")]
        observed = [{**result(cid), "estimated_cost": "1.25"} for cid in ("a", "b")]
        for precision in (1, 2, 28):
            for rounding in (ROUND_DOWN, ROUND_UP, ROUND_FLOOR, ROUND_HALF_EVEN):
                with self.subTest(precision=precision, rounding=rounding), localcontext() as context:
                    context.prec, context.rounding = precision, rounding
                    context.traps[Inexact] = context.traps[Rounded] = True
                    context.clear_flags()
                    usage = score(expected, observed)["usage_on_expected_cases"]["estimated_cost"]
                    self.assertEqual(usage, {"known_case_count": 2, "unknown_case_count": 0,
                                             "known_subtotal": "2.50", "total": "2.50"})
                    self.assertFalse(any(context.flags.values()))
                    self.assertEqual(context.prec, precision)
                    self.assertEqual(context.rounding, rounding)

    def test_cost_sum_keeps_bounds_fractional_precision_and_scientific_zero_safe(self):
        examples = (
            (["1000000000.000000000000", "1000000000.000000000000"], "2000000000.000000000000"),
            (["0.000000000001", "0.000000000001", "0.000000000001"], "0.000000000003"),
            (["1E+3", "2.5E-2", "7.5E-2"], "1000.100"),
            (["0E+999999999999999999", "-0.000", "0E-12"], "0.000000000000"),
            (["0E+999999999999999999", "1.25", "1.25"], "2.50"),
            (["0E+999999999999999999"], "0"),
        )
        for costs, expected_sum in examples:
            with self.subTest(costs=costs), localcontext() as context:
                context.prec, context.Emin, context.Emax, context.capitals = 1, -1, 1, 0
                for signal in context.traps:
                    context.traps[signal] = True
                context.clear_flags()
                expected = [reference(str(i)) for i in range(len(costs))]
                observed = [{**result(str(i)), "estimated_cost": cost} for i, cost in enumerate(costs)]
                report = score(expected, observed)
                self.assertEqual(report["dispositions"]["SUCCEEDED"], len(costs))
                self.assertEqual(report["usage_on_expected_cases"]["estimated_cost"]["total"], expected_sum)
                self.assertFalse(any(context.flags.values()))

    def test_exact_known_cost_sum_does_not_fill_unknown_or_discard_failed_usage(self):
        failed = {**result("b"), "status": "FAILED", "risk_outcome": None,
                  "present_field_ids": [], "estimated_cost": "1.25"}
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = context.traps[Rounded] = True
            report = score([reference(cid) for cid in ("a", "b", "c")],
                           [{**result("a"), "estimated_cost": "1.25"}, failed, result("c")])
        self.assertEqual(report["usage_on_expected_cases"]["estimated_cost"], {
            "known_case_count": 2, "unknown_case_count": 1, "known_subtotal": "2.50", "total": None})
        self.assertEqual(report["dispositions"]["FAILED"], 1)
        self.assertEqual(report["usage_on_expected_cases"]["input_tokens"]["known_subtotal"], 0)

    def test_cost_validation_bounds_still_hold_when_aggregation_is_exact(self):
        costs = ("1000000000.000000000001", "0E-13", "-0.000000000001", "1E999999999999999999")
        for cost in costs:
            with self.subTest(cost=cost), localcontext() as context:
                context.prec = 1
                context.traps[Inexact] = context.traps[Rounded] = True
                report = score([reference()], [{**result(), "estimated_cost": cost}])
                self.assertEqual(report["dispositions"]["INVALID"], 1)
                self.assertEqual(report["usage_on_expected_cases"]["estimated_cost"], {
                    "known_case_count": 0, "unknown_case_count": 1, "known_subtotal": "0", "total": None})

    def test_empty_denominators_are_null(self):
        report = score([], [])
        for key in ("completion", "acceptable_outcome_agreement", "completion_aware_escalation_recall",
                    "completion_aware_specificity", "required_field_id_coverage"):
            self.assertIsNone(report[key]["value"])
        self.assertIsNone(report["usage_on_expected_cases"]["input_tokens"]["total"])

    def test_scope_requires_synthetic_stub_and_b1_rejects_retrieval(self):
        for config, role in (("B4", DATA_ROLE), ([], DATA_ROLE), ("B1_OFFLINE_STUB", "GOLD")):
            with self.assertRaises(ValueError):
                score_stub_run(configuration=config, data_role=role, expectations=[], observations=[])
        report = score([reference()], [{**result(), "retrieved_passage_ids": ["passage"]}], "B1_OFFLINE_STUB")
        self.assertEqual(report["dispositions"]["INVALID"], 1)
        self.assertFalse(report["permissions"]["operation_authority"])
        self.assertFalse(report["permissions"]["retrieval_declared"])
        self.assertFalse(report["formal_performance_claim"])

    def test_malformed_rows_are_not_silently_omitted(self):
        report = score([reference()], [{"case_id": "synthetic-case"}, None, {"case_id": ""}])
        self.assertEqual(report["dispositions"]["INVALID"], 1)
        self.assertEqual(report["unidentifiable_observation_row_count"], 2)
        self.assertFalse(report["run_structure_valid"])

    def test_invalid_tokens_and_nonfinite_costs_rejected(self):
        for key, value in (("input_tokens", True), ("output_tokens", -1),
                           ("estimated_cost", "NaN"), ("estimated_cost", "Infinity"),
                           ("estimated_cost", "-1"), ("estimated_cost", 0.1),
                           ("estimated_cost", "1E999999"), ("estimated_cost", "0.0000000000001")):
            with self.subTest(key=key, value=value):
                report = score([reference()], [{**result(), key: value}])
                self.assertEqual(report["dispositions"]["INVALID"], 1)

    def test_inconsistent_expectations_and_duplicate_field_ids_rejected(self):
        for changed in ({"escalation_expected": True}, {"required_field_ids": ["x", "x"]},
                        {"acceptable_outcomes": []}, {"escalation_expected": 1}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                score([{**reference(), **changed}], [result()])

    def test_coverage_counts_expected_ids_once_not_semantic_truth(self):
        report = score([reference()], [{**result(), "present_field_ids": ["synthetic-fact", "extra-field"]}])
        self.assertEqual(report["required_field_id_coverage"], {"numerator": 1, "denominator": 1, "value": 1})

    def test_inputs_are_unchanged(self):
        expected, observed = [reference()], [result()]
        before = copy.deepcopy((expected, observed))
        score(expected, observed)
        self.assertEqual((expected, observed), before)


if __name__ == "__main__":
    unittest.main()
