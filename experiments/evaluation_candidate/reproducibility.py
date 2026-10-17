"""E.09 paired-manifest rehearsal, for public synthetic fixtures only.

Validate supplied bytes and declarations, never execute/read a provider, file,
URL, credential, environment variable or Gold label. Hashes establish integrity
consistency, NOT genuine execution, a blind protocol, source approval, permission
isolation or acceptance. Even a self-consistent fabricated run passes integrity
checks. No hidden-label detector or performance claim is provided.

Each B1/B4 run has configuration, cases, dataset, underlying_model, execution,
architecture, source_commit, artifacts and results. Cases use the runner's
{case_id, input} shape in the SAME order. Dataset is {version, sha256}, hashing
canonical_stub_json_bytes(cases). The five artifacts (corpus, prompts,
configuration, scorer, environment) each have {version, sha256, content: bytes}.
Configuration content is canonical JSON of the run's configuration,
underlying_model, execution and architecture. Other artifact bytes are opaque,
public synthetic material; their semantic meaning requires separate review.

Result entries are {case_id, disposition, error_code, raw_output, raw_output_sha256}.
raw_output is bytes of a retained structured observation, not a claim to contain
the original provider response. Invalid/unavailable responses need not be kept:
an explicit null digest records their absence. Omitted cases count MISSING.
The returned report contains pins/digests/counts, never raw inputs or outputs.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import re

from .runner import _snapshot
from .scoring import DATA_ROLE, _identifier, _observation


_MAX_CASES = 100  # Technical fixture bound, not an expansion of 30-case Gold.
_MAX_BYTES = 2 * 1024 * 1024
_PAIR_BYTES = 4 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{64}")
_COMMIT = re.compile(r"[a-f0-9]{40}")
_ARTIFACTS = {"corpus", "prompts", "configuration", "scorer", "environment"}
_RUN_FIELDS = {"configuration", "cases", "dataset", "underlying_model", "execution",
               "architecture", "source_commit", "artifacts", "results"}
_DISPOSITIONS = ("SUCCEEDED", "FAILED", "INVALID", "MISSING")


class ReproducibilityError(ValueError):
    """Sanitised manifest error; contains no supplied content or exception."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code="INVALID_REPRODUCIBILITY_MANIFEST"):
    if not condition:
        raise ReproducibilityError(code)


def _shape(value, keys):
    _require(type(value) is dict and set(value) == set(keys))


