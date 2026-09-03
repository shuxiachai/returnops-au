# System Design

## 1. Architectural drivers

The architecture is driven by seven properties:

1. Traceability: every recommendation must point to case evidence and sources.
2. Human accountability: high-impact actions require explicit approval.
3. Determinism at boundaries: money, inventory, and case state use rules and
   typed commands rather than free-form model output.
4. Auditability: model calls, retrieved passages, decisions, approvals, and tool
   results are recorded.
5. Replaceability: LLM, retrieval, commerce, and logistics providers sit behind
   interfaces.
6. Evaluability: each agent and the end-to-end workflow can be tested against a
   labelled case set.
7. Security and AI robustness: untrusted customer and retrieved content cannot
   grant authority, change workflow policy, expose secrets, or bypass tool and
   approval controls.

## 2. Proposed architecture

```mermaid
flowchart TB
    C["Customer portal"]
    F["Founder operations dashboard"]
    API["Application API"]
    DOM["Domain service and authoritative case state"]
    COORD["Customer Case Coordinator Agent"]
    ASSESS["Returns Assessment Agent"]
    REVIEW["Compliance & Risk Reviewer Agent"]
    GUARD["Approval Guard, deterministic approval and allowlist checks"]
    OPS["Deterministic Operations Service"]
    KB["Versioned policy knowledge base"]
    DB[("PostgreSQL and audit store")]
    COM["Mock order provider, read-only order snapshot"]
    LOG["Mock returns and logistics provider"]
    NOTIFY["Notification adapter"]
    OBS["Evaluation and observability"]

    C --> API
    F --> API
    API --> DOM
    DOM --> COORD
    COORD --> ASSESS
    COORD -->|Missing information| C
    ASSESS --> COM
    ASSESS --> KB
    ASSESS --> REVIEW
    REVIEW --> DOM
    DOM --> GUARD
    GUARD --> OPS
    OPS --> LOG
    OPS --> NOTIFY
    DOM --> DB
    COORD --> DB
    ASSESS --> DB
    REVIEW --> DB
    GUARD --> DB
    OPS --> DB
    COORD --> OBS
    ASSESS --> OBS
    REVIEW --> OBS
    OPS --> OBS
    DOM --> OBS
    F -->|Reject or manual outcome| NOTIFY
```

## 3. Proposed technology stack

| Area | Initial choice | Reason |
|---|---|---|
| Front end | Next.js and TypeScript | Portfolio-quality customer and operator experience |
| Application API | FastAPI and Python | Typed APIs and strong AI/agent ecosystem |
| Workflow | LangGraph or a small explicit state-machine abstraction | Persistent, inspectable agent workflow |
| Database | PostgreSQL | Transactional case, approval, and audit data |
| Retrieval | PostgreSQL with pgvector, if semantic retrieval proves necessary | One operational datastore and replaceable retrieval interface |
| Validation | Pydantic and JSON Schema | Reject malformed model and tool outputs |
| Testing | Pytest, Vitest, and Playwright | Unit, integration, and end-to-end coverage |
| Packaging | Docker Compose | Repeatable team environment and demonstration |
| Observability | Structured logs plus OpenTelemetry-compatible traces | Inspect agent and tool behaviour |

The team must validate the workflow and retrieval libraries with a time-boxed
technical spike. A library is not an architectural requirement.

## 4. Core domain model

| Entity | Responsibility |
|---|---|
| Customer | Minimal customer identity and contact data |
| Order | Purchase, payment, fulfilment, and line-item facts |
| ReturnCase | Aggregate root for the end-to-end workflow |
| CustomerStatement | Original and clarified customer messages |
| EvidenceItem | Submitted evidence and verification metadata |
| EvidenceAssessment | Required, present, missing, and conflicting evidence criteria plus targeted follow-up |
| PolicyDocument | Versioned store policy or approved guidance source |
| PolicyPassage | Retrieved passage with source version, content hash, location, and retrieval time |
| DecisionProposal | Versioned proposed remedy, rationale, alternatives, citations, and confidence |
| RiskFinding | Unsupported claim, conflict, missing evidence, or escalation reason |
| ApprovalRecord | Human decision bound to trusted actor, current proposal version, time, expiry, and exact command scope |
| ToolCommand | Allowlisted typed, idempotent external action request bound to case, proposal, and approval |
| AuditEvent | Immutable correlated record with component/source version, outcome, typed error, and redaction status |

## 5. ReturnCase state model

```mermaid
stateDiagram-v2
    [*] --> Submitted
    Submitted --> AwaitingInformation: required information missing
    AwaitingInformation --> UnderInvestigation: customer supplies information
    Submitted --> UnderInvestigation: minimum information present
    UnderInvestigation --> PolicyAssessment: order matched
    UnderInvestigation --> AwaitingInformation: order detail missing or correctable
    UnderInvestigation --> UnderInvestigation: provider failure and safe retry remains
    UnderInvestigation --> Escalated: confirmed conflict, unsafe content, or provider retry limit
    PolicyAssessment --> AwaitingInformation: evidence gap
    PolicyAssessment --> RiskReview: proposal produced
    RiskReview --> PolicyAssessment: revision requested
    RiskReview --> Escalated: ambiguous or high risk
    RiskReview --> AwaitingApproval: review passed
    AwaitingApproval --> Rejected: founder rejects
    AwaitingApproval --> Approved: founder approves
    AwaitingApproval --> PolicyAssessment: founder requests revision
    AwaitingApproval --> Escalated: founder requests manual handling
    Approved --> ActionInProgress: trusted exact-scope approval and allowlist checks pass
    ActionInProgress --> ActionFailed: tool failure
    ActionFailed --> ActionInProgress: safe retry
    ActionFailed --> Escalated: retry limit reached
    ActionInProgress --> Resolved: tool results confirmed
    Rejected --> Closed: founder-approved rejection outcome notified and audited
    Resolved --> Closed: approved outcome notified and audited
    Escalated --> Closed: founder records and notifies manual outcome
    Closed --> [*]
```

