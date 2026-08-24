# State Machine Diagram (ReturnCase Lifecycle)

> **MBSE Model Type**: Dynamic Behavioral State Machine  
> **Course Requirement**: System lifecycle processes, component states, exceptions, guard conditions  
> **Traceability**: [FR-001 ~ FR-012](file:///d:/AAA树下/硕士/26S2/5620/assignment/returnops-au/docs/04-requirements-and-backlog.md), [NFR-002, NFR-004](file:///d:/AAA树下/硕士/26S2/5620/assignment/returnops-au/docs/04-requirements-and-backlog.md)

---

## 1. Mermaid State Machine Model

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED : Customer submits request [FR-001]
    
    SUBMITTED --> AWAITING_INFORMATION : Missing mandatory fields [Order ID/Description missing]
    AWAITING_INFORMATION --> UNDER_INVESTIGATION : Customer provides clarification [FR-002]
    SUBMITTED --> UNDER_INVESTIGATION : Mandatory fields present [FR-002]
    
    UNDER_INVESTIGATION --> POLICY_ASSESSMENT : Order matched in commerce system [FR-003]
    UNDER_INVESTIGATION --> ESCALATED : Order not found / Abusive content / Fraud [FR-008]
    
    POLICY_ASSESSMENT --> AWAITING_INFORMATION : Diagnostic evidence gap detected [FR-005]
    POLICY_ASSESSMENT --> RISK_REVIEW : Policy & ACL passages retrieved [FR-006, FR-007]
    
    RISK_REVIEW --> POLICY_ASSESSMENT : Revision requested by Risk Reviewer [FR-008]
    RISK_REVIEW --> ESCALATED : Low confidence (<80%) / Policy conflict / Out of scope [FR-008]
    RISK_REVIEW --> AWAITING_APPROVAL : Independent review passed [FR-008]
    
    AWAITING_APPROVAL --> APPROVED : Human Founder approves remedy [FR-009]
    AWAITING_APPROVAL --> REJECTED : Human Founder rejects remedy [FR-009]
    AWAITING_APPROVAL --> ESCALATED : Human Founder flags for manual handling [FR-009]
    AWAITING_APPROVAL --> POLICY_ASSESSMENT : Human Founder requests AI re-investigation [FR-009]
    
    APPROVED --> ACTION_IN_PROGRESS : Operations Agent executes tool command [FR-010]
    ACTION_IN_PROGRESS --> ACTION_FAILED : Tool call timeout / API error [NFR-004]
    ACTION_FAILED --> ACTION_IN_PROGRESS : Safe idempotent retry (<3 attempts) [NFR-004]
    ACTION_FAILED --> ESCALATED : Retry limit reached [NFR-004]
    ACTION_IN_PROGRESS --> RESOLVED : Simulated return/label/refund confirmed [FR-010]
    
    RESOLVED --> CLOSED : Customer notified & audit logged [FR-011]
    REJECTED --> CLOSED : Rejection reason communicated [FR-011]
    ESCALATED --> CLOSED : Manual Founder resolution completed [FR-011]
    
    CLOSED --> [*]
```

---

## 2. Transition Guard Conditions & Invariants Table

| Source State | Target State | Trigger Event | Guard Condition / Rule |
| :--- | :--- | :--- | :--- |
| `SUBMITTED` | `UNDER_INVESTIGATION` | `IntakeCompleted` | `order_number != None` and `raw_text.length >= 10` |
| `SUBMITTED` | `AWAITING_INFORMATION` | `IntakeIncomplete` | `order_number == None` or ambiguous product name |
| `UNDER_INVESTIGATION` | `POLICY_ASSESSMENT` | `OrderLookupSuccess` | Order exists in Shopify, customer identity verified |
| `POLICY_ASSESSMENT` | `RISK_REVIEW` | `ProposalGenerated` | Proposal has $\ge 1$ cited policy/ACL passage |
| `RISK_REVIEW` | `AWAITING_APPROVAL` | `RiskReviewPassed` | No unverified claims, confidence $\ge 0.80$, no abuse flag |
| `AWAITING_APPROVAL` | `APPROVED` | `FounderApprove` | `ApprovalRecord` created with approver ID & scoped command |
| `APPROVED` | `ACTION_IN_PROGRESS` | `DispatchCommand` | `ToolCommand.approval_id_ref == active_approval.approval_id` |
| `ACTION_IN_PROGRESS` | `RESOLVED` | `ToolExecutionSuccess` | External API returns HTTP 200 / success payload |
