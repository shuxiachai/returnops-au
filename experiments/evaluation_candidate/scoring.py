"""Pure accounting for public synthetic scorer fixtures, never Gold evaluation.

This module invokes no adapter, model, network, database or operation. The B1/B4
names describe explicitly declared stub configurations, not implemented agents.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation


DATA_ROLE = "PUBLIC_SYNTHETIC_SCORER_FIXTURES_NOT_GOLD"
OUTCOMES = frozenset({"PASS", "PASS_WITH_WARNING", "REVISE", "NEEDS_INFORMATION", "ESCALATE"})
CONFIGURATIONS = frozenset({"B1_OFFLINE_STUB", "B4_OFFLINE_STUB"})


def _identifier(value):
    return type(value) is str and 1 <= len(value) <= 80 and value.strip() == value


def _identifiers(values):
    return (type(values) is list and all(_identifier(v) for v in values)
            and len(values) == len(set(values)))


def _ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _cost(value):
    if value is None:
        return None
    if type(value) is not str or len(value) > 40:
        raise ValueError("Cost must be an explicit decimal string or null")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid cost") from exc
    if (not amount.is_finite() or amount < 0 or amount > Decimal("1000000000")
            or amount.as_tuple().exponent < -12):
        raise ValueError("Invalid cost")
    return amount


def _observation(row, configuration):
    allowed = {"case_id", "status", "risk_outcome", "present_field_ids",
               "retrieved_passage_ids", "input_tokens", "output_tokens", "estimated_cost"}
    if set(row) != allowed or row["status"] not in {"SUCCEEDED", "FAILED"}:
        raise ValueError("Invalid observation shape")
    if not _identifiers(row["present_field_ids"]) or not _identifiers(row["retrieved_passage_ids"]):
        raise ValueError("Invalid observation identifiers")
    for key in ("input_tokens", "output_tokens"):
        value = row[key]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid token count")
    cost = _cost(row["estimated_cost"])
    if configuration == "B1_OFFLINE_STUB" and row["retrieved_passage_ids"]:
        raise ValueError("B1 cannot use retrieval")
    if row["status"] == "FAILED":
        if row["risk_outcome"] is not None or row["present_field_ids"] or row["retrieved_passage_ids"]:
            raise ValueError("Failure cannot also supply a scored decision")
    elif type(row["risk_outcome"]) is not str or row["risk_outcome"] not in OUTCOMES:
        raise ValueError("Invalid risk outcome")
    return cost


def score_stub_run(*, configuration: str, data_role: str,
                   expectations: list[dict], observations: list[dict]) -> dict:
    """Count synthetic decisions against separately supplied fixture expectations.

    Invalid expectation sets raise before scoring. Missing/duplicate/invalid
    observations remain denominator failures; no duplicate wins by list order.
    Every expected case has exactly one accounting disposition. Extra and
    unidentifiable observation rows are separately reported, never scored.
    """
    if (type(configuration) is not str or configuration not in CONFIGURATIONS
            or data_role != DATA_ROLE):
        raise ValueError("Only explicitly synthetic offline stub configurations are supported")
    if type(expectations) is not list or type(observations) is not list:
        raise ValueError("Expected lists")
    expected = {}
    for row in expectations:
        if (type(row) is not dict
                or set(row) != {"case_id", "escalation_expected", "acceptable_outcomes", "required_field_ids"}
                or not _identifier(row["case_id"])
                or row["case_id"] in expected
                or type(row["escalation_expected"]) is not bool
                or not _identifiers(row["required_field_ids"])
                or not _identifiers(row["acceptable_outcomes"])
                or not row["acceptable_outcomes"]
                or not set(row["acceptable_outcomes"]).issubset(OUTCOMES)
                or (row["escalation_expected"] and row["acceptable_outcomes"] != ["ESCALATE"])
                or (not row["escalation_expected"] and "ESCALATE" in row["acceptable_outcomes"])):
            raise ValueError("Invalid, inconsistent or duplicate fixture expectation")
        expected[row["case_id"]] = row

    grouped = defaultdict(list)
    unidentifiable = 0
    for row in observations:
        if type(row) is not dict or not _identifier(row.get("case_id")):
            unidentifiable += 1
        else:
            grouped[row["case_id"]].append(row)

    dispositions = Counter()
    confusion = Counter({key: 0 for key in ("TP", "FP", "TN", "FN", "UNSCORED_POSITIVE", "UNSCORED_NEGATIVE")})
    per_case = []
    correct = covered = 0
    telemetry = []
    for case_id, reference in expected.items():
        rows = grouped.get(case_id, [])
        row = rows[0] if len(rows) == 1 else None
        cost = None
        if not rows:
            disposition = "MISSING"
        elif len(rows) > 1:
            disposition = "DUPLICATE"
        else:
            try:
                cost = _observation(row, configuration)
                disposition = row["status"]
            except (ValueError, TypeError):
                disposition = "INVALID"
        dispositions[disposition] += 1
        if disposition in {"SUCCEEDED", "FAILED"}:
            telemetry.append((row["input_tokens"], row["output_tokens"], cost))
        else:
            telemetry.append((None, None, None))
        if disposition != "SUCCEEDED":
            confusion["UNSCORED_POSITIVE" if reference["escalation_expected"] else "UNSCORED_NEGATIVE"] += 1
            per_case.append({"case_id": case_id, "disposition": disposition, "outcome_matches": False})
            continue
        positive = row["risk_outcome"] == "ESCALATE"
        confusion[("TP" if positive else "FN") if reference["escalation_expected"] else ("FP" if positive else "TN")] += 1
        matches = row["risk_outcome"] in reference["acceptable_outcomes"]
        correct += matches
        covered += len(set(reference["required_field_ids"]).intersection(row["present_field_ids"]))
        per_case.append({"case_id": case_id, "disposition": disposition, "outcome_matches": matches})

    usage = {}
    for index, key in enumerate(("input_tokens", "output_tokens", "estimated_cost")):
        values = [item[index] for item in telemetry]
        known = [value for value in values if value is not None]
        total = sum(known, Decimal("0") if index == 2 else 0)
        # An empty run is not evidence of zero consumption.
        complete = bool(values) and len(known) == len(values)
        usage[key] = {
            "known_case_count": len(known), "unknown_case_count": len(values) - len(known),
            "known_subtotal": str(total) if index == 2 else total,
            "total": (str(total) if index == 2 else total) if complete else None,
        }

    positives = sum(row["escalation_expected"] for row in expectations)
    count = len(expected)
    extras = sorted(set(grouped).difference(expected))
    return {
        "data_role": DATA_ROLE, "configuration": configuration,
        "execution_mode": "STUB_ACCOUNTING_ONLY", "formal_performance_claim": False,
        "permissions": {"network_calls": False, "operation_authority": False,
                        "retrieval_declared": configuration == "B4_OFFLINE_STUB",
                        "independent_review_declared": configuration == "B4_OFFLINE_STUB"},
        "expected_case_count": count, "observation_row_count": len(observations),
        "dispositions": {key: dispositions[key] for key in ("SUCCEEDED", "FAILED", "MISSING", "DUPLICATE", "INVALID")},
        "extra_case_ids": extras,
        "extra_observation_row_count": sum(len(grouped[key]) for key in extras),
        "unidentifiable_observation_row_count": unidentifiable,
        "duplicate_case_ids": sorted(key for key, rows in grouped.items() if len(rows) > 1),
        "run_structure_valid": not (extras or unidentifiable or any(dispositions[key] for key in ("MISSING", "DUPLICATE", "INVALID"))),
        "completion": _ratio(dispositions["SUCCEEDED"], count),
        "acceptable_outcome_agreement": _ratio(correct, count),
        "escalation_confusion": dict(confusion),
        "completion_aware_escalation_recall": _ratio(confusion["TP"], positives),
        "completion_aware_specificity": _ratio(confusion["TN"], count - positives),
        "required_field_id_coverage": _ratio(covered, sum(len(row["required_field_ids"]) for row in expectations)),
        "usage_on_expected_cases": usage, "per_case": per_case,
    }
