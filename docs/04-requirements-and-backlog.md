# Requirements and Initial Backlog

## 1. Requirement classification

### Mandatory capabilities

| ID | Requirement | Acceptance summary |
|---|---|---|
| FR-001 | A customer can submit a product-problem request with an order identifier. | A valid ReturnCase is created and the original message is preserved. |
| FR-002 | The system extracts structured case facts and identifies missing mandatory information. | Labelled extraction tests meet the recall target. |
| FR-003 | The system retrieves a matching order snapshot through a provider interface. | Matched, missing, and conflicting orders follow distinct paths. |
| FR-004 | The system classifies supported requests as faulty product, wrong item, or change of mind. | Classification target is met on the held-out case set. |
| FR-005 | The system builds an evidence matrix and asks targeted follow-up questions. | Missing evidence is named without inventing facts. |
| FR-006 | The system retrieves relevant store-policy or approved-guidance passages with source locations. | Every policy claim carries a verifiable citation. |
| FR-007 | The system produces a typed resolution proposal with rationale, alternatives, confidence, and unresolved questions. | Invalid or incomplete outputs are rejected. |
| FR-008 | A separate risk review detects unsupported, conflicting, low-confidence, and out-of-scope proposals. | Escalation recall target is met. |
| FR-009 | A founder can approve, reject, or request revision of a proposal. | The decision records actor, scope, timestamp, and reason. |
| FR-010 | The system executes only an approved simulated operational action. | Tests prove unapproved and expired actions are blocked. |
| FR-011 | The system records relevant agent, source, approval, state, and tool events. | A reviewer can reconstruct the case path. |
| FR-012 | The founder can view current case state and pending approvals. | Dashboard reflects the authoritative case state. |

### Mandatory quality requirements

| ID | Requirement | Acceptance summary |
|---|---|---|
| NFR-001 | Traceability | Recommendation claims link to evidence or an approved source. |
| NFR-002 | Safety | No high-impact command runs without scoped human approval. |
| NFR-003 | Privacy | Prototype uses synthetic/de-identified data and minimises stored personal information. |
| NFR-004 | Reliability | Duplicate commands are idempotent and tool failures do not corrupt case state. |
| NFR-005 | Performance | Median proposal time is below two minutes in the demo environment. |
| NFR-006 | Testability | Agents, rules, adapters, and state transitions have automated tests. |
| NFR-007 | Maintainability | External providers and LLMs are accessed through documented interfaces. |
| NFR-008 | Observability | Workflow transitions and tool calls emit structured diagnostic records. |

### Optional features

| ID | Feature | Entry condition |
|---|---|---|
| OF-001 | Product-image evidence analysis | Core text workflow meets mandatory targets. |
| OF-002 | Multiple languages | English evaluation is stable. |
| OF-003 | Live Shopify development-store adapter | Mock adapter contract is complete and credentials are safely managed. |
| OF-004 | Live logistics label integration | Human approval and idempotency tests pass. |
| OF-005 | Inventory restocking workflow | Return receipt and inspection states exist. |
| OF-006 | Analytics dashboard | Core audit data is complete and reliable. |
| OF-007 | Anomaly or fraud risk scoring | A suitable labelled dataset and safe escalation policy exist. |

## 2. Initial epics

### Epic E1: Problem discovery and requirements

- Interview at least three potential users or domain-informed participants.
- Document current workflow, friction, exceptions, and measurable baseline.
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

- Create at least 100 synthetic labelled cases.
- Establish a simple baseline.
- Compare the four planned system configurations.
- Report accuracy, recall, citation correctness, latency, cost, and failures.
- Link requirements, models, code, tests, and demo evidence.

## 3. First two-week sprint

The first sprint proves the project is worth continuing. It does not attempt to
build the complete system.

### Sprint goal

Validate the problem and demonstrate one traceable vertical slice from customer
message to founder proposal.

### Proposed sprint issues

1. Conduct and summarise three problem interviews.
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

- Interview evidence and revised problem statement.
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