def canonical_stub_json_bytes(value):
    """Bounded plain JSON: sorted keys, compact UTF-8, finite numbers only.

    This is the runner's Python JSON convention, not RFC 8785. List order and
    numeric representations such as 1 versus 1.0 remain significant.
    """
    return json.dumps(_snapshot(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(raw):
    return sha256(raw).hexdigest()


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _consume(budget, size):
    budget[0] += size
    _require(budget[0] <= _PAIR_BYTES, "EVIDENCE_TOO_LARGE")


def _pin(value):
    _shape(value, {"version", "sha256"})
    _require(_identifier(value["version"]) and _hash(value["sha256"]))


def _model(value):
    _shape(value, {"provider_id", "model_id", "revision", "parameters"})
    _require(all(_identifier(value[key]) for key in ("provider_id", "model_id", "revision")))
    params = value["parameters"]
    _shape(params, {"temperature", "top_p", "seed", "max_output_tokens"})
    _require(type(params["temperature"]) in (int, float) and 0 <= params["temperature"] <= 2)
    _require(type(params["top_p"]) in (int, float) and 0 < params["top_p"] <= 1)
    _require(params["seed"] is None or (type(params["seed"]) is int and 0 <= params["seed"] < 2**32))
    _require(type(params["max_output_tokens"]) is int and 1 <= params["max_output_tokens"] <= 2**20)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("nonfinite JSON")


def _raw_disposition(raw, case_id, configuration):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json,
                           parse_constant=_invalid_constant)
        value = _snapshot(value)
        if type(value) is not dict or value.get("case_id") != case_id:
            return "INVALID"
        _observation(value, configuration)
        return value["status"]
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return "INVALID"


def _results(rows, case_ids, configuration, budget):
    _require(type(rows) is list and len(rows) <= _MAX_CASES)
    by_id = {}
    for row in rows:
        _shape(row, {"case_id", "disposition", "error_code", "raw_output", "raw_output_sha256"})
        metadata = _snapshot({key: value for key, value in row.items() if key != "raw_output"})
        _consume(budget, len(canonical_stub_json_bytes(metadata)))
        case_id, disposition = metadata["case_id"], metadata["disposition"]
        _require(_identifier(case_id) and case_id in case_ids, "UNKNOWN_RESULT_CASE")
        _require(case_id not in by_id, "DUPLICATE_RESULT_CASE")
        _require(type(disposition) is str and disposition in _DISPOSITIONS)
        raw, digest, error = row["raw_output"], metadata["raw_output_sha256"], metadata["error_code"]
        _require(error is None or type(error) is str)
        observed = None
        if raw is not None:
            _require(type(raw) is bytes and len(raw) <= _MAX_BYTES, "INVALID_RAW_OUTPUT")
            _consume(budget, len(raw))
            _require(_hash(digest) and _digest(raw) == digest, "RAW_OUTPUT_HASH_MISMATCH")
            observed = _raw_disposition(raw, case_id, configuration)
        else:
            _require(digest is None, "RAW_OUTPUT_HASH_WITHOUT_BYTES")
        if disposition == "SUCCEEDED":
            _require(observed == "SUCCEEDED" and error is None, "RESULT_DISPOSITION_MISMATCH")
        elif disposition == "FAILED":
            _require((observed == "FAILED" and error in {None, "ADAPTER_TIMEOUT", "ADAPTER_FAILURE"})
                     or (raw is None and error in {"ADAPTER_TIMEOUT", "ADAPTER_FAILURE"}),
                     "RESULT_DISPOSITION_MISMATCH")
        elif disposition == "INVALID":
            _require(error == "INVALID_ADAPTER_OUTPUT" and (raw is None or observed == "INVALID"),
                     "RESULT_DISPOSITION_MISMATCH")
        else:
            _require(raw is None and error is None, "RESULT_DISPOSITION_MISMATCH")
        by_id[case_id] = {**metadata, "raw_output_bytes": len(raw) if raw is not None else None}
    evidence = []
    for case_id in case_ids:
        evidence.append(by_id.get(case_id, {
            "case_id": case_id, "disposition": "MISSING", "error_code": None,
            "raw_output_sha256": None, "raw_output_bytes": None,
        }))
    counts = Counter(row["disposition"] for row in evidence)
    return {"expected_case_count": len(case_ids), "provided_result_count": len(rows),
            "dispositions": {key: counts[key] for key in _DISPOSITIONS},
            "all_cases_succeeded": counts["SUCCEEDED"] == len(case_ids),
            "unavailable_raw_output_case_ids": [r["case_id"] for r in evidence if r["raw_output_sha256"] is None],
            "case_evidence": evidence}


def _run(run, configuration, budget):
    _shape(run, _RUN_FIELDS)
    metadata = _snapshot({key: value for key, value in run.items() if key not in {"artifacts", "results"}})
    _consume(budget, len(canonical_stub_json_bytes(metadata)))
    _require(metadata["configuration"] == configuration)
    cases = metadata["cases"]
    _require(type(cases) is list and 1 <= len(cases) <= _MAX_CASES)
    case_ids, input_hashes = [], []
    for case in cases:
        _shape(case, {"case_id", "input"})
        _require(_identifier(case["case_id"]) and case["case_id"] not in case_ids
                 and type(case["input"]) is dict, "INVALID_CASE_MANIFEST")
        case_ids.append(case["case_id"])
        input_hashes.append(_digest(canonical_stub_json_bytes(case["input"])))
    _pin(metadata["dataset"])
    _require(metadata["dataset"]["sha256"] == _digest(canonical_stub_json_bytes(cases)), "DATASET_HASH_MISMATCH")
    _require(type(metadata["source_commit"]) is str and _COMMIT.fullmatch(metadata["source_commit"]) is not None)
    _model(metadata["underlying_model"])
    execution = metadata["execution"]
    _shape(execution, {"timeout_seconds", "retry_count"})
    _require(type(execution["timeout_seconds"]) in (int, float) and 0 < execution["timeout_seconds"] <= 60
             and type(execution["retry_count"]) is int and execution["retry_count"] == 0)
    architecture = metadata["architecture"]
    _shape(architecture, {"retrieval", "independent_review", "deterministic_gates", "operation_authority", "network_calls"})
    _require(all(type(v) is bool for v in architecture.values()))
    expected_architecture = {"retrieval": configuration == "B4_OFFLINE_STUB",
                             "independent_review": configuration == "B4_OFFLINE_STUB",
                             "deterministic_gates": configuration == "B4_OFFLINE_STUB",
                             "operation_authority": False, "network_calls": False}
    _require(architecture == expected_architecture, "INVALID_STUB_ARCHITECTURE")
    artifacts = run["artifacts"]
    _shape(artifacts, _ARTIFACTS)
    pins = {}
    for name in sorted(_ARTIFACTS):
        artifact = artifacts[name]
        _shape(artifact, {"version", "sha256", "content"})
        pin = _snapshot({key: artifact[key] for key in ("version", "sha256")})
        _pin(pin)
        raw = artifact["content"]
        _require(type(raw) is bytes and 1 <= len(raw) <= _MAX_BYTES, "INVALID_ARTIFACT_BYTES")
        _consume(budget, len(raw) + len(canonical_stub_json_bytes(pin)))
        _require(_digest(raw) == pin["sha256"], "ARTIFACT_HASH_MISMATCH")
        if name == "configuration":
            config = {key: metadata[key] for key in ("configuration", "underlying_model", "execution", "architecture")}
            _require(raw == canonical_stub_json_bytes(config), "CONFIGURATION_CONTENT_MISMATCH")
        pins[name] = {**pin, "byte_count": len(raw)}
    report = _results(run["results"], case_ids, configuration, budget)
    return {**report, "configuration": configuration, "dataset": metadata["dataset"],
            "source_commit": metadata["source_commit"], "underlying_model": metadata["underlying_model"],
            "execution": execution, "architecture_declarations": architecture, "artifact_pins": pins,
            "case_inputs": [{"case_id": cid, "input_sha256": digest} for cid, digest in zip(case_ids, input_hashes)]}


def validate_stub_pair(*, data_role: str, b1: dict, b4: dict) -> dict:
    """Check both fixture manifests and actual supplied bytes within 4 MiB.

    At most 100 nonempty unique case inputs per run, with identical execution
    order and canonical input bytes. Underlying model settings, deadline,
    no-retry policy, code commit, dataset, corpus, scorer and environment pins
    must match. Prompt/configuration pins may differ for architectural reasons.
    Both stub declarations prohibit network/operation authority; B1 additionally
    prohibits retrieval/review/gates. This checks declarations, not permissions.

    Missing/failed/invalid outputs keep all expected IDs in the accounting.
    The caller can retain no raw bytes for an unavailable/invalid result; its
    digest stays null, never a fabricated hash. Supplied bytes are checked, but
    authenticity/meaning/version labels and absent hidden labels are unproved.
    No scoring or formal freeze/blind-protocol acceptance occurs here.
    """
    try:
        _require(type(data_role) is str and data_role == DATA_ROLE)
        budget = [0]
        left = _run(b1, "B1_OFFLINE_STUB", budget)
        right = _run(b4, "B4_OFFLINE_STUB", budget)
        _require([r["case_id"] for r in left["case_inputs"]] == [r["case_id"] for r in right["case_inputs"]],
                 "PAIR_CASE_ORDER_MISMATCH")
        _require(left["case_inputs"] == right["case_inputs"], "PAIR_INPUT_MISMATCH")
        for key in ("dataset", "underlying_model", "execution", "source_commit"):
            _require(canonical_stub_json_bytes(left[key]) == canonical_stub_json_bytes(right[key]),
                     "PAIR_CONDITIONS_MISMATCH")
        for name in ("corpus", "scorer", "environment"):
            _require(left["artifact_pins"][name] == right["artifact_pins"][name], "PAIR_SHARED_ARTIFACT_MISMATCH")
        report = {
            "data_role": DATA_ROLE, "execution_mode": "PAIRED_STUB_EVIDENCE_VALIDATION_ONLY",
            "formal_performance_claim": False, "integrity_consistency_valid": True,
            "actual_execution_proven": False, "permission_isolation_proven": False,
            "blind_protocol_proven": False, "acceptance_proven": False,
            "comparison_scope": "WHOLE_ARCHITECTURE_NOT_ISOLATED_AGENT_CAUSALITY",
            "expected_case_count_per_run": left["expected_case_count"],
            "checked_evidence_bytes": budget[0], "b1": left, "b4": right,
        }
        report["receipt_sha256"] = _digest(canonical_stub_json_bytes(report))
        return report
    except ReproducibilityError as error:
        code = error.code
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        code = "INVALID_REPRODUCIBILITY_MANIFEST"
    raise ReproducibilityError(code) from None
