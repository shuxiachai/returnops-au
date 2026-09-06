# State Machine Diagram (ReturnCase Lifecycle)

> **MBSE Model Type**: Dynamic Behavioral State Machine  
> **Course Requirement**: System lifecycle processes, component states, exceptions, guard conditions  
> **Traceability**: [FR-001 to FR-012; NFR-002, NFR-004, and NFR-009](../04-requirements-and-backlog.md)

---

## 1. Mermaid State Machine Model

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED : Customer submits request [FR-001]
    
    SUBMITTED --> AWAITING_INFORMATION : Missing mandatory fields [Order ID/Description missing]
    AWAITING_INFORMATION --> UNDER_INVESTIGATION : Customer provides clarification [FR-002]
    SUBMITTED --> UNDER_INVESTIGATION : Mandatory fields present [FR-002]
    
    UNDER_INVESTIGATION --> POLICY_ASSESSMENT : Order matched in commerce system [FR-003]
    UNDER_INVESTIGATION --> AWAITING_INFORMATION : Order identifier missing / likely correctable [FR-003]
    UNDER_INVESTIGATION --> UNDER_INVESTIGATION : Provider timeout / safe retry below limit [FR-003, NFR-004]
    UNDER_INVESTIGATION --> ESCALATED : Confirmed conflict / Unsafe content / Provider retry limit [FR-003, FR-008, NFR-009]
    
    POLICY_ASSESSMENT --> AWAITING_INFORMATION : Diagnostic evidence gap detected [FR-005]
    POLICY_ASSESSMENT --> RISK_REVIEW : Policy & ACL passages retrieved [FR-006, FR-007]
    
    RISK_REVIEW --> POLICY_ASSESSMENT : Revision requested by Risk Reviewer [FR-008]
    RISK_REVIEW --> ESCALATED : Low confidence (<80%) / Policy conflict / Out of scope [FR-008]
    RISK_REVIEW --> AWAITING_APPROVAL : Independent review passed [FR-008]
    
    AWAITING_APPROVAL --> APPROVED : Human Founder approves remedy [FR-009]
    AWAITING_APPROVAL --> REJECTED : Human Founder rejects remedy [FR-009]
    AWAITING_APPROVAL --> ESCALATED : Human Founder flags for manual handling [FR-009]
    AWAITING_APPROVAL --> POLICY_ASSESSMENT : Human Founder requests AI re-investigation [FR-009]
    
    APPROVED --> ACTION_IN_PROGRESS : Exact-scope approval and allowlist guards pass [FR-010, NFR-002, NFR-009]
    ACTION_IN_PROGRESS --> ACTION_FAILED : Tool call timeout / API error [NFR-004]
    ACTION_FAILED --> ACTION_IN_PROGRESS : Safe idempotent retry (<3 attempts) [NFR-004]
    ACTION_FAILED --> ESCALATED : Retry limit reached [NFR-004]
    ACTION_IN_PROGRESS --> RESOLVED : Simulated return/label/refund confirmed [FR-010]
    
    RESOLVED --> CLOSED : Approved outcome notified and audited [FR-010, FR-011]
    REJECTED --> CLOSED : Founder-approved rejection outcome notified and audited [FR-009, FR-011]
    ESCALATED --> CLOSED : Founder records and notifies manual outcome [FR-009, FR-011]
    
    CLOSED --> [*]
```

---

## 2. Transition Guard Conditions & Invariants Table

| Source State | Target State | Trigger Event | Guard Condition / Rule |
| :--- | :--- | :--- | :--- |
| `SUBMITTED` | `UNDER_INVESTIGATION` | `IntakeCompleted` | `order_number != None` and `raw_text.length >= 10` |
| `SUBMITTED` | `AWAITING_INFORMATION` | `IntakeIncomplete` | `order_number == None` or ambiguous product name |
| `UNDER_INVESTIGATION` | `POLICY_ASSESSMENT` | `OrderLookupSuccess` | Order exists in Shopify, customer identity verified |
| `UNDER_INVESTIGATION` | `AWAITING_INFORMATION` | `OrderLookupNeedsCorrection` | Order identifier is missing, malformed, or plausibly mistyped; no confirmed mismatch |
| `UNDER_INVESTIGATION` | `ESCALATED` | `OrderConflictConfirmed` | A conflict, suspected abuse, or unsafe content remains after clarification |
| `UNDER_INVESTIGATION` | `UNDER_INVESTIGATION` | `OrderProviderRetry` | Provider failure is auditable, no snapshot is invented, and retry count remains below the configured limit |
| `UNDER_INVESTIGATION` | `ESCALATED` | `OrderProviderRetryLimitReached` | Provider failure remains after the configured retry limit |
| `POLICY_ASSESSMENT` | `RISK_REVIEW` | `ProposalGenerated` | Proposal has $\ge 1$ cited policy/ACL passage |
| `RISK_REVIEW` | `AWAITING_APPROVAL` | `RiskReviewPassed` | No unsupported claim, citation/source conflict, prompt injection, out-of-scope result, or unresolved high-risk finding; confidence $\ge 0.80$ |
| `AWAITING_APPROVAL` | `APPROVED` | `FounderApprove` | Trusted actor is authorised; case and proposal version are current; exact command set, amount limit, reason, and expiry are complete |
| `APPROVED` | `ACTION_IN_PROGRESS` | `DispatchCommand` | Approval decision is approved, unexpired, and bound to this case and current proposal; every typed command and amount exactly matches scope, is allowlisted, and has a stable idempotency key |
| `ACTION_IN_PROGRESS` | `RESOLVED` | `ToolExecutionSuccess` | External API returns HTTP 200 / success payload |
