"""Public invented times; no human, Gold, sealing or session evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Inexact, InvalidOperation, ROUND_DOWN, ROUND_UP, Rounded, localcontext
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
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from experiments.evaluation_candidate import human_timing
from experiments.evaluation_candidate.human_timing import (
    PRIVATE_ROLE, SYNTHETIC_ROLE, main, summarize_human_timing,
)


def stamp(seconds=0):
    return (datetime(2026, 10, 17, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def record(operator, case_id, position, start, end):
    return {"operator": operator, "case_id": case_id, "position": position, "status": "COMPLETED",
            "started_at": stamp(start), "ended_at": stamp(end), "pauses": []}


def fixture():
    return {"data_role": SYNTHETIC_ROLE,
            "input_pin": {"version": "invented-input-v1", "sha256": "1" * 64},
            "corpus_pin": {"version": "invented-corpus-v1", "sha256": "2" * 64},
            "expected_case_ids": ["a", "b"], "orders": {"A": ["a", "b"], "B": ["b", "a"]},
            "records": [record("A", "a", 1, 0, 10), record("A", "b", 2, 10, 30),
                        record("B", "b", 1, 0, 30), record("B", "a", 2, 30, 70)]}


def pause(start, end, kind="CUSTOMER_WAIT", reason="Invented external wait"):
    return {"kind": kind, "start_at": stamp(start), "end_at": stamp(end), "reason": reason}


def summarize(manifest=None):
    return summarize_human_timing(fixture() if manifest is None else manifest)


class HumanTimingTests(unittest.TestCase):
    def test_bundled_public_example_matches_documented_statistics_without_mutation(self):
        source = Path(__file__).resolve().parents[2] / "experiments/evaluation_candidate/data/human_timing_example.json"
        original_bytes = source.read_bytes()
        data = json.loads(original_bytes)
        original_data = deepcopy(data)
        result = summarize_human_timing(data)
        self.assertEqual(result["data_role"], SYNTHETIC_ROLE)
        self.assertEqual(result["operators"]["A"]["median_seconds"], 120)
        self.assertEqual(result["operators"]["A"]["iqr_seconds"], 60)
        self.assertEqual(result["operators"]["B"]["median_seconds"], 150)
        self.assertEqual(result["operators"]["B"]["iqr_seconds"], 60)
        for key, expected in (("median_seconds", 135), ("q1_seconds", 97.5),
                              ("q3_seconds", 172.5), ("iqr_seconds", 75)):
            self.assertEqual(result["pooled"][key], expected)
        self.assertEqual(result["pooled"]["sample_coverage"], {"numerator": 6, "denominator": 6, "value": 1})
        for key in ("human_participation_verified", "blindness_verified", "sealing_verified",
                    "formal_performance_claim", "target_acceptance_assessed"):
            self.assertFalse(result[key])
        self.assertEqual(data, original_data)
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_per_operator_and_pooled_type7_statistics(self):
        result = summarize()
        self.assertEqual(result["operators"]["A"]["median_seconds"], 15)
        self.assertEqual(result["operators"]["B"]["median_seconds"], 35)
        self.assertEqual(result["pooled"]["median_seconds"], 25)
        self.assertEqual(result["pooled"]["q1_seconds"], 17.5)
        self.assertEqual(result["pooled"]["q3_seconds"], 32.5)
        self.assertEqual(result["pooled"]["iqr_seconds"], 15)
        self.assertEqual(result["pooled"]["sample_coverage"], {"numerator": 4, "denominator": 4, "value": 1})
        self.assertTrue(result["run_structure_valid"])
        for key in ("human_participation_verified", "blindness_verified", "sealing_verified",
                    "formal_performance_claim", "target_acceptance_assessed"):
            self.assertFalse(result[key])

    def test_overlapping_adjacent_nested_and_zero_pauses_subtract_union_once(self):
        data = fixture()
        data["records"][0]["pauses"] = [pause(1, 4), pause(3, 6, "PROVIDER_WAIT"),
                                        pause(6, 8, "FOUNDER_WAIT"), pause(2, 2, "PHYSICAL_WAIT"), pause(1, 4)]
        case = summarize(data)["operators"]["A"]["per_case"][0]
        self.assertEqual(case["active_seconds"], 3)
        self.assertEqual(case["wall_seconds"], 10)
        self.assertEqual(case["excluded_pause_seconds"], 7)

    def test_reading_thinking_writing_break_and_generic_human_cannot_be_paused(self):
        for kind in ("READING", "THINKING", "WRITING", "CHECKING", "BREAK", "HUMAN", "MODEL", "NETWORK", True, []):
            data = fixture()
            data["records"][0]["pauses"] = [pause(1, 2, kind)]
            with self.subTest(kind=kind):
                self.assertEqual(summarize(data)["operators"]["A"]["dispositions"]["INVALID"], 1)

    def test_pause_reasons_and_bounds_are_required_and_not_echoed(self):
        for invalid in (pause(-1, 2), pause(8, 11), pause(3, 2), pause(1, 2, reason=" "),
                        pause(1, 2, reason="x" * 501), {**pause(1, 2), "active_seconds": 1}):
            data = fixture()
            data["records"][0]["pauses"] = [invalid]
            self.assertEqual(summarize(data)["operators"]["A"]["dispositions"]["INVALID"], 1)
        data = fixture()
        data["records"][0]["pauses"] = [pause(1, 2, reason="PRIVATE_REASON_DO_NOT_ECHO")]
        self.assertNotIn("PRIVATE_REASON_DO_NOT_ECHO", json.dumps(summarize(data)))

    def test_same_operator_overlap_invalidates_both_even_inside_pause(self):
        data = fixture()
        data["records"][1].update(started_at=stamp(5), ended_at=stamp(15))
        data["records"][0]["pauses"] = [pause(0, 10)]
        result = summarize(data)
        self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 2)
        self.assertEqual(result["operators"]["B"]["dispositions"]["COMPLETED"], 2)
        self.assertEqual(result["operators"]["A"]["per_case"][0]["conflicts"], ["CROSS_CASE_OVERLAP"])
        self.assertIsNone(result["operators"]["A"]["median_seconds"])

    def test_chronologically_reversed_frozen_order_invalidates_both(self):
        data = fixture()
        data["records"][0].update(started_at=stamp(40), ended_at=stamp(50))
        result = summarize(data)
        self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 2)
        self.assertEqual(result["operators"]["A"]["per_case"][0]["conflicts"], ["FROZEN_ORDER_VIOLATION"])

    def test_cross_operator_overlap_and_touching_endpoints_are_valid(self):
        result = summarize()
        self.assertEqual(result["pooled"]["sample_count"], 4)
        self.assertFalse(any(case["conflicts"] for case in result["operators"]["A"]["per_case"]))

    def test_duplicate_and_extra_timed_rows_cannot_hide_overlap(self):
        data = fixture()
        data["records"].append(record("A", "a", 1, 15, 25))
        result = summarize(data)
        self.assertEqual(result["operators"]["A"]["dispositions"]["DUPLICATE"], 1)
        self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 1)
        data = fixture()
        data["records"].append(record("A", "extra", 1, 5, 6))
        result = summarize(data)
        self.assertEqual(result["extra_records"], [{"operator": "A", "case_id": "extra", "row_count": 1}])
        self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 1)
        self.assertFalse(result["run_structure_valid"])

    def test_missing_failed_invalid_and_duplicates_remain_in_full_denominator(self):
        data = fixture()
        data["records"] = [data["records"][0], data["records"][0], {"operator": "A", "case_id": "b"},
                           {**data["records"][2], "status": "FAILED", "started_at": None, "ended_at": None}]
        result = summarize(data)
        self.assertEqual(result["pooled"]["sample_coverage"], {"numerator": 0, "denominator": 4, "value": 0})
        self.assertEqual(result["operators"]["A"]["dispositions"]["DUPLICATE"], 1)
        self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 1)
        self.assertEqual(result["operators"]["B"]["dispositions"]["FAILED"], 1)
        self.assertEqual(result["operators"]["B"]["dispositions"]["MISSING"], 1)
        self.assertIsNone(result["pooled"]["median_seconds"])

    def test_failed_partial_time_is_retained_but_is_not_a_completed_sample(self):
        data = fixture()
        data["records"][0]["status"] = "FAILED"
        result = summarize(data)
        case = result["operators"]["A"]["per_case"][0]
        self.assertEqual(case["active_seconds"], 10)
        self.assertFalse(case["included_in_completed_statistics"])
        self.assertEqual(result["operators"]["A"]["median_seconds"], 20)
        self.assertEqual(result["pooled"]["sample_count"], 3)

    def test_no_records_and_single_sample_have_null_or_conditional_quartiles(self):
        data = fixture()
        data["records"] = []
        result = summarize(data)
        for key in ("median_seconds", "q1_seconds", "q3_seconds", "iqr_seconds"):
            self.assertIsNone(result["pooled"][key])
        data["records"] = [record("A", "a", 1, 0, 10)]
        result = summarize(data)
        self.assertEqual(result["pooled"]["median_seconds"], 10)
        self.assertEqual(result["pooled"]["q1_seconds"], 10)
        self.assertEqual(result["pooled"]["q3_seconds"], 10)
        self.assertEqual(result["pooled"]["iqr_seconds"], 0)
        self.assertEqual(result["pooled"]["sample_coverage"]["value"], .25)

    def test_microsecond_rounding_is_independent_of_decimal_context(self):
        data = fixture()
        data["records"] = [record("A", "a", 1, 0, 0), record("A", "b", 2, 1, 1.000001)]
        for rounding in (ROUND_UP, ROUND_DOWN):
            for precision in (1, 3, 50):
                with self.subTest(rounding=rounding, precision=precision), localcontext() as context:
                    context.rounding, context.prec = rounding, precision
                    for signal in (Inexact, Rounded, InvalidOperation):
                        context.traps[signal] = True
                    result = summarize(data)["operators"]["A"]
                    self.assertEqual(result["median_seconds"], 0)
                    self.assertEqual(result["q1_seconds"], 0)
                    self.assertEqual(result["q3_seconds"], .000001)
                    self.assertEqual(result["iqr_seconds"], 0)  # exact 0.5 microseconds rounds half-even

    def test_pins_roles_fixed_subset_and_distinct_orders_are_validated(self):
        mutations = [lambda data: data.update(data_role="GOLD"),
                     lambda data: data.update(expected_case_ids=[]),
                     lambda data: data.update(expected_case_ids=["a"]),
                     lambda data: data.update(expected_case_ids=["a", "a"]),
                     lambda data: data["orders"].update(B=["a", "b"]),
                     lambda data: data["orders"].update(B=["b", "x"]),
                     lambda data: data["orders"].update(B=["b", "a", "a"]),
                     lambda data: data["input_pin"].update(sha256="not-a-hash"),
                     lambda data: data["corpus_pin"].update(version=""),
                     lambda data: data.update(gold_labels={"secret": "not accepted"})]
        for mutate in mutations:
            data = fixture()
            mutate(data)
            with self.assertRaises(ValueError):
                summarize(data)

    def test_private_role_reports_math_without_certifying_real_participation(self):
        data = fixture()
        data["data_role"] = PRIVATE_ROLE
        result = summarize(data)
        self.assertEqual(result["data_role"], PRIVATE_ROLE)
        self.assertEqual(result["pooled"]["sample_count"], 4)
        self.assertFalse(result["human_participation_verified"])
        self.assertFalse(result["blindness_verified"])
        self.assertFalse(result["sealing_verified"])

    def test_invalid_time_shape_position_supplied_duration_or_answer_is_not_scored(self):
        changes = [("started_at", True), ("ended_at", stamp(-1)), ("position", True), ("position", 2),
                   ("started_at", "2026-10-17T00:00:00+00:00"), ("started_at", "2026-02-30T00:00:00Z"),
                   ("started_at", "2026-10-17T00:00:00.1234567Z"),
                   ("ended_at", stamp(86401)), ("active_seconds", 0), ("answer", "PRIVATE_ANSWER")]
        for key, value in changes:
            data = fixture()
            data["records"][0][key] = value
            with self.subTest(key=key, value=value):
                result = summarize(data)
                self.assertEqual(result["operators"]["A"]["dispositions"]["INVALID"], 1)
                self.assertNotIn("PRIVATE_ANSWER", json.dumps(result))

    def test_failed_shape_may_not_have_single_endpoint_or_null_with_pause(self):
        for changes in ({"started_at": None}, {"ended_at": None},
                        {"started_at": None, "ended_at": None, "pauses": [pause(1, 2)]}):
            data = fixture()
            data["records"][0].update(status="FAILED", **changes)
            self.assertEqual(summarize(data)["operators"]["A"]["dispositions"]["INVALID"], 1)

    def test_unidentifiable_and_unknown_operator_rows_are_reported(self):
        data = fixture()
        data["records"] += [None, {"operator": "C", "case_id": "a"}, {"operator": "A", "case_id": ""}]
        result = summarize(data)
        self.assertEqual(result["unidentifiable_row_count"], 3)
        self.assertFalse(result["run_structure_valid"])

    def test_capacity_nonfinite_and_non_json_values_rejected(self):
        for mutate in (lambda data: data.update(records=[data["records"][0]] * 401),
                       lambda data: data.update(expected_case_ids=[str(i) for i in range(101)]),
                       lambda data: data["records"][0].update(started_at=float("nan")),
                       lambda data: data["records"][0].update(started_at=float("inf")),
                       lambda data: data["records"][0].update(started_at=object()),
                       lambda data: data["input_pin"].update(version="x" * (2 * 1024 * 1024))):
            data = fixture()
            mutate(data)
            with self.assertRaises(ValueError):
                summarize(data)
        data = fixture()
        data["records"][0]["pauses"] = [pause(1, 2)] * 101
        self.assertEqual(summarize(data)["operators"]["A"]["dispositions"]["INVALID"], 1)

    def test_input_objects_unchanged_and_storage_order_does_not_select_winners(self):
        data = fixture()
        before = deepcopy(data)
        result = summarize(data)
        self.assertEqual(data, before)
        data["records"].reverse()
        reversed_result = summarize(data)
        self.assertEqual(result["operators"], reversed_result["operators"])
        self.assertEqual(result["pooled"], reversed_result["pooled"])
        self.assertNotEqual(result["manifest_sha256"], reversed_result["manifest_sha256"])


@unittest.skipUnless(human_timing._file_io_supported(), "Requires protected POSIX file I/O")
class HumanTimingCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="returnops-human-timing-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.destination = self.root / "input.json", self.root / "new-report.json"

    def invoke(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--input", str(self.source), "--output", str(self.destination)])
        return code, out.getvalue(), err.getvalue()

    def write_input(self, data=None):
        self.source.write_text(json.dumps(fixture() if data is None else data), encoding="utf-8")

    def test_cli_import_creates_private_report_without_echoing_content(self):
        self.write_input()
        code, out, err = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        report = json.loads(self.destination.read_text(encoding="utf-8"))
        self.assertEqual(report["pooled"]["median_seconds"], 25)
        self.assertEqual(len(report["imported_file_sha256"]), 64)
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o600)
        self.assertNotIn("invented-input", out)
        self.assertNotIn(str(self.source), out)

    def test_existing_report_or_input_is_never_overwritten(self):
        self.write_input()
        self.destination.write_text("preserve", encoding="utf-8")
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.destination.read_text(), "preserve")
        self.destination = self.source
        original = self.source.read_bytes()
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.source.read_bytes(), original)

    def test_symlink_input_and_output_are_rejected_without_touching_targets(self):
        real = self.root / "real.json"
        real.write_text(json.dumps(fixture()), encoding="utf-8")
        self.source.symlink_to(real)
        self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.destination.exists())
        self.source.unlink()
        self.write_input()
        self.destination.symlink_to(real)
        before = real.read_bytes()
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(real.read_bytes(), before)

    def test_nonregular_directory_missing_and_oversize_inputs_fail_closed(self):
        self.assertEqual(self.invoke()[0], 2)
        self.source.mkdir()
        self.assertEqual(self.invoke()[0], 2)
        self.source.rmdir()
        self.source.write_bytes(b" " * (2 * 1024 * 1024 + 1))
        self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.destination.exists())

    @unittest.skipUnless(callable(getattr(os, "mkfifo", None)), "Requires FIFO creation")
    def test_fifo_input_fails_closed_without_blocking(self):
        os.mkfifo(self.source)
        self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.destination.exists())

    def test_duplicate_keys_nonfinite_invalid_utf8_and_private_errors_are_sanitized(self):
        bodies = [b'{"data_role":"PRIVATE_SECRET","data_role":"duplicate"}',
                  b'{"secret":NaN}', b'{"secret":Infinity}', b'\xffPRIVATE_SECRET',
                  b'{"PRIVATE_SECRET":', b'[]']
        for body in bodies:
            self.source.write_bytes(body)
            code, out, err = self.invoke()
            self.assertEqual(code, 2)
            self.assertEqual(out, "")
            self.assertEqual(err, "HUMAN_TIMING_IMPORT_FAILED\n")
            self.assertNotIn("PRIVATE_SECRET", err)
            self.assertFalse(self.destination.exists())

    def test_failed_write_cleans_only_its_own_partial_private_file(self):
        self.write_input()
        with patch("experiments.evaluation_candidate.human_timing.os.fsync", side_effect=OSError("PRIVATE_SECRET")):
            code, out, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertFalse(self.destination.exists())
        self.assertNotIn("PRIVATE_SECRET", err)
        self.assertEqual(out, "")

    def test_module_cli_runs_with_explicit_paths(self):
        self.write_input()
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run([sys.executable, "-B", "-m", "experiments.evaluation_candidate.human_timing",
                                 "--input", str(self.source), "--output", str(self.destination)],
                                cwd=repo, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.destination.exists())


class HumanTimingPlatformTests(unittest.TestCase):
    def fake_os(self):
        # A local namespace, not deletion/patching of process-wide os features.
        return SimpleNamespace(name="posix", O_NONBLOCK=1, O_NOFOLLOW=2,
            **{name: Mock(side_effect=AssertionError("I/O must not occur")) for name in
               ("open", "lstat", "fstat", "fdopen", "fchmod", "fsync")})

    def assert_refused_without_io(self, fake):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(human_timing, "os", fake), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(["--input", "PRIVATE_INPUT", "--output", "PRIVATE_OUTPUT"]), 2)
            for action in (lambda: human_timing._read_input("PRIVATE_INPUT"),
                           lambda: human_timing._write_output("PRIVATE_OUTPUT", {})):
                with self.assertRaisesRegex(human_timing.HumanTimingPlatformError,
                                           "^HUMAN_TIMING_PLATFORM_UNSUPPORTED$"):
                    action()
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "HUMAN_TIMING_PLATFORM_UNSUPPORTED\n")
        for value in vars(fake).values():
            if isinstance(value, Mock):
                value.assert_not_called()

    def test_native_windows_boundary_precedes_any_file_access(self):
        fake = self.fake_os()
        fake.name = "nt"
        self.assert_refused_without_io(fake)

    def test_missing_required_api_or_flag_is_typed_failure_not_attribute_error(self):
        for name in ("O_NONBLOCK", "O_NOFOLLOW", "fchmod", "fsync"):
            fake = self.fake_os()
            with patch.object(human_timing, "os", fake):
                self.assertTrue(human_timing._file_io_supported())
            delattr(fake, name)
            with self.subTest(missing=name):
                self.assert_refused_without_io(fake)
        for value in (0, None, True):
            fake = self.fake_os()
            fake.O_NOFOLLOW = value
            with self.subTest(no_follow=value):
                self.assert_refused_without_io(fake)

    def test_pure_accounting_remains_available_without_unix_file_apis(self):
        expected = summarize()
        with patch.object(human_timing, "os", SimpleNamespace(name="nt")):
            self.assertEqual(summarize(), expected)


if __name__ == "__main__":
    unittest.main()
