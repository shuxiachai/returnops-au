#!/usr/bin/env python3
"""C-F01 independent, local-only artifact regression probe (KAN-22 / KAN-32).

AI-assisted C verification, not a runtime guard, personal signature or F.01
acceptance. Loads the selected source's existing schema/fixtures and A-owned
oracle without modifying them. Optional old-oracle comparison runs only the
historical assert_proposal_bundle function against unchanged schema material.
No network, database, LLM, browser or provider calls are made.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_old_oracle(path: Path, validator):
    """Extract only the exact historical helper, not a rewritten approximation."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "assert_proposal_bundle"]
    if len(functions) != 1:
        raise ValueError("Historical source must contain one named oracle")
    namespace = {"validator": validator, "hashlib": hashlib}
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["assert_proposal_bundle"]


def outcome(oracle, record):
    try:
        oracle(deepcopy(record))
    except AssertionError as error:
        return {"accepted": False, "reason": str(error)}
    return {"accepted": True, "reason": None}


def cases_for(original, legal_results):
    cases = []

    def add(case_id, expected, change=None, original_finding=False):
        record = deepcopy(original)
        if change:
            change(record)
        cases.append((case_id, expected, record, original_finding))

    def stale_packet(record):
        record["record_id"] = "history-proposal-c-newer"
        record["object_version"] += 1
        record["content"]["packet"]["proposal_version"] += 1

    def coherent_newer(record):
        stale_packet(record)
        record["content"]["citation_verification"]["proposal_version"] += 1

    def zero_citations(record):
        record["content"]["packet"]["citations"] = []
        record["content"]["citation_verification"]["checks"] = []

    add("original-valid-bundle", True)
    add("coherent-newer-proposal", True, coherent_newer)
    add("original-newer-packet-stale-verification", False, stale_packet, True)
    add("original-cross-proposal-verification", False,
        lambda r: r["content"]["citation_verification"].update(proposal_id="proposal-c-other"), True)
    add("stale-verification-version", False,
        lambda r: r["content"]["citation_verification"].update(proposal_version=99))
    add("original-missing-check-coverage", False,
        lambda r: r["content"]["citation_verification"].update(checks=[]), True)
    add("extra-verification-check", False,
        lambda r: r["content"]["citation_verification"]["checks"].append({
            **deepcopy(r["content"]["citation_verification"]["checks"][0]),
            "citation_id": "citation-c-extra",
        }))
    add("replaced-verification-check", False,
        lambda r: r["content"]["citation_verification"]["checks"][0].update(citation_id="citation-c-replaced"))
    add("duplicate-verification-check", False,
        lambda r: r["content"]["citation_verification"]["checks"].append(
            deepcopy(r["content"]["citation_verification"]["checks"][0])))
    add("duplicate-packet-citation", False,
        lambda r: r["content"]["packet"]["citations"].append(
            deepcopy(r["content"]["packet"]["citations"][0])))
    for result in legal_results:
        if result != "VALID":
            add(f"retained-failed-evidence-{result.lower()}", True,
                lambda r, result=result: r["content"]["citation_verification"]["checks"][0].update(
                    result=result, message=f"Synthetic historical check reported {result}."))
    add("zero-citations-zero-checks", True, zero_citations)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Selected repository root")
    parser.add_argument("--baseline-source", type=Path, help="Optional historical rc.5 repository root")
    parser.add_argument("--output", type=Path, help="Optional JSON report output; source files stay read-only")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    tests = source / "tests/contracts"
    schema_path = source / "contracts/v1/schemas.json"
    oracle_path = tests / "test_contract_v1_rc4.py"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(tests))
    contract = importlib.import_module("test_contract_v1")
    current = importlib.import_module("test_contract_v1_rc4")
    if Path(current.__file__).resolve() != oracle_path:
        raise RuntimeError("Oracle import did not resolve to the selected source")
    fixture_before = deepcopy(contract.POSITIVE)
    source_hashes_before = {
        str(path.relative_to(source)): sha256(path)
        for parent in (source / "contracts", tests)
        for path in sorted(parent.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    old_oracle = None
    baseline_metadata = None
    if args.baseline_source:
        baseline = args.baseline_source.resolve(strict=True)
        old_path = baseline / "tests/contracts/test_contract_v1_rc4.py"
        if sha256(baseline / "contracts/v1/schemas.json") != sha256(schema_path):
            raise ValueError("Baseline schema differs; this focused cross-oracle comparison is not applicable")
        old_oracle = load_old_oracle(old_path, contract.validator)
        baseline_metadata = {"oracle_sha256": sha256(old_path), "schema_matches_target": True}
    legal_results = contract.SCHEMAS["$defs"]["CitationCheck"]["properties"]["result"]["enum"]
    results = []
    for case_id, expected, record, original_finding in cases_for(current.value("history-proposal"), legal_results):
        contract.validator("FounderHistoryRecord").validate(record)
        actual = outcome(current.assert_proposal_bundle, record)
        row = {"id": case_id, "schema_valid": True, "expected_accepted": expected,
               "current": actual, "passed": actual["accepted"] == expected,
               "original_c_f01_case": original_finding}
        if old_oracle:
            row["historical"] = outcome(old_oracle, record)
            if original_finding:
                row["historical_defect_reproduced"] = row["historical"]["accepted"]
                row["passed"] &= row["historical_defect_reproduced"]
        results.append(row)
    unchanged = contract.POSITIVE == fixture_before and all(
        sha256(source / relative) == expected for relative, expected in source_hashes_before.items())
    report = {
        "probe": "member-c-cf01-20260914", "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "source_oracle_sha256": sha256(oracle_path),
        "source_schema_sha256": sha256(schema_path), "baseline": baseline_metadata,
        "cases": results, "passed_cases": sum(row["passed"] for row in results),
        "total_cases": len(results), "source_and_fixture_unchanged": unchanged,
        "all_passed": unchanged and all(row["passed"] for row in results),
        "scope": "Schema-valid synthetic fixtures and test-only historical material oracle; not runtime, semantic claim support, personal acceptance or a clean-Git/Docker reproduction.",
    }
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
