"""C-only R.02 fault-matrix diagnostic; synthetic in-memory I/O only.

Usage: python -B this_file.py REPOSITORY_ROOT
No DB, HTTP, child process, real credentials or filesystem writes are used.
PASS means the explicitly enumerated control-flow assertions passed, not Gate 1,
OS-level cleanup, SIGKILL handling, a personal signature or business acceptance.
"""
import hashlib
import json
import sys
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
driver_path = root / "tools/r02/driver.py"
source_hash = hashlib.sha256(driver_path.read_bytes()).hexdigest()
sys.path[:0] = [str(root / "tools/r02"), str(root / "apps/api"), str(root / "packages")]
import driver

# Match the CLI's canonical paths, including drive qualification on Windows.
# Resolve before mocking filesystem methods; these synthetic paths are never created.
PRIVATE = Path("/c-matrix-never-created-private").resolve()
OUTPUT = Path("/c-matrix-never-created-output").resolve()
IDENTITIES = Path("/c-matrix-never-created-identities").resolve()
SENTINEL = "C_SYNTHETIC_PRIVATE_VALUE_7821"


def cleanup_case(name, faults=(), credential_log=False):
    """Real finish/publish_api_log/screen_log/render_receipt; only I/O is fake."""
    calls, captured, log_output = [], [], []
    state = {"private": True}
    run = driver.Run(OUTPUT, keep_api_log=True)
    run.private = PRIVATE
    run.locate("<private>", PRIVATE)
    run.secrets.append(SENTINEL)
    run.data["result"] = "PASSED"

    def fail_if(key):
        if key in faults:
            raise OSError(SENTINEL)

    def dispose():
        calls.append("dispose")
        fail_if("dispose")

    def read(path):
        calls.append("log_read")
        fail_if("log_read")
        return ((SENTINEL + " ") if credential_log else "").encode() + str(PRIVATE).encode()

    original_screen = driver.screen_log

    def screen(*args):
        calls.append("screen")
        fail_if("screen")
        return original_screen(*args)

    def write(path, data):
        calls.append("log_write")
        assert path == OUTPUT / driver.API_LOG
        fail_if("log_write")
        log_output.append(data)
        return len(data)

    def remove(*args, **kwargs):
        calls.append("remove")
        fail_if("remove")
        state["private"] = "remove_survives" in faults

    def exists(path):
        return state["private"] if path == PRIVATE else path == PRIVATE / driver.API_LOG

    def receipt(path, data, forbidden):
        calls.append("receipt")
        fail_if("receipt")
        captured.append(json.loads(driver.render_receipt(data, forbidden)))

    run.engine = SimpleNamespace(dispose=dispose)
    stdout, stderr = StringIO(), StringIO()
    with patch.object(Path, "read_bytes", read), patch.object(Path, "write_bytes", write), \
         patch.object(Path, "exists", exists), patch.object(driver, "screen_log", screen), \
         patch.object(driver.shutil, "rmtree", remove), patch.object(driver, "write_receipt", receipt), \
         redirect_stdout(stdout), redirect_stderr(stderr):
        run.finish()
    assert calls.index("dispose") < calls.index("log_read") < calls.index("remove") < calls.index("receipt")
    assert run.receipt_written == ("receipt" not in faults)
    codes = run.data.get("cleanup_failures", [])
    expected = []
    if "dispose" in faults:
        expected.append("ENGINE_DISPOSE_FAILED")
    if any(f in faults for f in ("log_read", "screen", "log_write")):
        expected.append("API_LOG_SCREEN_FAILED")
    if "remove" in faults:
        expected.append("PRIVATE_DIRECTORY_REMOVE_FAILED")
    assert codes == expected
    assert run.data["private_directory_removed"] == (not state["private"])
    material = stdout.getvalue() + stderr.getvalue() + json.dumps(captured) + repr(log_output)
    assert SENTINEL not in material and str(PRIVATE) not in material
    assert "receipt" not in faults or not captured
    if "log_write" in faults:
        assert not log_output
    elif "log_read" in faults or "screen" in faults:
        assert log_output == [driver.LOG_UNSCREENED]
    elif credential_log:
        assert log_output == [driver.LOG_WITHHELD]
    else:
        assert log_output == [b"<private>"]
    # A cleanup error does not rewrite the business result: record this limit explicitly.
    return dict(name=name, assertions="PASS", operations=calls, cleanup_codes=codes,
                private_removed=not state["private"], receipt_captured=bool(captured),
                recorded_business_result=run.data["result"])


