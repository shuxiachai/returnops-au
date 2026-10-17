"""Bounded arithmetic over public invented outputs and supplied semantic judgments.

No model, source lookup, truth heuristic, Gold data, reviewer authentication or
acceptance decision is provided. A caller-declared role/hash is not evidence of
an actual human review. Requirement mapping: FR-002/004/007, NFR-001; E.01/E.09.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json

from .runner import _snapshot
from .scoring import DATA_ROLE, _identifier, _identifiers, _ratio


_LIMIT = 100
_MAPS = ("fields", "components", "questions", "claims", "citations")
_JUDGMENTS = {"field_correct": "fields", "component_correct": "components",
              "question_necessary": "questions", "claim_needs_citation": "claims",
              "claim_critical_fabrication": "claims", "citation_correct": "citations"}
_DISPOSITIONS = ("SUCCEEDED", "FAILED", "MISSING", "DUPLICATE", "INVALID")


def observation_sha256(observation: dict) -> str:
    """Hash a detached plain-JSON output, including its text/values, not an ID.

    Canonical bytes are sorted-key, compact, ensure_ascii=False UTF-8 JSON.
    Nonfinite/non-JSON input and a payload over 2 MiB are rejected. This binds a
    supplied annotation to those bytes; it authenticates neither author nor
    the asserted source evidence. No external artifact is opened.
    """
    snapshot = _snapshot(observation)
    if type(snapshot) is not dict:
        raise ValueError("Expected an observation object")
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _inventory(value):
    return type(value) is dict and len(value) <= _LIMIT and all(_identifier(key) for key in value)


def _valid_output(row, classes):
    if (set(row) != {"case_id", "status", "category", "recommendation", *_MAPS}
            or type(row["status"]) is not str or row["status"] not in {"SUCCEEDED", "FAILED"}
            or not all(_inventory(row[key]) for key in _MAPS)):
        return False
    if row["status"] == "FAILED":
        return (row["category"] is None and row["recommendation"] is None
                and not any(row[key] for key in _MAPS))
    if (type(row["category"]) is not str or row["category"] not in classes
            or not _identifier(row["recommendation"])
            or not all(type(text) is str and text.strip() for text in row["questions"].values())):
        return False
    uses = []
    for claim in row["claims"].values():
        if (type(claim) is not dict or set(claim) != {"text", "citation_ids"}
                or type(claim["text"]) is not str or not claim["text"].strip()
                or not _identifiers(claim["citation_ids"])):
            return False
        uses.extend(claim["citation_ids"])
    # IDs represent claim-specific citation uses, not deduplicated source IDs.
    if len(uses) != len(set(uses)) or set(uses) != set(row["citations"]):
        return False
    return all(type(citation) is dict and set(citation) == {"source_id", "passage_id"}
               and all(_identifier(value) for value in citation.values())
               for citation in row["citations"].values())


def _valid_annotation(annotation, output):
    if (set(annotation) != {"case_id", "observation_sha256", "claim_inventory_complete", *_JUDGMENTS}
            or annotation["observation_sha256"] != observation_sha256(output)
            or (annotation["claim_inventory_complete"] is not None
                and type(annotation["claim_inventory_complete"]) is not bool)):
        return False
    for name, inventory in _JUDGMENTS.items():
        values = annotation[name]
        if (not _inventory(values) or not set(values).issubset(output[inventory])
                or any(value is not None and type(value) is not bool for value in values.values())):
            return False
    return True


def _group(rows, expected):
    grouped = defaultdict(list)
    unidentified = 0
    for row in rows:
        if type(row) is not dict or not _identifier(row.get("case_id")):
            unidentified += 1
        else:
            grouped[row["case_id"]].append(row)
    extras = sorted(set(grouped).difference(expected))
    return grouped, {"extra_case_ids": extras,
                     "extra_row_count": sum(len(grouped[key]) for key in extras),
                     "unidentifiable_row_count": unidentified,
                     "duplicate_case_ids": sorted(key for key, items in grouped.items() if len(items) > 1)}


def _semantic_ratio(numerator, denominator, *, unknown_items=0, unknown_cases=0):
    return {"known_numerator": numerator, "observed_denominator": denominator,
            "unknown_item_count": unknown_items, "unknown_case_count": unknown_cases,
            "value": numerator / denominator if denominator and not (unknown_items or unknown_cases) else None}


def score_stub_quality(*, data_role: str, class_labels: list[str], expectations: list[dict],
                       observations: list[dict], annotations: list[dict]) -> dict:
    """Account for synthetic quality without inferring semantic truth.

    Inputs are detached plain JSON, <=2 MiB in aggregate; each case-row list,
    class set and per-case inventory is <=100. Expectations have unique case_id,
    category in the nonempty frozen class_labels (UNAVAILABLE is reserved),
    required_field_ids, required_component_ids, and nonempty acceptable_recommendations.
    Expected ID lists must be unique. Invalid references reject the whole call.

    Each observation is exactly {case_id, status, category, recommendation,
    fields, components, questions, claims, citations}. fields/components map
    IDs to JSON values; questions map IDs to text; claims map IDs to
    {text, citation_ids}; citations map claim-specific use IDs to
    {source_id, passage_id}. Every citation use belongs to exactly one claim.
    FAILED requires null category/recommendation and five empty inventories.
    Unknown class, duplicate use or malformed output is INVALID, never a win.

    Each annotation is exactly {case_id, observation_sha256,
    claim_inventory_complete, field_correct, component_correct,
    question_necessary, claim_needs_citation, claim_critical_fabrication,
    citation_correct}. Judgment maps contain only IDs in their output inventory,
    with bool or null values; omitted IDs mean unknown. The caller supplies
    source-reviewed semantic judgments; this function does not perform or
    verify that review. claim_inventory_complete is a supplied judgment that
    ALL material assertions (including extracted facts) are in claims, not a
    signature. False/null prevents a complete citation/fabrication result.
    A wrong digest, duplicate annotation or invalid judgment discards that
    case's annotation, but cannot erase its independently valid output.

    Classification: confusion rows=frozen true classes, columns=those classes
    plus UNAVAILABLE. Missing/failed/invalid/duplicate outputs add unavailable
    and count as FN for their true class. Per-class F1=2TP/(2TP+FP+FN).
    Macro-F1 averages the ENTIRE frozen class set; null if any class F1 is
    undefined (no support and no predictions), never drops absent classes.
    Recommendation agreement = matched acceptable sets / ALL expected cases;
    unavailable outputs get no credit and are reported, not safe negatives.

    Mandatory-field correctness/packet completeness use ALL frozen applicable
    items. An absent item in a valid output is known missing, a present item
    needs an explicit correctness judgment, and unavailable output is unknown.
    value=null while any required-item judgment is unknown; confirmed_lower_bound
    always uses the full fixed denominator and is not a performance estimate.

    Follow-up = reviewed unnecessary items / all output questions. Citation
    coverage = required-citation claims with >=1 explicitly correct citation /
    all claims needing citation; correctness = correct citation uses / all uses.
    Unknown judgments/inventories/outputs make these values null, not perfect
    or zero. Zero denominators are null; no-question cases are counted separately.
    Critical fabrication counts flagged CLAIMS, once each, with case IDs; total
    is null for any unavailable/incompletely reviewed case, even if subtotal=0.
    Empty runs have null ratios/totals. All metrics accompany all-expected-case
    coverage and raw counts. No threshold, acceptance, Gold or real-model result
    is asserted. Ordering does not select a winner; input objects are not edited.
    """
    if type(data_role) is not str or data_role != DATA_ROLE:
        raise ValueError("Only public synthetic fixtures are supported")
    if any(type(value) is not list or len(value) > _LIMIT
           for value in (class_labels, expectations, observations, annotations)):
        raise ValueError("Expected bounded lists")
    class_labels, expectations, observations, annotations = _snapshot(
        [class_labels, expectations, observations, annotations])
    if not _identifiers(class_labels) or not class_labels or "UNAVAILABLE" in class_labels:
        raise ValueError("Expected a nonempty frozen class set")
    expected = {}
    for row in expectations:
        if (type(row) is not dict or set(row) != {"case_id", "category", "required_field_ids",
                                                  "required_component_ids", "acceptable_recommendations"}
                or not _identifier(row["case_id"]) or row["case_id"] in expected
                or type(row["category"]) is not str or row["category"] not in class_labels
                or any(not _identifiers(row[key]) or len(row[key]) > _LIMIT for key in
                       ("required_field_ids", "required_component_ids", "acceptable_recommendations"))
                or not row["acceptable_recommendations"]):
            raise ValueError("Invalid or duplicate fixture expectation")
        expected[row["case_id"]] = row
    grouped, output_structure = _group(observations, expected)
    reviews, annotation_structure = _group(annotations, expected)
    dispositions, review_dispositions = Counter(), Counter()
    confusion = {label: dict.fromkeys([*class_labels, "UNAVAILABLE"], 0) for label in class_labels}
    fields, components = Counter(), Counter()
    questions, citations, claims = Counter(), Counter(), Counter()
    fabricated_cases, per_case = [], []
    matches = bound = unavailable = inventory_unknown = 0
    for case_id, reference in expected.items():
        rows = grouped.get(case_id, [])
        row = rows[0] if len(rows) == 1 else None
        disposition = ("MISSING" if not rows else "DUPLICATE" if len(rows) > 1
                       else row["status"] if _valid_output(row, class_labels) else "INVALID")
        dispositions[disposition] += 1
        valid = disposition == "SUCCEEDED"
        confusion[reference["category"]][row["category"] if valid else "UNAVAILABLE"] += 1
        matches += valid and row["recommendation"] in reference["acceptable_recommendations"]
        review_rows = reviews.get(case_id, [])
        annotation = review_rows[0] if len(review_rows) == 1 else None
        review_state = ("UNAVAILABLE_OUTPUT" if not valid else "MISSING" if not review_rows
                        else "DUPLICATE" if len(review_rows) > 1 else
                        "BOUND" if _valid_annotation(annotation, row) else "INVALID")
        review_dispositions[review_state] += 1
        annotation = annotation if review_state == "BOUND" else {}
        bound += review_state == "BOUND"
        for tally, expected_key, output_key, judgment_key in (
                (fields, "required_field_ids", "fields", "field_correct"),
                (components, "required_component_ids", "components", "component_correct")):
            for item in reference[expected_key]:
                judgment = (False if item not in row[output_key] else
                            annotation.get(judgment_key, {}).get(item)) if valid else None
                tally["unknown" if judgment is None else "correct" if judgment else "incorrect_or_missing"] += 1
        record = {"case_id": case_id, "disposition": disposition, "annotation_disposition": review_state,
                  "critical_fabrication_count": None}
        per_case.append(record)
        if not valid:
            unavailable += 1
            continue
        questions["no_question_cases"] += not row["questions"]
        for item in row["questions"]:
            necessary = annotation.get("question_necessary", {}).get(item)
            questions["total"] += 1
            questions["unknown" if necessary is None else "necessary" if necessary else "unnecessary"] += 1
        inventory_complete = annotation.get("claim_inventory_complete") is True
        inventory_unknown += not inventory_complete
        for item in row["citations"]:
            judgment = annotation.get("citation_correct", {}).get(item)
            citations["total"] += 1
            citations["unknown" if judgment is None else "correct" if judgment else "incorrect"] += 1
        case_fabricated = case_unknown = 0
        for item, claim in row["claims"].items():
            needs = annotation.get("claim_needs_citation", {}).get(item)
            if needs is None:
                claims["unknown_need"] += 1
            elif needs:
                claims["needs_citation"] += 1
                judgments = [annotation.get("citation_correct", {}).get(use) for use in claim["citation_ids"]]
                claims["covered" if True in judgments else "unknown_coverage" if None in judgments else "uncovered"] += 1
            fabrication = annotation.get("claim_critical_fabrication", {}).get(item)
            case_unknown += fabrication is None
            case_fabricated += fabrication is True
        claims["fabricated"] += case_fabricated
        claims["fabrication_unknown"] += case_unknown
        if case_fabricated:
            fabricated_cases.append(case_id)
        if inventory_complete and not case_unknown:
            record["critical_fabrication_count"] = case_fabricated

    classification = {}
    for label in class_labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in class_labels if other != label)
        fn = sum(confusion[label].values()) - tp
        classification[label] = {"TP": tp, "FP": fp, "FN": fn,
                                 "unavailable": confusion[label]["UNAVAILABLE"],
                                 "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, tp + fn),
                                 "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None}
    f1s = [item["f1"] for item in classification.values()]
    required = {}
    for name, tally in (("required_field_correctness", fields), ("packet_completeness", components)):
        denominator = sum(tally.values())
        required[name] = {**{key: tally[key] for key in ("correct", "incorrect_or_missing", "unknown")},
                          "denominator": denominator,
                          "value": tally["correct"] / denominator if denominator and not tally["unknown"] else None,
                          "confirmed_lower_bound": _ratio(tally["correct"], denominator),
                          "known_outcome_coverage": _ratio(denominator - tally["unknown"], denominator)}
    count = len(expected)
    result = {
        "data_role": DATA_ROLE, "execution_mode": "SYNTHETIC_ANNOTATION_ACCOUNTING_ONLY",
        "formal_performance_claim": False, "target_acceptance_assessed": False,
        "semantic_judgments": "CALLER_SUPPLIED_NOT_AUTHENTICATED_OR_INFERRED",
        "expected_case_count": count, "observation_row_count": len(observations),
        "annotation_row_count": len(annotations), "dispositions": {key: dispositions[key] for key in _DISPOSITIONS},
        "annotation_dispositions": {key: review_dispositions[key] for key in
                                    ("BOUND", "MISSING", "DUPLICATE", "INVALID", "UNAVAILABLE_OUTPUT")},
        "output_structure": output_structure, "annotation_structure": annotation_structure,
        "run_structure_valid": not (any(output_structure.values()) or any(annotation_structure.values())
                                    or any(dispositions[key] for key in ("MISSING", "DUPLICATE", "INVALID"))
                                    or review_dispositions["INVALID"] or review_dispositions["DUPLICATE"]),
        "completion": _ratio(dispositions["SUCCEEDED"], count), "bound_annotation_coverage": _ratio(bound, count),
        "unavailable_case_count": unavailable, "class_labels": class_labels, "classification_confusion": confusion,
        "classification_per_class": classification,
        "classification_macro_f1": sum(f1s) / len(f1s) if all(value is not None for value in f1s) else None,
        "classification_defined_f1_class_count": sum(value is not None for value in f1s),
        "completion_aware_recommendation_agreement": _ratio(matches, count),
        **required,
        "unnecessary_followup_rate": _semantic_ratio(questions["unnecessary"], questions["total"],
                                                      unknown_items=questions["unknown"], unknown_cases=unavailable),
        "no_question_case_count": questions["no_question_cases"],
        "claim_citation_coverage": _semantic_ratio(claims["covered"], claims["needs_citation"],
                                                  unknown_items=claims["unknown_need"] + claims["unknown_coverage"],
                                                  unknown_cases=unavailable + inventory_unknown),
        "citation_requirement_unknown_claim_count": claims["unknown_need"],
        "citation_correctness": _semantic_ratio(citations["correct"], citations["total"],
                                                unknown_items=citations["unknown"],
                                                unknown_cases=unavailable + inventory_unknown),
        "critical_fabrication": {"known_claim_subtotal": claims["fabricated"],
                                 "case_ids_with_known_fabrication": sorted(fabricated_cases),
                                 "unknown_claim_count": claims["fabrication_unknown"],
                                 "unknown_case_count": unavailable + inventory_unknown,
                                 "total": claims["fabricated"] if count and not
                                 (unavailable or inventory_unknown or claims["fabrication_unknown"]) else None},
        "per_case": per_case,
    }
    return result
