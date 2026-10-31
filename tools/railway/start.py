"""Railway container entry for the Week 13 demonstration (docs/46 section 9, docs/15 PD-03).

Every start is a fresh synthetic demonstration, the same as `demo.ps1 fresh` on the demo
machine: the returnops_f02 database is dropped and created again, migrated, the demo store
is provisioned into a private folder (README step 3), the demo API serves on 127.0.0.1:8000
and Caddy serves the web build and proxies /v1 and /health on Railway's PORT.

DATABASE_URL is the postgresql:// URL of the project's PostgreSQL 17 service (README); the app
uses its own returnops_f02 database on that server. No credential or token is printed; the
presenter copies the sessions with `demo.ps1 cloud-tokens`. R.05.b; NFR-003/009.
"""
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
SHOP = Path('/app/private/demo-shop')
PROVISION = ['--store', 'synthetic_au_store', '--customer-one', 'synthetic_customer_a',
             '--customer-two', 'synthetic_customer_b', '--founder', 'synthetic_founder',
             '--order-investigation', '--fixed-proposal', '--founder-manual']
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


def run(step, arguments, environment):
    if subprocess.run(arguments, env=environment, cwd='/app').returncode != 0:
        stop(f'{step} failed; see the lines above.')


def wait_ready(process, url, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None or REQUESTED:
            return False
        try:
            with urllib.request.urlopen(url, timeout=3) as answer:
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
    say(f'resetting the {DATABASE} database')
    reset_database(server)
    finish_if_requested()
    run('alembic upgrade head', [sys.executable, '-m', 'alembic', 'upgrade', 'head'], environment)
    finish_if_requested()
    if SHOP.exists():
        shutil.rmtree(SHOP)
    run('demo provision', [sys.executable, '-m', 'returnops_api.demo', 'provision', '--private-dir', str(SHOP), *PROVISION], environment)
    finish_if_requested()

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
    while api.poll() is None and web.poll() is None:
        time.sleep(1)
    end_children()
    if REQUESTED:
        say('stopped on request')
        raise SystemExit(0)
    stop('the demo API or Caddy stopped.')


if __name__ == '__main__':
    main()
