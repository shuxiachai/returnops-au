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


def say(text):
    print(f'[demo start] {text}', flush=True)


def stop(text):
    say(f'STOP {text}')
    raise SystemExit(1)


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
            if time.monotonic() > deadline:
                stop('PostgreSQL did not accept a connection within 120 s.')
            time.sleep(3)


def run(step, arguments, environment):
    if subprocess.run(arguments, env=environment, cwd='/app').returncode != 0:
        stop(f'{step} failed; see the lines above.')


def wait_ready(process, url, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
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
    server, app = database_urls(os.environ.get('DATABASE_URL'))
    environment = {**os.environ, 'DATABASE_URL': app}
    say(f'resetting the {DATABASE} database')
    reset_database(server)
    run('alembic upgrade head', [sys.executable, '-m', 'alembic', 'upgrade', 'head'], environment)
    if SHOP.exists():
        shutil.rmtree(SHOP)
    run('demo provision', [sys.executable, '-m', 'returnops_api.demo', 'provision', '--private-dir', str(SHOP), *PROVISION], environment)

    api = subprocess.Popen([sys.executable, '-m', 'returnops_api.demo', 'serve', '--auth-file', str(SHOP / 'auth.json'),
                            '--port', '8000', '--fixed-proposal', '--founder-decisions'], env=environment, cwd='/app')
    if not wait_ready(api, 'http://127.0.0.1:8000/health/ready', 60):
        api.kill()
        stop('the demo API did not become ready within 60 s.')
    say('demo API ready on 127.0.0.1:8000; starting Caddy')
    web = subprocess.Popen(['caddy', 'run', '--config', '/app/Caddyfile', '--adapter', 'caddyfile'], cwd='/app')

    requested = []

    def forward(signum, _frame):
        requested.append(signum)
        for child in (web, api):
            if child.poll() is None:
                child.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)

    # Either process ending on its own ends the container with exit code 1, so Railway's
    # restart policy starts a fresh demonstration; a stop that Railway asked for exits 0.
    while api.poll() is None and web.poll() is None:
        time.sleep(1)
    for child in (web, api):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
    if requested:
        say('stopped on request')
        raise SystemExit(0)
    stop('the demo API or Caddy stopped.')


if __name__ == '__main__':
    main()
