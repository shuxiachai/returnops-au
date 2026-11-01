"""Railway container entry for the Week 13 demonstration (docs/46 section 9, docs/15 PD-03).

The first start, and any start after `demo.ps1 cloud-fresh` (`start.py forget-data`) or with
RETURNOPS_RESET_ON_START=1, is a fresh synthetic demonstration, the same as `demo.ps1 fresh`
on the demo machine: the returnops_f02 database is dropped and created again, migrated, the
demo store is provisioned into a private folder (README step 3). Since 31 October 2026 a
later start keeps the previous deployment's data: the private files (signing key, password
hashes, sessions) are kept in a small database of their own, returnops_f02_private, on the
same server, restored at start and saved again when they change; the database is migrated,
not dropped, and the three demo people get new access keys. Then the demo API serves on
127.0.0.1:8000 and Caddy serves the web build and proxies /v1 and /health on Railway's PORT.

DATABASE_URL is the postgresql:// URL of the project's PostgreSQL 17 service (README); the app
uses its own returnops_f02 database on that server. No credential or token is printed; the
presenter copies the sessions with `demo.ps1 cloud-tokens`. R.05.b; NFR-003/009.

S5 on Railway (1 November 2026, docs/45 S5): `python /app/start.py s5`, which `demo.ps1
cloud-s5` runs through `railway ssh`, asks this process to run the R.02 driver in demo mode
(tools/r02/README.md) against a database of its own, returnops_f02_s5, created fresh for each
run; the demo API, its workers and the demonstration's data stay as they are. Once the
driver's receipt says PASSED, Caddy is restarted to proxy to the driver's API on
127.0.0.1:8100 (or the next free port), so the public address shows the completed case to the demo_cups_founder
access key. `start.py s5-end` (`demo.ps1 cloud-s5-end`), the end of that key's 899 s session
or the driver ending restarts Caddy towards the demo API again. Approval and execution stay
inside the driver, which the presenter starts; no click in the browser starts an operation.
FR-009 to FR-012, NFR-001.
"""
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql

DATABASE = 'returnops_f02'
PRIVATE_DATABASE = 'returnops_f02_private'
SHOP = Path('/app/private/demo-shop')
PROVISION = ['--store', 'synthetic_au_store', '--customer-one', 'synthetic_customer_a',
             '--customer-two', 'synthetic_customer_b', '--founder', 'founder',
             '--order-investigation', '--fixed-proposal', '--founder-manual']
FOUNDER = PROVISION[PROVISION.index('--founder') + 1]
# A start keeps the previous data only with all of these; passwords.json comes along when present.
KEPT_FILES = ('auth.json', 'credentials.json', 'sessions.json')
SYNC_SECONDS = 5
REQUESTED = []
CHILDREN = []
API_PORT = 8000
# S5 on Railway: the driver's database, folder, API port and the dedicated store of README step 5
# (no order investigation, fixed proposal or manual authority).
S5_DATABASE = 'returnops_f02_s5'
S5_ROOT = Path('/app/private/s5')
S5_PORT = 8100
DRIVER = Path('/app/tools/r02/driver.py')
S5_PROVISION = ['--store', 'demo_cups_store', '--customer-one', 'demo_cups_customer_one',
                '--customer-two', 'demo_cups_customer_two', '--founder', 'demo_cups_founder']
S5_KINDS = ('s5', 's5-end')
S5_WAIT_SECONDS = {'s5': 600, 's5-end': 120}
S5_GRACE_SECONDS = 60


def serve_arguments(environ):
    """The demo API's command. The advisory model showcase (docs/44) runs only when the service
    variable RETURNOPS_MODEL_SHOWCASE is 1 and the model variables are complete and valid;
    otherwise the demonstration starts without it rather than not at all (31 October 2026).
    The messages name variables only, never their values."""
    arguments = [sys.executable, '-m', 'returnops_api.demo', 'serve', '--auth-file', str(SHOP / 'auth.json'),
                 '--port', '8000', '--fixed-proposal', '--founder-decisions', '--accounts']
    if environ.get('RETURNOPS_MODEL_SHOWCASE') != '1':
        return arguments
    from returnops_api.model_settings import ModelSettings
    from returnops_api.settings import ConfigurationError
    try:
        ModelSettings.from_environment(environ)
    except ConfigurationError as error:
        say(f'model showcase requested but not configured ({error}); starting without it')
        return arguments
    say('model showcase on: advisory facts for the Founder; the key is not printed')
    return arguments + ['--model-showcase']


