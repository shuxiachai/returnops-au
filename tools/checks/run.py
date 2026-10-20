"""Run the existing F.02 offline or PostgreSQL checks without installing tools.

Traceability: F.02; NFR-001/006/007; the M-A/M-S model chains. Environment
checks establish infrastructure readiness, not business contract acceptance.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_GROUPS = {
    "execution": 13,
    "founder_manual": 6,
    "founder_revision": 5,
    "label_artifact": 8,
    "label_execution_bridge": 8,
    "lifecycle_core": 14,
    "notification": 13,
}
PARTS = ("foundation", *LIFECYCLE_GROUPS)
MANIFEST = Path("tools/checks/lifecycle-groups.json")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def _collection_inventory(root: Path) -> set[str]:
    """Inspect source paths/configuration only; never import or collect tests."""
    expected_options = {
        "testpaths": ["tests/environment", "tests/security", "tests/storage",
                      "tests/customer", "tests/orders", "tests/investigation",
                      "tests/founder", "tests/lifecycle"],
        "addopts": "--strict-markers",
        "markers": ["database: requires an explicitly configured disposable PostgreSQL database"],
    }
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    if config.get("tool", {}).get("pytest") != {"ini_options": expected_options}:
        raise ValueError("Unsupported pytest collection configuration.")
    if any(os.environ.get(key) for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")):
        raise ValueError("Pytest environment overrides are unsupported for CI parts.")
    lifecycle = root / "tests/lifecycle"
    if not lifecycle.is_dir():
        raise ValueError("Missing lifecycle test directory.")
    directories = [root, root / "tests"]
    inventory = set()
    for directory, subdirs, files in os.walk(lifecycle, followlinks=False):
        current = Path(directory)
        directories.append(current)
        for name in [*subdirs, *files]:
            path = current / name
            if path.is_symlink() or path.is_junction():
                raise ValueError("Linked lifecycle paths are unsupported.")
        for name in files:
            if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")):
                inventory.add((current / name).relative_to(root).as_posix())
    for directory in directories:
        if directory.is_symlink() or directory.is_junction():
            raise ValueError("Linked test directories are unsupported.")
        config_names = ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml",
                        "tox.ini", "setup.cfg")
        if any((directory / name).exists() for name in config_names):
            raise ValueError("Additional pytest configuration is unsupported.")
        if directory != root and (directory / "pyproject.toml").exists():
            raise ValueError("Nested pytest configuration is unsupported.")
        conftest = directory / "conftest.py"
        if conftest.exists():
            tree = ast.parse(conftest.read_text(encoding="utf-8"))
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            names.update(node.name for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.update(alias.asname or alias.name.split(".")[0]
                                 for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if any(alias.name == "*" for alias in node.names):
                        raise ValueError("Conftest star imports are unsupported.")
                    names.update(alias.asname or alias.name for alias in node.names)
            if any(name.startswith("pytest_") or name.startswith("collect_ignore")
                   for name in names):
                raise ValueError("Custom conftest collection hooks are unsupported.")
    return inventory


def load_lifecycle_groups(root: Path | None = None) -> dict[str, list[str]]:
    """Fail closed on manifest drift; node-union acceptance remains a CI review."""
    root = (ROOT if root is None else root).resolve()
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"),
                              object_pairs_hook=_unique_object)
        if (type(manifest) is not dict or set(manifest) != {"version", "groups"}
                or type(manifest["version"]) is not int or manifest["version"] != 1
                or type(manifest["groups"]) is not dict
                or set(manifest["groups"]) != set(LIFECYCLE_GROUPS)):
            raise ValueError("Invalid lifecycle manifest structure.")
        groups = manifest["groups"]
        selected = []
        for group, count in LIFECYCLE_GROUPS.items():
            files = groups[group]
            if type(files) is not list or len(files) != count:
                raise ValueError("Invalid lifecycle group size.")
            for name in files:
                if type(name) is not str:
                    raise ValueError("Invalid lifecycle file path.")
                path = PurePosixPath(name)
                if (path.as_posix() != name or path.is_absolute() or "\\" in name
                        or ":" in name or ".." in path.parts or "\x00" in name
                        or path.parts[:2] != ("tests", "lifecycle")
                        or not name.endswith(".py")
                        or not (path.name.startswith("test_") or path.name.endswith("_test.py"))):
                    raise ValueError("Noncanonical lifecycle file path.")
                physical = root / name
                if not physical.is_file() or not physical.resolve().is_relative_to(root):
                    raise ValueError("Missing or external lifecycle file.")
                selected.append(name)
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate lifecycle file.")
        if set(selected) != _collection_inventory(root):
            raise ValueError("Lifecycle manifest does not match the recursive test inventory.")
        return {name: groups[name] for name in LIFECYCLE_GROUPS}
    except (OSError, ValueError, SyntaxError, TypeError, AttributeError) as exc:
        # Do not disclose raw JSON, configuration values, or local path details.
        raise ValueError("Invalid lifecycle manifest or unsupported collection configuration.") from exc


def ci_matrix(root: Path | None = None) -> dict:
    groups = load_lifecycle_groups(root)
    return {"include": [{"part": part} for part in ("foundation", *groups)]}


def validate_ci_needs(raw: str, matrix: dict) -> None:
    """Require all dependency results and the exact eight-part plan."""
    try:
        needs = json.loads(raw, object_pairs_hook=_unique_object)
        required = {"offline-contract-models", "environment-plan", "environment-checks"}
        if type(needs) is not dict or set(needs) != required:
            raise ValueError("Missing CI dependency.")
        for job in needs.values():
            if (type(job) is not dict or set(job) != {"result", "outputs"}
                    or job["result"] != "success" or type(job["outputs"]) is not dict):
                raise ValueError("Unsuccessful CI dependency.")
        planned = json.loads(needs["environment-plan"]["outputs"]["matrix"],
                             object_pairs_hook=_unique_object)
        if planned != matrix:
            raise ValueError("Unexpected CI matrix.")
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("CI gate requires successful offline, plan and all eight environment parts.") from exc


def build_steps(
    mode: str, baseline_ref: str = "HEAD", skip_baseline: bool = False,
    *, part: str | None = None, root: Path | None = None,
) -> list[tuple[str, list[str]]]:
    """Return argument arrays; no shell interpretation or implicit installation."""
    python = [sys.executable, "-B"]
    if part is not None and (mode != "environment" or part not in PARTS):
        raise ValueError("Unsupported environment part.")
    if mode == "offline":
        model_args = ["--skip-baseline"] if skip_baseline else ["--baseline-ref", baseline_ref]
        return [
            ("contract artifacts", python + ["-m", "unittest", "discover", "-s", "tests/contracts", "-p", "test_*.py", "-v"]),
            ("document/model references", python + ["tools/model-checks/check.py", *model_args]),
            ("model-checker regressions", python + ["-m", "unittest", "discover", "-s", "tools/model-checks", "-p", "test_*.py", "-v"]),
            ("check-runner regressions", python + ["-m", "unittest", "discover", "-s", "tools/checks", "-p", "test_*.py", "-v"]),
            ("Mermaid grammar", ["node", "tools/model-checks/check-mermaid.mjs"]),
            ("synthetic order provider", python + ["-m", "pytest", "tests/orders", "-q"]),
        ]
    if mode == "environment":
        steps = [
            ("upgrade the configured test database", python + ["-m", "alembic", "upgrade", "head"]),
            ("report installed migration", python + ["-m", "alembic", "current"]),
            ("API/PostgreSQL environment tests", python + ["-m", "pytest", "tests/environment", "-q"]),
            ("initial-record PostgreSQL storage tests", python + ["-m", "pytest", "tests/storage", "-q"]),
            ("customer HTTP, concurrency and retention tests", python + ["-m", "pytest", "tests/customer", "-q"]),
            ("order investigation PostgreSQL and real TCP tests", python + ["-m", "pytest", "tests/investigation", "-q"]),
            ("Founder read PostgreSQL and real TCP tests", python + ["-m", "pytest", "tests/founder", "-q"]),
            ("Lifecycle guard PostgreSQL component tests", python + ["-m", "pytest", "tests/lifecycle", "-q", "--tb=short", "-x", "-p", "tools.checks.lifecycle_progress"]),
        ]
        if part is None:
            return steps
        groups = load_lifecycle_groups(root)
        if part == "foundation":
            return steps[:-1]
        return steps[:2] + [
            (f"Lifecycle {part} PostgreSQL component tests",
             python + ["-m", "pytest", *groups[part], "-q", "--tb=short", "-x",
                       "-p", "tools.checks.lifecycle_progress"]),
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
    environment = groups.add_parser("environment", help="migrate DATABASE_URL and test API/PostgreSQL infrastructure")
    environment.add_argument("--part", choices=PARTS, help="one validated CI part; omit for all eight existing steps")
    groups.add_parser("ci-matrix", help="validate lifecycle file coverage and print the eight CI parts")
    groups.add_parser("ci-gate", help="require strict success of all CI dependencies from CI_NEEDS_JSON")
    args = parser.parse_args(argv)
    try:
        if args.mode in {"ci-matrix", "ci-gate"}:
            matrix = ci_matrix()
            if args.mode == "ci-matrix":
                print(json.dumps(matrix, separators=(",", ":")))
            else:
                validate_ci_needs(os.environ.get("CI_NEEDS_JSON", ""), matrix)
                print("PASS offline, plan and all eight environment parts.")
            return 0
        steps = build_steps(args.mode, getattr(args, "baseline_ref", "HEAD"),
                            getattr(args, "skip_baseline", False),
                            part=getattr(args, "part", None))
    except ValueError as exc:
        parser.error(str(exc))
    if args.mode == "environment":
        try:
            validate_database_url(os.environ.get("DATABASE_URL"))
        except ValueError as exc:
            parser.error(str(exc))
        print("Environment checks migrate the explicitly configured database; use a disposable project test database.", flush=True)
    return run_steps(steps)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
