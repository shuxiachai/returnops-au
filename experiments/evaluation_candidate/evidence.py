"""One-command E.09 rehearsal with five fixed public, invented cases.

Run ``python -B -m experiments.evaluation_candidate.evidence --output-dir NEW``.
NEW's parent must exist and every path component must be a physical directory,
not a symlink. A private same-parent stage is atomically published without
replacement (macOS/Linux); errors remove only this command's unpublished stage.

This is NOT a provider benchmark, Gold freeze, permission sandbox, authentic
human review, delivery gate or acceptance. The two local fixture adapters do
not implement B1/B4 architecture. Declared latency examples are not measured
adapter/proposal time. Hashes show byte consistency, not provenance or truth.
Only stdlib and the adjacent pure evaluation modules are used. Git is read
locally for source identity; no network, credentials or arbitrary input loader.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import ctypes
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import secrets
import stat
import subprocess
import sys

from .latency import summarize_stub_proposal_latency
from .quality import observation_sha256, score_stub_quality
from .reproducibility import canonical_stub_json_bytes, validate_stub_pair
from .runner import run_stub_cases
from .scoring import DATA_ROLE, score_stub_run


CONFIGS = ("B1_OFFLINE_STUB", "B4_OFFLINE_STUB")
_VERSION = "public-five-case-evidence-v1"
_LIMIT = 2 * 1024 * 1024
_SOURCE_NAMES = ("__init__.py", "scoring.py", "runner.py", "latency.py",
                 "quality.py", "reproducibility.py", "evidence.py")
_SCOPE = {
    "data_role": DATA_ROLE, "execution_mode": "FIXED_OFFLINE_SYNTHETIC_REHEARSAL_ONLY",
    "formal_performance_claim": False, "actual_provider_execution": False,
    "actual_retrieval_or_independent_agent": False, "gold_or_freeze_receipt": False,
    "human_review_authenticated": False, "gate_or_acceptance_claim": False,
    "permission_sandbox_claim": False,
    "latency_origin": "DECLARED_SYNTHETIC_EVENT_FIXTURE_NOT_OBSERVED_RUNTIME",
    "semantic_judgments": "PREDEFINED_PUBLIC_FIXTURE_JUDGMENTS_NOT_HUMAN_REVIEW",
}


class EvidenceError(ValueError):
    """A bounded diagnostic without local paths or exception contents."""


def _digest(raw):
    return sha256(raw).hexdigest()


def _json(value):
    return canonical_stub_json_bytes(value)


def _fixtures():
    """Build independent fixed expectations/judgments BEFORE any invocation.

    These toy values intentionally contain failure, invalid and unknown cases.
    They are not a proposed expansion of the project's 30-case Gold study.
    """
    scenarios = (
        ("demo-faulty-supported", "FAULTY", "The invented lamp will not switch on.", "RETURN"),
        ("demo-change-mind-unknown", "CHANGE_MIND", "I changed my mind about an invented mug.", "REVIEW"),
        ("demo-wrong-item-failure", "WRONG_ITEM", "The invented parcel contains a blue hat, not a red hat.", "RETURN"),
        ("demo-source-conflict", "FAULTY", "Two supplied invented notes disagree about the lamp fault.", "ESCALATE"),
        ("demo-malformed-output", "WRONG_ITEM", "An invented scarf arrived instead of an invented hat.", "RETURN"),
    )
    cases = [{"case_id": cid, "input": {"request": text, "order_ref": "public-order-" + str(i)}}
             for i, (cid, _, text, _) in enumerate(scenarios, 1)]
    risk_expected = [{"case_id": cid, "escalation_expected": cid == "demo-source-conflict",
                      "acceptable_outcomes": ["ESCALATE"] if cid == "demo-source-conflict" else ["PASS", "NEEDS_INFORMATION"],
                      "required_field_ids": ["request", "order_ref"]} for cid, *_ in scenarios]
    quality_expected = [{"case_id": cid, "category": category,
                         "required_field_ids": ["request", "order_ref"],
                         "required_component_ids": ["rationale"],
                         "acceptable_recommendations": [recommendation]}
                        for cid, category, _, recommendation in scenarios]
    outputs, annotations = {}, {}
    for config in CONFIGS:
        b4 = config == CONFIGS[1]
        outputs[config], annotations[config] = {}, []
        for i, (cid, category, text, recommendation) in enumerate(scenarios, 1):
            conflict = cid == "demo-source-conflict"
            rich = {
                "case_id": cid, "status": "SUCCEEDED", "category": category,
                "recommendation": recommendation if b4 or not conflict else "RETURN",
                "fields": {"request": text, "order_ref": "public-order-" + str(i)},
                "components": {"rationale": "Invented review rationale; not consumer or legal advice."},
                "questions": {"clarification": "Which invented note should be corrected?"} if conflict else {},
                "claims": {"guidance": {"text": "The invented demonstration policy asks for a review.",
                                         "citation_ids": ["use-policy"] if b4 else []}},
                "citations": {"use-policy": {"source_id": "public-demo-policy", "passage_id": "demo-p1"}} if b4 else {},
            }
            if not b4 and cid == "demo-faulty-supported":
                del rich["fields"]["order_ref"]  # Deliberate incomplete fixture.
            # Inventory every material assertion in the rich fixture, not just
            # the policy sentence. Question text is a request, not an asserted
            # fact. These explicit toy facts need no external policy citation.
            rich["claims"].update({
                "field-" + key: {"text": value, "citation_ids": []}
                for key, value in rich["fields"].items()
            })
            rich["claims"].update({
                "category": {"text": rich["category"], "citation_ids": []},
                "recommendation": {"text": rich["recommendation"], "citation_ids": []},
                "rationale": {"text": rich["components"]["rationale"], "citation_ids": []},
            })
            outputs[config][cid] = {
                "quality": rich,
                "risk_outcome": "ESCALATE" if conflict and b4 else (
                    "NEEDS_INFORMATION" if cid == "demo-change-mind-unknown" else "PASS"),
                "behavior": "FAIL" if cid == "demo-wrong-item-failure" else (
                    "INVALID" if cid == "demo-malformed-output" else "RETURN"),
            }
            unknown = cid == "demo-change-mind-unknown"
            # Fixed toy reviewer judgments, bound now, not inferred from a later
            # adapter response. A changed response cannot silently get rehashed.
            annotations[config].append({
                "case_id": cid, "observation_sha256": observation_sha256(rich),
                "claim_inventory_complete": None if unknown else True,
                "field_correct": {"request": None if unknown else True,
                                  **({"order_ref": True} if "order_ref" in rich["fields"] else {})},
                "component_correct": {"rationale": None if unknown else not (conflict and not b4)},
                "question_necessary": {"clarification": True} if conflict else {},
                "claim_needs_citation": {key: key == "guidance" for key in rich["claims"]},
                "claim_critical_fabrication": {key: None if unknown else False for key in rich["claims"]},
                "citation_correct": {"use-policy": None if unknown else True} if b4 else {},
            })
    latency = [{"case_id": cid, "status": "REVIEW_READY",
                "accepted_complete_at": "2026-01-01T00:00:00Z",
                "stored_review_ready_at": "2026-01-01T00:00:20Z",
                "excluded_waits": [{"kind": "HUMAN", "start_at": "2026-01-01T00:00:05Z",
                                    "end_at": "2026-01-01T00:00:10Z"}]} for cid, *_ in scenarios]
    return {"cases": cases, "risk_expectations": risk_expected, "quality_expectations": quality_expected,
            "class_labels": ["FAULTY", "CHANGE_MIND", "WRONG_ITEM"],
            "outputs": outputs, "annotations": annotations, "latency": latency,
            "corpus": {"role": "INVENTED_TEXT_NOT_ADMITTED_C1_CORPUS",
                       "passages": [{"source_id": "public-demo-policy", "passage_id": "demo-p1",
                                     "text": "The invented demonstration policy asks for a review."}]}}


class _FixtureAdapter:
    """Trusted fixed-output stub. Receives no expectations or judgment objects."""

    def __init__(self, outputs):
        self.outputs = deepcopy(outputs)
        self.retained = {}

    async def __call__(self, invocation):
        spec = deepcopy(self.outputs[invocation.case_id])
        if spec["behavior"] == "FAIL":
            raise RuntimeError("PUBLIC_SYNTHETIC_ADAPTER_FAILURE")
        rich = spec["quality"]
        risk = {"case_id": invocation.case_id, "status": "SUCCEEDED",
                "risk_outcome": spec["risk_outcome"], "present_field_ids": sorted(rich["fields"]),
                "retrieved_passage_ids": sorted({v["passage_id"] for v in rich["citations"].values()}),
                "input_tokens": None, "output_tokens": None, "estimated_cost": None}
        if spec["behavior"] == "INVALID":
            risk["unexpected_fixture_field"] = True
        self.retained[invocation.case_id] = {
            "configuration": invocation.configuration, "case_id": invocation.case_id,
            "input_sha256": _digest(invocation.input_json.encode("utf-8")),
            "risk_sha256": _digest(_json(risk)), "quality_sha256": observation_sha256(rich),
            "quality": rich,
        }
        return risk


def _quality_for_batch(batch, retained, cases):
    selected, bindings = [], []
    inputs = {row["case_id"]: _digest(_json(row["input"])) for row in cases}
    for result, observation in zip(batch["case_results"], batch["observations"], strict=True):
        cid, disposition = result["case_id"], result["disposition"]
        record = retained.get(cid)
        bound = bool(record is not None and record["configuration"] == batch["configuration"]
                     and record["case_id"] == cid and record["input_sha256"] == inputs[cid]
                     and record["risk_sha256"] == _digest(_json(observation))
                     and record["quality_sha256"] == observation_sha256(record["quality"]))
        if disposition == "SUCCEEDED" and bound:
            selected.append(deepcopy(record["quality"]))
        elif disposition == "FAILED":
            selected.append({"case_id": cid, "status": "FAILED", "category": None,
                             "recommendation": None, "fields": {}, "components": {},
                             "questions": {}, "claims": {}, "citations": {}})
        else:
            selected.append({"case_id": cid})  # Invalid/missing binding earns no quality success.
        bindings.append({"case_id": cid, "runner_disposition": disposition,
                         "same_invocation_binding_valid": bound,
                         "quality_selected": disposition == "SUCCEEDED" and bound,
                         "retained": deepcopy(record)})
    return {"observations": selected, "bindings": bindings}


def _latency_for_batch(batch, declared):
    by_id = {row["case_id"]: row for row in declared}
    result = []
    for row in batch["case_results"]:
        cid = row["case_id"]
        if row["disposition"] == "SUCCEEDED":
            result.append(deepcopy(by_id[cid]))
        elif row["disposition"] == "FAILED":
            result.append({"case_id": cid, "status": "FAILED", "accepted_complete_at": None,
                           "stored_review_ready_at": None, "excluded_waits": []})
        else:
            result.append({"case_id": cid})
    return result


def _git(root, args, *, absent_ok=False):
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0"}
    try:
        result = subprocess.run(["git", "--no-pager", "-c", "core.fsmonitor=false",
                                 "-c", "core.untrackedCache=false", "-C", str(root), *args],
                                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        raise EvidenceError("SOURCE_IDENTITY_UNAVAILABLE") from None
    if result.returncode:
        if absent_ok:
            return None
        raise EvidenceError("SOURCE_IDENTITY_UNAVAILABLE")
    if len(result.stdout) > _LIMIT:
        raise EvidenceError("SOURCE_IDENTITY_TOO_LARGE")
    return result.stdout


def _source_identity():
    root = Path(__file__).resolve().parents[2]
    commit = _git(root, ["rev-parse", "HEAD"]).decode("ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise EvidenceError("SOURCE_IDENTITY_UNAVAILABLE")
    sources = {}
    for name in _SOURCE_NAMES:
        relative = "experiments/evaluation_candidate/" + name
        path = root / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _LIMIT:
            raise EvidenceError("INVALID_SOURCE_FILE")
        raw = path.read_bytes()
        pinned = _git(root, ["show", commit + ":" + relative], absent_ok=True)
        sources[relative] = {"sha256": _digest(raw), "byte_count": len(raw),
                             "head_sha256": _digest(pinned) if pinned is not None else None,
                             "matches_head": pinned == raw}
    return {"head_commit": commit, "files": sources,
            "relevant_sources_match_head": all(item["matches_head"] for item in sources.values()),
            "repository_worktree_clean_at_capture": not bool(_git(root, ["status", "--porcelain", "--untracked-files=normal"])),
            "identity_limit": "HEAD_AND_ACTUAL_FILE_BYTES_NOT_EXECUTION_ATTESTATION"}


def _environment():
    return {"python": platform.python_version(), "implementation": platform.python_implementation(),
            "system": platform.system(), "system_release": platform.release(), "machine": platform.machine(),
            "dependencies": "PYTHON_STDLIB_AND_TRACKED_EVALUATION_MODULES_ONLY",
            "external_read_only_tool": "git", "network_calls": False}


def _artifact(raw):
    return {"version": _VERSION, "sha256": _digest(raw), "content": raw}


def _pair_run(batch, fixtures, source, environment):
    configuration = batch["configuration"]
    b4 = configuration == CONFIGS[1]
    run = {"configuration": configuration, "cases": deepcopy(fixtures["cases"]),
           "dataset": {"version": _VERSION, "sha256": _digest(_json(fixtures["cases"]))},
           "underlying_model": {"provider_id": "NO_PROVIDER_SYNTHETIC_FIXTURE",
                                "model_id": "NO_MODEL_FIXED_OUTPUT", "revision": _VERSION,
                                "parameters": {"temperature": 0, "top_p": 1, "seed": None, "max_output_tokens": 512}},
           "execution": {"timeout_seconds": 30, "retry_count": 0},
           "architecture": {"retrieval": b4, "independent_review": b4, "deterministic_gates": b4,
                            "operation_authority": False, "network_calls": False},
           "source_commit": source["head_commit"], "artifacts": {}, "results": []}
    configuration_bytes = _json({key: run[key] for key in ("configuration", "underlying_model", "execution", "architecture")})
    run["artifacts"] = {
        "corpus": _artifact(_json(fixtures["corpus"])),
        "prompts": _artifact(_json({"role": "FIXTURE_BEHAVIOR_NOT_SUBMITTED_MODEL_PROMPT",
                                    "configuration": configuration, "outputs": fixtures["outputs"][configuration]})),
        "configuration": _artifact(configuration_bytes),
        "scorer": _artifact(_json(source)), "environment": _artifact(_json(environment)),
    }
    for row, observation in zip(batch["case_results"], batch["observations"], strict=True):
        raw = _json(observation)  # Actual runner result, including sanitized INVALID sentinel.
        run["results"].append({**row, "raw_output": raw, "raw_output_sha256": _digest(raw)})
    return run


def _encode_bytes(value):
    """Losslessly expose known UTF-8 fixture bytes in the bundle's paired JSON."""
    if type(value) is bytes:
        return {"encoding": "utf-8", "content": value.decode("utf-8")}
    if type(value) is dict:
        return {key: _encode_bytes(item) for key, item in value.items()}
    if type(value) is list:
        return [_encode_bytes(item) for item in value]
    return value


