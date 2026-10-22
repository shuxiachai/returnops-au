"""R.02 API child process on an owned ephemeral loopback port; not installed.

Follows tests/founder/tcp_support.py: bind port 0, start one child with Popen
(never a shell background job), poll /health/ready, then terminate and kill.
The child composes the real app with create_app(engine, auth_config,
**COMPOSITION); the same constant is returned to the driver for its receipt.
No worker runs in the API process, so only the driver moves its one case. The
engine is the production build_engine() and the auth file is read by the
production load_private_auth_config(). The child gets only the environment it
needs (CHILD_ENVIRONMENT), not every variable of the caller.

The private auth file holds only issuer/audience/signing key. It is created
0600 (O_EXCL) inside a 0700 temporary directory that the driver removes; it
must never be uploaded as a CI artifact.

Demo mode only (driver --api-port/--keep-api): api_process(port=N) binds the
fixed loopback port N instead of port 0 and refuses a port that is already in
use; hold() keeps the child running until Ctrl+C or until it exits by itself.
The default (port=None, no hold) is unchanged.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx

COMPOSITION = dict(enable_processor=False, enable_fixed_proposal=False, enable_founder_decisions=True)
CHILD = r"""
import os
import uvicorn
from returnops_api.customer_config import load_private_auth_config
from returnops_api.database import build_engine
from returnops_api.main import create_app
from returnops_api.settings import Settings, require_environment_database
settings = Settings.from_environment()
require_environment_database(settings.database_url.get_secret_value())
app = create_app(engine=build_engine(settings), auth_config=load_private_auth_config(), **%r)
uvicorn.run(app, host='127.0.0.1', port=int(os.environ['RETURNOPS_R02_PORT']), access_log=False, log_level='warning')
""" % (COMPOSITION,)
# Names passed through to the child; everything else (other RETURNOPS_* flags,
# CI tokens, unrelated credentials) is dropped. PG* keeps libpq options.
CHILD_ENVIRONMENT = ('DATABASE_URL', 'PATH', 'PATHEXT', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'TEMP',
                     'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'LANG', 'LANGUAGE', 'TZ',
                     'VIRTUAL_ENV', 'SSL_CERT_FILE', 'SSL_CERT_DIR')
CHILD_PREFIXES = ('PYTHON', 'PG', 'LC_')


class ApiChildError(Exception):
    """A safe code only (str(error)); no child output or local detail is echoed."""


@dataclass(frozen=True)
class ApiChild:
    url: str
    pid: int
    composition: dict
    environment_names: tuple
    process: object = field(default=None, repr=False, compare=False)


def require_private_runtime():
    # Same rule as returnops_api.demo: the private 0700 Windows DACL needs 3.12.4+.
    if os.name == 'nt' and sys.version_info < (3, 12, 4):
        raise ApiChildError('PRIVATE_RUNTIME_REQUIRES_PYTHON_3_12_4')


def private_directory():
    require_private_runtime()
    return Path(tempfile.mkdtemp(prefix='r02-private-'))


def write_auth_file(directory, issuer, audience, signing_key):
    path = Path(directory).resolve() / 'auth.json'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
        json.dump({'issuer': issuer, 'audience': audience,
                   'signing_key_base64': base64.b64encode(signing_key).decode('ascii')}, output, ensure_ascii=True)
        output.write('\n')
    return path


def _code_path(existing):
    # The child imports exactly the package directories this process imported.
    import returnops_api
    import returnops_domain
    roots = [str(Path(module.__file__).resolve().parent.parent) for module in (returnops_api, returnops_domain)]
    parts = roots + ([existing] if existing else [])
    return os.pathsep.join(dict.fromkeys(parts))


def child_environment(source, auth_file, port):
    env = {name: value for name, value in source.items()
           if name.upper() in CHILD_ENVIRONMENT or name.upper().startswith(CHILD_PREFIXES)}
    # UTF-8 output lets the driver find and replace local directories in a kept log.
    env.update(RETURNOPS_AUTH_FILE=str(auth_file), RETURNOPS_R02_PORT=str(port), PYTHONDONTWRITEBYTECODE='1',
               PYTHONIOENCODING='utf-8', PYTHONPATH=_code_path(source.get('PYTHONPATH')))
    return env


def _stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def reserve_port(port=None):
    """Port 0 (default) lets the OS choose; a fixed demo port must be free on loopback.

    On Windows SO_EXCLUSIVEADDRUSE makes the probe fail if any socket, including
    a wildcard listener, already holds the port (tools/environment/native_check.py).
    The probe is closed before the child binds, so a race remains possible.
    """
    with socket.socket() as listener:
        if port is not None and os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        if port is None:
            listener.bind(('127.0.0.1', 0))
        else:
            try:
                listener.bind(('127.0.0.1', port))
            except OSError:
                raise ApiChildError('API_PORT_UNAVAILABLE') from None
        return listener.getsockname()[1]


def hold(api, *, interval=1.0, sleep=time.sleep):
    """Keep the child running until Ctrl+C ('INTERRUPTED') or until it exits ('EXITED').

    The caller's api_process context then stops it as usual (terminate, then kill).
    """
    try:
        while api.process.poll() is None:
            sleep(interval)
    except KeyboardInterrupt:
        return 'INTERRUPTED'
    return 'EXITED'


@contextmanager
def api_process(auth_file, log_path, *, ready_seconds=30.0, port=None):
    port = reserve_port(port)
    env = child_environment(os.environ, auth_file, port)
    url = 'http://127.0.0.1:' + str(port)
    with open(log_path, 'wb') as output:
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD], env=env, stdout=output,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            ready = False
            deadline = time.monotonic() + ready_seconds
            with httpx.Client(timeout=1, trust_env=False) as probe:
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        if probe.get(url + '/health/ready').status_code == 200:
                            ready = True
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(.05)
            if not ready:
                raise ApiChildError('API_CHILD_NOT_READY')
            yield ApiChild(url, process.pid, dict(COMPOSITION), tuple(sorted(env)), process)
        finally:
            _stop(process)
