# Requirements and Initial Backlog

> **Baseline**: v0.2, refined during Laboratory 3. Requirement IDs remain
> stable across the ad-hoc, feature-oriented, and use-case views.
>
> **Planning status**: This Markdown file preserves requirement and backlog
> content; Jira is the live source for sprint selection, owner, estimate,
> blocker, and status history. Repository work links each Jira key to a GitHub
> Issue/PR.

## 1. Requirement classification

### Mandatory capabilities

| ID | Requirement | Acceptance summary |
|---|---|---|
| FR-001 | A customer can submit a supported physical-goods return or remedy request with a message and, when known, an order identifier. | Exactly one `ReturnCase` is created and the original statement is preserved. A missing order identifier enters the information-request path and never triggers an operational action. |
| FR-002 | The system extracts typed case facts and identifies missing mandatory information. | On the labelled benchmark, mandatory-information recall is at least 95%; missing or ambiguous facts are reported rather than invented. |
| FR-003 | The system retrieves a read-only order snapshot through a typed provider interface. | Matched, not-found, conflicting, and provider-failure outcomes follow distinct, auditable paths. |
| FR-004 | The system classifies eligible requests as faulty product, wrong item, or change of mind. | Supported-class accuracy is at least 90%; ambiguous and out-of-scope requests request clarification or escalate instead of receiving a forced label. |
| FR-005 | The system builds an evidence matrix and asks targeted follow-up questions. | Present, missing, and conflicting evidence are distinguished; follow-up requests name only information needed for the case. |
| FR-006 | The system retrieves relevant passages from the versioned store-policy and approved-guidance corpus. | Each result includes source ID, version, and section or location. Missing or conflicting guidance is surfaced to risk review and is not silently resolved. |
| FR-007 | The system produces a non-executable typed resolution proposal with rationale, alternatives, confidence, citations, and unresolved questions. | Schema-invalid or incomplete output is rejected; a proposal cannot itself authorize or become a `ToolCommand`; remedy-category agreement is at least 85% on the reviewed benchmark. |
| FR-008 | An independent risk review detects unsupported claims, citation mismatch, source conflict, low confidence, out-of-scope content, and prompt-injection attempts. | Risk-case escalation recall is at least 95%; a failed review revises, waits for information, or escalates rather than reaching approval. |
| FR-009 | An authenticated and authorised founder can approve, reject, request revision, or escalate the current proposal and record a customer-facing outcome for a rejection or completed manual resolution. | Every immutable decision records the case and proposal version, actor, reason, and timestamp; an approval additionally records permitted command scope, amount limit where relevant, and expiry; reject or manual-resolution closure requires an audited simulated notification result. |
| FR-010 | The system executes only allowlisted simulated commands that exactly match a valid, scoped approval and sends the resulting customer-facing outcome through the simulated notification interface. | Missing, expired, wrong-case, stale-proposal, over-limit, and wrong-command approvals are blocked before a provider call; duplicate idempotency keys cause at most one effect; notification retry never repeats the remedy operation. |
| FR-011 | The system append-only records relevant input, agent/model, source-version, approval, state-transition, and tool-result events. | A reviewer can reconstruct the case path and identify the versions, actor, time, result, and failure reason for each material step. |
| FR-012 | The founder can view authoritative case state and pending approvals. | The dashboard shows the current proposal version, evidence, citations, risk findings, approval scope, and auditable history without maintaining a second source of truth. |

### Mandatory quality requirements

| ID | Requirement | Acceptance summary |
|---|---|---|
| NFR-001 | Traceability | Citation coverage is 100% for proposal claims that depend on policy or case evidence; citation correctness is at least 90% on the labelled benchmark. |
| NFR-002 | Safety | Every high-impact command without a valid exact-scope approval is blocked before any provider call or authoritative state mutation. |
| NFR-003 | Privacy | The repository and demonstration use only synthetic or de-identified data, minimise retained personal information, and exclude secrets from fixtures and logs. |
| NFR-004 | Reliability | A repeated idempotency key produces at most one operational effect, retries or provider failures cannot create an illegal case transition, and mock tool success is at least 95% on the standard benchmark excluding deliberate fault-injection cases. |
| NFR-005 | Performance | In the fixed demo environment, median submission-to-proposal latency is below 120 seconds for complete benchmark cases, excluding human waiting time. |
| NFR-006 | Testability | Mandatory acceptance criteria, state guards, approval-negative paths, and adapter contracts have automated normal- and failure-path tests. |
| NFR-007 | Maintainability | LLM, commerce, policy, logistics, and notification providers are accessed through documented typed interfaces with contract tests. |
| NFR-008 | Observability | Structured events contain case/correlation ID, component and source version, time, outcome, and typed error while redacting sensitive content. |
| NFR-009 | Security and AI robustness | Customer text, attachments, and retrieved documents are untrusted data; they cannot change workflow policy, grant authority, expose secrets, call a non-allowlisted tool, or bypass authenticated role and approval checks. |

### Governing business rules

