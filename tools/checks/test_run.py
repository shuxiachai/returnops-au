"""Runner regressions; subprocesses and database connections are not started."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("returnops_check_runner", Path(__file__).with_name("run.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_stops_after_failed_check_and_preserves_exit_status(self):
        steps = [("one", ["python", "first.py"]), ("two", ["python", "second.py"])]
        with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)) as execute:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.run_steps(steps), 7)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(execute.call_args.args[0], steps[0][1])
        self.assertNotIn("shell", execute.call_args.kwargs)

    def test_missing_tool_is_a_failure(self):
        with patch.object(runner.subprocess, "run", side_effect=FileNotFoundError):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.run_steps([("missing", ["missing"])]), 1)

    def test_database_target_is_explicit_and_errors_do_not_echo_credentials(self):
        base = "postgresql+psycopg://user:private@localhost/"
        prefix = "returnops_f02_"
        invalid_targets = (
            None,
            "",
            "sqlite:///data.db",
            "postgresql://user:private@localhost/returnops_f02",
            "postgresql+psycopg://user:private@localhost",
            "postgresql+psycopg://user:private@localhost/other_database",
            "postgresql+psycopg://user:private@localhost/returnops_f02_bad/other",
            "postgresql+psycopg://user:private@localhost/returnops_f02?dbname=other_database",
            "postgresql+psycopg://user:private@localhost/returnops_f02#override",
            "postgresql+psycopg://localhost/returnops_f02",
            "postgresql+psycopg://user:private@localhost:invalid/returnops_f02",
            base + "returnops_f02?",
            base + "returnops_f02#",
            base + "returnops_f02_CI",
            base + "returnops_f02_é",
            base + prefix,
            base + prefix + "a" * (64 - len(prefix)),
        )
        for value in invalid_targets:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as error:
                    runner.validate_database_url(value)
                self.assertNotIn("private", str(error.exception))
        runner.validate_database_url("postgresql+psycopg://ci:synthetic@localhost:5432/returnops_f02_ci")
        runner.validate_database_url("postgresql+psycopg://ci:synthetic@localhost:5432/returnops_f02")
        runner.validate_database_url(base + prefix + "a" * (63 - len(prefix)))
        runner.validate_database_url("postgresql+psycopg://ci:encoded%3F%23@localhost/returnops_f02_ci_1")

    def test_missing_database_target_never_starts_migration(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(runner, "run_steps") as execute:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                runner.main(["environment"])
        self.assertEqual(error.exception.code, 2)
        execute.assert_not_called()

    def test_wbs_baseline_is_one_literal_argument_and_skip_is_explicit(self):
        literal = "refs/heads/example; literal argument"
        steps = runner.build_steps("offline", baseline_ref=literal)
        model = next(command for label, command in steps if label == "document/model references")
        self.assertEqual(model[-2:], ["--baseline-ref", literal])
        skipped = runner.build_steps("offline", skip_baseline=True)
        self.assertIn("--skip-baseline", skipped[1][1])
        self.assertNotIn("--baseline-ref", skipped[1][1])


    def test_offline_selects_the_order_component_alongside_all_existing_groups(self):
        steps = runner.build_steps("offline", baseline_ref="verified-base")
        self.assertEqual([label for label, _ in steps], [
            "contract artifacts", "document/model references", "model-checker regressions",
            "check-runner regressions", "Mermaid grammar", "synthetic order provider",
        ])
        selected = [command for label, command in steps if label == "synthetic order provider"]
        self.assertEqual(selected, [[runner.sys.executable, "-B", "-m", "pytest", "tests/orders", "-q"]])

    def test_environment_selects_investigation_and_founder_after_all_existing_groups(self):
        steps = runner.build_steps("environment")
        self.assertEqual([label for label, _ in steps], [
            "upgrade the configured test database", "report installed migration",
            "API/PostgreSQL environment tests", "initial-record PostgreSQL storage tests",
            "customer HTTP, concurrency and retention tests", "order investigation PostgreSQL and real TCP tests",
            "Founder read PostgreSQL and real TCP tests", "Lifecycle guard PostgreSQL component tests",
        ])
        self.assertEqual(steps[-3][1], [runner.sys.executable, "-B", "-m", "pytest", "tests/investigation", "-q"])
        self.assertEqual(steps[-2][1], [runner.sys.executable, "-B", "-m", "pytest", "tests/founder", "-q"])
        self.assertEqual(steps[-1][1], [runner.sys.executable, "-B", "-m", "pytest", "tests/lifecycle", "-q"])

if __name__ == "__main__":
    unittest.main()
