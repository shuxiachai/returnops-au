from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator

from .enums import (
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(BaseModel):
    """Minimal customer entity."""
    customer_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str
    phone: Optional[str] = None


class LineItem(BaseModel):
    """An item within an order snapshot."""
    item_id: str
    sku: str
    title: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)
    returnable: bool = True


class OrderSnapshot(BaseModel):
    """Snapshot of order facts queried from commerce provider."""
    order_id: str
    order_number: str
    customer: Customer
    line_items: List[LineItem]
    order_date: datetime
    fulfillment_date: Optional[datetime] = None
    payment_status: str = "paid"  # e.g., 'paid', 'refunded', 'partially_refunded'
    fulfillment_status: str = "fulfilled"  # e.g., 'fulfilled', 'unfulfilled'
    total_amount: float = Field(ge=0.0)
    currency: str = "AUD"
    shipping_address: Optional[Dict[str, str]] = None


class CustomerStatement(BaseModel):
    """Raw customer message or structured clarification."""
    statement_id: str = Field(default_factory=lambda: str(uuid4()))
    raw_text: str
    submitted_at: datetime = Field(default_factory=_utcnow)
    extracted_order_number: Optional[str] = None
    extracted_item_title: Optional[str] = None
    claimed_issue: Optional[str] = None
    requested_remedy: Optional[str] = None


class EvidenceItem(BaseModel):
    """Evidence supplied by customer or diagnostic tests."""
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    type: EvidenceType
    uri_or_content: str
    description: str
    verification_status: EvidenceVerificationStatus = EvidenceVerificationStatus.PENDING
    verified_by: Optional[str] = None
    verification_notes: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=_utcnow)


class PolicyPassage(BaseModel):
    """Retrieved store policy or ACCC statutory guidance passage with location."""
    source_id: str
    title: str
    url: Optional[str] = None
    section: str
    text_snippet: str
    is_statutory: bool = False  # True if ACCC/ACL, False if Store Policy
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)


class RiskFinding(BaseModel):
    """Risk flag or contradiction detected during automated review."""
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    risk_level: RiskLevel
    category: RiskCategory
    reason: str
    suggested_action: str
    detected_at: datetime = Field(default_factory=_utcnow)


class DecisionProposal(BaseModel):
    """Structured resolution proposal produced by Resolution Planner."""
    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    request_type: RequestType
    recommended_remedy: RemedyType
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    cited_passages: List[PolicyPassage] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    alternative_remedies: List[RemedyType] = Field(default_factory=list)
    estimated_cost: float = Field(ge=0.0, default=0.0)
    requires_escalation: bool = False
    escalation_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class ApprovalRecord(BaseModel):
    """Mandatory human decision authorizing high-impact actions."""
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    approver: str  # e.g., 'founder@store.com.au'
    decision: ApprovalDecision
    permitted_remedy: RemedyType
    max_approved_amount: Optional[float] = Field(ge=0.0, default=None)
    permitted_command: str  # e.g., 'create_return_label', 'issue_refund'
    notes: Optional[str] = None
    decided_at: datetime = Field(default_factory=_utcnow)
    expires_at: Optional[datetime] = None


class ToolCommand(BaseModel):
    """Idempotent operational command requested or executed."""
    command_id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str
    tool_name: str  # e.g., 'mock_shopify.create_return', 'mock_auspost.generate_label'
    parameters: Dict[str, Any]
    status: ToolCommandStatus = ToolCommandStatus.PENDING
    approval_id_ref: Optional[str] = None  # Must link to an ApprovalRecord for high-impact tools
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    executed_at: Optional[datetime] = None


class AuditEvent(BaseModel):
    """Immutable audit trail record."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    timestamp: datetime = Field(default_factory=_utcnow)
    actor_type: ActorType
    actor_id: str
    action: str  # e.g., 'STATE_TRANSITION', 'PROPOSAL_GENERATED', 'FOUNDER_APPROVED'
    previous_state: Optional[CaseStatus] = None
    new_state: Optional[CaseStatus] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class ReturnCase(BaseModel):
    """Aggregate Root representing an end-to-end customer return journey."""
    case_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    status: CaseStatus = CaseStatus.SUBMITTED

    # Customer & Statement History
    customer: Optional[Customer] = None
    statements: List[CustomerStatement] = Field(default_factory=list)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)

    # Order Facts
    order_snapshot: Optional[OrderSnapshot] = None
    matched_line_item: Optional[LineItem] = None

    # Analysis & Grounding
    classified_request_type: Optional[RequestType] = None
    retrieved_policies: List[PolicyPassage] = Field(default_factory=list)
    proposals: List[DecisionProposal] = Field(default_factory=list)
    risk_findings: List[RiskFinding] = Field(default_factory=list)

    # Human Gate & Execution
    approvals: List[ApprovalRecord] = Field(default_factory=list)
    tool_commands: List[ToolCommand] = Field(default_factory=list)
    audit_trail: List[AuditEvent] = Field(default_factory=list)

    @property
    def latest_proposal(self) -> Optional[DecisionProposal]:
        return self.proposals[-1] if self.proposals else None

    @property
    def active_approval(self) -> Optional[ApprovalRecord]:
        for app in reversed(self.approvals):
            if app.decision == ApprovalDecision.APPROVED:
                return app
        return None
