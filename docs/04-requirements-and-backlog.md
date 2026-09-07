# Requirements and Initial Backlog

> **Status (2026-09-07)**: v1.0 alignment draft of the original Laboratory 3
> requirements/backlog. This is a derived summary of
> [the lead-approved product candidate](00-project-definition-v1.md), not a
> second authority for acceptance criteria. IDs are preserved. Team/tutor
> adoption and review of this alignment remain pending. The aligned version is
> published in [PR #9](https://github.com/shuxiachai/returnops-au/pull/9); consult its merge record separately from acceptance.
> The proposal-bound FR-009 summary and failure-target manual exception need
> the joint wording confirmation recorded in docs/00 section 4.4 and docs/09.
>
> **Execution plan**: [Frozen allocation](07-frozen-work-allocation.md) fixes
> the nine features and owners; [work packages](08-delivery-work-packages.md)
> replace the initial sprint below for new work. Original contributions and
> the v0.2 Lab 3 history remain in Git history.
>
> **Planning status**: This Markdown file preserves requirement and backlog
> content; Jira is the live source for sprint selection, owner, estimate,
> blocker, and status history. Repository work links each Jira key to a GitHub
> Issue/PR.

## 1. Requirement classification

### Mandatory capabilities

| ID | Requirement | Acceptance summary |
|---|---|---|
| FR-001 | Accept an English physical-goods request, original message, optional order ID/outcome/evidence. | One submission key creates at most one case; preserve `CustomerStatement`. Missing required facts trigger clarification, not a command; reasonable proof-of-purchase alternatives are allowed. |
| FR-002 | Coordinator extracts typed facts and separates missing, ambiguous, conflicting and not-applicable information. | Mandatory-information recall ≥95%; unnecessary follow-up ≤15%; zero critical-fact fabrication on frozen negatives. Freeze definitions/denominators before evaluation. |
| FR-003 | Assessment obtains a read-only order snapshot through a typed provider. | Test `MATCHED`, `NOT_FOUND`, `CONFLICT`, `AUTHORITY_DENIED`, `PROVIDER_FAILURE`; lookup cannot mutate orders. |
| FR-004 | Separately store issue category, customer-requested outcome, possible basis and assessment status. | Independent fields cannot overwrite one another; category macro-F1 ≥0.85 (stretch ≥0.90). Unclear/out-of-scope cases clarify or escalate; no final legal determination. |
| FR-005 | Build a criterion-level evidence matrix and case-relevant follow-ups. | `PRESENT/MISSING/CONFLICTING/NOT_APPLICABLE`; allow proof-of-purchase alternatives. Original packaging is not a universal faulty-product rule; transport/cost questions are asked only when relevant. |
| FR-006 | Retrieve from reviewed, versioned store-policy and consumer-guidance sources. | 100% provenance completeness: source ID/type, version when available, access date, location, content hash, retrieval time. Material case-relevant conflicts remain visible to Risk Review. |
| FR-007 | Generate a versioned, non-executable `DecisionPacket` referencing the original statement. | Conditional recommendation, alternatives, rationale, citations, confidence, open questions and relevant return-cost/responsibility facts; completeness ≥95% with a frozen denominator. No direct packet-to-approval/command conversion. |
| FR-008 | Independently review evidence, citation support, conflicts, scope, confidence, injection and authority manipulation. | Recall ≥95%, specificity ≥80%; exactly `PASS/PASS_WITH_WARNING/REVISE/NEEDS_INFORMATION/ESCALATE`. Escalated proposals cannot be approved for execution; a new proposal needs a new pass/warning-pass review. |
| FR-009 | Only the trusted Human Founder may `APPROVE/REJECT/REQUEST_REVISION/MANUAL_HANDLING` the current proposal. | Bind actor, case, proposal ID/version, reason/time; approval also binds exact commands, parameter fingerprint, applicable amount ceiling and expiry. Wrong actor/case/version/scope or expired approval is invalid. Rejection/manual outcome is recorded and notified. |
| FR-010 | Execute only exact-approved, allowlisted simulated return/label operations and independently notify the outcome. | Verify provider authority separately. Record provider ID, fingerprint, typed result/error and idempotency key. Unknown timeout requires `UNKNOWN/RECONCILING` before retry; duplicate key has at most one effect; notification retry never repeats return/label. Include next steps and relevant packaging/drop-off/cost/responsibility facts. No real money, order, inventory or shipment effects. |
| FR-011 | Maintain reconstructable, tamper-evident audit records separately from identifiable content. | Correlation links inputs, component/model/corpus versions, proposal/review/approval, state and provider/notification results. Retention/redaction/deletion preserve non-personal event IDs/hash integrity, not personal content forever. |
| FR-012 | Show authoritative case, proposal, evidence, citations, risk, approval, operations, notification and audit state. | Founder-only API access; versions visible; UI keeps no independent workflow state. |

### Mandatory quality requirements

| ID | Requirement | Acceptance summary |
|---|---|---|
| NFR-001 | Traceability | Citation coverage is 100% for proposal claims that depend on policy or case evidence; citation correctness is at least 90% on the labelled benchmark. |
| NFR-002 | Safety | Block invalid state, failed/stale risk review, invalid exact approval, missing provider authority and non-allowlisted commands before effects. Domain Service alone writes business state, including safe blocked-attempt records. |
| NFR-003 | Privacy | Synthetic/de-identified data only; test secret exclusion, log redaction, model field allowlists, approved provider data flows and retention/deletion without breaking non-personal audit integrity. |
| NFR-004 | Reliability | Zero duplicate effects and illegal transitions; ambiguous outcomes reconcile before retry; notification retry does not repeat operations. |
| NFR-005 | Performance | p95 `accepted-complete-input → stored-review-ready-proposal` <120 seconds in the fixed environment; include machine revision/risk loops, exclude human and physical waiting only. Report p50/p95, failures, environment/model, tokens and cost. |
| NFR-006 | Testability | Mandatory acceptance criteria, state guards, approval-negative paths, and adapter contracts have automated normal- and failure-path tests. |
| NFR-007 | Maintainability | LLM, commerce, policy, logistics, and notification providers are accessed through documented typed interfaces with contract tests. |
| NFR-008 | Observability | Structured events contain case/correlation ID, component and source version, time, outcome, and typed error while redacting sensitive content. |
| NFR-009 | Security and AI robustness | Customer text, attachments, and retrieved documents are untrusted data; they cannot change workflow policy, grant authority, expose secrets, call a non-allowlisted tool, or bypass authenticated role and approval checks. |

### Governing business rules

| ID | Rule |
|---|---|
| BR-001 | ReturnOps AU presents approved guidance and conditional recommendations; it does not give legal advice or make a definitive ACL entitlement, major-failure, or minor-failure determination. |
| BR-002 | Material case-relevant source conflicts remain visible. Non-blocking differences may give `PASS_WITH_WARNING`; unresolved conflicts preventing a safe recommendation require `ESCALATE`. No silent source precedence. |
| BR-003 | Refund, replacement, repair, order/payment/inventory mutation, and cost-bearing logistics operations are high-impact actions. |
| BR-004 | The course prototype uses simulated provider operations and never moves real money or changes a production order. |
| BR-005 | High model confidence cannot bypass missing evidence, a failed risk review, command allowlisting, or human approval. |
| BR-006 | ReturnOps approval and external-provider permission are independent prerequisites. |
| BR-007 | Changed proposal version, remedy, amount, line items, commands or parameter fingerprint requires new approval. |
| BR-008 | Customer-requested outcome and system recommendation remain separate. |
| BR-009 | One case covers one order and potentially multiple line items; one return shipment has one parcel label, with no split shipments. |
| BR-010 | Core completion requires stored simulated return/label results and successful outcome notification. `NOTIFICATION_PENDING/NOTIFICATION_FAILED` cannot cause an operation to be repeated. |
| BR-011 | Desk evidence, assumptions, targets and measured results are separately labelled. |
| BR-012 | AI cannot directly write authoritative state, create a trusted approval or call operations providers. |

### Optional features and this team's selected configuration

`OF` remains a product-variation label, not permission to omit a selected course
feature. A3, B3 and C3 must be delivered within the course; their prerequisites
control integration order. Unselected options below are not course commitments.

| ID | Feature | Entry condition |
|---|---|---|
| OF-001 | Product-image evidence analysis — **C3 selected** | Stable text workflow and authorised attachments; observations retain uncertainty/original image references, no fourth business AI role or automatic entitlement decision. |
| OF-002 | Multiple languages — unselected | Future scope review after stable English evaluation. |
| OF-003 | Shopify development-store adapter — unselected | Future scope/security review; not a current production-order integration. |
| OF-004 | Independent logistics sandbox/test adapter — **A3 selected** | Verify test access and no real shipment/charge first; preserve approval, provider permission, idempotency and reconciliation. Core mock/retry work cannot count twice; unavailable test access is an explicit blocker. |
| OF-005 | Inventory restocking — unselected/outside current endpoint | Requires a separately approved receipt/inspection and state-model extension. |
| OF-006 | Limited operations analytics — **B3 selected** | A supplies authoritative statistics; B shows case totals, current state, latest valid current-proposal risk and recorded proposal latency, including no-data/failure/sample-count handling. |
| OF-007 | Anomaly or fraud scoring — unselected | Needs a suitable labelled dataset and separate approval; flag/escalate only, never automatic denial. |

All quantitative thresholds here are `PROTOTYPE_TARGET`, not measured results.
Use 30 double-reviewed Gold cases and the required experiment `B1` versus `B4`,
with separate 10–20 pilot cases and parameterised safety/workflow tests. The
20-case human timing study is a Gold subset, not a second evaluation set; A/B
complete blind timing before label review or viewing each other's output.
C coordinates labels/runner; each member tests their own features. Report raw
counts and denominators, and do not attribute the bundle comparison solely to
multi-agent decomposition. Research appendix expansion, experiment B2/B3,
100-scenario expansion and hybrid retrieval remain portfolio work.

## 2. Initial epics

These stable epic labels are a scope index, not a replacement ownership/status
board. C maps existing Jira records to `docs/07` and `docs/08`; do not recreate
epics or invent Jira keys from this list.

### Epic E1: Problem discovery and requirements

- Freeze and summarise the desk-research evidence, assumptions, and limitations;
  do not claim primary user validation.
- Document the evidence-informed reference workflow, friction, exceptions, and
  controlled student-operator baseline.
- Confirm the target user and three supported request types.
- Review the one-sentence brief and MVP boundary with the tutor.
- Build the requirements traceability matrix.

### Epic E2: Domain model and mock environment

- Define Order/LineItem, ReturnCase, CustomerStatement, EvidenceAssessment,
  DecisionPacket, RiskReview, ApprovalRecord, OperationAttempt, Notification
  and AuditEvent schemas; separate one-order/multi-item and one-parcel concepts.
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
- Implement C's keyword/BM25 baseline; semantic/hybrid retrieval is a later
  portfolio comparison, not a mandatory core dependency.
- Return complete provenance, resolvable citations and material conflicts.
- C1 verifies citation resolution/content; C2 checks semantic claim support.

### Epic E5: Resolution and human control

- Implement typed proposal generation.
- Implement independent risk review.
- Implement approval, rejection, revision and manual-handling outcomes.
- Enforce scoped approval before every simulated high-impact action.
- Reconcile unknown effects before retry; keep notification delivery independent.

### Epic E6: Evaluation and evidence

- Create 30 double-reviewed synthetic Gold cases.
- Compare the required single-LLM (`B1`) and governed multi-agent (`B4`)
  configurations on the same frozen cases.
- Cover approval/security and workflow/provider failures with parameterised
  automated tests; do not impose a fixed course scenario quota.
- Defer `B2`/`B3` ablations and any expansion towards 100 scenarios to optional
  portfolio work.
- Report macro-F1, risk recall/specificity, citation correctness, p50/p95 latency,
  cost, denominators and failures; targets are not results.
- Link requirements, models, code, tests, and demo evidence.

## 3. Historical first two-week sprint proposal (v0.2)

The following is retained as planning history, not a new instruction or evidence
that these tasks were performed. Use `docs/08` dependencies and actual Jira
selection now. In particular, model/contract preparation precedes the fixed-
proposal Gate 1 safety spine; connect LLM output to execution only after Gate 1.
Offline AI work and UI mocks can run in parallel. Historical ten-case fixtures
do not replace the separate pilot/30-case Gold protocol.

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
Jira Key: pending Member C mapping (replace with an existing verified key)
Work Package: A1.07
Owner: Member A
Reviewer: Member C
Requirement: FR-005, FR-006, FR-007
Use Case: UC-02
Model: shared assessment sequence + owner's relevant model contribution
Implementation / Tests: link actual paths when created, not hypothetical evidence
Evidence: actual test run / PR / trace once available
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