def say(text):
    print(f'[demo start] {text}', flush=True)


def stop(text):
    say(f'STOP {text}')
    raise SystemExit(1)


def forward(signum, _frame):
    REQUESTED.append(signum)
    for child in CHILDREN:
        if child.poll() is None:
            child.send_signal(signum)


def end_children():
    for child in reversed(CHILDREN):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()


def finish_if_requested():
    if REQUESTED:
        end_children()
        say('stopped on request')
        raise SystemExit(0)


def database_urls(raw):
    """The server URL from Railway, and the app URL on the dedicated returnops_f02 database."""
    parts = urlsplit(raw or '')
    if parts.scheme not in ('postgresql', 'postgres') or not parts.hostname:
        stop('DATABASE_URL must be the postgresql:// URL of the PostgreSQL 17 service (README, Railway deployment).')
    server = urlunsplit(('postgresql', parts.netloc, parts.path or '/postgres', '', ''))
    app = urlunsplit(('postgresql+psycopg', parts.netloc, '/' + DATABASE, '', ''))
    return server, app


def reset_database(server):
    deadline = time.monotonic() + 120
    while True:
        try:
            with psycopg.connect(server, autocommit=True, connect_timeout=5) as connection:
                connection.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(DATABASE)))
                connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
            return
        except psycopg.OperationalError:
            finish_if_requested()
            if time.monotonic() > deadline:
                stop('PostgreSQL did not accept a connection within 120 s.')
            time.sleep(3)
        except psycopg.Error:
            # libpq can quote the whole URL, password included, when it cannot parse it.
            stop('DATABASE_URL could not be used as a PostgreSQL connection URL (README, Railway deployment); no detail is printed.')


def on_server(server, name):
    """The URL of database `name` on the server of `server`."""
    parts = urlsplit(server)
    return urlunsplit((parts.scheme, parts.netloc, '/' + name, '', ''))


def database_exists(server, name):
    with psycopg.connect(server, autocommit=True, connect_timeout=5) as connection:
        return connection.execute('SELECT 1 FROM pg_database WHERE datname = %s', (name,)).fetchone() is not None


def open_private_store(server, name=PRIVATE_DATABASE):
    """The kept private files live in their own database, outside the frozen application schema."""
    if not database_exists(server, name):
        with psycopg.connect(server, autocommit=True, connect_timeout=5) as connection:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with psycopg.connect(on_server(server, name), autocommit=True, connect_timeout=5) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS private_files (name text PRIMARY KEY, body bytea NOT NULL)')


def load_private(server, name=PRIVATE_DATABASE):
    with psycopg.connect(on_server(server, name), connect_timeout=5) as connection:
        return {row[0]: bytes(row[1]) for row in connection.execute('SELECT name, body FROM private_files')}


def save_private(server, files, name=PRIVATE_DATABASE):
    """Replace the kept set in one transaction, so a reader never sees half of it."""
    with psycopg.connect(on_server(server, name), connect_timeout=5) as connection:
        with connection.transaction():
            connection.execute('DELETE FROM private_files')
            for file_name, body in sorted(files.items()):
                connection.execute('INSERT INTO private_files (name, body) VALUES (%s, %s)', (file_name, body))


def forget_private(server, name=PRIVATE_DATABASE):
    if database_exists(server, name):
        with psycopg.connect(on_server(server, name), connect_timeout=5) as connection:
            connection.execute('DELETE FROM private_files')


def read_folder(folder):
    """The private files to keep: regular top-level files, nothing linked."""
    if not folder.is_dir():
        return {}
    return {path.name: path.read_bytes() for path in sorted(folder.iterdir())
            if path.is_file() and not path.is_symlink() and not path.name.endswith('.tmp')}


