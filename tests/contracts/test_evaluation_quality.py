"""Invented review judgments test arithmetic, not actual model/source quality."""
from copy import deepcopy
import unittest

from experiments.evaluation_candidate import DATA_ROLE
from experiments.evaluation_candidate.quality import observation_sha256, score_stub_quality


def reference(case_id="a", category="FAULTY"):
    return {"case_id": case_id, "category": category, "required_field_ids": ["purchase"],
            "required_component_ids": ["rationale"], "acceptable_recommendations": ["RETURN", "REPLACE"]}


def output(case_id="a", category="FAULTY"):
    return {"case_id": case_id, "status": "SUCCEEDED", "category": category, "recommendation": "RETURN",
            "fields": {"purchase": {"value": "invented purchase"}}, "components": {"rationale": "invented reason"},
            "questions": {"q1": "Which invented item?"},
            "claims": {"c1": {"text": "Invented claim", "citation_ids": ["cite1"]}},
            "citations": {"cite1": {"source_id": "synthetic-policy", "passage_id": "p1"}}}


def failed(case_id="a"):
    row = output(case_id)
    row.update(status="FAILED", category=None, recommendation=None,
               fields={}, components={}, questions={}, claims={}, citations={})
    return row


def annotation(row):
    return {"case_id": row["case_id"], "observation_sha256": observation_sha256(row),
            "claim_inventory_complete": True,
            "field_correct": dict.fromkeys(row["fields"], True),
            "component_correct": dict.fromkeys(row["components"], True),
            "question_necessary": dict.fromkeys(row["questions"], True),
            "claim_needs_citation": dict.fromkeys(row["claims"], True),
            "claim_critical_fabrication": dict.fromkeys(row["claims"], False),
            "citation_correct": dict.fromkeys(row["citations"], True)}


def score(expected, observed, reviewed, classes=None):
    return score_stub_quality(data_role=DATA_ROLE, class_labels=classes or ["FAULTY"],
                              expectations=expected, observations=observed, annotations=reviewed)


