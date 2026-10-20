"""Runner regressions with controlled dummy subprocesses; no production tests or DB connections."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


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
        self.assertEqual(steps[-1][1], [runner.sys.executable, "-B", "-m", "pytest", "tests/lifecycle", "-q", "--tb=short", "-x", "-p", "tools.checks.lifecycle_progress"])

PROGRESS_SPEC = importlib.util.spec_from_file_location(
    "lifecycle_progress_for_unit_tests", Path(__file__).with_name("lifecycle_progress.py")
)
progress = importlib.util.module_from_spec(PROGRESS_SPEC)
PROGRESS_SPEC.loader.exec_module(progress)


class ProgressUnitTests(unittest.TestCase):
    def test_observation_does_not_change_items_and_emits_only_public_metadata(self):
        from types import SimpleNamespace

        nodes = [SimpleNamespace(nodeid="synthetic.py::test_b[SYNTHETIC_PRIVATE_PARAMETER]"),
                 SimpleNamespace(nodeid="synthetic.py::test_a")]
        session = SimpleNamespace(items=nodes)
        report = SimpleNamespace(
            nodeid=nodes[0].nodeid, when="call", outcome="passed", duration=0.125,
            longrepr="SYNTHETIC_PRIVATE_REPORT", sections=["SYNTHETIC_PRIVATE_SECTION"],
        )
        stream = io.StringIO()
        with patch.object(progress.sys, "__stdout__", stream):
            progress.pytest_sessionstart(session)
            progress.pytest_collection_finish(session)
            progress.pytest_runtest_logstart(nodes[0].nodeid, ("private-location", 0, "private"))
            progress.pytest_runtest_logreport(report)
            progress.pytest_runtest_logfinish(nodes[0].nodeid, None)
        self.assertIs(session.items, nodes)
        self.assertEqual([item.nodeid for item in nodes],
                         ["synthetic.py::test_b[SYNTHETIC_PRIVATE_PARAMETER]", "synthetic.py::test_a"])
        records = [json.loads(line[len(progress.PREFIX):])
                   for line in stream.getvalue().splitlines() if line.startswith(progress.PREFIX)]
        self.assertEqual([r["nodeid_sha256"] for r in records if r["event"] == "collection_node"],
                         [hashlib.sha256(item.nodeid.encode("utf-8")).hexdigest() for item in nodes])
        phase = next(r for r in records if r["event"] == "phase_end")
        self.assertEqual(set(phase), {
            "format", "event", "pid", "monotonic_seconds", "nodeid",
            "nodeid_sha256", "parameter_id_sha256", "phase", "outcome", "duration_seconds",
        })
        self.assertEqual(phase["duration_seconds"], 0.125)
        self.assertNotIn("PRIVATE", stream.getvalue())
        self.assertNotIn("private-location", stream.getvalue())

    def test_broken_output_cannot_replace_test_result_or_swallow_interrupt(self):
        stream = unittest.mock.Mock()
        stream.write.side_effect = BrokenPipeError("SYNTHETIC_PRIVATE_ERROR")
        with patch.object(progress.sys, "__stdout__", stream):
            progress._emit("synthetic")
        stream.write.side_effect = KeyboardInterrupt
        with patch.object(progress.sys, "__stdout__", stream), self.assertRaises(KeyboardInterrupt):
            progress._emit("synthetic")

    def test_only_lifecycle_command_adds_observer(self):
        commands = [command for _, command in runner.build_steps("environment")]
        self.assertTrue(all("tools.checks.lifecycle_progress" not in cmd for cmd in commands[:-1]))
        self.assertEqual(commands[-1][-6:], [
            "tests/lifecycle", "-q", "--tb=short", "-x", "-p",
            "tools.checks.lifecycle_progress",
        ])


# This child starts with -I -B -S. Only an explicit dependency directory and
# this checkout are added; .pth files and third-party pytest autoload are off.
# It never discovers or imports production tests. Audit guards reject database
# imports, network connections, additional children, and writes outside its own
# synthetic case directory. Guard attempts are reported even if caught.
DUMMY_BOOTSTRAP = r'''
import importlib.abc
import json
import os
from pathlib import Path
import sys

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(config["case_root"]).resolve()
attempts = []

def deny(kind, event=None, requested=None, resolved=None):
    record = {"kind": kind}
    if event is not None:
        record["event"] = event
    if requested is not None:
        record["requested_path"] = os.fsdecode(requested)[:1024]
    if resolved is not None:
        record["resolved_path"] = str(resolved)[:1024]
    attempts.append(record)
    raise RuntimeError("Synthetic diagnostic guard blocked " + kind)

def in_root(value, event):
    if isinstance(value, (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(value)).resolve()
        if not path.is_relative_to(root):
            deny("outside_write", event, value, path)

def audit(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "sqlite3.connect"}:
        deny("connection")
    if event in {"subprocess.Popen", "os.system", "os.fork", "os.exec", "os.posix_spawn"}:
        deny("extra_process")
    if event == "open":
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            in_root(args[0], event)
    if event in {"os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"}:
        in_root(args[0], event)
    if event in {"os.rename", "os.link", "os.symlink"}:
        in_root(args[0], event)
        in_root(args[1], event)

class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("returnops_") or fullname.split(".")[0] in {
            "psycopg", "psycopg2", "sqlalchemy", "alembic", "sqlite3"
        }:
            deny("database_or_production_import")
        return None

sys.addaudithook(audit)
sys.meta_path.insert(0, ImportGuard())
sys.path[:0] = [config["candidate_root"], config["dependency_directory"]]
import pytest
import platform
platform.node = lambda: "returnops-synthetic-dummy"
code = pytest.main(config["pytest_args"])
loaded_production = [name for name in sys.modules if name.startswith("returnops_")]
receipt = {
    "pytest_version": pytest.__version__,
    "exitcode": int(code),
    "guard_attempts": attempts,
    "loaded_production_modules": loaded_production,
    "bytecode_disabled": sys.dont_write_bytecode,
    "site_disabled": bool(sys.flags.no_site),
}
Path(config["receipt"]).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
raise SystemExit(code)
'''


DUMMY_HEADER = '''from pathlib import Path
import time
import pytest
ROOT = Path(__file__).parent
def mark(value):
    with (ROOT / "trace.txt").open("a", encoding="utf-8") as stream:
        stream.write(value + "\\n")
'''

DUMMY_CASES = {
    "pass": '''
def test_first():
    mark("first")
    (ROOT / "entered").write_text("entered", encoding="utf-8")
    deadline = time.monotonic() + 10
    while not (ROOT / "release").exists():
        assert time.monotonic() < deadline, "Synthetic release handshake expired"
        time.sleep(0.01)
def test_second():
    mark("second")
''',
    "setup_failure": '''
@pytest.fixture
def broken():
    mark("setup")
    raise RuntimeError("SYNTHETIC_SETUP_FAILURE")
def test_first(broken):
    mark("unreachable_first")
def test_second():
    mark("unreachable_second")
''',
    "call_failure": '''
def test_first():
    mark("first")
def test_second():
    mark("second")
    assert False, "SYNTHETIC_CALL_FAILURE"
def test_third():
    mark("unreachable_third")
''',
    "teardown_failure": '''
@pytest.fixture
def broken():
    mark("setup")
    yield
    mark("teardown")
    raise RuntimeError("SYNTHETIC_TEARDOWN_FAILURE")
def test_first(broken):
    mark("first")
def test_second():
    mark("unreachable_second")
''',
    "setup_skip": '''
@pytest.fixture
def skipped():
    mark("setup")
    pytest.skip("SYNTHETIC_SETUP_SKIP")
def test_first(skipped):
    mark("unreachable_first")
def test_second():
    mark("second")
''',
    "call_skip": '''
def test_first():
    mark("first")
    pytest.skip("SYNTHETIC_CALL_SKIP")
def test_second():
    mark("second")
''',
    "sensitive_parameters": '''
@pytest.mark.parametrize("value", [0, 1], ids=[
    "SYNTHETIC_PRIVATE_BUSINESS_VALUE",
    "postgresql+psycopg://synthetic:DO_NOT_LOG@example.invalid/db",
])
def test_parameter(value):
    mark("parameter_" + str(value))
''',
}


class ProgressDummyProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = Path(__file__).resolve().parents[2]
        configured = os.environ.get("RETURNOPS_DIAGNOSTIC_PYTEST_DEPS")
        if configured:
            cls.dependencies = Path(configured).resolve()
        else:
            spec = importlib.util.find_spec("pytest")
            if spec is None or spec.origin is None:
                raise RuntimeError("An existing pytest dependency directory is required")
            cls.dependencies = Path(spec.origin).resolve().parent.parent
        evidence = os.environ.get("RETURNOPS_DIAGNOSTIC_EVIDENCE_DIR")
        if evidence:
            cls.evidence = Path(evidence).resolve()
            cls.evidence.mkdir(parents=True, exist_ok=True)
        else:
            cls.evidence = Path(tempfile.mkdtemp(prefix="lifecycle-observer-dummy-"))
        cls.sequence = 0

    def run_dummy(self, case, observed):
        self.__class__.sequence += 1
        work = self.evidence / f"{self.sequence:02d}-{case}-{'observed' if observed else 'baseline'}"
        work.mkdir()
        (work / "tmp").mkdir()
        (work / "test_synthetic.py").write_text(DUMMY_HEADER + DUMMY_CASES[case], encoding="utf-8")
        (work / "pytest.ini").write_text("[pytest]\naddopts =\n", encoding="utf-8")
        bootstrap = work / "bootstrap.py"
        bootstrap.write_text(DUMMY_BOOTSTRAP, encoding="utf-8")
        receipt = work / "receipt.json"
        arguments = [
            "-c", str(work / "pytest.ini"), "--rootdir", str(work),
            "--confcutdir", str(work), "--basetemp", str(work / "pytest-tmp"),
            "-p", "no:cacheprovider", "--junitxml", str(work / "junit.xml"),
            "--log-file", str(work / "pytest.log"),
            str(work / "test_synthetic.py"), "-q", "--tb=short", "-x",
        ]
        if observed:
            arguments += ["-p", "tools.checks.lifecycle_progress"]
        config = {
            "case_root": str(work), "candidate_root": str(self.candidate),
            "dependency_directory": str(self.dependencies),
            "pytest_args": arguments, "receipt": str(receipt),
        }
        configuration = work / "configuration.json"
        configuration.write_text(json.dumps(config, indent=2), encoding="utf-8")
        environment = os.environ.copy()
        for key in ("DATABASE_URL", "PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS",
                    "PYTEST_PLUGINS", "PYTEST_DEBUG", "MANUAL_EVIDENCE_DIR", "MANUAL_INSTALLED_DIR"):
            environment.pop(key, None)
        environment.update({
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1", "TEMP": str(work / "tmp"), "TMP": str(work / "tmp"),
        })
        if case == "pass" and not observed:
            (work / "release").write_text("release", encoding="utf-8")
        command = [sys.executable, "-I", "-B", "-S", "-X", "utf8", str(bootstrap), str(configuration)]
        lines, records, reader_errors = [], [], []
        started = threading.Event()
        with (work / "stderr.txt").open("wb") as errors:
            process = subprocess.Popen(command, cwd=work, env=environment, stdout=subprocess.PIPE,
                                       stderr=errors)
            def read_output():
                try:
                    for line in process.stdout:
                        lines.append(line)
                        try:
                            decoded = line.decode("utf-8")
                        except UnicodeDecodeError:
                            reader_errors.append("UnicodeDecodeError")
                            continue
                        if decoded.startswith(progress.PREFIX):
                            record = json.loads(decoded[len(progress.PREFIX):])
                            records.append(record)
                            if record["event"] == "node_start":
                                started.set()
                except Exception as exc:
                    reader_errors.append(type(exc).__name__)
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            start_before_completion = False
            try:
                if case == "pass" and observed:
                    self.assertTrue(started.wait(10), "No flushed node_start received")
                    deadline = time.monotonic() + 10
                    while not (work / "entered").exists() and process.poll() is None:
                        self.assertLess(time.monotonic(), deadline, "Synthetic body did not enter")
                        time.sleep(0.01)
                    self.assertTrue((work / "entered").exists())
                    self.assertIsNone(process.poll(), "Child completed before release")
                    start_before_completion = True
                    (work / "release").write_text("release", encoding="utf-8")
                returncode = process.wait(timeout=30)
            finally:
                # Never kill an unknown child or retry a failed attempt.
                if process.poll() is not None:
                    reader.join(timeout=5)
                    if not reader.is_alive():
                        process.stdout.close()
                (work / "stdout.txt").write_bytes(b"".join(lines))
                (work / "parent-observation.json").write_text(json.dumps({
                    "command": command, "returncode": process.poll(),
                    "start_received_while_child_waited_for_release": start_before_completion,
                    "reader_errors": reader_errors, "reader_alive": reader.is_alive(),
                    "killed": False, "retried": False,
                }, indent=2), encoding="utf-8")
        self.assertFalse(reader.is_alive())
        self.assertEqual(reader_errors, [])
        child = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(child["exitcode"], returncode)
        self.assertEqual(child["guard_attempts"], [])
        self.assertEqual(child["loaded_production_modules"], [])
        self.assertTrue(child["bytecode_disabled"])
        self.assertTrue(child["site_disabled"])
        xml = ET.parse(work / "junit.xml")
        outcomes = [(node.attrib["name"], tuple(child.tag for child in node
                    if child.tag in {"failure", "error", "skipped"}))
                    for node in xml.iter("testcase")]
        trace = (work / "trace.txt").read_text(encoding="utf-8")
        return returncode, outcomes, trace, records

    def assert_same(self, case, expected_exit, failed_phase=None, skip_phase=None):
        baseline = self.run_dummy(case, False)
        observed = self.run_dummy(case, True)
        self.assertEqual(baseline[:3], observed[:3])
        self.assertEqual(observed[0], expected_exit)
        records = observed[3]
        collected = [r["nodeid_sha256"] for r in records if r["event"] == "collection_node"]
        started = [r["nodeid_sha256"] for r in records if r["event"] == "node_start"]
        finished = [r["nodeid_sha256"] for r in records if r["event"] == "node_finish"]
        expected_collected = ["test_synthetic.py::test_first", "test_synthetic.py::test_second"]
        if case == "call_failure":
            expected_collected += ["test_synthetic.py::test_third"]
        if case == "sensitive_parameters":
            expected_collected = [
                "test_synthetic.py::test_parameter[SYNTHETIC_PRIVATE_BUSINESS_VALUE]",
                "test_synthetic.py::test_parameter[postgresql+psycopg://synthetic:DO_NOT_LOG@example.invalid/db]",
            ]
            rendered = json.dumps(records)
            self.assertNotIn("SYNTHETIC_PRIVATE_BUSINESS_VALUE", rendered)
            self.assertNotIn("DO_NOT_LOG", rendered)
            self.assertNotIn("postgresql", rendered)
            for record in records:
                if "nodeid" in record:
                    self.assertTrue(record["nodeid"].startswith("test_synthetic.py::test_parameter["))
                    self.assertRegex(record["parameter_id_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(collected, [hashlib.sha256(node.encode("utf-8")).hexdigest()
                                    for node in expected_collected])
        self.assertEqual(started, [
            hashlib.sha256(("test_synthetic.py::" + name).encode("utf-8")).hexdigest()
            for name, _ in observed[1]
        ])
        self.assertEqual(finished, started)
        self.assertEqual([r["ordinal"] for r in records if r["event"] == "node_start"],
                         list(range(1, len(started) + 1)))
        self.assertEqual([r["count"] for r in records if r["event"] in
                          {"collection_start", "collection_end"}], [len(collected)] * 2)
        phases = [r for r in records if r["event"] == "phase_end"]
        self.assertTrue(all(r["duration_seconds"] >= 0 for r in phases))
        self.assertTrue(all(type(r["pid"]) is int and r["pid"] > 0 for r in records))
        if failed_phase:
            self.assertEqual([(r["phase"], r["outcome"]) for r in phases
                              if r["outcome"] == "failed"], [(failed_phase, "failed")])
        if skip_phase:
            self.assertEqual([(r["phase"], r["outcome"]) for r in phases
                              if r["outcome"] == "skipped"], [(skip_phase, "skipped")])

    def test_pass_and_flushed_start_before_completion(self):
        self.assert_same("pass", 0)

    def test_setup_failure_preserves_exit_and_order(self):
        self.assert_same("setup_failure", 1, failed_phase="setup")

    def test_call_failure_preserves_exit_and_order(self):
        self.assert_same("call_failure", 1, failed_phase="call")

    def test_teardown_failure_preserves_exit_and_order(self):
        self.assert_same("teardown_failure", 1, failed_phase="teardown")

    def test_setup_skip_preserves_exit_and_order(self):
        self.assert_same("setup_skip", 0, skip_phase="setup")

    def test_call_skip_preserves_exit_and_order(self):
        self.assert_same("call_skip", 0, skip_phase="call")

    def test_parameter_ids_are_redacted_but_order_and_identity_remain_traceable(self):
        self.assert_same("sensitive_parameters", 0)


if __name__ == "__main__":
    unittest.main()