| ID | Rule |
|---|---|
| BR-001 | ReturnOps AU presents approved guidance and conditional recommendations; it does not give legal advice or make a definitive ACL entitlement, major-failure, or minor-failure determination. |
| BR-002 | A conflict between store policy, approved guidance, or case evidence is displayed with its sources and escalated. The AI does not silently declare one source to override another. |
| BR-003 | Refund, replacement, repair, order/payment/inventory mutation, and cost-bearing logistics operations are high-impact actions. |
| BR-004 | The course prototype uses simulated provider operations and never moves real money or changes a production order. |
| BR-005 | High model confidence cannot bypass missing evidence, a failed risk review, command allowlisting, or human approval. |

### Optional features

| ID | Feature | Entry condition |
|---|---|---|
| OF-001 | Product-image evidence analysis | Core text workflow meets mandatory targets. |
| OF-002 | Multiple languages | English evaluation is stable. |
| OF-003 | Live Shopify development-store adapter | Mock adapter contract is complete and credentials are safely managed. |
| OF-004 | Logistics provider sandbox/test-mode label integration | Human approval, idempotency, credential, and no-real-shipment/no-charge tests pass; production fulfilment remains outside the course prototype. |
| OF-005 | Inventory restocking workflow | A separately reviewed return-receipt and inspection state-model extension exists. |
| OF-006 | Analytics dashboard | Core audit data is complete and reliable. |
| OF-007 | Anomaly or fraud risk scoring | A suitable labelled dataset exists and scoring can only flag or escalate, not automatically deny a remedy. |

## 2. Initial epics

### Epic E1: Problem discovery and requirements

- Freeze and summarise the desk-research evidence, assumptions, and limitations;
  do not claim primary user validation.
- Document the evidence-informed reference workflow, friction, exceptions, and
  controlled student-operator baseline.
- Confirm the target user and three supported request types.
- Review the one-sentence brief and MVP boundary with the tutor.
- Build the requirements traceability matrix.

### Epic E2: Domain model and mock environment

- Define Order, ReturnCase, EvidenceItem, DecisionProposal, ApprovalRecord, and
  AuditEvent schemas.
- Create realistic but synthetic orders, policies, and customer requests.
- Implement the mock commerce and logistics adapters.
- Implement valid state transitions and transition tests.

### Epic E3: Case investigation workflow

- Implement case submission and structured extraction.
- Implement order matching and missing-information paths.
- Implement request classification and evidence matrix generation.
- Add founder-facing case timeline.

### Epic E4: Policy and guidance grounding

- Build a versioned approved corpus.
- Evaluate keyword, semantic, and hybrid retrieval on labelled queries.
- Return source identifiers and passage locations.
- Reject responses containing unsupported policy claims.

### Epic E5: Resolution and human control

- Implement typed proposal generation.
- Implement independent risk review.
- Implement approval, rejection, and revision.
- Enforce scoped approval before every simulated high-impact action.

### Epic E6: Evaluation and evidence

- Create 30 double-reviewed synthetic Gold cases.
- Compare the required single-LLM (`B1`) and governed multi-agent (`B4`)
  configurations on the same frozen cases.
- Cover approval/security and workflow/provider failures with parameterised
  automated tests; do not impose a fixed course scenario quota.
- Defer `B2`/`B3` ablations and any expansion towards 100 scenarios to optional
  portfolio work.
- Report accuracy, recall, citation correctness, latency, cost, and failures.
- Link requirements, models, code, tests, and demo evidence.

## 3. First two-week sprint

This is a planning reference. The actual sprint selection, owners, estimates,
and status are maintained in Jira. The first sprint proves the project is worth
continuing; it does not attempt to build the complete system.

### Sprint goal

Validate the problem and demonstrate one traceable vertical slice from customer
message to founder proposal.

### Proposed sprint issues

1. Freeze and summarise the existing desk-research evidence and assumptions;
   do not represent it as primary user validation.
2. Produce the current-state customer return journey.
3. Confirm the MVP request types and explicit non-scope.
4. Define the ReturnCase and Order schemas.
5. Create ten synthetic case fixtures with reviewed labels.
6. Implement a mock order lookup.
7. Extract a typed case from one customer message.
8. Retrieve one relevant policy passage with a source location.
9. Display a non-executable proposal to the founder.
10. Record a trace from submission through proposal.

### Sprint review evidence

- Frozen evidence summary, limitations, and revised problem statement.
- One end-to-end demonstration case.
- One failure-path demonstration for a missing order or missing evidence.
- Initial accuracy and latency measurement.
- Updated risks and scope decision.

## 4. Traceability convention

Every implementation issue should list:

```text
Requirement: FR-007
Model: Return assessment activity diagram, Resolution sequence diagram
Tests: tests/integration/test_resolution_proposal.py
Evidence: evaluation run or pull-request screenshot/trace
```

Requirement IDs remain stable. If a requirement changes, update its text,
rationale, affected models, acceptance tests, and change history rather than
silently reusing the ID for a different requirement.

## 5. Laboratory 3 modelling views

The same baseline is represented through three complementary views:

- [Laboratory 3 integrated requirements model](05-lab-3-requirement-modelling.md)
  records the ad-hoc stakeholder language, ambiguity resolutions, detailed use
  cases, and end-to-end traceability.
- [Feature diagram and decomposition model](diagrams/04-feature-diagram.md)
  records mandatory and optional capabilities, variation points, feature
  attributes, and cross-tree constraints.
- [Use-case diagram](diagrams/05-use-case-diagram.md) records the system
  boundary, external actors, actor goals, included behaviour, conditional
  extensions, and human authority checkpoints.
