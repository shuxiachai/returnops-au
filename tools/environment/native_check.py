"""F.02 native PostgreSQL evidence, not PostgreSQL 17/Compose acceptance.

Use the installed project Python; --bin selects existing PostgreSQL binaries.
Creates a fresh disposable cluster, runs the environment suite and TCP smoke
checks, then stops only its own API/cluster. Logs/data remain under repo/tmp.
Trace: NFR-003/006/007/008; docs/02 architecture and docs/10 environment plan.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True, help="PostgreSQL bin directory")
    parser.add_argument("--db-port", type=int, default=5433)
    parser.add_argument("--api-port", type=int, default=8000)
    args = parser.parse_args()
    suffix = ".exe" if os.name == "nt" else ""
    binaries = {name: args.bin.resolve() / (name + suffix)
                for name in ("postgres", "initdb", "pg_ctl", "createdb")}
    if any(not path.is_file() for path in binaries.values()):
        parser.error("Required PostgreSQL binaries are missing from --bin.")
    ports = (args.db_port, args.api_port)
    if len(set(ports)) != 2 or any(not 1024 <= port <= 65535 for port in ports):
        parser.error("Use two distinct unprivileged ports between 1024 and 65535.")
    try:
        for port in ports:
            with socket.socket() as probe:
                if os.name == "nt":
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind(("127.0.0.1", port))
        temporary = (ROOT / "tmp").resolve()
        if not temporary.is_relative_to(ROOT):
            parser.error("The temporary directory must remain inside this repository.")
        temporary.mkdir(exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="f02-native-", dir=temporary)).resolve()
    except OSError:
        parser.error("Ports must be unused and the repository tmp directory writable.")
    data, pwfile = work / "data", work / "init-password.txt"
    if not data.resolve().is_relative_to(work) or data.exists():
        parser.error("Refusing a pre-existing or out-of-scope cluster directory.")
    password = secrets.token_hex(32)
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("PG") and key.upper() not in
           {"DATABASE_URL", "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB"}}
    env.update(PGPASSWORD=password, PGCONNECT_TIMEOUT="3", PGPASSFILE=str(work / "unused.pgpass"),
               PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTEST_ADDOPTS="-p no:cacheprovider",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", NO_COLOR="1")
    env["DATABASE_URL"] = (
        f"postgresql+psycopg://returnops_native:{password}@127.0.0.1:"
        f"{args.db_port}/returnops_f02_native"
    )
    logs = [work / name for name in ("commands.log", "postgres.log", "api.log")]
    api, api_output = None, None
    success, cleanup_ok = False, True

    def run(command: list, timeout: int = 60, checked: bool = True) -> int:
        with logs[0].open("a", encoding="utf-8") as output:
            result = subprocess.run([str(part) for part in command], cwd=ROOT, env=env,
                                    stdout=output, stderr=subprocess.STDOUT, timeout=timeout,
                                    creationflags=FLAGS, check=False)
        if checked and result.returncode:
            raise RuntimeError("A native check command failed; consult retained logs.")
        return result.returncode

    def stop_cluster() -> bool:
        # A failed/timed-out pg_ctl start may still have launched this postmaster.
        if not data.exists():
            return True
        status = run([binaries["pg_ctl"], "-D", data, "status"], checked=False)
        if status == 0 or (data / "postmaster.pid").exists():
            return run([binaries["pg_ctl"], "-D", data, "-w", "-t", "30",
                        "-m", "fast", "stop"], timeout=40, checked=False) == 0
        return status in (3, 4)

    opener = build_opener(ProxyHandler({}))

    def response(path: str) -> tuple[int, dict]:
        try:
            reply = opener.open(f"http://127.0.0.1:{args.api_port}{path}", timeout=8)
        except HTTPError as error:
            reply = error
        with reply:
            body = reply.read(4096)
            if password.encode() in body:
                raise RuntimeError("HTTP response disclosed test credentials.")
            return reply.code, json.loads(body)

    try:
        descriptor = os.open(pwfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(password + "\n")
        run([binaries["postgres"], "--version"])
        run([binaries["initdb"], "-D", data, "-U", "returnops_native",
             "--auth=scram-sha-256", "--pwfile", pwfile, "--encoding=UTF8", "--locale=C"])
        pwfile.unlink()
        with (data / "postgresql.conf").open("a", encoding="utf-8") as output:
            output.write(f"\nlisten_addresses = '127.0.0.1'\nport = {args.db_port}\n"
                         "unix_socket_directories = ''\n")
        run([binaries["pg_ctl"], "-D", data, "-l", logs[1], "-w", "-t", "30", "start"], 40)
        run([binaries["createdb"], "-h", "127.0.0.1", "-p", args.db_port,
             "-U", "returnops_native", "-w", "--maintenance-db=postgres", "returnops_f02_native"])
        run([sys.executable, "-B", "tools/checks/run.py", "environment"], timeout=120)
        counts = re.findall(r"(\d+) passed", logs[0].read_text(encoding="utf-8", errors="replace"))
        if not counts:
            raise RuntimeError("Environment suite did not report a passing test count.")
        print(f"Native environment tests: {counts[-1]} passed.", flush=True)
        api_output = logs[2].open("w", encoding="utf-8")
        api = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn",
                                "returnops_api.main:create_app", "--factory", "--host",
                                "127.0.0.1", "--port", str(args.api_port), "--no-access-log"], cwd=ROOT, env=env,
                               stdout=api_output, stderr=subprocess.STDOUT, creationflags=FLAGS)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if api.poll() is not None:
                raise RuntimeError("The owned API process exited before readiness.")
            try:
                if response("/health/ready") == (200, {"status": "ready"}):
                    break
            except (URLError, TimeoutError, OSError):
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("API readiness timed out.")
        if api.poll() is not None or response("/health/live") != (200, {"status": "alive"}):
            raise RuntimeError("The owned API failed the liveness check.")
        print("Real TCP checks: live=200, ready=200.", flush=True)
        if not stop_cluster():
            raise RuntimeError("Could not stop the owned database for the outage check.")
        if (response("/health/ready") != (503, {"status": "not_ready"})
                or response("/health/live") != (200, {"status": "alive"})):
            raise RuntimeError("The owned API failed the database-outage check.")
        print("Owned database outage: ready=503, live=200.", flush=True)
        success = True
    except (Exception, KeyboardInterrupt):
        print("Native checks failed or were interrupted; inspect the retained logs.", file=sys.stderr)
    finally:
        try:
            if api is not None and api.poll() is None:
                api.terminate()
                try:
                    api.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api.kill()
                    api.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            cleanup_ok = False
        try:
            if api_output is not None:
                api_output.close()
        except OSError:
            cleanup_ok = False
        try:
            cleanup_ok = stop_cluster() and cleanup_ok
        except (OSError, subprocess.SubprocessError):
            cleanup_ok = False
        try:
            pwfile.unlink(missing_ok=True)
        except OSError:
            cleanup_ok = False
        for log in logs:
            try:
                if log.exists():
                    content = log.read_text(encoding="utf-8", errors="replace")
                    if password in content:
                        log.write_text(content.replace(password, "[REDACTED]"), encoding="utf-8")
                        print("A generated credential was redacted from a log; this run failed.")
                        success = False
            except OSError:
                cleanup_ok = False
        print(f"Retained cluster data and logs: {work}")
        print("Owned processes stopped." if cleanup_ok else "Cleanup incomplete; inspect this run's logs.")
    return 0 if success and cleanup_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
