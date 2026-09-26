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
        probe = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import returnops_api, returnops_api.security, returnops_domain
from returnops_domain import StatementContent
from returnops_domain.storage import InitialRecordUnitOfWork
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.retention import RetentionService
from returnops_domain.wire import create_request
from returnops_domain.evidence_validation import validate_evidence
from returnops_api.main import create_app
installed = Path(sys.argv[1]).resolve()
for package in (returnops_api, returnops_api.security, returnops_domain):
    assert Path(package.__file__).resolve().is_relative_to(installed)
assert 'experiments' not in sys.modules
assert create_request({'original_message':'package probe'})['requested_outcome']=='UNSPECIFIED'
value = StatementContent('statement_probe', '\\x00\\ud800', 'OTHER', None)
assert value.raw_text == '\\x00\\ud800'
print('PASS installed API/security/domain/storage imports outside checkout')
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(installed)], cwd=workspace, env=environment, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
