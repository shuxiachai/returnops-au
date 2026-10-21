"""Public invented E.09 byte-manifest fixtures, never Gold/provider evidence."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from experiments.evaluation_candidate import DATA_ROLE
from experiments.evaluation_candidate.reproducibility import (
    ReproducibilityError, canonical_stub_json_bytes, validate_stub_pair,
)
from experiments.evaluation_candidate.runner import run_stub_cases


def digest(raw):
    return sha256(raw).hexdigest()


def artifact(content, version="public-fixture-v1"):
    return {"version": version, "sha256": digest(content), "content": content}


def observation(case_id):
    return {"case_id": case_id, "status": "SUCCEEDED", "risk_outcome": "PASS",
            "present_field_ids": [], "retrieved_passage_ids": [],
            "input_tokens": None, "output_tokens": None, "estimated_cost": None}


def result(case_id, disposition="SUCCEEDED", raw=None, error=None):
    if raw is None and disposition == "SUCCEEDED":
        raw = canonical_stub_json_bytes(observation(case_id))
    return {"case_id": case_id, "disposition": disposition, "error_code": error,
            "raw_output": raw, "raw_output_sha256": digest(raw) if raw is not None else None}


def repin(run):
    run["dataset"]["sha256"] = digest(canonical_stub_json_bytes(run["cases"]))
    config = {key: run[key] for key in ("configuration", "underlying_model", "execution", "architecture")}
    run["artifacts"]["configuration"] = artifact(canonical_stub_json_bytes(config))


def run_fixture(configuration):
    is_b4 = configuration == "B4_OFFLINE_STUB"
    run = {
        "configuration": configuration,
        "cases": [{"case_id": cid, "input": {"text": "Public invented scenario " + cid}} for cid in ("a", "b")],
        "dataset": {"version": "public-synthetic-v1", "sha256": ""},
        "underlying_model": {"provider_id": "synthetic-provider", "model_id": "synthetic-model",
                             "revision": "synthetic-revision-1", "parameters": {
                                 "temperature": 0, "top_p": 1, "seed": None, "max_output_tokens": 512}},
        "execution": {"timeout_seconds": 1, "retry_count": 0},
        "architecture": {"retrieval": is_b4, "independent_review": is_b4, "deterministic_gates": is_b4,
                         "operation_authority": False, "network_calls": False},
        "source_commit": "a" * 40,  # Deliberately invented, never asserted to resolve.
        "artifacts": {name: artifact(("public fixture " + name).encode())
                      for name in ("corpus", "scorer", "environment")},
        "results": [result(cid) for cid in ("a", "b")],
    }
    run["artifacts"]["prompts"] = artifact(("public fixture " + configuration).encode())
    repin(run)
    return run


class ReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.b1 = run_fixture("B1_OFFLINE_STUB")
        self.b4 = run_fixture("B4_OFFLINE_STUB")

    def validate(self):
        return validate_stub_pair(data_role=DATA_ROLE, b1=self.b1, b4=self.b4)

    def rejects(self, code=None):
        with self.assertRaises(ReproducibilityError) as caught:
            self.validate()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)

    def test_pair_pins_actual_bytes_and_preserves_architecture_differences(self):
        report = self.validate()
        self.assertTrue(report["integrity_consistency_valid"])
        for key in ("formal_performance_claim", "actual_execution_proven", "permission_isolation_proven",
                    "blind_protocol_proven", "acceptance_proven"):
            self.assertFalse(report[key])
        self.assertNotEqual(report["b1"]["artifact_pins"]["prompts"], report["b4"]["artifact_pins"]["prompts"])
        self.assertNotEqual(report["b1"]["artifact_pins"]["configuration"], report["b4"]["artifact_pins"]["configuration"])
        self.assertEqual(report["b1"]["case_evidence"][0]["raw_output_sha256"], digest(self.b1["results"][0]["raw_output"]))
        receipt = report.pop("receipt_sha256")
        self.assertEqual(receipt, digest(canonical_stub_json_bytes(report)))
        self.assertNotIn("Public invented scenario", json.dumps(report))
        self.assertNotIn("public fixture corpus", json.dumps(report))

    def test_order_ids_and_input_bytes_must_match(self):
        original = deepcopy(self.b4)
        for mode, code in (("order", "PAIR_CASE_ORDER_MISMATCH"), ("id", "PAIR_CASE_ORDER_MISMATCH"),
                           ("text", "PAIR_INPUT_MISMATCH")):
            self.b4 = deepcopy(original)
            if mode == "order":
                self.b4["cases"].reverse()
            elif mode == "id":
                self.b4["cases"][0]["case_id"] = "changed"
                self.b4["results"][0] = result("changed")
            else:
                self.b4["cases"][0]["input"]["text"] += " changed"
            repin(self.b4)
            with self.subTest(mode=mode):
                self.rejects(code)

    def test_canonical_key_order_matches_but_numeric_representations_do_not(self):
        for run in (self.b1, self.b4):
            run["cases"][0]["input"] = {"z": 1, "a": 2}
            repin(run)
        self.b4["cases"][0]["input"] = {"a": 2, "z": 1}
        repin(self.b4)
        self.validate()
        self.b4["cases"][0]["input"]["z"] = 1.0
        repin(self.b4)
        self.rejects("PAIR_INPUT_MISMATCH")

    def test_empty_duplicate_extra_or_missing_case_is_not_silently_compared(self):
        original = deepcopy(self.b4)
        for cases in ([], [original["cases"][0]] * 2,
                      original["cases"] + [{"case_id": "extra", "input": {}}], original["cases"][:1]):
            self.b4 = deepcopy(original)
            self.b4["cases"] = cases
            self.b4["results"] = []
            repin(self.b4)
            with self.subTest(count=len(cases)):
                self.rejects()

    def test_underlying_model_and_execution_must_match_not_just_model_name(self):
        original = deepcopy(self.b4)
        changes = (("provider_id", "other"), ("revision", "other"), ("model_id", "other"))
        for key, value in changes:
            self.b4 = deepcopy(original)
            self.b4["underlying_model"][key] = value
            repin(self.b4)
            with self.subTest(key=key):
                self.rejects("PAIR_CONDITIONS_MISMATCH")
        for key, value in (("temperature", .5), ("top_p", .9), ("seed", 3), ("max_output_tokens", 1024)):
            self.b4 = deepcopy(original)
            self.b4["underlying_model"]["parameters"][key] = value
            repin(self.b4)
            with self.subTest(key=key):
                self.rejects("PAIR_CONDITIONS_MISMATCH")
        self.b4 = deepcopy(original)
        self.b4["execution"]["timeout_seconds"] = 2
        repin(self.b4)
        self.rejects("PAIR_CONDITIONS_MISMATCH")

    def test_source_dataset_shared_artifact_versions_and_bytes_are_pinned(self):
        original = deepcopy(self.b4)
        for name in ("corpus", "scorer", "environment"):
            self.b4 = deepcopy(original)
            self.b4["artifacts"][name] = artifact(b"different public bytes")
            with self.subTest(name=name):
                self.rejects("PAIR_SHARED_ARTIFACT_MISMATCH")
        for key in ("source_commit", "dataset"):
            self.b4 = deepcopy(original)
            if key == "dataset":
                self.b4[key]["version"] = "other-version"
            else:
                self.b4[key] = "b" * 40
            with self.subTest(key=key):
                self.rejects("PAIR_CONDITIONS_MISMATCH")

    def test_bad_missing_or_unbacked_hash_cannot_be_accepted(self):
        self.b4["artifacts"]["scorer"]["content"] += b"changed"
        self.rejects("ARTIFACT_HASH_MISMATCH")
        self.b4 = run_fixture("B4_OFFLINE_STUB")
        self.b4["dataset"]["sha256"] = "f" * 64
        self.rejects("DATASET_HASH_MISMATCH")
        self.b4 = run_fixture("B4_OFFLINE_STUB")
        del self.b4["artifacts"]["environment"]["content"]
        self.rejects()

    def test_configuration_artifact_must_match_declared_fields(self):
        self.b4["artifacts"]["configuration"] = artifact(b'{"api_key":"not-a-real-secret"}')
        self.rejects("CONFIGURATION_CONTENT_MISMATCH")

    def test_failed_invalid_missing_results_remain_in_all_expected_accounting(self):
        for run in (self.b1, self.b4):
            run["cases"] += [{"case_id": cid, "input": {}} for cid in ("c", "d")]
            run["results"] = [result("a"), result("b", "FAILED", error="ADAPTER_TIMEOUT"),
                              result("c", "INVALID", raw=b"malformed public output", error="INVALID_ADAPTER_OUTPUT")]
            repin(run)
        report = self.validate()
        for side in ("b1", "b4"):
            run = report[side]
            self.assertEqual(run["expected_case_count"], 4)
            self.assertEqual(run["dispositions"], dict.fromkeys(("SUCCEEDED", "FAILED", "INVALID", "MISSING"), 1))
            self.assertFalse(run["all_cases_succeeded"])
            self.assertEqual(run["unavailable_raw_output_case_ids"], ["b", "d"])
            self.assertEqual(run["case_evidence"][2]["raw_output_sha256"], digest(b"malformed public output"))
        self.assertNotIn("malformed public output", json.dumps(report))

    def test_explicit_missing_and_unretained_invalid_have_null_digests(self):
        self.b4["results"] = [result("a", "MISSING"), result("b", "INVALID", error="INVALID_ADAPTER_OUTPUT")]
        report = self.validate()["b4"]
        self.assertEqual(report["unavailable_raw_output_case_ids"], ["a", "b"])
        self.assertEqual(report["dispositions"]["MISSING"], 1)
        self.assertEqual(report["dispositions"]["INVALID"], 1)

    def test_b1_retrieval_and_malformed_outputs_have_digests_but_no_success_credit(self):
        base = observation("a")
        invalid = [canonical_stub_json_bytes({**base, "retrieved_passage_ids": ["passage"]}),
                   canonical_stub_json_bytes({**base, "input_tokens": True}),
                   canonical_stub_json_bytes({**base, "approval": True}),
                   canonical_stub_json_bytes(observation("wrong-case")),
                   b'{"case_id":"a","case_id":"a"}', b'{"case_id":"a","risk_outcome":NaN}', b"\xff"]
        for raw in invalid:
            with self.subTest(raw=raw[:25]):
                self.b1["results"][0] = result("a", "INVALID", raw, "INVALID_ADAPTER_OUTPUT")
                report = self.validate()["b1"]
                self.assertEqual(report["dispositions"]["INVALID"], 1)
                self.assertEqual(report["case_evidence"][0]["raw_output_sha256"], digest(raw))
                self.b1["results"][0] = result("a", "SUCCEEDED", raw)
                self.rejects("RESULT_DISPOSITION_MISMATCH")

    def test_valid_failed_observation_retains_its_exact_raw_byte_digest(self):
        failed = {**observation("a"), "status": "FAILED", "risk_outcome": None, "input_tokens": 7}
        raw = json.dumps(failed, indent=2).encode()
        self.b4["results"][0] = result("a", "FAILED", raw)
        report = self.validate()["b4"]
        self.assertEqual(report["dispositions"]["FAILED"], 1)
        self.assertEqual(report["case_evidence"][0]["raw_output_sha256"], digest(raw))

    def test_runner_failure_and_timeout_observations_retain_both_bytes_and_diagnostic(self):
        async def exercise(mode):
            async def adapter(invocation):
                if invocation.case_id == "a":
                    if mode == "timeout":
                        await asyncio.sleep(1)
                    raise RuntimeError("private-provider-secret")
                return observation(invocation.case_id)

            for run in (self.b1, self.b4):
                run["execution"]["timeout_seconds"] = .01
                repin(run)
                batch = await run_stub_cases(configuration=run["configuration"], data_role=DATA_ROLE,
                                             cases=run["cases"], adapter=adapter, timeout_seconds=.01)
                run["results"] = [result(diag["case_id"], diag["disposition"],
                                         canonical_stub_json_bytes(row), diag["error_code"])
                                  for row, diag in zip(batch["observations"], batch["case_results"])]

        for mode, expected in (("failure", "ADAPTER_FAILURE"), ("timeout", "ADAPTER_TIMEOUT")):
            with self.subTest(mode=mode):
                asyncio.run(exercise(mode))
                report = self.validate()
                for side in ("b1", "b4"):
                    self.assertEqual(report[side]["dispositions"]["FAILED"], 1)
                    self.assertEqual(report[side]["case_evidence"][0]["error_code"], expected)
                    self.assertIsNotNone(report[side]["case_evidence"][0]["raw_output_sha256"])
                self.assertNotIn("private-provider-secret", json.dumps(report))
        self.b4["results"][0]["error_code"] = "ARBITRARY_FAILURE"
        self.rejects("RESULT_DISPOSITION_MISMATCH")

    def test_false_failure_missing_or_invalid_labels_do_not_hide_success(self):
        raw = canonical_stub_json_bytes(observation("a"))
        for disposition, error in (("FAILED", None), ("INVALID", "INVALID_ADAPTER_OUTPUT"), ("MISSING", None)):
            self.b4["results"][0] = result("a", disposition, raw, error)
            with self.subTest(disposition=disposition):
                self.rejects("RESULT_DISPOSITION_MISMATCH")

    def test_output_digest_must_have_exact_matching_bytes(self):
        self.b4["results"][0]["raw_output_sha256"] = "f" * 64
        self.rejects("RAW_OUTPUT_HASH_MISMATCH")
        self.b4["results"][0] = result("a", "FAILED", error="ADAPTER_FAILURE")
        self.b4["results"][0]["raw_output_sha256"] = "f" * 64
        self.rejects("RAW_OUTPUT_HASH_WITHOUT_BYTES")

    def test_extra_duplicate_and_misbound_result_records_are_rejected(self):
        for extra, code in ((result("a"), "DUPLICATE_RESULT_CASE"), (result("unknown"), "UNKNOWN_RESULT_CASE")):
            self.b4["results"] = [result("a"), result("b"), extra]
            with self.subTest(code=code):
                self.rejects(code)

    def test_bool_nonfinite_non_json_oversize_and_recursive_metadata_fail_safely(self):
        recursive = {}
        recursive["self"] = recursive
        for value in ({1: "bad key"}, {"tuple": (1,)}, {"n": float("nan")},
                      {"n": float("inf")}, {"text": "x" * (2 * 1024 * 1024)}, recursive):
            self.b4["cases"][0]["input"] = value
            self.rejects()
        self.b4 = run_fixture("B4_OFFLINE_STUB")
        for key in ("seed", "max_output_tokens", "temperature", "top_p"):
            original = self.b4["underlying_model"]["parameters"][key]
            self.b4["underlying_model"]["parameters"][key] = True
            repin(self.b4)
            self.rejects()
            self.b4["underlying_model"]["parameters"][key] = original

    def test_architecture_and_configuration_cannot_declare_authority_or_credentials(self):
        original = deepcopy(self.b1)
        for key in ("retrieval", "independent_review", "deterministic_gates", "operation_authority", "network_calls"):
            self.b1 = deepcopy(original)
            self.b1["architecture"][key] = True
            repin(self.b1)
            with self.subTest(key=key):
                self.rejects("INVALID_STUB_ARCHITECTURE")
        self.b1 = deepcopy(original)
        self.b1["underlying_model"]["api_key"] = "not-a-real-secret"
        repin(self.b1)
        self.rejects()

    def test_pair_and_case_capacity_bounds(self):
        self.b4["cases"] = [{"case_id": str(i), "input": {}} for i in range(101)]
        repin(self.b4)
        self.rejects()
        self.b4 = run_fixture("B4_OFFLINE_STUB")
        for run in (self.b1, self.b4):
            for name in ("corpus", "scorer", "environment"):
                run["artifacts"][name] = artifact(b"x" * (1024 * 1024))
        self.rejects("EVIDENCE_TOO_LARGE")

    def test_scope_unknown_fields_and_non_json_metadata_are_rejected(self):
        with self.assertRaises(ReproducibilityError):
            validate_stub_pair(data_role="GOLD", b1=self.b1, b4=self.b4)
        self.b4["expected_labels"] = ["PASS"]
        self.rejects()
        del self.b4["expected_labels"]
        self.b4["source_commit"] = "floating-main"
        self.rejects()

    def test_receipt_has_no_mutable_alias_to_input_manifest(self):
        before = deepcopy(self.b4)
        report = self.validate()
        report["b4"]["underlying_model"]["parameters"]["max_output_tokens"] = 999
        report["b4"]["artifact_pins"]["corpus"]["version"] = "changed"
        self.assertEqual(self.b4, before)
        self.b4["results"].clear()
        self.assertEqual(len(report["b4"]["case_evidence"]), 2)


if __name__ == "__main__":
    unittest.main()