async def build_demo_evidence():
    """Return deterministic filename -> bytes artifacts; never publish files.

    No external adapter/input argument is provided. Fixtures are public toy
    observations, not blind performance data. The exact source and environment
    are captured, so different sources/environments produce different hashes.
    """
    fixtures = _fixtures()
    source, environment = _source_identity(), _environment()
    batches, quality, latency, scores, pairs = {}, {}, {}, {}, {}
    for configuration in CONFIGS:
        adapter = _FixtureAdapter(fixtures["outputs"][configuration])
        batch = await run_stub_cases(configuration=configuration, data_role=DATA_ROLE,
                                     cases=fixtures["cases"], adapter=adapter, timeout_seconds=30)
        batches[configuration] = batch
        quality[configuration] = _quality_for_batch(batch, adapter.retained, fixtures["cases"])
        latency[configuration] = _latency_for_batch(batch, fixtures["latency"])
        scores[configuration] = {
            "risk": score_stub_run(configuration=configuration, data_role=DATA_ROLE,
                                   expectations=fixtures["risk_expectations"], observations=batch["observations"]),
            "quality": score_stub_quality(data_role=DATA_ROLE, class_labels=fixtures["class_labels"],
                                          expectations=fixtures["quality_expectations"],
                                          observations=quality[configuration]["observations"],
                                          annotations=fixtures["annotations"][configuration]),
            "declared_synthetic_latency": summarize_stub_proposal_latency(
                data_role=DATA_ROLE, expected_case_ids=[r["case_id"] for r in fixtures["cases"]],
                observations=latency[configuration]),
            "error_counts": dict(sorted(Counter(row["error_code"] for row in batch["case_results"]
                                                 if row["error_code"] is not None).items())),
        }
        pairs[configuration] = _pair_run(batch, fixtures, source, environment)
    paired = validate_stub_pair(data_role=DATA_ROLE, b1=pairs[CONFIGS[0]], b4=pairs[CONFIGS[1]])
    if source != _source_identity():
        raise EvidenceError("SOURCE_CHANGED_DURING_REHEARSAL")
    artifacts = {
        "inputs.json": {**_SCOPE, "cases": fixtures["cases"]},
        "fixture-expectations.json": {**_SCOPE, "risk": fixtures["risk_expectations"],
                                      "quality": fixtures["quality_expectations"],
                                      "class_labels": fixtures["class_labels"],
                                      "annotations_bound_before_invocation": fixtures["annotations"]},
        "source-manifest.json": source, "environment.json": environment,
        "b1.raw.json": batches[CONFIGS[0]], "b4.raw.json": batches[CONFIGS[1]],
        "quality-evidence.json": {**_SCOPE, "runs": quality},
        "latency-fixtures.json": {**_SCOPE, "declared_events": fixtures["latency"],
                                  "accounted_events_by_runner_disposition": latency},
        "paired-inputs.json": {**_SCOPE, "byte_encoding": "TAGGED_UTF8_EXACT_CONTENT",
                               "runs": _encode_bytes(pairs)},
        "summaries.json": {**_SCOPE, "runs": scores, "paired_integrity": paired},
    }
    files = {name: _json(value) for name, value in artifacts.items()}
    manifest = {**_SCOPE, "format_version": _VERSION,
                "files": {name: {"sha256": _digest(raw), "byte_count": len(raw)}
                          for name, raw in sorted(files.items())}}
    # Hash only reproducible content. Creation time is recorded separately and
    # neither this hash nor any timestamp is a seal or authenticity signature.
    manifest["content_id"] = _digest(_json(manifest))
    files["manifest.json"] = _json(manifest)
    return files


