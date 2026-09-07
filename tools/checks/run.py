"""Run the existing F.02 offline or PostgreSQL checks without installing tools.

Traceability: F.02; NFR-001/006/007; the M-A/M-S model chains. Environment
checks establish infrastructure readiness, not business contract acceptance.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]


def build_steps(
    mode: str, baseline_ref: str = "HEAD", skip_baseline: bool = False
) -> list[tuple[str, list[str]]]:
    """Return argument arrays; no shell interpretation or implicit installation."""
    python = [sys.executable, "-B"]
    if mode == "offline":
        model_args = ["--skip-baseline"] if skip_baseline else ["--baseline-ref", baseline_ref]
        return [
            ("contract artifacts", python + ["-m", "unittest", "discover", "-s", "tests/contracts", "-p", "test_*.py", "-v"]),
            ("document/model references", python + ["tools/model-checks/check.py", *model_args]),
            ("model-checker regressions", python + ["-m", "unittest", "discover", "-s", "tools/model-checks", "-p", "test_*.py", "-v"]),
            ("check-runner regressions", python + ["-m", "unittest", "discover", "-s", "tools/checks", "-p", "test_*.py", "-v"]),
            ("Mermaid grammar", ["node", "tools/model-checks/check-mermaid.mjs"]),
        ]
    if mode == "environment":
        return [
            ("upgrade the configured test database", python + ["-m", "alembic", "upgrade", "head"]),
            ("report installed migration", python + ["-m", "alembic", "current"]),
            ("API/PostgreSQL environment tests", python + ["-m", "pytest", "tests/environment", "-q"]),
        ]
    raise ValueError(f"Unknown check group: {mode}")


def validate_database_url(value: str | None) -> None:
    """Fail before a migration when no explicit PostgreSQL test target is set.

    This validates connection shape, not database ownership or authorization.
    Never include the value (which may contain credentials) in diagnostics.
    """
    try:
        raw = value or ""
        parsed = urlsplit(raw)
        name = parsed.path[1:]
        valid = (
            parsed.scheme == "postgresql+psycopg"
            and bool(parsed.hostname)
            and bool(parsed.username)
            and (parsed.port is None or 1 <= parsed.port <= 65535)
            and "?" not in raw
            and "#" not in raw
            and len(name) <= 63
            and bool(re.fullmatch(r"returnops_f02(?:_[a-z0-9_]+)?", name))
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Set DATABASE_URL explicitly to a disposable PostgreSQL test database "
            "using postgresql+psycopg://.../returnops_f02 (or a returnops_f02_ "
            "name with lowercase ASCII letters, digits and underscores; 63 characters "
            "maximum), with host and user and without raw ?/# characters, before "
            "environment checks."
        )


def run_steps(steps: list[tuple[str, list[str]]], root: Path = ROOT) -> int:
    """Stream subprocess output and stop at the first failure."""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    for label, command in steps:
        print(f"RUN {label}", flush=True)
        try:
            result = subprocess.run(command, cwd=root, env=environment, check=False)
        except OSError:
            print(f"FAIL {label}: cannot start the required tool; check installed dependencies.", file=sys.stderr)
            return 1
        if result.returncode:
            print(f"FAIL {label}: exit {result.returncode}; remaining checks were not run.", file=sys.stderr)
            return result.returncode if result.returncode > 0 else 1
        print(f"PASS {label}", flush=True)
    print(f"Passed {len(steps)} check steps. See each check's scope and limitations above.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    groups = parser.add_subparsers(dest="mode", required=True)
    offline = groups.add_parser("offline", help="contract artifacts, model references and Mermaid grammar")
    baseline = offline.add_mutually_exclusive_group()
    baseline.add_argument("--baseline-ref", default="HEAD", help="existing local Git ref for the WBS comparison (default: HEAD)")
    baseline.add_argument("--skip-baseline", action="store_true", help="disclose and skip only the independent Git WBS comparison")
    groups.add_parser("environment", help="migrate DATABASE_URL and test API/PostgreSQL infrastructure")
    args = parser.parse_args(argv)
    if args.mode == "environment":
        try:
            validate_database_url(os.environ.get("DATABASE_URL"))
        except ValueError as exc:
            parser.error(str(exc))
        print("Environment checks migrate the explicitly configured database; use a disposable project test database.", flush=True)
    return run_steps(build_steps(args.mode, getattr(args, "baseline_ref", "HEAD"), getattr(args, "skip_baseline", False)))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
