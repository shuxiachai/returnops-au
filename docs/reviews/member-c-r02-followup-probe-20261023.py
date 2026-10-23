"""Read-only synthetic follow-up; no DB, subprocess, credentials or file writes.

Usage: python -B this_file.py REPOSITORY_ROOT
Prints diagnostic observations. Exit 1 means a reviewed condition remains open,
not that the patched interruption behavior failed. This is not a CI expected-bug
test, a real-process cancellation test, or a Gate 1 acceptance result.
"""
import copy
import json
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / "tools/r02"), str(root / "apps/api"), str(root / "packages")]
import driver


def interrupt_probe(keep_api):
    cleanup, receipts, log_paths = [], [], []

    @contextmanager
    def fake_api(auth_file, log, **kwargs):
        log_paths.append(log)
        try:
            yield SimpleNamespace(url="http://127.0.0.1:8000", composition={}, environment_names=())
        finally:
            cleanup.append("api-stopped")

    def interrupt():
        raise KeyboardInterrupt()

    run = driver.Run(Path("/r02-not-created-public"), keep_api=keep_api, keep_api_log=True)
    run.private = Path("/r02-not-created-private")
    run.auth_file = run.private / "auth.json"
    run.environment = lambda: None
    run.provision = lambda: None
    run.customer_create = interrupt
    run.publish = lambda: receipts.append(copy.deepcopy(run.data))
    propagated = False
    with patch.object(driver.api_child, "api_process", fake_api), \
         patch.object(driver.httpx, "Client", lambda **kw: nullcontext(object())), \
         patch.object(driver.shutil, "rmtree", lambda *a, **kw: cleanup.append("private-remove")), \
         patch.object(Path, "exists", lambda self: False):
        try:
            run.execute()
        except KeyboardInterrupt:
            propagated = True
    terminal = bool(receipts) and receipts[-1].get("result") == "FAILED" \
        and receipts[-1].get("stop", {}).get("code") == "INTERRUPTED"
    return {
        "keep_api": keep_api,
        "terminal_failed_interrupted": terminal,
        "cleanup_attempted": cleanup == ["api-stopped", "private-remove"],
        "interrupt_propagated": propagated,
        "raw_log_target_is_public_output": log_paths == [run.output / driver.API_LOG],
    }


def dispose_probe():
    cleanup, receipts = [], []

    def fail():
        raise OSError("synthetic-dispose-failure")

    run = driver.Run(Path("/r02-not-created-public"))
    run.private = Path("/r02-not-created-private")
    run.engine = SimpleNamespace(dispose=fail)
    run.publish = lambda: receipts.append(copy.deepcopy(run.data))
    propagated = False
    with patch.object(driver.shutil, "rmtree", lambda *a, **kw: cleanup.append("private-remove")), \
         patch.object(Path, "exists", lambda self: False):
        try:
            run.finish()
        except OSError:
            propagated = True
    return {"dispose_error_propagated": propagated,
            "private_cleanup_attempted": bool(cleanup), "receipt_published": bool(receipts)}


def receipt_write_probe():
    """Exercise the real CLI/execute/finish path with a fake chain and refused writer.

    All database, subprocess, HTTP and filesystem mutations are replaced in
    memory. Only safe booleans, the exit code and exception type are returned;
    the synthetic private exception text is never printed.
    """
    calls, stdout, stderr = [], StringIO(), StringIO()
    private_detail = "synthetic-private-receipt-write-detail"

    @contextmanager
    def fake_api(*args, **kwargs):
        try:
            yield SimpleNamespace(url="http://127.0.0.1:8000", composition={}, environment_names=())
        finally:
            calls.append("api-stopped")

    def fail_write(*args, **kwargs):
        calls.append("receipt-write-attempt")
        raise OSError(private_detail)

    run = driver.Run(Path("/r02-not-created-public"))
    run.private = Path("/r02-not-created-private")
    run.auth_file = run.private / "auth.json"
    run.environment = lambda: None
    run.provision = lambda: None
    run.customer_create = lambda: run.check("synthetic_chain_check", True)
    for method in ("processors", "review_and_preview", "decisions", "execution_chain", "read_back"):
        setattr(run, method, lambda: None)
    exit_code, error_type = None, None
    with patch.object(driver, "Run", lambda *a, **kw: run), \
         patch.object(driver.api_child, "api_process", fake_api), \
         patch.object(driver.httpx, "Client", lambda **kw: nullcontext(object())), \
         patch.object(driver.shutil, "rmtree", lambda *a, **kw: calls.append("private-remove")), \
         patch.object(Path, "exists", lambda self: False), \
         patch.object(Path, "mkdir", lambda *a, **kw: None), \
         patch.object(driver, "write_receipt", fail_write), \
         redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            exit_code = driver.main(["--output", str(run.output)])
        except Exception as error:
            error_type = type(error).__name__
    return {
        "receipt_writer_failed": calls.count("receipt-write-attempt") == 1,
        "exit_code": exit_code,
        "propagated_error_type": error_type,
        "stdout_claims_passed": "R.02 driver result: PASSED" in stdout.getvalue(),
        "cleanup_attempted": calls[:2] == ["api-stopped", "private-remove"],
        "receipt_written_flag": run.receipt_written,
        "fixed_failure_notice": "R.02: the run receipt could not be written." in stderr.getvalue(),
        "private_exception_text_leaked": private_detail in stdout.getvalue() + stderr.getvalue(),
    }


interruptions = [interrupt_probe(False), interrupt_probe(True)]
disposal = dispose_probe()
receipt_write = receipt_write_probe()
c01_fixed = all(row["terminal_failed_interrupted"] and row["cleanup_attempted"]
                for row in interruptions)
c02_open = not disposal["private_cleanup_attempted"] or not disposal["receipt_published"] \
    or any(row["raw_log_target_is_public_output"] for row in interruptions)
c03_false_success = receipt_write["receipt_writer_failed"] and receipt_write["exit_code"] == 0
c03_verified = receipt_write["receipt_writer_failed"] and not receipt_write["private_exception_text_leaked"]
if c03_false_success:
    c03_status = "OPEN_FALSE_SUCCESS"
elif not c03_verified:
    c03_status = "OPEN_UNVERIFIED"
elif receipt_write["propagated_error_type"] == "OSError":
    c03_status = "WRITE_FAILURE_PROPAGATED"
elif receipt_write["exit_code"] is not None and receipt_write["exit_code"] != 0:
    c03_status = "FAIL_CLOSED_BOUNDED"
else:
    c03_status = "OPEN_UNVERIFIED"
print(json.dumps({"scope": "synthetic-in-memory-only", "R02-C-01":
                  "FIX_VERIFIED_BOUNDED" if c01_fixed else "OPEN",
                  "R02-C-02": "OPEN" if c02_open else "NEEDS_FULL_FAILURE_MATRIX_REVIEW",
                  "R02-C-03": c03_status, "interruptions": interruptions,
                  "disposal": disposal, "receipt_write": receipt_write}, indent=2))
sys.exit(1 if not c01_fixed or c02_open or c03_status.startswith("OPEN") else 0)