def write_folder(folder, files):
    """Restore kept files with the modes provision uses: the folder 0700, each file 0600."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(mode=0o700)
    for file_name, body in files.items():
        if file_name in ('', '.', '..') or '/' in file_name or '\\' in file_name:
            raise ValueError('unexpected kept file name')
        descriptor = os.open(folder / file_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(body)


def fingerprint(files):
    return tuple(sorted((name, hashlib.sha256(body).hexdigest()) for name, body in files.items()))


def provisioned(server, database=DATABASE, founder=FOUNDER):
    """Whether the application database exists and still holds the enabled demo Founder."""
    if not database_exists(server, database):
        return False
    with psycopg.connect(on_server(server, database), connect_timeout=5) as connection:
        if connection.execute("SELECT to_regclass('customer_principals')").fetchone()[0] is None:
            return False
        row = connection.execute("SELECT enabled FROM customer_principals WHERE principal_id = %s AND role = 'FOUNDER'",
                                 (founder,)).fetchone()
        return row is not None and row[0] is True


def keep_previous(files, has_data, environ):
    return (environ.get('RETURNOPS_RESET_ON_START') != '1' and has_data
            and all(name in files for name in KEPT_FILES))


def wait_for_server(server):
    deadline = time.monotonic() + 120
    while True:
        try:
            with psycopg.connect(server, connect_timeout=5):
                return
        except psycopg.OperationalError:
            finish_if_requested()
            if time.monotonic() > deadline:
                stop('PostgreSQL did not accept a connection within 120 s.')
            time.sleep(3)
        except psycopg.Error:
            stop('DATABASE_URL could not be used as a PostgreSQL connection URL (README, Railway deployment); no detail is printed.')


def start_kept(server, environment):
    """True when the previous deployment's data and private files are back in place."""
    try:
        open_private_store(server)
        files = load_private(server)
    except psycopg.Error:
        say('the kept private files could not be read; starting a fresh demonstration')
        return False
    try:
        has_data = provisioned(server)
    except psycopg.Error:
        # Never wipe data that could not be read: the next start tries again.
        stop('the kept database could not be read; nothing was removed.')
    if not keep_previous(files, has_data, os.environ):
        return False
    say('keeping the data of the previous deployment (demo.ps1 cloud-fresh starts a fresh one)')
    write_folder(SHOP, files)
    for step, arguments in (
            ('alembic upgrade head', [sys.executable, '-m', 'alembic', 'upgrade', 'head']),
            ('new demo sessions', [sys.executable, '-m', 'returnops_api.demo', 'renew-sessions', '--private-dir', str(SHOP)])):
        finish_if_requested()
        if subprocess.run(arguments, env=environment, cwd='/app').returncode != 0:
            say(f'{step} failed on the kept data; starting a fresh demonstration')
            return False
    return True


def save_if_changed(server, saved):
    """Keep the private files when they changed (a registration, new sessions); never print them."""
    files = read_folder(SHOP)
    current = fingerprint(files)
    if not files or current == saved:
        return saved
    try:
        save_private(server, files)
    except psycopg.Error:
        say('the private files could not be kept just now; trying again')
        return saved
    return current


def forget_data():
    """`python /app/start.py forget-data` (demo.ps1 cloud-fresh): the next start is a fresh demonstration."""
    server, _ = database_urls(os.environ.get('DATABASE_URL'))
    try:
        forget_private(server)
    except psycopg.Error:
        stop('the kept data could not be cleared; nothing was changed.')
    say('the kept private files are cleared; the next start resets the demonstration')


def run(step, arguments, environment):
    if subprocess.run(arguments, env=environment, cwd='/app').returncode != 0:
        stop(f'{step} failed; see the lines above.')


