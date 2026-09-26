"""Execute via an isolated interpreter outside checkout, or stdin in the image."""
import sys
import sysconfig
from pathlib import Path

installed = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else Path(sysconfig.get_path("purelib")).resolve()
if len(sys.argv) == 2:
    sys.path.insert(0, str(installed))
import returnops_api, returnops_api.security, returnops_domain
from returnops_domain import StatementContent
from returnops_domain.storage import InitialRecordUnitOfWork
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.intake_processor import IntakeProcessor
from returnops_domain.retention import RetentionService
from returnops_domain.wire import create_request
from returnops_domain.evidence_validation import validate_evidence
from returnops_domain.mock_orders import MockOrderProvider, load_builtin_catalogue
from returnops_domain.order_ports import OrderLookupError, OrderReadContext
from returnops_api.main import create_app

for package in (returnops_api, returnops_api.security, returnops_domain):
    assert Path(package.__file__).resolve().is_relative_to(installed)
assert "experiments" not in sys.modules
assert create_request({"original_message": "package probe"})["requested_outcome"] == "UNSPECIFIED"
value = StatementContent("statement_probe", "\x00\ud800", "OTHER", None)
assert value.raw_text == "\x00\ud800"

catalogue = load_builtin_catalogue()
class SyntheticProbeResolver:
    """Only this explicit synthetic case/version is allowed; no DB/F03 claim."""
    def resolve(self, case_id, input_version):
        if case_id != "synthetic_probe_case":
            raise OrderLookupError("CASE_ACCESS_DENIED")
        if input_version != 1:
            raise OrderLookupError("STALE_INPUT")
        return OrderReadContext(case_id, input_version, "synthetic_au_store", "synthetic_customer_a",
            "package_order_probe", catalogue.metadata.provider_id, True)

provider = MockOrderProvider(SyntheticProbeResolver(), catalogue, service_id="package_order_probe")
result = provider.lookup({"case_id": "synthetic_probe_case", "input_version": 1, "order_reference": "SYN-1001"})
assert result["status"] == "MATCHED" and result["input_version"] == 1
assert result["snapshot"]["snapshot_id"] == "synthetic_snapshot_1001"
assert result["snapshot"]["retrieved_at"] == "2026-09-20T00:00:00Z"
assert len(catalogue.metadata.dataset_sha256) == 64
print("PASS installed API/security/domain/storage imports outside checkout")
print("PASS installed synthetic order resource and scoped lookup (A1.04)")
