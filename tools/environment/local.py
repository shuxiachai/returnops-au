"""F.02 local configuration without putting a database password in shell history.

NFR-003/006/007, docs/02 infrastructure. Never changes existing configuration.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def initialise(path: Path) -> int:
    content = (
        "# Local disposable F.02 database; do not commit.\n"
        "POSTGRES_USER=returnops_dev\nPOSTGRES_DB=returnops_f02\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n"
        "DB_PORT=5433\nAPI_PORT=8000\n"
    )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Configuration already exists; left unchanged.")
        return 0
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print("Created ignored local configuration with a fresh password; no secret displayed.")
    return 0


def run_with_environment(path: Path, command: list[str]) -> int:
    if not command:
        raise ValueError("Provide a command after run.")
    from sqlalchemy.engine import URL

    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("Invalid local configuration line.")
        values[key.strip()] = value.strip()
    required = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DB_PORT", "API_PORT"}
    if not required.issubset(values) or any(not values[k] for k in required):
        raise ValueError("Local configuration is incomplete; see .env.example.")
    url = URL.create(
        "postgresql+psycopg", username=values["POSTGRES_USER"],
        password=values["POSTGRES_PASSWORD"], host="127.0.0.1",
        port=int(values["DB_PORT"]), database=values["POSTGRES_DB"],
    )
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if command[0] in ("python", "python3"):
        command = [sys.executable, *command[1:]]
    return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("action", choices=("init", "run"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "init":
            return initialise(args.env_file)
        return run_with_environment(args.env_file, args.command)
    except (OSError, ValueError, ImportError):
        print("Local environment command failed; check the file and installed dependencies. No configuration values were printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