# The readiness check talks to 127.0.0.1 only: never through an HTTP(S)_PROXY from the
# environment, which would make it fail and the container restart (runtime review).
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def wait_ready(process, url, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None or REQUESTED:
            return False
        try:
            with LOCAL.open(url, timeout=3) as answer:
                if answer.status == 200 and b'"ready"' in answer.read():
                    return True
        except OSError:
            pass
        time.sleep(1)
    return False


def write_small(path, text, mode=0o600):
    """A small file replaced in one step, so a reader sees the old or the new text, never half."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{uuid.uuid4().hex[:8]}.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def read_json(path):
    """The JSON object in `path`, or None while it is missing or still being written."""
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def session_expiry(path):
    """When the earliest session of a provision sessions.json ends (Unix seconds), or None."""
    try:
        return min(int(session['expires_at']) for session in (read_json(path) or {})['sessions'])
    except (KeyError, TypeError, ValueError):
        return None


def recreate_database(server, name):
    """Drop and create one database; an error reaches the caller, and the demonstration stays."""
    with psycopg.connect(server, autocommit=True, connect_timeout=5) as connection:
        connection.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
        connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))


def free_port(first=S5_PORT, count=100):
    """The first loopback port from `first` that a plain bind accepts now, as the driver's own
    check does; a port the previous run left in TIME_WAIT is skipped. None if there is none."""
    for port in range(first, first + count):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    return None


def stop_child(process, first, seconds):
    """Stop one child with `first` (SIGINT lets the driver stop its API child), then terminate, then kill."""
    if process.poll() is None:
        process.send_signal(first)
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    if process in CHILDREN:
        CHILDREN.remove(process)


class Proxy:
    """Caddy on Railway's PORT, proxying /v1 and /health to one local API port (Caddyfile)."""

    def __init__(self, popen=subprocess.Popen):
        self.popen, self.process, self.port = popen, None, API_PORT

    def start(self, port=API_PORT):
        self.process = self.popen(['caddy', 'run', '--config', '/app/Caddyfile', '--adapter', 'caddyfile'],
                                  cwd='/app', env={**os.environ, 'RETURNOPS_API_PORT': str(port)})
        CHILDREN.append(self.process)
        self.port = port

    def switch(self, port):
        """Restart Caddy towards `port`; a request in the second between the two is refused."""
        if port == self.port and self.process.poll() is None:
            return
        stop_child(self.process, signal.SIGTERM, 10)
        self.start(port)
        say(f'Caddy now proxies /v1 and /health to 127.0.0.1:{port}')


def safe_id(value):
    text = str(value) if value is not None else ''
    return text if text and len(text) <= 64 and all(c.isalnum() or c in '_-' for c in text) else None


class S5Mode:
    """S5 inside the running container (`start.py s5`), one driver run at a time.

    Requests and the status are small files in S5_ROOT. The status holds states, codes, the
    case ID and times, never a token; the access keys stay in run/identities until the run
    ends. The demo API on 8000 is never stopped: the driver works on its own database."""

    def __init__(self, server, app, environment, root=S5_ROOT, popen=subprocess.Popen,
                 run=subprocess.run, ready=None, clock=time.time):
        self.server, self.app, self.environment, self.root = server, app, environment, root
        self.popen, self.run, self.clock = popen, run, clock
        self.ready = ready or (lambda driver, port: wait_ready(driver, f'http://127.0.0.1:{port}/health/ready', 30))
        self.driver, self.port, self.shown, self.deadline = None, None, False, None
        self.status = {'state': 'idle'}

    @property
    def run_dir(self):
        return self.root / 'run'

    def reset(self):
        """A new container starts without a run; a request or run folder left behind is dropped."""
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        (self.root / 'request').unlink(missing_ok=True)
        self.save()

    def save(self, **fields):
        self.status.update(fields, updated_at=int(self.clock()))
        write_small(self.root / 'status.json', json.dumps(self.status, sort_keys=True) + '\n')

    def answer(self, ident, value):
        """Answers to requests that start nothing: busy, ended or idle (the last ten are kept)."""
        answered = {**(self.status.get('answered') or {}), ident: value}
        self.save(answered=dict(list(answered.items())[-10:]))

    def take_request(self):
        path = self.root / 'request'
        try:
            words = path.read_text(encoding='ascii').split()
            path.unlink()
        except (OSError, ValueError):
            return None
        if len(words) == 2 and words[0] in S5_KINDS and words[1].isalnum() and len(words[1]) <= 32:
            return words[0], words[1]
        return None

    def step(self, switch):
        """Called about once a second by main(); `switch(port)` restarts Caddy towards that port.
        Whatever happens here, the demonstration keeps running."""
        try:
            request = self.take_request()
            if request and request[0] == 's5':
                self.begin(request[1], switch)
            elif request:
                self.end(request[1], switch)
            self.watch(switch)
        except Exception as error:  # no message: it could carry a URL
            say(f'S5: unexpected {type(error).__name__}; S5 stops and the demonstration keeps running')
            self.finish(switch, 'failed', code='S5_INTERNAL')

    def begin(self, ident, switch):
        if self.driver is not None:
            return self.answer(ident, 'busy')
        self.status = {'request': ident, 'state': 'starting', 'answered': self.status.get('answered') or {}}
        self.save()
        say(f'S5: preparing a fresh database ({S5_DATABASE}) and the demo-cups identities')
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)
        self.run_dir.mkdir(mode=0o700, parents=True)
        try:
            recreate_database(self.server, S5_DATABASE)
        except psycopg.Error:
            return self.finish(switch, 'failed', code='S5_DATABASE')
        # Only the database URL of the demonstration's variables: no model key, no demo password.
        environment = {name: value for name, value in self.environment.items() if not name.startswith('RETURNOPS_')}
        environment['DATABASE_URL'] = on_server(self.app, S5_DATABASE)
        identities, output = self.run_dir / 'identities', self.run_dir / 'output'
        for code, arguments in (
                ('S5_MIGRATION', [sys.executable, '-m', 'alembic', 'upgrade', 'head']),
                ('S5_PROVISION', [sys.executable, '-m', 'returnops_api.demo', 'provision',
                                  '--private-dir', str(identities), *S5_PROVISION])):
            if self.run(arguments, env=environment, cwd='/app').returncode != 0:
                return self.finish(switch, 'failed', code=code)
        self.port = free_port()
        if self.port is None:
            return self.finish(switch, 'failed', code='S5_NO_FREE_PORT')
        self.driver = self.popen([sys.executable, '-B', str(DRIVER), '--output', str(output),
                                  '--identities', str(identities), '--api-port', str(self.port), '--keep-api'],
                                 env=environment, cwd='/app')
        CHILDREN.append(self.driver)
        self.save(state='running', port=self.port)
        say('S5: the R.02 driver is running in demo mode')

    def watch(self, switch):
        if self.driver is None:
            return
        if self.status.get('state') == 'running':
            receipt = read_json(self.run_dir / 'output' / 'run-receipt.json')
            if receipt is not None and receipt.get('result') != 'RUNNING':
                return self.received(receipt, switch)
        if self.driver.poll() is not None:
            if self.status.get('state') == 'running':
                return self.finish(switch, 'failed', code='DRIVER_ENDED')
            return self.finish(switch, 'ended')
        if self.shown and self.deadline is not None and self.clock() > self.deadline:
            say('S5: the demo_cups_founder session has ended')
            self.finish(switch, 'ended')

    def received(self, receipt, switch):
        stop = receipt.get('stop') if isinstance(receipt.get('stop'), dict) else {}
        fields = dict(result=safe_id(receipt.get('result')), case_id=safe_id(receipt.get('case_id')),
                      code=safe_id(stop.get('code')))
        if fields['result'] != 'PASSED':
            return self.finish(switch, 'failed', **fields)
        if not self.ready(self.driver, self.port):
            return self.finish(switch, 'failed', **{**fields, 'code': 'S5_API_NOT_READY'})
        switch(self.port)
        self.shown = True
        expires = session_expiry(self.run_dir / 'identities' / 'sessions.json')
        self.deadline = (expires or int(self.clock()) + 899) + S5_GRACE_SECONDS
        self.save(state='passed', expires_at=expires, **fields)
        say(f'S5: driver result PASSED, case {fields["case_id"]}; the public address shows the driver API')

    def end(self, ident, switch):
        if self.driver is None:
            return self.answer(ident, 'idle')
        self.finish(switch, 'ended')
        self.answer(ident, 'ended')

    def finish(self, switch, state, **fields):
        """Show the demonstration again, stop the driver (SIGINT, so it stops its API child) and
        delete the demo-cups identities (signing key and access keys); the receipt stays."""
        try:
            if self.shown:
                switch(API_PORT)
        finally:
            self.shown, self.deadline = False, None
            if self.driver is not None:
                stop_child(self.driver, signal.SIGINT, 60)
                self.driver = None
            shutil.rmtree(self.run_dir / 'identities', ignore_errors=True)
            self.save(state=state, **fields)
            say(f'S5: {state}' + (f' ({fields["code"]})' if fields.get('code') else ''))

    def close(self):
        """The container stops: the driver gets SIGINT like a Ctrl+C."""
        if self.driver is not None:
            stop_child(self.driver, signal.SIGINT, 20)
            self.driver = None