def receipt_case(form, keep_api):
    """Real CLI/execute/finish/publish, with in-memory chain and writer.

    Real render_receipt selects full/reduced/bare/withheld via forbidden synthetic
    strings, rather than simply making the writer raise ReceiptLeak every time.
    """
    calls, receipts = [], []
    stdout, stderr = StringIO(), StringIO()
    identities = IDENTITIES if keep_api else None
    run = driver.Run(OUTPUT, identities=identities, keep_api=keep_api)
    run.private, run.auth_file = PRIVATE, PRIVATE / "auth.json"
    run.environment = lambda: None
    run.provision = lambda: None
    run.customer_create = lambda: run.check("synthetic_control_only", True)
    for method in ("processors", "review_and_preview", "decisions", "execution_chain", "read_back"):
        setattr(run, method, lambda: None)
    if form == "reduced":
        run.data["synthetic_private"] = SENTINEL
        run.secrets.append(SENTINEL)
    elif form == "bare":
        run.secrets.append("finished_at")  # present in full/reduced, absent in bare
    elif form == "withheld":
        run.secrets.append("r02-run-receipt/v1")  # all forms must be withheld

    @contextmanager
    def api(*args, **kwargs):
        calls.append("start")
        try:
            yield SimpleNamespace(url="http://127.0.0.1:8000", composition={}, environment_names=())
        finally:
            calls.append("stop")

    def write(path, data, forbidden):
        calls.append("write_attempt")
        if form == "io_error":
            raise OSError(SENTINEL)
        receipts.append(json.loads(driver.render_receipt(data, forbidden)))

    run.hold = lambda api: calls.append("hold")

    def factory(output, **kwargs):
        assert output == OUTPUT
        assert kwargs["keep_api"] == keep_api and kwargs["identities"] == identities
        return run

    argv = ["--output", str(OUTPUT)]
    if keep_api:
        argv += ["--identities", str(identities), "--keep-api"]
    with patch.object(driver, "Run", factory), \
         patch.object(driver.api_child, "api_process", api), \
         patch.object(driver.httpx, "Client", lambda **kwargs: nullcontext(object())), \
         patch.object(driver.shutil, "rmtree", lambda *args, **kwargs: calls.append("remove")), \
         patch.object(Path, "exists", lambda path: False), \
         patch.object(Path, "mkdir", lambda *args, **kwargs: None), \
         patch.object(driver, "write_receipt", write), redirect_stdout(stdout), redirect_stderr(stderr):
        code = driver.main(argv)
    assert code == (0 if form == "full" else 1)
    assert bool(receipts) == (form not in ("withheld", "io_error"))
    assert ("hold" in calls) == (keep_api and bool(receipts))
    assert "stop" in calls and "remove" in calls
    assert SENTINEL not in stdout.getvalue() + stderr.getvalue() + json.dumps(receipts)
    if not receipts:
        assert "see run-receipt.json" not in stdout.getvalue()
        assert "R.02 driver result: PASSED" not in stdout.getvalue()
    if form in ("reduced", "bare"):
        assert receipts[0]["result"] == "FAILED"
        assert receipts[0]["stop"]["code"] == "RECEIPT_REDACTION_FAILED"
    assert calls.count("write_attempt") == {
        "full": 1, "reduced": 2, "bare": 3, "withheld": 3, "io_error": 2 if keep_api else 1}[form]
    if form == "reduced":
        assert "finished_at" in receipts[0] and receipts[0]["stop"]["original_result"] == "PASSED"
    if form == "bare":
        assert set(receipts[0]) == {"format", "result", "stop"}
    return dict(name=form, keep_api=keep_api, assertions="PASS", exit_code=code,
                render_attempts=calls.count("write_attempt"), receipt_captured=bool(receipts),
                hold_called="hold" in calls, withheld=getattr(run, "receipt_withheld", False))


cases = [("normal", ()), ("dispose", ("dispose",)), ("log_read", ("log_read",)),
         ("screen", ("screen",)), ("log_write", ("log_write",)), ("remove_raises", ("remove",)),
         ("screen_and_notice_write", ("screen", "log_write")),
         ("remove_survives", ("remove_survives",)), ("receipt_io", ("receipt",)),
         ("combined", ("dispose", "log_read", "log_write", "remove", "receipt"))]
cleanup = [cleanup_case(name, faults) for name, faults in cases]
cleanup.append(cleanup_case("credential_log_withheld", credential_log=True))
cleanup.append(cleanup_case("credential_notice_write", ("log_write",), credential_log=True))
receipt_rows = [receipt_case(form, keep) for keep in (False, True)
                for form in ("full", "reduced", "bare", "withheld", "io_error")]
print(json.dumps(dict(scope="synthetic-in-memory-ordinary-exceptions-only",
                      driver_sha256=source_hash, total_rows=len(cleanup)+len(receipt_rows),
                      cleanup=cleanup, receipt_forms=receipt_rows,
                      disposition="BOUNDED_MATRIX_PASS_NOT_FULL_R02_C02_CLOSURE",
                      unverified=["real OS read/write/delete faults", "cleanup interrupted a second time",
                                  "SIGKILL/power loss", "child termination and actual PostgreSQL/browser demo",
                                  "designated human acceptance"]), indent=2))