## 6. Primary sequence

```mermaid
sequenceDiagram
    actor Customer
    actor Founder
    participant Portal
    participant DomainService
    participant Coordinator
    participant Assessment
    participant Reviewer
    participant ApprovalGuard
    participant OperationsService
    participant OrderProvider
    participant LogisticsAdapter
    participant NotificationAdapter

    Customer->>Portal: Submit request and order number
    Portal->>DomainService: Create ReturnCase
    DomainService->>Coordinator: Extract typed case facts
    Coordinator-->>DomainService: Facts and missing fields
    DomainService->>Assessment: Investigate order, retrieve passages, and propose remedy or escalation
    Assessment->>OrderProvider: Query order
    OrderProvider-->>Assessment: Versioned snapshot or typed provider failure
    Assessment-->>DomainService: Typed proposal with versioned passages and conflict flags
    DomainService->>Reviewer: Verify evidence and claims
    alt Conflict, unsupported claim, injection, or unresolved risk
        Reviewer-->>DomainService: Escalate with sources and findings
        DomainService-->>Founder: Manual handling packet, no approval request
    else Independent review passes
        Reviewer-->>DomainService: Pass current proposal version
        DomainService-->>Founder: Approval request with evidence and exact plan
        Founder->>DomainService: Approve current proposal and explicit command set
        DomainService->>ApprovalGuard: Validate trusted actor, case, proposal, scope, amount, expiry
        ApprovalGuard-->>DomainService: Valid scoped ApprovalRecord
        DomainService->>OperationsService: Dispatch trusted approval reference and approved command set
        OperationsService->>ApprovalGuard: Revalidate each allowlisted typed command
        ApprovalGuard-->>OperationsService: Exact-scope dispatch allowed
        OperationsService->>LogisticsAdapter: CREATE_RETURN with idempotency key
        OperationsService->>LogisticsAdapter: GENERATE_LABEL with idempotency key
        OperationsService->>NotificationAdapter: Send approved outcome after tool success
        NotificationAdapter-->>Customer: Confirm approved next step
    end
```

## 7. Human gates

Human approval is mandatory for:

- refund, replacement, or repair authorisation;
- any action that changes order, payment, or inventory state;
- low-confidence or conflicting policy interpretation;
- suspected fraud, abusive behaviour, or sensitive evidence;
- prompt-injection attempts or unauthorised access to approval/tool functions;
- cases outside the three supported MVP request types.

An approval record must bind the trusted approver identity to the case, current
proposal version, explicit command set, maximum amount if applicable, timestamp,
and expiry. Dispatch also verifies the allowlist and current case state.
Approval is not a general permission for an agent to take unrelated actions.

## 8. Agent collaboration contract

Agents exchange typed state, not conversational transcripts as the source of
truth. Each agent returns:

- `status`: success, needs_information, revise, or escalate;
- `facts`: claims supported by case evidence;
- `citations`: source identifier and location;
- `confidence`: calibrated score or categorical band;
- `open_questions`: information still required;
- `recommended_next_step`;
- `risk_flags`.

The Domain Service controls state transitions. An agent cannot invoke another
agent without an allowed workflow transition.

## 9. Evaluation design

Create one versioned course-evaluation set of 30 double-reviewed synthetic Gold
cases covering:

- balanced supported request types;
- missing-order and missing-evidence cases;
- conflicting store policy and approved guidance;
- straightforward and ambiguous product problems;
- prompt-injection text embedded in customer messages or policy files;
- cases that must be escalated.

Use parameterised automated tests, without a fixed scenario quota, for approval,
security, illegal-state, duplicate-command, timeout, notification, and
reconciliation paths.

Compare these required configurations on the same Gold set:

1. single LLM without retrieval;
2. multi-agent workflow with retrieval, deterministic rules, and risk review.

Single-LLM-with-retrieval and ungoverned multi-agent ablations, plus any
expansion towards 100 scenarios, are optional portfolio work after the course
release is stable.

The required comparison evaluates the complete governed architecture bundle
against a naive baseline; it does not isolate the causal contribution of
multi-agent decomposition without the optional ablations.

Report accuracy, recall, citation correctness, escalation recall, latency, and
estimated model cost. Record failure examples, not only aggregate scores.

## 10. Architectural decisions to defend

| Chosen approach | Discarded alternative | Rationale |
|---|---|---|
| Explicit governed workflow | Unrestricted agents calling each other | Easier to model, test, audit, and control |
| Typed tool commands | Free-form actions generated by an LLM | Prevents malformed or over-broad actions |
| Human approval before impact | Fully autonomous refunding | Preserves accountability and limits harm |
| Mock provider adapters | Production payment and logistics access | Safe and achievable for a course prototype |
| Small approved corpus | Open web search for every case | Better provenance, repeatability, and evaluation |
| Three request types | Universal customer support | Keeps requirements and evaluation tractable |

## 11. Model-to-code traceability

| Stage 1 model | Stage 2 evidence |
|---|---|
| User requirements | Acceptance tests and demo scenarios |
| Feature model | Feature flags and MVP backlog |
| Use-case descriptions | API and end-to-end tests |
| Package diagram | Source modules and dependency rules |
| Class diagram | Domain entities and schemas |
| Activity diagram | Domain Service paths and branch tests |
| State machine | ReturnCase transition implementation |
| Sequence diagram | Integration test traces |
| Assumptions | Configuration, limitations, and risk register |
