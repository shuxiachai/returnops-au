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
"""
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
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
    web = subprocess.Popen(['caddy', 'run', '--config', '/app/Caddyfile', '--adapter', 'caddyfile'], cwd='/app')
    CHILDREN.append(web)
    finish_if_requested()

    # Either process ending on its own ends the container with exit code 1, so Railway's
    # restart policy starts a fresh demonstration; a stop that Railway asked for exits 0.
    ticks = 0
    while api.poll() is None and web.poll() is None:
        time.sleep(1)
        ticks += 1
        if ticks % SYNC_SECONDS == 0:
            saved = save_if_changed(server, saved)
    end_children()
    save_if_changed(server, saved)
    if REQUESTED:
        say('stopped on request')
        raise SystemExit(0)
    stop('the demo API or Caddy stopped.')


if __name__ == '__main__':
    if sys.argv[1:] == ['forget-data']:
        forget_data()
    elif sys.argv[1:]:
        say('usage: start.py [forget-data]')
        raise SystemExit(2)
    else:
        main()
