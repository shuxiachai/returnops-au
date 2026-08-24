# Sequence Diagram (Multi-Agent Governed Execution)

> **MBSE Model Type**: Dynamic Behavioral Sequence Diagram  
> **Course Requirement**: Agent-to-agent collaboration, human-in-the-loop gate, tool invocation  
> **Traceability**: [FR-001 ~ FR-012](file:///d:/AAA树下/硕士/26S2/5620/assignment/returnops-au/docs/04-requirements-and-backlog.md)

---

## 1. Mermaid Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer
    actor Founder as Human Founder
    participant Portal as Customer Portal (Next.js)
    participant API as ReturnOps API (FastAPI)
    participant Orch as LangGraph Orchestrator
    participant Intake as Intake Agent
    participant OrderAgent as Order Agent
    participant PolicyAgent as Policy & ACL Agent
    participant RemedyAgent as Remedy Planning Agent
    participant RiskAgent as Risk Reviewer Agent
    participant OpsAgent as Operations Agent
    participant Shopify as Mock Shopify Adapter
    participant AusPost as Mock AusPost Adapter
    participant DB as PostgreSQL & Audit Store

    Customer->>Portal: Submit claim (Message, Order# AU-1024, Photos)
    Portal->>API: POST /api/cases (payload)
    API->>DB: INSERT ReturnCase (status: SUBMITTED)
    API->>Orch: Start Investigation Workflow(case_id)
    
    %% Phase 1: Intake & Extraction
    Orch->>Intake: Process CustomerStatement
    Intake-->>Orch: Structured Facts (Order#, Item, Claim: Faulty)
    Orch->>DB: UPDATE ReturnCase (status: UNDER_INVESTIGATION)
    
    %% Phase 2: Order Lookup
    Orch->>OrderAgent: Verify Order(AU-1024)
    OrderAgent->>Shopify: Query Order & Line Items
    Shopify-->>OrderAgent: OrderSnapshot (Paid, Fulfilled 21 days ago, Breville Coffee Machine)
    OrderAgent-->>Orch: Order Facts Verified
    
    %% Phase 3: Policy RAG Grounding
    Orch->>PolicyAgent: Retrieve Applicable Policies (Faulty Product, Coffee Machine)
    PolicyAgent->>DB: Vector Search (Store Policy + ACCC Guarantees)
    DB-->>PolicyAgent: Retrieved Passages (14-day store limit vs ACL Statutory Warranty)
    PolicyAgent-->>Orch: Cited Passages with ACL Precedence
    
    %% Phase 4: Remedy Planning
    Orch->>RemedyAgent: Propose Remedy(Facts, Order, Policies)
    RemedyAgent-->>Orch: DecisionProposal (Remedy: Replacement/Repair, Confidence: 0.92, Cited ACCC)
    
    %% Phase 5: Risk & Governance Review
    Orch->>RiskAgent: Evaluate Proposal for Hallucinations & Conflicts
    RiskAgent-->>Orch: RiskAssessment(Pass, Confidence >= 0.80, No Tampering)
    Orch->>DB: UPDATE ReturnCase (status: AWAITING_APPROVAL)
    
    %% Phase 6: Human Gate
    Orch-->>Founder: Notify Pending Approval (Dashboard Alert)
    Founder->>Portal: Review Evidence, Citations & Proposed Remedy
    Founder->>API: POST /api/cases/{id}/approval (Decision: APPROVED, Scope: REPLACEMENT_LABEL)
    API->>DB: INSERT ApprovalRecord
    API->>Orch: Resume Workflow with Approval
    
    %% Phase 7: Governed Execution
    Orch->>OpsAgent: Execute Approved Command(ApprovalRecord)
    OpsAgent->>Shopify: Create Return Record
    Shopify-->>OpsAgent: ReturnID: RET-9981
    OpsAgent->>AusPost: Generate Return Shipping Label
    AusPost-->>OpsAgent: LabelPDF / Tracking#: AP-66723-AU
    OpsAgent-->>Orch: Tool Execution Success
    
    Orch->>DB: UPDATE ReturnCase (status: RESOLVED)
    Orch-->>Customer: Send Return Instructions & PDF Label
```

---

## 2. Key Architectural Highlights in the Sequence

1. **Deterministic State Synchronization**: Every agent step synchronizes its output to PostgreSQL via typed Pydantic contracts.
2. **Explicit Human Intervention**: The Orchestrator halts between Step 17 and Step 19, transitioning the case to `AWAITING_APPROVAL`. It only resumes upon receipt of a validated `ApprovalRecord`.
3. **Idempotent Tool Execution**: Step 21 and 23 attach a unique `idempotency_key` ensuring duplicate clicks by the founder do not issue double refunds or redundant shipping labels.
