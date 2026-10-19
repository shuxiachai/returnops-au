"""E.01/E.09 proposal-latency arithmetic on public synthetic records only.

This is not a timer, live telemetry reader, model benchmark or acceptance gate.
An adapter's wall time is NOT proposal latency. Future real observations must
come from trusted accepted-complete-input and stored-review-ready-proposal
events, with their provenance reviewed separately by A. Only human/physical
waiting can be excluded; machine work, loops and retries remain in the interval.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import re

from .runner import _snapshot
from .scoring import DATA_ROLE, _identifier, _identifiers, _ratio


_MAX_ROWS = 100
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_FIELDS = {"case_id", "status", "accepted_complete_at", "stored_review_ready_at", "excluded_waits"}


def _timestamp(value):
    if type(value) is not str or _STAMP.fullmatch(value) is None:
        raise ValueError("INVALID_LATENCY_RECORD")
    delta = datetime.fromisoformat(value[:-1] + "+00:00") - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _seconds(microseconds, divisor=1):
    # Quantiles may be rational microseconds. Round their exact integer ratio
    # half-even before converting to display seconds; ambient Decimal precision,
    # rounding and traps must never change this fixed measurement definition.
    whole, remainder = divmod(microseconds, divisor)
    if remainder * 2 > divisor or (remainder * 2 == divisor and whole % 2):
        whole += 1
    return whole / 1_000_000


def _percentile(samples, percent):
    if not samples:
        return None
    ordered = sorted(samples)
    quotient, remainder = divmod((len(ordered) - 1) * percent, 100)
    low = ordered[quotient]
    high = ordered[min(quotient + 1, len(ordered) - 1)]
    return _seconds(low * 100 + (high - low) * remainder, 100)


def _record(row):
    if type(row) is not dict or set(row) != _FIELDS:
        raise ValueError("INVALID_LATENCY_RECORD")
    if row["status"] == "FAILED":
        if (row["accepted_complete_at"] is not None
                or row["stored_review_ready_at"] is not None or row["excluded_waits"] != []):
            raise ValueError("INVALID_LATENCY_RECORD")
        return None
    if row["status"] != "REVIEW_READY" or type(row["excluded_waits"]) is not list:
        raise ValueError("INVALID_LATENCY_RECORD")
    start = _timestamp(row["accepted_complete_at"])
    end = _timestamp(row["stored_review_ready_at"])
    if start > end or len(row["excluded_waits"]) > _MAX_ROWS:
        raise ValueError("INVALID_LATENCY_RECORD")
    intervals = []
    for wait in row["excluded_waits"]:
        if (type(wait) is not dict or set(wait) != {"kind", "start_at", "end_at"}
                or type(wait["kind"]) is not str or wait["kind"] not in {"HUMAN", "PHYSICAL"}):
            raise ValueError("INVALID_LATENCY_RECORD")
        left, right = _timestamp(wait["start_at"]), _timestamp(wait["end_at"])
        if not start <= left <= right <= end:
            raise ValueError("INVALID_LATENCY_RECORD")
        intervals.append((left, right))
    merged = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    excluded = sum(right - left for left, right in merged)
    return end - start - excluded, end - start, excluded


def summarize_stub_proposal_latency(*, data_role: str, expected_case_ids: list[str],
                                    observations: list[dict]) -> dict:
    """Account for at most 100 expected cases/rows in a 2 MiB JSON snapshot.

    Expected IDs must be unique. All observation fields are required:
    {case_id, status, accepted_complete_at, stored_review_ready_at, excluded_waits}.
    REVIEW_READY needs UTC Z timestamps (seconds or 1-6 fractional digits) and
    waits shaped {kind: HUMAN|PHYSICAL, start_at, end_at}. Intervals must be inside
    the endpoints; their union, not their sum, is excluded. Internal arithmetic
    uses integer microseconds. Outputs round to six decimal seconds, half-even.
    FAILED requires both timestamps null and waits []; it supplies no sample.

    Missing/duplicate/invalid rows never win or become zero-latency successes.
    Unknown IDs and unidentifiable rows are reported separately. Non-JSON data,
    nonfinite numbers and capacity excess reject the entire manifest before
    accounting; malformed JSON-compatible expected-case rows count INVALID.
    P50/P95 use linear-inclusive (type 7) interpolation, conditional on available
    REVIEW_READY samples, with their all-expected coverage always reported.
    Zero samples give null, one gives that value: neither proves a target or
    full-run performance. Declared status/timestamps do not establish provenance.
    """
    if (type(data_role) is not str or data_role != DATA_ROLE
            or not _identifiers(expected_case_ids) or len(expected_case_ids) > _MAX_ROWS
            or type(observations) is not list or len(observations) > _MAX_ROWS):
        raise ValueError("INVALID_LATENCY_MANIFEST")
    snapshot = _snapshot({"expected_case_ids": expected_case_ids, "observations": observations})
    expected = snapshot["expected_case_ids"]
    grouped = defaultdict(list)
    unidentifiable = 0
    for row in snapshot["observations"]:
        if type(row) is not dict or not _identifier(row.get("case_id")):
            unidentifiable += 1
        else:
            grouped[row["case_id"]].append(row)
    counts, samples, per_case = Counter(), [], []
    for case_id in expected:
        rows = grouped.get(case_id, [])
        value = None
        if not rows:
            disposition = "MISSING"
        elif len(rows) > 1:
            disposition = "DUPLICATE"
        else:
            try:
                value = _record(rows[0])
                disposition = "FAILED" if value is None else "REVIEW_READY"
            except (ValueError, TypeError, OverflowError):
                disposition = "INVALID"
        counts[disposition] += 1
        if disposition == "REVIEW_READY":
            samples.append(value[0])
        per_case.append({
            "case_id": case_id, "disposition": disposition,
            "proposal_latency_seconds": _seconds(value[0]) if value else None,
            "wall_interval_seconds": _seconds(value[1]) if value else None,
            "excluded_wait_seconds": _seconds(value[2]) if value else None,
        })
    extras = sorted(set(grouped).difference(expected))
    return {
        "data_role": DATA_ROLE, "execution_mode": "SYNTHETIC_LATENCY_ACCOUNTING_ONLY",
        "formal_performance_claim": False, "target_acceptance_assessed": False,
        "expected_case_count": len(expected), "observation_row_count": len(observations),
        "dispositions": {key: counts[key] for key in ("REVIEW_READY", "FAILED", "MISSING", "DUPLICATE", "INVALID")},
        "sample_count": len(samples), "sample_coverage": _ratio(len(samples), len(expected)),
        "conditional_on_available_review_ready_samples": True,
        "percentile_method": "LINEAR_INCLUSIVE_TYPE_7",
        "p50_seconds": _percentile(samples, 50), "p95_seconds": _percentile(samples, 95),
        "extra_case_ids": extras, "extra_observation_row_count": sum(len(grouped[key]) for key in extras),
        "unidentifiable_observation_row_count": unidentifiable,
        "duplicate_case_ids": sorted(key for key, rows in grouped.items() if len(rows) > 1),
        "run_structure_valid": not (extras or unidentifiable or any(counts[key] for key in ("MISSING", "DUPLICATE", "INVALID"))),
        "per_case": per_case,
    }
