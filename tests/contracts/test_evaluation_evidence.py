"""Local offline evidence CLI checks; fixtures never establish real acceptance."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from experiments.evaluation_candidate import evidence
from experiments.evaluation_candidate.quality import observation_sha256
from experiments.evaluation_candidate.reproducibility import validate_stub_pair


def publication_supported():
    try:
        evidence._require_publication_support()
    except evidence.EvidencePlatformError:
        return False
    return True


UNIX_PUBLICATION = unittest.skipUnless(publication_supported(), "Requires POSIX atomic no-replace publication")
FIXTURE_SOURCE = {"head_commit": "a" * 40, "identity_limit": "SYNTHETIC_TEST_SOURCE_NOT_ACTUAL_GIT"}


def build_fixture_evidence():
    # Keep pipeline/accounting tests runnable without Unix Git lookup or file
    # publication. A separate supported-host test checks actual source identity.
    with patch.object(evidence, "_source_identity", return_value=deepcopy(FIXTURE_SOURCE)):
        return asyncio.run(evidence.build_demo_evidence())


def decode_bytes(value):
    if type(value) is dict:
        if set(value) == {"encoding", "content"} and value["encoding"] == "utf-8":
            return value["content"].encode("utf-8")
        return {key: decode_bytes(item) for key, item in value.items()}
    if type(value) is list:
        return [decode_bytes(item) for item in value]
    return value


class EvaluationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(evidence.__file__).resolve().parents[2]
        cls.files = build_fixture_evidence()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="returnops-evidence-test-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name).resolve()  # macOS /var alias is intentionally not accepted.
        self.output = self.parent / "new-evidence"

    def loaded(self, name, files=None):
        return json.loads((files or self.files)[name])

    def run_cli(self, output):
        return subprocess.run(
            [sys.executable, "-S", "-B", "-m", "experiments.evaluation_candidate.evidence",
             "--output-dir", str(output)], cwd=self.root,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONPATH": str(self.root),
                 "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=30, check=False,
        )

    def test_actual_runner_results_keep_failure_invalid_and_unknown(self):
        summary = self.loaded("summaries.json")
        for config, filename in zip(evidence.CONFIGS, ("b1.raw.json", "b4.raw.json")):
            with self.subTest(config=config):
                batch, scores = self.loaded(filename), summary["runs"][config]
                self.assertEqual(batch["adapter_call_count"], 5)
                self.assertEqual(batch["retry_count"], 0)
                self.assertEqual(scores["risk"]["dispositions"], {
                    "SUCCEEDED": 3, "FAILED": 1, "INVALID": 1, "MISSING": 0, "DUPLICATE": 0})
                self.assertEqual(scores["quality"]["dispositions"], scores["risk"]["dispositions"])
                self.assertEqual(scores["error_counts"], {"ADAPTER_FAILURE": 1, "INVALID_ADAPTER_OUTPUT": 1})
                self.assertIsNone(scores["quality"]["required_field_correctness"]["value"])
                self.assertIsNone(scores["quality"]["critical_fabrication"]["total"])
                self.assertFalse(summary["formal_performance_claim"])
                self.assertFalse(summary["gold_or_freeze_receipt"])
                self.assertFalse(summary["gate_or_acceptance_claim"])
        for row in self.loaded("b1.raw.json")["observations"]:
            self.assertFalse(row.get("retrieved_passage_ids", []))

    def test_annotations_fixed_before_runner_and_binding_from_same_invocation(self):
        fixtures = self.loaded("fixture-expectations.json")
        quality = self.loaded("quality-evidence.json")["runs"]
        cases = self.loaded("inputs.json")["cases"]
        self.assertEqual(len(cases), 5)
        self.assertTrue(all(set(c["input"]) == {"request", "order_ref"} for c in cases))
        for config in evidence.CONFIGS:
            annotations = {r["case_id"]: r for r in fixtures["annotations_bound_before_invocation"][config]}
            for row in quality[config]["bindings"]:
                if row["quality_selected"]:
                    retained = row["retained"]
                    self.assertTrue(row["same_invocation_binding_valid"])
                    self.assertEqual(retained["quality_sha256"], observation_sha256(retained["quality"]))
                    self.assertEqual(annotations[row["case_id"]]["observation_sha256"], retained["quality_sha256"])
                else:
                    self.assertIn(row["runner_disposition"], {"FAILED", "INVALID"})

    def test_changed_companion_is_not_automatically_reannotated(self):
        original = evidence._FixtureAdapter

        class ChangedRich(original):
            async def __call__(self, invocation):
                reply = await super().__call__(invocation)
                if invocation.case_id == "demo-faulty-supported":
                    record = self.retained[invocation.case_id]
                    record["quality"]["components"]["rationale"] = "Changed output not reviewed by fixed fixture."
                    record["quality_sha256"] = observation_sha256(record["quality"])
                return reply

        with patch.object(evidence, "_FixtureAdapter", ChangedRich):
            files = build_fixture_evidence()
        for config in evidence.CONFIGS:
            quality = self.loaded("summaries.json", files)["runs"][config]["quality"]
            self.assertEqual(quality["annotation_dispositions"]["INVALID"], 1)  # Changed successful output.
            self.assertEqual(quality["dispositions"]["SUCCEEDED"], 3)
            self.assertIsNone(quality["required_field_correctness"]["value"])

    def test_fixed_claim_inventory_covers_fields_components_and_decisions(self):
        fixtures = evidence._fixtures()
        for config in evidence.CONFIGS:
            annotations = {row["case_id"]: row for row in fixtures["annotations"][config]}
            for cid, spec in fixtures["outputs"][config].items():
                with self.subTest(config=config, case=cid):
                    row = spec["quality"]
                    claims = row["claims"]
                    for key, value in row["fields"].items():
                        self.assertEqual(claims["field-" + key]["text"], value)
                    for key in ("category", "recommendation"):
                        self.assertEqual(claims[key]["text"], row[key])
                    self.assertEqual(claims["rationale"]["text"], row["components"]["rationale"])
                    annotation = annotations[cid]
                    self.assertEqual(set(annotation["claim_critical_fabrication"]), set(claims))
                    self.assertEqual(set(annotation["claim_needs_citation"]), set(claims))
                    if cid == "demo-change-mind-unknown":
                        self.assertIsNone(annotation["claim_inventory_complete"])
                        self.assertTrue(all(value is None for value in annotation["claim_critical_fabrication"].values()))
                    else:
                        self.assertTrue(annotation["claim_inventory_complete"])

    def test_failure_after_retained_success_never_credits_quality(self):
        original = evidence._FixtureAdapter

        class FailAfterOutput(original):
            async def __call__(self, invocation):
                reply = await super().__call__(invocation)
                if invocation.case_id == "demo-faulty-supported":
                    raise RuntimeError("DO_NOT_LEAK_RAW_EXCEPTION_OR_CREDENTIALS")
                return reply

        with patch.object(evidence, "_FixtureAdapter", FailAfterOutput):
            files = build_fixture_evidence()
        for config in evidence.CONFIGS:
            quality = self.loaded("quality-evidence.json", files)["runs"][config]
            self.assertEqual(quality["observations"][0]["status"], "FAILED")
            self.assertFalse(quality["bindings"][0]["quality_selected"])
            self.assertIsNotNone(quality["bindings"][0]["retained"])
        self.assertNotIn(b"DO_NOT_LEAK_RAW_EXCEPTION", b"".join(files.values()))

    def test_changed_risk_projection_loses_companion_binding(self):
        original = evidence._FixtureAdapter

        class ChangedRisk(original):
            async def __call__(self, invocation):
                reply = await super().__call__(invocation)
                if invocation.case_id == "demo-faulty-supported":
                    reply["present_field_ids"].append("unbound-field")
                return reply

        with patch.object(evidence, "_FixtureAdapter", ChangedRisk):
            files = build_fixture_evidence()
        for config in evidence.CONFIGS:
            row = self.loaded("quality-evidence.json", files)["runs"][config]
            self.assertEqual(row["observations"][0], {"case_id": "demo-faulty-supported"})
            self.assertFalse(row["bindings"][0]["same_invocation_binding_valid"])

    def test_b1_retrieval_injection_is_invalid_not_quality_success(self):
        original = evidence._FixtureAdapter

        class ForbiddenRetrieval(original):
            async def __call__(self, invocation):
                reply = await super().__call__(invocation)
                if invocation.configuration == evidence.CONFIGS[0] and invocation.case_id == "demo-faulty-supported":
                    reply["retrieved_passage_ids"] = ["unexpected-passage"]
                return reply

        with patch.object(evidence, "_FixtureAdapter", ForbiddenRetrieval):
            files = build_fixture_evidence()
        self.assertEqual(self.loaded("b1.raw.json", files)["case_results"][0]["disposition"], "INVALID")
        self.assertEqual(self.loaded("quality-evidence.json", files)["runs"][evidence.CONFIGS[0]]["observations"][0],
                         {"case_id": "demo-faulty-supported"})

    def test_paired_supplied_bytes_replay_and_match_actual_runner_rows(self):
        pairs = decode_bytes(self.loaded("paired-inputs.json")["runs"])
        report = validate_stub_pair(data_role=evidence.DATA_ROLE, b1=pairs[evidence.CONFIGS[0]], b4=pairs[evidence.CONFIGS[1]])
        self.assertEqual(report, self.loaded("summaries.json")["paired_integrity"])
        for config, filename in zip(evidence.CONFIGS, ("b1.raw.json", "b4.raw.json")):
            for paired, actual in zip(pairs[config]["results"], self.loaded(filename)["observations"], strict=True):
                self.assertEqual(json.loads(paired["raw_output"]), actual)
                self.assertEqual(paired["raw_output_sha256"], sha256(paired["raw_output"]).hexdigest())
        self.assertFalse(report["actual_execution_proven"])
        self.assertFalse(report["blind_protocol_proven"])

    def test_latency_is_declared_fixture_and_not_runtime_stopwatch(self):
        fixture = self.loaded("latency-fixtures.json")
        self.assertEqual(fixture["latency_origin"], "DECLARED_SYNTHETIC_EVENT_FIXTURE_NOT_OBSERVED_RUNTIME")
        for config in evidence.CONFIGS:
            rows = fixture["accounted_events_by_runner_disposition"][config]
            self.assertEqual(rows[0]["stored_review_ready_at"], "2026-01-01T00:00:20Z")
            self.assertEqual(rows[2]["status"], "FAILED")
            self.assertEqual(rows[4], {"case_id": "demo-malformed-output"})

    @UNIX_PUBLICATION
    def test_exact_source_bytes_commit_and_dirty_transparency_without_private_paths(self):
        source = evidence._source_identity()
        actual_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, capture_output=True,
                                     text=True, check=True).stdout.strip()
        self.assertEqual(source["head_commit"], actual_head)
        for name, record in source["files"].items():
            self.assertEqual(record["sha256"], sha256((self.root / name).read_bytes()).hexdigest())
            self.assertEqual(record["matches_head"], record["sha256"] == record["head_sha256"])
        self.assertEqual(source["relevant_sources_match_head"], all(r["matches_head"] for r in source["files"].values()))
        raw = evidence._json(source)
        self.assertNotIn(str(self.root).encode(), raw)
        self.assertNotIn(str(Path.home()).encode(), raw)

    def test_source_change_during_run_refuses_bundle(self):
        source = self.loaded("source-manifest.json")
        changed = deepcopy(source)
        changed["head_commit"] = "b" * 40
        with patch.object(evidence, "_source_identity", side_effect=[source, changed]):
            with self.assertRaisesRegex(evidence.EvidenceError, "SOURCE_CHANGED_DURING_REHEARSAL"):
                asyncio.run(evidence.build_demo_evidence())

    def test_comparison_artifacts_repeat_exactly_and_manifest_covers_each_file(self):
        again = build_fixture_evidence()
        self.assertEqual(again, self.files)
        manifest = self.loaded("manifest.json")
        self.assertEqual(set(manifest["files"]), set(self.files) - {"manifest.json"})
        for name, record in manifest["files"].items():
            self.assertEqual(record, {"sha256": sha256(self.files[name]).hexdigest(), "byte_count": len(self.files[name])})
        content_id = manifest.pop("content_id")
        self.assertEqual(content_id, sha256(evidence._json(manifest)).hexdigest())

    @UNIX_PUBLICATION
    def test_real_cli_without_site_packages_writes_private_complete_bundle(self):
        result = self.run_cli(self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["file_count"], 13)
        self.assertEqual(set(p.name for p in self.output.iterdir()), set(self.files) | {"creation.json", "index.json"})
        actual_files = asyncio.run(evidence.build_demo_evidence())
        for name, expected in actual_files.items():
            self.assertEqual((self.output / name).read_bytes(), expected)
        all_bytes = b"\n".join(path.read_bytes() for path in self.output.iterdir())
        self.assertNotIn(str(self.root).encode(), all_bytes)
        self.assertNotIn(str(Path.home()).encode(), all_bytes)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        index = json.loads((self.output / "index.json").read_bytes())
        for name, record in index["files"].items():
            raw = (self.output / name).read_bytes()
            self.assertEqual(record, {"sha256": sha256(raw).hexdigest(), "byte_count": len(raw)})
            self.assertEqual(stat.S_IMODE((self.output / name).stat().st_mode), 0o600)
        creation = json.loads((self.output / "creation.json").read_bytes())
        self.assertTrue(creation["timestamp_is_not_a_seal"])
        self.assertTrue(index["creation_excluded_from_reproducible_content_id"])

    @UNIX_PUBLICATION
    def test_existing_paths_including_empty_directory_and_symlink_are_preserved(self):
        protected = self.parent / "protected"
        protected.write_bytes(b"original")
        targets = [self.parent / name for name in ("file", "empty-dir", "nonempty-dir", "link", "dangling")]
        targets[0].write_bytes(b"keep")
        targets[1].mkdir()
        targets[2].mkdir()
        (targets[2] / "keep").write_bytes(b"keep")
        targets[3].symlink_to(protected)
        targets[4].symlink_to(self.parent / "absent")
        for target in targets:
            with self.subTest(target=target.name), self.assertRaises(evidence.EvidenceError):
                evidence.publish_demo_evidence(target, self.files)
        self.assertEqual(protected.read_bytes(), b"original")
        self.assertEqual(targets[0].read_bytes(), b"keep")
        self.assertEqual(list(targets[1].iterdir()), [])
        self.assertEqual((targets[2] / "keep").read_bytes(), b"keep")
        self.assertTrue(targets[3].is_symlink())
        self.assertTrue(targets[4].is_symlink())
        self.assertFalse(list(self.parent.glob(".returnops-evidence-*")))

    @UNIX_PUBLICATION
    def test_symlink_parent_dotdot_and_missing_parent_are_rejected(self):
        linked = self.parent / "linked"
        linked.symlink_to(self.parent, target_is_directory=True)
        for output in (linked / "output", self.parent / ".." / "output", self.parent / "missing" / "output"):
            with self.subTest(output=str(output)), self.assertRaises((evidence.EvidenceError, OSError)):
                evidence.publish_demo_evidence(output, self.files)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.parent.glob(".returnops-evidence-*")))

    @UNIX_PUBLICATION
    def test_racing_destination_is_never_overwritten_and_stage_removed(self):
        original = evidence._rename_no_replace

        def destination_appears(parent_fd, stage, target):
            os.mkdir(target, dir_fd=parent_fd)
            original(parent_fd, stage, target)

        with patch.object(evidence, "_rename_no_replace", destination_appears):
            with self.assertRaises(evidence.EvidenceError):
                evidence.publish_demo_evidence(self.output, self.files)
        self.assertTrue(self.output.is_dir())
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(list(self.parent.glob(".returnops-evidence-*")))

    @UNIX_PUBLICATION
    def test_write_failure_publishes_nothing_and_cleans_only_owned_stage(self):
        preserved = self.parent / "preserved"
        preserved.write_bytes(b"unchanged")
        with patch.object(evidence.os, "fsync", side_effect=OSError("synthetic write failure")):
            with self.assertRaises(OSError):
                evidence.publish_demo_evidence(self.output, self.files)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.parent.glob(".returnops-evidence-*")))
        self.assertEqual(preserved.read_bytes(), b"unchanged")

    @UNIX_PUBLICATION
    def test_stage_open_failure_removes_new_empty_stage(self):
        original = evidence.os.open

        def cannot_open_stage(path, *args, **kwargs):
            if isinstance(path, str) and path.startswith(".returnops-evidence-"):
                raise OSError("invented stage open failure")
            return original(path, *args, **kwargs)

        with patch.object(evidence.os, "open", cannot_open_stage):
            with self.assertRaises(OSError):
                evidence.publish_demo_evidence(self.output, self.files)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.parent.glob(".returnops-evidence-*")))

    @UNIX_PUBLICATION
    def test_cli_nonoverwrite_is_nonzero_and_sanitized(self):
        self.output.mkdir()
        result = self.run_cli(self.output)
        self.assertEqual(result.returncode, 1)
        self.assertIn("no existing destination was overwritten", result.stderr)
        self.assertNotIn(str(self.parent), result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(list(self.output.iterdir()), [])

    @UNIX_PUBLICATION
    def test_output_filename_traversal_or_oversize_never_writes(self):
        files = dict(self.files)
        files["../other"] = b"invalid"
        with self.assertRaises(evidence.EvidenceError):
            evidence.publish_demo_evidence(self.output, files)
        files = dict(self.files)
        files["inputs.json"] = b"x" * (evidence._LIMIT + 1)
        with self.assertRaises(evidence.EvidenceError):
            evidence.publish_demo_evidence(self.output, files)
        self.assertFalse(self.output.exists())


class EvaluationEvidencePlatformTests(unittest.TestCase):
    def fake_os(self):
        operations = ("open", "mkdir", "stat", "unlink", "rmdir", "close", "fdopen", "fsync", "fstat")
        return SimpleNamespace(name="posix", O_DIRECTORY=1, O_NOFOLLOW=2,
            supports_dir_fd=[SimpleNamespace(__name__=name) for name in ("open", "mkdir", "stat", "unlink", "rmdir")],
            supports_follow_symlinks=[SimpleNamespace(__name__="stat")],
            **{name: Mock(side_effect=AssertionError("I/O must not occur")) for name in operations})

    def assert_refused_without_io(self, fake, platform="linux", expected="EVIDENCE_PLATFORM_UNSUPPORTED",
                                  library=None, load_error=None):
        out, err = io.StringIO(), io.StringIO()
        with (patch.object(evidence, "os", fake), patch.object(evidence.sys, "platform", platform),
              patch.object(evidence.ctypes, "CDLL", return_value=library, side_effect=load_error) as load,
              patch.object(evidence, "build_demo_evidence") as build,
              patch.object(evidence, "_source_identity") as source,
              patch.object(evidence, "_open_parent") as parent,
              redirect_stdout(out), redirect_stderr(err)):
            self.assertEqual(evidence.main(["--output-dir", "PRIVATE_DESTINATION"]), 1)
            with self.assertRaisesRegex(evidence.EvidencePlatformError, "^" + expected + "$"):
                evidence.publish_demo_evidence("PRIVATE_DESTINATION", {})
            build.assert_not_called()
            source.assert_not_called()
            parent.assert_not_called()
            if expected == "EVIDENCE_PLATFORM_UNSUPPORTED":
                load.assert_not_called()
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), expected + "\n")
        for value in vars(fake).values():
            if isinstance(value, Mock):
                value.assert_not_called()

    def test_windows_boundary_refuses_before_git_build_or_publication(self):
        fake = self.fake_os()
        fake.name = "nt"
        self.assert_refused_without_io(fake, platform="win32")

    def test_missing_publication_flags_or_capabilities_fail_closed(self):
        for name in ("O_DIRECTORY", "O_NOFOLLOW", "supports_dir_fd", "supports_follow_symlinks", "fsync"):
            fake = self.fake_os()
            with patch.object(evidence, "os", fake), patch.object(evidence.sys, "platform", "linux"):
                self.assertTrue(evidence._publication_io_supported())
            delattr(fake, name)
            with self.subTest(missing=name):
                self.assert_refused_without_io(fake)
        for name, value in (("O_NOFOLLOW", 0), ("O_DIRECTORY", True), ("supports_dir_fd", []),
                            ("supports_follow_symlinks", [])):
            fake = self.fake_os()
            setattr(fake, name, value)
            with self.subTest(capability=name, value=value):
                self.assert_refused_without_io(fake)

    def test_absent_native_atomic_primitive_fails_before_any_source_or_output_io(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                self.assert_refused_without_io(self.fake_os(), platform=platform,
                    expected="ATOMIC_PUBLICATION_UNSUPPORTED", library=SimpleNamespace())
        self.assert_refused_without_io(self.fake_os(), expected="ATOMIC_PUBLICATION_UNSUPPORTED",
                                      load_error=OSError("PRIVATE_LOADER_PATH"))

    def test_fixture_pipeline_remains_portable_without_publication_or_git(self):
        fake = self.fake_os()
        fake.name = "nt"
        with patch.object(evidence, "os", fake), patch.object(evidence, "_git") as git:
            files = build_fixture_evidence()
            git.assert_not_called()
        summary = json.loads(files["summaries.json"])
        self.assertEqual(summary["runs"][evidence.CONFIGS[0]]["risk"]["dispositions"]["FAILED"], 1)
        self.assertFalse(summary["formal_performance_claim"])


if __name__ == "__main__":
    unittest.main()