def _open_parent(output):
    path = Path(output)
    if ".." in path.parts or not path.name or path.name in {".", ".."}:
        raise EvidenceError("INVALID_OUTPUT_PATH")
    absolute = path if path.is_absolute() else Path.cwd() / path
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parts[1:-1]:
            next_fd = os.open(component, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        try:
            os.stat(absolute.name, dir_fd=current, follow_symlinks=False)
        except FileNotFoundError:
            return current, absolute.name
        raise EvidenceError("OUTPUT_ALREADY_EXISTS")
    except BaseException:
        os.close(current)
        raise


def _rename_no_replace(parent_fd, source_name, destination_name):
    """Native atomic no-replace rename; never fall back to overwrite rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function, flag = getattr(libc, "renameatx_np", None), 0x4  # RENAME_EXCL, sys/stdio.h.
    elif sys.platform.startswith("linux"):
        function, flag = getattr(libc, "renameat2", None), 1  # RENAME_NOREPLACE.
    else:
        function, flag = None, None
    if function is None:
        raise EvidenceError("ATOMIC_PUBLICATION_UNSUPPORTED")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(parent_fd, os.fsencode(source_name), parent_fd, os.fsencode(destination_name), flag):
        raise EvidenceError("ATOMIC_PUBLICATION_REFUSED")


def publish_demo_evidence(output, files):
    """Publish only generated fixed filenames to a new private directory.

    Atomic visibility is provided, not a crash-durability/hostile-local-user
    sandbox claim. Existing paths, including empty directories and dangling
    links, are never replaced. This function accepts no arbitrary source files.
    """
    expected = {"inputs.json", "fixture-expectations.json", "source-manifest.json", "environment.json",
                "b1.raw.json", "b4.raw.json", "quality-evidence.json", "latency-fixtures.json",
                "paired-inputs.json", "summaries.json", "manifest.json"}
    if (type(files) is not dict or set(files) != expected
            or any(type(raw) is not bytes or len(raw) > _LIMIT for raw in files.values())):
        raise EvidenceError("INVALID_GENERATED_BUNDLE")
    files = dict(files)
    files["creation.json"] = _json({"created_at_utc": datetime.now(timezone.utc).isoformat(),
                                     "manifest_sha256": _digest(files["manifest.json"]),
                                     "timestamp_is_not_a_seal": True})
    files["index.json"] = _json({"files": {name: {"sha256": _digest(raw), "byte_count": len(raw)}
                                           for name, raw in sorted(files.items())},
                                "index_excludes_itself": True,
                                "creation_excluded_from_reproducible_content_id": True})
    parent_fd, destination = _open_parent(output)
    stage, stage_fd, created, published = ".returnops-evidence-" + secrets.token_hex(16), None, [], False
    stage_identity = None
    try:
        os.mkdir(stage, 0o700, dir_fd=parent_fd)
        stage_identity = os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
        stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        for name, raw in sorted(files.items()):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=stage_fd)
            created.append(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        opened, named = os.fstat(stage_fd), os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(named.st_mode) or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise EvidenceError("STAGING_DIRECTORY_CHANGED")
        _rename_no_replace(parent_fd, stage, destination)
        published = True
    finally:
        try:
            if stage_fd is not None:
                try:
                    if not published:
                        for name in created:
                            os.unlink(name, dir_fd=stage_fd)
                finally:
                    os.close(stage_fd)
            if not published and stage_identity is not None:
                try:
                    named = os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    named = None
                if named is not None and (named.st_dev, named.st_ino) == (stage_identity.st_dev, stage_identity.st_ino):
                    os.rmdir(stage, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="New physical path; existing parent; no overwrite")
    args = parser.parse_args(argv)
    try:
        files = asyncio.run(build_demo_evidence())
        publish_demo_evidence(args.output_dir, files)
    except (EvidenceError, ValueError, OSError, subprocess.SubprocessError):
        print("Offline evidence failed; no existing destination was overwritten.", file=sys.stderr)
        return 1
    print(json.dumps({"status": "SYNTHETIC_EVIDENCE_WRITTEN", "file_count": len(files) + 2,
                      "manifest_sha256": _digest(files["manifest.json"]), "formal_acceptance": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
