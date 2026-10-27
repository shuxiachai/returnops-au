"""C-only bounded OS fault diagnostic; never a business/gate acceptance run.

Only owned temporary files and no-network Python sleep children are used.
The real Run.finish/write_receipt and ApiChild._stop paths are exercised.
Synthetic chain/context seams replace all API/DB/business work. No tracked
source file is changed. Run with the locked Python and explicit repository plus
a NEW output directory. This is a pinned fix-review diagnostic, not a business CI gate:
exit 0 means the nine bounded OS observations match the assertions. The original
25 October defect reproducer remains unchanged. Signals target only this
diagnostic process; all children are owned no-network Python sleepers.
"""
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import signal
import select
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


if len(sys.argv) != 3:
    raise SystemExit('Usage: python -B probe.py EXACT_REPOSITORY NEW_OUTPUT_DIRECTORY')
if sys.flags.optimize:
    raise SystemExit('Run without Python optimization: diagnostic assertions must remain enabled.')
if os.name != 'posix' or os.geteuid() == 0:
    raise SystemExit('This diagnostic requires a non-root POSIX account.')
ROOT = Path(sys.argv[1]).resolve()
OUTPUT = Path(sys.argv[2]).resolve()
REFERENCE_SOURCE = '65037770d452cc939e7b66f1cee9a437648edb5b'
EXPECTED_HASHES = {
    'driver.py': '3558dfbf2eca922659e4d7369a29666170d81b412ae846f19e53704c50d5f721',
    'api_child.py': '66f152a4ea7313fc3409beac3f4465c9219ed329b32b367798e506b7062cdec7',
}
SOURCE_HASHES = {name: hashlib.sha256((ROOT / 'tools/r02' / name).read_bytes()).hexdigest()
                 for name in EXPECTED_HASHES}
if SOURCE_HASHES != EXPECTED_HASHES:
    raise SystemExit('Source bytes differ from the reviewed target; inspect before adapting this reproducer.')
if OUTPUT.exists() or OUTPUT.is_symlink():
    raise SystemExit('Refusing to reuse an output directory.')
OUTPUT.mkdir(mode=0o700)
sys.path[:0] = [str(ROOT / 'tools/r02'), str(ROOT / 'apps/api'), str(ROOT / 'packages')]
import driver
import api_child
for module, name in ((driver, 'driver.py'), (api_child, 'api_child.py')):
    if Path(module.__file__).resolve() != (ROOT / 'tools/r02' / name).resolve():
        raise SystemExit('Imported module is not the explicitly selected review source.')

MARKER = 'C_OS_PROBE_SYNTHETIC_MARKER_20261026'
ROWS = []
STARTED = time.time()


def inspect_receipt(run):
    path = run.output / driver.RECEIPT
    return json.loads(path.read_text()) if path.is_file() else None


