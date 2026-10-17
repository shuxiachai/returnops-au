"""Local student active-time accounting, not evidence of participation or blindness.

Trace: docs/00 section 12.2; E.02/E.03/E.04/E.08. This module never accepts
answers or Gold labels. Preparing this tool does not complete those work items.
The CLI imports one explicit local file and exclusively creates one private
report; it discovers no files, services, credentials or network resources.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import os
import re
import stat
import sys

from .latency import _seconds, _timestamp
from .runner import _snapshot
from .scoring import _identifier, _identifiers, _ratio


SYNTHETIC_ROLE = "PUBLIC_SYNTHETIC_HUMAN_TIMING_FIXTURES_NOT_BASELINE"
PRIVATE_ROLE = "PRIVATE_STUDENT_TIMING_RECORDS"
_OPERATORS = ("A", "B")
_PAUSES = {"CUSTOMER_WAIT", "PROVIDER_WAIT", "FOUNDER_WAIT", "PHYSICAL_WAIT"}
_DISPOSITIONS = ("COMPLETED", "FAILED", "MISSING", "DUPLICATE", "INVALID")
_MAX_BYTES = 2 * 1024 * 1024
_MAX_CASES = 100
_MAX_RECORDS = 400
_MAX_DURATION_US = 86_400 * 1_000_000
_HASH = re.compile(r"[a-f0-9]{64}")


def _require(condition):
    if not condition:
        raise ValueError("INVALID_HUMAN_TIMING_MANIFEST")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _pin(value):
    return (type(value) is dict and set(value) == {"version", "sha256"}
            and _identifier(value["version"]) and type(value["sha256"]) is str
            and _HASH.fullmatch(value["sha256"]) is not None)


def _record(row, order):
    if (set(row) != {"operator", "case_id", "position", "status", "started_at", "ended_at", "pauses"}
            or type(row["position"]) is not int or not 1 <= row["position"] <= len(order)
            or type(row["status"]) is not str or row["status"] not in {"COMPLETED", "FAILED"}
            or type(row["pauses"]) is not list or len(row["pauses"]) > _MAX_CASES
            or (row["case_id"] in order and order[row["position"] - 1] != row["case_id"])):
        raise ValueError("INVALID_TIMING_RECORD")
    if row["status"] == "FAILED" and row["started_at"] is None and row["ended_at"] is None:
        if row["pauses"]:
            raise ValueError("INVALID_TIMING_RECORD")
        return None
    start, end = _timestamp(row["started_at"]), _timestamp(row["ended_at"])
    if not 0 <= end - start <= _MAX_DURATION_US:
        raise ValueError("INVALID_TIMING_RECORD")
    intervals = []
    for pause in row["pauses"]:
        if (type(pause) is not dict or set(pause) != {"kind", "start_at", "end_at", "reason"}
                or type(pause["kind"]) is not str or pause["kind"] not in _PAUSES
                or type(pause["reason"]) is not str or not pause["reason"].strip()
                or len(pause["reason"]) > 500):
            raise ValueError("INVALID_TIMING_RECORD")
        left, right = _timestamp(pause["start_at"]), _timestamp(pause["end_at"])
        if not start <= left <= right <= end:
            raise ValueError("INVALID_TIMING_RECORD")
        intervals.append((left, right))
    merged = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    excluded = sum(right - left for left, right in merged)
    return {"start": start, "end": end, "active": end - start - excluded,
            "wall": end - start, "excluded": excluded}


def _statistics(samples, expected_count):
    ordered = sorted(samples)

    def quantile_numerator(percent):
        low, remainder = divmod((len(ordered) - 1) * percent, 100)
        return ordered[low] * 100 + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * remainder

    q1 = quantile_numerator(25) if ordered else None
    q3 = quantile_numerator(75) if ordered else None
    return {"sample_count": len(samples), "expected_case_count": expected_count,
            "sample_coverage": _ratio(len(samples), expected_count),
            "conditional_on_valid_completed_records": True,
            "quartile_method": "LINEAR_INCLUSIVE_TYPE_7_MICROSECOND_HALF_EVEN",
            "median_seconds": _seconds(quantile_numerator(50), 100) if ordered else None,
            "q1_seconds": _seconds(q1, 100) if ordered else None,
            "q3_seconds": _seconds(q3, 100) if ordered else None,
            "iqr_seconds": _seconds(q3 - q1, 100) if ordered else None}


def summarize_human_timing(manifest: dict) -> dict:
    """Validate a detached bounded JSON record set and derive active-time statistics.

    Exact manifest keys: data_role, input_pin, corpus_pin, expected_case_ids,
    orders, records. The role is SYNTHETIC_ROLE or PRIVATE_ROLE. Each pin is
    {version, sha256}; these are supplied references, not verified file bytes.
    expected_case_ids contains 2..100 unique IDs. orders is exactly {A: [...],
    B: [...]}, two DISTINCT permutations of those IDs; one case cannot satisfy
    this constraint. The tool checks consistency, not prior freezing/randomness.

    Each record is {operator, case_id, position, status, started_at, ended_at,
    pauses}. operator is A/B; position is the 1-based frozen order position;
    status is COMPLETED/FAILED. Times are UTC Z with seconds or 1..6 fractional
    digits. No supplied duration is accepted. A timed record spans at most 24h
    (technical import limit, not a course rule). Each pause is exactly {kind,
    start_at, end_at, reason}; only CUSTOMER_WAIT, PROVIDER_WAIT, FOUNDER_WAIT,
    PHYSICAL_WAIT are excludable. Reasons are nonblank <=500 characters and are
    never copied into the report. Pauses must lie inside the case interval.
    Their union is subtracted once; reading, checking, thinking and writing
    remain active work. False pause labels cannot be detected by this arithmetic.
    Break rules still need E.01 agreement; there is no generic HUMAN/BREAK kind.

    FAILED may have a measured partial interval, or both times null with no
    pauses. Failed partial time is retained but never enters completed-sample
    quartiles. Missing/duplicate/invalid cases remain in all expected operator-
    case denominators (pooled denominator=2*N), never zero samples. Extra and
    unidentifiable rows are reported. Valid timed extra/duplicate rows also
    participate in same-operator overlap checks so they cannot hide a conflict.
    Overlap or reversal of frozen chronological order invalidates BOTH involved
    expected cases. A and B may overlap each other. Touching endpoints are valid.

    Each operator and the pool get median/Q1/Q3/IQR, conditional sample counts
    and coverage. Type-7 interpolation uses integer microseconds; IQR is Q3-Q1
    before half-even rounding to display microseconds. Empty samples give null;
    a single sample gives itself with zero IQR, not a full-study result.

    Limits: 2 MiB whole manifest, <=400 rows, <=100 pauses per row. Private role
    permits future authorised imports, not certification of participation,
    blind conditions, sealed labels, actual answers, omissions, source approval,
    E.08 acceptance or merchant performance. Answers/Gold are outside this schema.
    Only synthetic examples should be committed; private files/reports stay in
    approved private storage outside the public checkout. Inputs are unchanged.
    """
    manifest = _snapshot(manifest)
    _require(type(manifest) is dict and set(manifest) == {
        "data_role", "input_pin", "corpus_pin", "expected_case_ids", "orders", "records"})
    _require(type(manifest["data_role"]) is str and manifest["data_role"] in {SYNTHETIC_ROLE, PRIVATE_ROLE})
    _require(_pin(manifest["input_pin"]) and _pin(manifest["corpus_pin"]))
    expected, orders, records = manifest["expected_case_ids"], manifest["orders"], manifest["records"]
    _require(_identifiers(expected) and 2 <= len(expected) <= _MAX_CASES)
    _require(type(orders) is dict and set(orders) == set(_OPERATORS))
    _require(all(_identifiers(orders[operator]) and set(orders[operator]) == set(expected) for operator in _OPERATORS))
    _require(orders["A"] != orders["B"])
    _require(type(records) is list and len(records) <= _MAX_RECORDS)
    grouped, parsed, unidentifiable = defaultdict(list), {}, 0
    for index, row in enumerate(records):
        if (type(row) is not dict or type(row.get("operator")) is not str or row["operator"] not in _OPERATORS
                or not _identifier(row.get("case_id"))):
            unidentifiable += 1
            continue
        key = (row["operator"], row["case_id"])
        grouped[key].append(index)
        try:
            parsed[index] = _record(row, orders[row["operator"]])
        except (ValueError, TypeError, OverflowError):
            pass
    conflicts = defaultdict(set)
    timed = [(index, value) for index, value in parsed.items() if value is not None]
    for position, (left_index, left) in enumerate(timed):
        a = records[left_index]
        for right_index, right in timed[position + 1:]:
            b = records[right_index]
            if a["operator"] != b["operator"] or a["case_id"] == b["case_id"]:
                continue
            kind = None
            if max(left["start"], right["start"]) < min(left["end"], right["end"]):
                kind = "CROSS_CASE_OVERLAP"
            elif a["case_id"] in expected and b["case_id"] in expected:
                earlier, later = (left, right) if a["position"] < b["position"] else (right, left)
                if earlier["end"] > later["start"]:
                    kind = "FROZEN_ORDER_VIOLATION"
            if kind:
                conflicts[(a["operator"], a["case_id"])].add(kind)
                conflicts[(b["operator"], b["case_id"])].add(kind)
    operators, pooled = {}, []
    for operator in _OPERATORS:
        counts, samples, per_case = Counter(), [], []
        for position, case_id in enumerate(orders[operator], start=1):
            key = (operator, case_id)
            indexes = grouped.get(key, [])
            index = indexes[0] if len(indexes) == 1 else None
            disposition = ("MISSING" if not indexes else "DUPLICATE" if len(indexes) > 1
                           else "INVALID" if index not in parsed or conflicts[key] else records[index]["status"])
            value = parsed.get(index) if disposition in {"COMPLETED", "FAILED"} else None
            counts[disposition] += 1
            if disposition == "COMPLETED":
                samples.append(value["active"])
            per_case.append({"case_id": case_id, "position": position, "disposition": disposition,
                             "conflicts": sorted(conflicts[key]),
                             "active_seconds": _seconds(value["active"]) if value else None,
                             "wall_seconds": _seconds(value["wall"]) if value else None,
                             "excluded_pause_seconds": _seconds(value["excluded"]) if value else None,
                             "included_in_completed_statistics": disposition == "COMPLETED"})
        operators[operator] = {**_statistics(samples, len(expected)),
                               "order_sha256": sha256(_canonical(orders[operator])).hexdigest(),
                               "dispositions": {key: counts[key] for key in _DISPOSITIONS}, "per_case": per_case}
        pooled.extend(samples)
    extras = [{"operator": operator, "case_id": case_id, "row_count": len(indexes)}
              for (operator, case_id), indexes in sorted(grouped.items()) if case_id not in expected]
    duplicates = [{"operator": operator, "case_id": case_id}
                  for (operator, case_id), indexes in sorted(grouped.items()) if len(indexes) > 1]
    return {"data_role": manifest["data_role"], "execution_mode": "LOCAL_TIMING_RECORD_ACCOUNTING_ONLY",
            "human_participation_verified": False, "blindness_verified": False, "sealing_verified": False,
            "target_acceptance_assessed": False, "formal_performance_claim": False,
            "pins_are_declared_not_authenticated": True, "input_pin": manifest["input_pin"],
            "corpus_pin": manifest["corpus_pin"], "manifest_sha256": sha256(_canonical(manifest)).hexdigest(),
            "expected_cases_per_operator": len(expected), "record_row_count": len(records),
            "operators": operators, "pooled": _statistics(pooled, 2 * len(expected)),
            "extra_records": extras, "unidentifiable_row_count": unidentifiable,
            "duplicate_operator_case_ids": duplicates,
            "run_structure_valid": not (extras or duplicates or unidentifiable or any(
                operators[operator]["dispositions"][key] for operator in _OPERATORS for key in ("INVALID", "MISSING")))}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("INVALID_HUMAN_TIMING_JSON")


def _read_input(path):
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    # Final-component symlinks and nonregular inputs (including FIFOs) fail closed.
    if stat.S_ISLNK(os.lstat(path).st_mode):
        raise ValueError("INVALID_HUMAN_TIMING_INPUT")
    with os.fdopen(os.open(path, flags), "rb") as source:
        before = os.fstat(source.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= _MAX_BYTES)
        raw = source.read(_MAX_BYTES + 1)
        after = os.fstat(source.fileno())
        _require(len(raw) <= _MAX_BYTES and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns))
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    return value, sha256(raw).hexdigest()


def _write_output(path, report):
    raw = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    owned = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as destination:
            os.fchmod(destination.fileno(), 0o600)
            destination.write(raw)
            destination.flush()
            os.fsync(destination.fileno())
    except (OSError, ValueError):
        # Remove only our own incomplete file, never a concurrent replacement.
        try:
            current = os.lstat(path)
            if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                os.unlink(path)
        except OSError:
            pass
        raise


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "HUMAN_TIMING_ARGUMENT_ERROR\n")


def main(argv=None):
    parser = _Parser(description="Import timing records without answers; create a new private JSON report.")
    parser.add_argument("--input", required=True, help="explicit regular UTF-8 JSON file")
    parser.add_argument("--output", required=True, help="new report path in approved private storage")
    args = parser.parse_args(argv)
    try:
        manifest, digest = _read_input(args.input)
        report = summarize_human_timing(manifest)
        report["imported_file_sha256"] = digest
        _write_output(args.output, report)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        print("HUMAN_TIMING_IMPORT_FAILED", file=sys.stderr)
        return 2
    print("Human timing accounting report created; participation/blindness/acceptance not verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