class EvaluationQualityTests(unittest.TestCase):
    def test_known_fixture_arithmetic_and_scope(self):
        rows = [output(), output("b", "OTHER")]
        result = score([reference(), reference("b", "OTHER")], rows,
                       [annotation(row) for row in rows], ["FAULTY", "OTHER"])
        self.assertEqual(result["classification_macro_f1"], 1)
        self.assertEqual(result["completion"], {"numerator": 2, "denominator": 2, "value": 1})
        self.assertEqual(result["bound_annotation_coverage"]["denominator"], 2)
        for key in ("required_field_correctness", "packet_completeness", "claim_citation_coverage", "citation_correctness"):
            self.assertEqual(result[key]["value"], 1)
        self.assertEqual(result["unnecessary_followup_rate"]["value"], 0)
        self.assertEqual(result["critical_fabrication"]["total"], 0)
        self.assertFalse(result["formal_performance_claim"])
        self.assertFalse(result["target_acceptance_assessed"])
        self.assertEqual(result["semantic_judgments"], "CALLER_SUPPLIED_NOT_AUTHENTICATED_OR_INFERRED")

    def test_confusion_and_f1_use_frozen_classes(self):
        rows = [output(), output("b", "FAULTY")]
        result = score([reference(), reference("b", "OTHER")], rows, [], ["FAULTY", "OTHER"])
        self.assertEqual(result["classification_confusion"]["OTHER"]["FAULTY"], 1)
        self.assertAlmostEqual(result["classification_macro_f1"], 1 / 3)
        self.assertEqual(result["classification_per_class"]["FAULTY"]["FP"], 1)
        self.assertEqual(result["classification_per_class"]["OTHER"]["FN"], 1)
        self.assertIsNone(result["classification_per_class"]["OTHER"]["precision"]["value"])

    def test_absent_class_is_not_silently_removed_from_macro(self):
        row = output()
        result = score([reference()], [row], [annotation(row)], ["FAULTY", "OTHER"])
        self.assertIsNone(result["classification_macro_f1"])
        self.assertEqual(result["classification_defined_f1_class_count"], 1)
        self.assertIsNone(result["classification_per_class"]["OTHER"]["f1"])

    def test_unavailable_outputs_remain_in_confusion_and_all_case_denominators(self):
        rows = [output(), failed("b"), {"case_id": "c"}, output("e"), output("e")]
        result = score([reference(key) for key in ("a", "b", "c", "d", "e")], rows, [annotation(rows[0])])
        self.assertEqual(result["dispositions"], {"SUCCEEDED": 1, "FAILED": 1, "MISSING": 1, "DUPLICATE": 1, "INVALID": 1})
        self.assertEqual(result["classification_confusion"]["FAULTY"]["UNAVAILABLE"], 4)
        self.assertEqual(result["classification_per_class"]["FAULTY"]["FN"], 4)
        self.assertAlmostEqual(result["classification_macro_f1"], 1 / 3)
        self.assertEqual(result["completion_aware_recommendation_agreement"]["value"], .2)
        self.assertEqual(result["required_field_correctness"]["denominator"], 5)
        self.assertEqual(result["required_field_correctness"]["unknown"], 4)
        self.assertEqual(result["required_field_correctness"]["confirmed_lower_bound"]["value"], .2)
        self.assertIsNone(result["critical_fabrication"]["total"])
        self.assertIsNone(result["unnecessary_followup_rate"]["value"])
        self.assertIsNone(result["citation_correctness"]["value"])

    def test_failure_only_is_neither_fabrication_free_nor_perfect_classification(self):
        result = score([reference()], [failed()], [])
        self.assertEqual(result["classification_macro_f1"], 0)
        self.assertIsNone(result["critical_fabrication"]["total"])
        self.assertIsNone(result["claim_citation_coverage"]["value"])
        self.assertEqual(result["critical_fabrication"]["unknown_case_count"], 1)

    def test_empty_run_and_zero_denominators_are_unknown(self):
        result = score([], [], [])
        for key in ("required_field_correctness", "packet_completeness", "claim_citation_coverage",
                    "citation_correctness", "unnecessary_followup_rate", "completion"):
            self.assertIsNone(result[key]["value"])
        self.assertIsNone(result["classification_macro_f1"])
        self.assertIsNone(result["critical_fabrication"]["total"])

    def test_presence_or_nonempty_text_does_not_establish_semantic_correctness(self):
        row = output()
        review = annotation(row)
        review["field_correct"]["purchase"] = False
        review["component_correct"]["rationale"] = False
        review["citation_correct"]["cite1"] = False
        result = score([reference()], [row], [review])
        for key in ("required_field_correctness", "packet_completeness", "claim_citation_coverage", "citation_correctness"):
            self.assertEqual(result[key]["value"], 0)

    def test_absent_required_items_are_known_missing_not_optional(self):
        row = output()
        row["fields"], row["components"] = {}, {}
        result = score([reference()], [row], [])
        for key in ("required_field_correctness", "packet_completeness"):
            self.assertEqual(result[key]["value"], 0)
            self.assertEqual(result[key]["incorrect_or_missing"], 1)

    def test_missing_partial_and_null_annotations_stay_unknown(self):
        row = output()
        review = annotation(row)
        review["field_correct"].clear()
        review["component_correct"]["rationale"] = None
        review["question_necessary"]["q1"] = None
        review["claim_critical_fabrication"]["c1"] = None
        review["citation_correct"]["cite1"] = None
        for reviews in ([], [review]):
            result = score([reference()], [row], reviews)
            for key in ("required_field_correctness", "packet_completeness", "unnecessary_followup_rate",
                        "citation_correctness", "claim_citation_coverage"):
                self.assertIsNone(result[key]["value"])
            self.assertIsNone(result["critical_fabrication"]["total"])

    def test_fabricated_claims_count_once_and_need_complete_inventory(self):
        row = output()
        row["claims"]["c2"] = {"text": "Another invented claim", "citation_ids": []}
        review = annotation(row)
        review["claim_critical_fabrication"] = {"c1": True, "c2": True}
        result = score([reference()], [row], [review])
        self.assertEqual(result["critical_fabrication"]["total"], 2)
        self.assertEqual(result["critical_fabrication"]["case_ids_with_known_fabrication"], ["a"])
        for complete in (False, None):
            review["claim_inventory_complete"] = complete
            result = score([reference()], [row], [review])
            self.assertIsNone(result["critical_fabrication"]["total"])
            self.assertEqual(result["critical_fabrication"]["known_claim_subtotal"], 2)
            self.assertIsNone(result["claim_citation_coverage"]["value"])

    def test_followup_counts_items_and_no_question_cases_separately(self):
        a, b = output(), output("b")
        a["questions"]["q2"] = "Another unnecessary invented question?"
        b["questions"] = {}
        reviews = [annotation(a), annotation(b)]
        reviews[0]["question_necessary"]["q2"] = False
        result = score([reference(), reference("b")], [a, b], reviews)
        self.assertEqual(result["unnecessary_followup_rate"]["observed_denominator"], 2)
        self.assertEqual(result["unnecessary_followup_rate"]["value"], .5)
        self.assertEqual(result["no_question_case_count"], 1)
        result = score([reference("b")], [b], [reviews[1]])
        self.assertIsNone(result["unnecessary_followup_rate"]["value"])

    def test_claim_coverage_and_citation_correctness_have_different_units(self):
        row = output()
        row["claims"]["c1"]["citation_ids"].append("cite2")
        row["citations"]["cite2"] = {"source_id": "synthetic-policy", "passage_id": "p2"}
        review = annotation(row)
        review["citation_correct"]["cite2"] = False
        result = score([reference()], [row], [review])
        self.assertEqual(result["claim_citation_coverage"]["value"], 1)
        self.assertEqual(result["citation_correctness"]["value"], .5)
        review["citation_correct"]["cite2"] = None
        result = score([reference()], [row], [review])
        self.assertEqual(result["claim_citation_coverage"]["value"], 1)
        self.assertIsNone(result["citation_correctness"]["value"])

    def test_unknown_citation_need_cannot_be_excluded_from_denominator(self):
        row = output()
        review = annotation(row)
        review["claim_needs_citation"]["c1"] = None
        result = score([reference()], [row], [review])
        self.assertIsNone(result["claim_citation_coverage"]["value"])
        self.assertEqual(result["citation_requirement_unknown_claim_count"], 1)
        review["claim_needs_citation"]["c1"] = False
        result = score([reference()], [row], [review])
        self.assertIsNone(result["claim_citation_coverage"]["value"])

    def test_acceptable_recommendation_set_allows_alternatives_without_risk_conflation(self):
        row = output()
        for recommendation, expected in (("RETURN", 1), ("REPLACE", 1), ("DECLINE", 0)):
            row["recommendation"] = recommendation
            result = score([reference()], [row], [])
            self.assertEqual(result["completion_aware_recommendation_agreement"]["value"], expected)

    def test_content_mutation_cannot_reuse_old_semantic_judgments(self):
        original = output()
        review = annotation(original)
        mutations = [("fields", {"purchase": "changed"}), ("components", {"rationale": "changed"}),
                     ("questions", {"q1": "changed?"}),
                     ("claims", {"c1": {"text": "changed", "citation_ids": ["cite1"]}}),
                     ("citations", {"cite1": {"source_id": "changed", "passage_id": "p1"}})]
        for key, value in mutations:
            changed = {**original, key: value}
            with self.subTest(key=key):
                result = score([reference()], [changed], [review])
                self.assertEqual(result["annotation_dispositions"]["INVALID"], 1)
                self.assertEqual(result["dispositions"]["SUCCEEDED"], 1)
                self.assertIsNone(result["critical_fabrication"]["total"])

    def test_digest_canonicalizes_dictionary_order_not_content(self):
        row = output()
        self.assertEqual(observation_sha256(row), observation_sha256(dict(reversed(list(row.items())))))
        self.assertEqual(len(observation_sha256(row)), 64)
        row["fields"]["purchase"] = "changed"
        self.assertNotEqual(observation_sha256(row), observation_sha256(output()))

    def test_duplicate_annotations_never_pick_a_favorable_row(self):
        row = output()
        good, bad = annotation(row), annotation(row)
        bad["claim_critical_fabrication"]["c1"] = True
        for reviews in ([good, bad], [bad, good]):
            result = score([reference()], [row], reviews)
            self.assertEqual(result["annotation_dispositions"]["DUPLICATE"], 1)
            self.assertIsNone(result["critical_fabrication"]["total"])
            self.assertEqual(result["bound_annotation_coverage"]["value"], 0)

    def test_extras_unidentifiable_rows_and_duplicate_extras_are_reported(self):
        row, extra = output(), output("extra")
        result = score([reference()], [row, extra, extra, None], [annotation(row), annotation(extra), None])
        self.assertEqual(result["output_structure"]["extra_case_ids"], ["extra"])
        self.assertEqual(result["output_structure"]["extra_row_count"], 2)
        self.assertEqual(result["output_structure"]["unidentifiable_row_count"], 1)
        self.assertEqual(result["annotation_structure"]["unidentifiable_row_count"], 1)
        self.assertFalse(result["run_structure_valid"])
        self.assertEqual(result["expected_case_count"], 1)

    def test_invalid_annotation_ids_boolean_coercion_and_hash_are_rejected(self):
        row = output()
        for key, value in (("field_correct", {"invented-extra": True}), ("field_correct", {"purchase": 1}),
                           ("claim_inventory_complete", 1), ("claim_inventory_complete", "true"),
                           ("citation_correct", {"cite1": "false"}), ("observation_sha256", "0" * 64)):
            review = annotation(row)
            review[key] = value
            with self.subTest(key=key, value=value):
                result = score([reference()], [row], [review])
                self.assertEqual(result["annotation_dispositions"]["INVALID"], 1)
                self.assertIsNone(result["critical_fabrication"]["total"])

    def test_invalid_outputs_fail_closed_without_throwing_or_getting_credit(self):
        variants = [{**output(), "category": "UNLISTED"}, {**output(), "category": []},
                    {**output(), "questions": []}, {**output(), "status": True},
                    {**failed(), "recommendation": "RETURN"}, {**output(), "extra": True}]
        for mutate in (lambda row: row["claims"]["c1"]["citation_ids"].append("cite1"),
                       lambda row: row["claims"].update(c2={"text": "reuse", "citation_ids": ["cite1"]}),
                       lambda row: row["citations"].clear(),
                       lambda row: row["citations"].update(unused={"source_id": "x", "passage_id": "y"}),
                       lambda row: row["questions"].update(q1=" ")):
            row = output()
            mutate(row)
            variants.append(row)
        for row in variants:
            result = score([reference()], [row], [])
            self.assertEqual(result["dispositions"]["INVALID"], 1)
            self.assertEqual(result["completion_aware_recommendation_agreement"]["value"], 0)

    def test_bad_references_roles_limits_and_nonfinite_data_reject_batch(self):
        row = output()
        bad_references = [[reference(), reference()], [{**reference(), "category": "OTHER"}],
                          [{**reference(), "required_field_ids": ["x", "x"]}],
                          [{**reference(), "acceptable_recommendations": []}]]
        for expected in bad_references:
            with self.assertRaises(ValueError):
                score(expected, [row], [])
        for classes in ([], ["FAULTY", "FAULTY"], ["UNAVAILABLE"], [True], ["FAULTY"] * 101):
            with self.assertRaises(ValueError):
                score_stub_quality(data_role=DATA_ROLE, class_labels=classes, expectations=[], observations=[], annotations=[])
        with self.assertRaises(ValueError):
            score_stub_quality(data_role="GOLD", class_labels=["FAULTY"], expectations=[], observations=[], annotations=[])
        variants = [[row] * 101, [{**row, "fields": {"purchase": float("nan")}}],
                    [{**row, "fields": {"purchase": float("inf")}}],
                    [{**row, "fields": {"purchase": "x" * (2 * 1024 * 1024)}}]]
        for rows in variants:
            with self.assertRaises(ValueError):
                score([reference()], rows, [])

    def test_aggregate_budget_and_per_inventory_bound_are_enforced(self):
        rows = [output(), output("b")]
        for row in rows:
            row["fields"]["purchase"] = "x" * (1024 * 1024)
        with self.assertRaises(ValueError):
            score([reference(), reference("b")], rows, [])
        row = output()
        row["fields"] = {f"f{index}": "x" for index in range(101)}
        self.assertEqual(score([reference()], [row], [])["dispositions"]["INVALID"], 1)

    def test_inputs_unchanged_and_row_order_cannot_change_metrics(self):
        refs, rows = [reference(), reference("b")], [output(), output("b")]
        reviews = [annotation(row) for row in rows]
        before = deepcopy((refs, rows, reviews))
        result = score(refs, rows, reviews)
        self.assertEqual((refs, rows, reviews), before)
        self.assertEqual(result, score(refs, rows[::-1], reviews[::-1]))


if __name__ == "__main__":
    unittest.main()
