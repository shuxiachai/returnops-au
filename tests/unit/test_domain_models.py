import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError

from packages.domain.enums import (
    ActorType,
    ApprovalDecision,
    CaseStatus,
    EvidenceType,
    EvidenceVerificationStatus,
    RemedyType,
    RequestType,
    RiskCategory,
    RiskLevel,
    ToolCommandStatus,
)
from packages.domain.models import (
    ApprovalRecord,
    AuditEvent,
    Customer,
    CustomerStatement,
    DecisionProposal,
    EvidenceItem,
    LineItem,
    OrderSnapshot,
    PolicyPassage,
    ReturnCase,
    RiskFinding,
    ToolCommand,
)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_load_order_fixtures():
    """Verify orders.json fixture parses into OrderSnapshot domain models."""
    orders_file = FIXTURES_DIR / "orders.json"
    assert orders_file.exists()

    with open(orders_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 3
    for raw_order in data:
        order = OrderSnapshot(**raw_order)
        assert order.order_number.startswith("AU-")
        assert len(order.line_items) > 0
        assert order.total_amount > 0


def test_load_policy_fixtures():
    """Verify policies.json fixture parses into PolicyPassage domain models."""
    policy_file = FIXTURES_DIR / "policies.json"
    assert policy_file.exists()

    with open(policy_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 4
    statutory_count = 0
    for raw_policy in data:
        passage = PolicyPassage(**raw_policy)
        assert len(passage.text_snippet) > 20
        if passage.is_statutory:
            statutory_count += 1

    assert statutory_count >= 3  # At least 3 ACCC ACL statutory passages


def test_return_case_lifecycle_invariants():
    """Verify ReturnCase aggregate root lifecycle, proposals, and approvals."""
    # 1. Customer submits case
    cust = Customer(name="Sarah Jenkins", email="sarah.j@example.com.au")
    stmt = CustomerStatement(
        raw_text="Coffee machine stopped working after 3 weeks. Order AU-1024.",
        extracted_order_number="AU-1024",
    )
    case = ReturnCase(
        customer=cust,
        statements=[stmt],
        status=CaseStatus.SUBMITTED,
    )
    assert case.status == CaseStatus.SUBMITTED
    assert len(case.statements) == 1
    assert case.latest_proposal is None
    assert case.active_approval is None

    # 2. Attach proposal
    passage = PolicyPassage(
        source_id="ACCC-ACL-001",
        title="ACCC Guarantees",
        section="Acceptable Quality",
        text_snippet="Consumer guarantees apply automatically.",
        is_statutory=True,
    )
    proposal = DecisionProposal(
        request_type=RequestType.FAULTY_PRODUCT,
        recommended_remedy=RemedyType.REPLACEMENT,
        confidence_score=0.92,
        rationale="Product died within 3 weeks; statutory consumer guarantees apply.",
        cited_passages=[passage],
    )
    case.proposals.append(proposal)
    case.status = CaseStatus.AWAITING_APPROVAL
    assert case.latest_proposal.recommended_remedy == RemedyType.REPLACEMENT
    assert case.latest_proposal.confidence_score == 0.92

    # 3. Attach human approval
    approval = ApprovalRecord(
        case_id=case.case_id,
        approver="founder@store.com.au",
        decision=ApprovalDecision.APPROVED,
        permitted_remedy=RemedyType.REPLACEMENT,
        permitted_command="mock_auspost.generate_return_label",
        notes="Approved under ACCC statutory guarantee.",
    )
    case.approvals.append(approval)
    case.status = CaseStatus.APPROVED
    assert case.active_approval is not None
    assert case.active_approval.decision == ApprovalDecision.APPROVED

    # 4. Dispatch tool command scoped to approval
    command = ToolCommand(
        idempotency_key=f"ret-lbl-{case.case_id}",
        tool_name="mock_auspost.generate_return_label",
        parameters={"order_id": "AU-1024", "customer_email": cust.email},
        approval_id_ref=case.active_approval.approval_id,
        status=ToolCommandStatus.PENDING,
    )
    case.tool_commands.append(command)
    assert case.tool_commands[0].approval_id_ref == approval.approval_id


def test_schema_validation_failures():
    """Verify Pydantic raises validation errors for invalid constraints."""
    with pytest.raises(ValidationError):
        # Negative quantity should fail validation
        LineItem(
            item_id="item_1",
            sku="SKU-1",
            title="Invalid Item",
            quantity=-1,
            unit_price=100.0,
        )

    with pytest.raises(ValidationError):
        # Negative confidence score should fail validation
        DecisionProposal(
            request_type=RequestType.FAULTY_PRODUCT,
            recommended_remedy=RemedyType.REFUND,
            confidence_score=1.5,  # Must be <= 1.0
            rationale="Invalid score",
        )