def describe(status, answer=None):
    case = status.get('case_id') or 'unknown'
    state = status.get('state')
    if answer == 'busy':
        return f'a run is already active ({state}, case {case}); demo.ps1 cloud-s5-end ends it'
    if answer == 'idle':
        return 'no S5 run was active; the public address shows the demonstration'
    if answer == 'ended' or state == 'ended':
        return 'S5 ended; the public address shows the demonstration again'
    if state == 'starting':
        return f'preparing a fresh database ({S5_DATABASE}) and the demo-cups identities'
    if state == 'running':
        return 'the R.02 driver is running in demo mode (about two minutes)'
    if state == 'passed':
        until = time.strftime('%H:%M UTC', time.gmtime(status['expires_at'])) if status.get('expires_at') else 'its session ends'
        return (f'driver result PASSED, case {case}; the public address shows the driver API '
                f'until {until} or demo.ps1 cloud-s5-end')
    if state == 'failed':
        return (f'driver result {status.get("result") or "not reached"} ({status.get("code") or "see the deployment log"}); '
                'the demonstration itself was not changed')
    return f'state {state}'


def ask(kind, root=S5_ROOT, wait=None, clock=time.monotonic, sleep=time.sleep):
    """`start.py s5` / `start.py s5-end`, run through `railway ssh` (demo.ps1 cloud-s5 / cloud-s5-end).
    Exit 0 when the run passed (or was already shown), or when S5 ended or was not active."""
    if not (root / 'status.json').is_file():
        say('S5: this deployment does not answer S5 requests; deploy main with demo.ps1 cloud first')
        return 1
    ident = uuid.uuid4().hex[:16]
    # Readable by the container's user whichever user railway ssh runs as; it holds no secret.
    write_small(root / 'request', f'{kind} {ident}\n', mode=0o644)
    deadline = clock() + (wait or S5_WAIT_SECONDS[kind])
    shown = None
    while clock() < deadline:
        status = read_json(root / 'status.json') or {}
        answer = (status.get('answered') or {}).get(ident)
        if answer:
            say('S5: ' + describe(status, answer))
            return 0 if answer in ('ended', 'idle') or status.get('state') == 'passed' else 1
        if kind == 's5' and status.get('request') == ident:
            state = status.get('state')
            if state != shown:
                say('S5: ' + describe(status))
                shown = state
            if state in ('passed', 'failed', 'ended'):
                return 0 if state == 'passed' else 1
        sleep(2)
    say(f'S5: no answer within {wait or S5_WAIT_SECONDS[kind]} s; read the deployment log on railway.com')
    return 1