def filesystem_case(name):
    with tempfile.TemporaryDirectory(prefix='owned-c-os-', dir=OUTPUT) as directory:
        base = Path(directory)
        output, private = base / 'output', base / 'private'
        output.mkdir(mode=0o700)
        private.mkdir(mode=0o700)
        raw_log = private / driver.API_LOG
        raw_log.write_text('synthetic path ' + str(private))
        run = driver.Run(output, keep_api_log=True)
        run.private = private
        run.locate('<private>', private)
        run.secrets.append(MARKER)
        run.data.update(result='FAILED', stop={'code': 'SYNTHETIC_NO_DB'})
        stdout, stderr = StringIO(), StringIO()
        actual_error = None
        try:
            if name == 'log_read_eacces':
                raw_log.chmod(0)
                try:
                    raw_log.read_bytes()
                except PermissionError as error:
                    actual_error = error.errno
                assert actual_error == 13, 'Permission refusal was not reproduced'
            elif name == 'log_write_is_directory':
                (output / driver.API_LOG).mkdir()
            elif name == 'receipt_write_eacces':
                # Log publishing is disabled so this is specifically the receipt write.
                run.keep_api_log = False
                output.chmod(0o500)
                try:
                    with (output / 'permission-check').open('x'):
                        pass
                except PermissionError as error:
                    actual_error = error.errno
                assert actual_error == 13, 'Permission refusal was not reproduced'
            elif name == 'private_removal_eacces':
                private.chmod(0o500)
                try:
                    raw_log.unlink()
                except PermissionError as error:
                    actual_error = error.errno
                assert actual_error == 13, 'Unlink refusal was not reproduced'
            elif name == 'receipt_target_is_directory':
                (output / driver.RECEIPT).mkdir()
            else:
                raise AssertionError(name)
            with redirect_stdout(stdout), redirect_stderr(stderr):
                run.finish()
            receipt = inspect_receipt(run)
            material = stdout.getvalue() + stderr.getvalue() + json.dumps(receipt)
            assert MARKER not in material and str(private) not in material
            if name in ('receipt_write_eacces', 'receipt_target_is_directory'):
                assert not run.receipt_written and receipt is None and not private.exists()
                assert 'run receipt could not be written' in stderr.getvalue()
            else:
                assert run.receipt_written and receipt['stop']['code'] == 'SYNTHETIC_NO_DB'
            if name in ('log_read_eacces', 'log_write_is_directory'):
                assert receipt['cleanup_failures'] == ['API_LOG_SCREEN_FAILED']
                assert receipt['private_directory_removed'] is True and not private.exists()
            if name == 'log_read_eacces':
                assert (output / driver.API_LOG).read_bytes() == driver.LOG_UNSCREENED
                assert receipt['api_log'] == 'WITHHELD'
            if name == 'private_removal_eacces':
                assert private.exists() and receipt['private_directory_removed'] is False
                assert run.private_left and 'private temporary directory was not removed' in run.cleanup_note()
                assert 'could not be removed' in stderr.getvalue()
            ROWS.append(dict(name=name, assertions='PASS', actual_permission_errno=actual_error,
                             receipt_written=run.receipt_written,
                             cleanup_codes=run.cleanup_failures, private_left=run.private_left))
        finally:
            output.chmod(0o700)
            if private.exists():
                private.chmod(0o700)
            if raw_log.exists():
                raw_log.chmod(0o600)


def existing_receipt_case():
    with tempfile.TemporaryDirectory(prefix='owned-c-existing-', dir=OUTPUT) as directory:
        output = Path(directory)
        prior = b'{"synthetic_previous_receipt":true}\n'
        path = output / driver.RECEIPT
        path.write_bytes(prior)
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = driver.main(['--output', str(output)])
        assert result == 2 and path.read_bytes() == prior
        assert 'Refusing to overwrite' in stderr.getvalue()
        ROWS.append(dict(name='existing_receipt_cli_refused', assertions='PASS', cli_exit=2,
                         original_bytes_preserved=True))


def child(ignore_term):
    code = ('import signal,time,sys\n'
            + ('signal.signal(signal.SIGTERM, signal.SIG_IGN)\n' if ignore_term else '')
            + 'print("READY",flush=True)\ntime.sleep(60)\n')
    process = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', code],
                               env={'PYTHONDONTWRITEBYTECODE': '1'},
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        assert ready and process.stdout.readline() == b'READY\n', 'Owned child did not become ready'
    except BaseException:
        reap(process)
        raise
    return process


def reap(process):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)
    process.stdout.close()
    process.stderr.close()


def stop_case(ignore_term):
    process = child(ignore_term)
    started = time.monotonic()
    try:
        api_child._stop(process)
        elapsed = time.monotonic() - started
        expected = -signal.SIGKILL if ignore_term else -signal.SIGTERM
        assert process.poll() == expected
        if ignore_term:
            assert elapsed >= 9.5
        ROWS.append(dict(name='ignore_sigterm_forced_kill' if ignore_term else 'normal_sigterm_stop',
                         assertions='PASS', returncode=process.returncode,
                         elapsed_seconds=round(elapsed, 3), child_reaped=True))
    finally:
        reap(process)


