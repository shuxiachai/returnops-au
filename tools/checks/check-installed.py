"""Build/install locally without dependency resolution; import outside checkout.

The current interpreter must already have the locked build/runtime dependencies.
The wheel build may write ignored build metadata in this checkout. Installation
and import use an owned temporary directory; no shared environment is changed.
"""

from pathlib import Path
import os
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="returnops-package-") as temporary:
        workspace = Path(temporary)
        wheels = workspace / "wheels"
        installed = workspace / "installed"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["PIP_NO_INDEX"] = "1"
        commands = [
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheels), str(ROOT)],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=workspace, env=environment, check=False)
            if result.returncode:
                return result.returncode
        wheel, = wheels.glob("returnops_au-*.whl")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(installed), str(wheel)], cwd=workspace, env=environment, check=False)
        if result.returncode:
            return result.returncode
        probe = Path(__file__).with_name("probe-installed.py").read_text(encoding="utf-8")
        result = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(installed)], cwd=workspace, env=environment, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