def main():
    # Handlers before any step: start.py is PID 1 in the container, and PID 1 ignores a
    # signal without a handler, so a stop during the reset, migration or provisioning used
    # to wait for SIGKILL while a newer deployment was already provisioning (30 October 2026).
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    server, app = database_urls(os.environ.get('DATABASE_URL'))
    environment = {**os.environ, 'DATABASE_URL': app}
    wait_for_server(server)
    if not start_kept(server, environment):
        say(f'resetting the {DATABASE} database')
        reset_database(server)
        finish_if_requested()
        run('alembic upgrade head', [sys.executable, '-m', 'alembic', 'upgrade', 'head'], environment)
        finish_if_requested()
        if SHOP.exists():
            shutil.rmtree(SHOP)
        run('demo provision', [sys.executable, '-m', 'returnops_api.demo', 'provision', '--private-dir', str(SHOP), *PROVISION], environment)
    finish_if_requested()
    try:
        open_private_store(server)
    except psycopg.Error:
        say('the private files cannot be kept on this server; the next deployment starts fresh')
    saved = save_if_changed(server, None)

    api = subprocess.Popen(serve_arguments(environment), env=environment, cwd='/app')
    CHILDREN.append(api)
    if not wait_ready(api, 'http://127.0.0.1:8000/health/ready', 60):
        finish_if_requested()
        api.kill()
        stop('the demo API did not become ready within 60 s.')
    say('demo API ready on 127.0.0.1:8000; starting Caddy')
    proxy = Proxy()
    proxy.start()
    finish_if_requested()
    s5 = S5Mode(server, app, environment)
    try:
        s5.reset()
    except OSError:
        say('S5: its folder could not be prepared; S5 is not available in this container')
        s5 = None

    # Either process ending on its own ends the container with exit code 1, so Railway's
    # restart policy starts the demonstration again; a stop that Railway asked for exits 0.
    ticks = 0
    while not REQUESTED and api.poll() is None and proxy.process.poll() is None:
        time.sleep(1)
        ticks += 1
        if s5 is not None:
            s5.step(proxy.switch)
        if ticks % SYNC_SECONDS == 0:
            saved = save_if_changed(server, saved)
    if s5 is not None:
        s5.close()
    end_children()
    save_if_changed(server, saved)
    if REQUESTED:
        say('stopped on request')
        raise SystemExit(0)
    stop('the demo API or Caddy stopped.')


if __name__ == '__main__':
    if sys.argv[1:] == ['forget-data']:
        forget_data()
    elif len(sys.argv) == 2 and sys.argv[1] in S5_KINDS:
        raise SystemExit(ask(sys.argv[1]))
    elif sys.argv[1:]:
        say('usage: start.py [forget-data | s5 | s5-end]')
        raise SystemExit(2)
    else:
        main()