def double_interrupt_case():
    process = child(True)
    timers = []
    stop_interrupted = False
    stop_reports = []
    try:
        with tempfile.TemporaryDirectory(prefix='owned-c-interrupt-', dir=OUTPUT) as directory:
            base = Path(directory)
            output, private = base / 'output', base / 'private'
            output.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            (private / 'auth.json').write_text('{"synthetic_only":true}')
            run = driver.Run(output)
            run.private, run.auth_file = private, private / 'auth.json'
            run.locate('<private>', private)
            run.environment = lambda: None
            run.provision = lambda: None

            def first_interrupt():
                os.kill(os.getpid(), signal.SIGINT)

            run.customer_create = first_interrupt

            @contextmanager
            def owned_child_context(*args, **kwargs):
                nonlocal stop_interrupted
                try:
                    yield SimpleNamespace(url='http://127.0.0.1:1', composition={}, environment_names=())
                finally:
                    timer = threading.Timer(.25, lambda: os.kill(os.getpid(), signal.SIGINT))
                    timers.append(timer)
                    timer.start()
                    try:
                        def report(stopped, pid):
                            stop_reports.append((stopped, pid))
                            kwargs['on_stop'](stopped, pid)
                        api_child._stop(process, report=report)
                    except KeyboardInterrupt:
                        stop_interrupted = True
                        raise

            stdout, stderr = StringIO(), StringIO()
            with patch.object(driver.api_child, 'api_process', owned_child_context), \
                 patch.object(driver.httpx, 'Client', lambda **kwargs: nullcontext(object())), \
                 redirect_stdout(stdout), redirect_stderr(stderr):
                result = run.execute()
            receipt = inspect_receipt(run)
            alive = process.poll() is None
            assert result == 'FAILED' and receipt['stop']['code'] == 'INTERRUPTED'
            assert receipt['private_directory_removed'] is True and not private.exists()
            assert not run.cleanup_failures and not run.private_left
            assert not alive and stop_interrupted, 'Fix must reap before reraising the interruption'
            assert process.returncode == -signal.SIGKILL
            assert stop_reports == [(True, process.pid)] and run.child_left is None
            ROWS.append(dict(name='second_sigint_during_real_child_stop', assertions='PASS',
                             first_sigint='synthetic chain', second_sigint='real child stop interrupted',
                             stop_interrupted=stop_interrupted,
                             driver_result=result, receipt_stop_code=receipt['stop']['code'],
                             receipt_private_removed=receipt['private_directory_removed'],
                             cleanup_codes=run.cleanup_failures, child_alive_after_execute=alive,
                             child_returncode=process.returncode, stop_reported=True,
                             stop_reported_stopped=stop_reports[0][0],
                             harness_kill_and_reap_required=False))
    finally:
        for timer in timers:
            timer.cancel()
            timer.join(timeout=2)
        reap(process)


for name in ('log_read_eacces', 'log_write_is_directory', 'receipt_write_eacces',
             'private_removal_eacces', 'receipt_target_is_directory'):
    filesystem_case(name)
existing_receipt_case()
stop_case(False)
stop_case(True)
double_interrupt_case()
report = dict(scope='C-owned real-OS fault review; synthetic chain and no-network sleep children',
              reference_source_commit=REFERENCE_SOURCE,
              source_sha256=SOURCE_HASHES,
              diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              platform=sys.platform, python=sys.version.split()[0],
              rows=ROWS, row_count=len(ROWS), duration_seconds=round(time.time()-STARTED, 3),
              no_database=True, no_network=True, no_model=True,
              children_reaped_by_harness=True,
              disposition='NARROW_SECOND_INTERRUPT_CHILD_LEAK_CORRECTED_AT_PR136_SOURCE',
              unverified=['real API child and DB/browser workflow', 'Windows process/file behavior',
                          'disk full/power loss/SIGKILL', 'interrupts during later engine/log/directory/receipt cleanup',
                          'whole failure matrix', 'human/gate acceptance'])
encoded = json.dumps(report, indent=2) + '\n'
with (OUTPUT / 'result.json').open('x') as file:
    file.write(encoded)
print(encoded)
