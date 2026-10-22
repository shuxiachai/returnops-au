"""Read-only in-memory reproduction; no DB, subprocess, credentials or file writes.

Run with repository root as argv[1] and its locked Python dependencies.
These assertions reproduce two defects at main 4aec7c0, not a passing fix.
"""
import copy
from contextlib import contextmanager, nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / "tools/r02"), str(root / "apps/api"), str(root / "packages")]
import driver


@contextmanager
def fake_api(*args, **kwargs):
    try:
        yield SimpleNamespace(url="http://127.0.0.1:8000", composition={}, environment_names=())
    finally:
        cleanup.append("api-stopped")


def interrupt():
    raise KeyboardInterrupt()


def dispose_failure():
    raise OSError("synthetic-dispose-failure")


cleanup, receipts = [], []
run = driver.Run(Path("/r02-not-created-public"))
run.private = Path("/r02-not-created-private")
run.auth_file = run.private / "auth.json"
run.environment = lambda: None
run.provision = lambda: None
run.customer_create = interrupt
run.publish = lambda: receipts.append(copy.deepcopy(run.data))
with patch.object(driver.api_child, "api_process", fake_api), \
     patch.object(driver.httpx, "Client", lambda **kw: nullcontext(object())), \
     patch.object(driver.shutil, "rmtree", lambda *a, **kw: cleanup.append("private-remove")), \
     patch.object(Path, "exists", lambda self: False):
    try:
        run.execute()
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected cancellation propagation")
assert cleanup == ["api-stopped", "private-remove"]
assert receipts[0]["result"] == "RUNNING" and "stop" not in receipts[0]
print("REPRODUCED R02-C-01: interrupted run publishes RUNNING with no stop; cleanup attempted")

cleanup, receipts = [], []
run = driver.Run(Path("/r02-not-created-public"))
run.private = Path("/r02-not-created-private")
run.engine = SimpleNamespace(dispose=dispose_failure)
run.publish = lambda: receipts.append(copy.deepcopy(run.data))
with patch.object(driver.shutil, "rmtree", lambda *a, **kw: cleanup.append("private-remove")):
    try:
        run.finish()
    except OSError:
        pass
    else:
        raise AssertionError("expected synthetic dispose failure")
assert not cleanup and not receipts
print("REPRODUCED R02-C-02: dispose failure skips private-directory cleanup and receipt publication")
print("No filesystem writes, real subprocesses, database connections or model calls were used.")
