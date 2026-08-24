from enum import Enum


class RequestType(str, Enum):
    """Supported customer request classifications."""
    FAULTY_PRODUCT = "faulty_product"
    WRONG_ITEM = "wrong_item"
    CHANGE_OF_MIND = "change_of_mind"
    OUT_OF_SCOPE = "out_of_scope"


class CaseStatus(str, Enum):
    """Authoritative lifecycle states of a ReturnCase."""
    SUBMITTED = "submitted"
    AWAITING_INFORMATION = "awaiting_information"
    UNDER_INVESTIGATION = "under_investigation"
    POLICY_ASSESSMENT = "policy_assessment"
    RISK_REVIEW = "risk_review"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTION_IN_PROGRESS = "action_in_progress"
    ACTION_FAILED = "action_failed"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class RemedyType(str, Enum):
    """Possible proposed and approved outcomes."""
    REFUND = "refund"
    REPLACEMENT = "replacement"
    REPAIR = "repair"
    STORE_CREDIT = "store_credit"
    REJECT = "reject"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class RiskLevel(str, Enum):
    """Categorical risk assessment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(str, Enum):
    """Reasons for risk flags or escalation."""
    MISSING_EVIDENCE = "missing_evidence"
    ORDER_MISMATCH = "order_mismatch"
    POLICY_AMBIGUITY = "policy_ambiguity"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    SUSPECTED_ABUSE = "suspected_abuse"
    HIGH_VALUE_THRESHOLD = "high_value_threshold"
    OUT_OF_SCOPE = "out_of_scope"


class EvidenceType(str, Enum):
    """Types of customer or system evidence."""
    PHOTO = "photo"
    VIDEO = "video"
    SERIAL_NUMBER = "serial_number"
    DIAGNOSTIC_TEXT = "diagnostic_text"
    RECEIPT = "receipt"
    COURIER_TRACKING = "courier_tracking"


class EvidenceVerificationStatus(str, Enum):
    """Verification state of a piece of evidence."""
    PENDING = "pending"
    VERIFIED = "verified"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"


class ApprovalDecision(str, Enum):
    """Human decision recorded in ApprovalRecord."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    ESCALATED = "escalated"


class ActorType(str, Enum):
    """Entities taking actions in the system."""
    CUSTOMER = "customer"
    INTAKE_AGENT = "intake_agent"
    ORDER_AGENT = "order_agent"
    POLICY_AGENT = "policy_agent"
    RESOLUTION_AGENT = "resolution_agent"
    RISK_AGENT = "risk_agent"
    OPERATIONS_AGENT = "operations_agent"
    FOUNDER = "founder"
    SYSTEM = "system"


class ToolCommandStatus(str, Enum):
    """Execution status of an external operational tool command."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED_NO_APPROVAL = "blocked_no_approval"
