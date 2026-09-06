# Laboratory 3 - Requirements Modelling

> **Course activity**: ELEC5620 Week 4, Laboratory 3
>
> **Project**: ReturnOps AU
>
> **Tracking**: [GitHub Issue #1](https://github.com/shuxiachai/returnops-au/issues/1)
>
> **Status**: Complete modelling baseline; ready for team and tutor review
>
> **Canonical requirements**:
> [Requirements and Initial Backlog](04-requirements-and-backlog.md)

The Laboratory 3 note asks the team to model the same project requirements
through three complementary approaches: ad-hoc, feature-oriented, and use case.
It does not prescribe a page count or submission template. This document keeps
one stable requirement baseline and shows how each approach adds a different
kind of precision.

The course PDF was reviewed locally and is intentionally not copied into this
repository. Only the team's original project analysis is committed.

## 1. Modelling objective and system scope

ReturnOps AU helps an Australian e-commerce SME founder handle physical-goods
return and remedy requests. It collects a customer request, investigates the
order and evidence, retrieves relevant passages from a reviewed corpus,
prepares a conditional proposal, performs independent risk review, and waits
for an authorised founder decision before any simulated high-impact action.

The three views answer different questions:

| Approach | Primary question | Lab 3 output |
|---|---|---|
| Ad-hoc | What do stakeholders say they need, and where is the language ambiguous? | Stakeholder narrative, raw needs, assumptions, and ambiguity resolutions |
| Feature-oriented | What capabilities, options, qualities, and dependencies must the product contain? | FODA hierarchy, runtime variation points, feature attributes, and cross-tree constraints |
| Use case | Which actor is trying to achieve which observable goal, including failure and uncertainty? | System boundary, actor-goal diagram, authority limits, success scenarios, and extension scenarios |

The canonical vocabulary is:

- `AH-xx`: informal stakeholder need used only in this Lab 3 analysis;
- `FR-xxx`: mandatory functional requirement;
- `NFR-xxx`: mandatory quality or constraint requirement;
- `BR-xxx`: governing business rule;
- `OF-xxx`: optional feature that cannot enter the MVP before its entry gate;
- `UC-xx`: actor-goal use case.

## 2. Part One - Ad-hoc approach

### 2.1 Informal stakeholder narrative

An e-commerce founder currently receives a customer message, searches for an
order, checks fulfilment and payment data, reads a store policy, considers the
customer's evidence, and decides what to do. These facts are spread across
several systems. The process is slow, repeated for every case, and vulnerable
to inconsistent interpretation.

A customer wants to explain the issue once, learn what information is missing,
and receive a consistent next step. The customer should not need to understand
the store's internal tools or the agent architecture.

The founder wants a concise decision packet containing verified order facts,
an evidence matrix, relevant source passages, alternatives, uncertainty, and a
clear action scope. The founder does not want an AI to quietly move money,
change inventory, claim legal certainty, or hide conflicting information.

ReturnOps AU should therefore do the repetitive investigation and preparation,
while the accountable human remains the decision maker. Every material fact,
proposal version, approval, state change, and simulated tool result should be
recoverable for review and evaluation.

### 2.2 Raw stakeholder needs

The `AH` identifiers make the informal statements traceable; they do not turn
this section into a second formal specification.

| ID | Stakeholder-language need | Refined baseline |
|---|---|---|
| AH-01 | "Let me describe the return or product issue without navigating internal systems." | FR-001 |
| AH-02 | "Tell me exactly what information is missing instead of guessing." | FR-002, FR-005 |
| AH-03 | "Show whether the order and affected item really match the request." | FR-003 |
| AH-04 | "Separate faulty products, wrong deliveries, and change-of-mind requests." | FR-004 |
| AH-05 | "Show which evidence supports the case, which evidence conflicts, and what is still absent." | FR-005 |
| AH-06 | "Show the actual policy or approved-guidance passage behind a recommendation." | FR-006, NFR-001 |
| AH-07 | "Give the founder a proposal with reasons, alternatives, uncertainty, and unresolved questions." | FR-007 |
| AH-08 | "If the sources conflict or the system is uncertain, stop and hand the case to a person." | FR-008, BR-002, BR-005 |
| AH-09 | "The founder must control every decision that can affect money, an order, inventory, or paid logistics." | FR-009, NFR-002, BR-003 |
| AH-10 | "Execute only the exact approved simulated action and never perform it twice by accident." | FR-010, NFR-004 |
| AH-11 | "Let a reviewer reconstruct who or what decided, changed, approved, and called a tool." | FR-011, NFR-008 |
| AH-12 | "Give the founder one reliable view of current cases and pending decisions." | FR-012 |
| AH-13 | "Do not make the founder wait through another ten-minute manual investigation." | NFR-005 |
| AH-14 | "Do not expose real customer data, credentials, or sensitive evidence in a student prototype." | NFR-003, NFR-009 |
| AH-15 | "A provider timeout or duplicate click must not corrupt the case or repeat an action." | NFR-004 |
| AH-16 | "Customer or policy text must not be able to instruct the AI to ignore its controls." | FR-008, NFR-009 |
| AH-17 | "We should be able to replace an LLM or provider without rebuilding the whole product." | NFR-007 |
| AH-18 | "The team must prove the normal path and dangerous failure paths with repeatable tests." | NFR-006 |
| AH-19 | "Tell the customer the approved outcome, but never repeat the remedy if message delivery needs a retry." | FR-010, NFR-004 |

### 2.3 Ambiguities resolved during refinement

| Informal phrase | Risk if left unresolved | Baseline decision |
|---|---|---|
| "Product-problem request" | Excludes wrong-item and change-of-mind cases even though they are in the MVP. | Use `return or remedy request` as the umbrella term; retain exactly three supported request types. |
| "Appropriate remedy" | Could be interpreted as a final legal or commercial decision made by AI. | The system produces a conditional, non-executable proposal; the founder decides. |
| "Follow ACL" | Could imply automated legal advice or a definitive major/minor-failure ruling. | Retrieve approved ACCC guidance, show sources and uncertainty, and escalate conflicts; BR-001 prohibits a definitive legal determination. |
| "Policy grounding" | Could hide disagreement between store policy and approved guidance. | Preserve both passages and create a `RiskFinding`; BR-002 prohibits silent precedence. |
| "Automatic handling" | Could imply autonomous refund, replacement, repair, or shipment. | Investigation may be automated; every high-impact command requires risk review and exact-scope human approval. |
| "Fast" | Has no reproducible measurement boundary. | Measure median submission-to-proposal latency under 120 seconds on complete benchmark cases, excluding human wait time. |
| "Correct citations" | Mixes whether a citation exists with whether it supports the claim. | Citation coverage target is 100%; benchmark citation correctness target is at least 90%. |
| "Integration" | Could require unsafe production credentials and real transactions. | Mock commerce and logistics adapters are mandatory for the MVP; live adapters remain gated optional features. |

### 2.4 Assumptions, constraints, and explicit non-scope

- The prototype supports English-language requests about Australian physical
  goods and an existing or claimed order.
- The three supported request types are faulty product, wrong item, and change
  of mind. Ambiguous and other requests wait for information or escalate.
- Orders, customers, policies, attachments, payments, returns, and labels are
  synthetic or de-identified.
- The approved guidance corpus is curated and versioned offline by the team;
  the MVP does not include a policy-administration UI.
- The prototype does not give legal advice, make a definitive ACL entitlement
  determination, move real money, or mutate a production order.
- Optional features enter only after the mandatory baseline and its safety
  tests meet the entry conditions in the feature model.

## 3. Part Two - Feature-oriented approach

The complete model is in the
[Feature Diagram and Decomposition Model](diagrams/04-feature-diagram.md).
It uses the course concepts of mandatory and optional sub-features, exclusive
alternatives, option groups, feature attributes, and cross-tree constraints.

### 3.1 Feature groups

| Feature group | Type | Leaf requirements or options | Stakeholder value |
|---|---|---|---|
| Case Intake | Mandatory | FR-001, FR-002 | Creates a traceable case and identifies missing facts. |
| Case Investigation | Mandatory | FR-003, FR-004, FR-005 | Verifies order facts, request type, and evidence gaps. |
| Grounded Decision | Mandatory | FR-006, FR-007, FR-008 | Produces a cited, typed, independently reviewed proposal. |
| Governed Operations | Mandatory | FR-009, FR-010 | Keeps an authorised human responsible for high-impact action. |
| Audit and Oversight | Mandatory | FR-011, FR-012 | Makes case state, decisions, and evidence inspectable. |
| Commerce Adapter | XOR `1..1` per deployment | Mock selected for MVP; OF-003 live Shopify optional | Preserves a stable order interface while changing provider. |
| Logistics Adapter | XOR `1..1` per deployment | Mock selected for MVP; OF-004 sandbox/test-mode provider optional | Preserves approval and idempotency across providers without creating a real shipment or charge. |
| Retrieval Strategy | XOR `1..1` per evaluation run | Keyword, semantic, or hybrid | Allows a controlled comparison without changing FR-006. |
| Stage 2 Extensions | Option group `0..*` | OF-001, OF-002, OF-005, OF-006, OF-007 | Adds value only after core acceptance gates pass. |

### 3.2 Important feature constraints

- A typed proposal requires both an evidence matrix and approved-source
  grounding (`FR-007 requires FR-005 and FR-006`).
- Risk review requires a versioned typed proposal (`FR-008 requires FR-007`).
- Operational execution requires a passed risk review and a valid, exact-scope
  founder approval (`FR-010 requires FR-008 and FR-009`).
- The founder dashboard requires authoritative audit and state data
  (`FR-012 requires FR-011`).
- Live adapters require the provider interfaces, approval enforcement,
  idempotency, credential protection, and tool allowlisting.
- Analytics requires complete structured audit data; fraud scoring may only
  flag or escalate; inventory restocking requires a separately reviewed state
  extension.

The request categories and remedy categories are runtime case values, not
product-configuration alternatives. Modelling them as FODA XOR features would
incorrectly suggest that a deployment supports only one request or remedy type.

### 3.3 Feature attributes

`NFR-001` through `NFR-009` are mandatory cross-cutting attributes rather than
optional product checkboxes. Their principal attachment points and measurable
interpretations are recorded in Section 4 of the feature model. This prevents a
team from selecting a functional feature while accidentally omitting its
safety, security, reliability, or traceability obligations.

## 4. Part Three - Use case approach

The [Use-Case Diagram and Actor Boundary Model](diagrams/05-use-case-diagram.md)
summarises the system boundary and relationships. Following the course's
modified Cockburn approach, the textual scenarios below are authoritative: an
oval alone does not specify success, failure, uncertainty, or authority.

### 4.1 Actors and actor goals

| Actor | Goal | Boundary decision |
|---|---|---|
| End Customer | Lodge a request and supply missing information or evidence | May write only customer statements/evidence; cannot approve or invoke tools |
| Authorised Founder / Operations Manager | Make an informed, accountable, scoped decision | Approval must come from an authenticated role and current proposal |
| Mock Commerce Provider | Supply order facts and execute an approved simulated commerce command | Cannot decide a remedy or accept an unapproved command |
| Mock Logistics Provider | Execute an approved, idempotent simulated logistics command | Cannot create a real shipment or broaden command scope |
| Simulated Notification Provider | Deliver targeted information requests and approved outcome messages | Cannot decide, approve, or alter a remedy; a retry cannot repeat an operational command |

AI agents, the API, database, and orchestrator are internal components, not UML
external actors. The ACCC website is an offline corpus source, not a runtime
actor. A system administrator is a stakeholder but has no MVP use case because
the baseline contains no administration UI.

### 4.2 Use-case catalogue

| ID | Actor goal | Primary actor or trigger | Requirement coverage |
|---|---|---|---|
| UC-01 | Lodge a return/remedy request | End Customer | FR-001, FR-002, FR-011 |
| UC-01E | Provide requested clarification or evidence | End Customer | FR-002, FR-005, FR-011 |
| UC-02 | Assess a case and prepare an evidence-grounded proposal | End Customer initiates through UC-01; Founder receives the decision packet | FR-002 to FR-008, FR-011 |
| UC-03 | Review and decide the current proposal | Authorised Founder | FR-009, FR-011, FR-012 |
| UC-04 | Execute exactly the approved simulated action | Founder approval action from UC-03; Commerce/Logistics/Notification Providers support | FR-010, FR-011 |
| UC-05 | Inspect case status and audit history | Authorised Founder | FR-011, FR-012 |

### 4.3 UC-01 - Lodge a return/remedy request

| Field | Specification |
|---|---|
| Goal | Create a traceable case and tell the customer what information is needed next. |
| Level | User goal |
| Primary actor | End Customer |
| Preconditions | Customer can access the portal; the prototype accepts only synthetic or de-identified demonstration data. |
| Trigger | Customer submits a new return or remedy message. |
| Success condition | Original submission is preserved, a case ID exists, and the case proceeds to investigation or explicitly awaits missing information. |
| Failure condition | No valid case is created; no operational action occurs; the failure is visible and auditable. |
| Authority | Customer may add statements and evidence only to the submitted case. Submission never grants approval. |
| Traceability | FR-001, FR-002, FR-005, FR-011; NFR-003, NFR-008, NFR-009 |

Main success scenario:

1. Customer enters a problem description, requested outcome, and known order
   identifier, and may attach evidence.
2. The system validates input formats, file restrictions, and untrusted-content
   boundaries.
3. The system preserves the original statement and accepted evidence.
4. The system creates a unique `ReturnCase` in `SUBMITTED`.
5. The system extracts typed facts and identifies missing mandatory information.
6. With sufficient information, the case moves to `UNDER_INVESTIGATION`.
7. The system returns the case ID and the next expected step.

Extension and failure scenarios:

- **2a - Invalid or unsafe attachment:** reject that attachment, explain the
  restriction, retain safe form data, and do not pass its content to tools.
- **3a - Persistence failure:** create no partial duplicate; return a retryable
  error and a correlated diagnostic event.
- **5a - Missing or ambiguous information:** move to `AWAITING_INFORMATION`,
  ask targeted questions, and invoke UC-01E. When the customer supplies enough
  information, preserve the new statement and resume at Step 6.
- **5b - Potentially out-of-scope request:** preserve the request; UC-02 makes
  the risk/escalation decision rather than silently discarding it.

### 4.4 UC-01E - Provide clarification or evidence

| Field | Specification |
|---|---|
| Goal | Supply the requested missing information so the case can safely resume. |
| Level | User goal extension |
| Primary actor | End Customer |
| Supporting actor | Simulated Notification Provider |
| Preconditions | A case exists in `AWAITING_INFORMATION`, and the outstanding questions are visible to the customer. |
| Trigger | Customer submits a clarification or additional evidence in response to a targeted request. |
| Success condition | The original clarification is preserved, the evidence matrix is updated, and a sufficiently complete case returns to `UNDER_INVESTIGATION`. |
| Failure condition | Invalid content is not accepted as evidence; the case remains safe in `AWAITING_INFORMATION` with an explicit reason. |
| Authority | Customer may add statements and evidence to that case only; clarification cannot approve or execute a remedy. |
| Traceability | FR-002, FR-005, FR-011; NFR-003, NFR-008, NFR-009 |

Main success scenario:

1. Customer reviews the targeted question and submits clarification or evidence.
2. The system validates the case association, format, attachment restrictions,
   and untrusted-content boundary.
3. The system append-only preserves the new statement and accepted evidence.
4. The system updates typed facts and the present, missing, and conflicting
   evidence assessment.
5. When mandatory information is sufficient, the case returns to
   `UNDER_INVESTIGATION` and resumes UC-02.

Extension and failure scenarios:

- **2a - Unsafe or unsupported attachment:** reject that attachment, retain
  safe text, and explain the restriction.
- **4a - Information is still incomplete:** keep `AWAITING_INFORMATION` and ask
  only the remaining questions; the customer may repeat UC-01E.
- **4b - New information creates a confirmed conflict:** preserve both versions
  and let UC-02 create the risk finding or escalation.
- **5a - Persistence or notification failure:** do not lose the accepted
  statement or create a duplicate; expose a retryable, correlated error.

### 4.5 UC-02 - Assess case and prepare proposal

| Field | Specification |
|---|---|
| Goal | Have an eligible request assessed and prepared for a responsible human decision without taking a high-impact action. |
| Level | User goal |
| Primary actor | End Customer; the Founder is the business beneficiary of the decision packet. |
| Primary trigger | Customer submits an eligible request through UC-01 with sufficient information. |
| Supporting actor | Mock Commerce Provider |
| Preconditions | Case exists; provider interface and versioned approved corpus are available. |
| Success condition | A valid proposal and review result are stored and the case reaches `AWAITING_APPROVAL`. |
| Failure condition | No proposal is represented as actionable; the case waits for information or escalates with an explicit reason. |
| Authority | Agents may read authorised case/order/corpus data and write typed analysis and audit records; they may not alter order, payment, inventory, or logistics state. |
| Traceability | FR-002 to FR-008, FR-011; NFR-001, NFR-003, NFR-005 to NFR-009; BR-001, BR-002, BR-005 |

Main success scenario:

1. Customer submits an eligible return/remedy request through UC-01.
2. The system automatically verifies the order and affected line item through the provider
   interface and classifies the request.
3. The system builds an evidence matrix showing present, missing, and
   conflicting evidence.
4. The system retrieves relevant versioned store-policy or approved-guidance
   passages with source locations.
5. The system drafts a typed, non-executable proposal containing remedy option,
   rationale, alternatives, confidence, citations, and unresolved questions.
6. An independent Risk Reviewer verifies claims, citation support, conflicts,
   authority boundaries, and untrusted-content handling.
7. The system stores the proposal version and review result.
8. The case moves to `AWAITING_APPROVAL` and becomes visible to the Founder.

Extension and failure scenarios:

- **1a - Unauthorised assessment request:** deny access and preserve the case.
- **2a - Likely typo or insufficient order detail:** move to
  `AWAITING_INFORMATION` and request correction rather than labelling the
  customer as risky.
- **2b - Confirmed order/customer conflict or suspected abuse:** create a risk
  finding and move to `ESCALATED`.
- **2c - Provider unavailable:** preserve authoritative state and retry within
  policy; if the retry limit is reached, move to `ESCALATED` with the provider
  failure reason and do not invent an order snapshot.
- **3a - Missing evidence:** invoke UC-01E and resume from the interrupted step.
- **4a - Missing source or source conflict:** preserve the relevant passages,
  avoid a definitive legal claim, and escalate with the reason.
- **5a - Invalid typed output:** reject it and retry within the configured
  limit; if the limit is reached, move to `ESCALATED` with a typed validation
  failure and no actionable proposal.
- **6a - Unsupported or citation-mismatched claim:** return to proposal revision.
- **6b - Low confidence, out-of-scope content, sensitive evidence, or prompt
  injection:** stop automated progression and escalate.

Observable acceptance evidence includes at least 90% supported-class accuracy,
95% mandatory-information recall, 85% remedy-category agreement, 90% citation
correctness, 95% risk-case escalation recall, and median complete-case proposal
time below 120 seconds.

### 4.6 UC-03 - Review and decide proposal

| Field | Specification |
|---|---|
| Goal | An accountable human records an informed and precisely scoped decision. |
| Level | User goal |
| Primary actor | Authorised Founder / Operations Manager |
| Supporting actor | Simulated Notification Provider for a rejected or manually resolved customer outcome |
| Preconditions | Actor is authenticated and authorised; case is `AWAITING_APPROVAL`; the displayed proposal version is current. |
| Trigger | Founder opens a pending approval item. |
| Success condition | The chosen approve, reject, revision, or escalation outcome is immutably recorded; only approve creates a valid, exact-scope permission. |
| Failure condition | The requested decision cannot be safely recorded because authorisation, freshness, validation, or persistence fails; no new permission or workflow transition is created. |
| Authority | Only the authenticated human may approve. Navigation, silence, prior approvals, and model confidence never imply approval. |
| Traceability | FR-009, FR-011, FR-012; NFR-001, NFR-002, NFR-003, NFR-004, NFR-008, NFR-009 |

Main success scenario:

1. Founder opens the pending case.
2. The system shows authoritative state, statements, order facts, evidence
   matrix, source passages, proposal version, confidence, risks, and questions.
3. Founder chooses `Approve` and specifies the permitted remedy, command scope,
   amount limit where relevant, expiry, and reason.
4. The system verifies actor authority, current proposal version, case state,
   and scope completeness.
5. The system creates an immutable `ApprovalRecord` from the trusted identity.
6. The case moves to `APPROVED`, and the decision is audited.
7. UC-04 becomes eligible for the approved scope only.

Extension and failure scenarios:

- **3a - Reject:** record the founder-approved customer-facing reason, move to
  `REJECTED`, execute nothing, and close only after the simulated notification
  result and audit event are recorded.
- **3b - Request revision:** record the instruction and return to
  `POLICY_ASSESSMENT` without preserving any action permission.
- **3c - Manual escalation:** record the handoff and move to `ESCALATED`. The
  case closes only after the Founder later records a manual outcome and the
  simulated notification result is audited.
- **4a - Stale proposal or changed case:** block the decision and require a
  refresh and re-review.
- **4b - Unauthorised actor:** deny the action and record a security event.
- **4c - Missing command scope, reason, expiry, or required amount limit:**
  reject the approval as incomplete.

### 4.7 UC-04 - Execute approved simulated action

| Field | Specification |
|---|---|
| Goal | Complete exactly the authorised simulated remedy once and retain a traceable result. |
| Level | User goal |
| Primary authorising actor | Authorised Founder / Operations Manager |
| Supporting actors | Mock Commerce Provider; Mock Logistics Provider; Simulated Notification Provider |
| Preconditions | Case is `APPROVED`; approval is current, unexpired, and scoped to the exact case, proposal, commands, and applicable amount. |
| Trigger | Founder's approve action in UC-03 commits the exact action plan and trusted approval reference. No second approval or submission is implied. |
| Success condition | All authorised simulated commands succeed, each causes at most one effect, results and audit events are stored, the approved outcome is sent, and the case reaches `CLOSED`. |
| Failure condition | No unapproved action executes; provider failures remain retry-safe and visible. |
| Authority | The system may call only the mock commands listed in the approval and never moves real money. |
| Traceability | FR-010, FR-011; NFR-002 to NFR-004, NFR-006 to NFR-009; BR-003, BR-004 |

Main success scenario:

1. Founder's approve action in UC-03 supplies the exact action plan and trusted
   approval reference.
2. The orchestrator receives that committed plan without asking for a second
   decision.
3. The system validates case, proposal version, permitted commands, amount, and
   expiry against the trusted approval record.
4. The system creates typed commands with stable idempotency keys.
5. The system checks whether each command already has a successful result.
6. The system invokes the relevant mock provider for unfinished commands only.
7. Results and audit events are persisted before the next transition.
8. The case moves to `RESOLVED`, and the outcome becomes visible to the Founder.
9. The simulated notification provider sends the approved outcome and any
   return instructions to the customer.
10. After notification and audit completion are confirmed, the case moves to
    `CLOSED`.

Extension and failure scenarios:

- **1a - Unauthorised execution request:** deny the request and record a
  security event.
- **3a - Missing, expired, stale, or mismatched approval:** block before any
  provider call and record `BLOCKED_NO_APPROVAL` or an equivalent typed result.
- **5a - Duplicate request:** return the prior result without another provider
  call.
- **6a - Timeout or provider error:** move to `ACTION_FAILED` and retry with the
  same idempotency key within the configured limit.
- **6b - Partial composite execution:** preserve successful results and resume
  unfinished commands only.
- **6c - Retry limit reached:** move to `ESCALATED` and show the Founder the
  exact completed and failed steps.
- **9a - Notification failure after remedy success:** keep the case `RESOLVED`,
  retry notification independently, and never repeat an operational command.

Observable acceptance evidence includes at least 95% successful mock tool
operations on the standard benchmark, 100% blocking of invalid approval paths,
and at-most-one effect for every idempotency key.

### 4.8 UC-05 - Inspect case status and audit trail

| Field | Specification |
|---|---|
| Goal | Understand the authoritative state, pending decision, and history of a case. |
| Level | User goal |
| Primary actor | Authorised Founder / Operations Manager |
| Preconditions | Actor is authenticated and authorised for the case. |
| Trigger | Founder opens the case dashboard or a specific case. |
| Success condition | Current state, proposal, evidence, sources, risks, approvals, commands, and ordered audit history are displayed from authoritative records. |
| Failure condition | No misleading partial state is presented; access or retrieval failure is explicit and auditable. |
| Authority | Read access does not create an approval or alter the workflow. |
| Traceability | FR-011, FR-012; NFR-001, NFR-003, NFR-008, NFR-009 |

Main success scenario:

1. Founder selects a case or the pending-approval queue.
2. The system authorises access and reads authoritative case and audit records.
3. The dashboard shows current state, current proposal version, evidence,
   citations, risks, approval status, tool outcomes, and event chronology.
4. Founder may proceed to UC-03 only when the case is awaiting approval.

Extensions:

- **2a - Unauthorised actor:** deny access and record a security event.
- **2b - Read failure or incomplete audit data:** show an explicit unavailable
  state and correlation ID instead of a stale or fabricated result.

## 5. Consistency and traceability across the three views

| Stakeholder concern | Ad-hoc view | Feature view | Use-case view | Canonical baseline |
|---|---|---|---|---|
| Submit and clarify a request | AH-01, AH-02 | Case Intake | UC-01, UC-01E | FR-001, FR-002, FR-005 |
| Verify order, type, and evidence | AH-03 to AH-05 | Case Investigation | UC-02 | FR-003 to FR-005 |
| Ground, propose, and review risk | AH-06 to AH-08 | Grounded Decision | UC-02 | FR-006 to FR-008, NFR-001 |
| Preserve human authority | AH-09 | Governed Operations | UC-03 | FR-009, NFR-002, BR-003, BR-005 |
| Execute safely, notify, and avoid duplicate effects | AH-10, AH-15, AH-19 | Governed Operations plus provider XOR groups | UC-04 | FR-010, NFR-004, NFR-009 |
| Reconstruct and monitor cases | AH-11, AH-12 | Audit and Oversight | UC-05 | FR-011, FR-012, NFR-008 |
| Meet measurable quality | AH-13 to AH-18 | Feature attributes `[C]` | Preconditions, success/failure conditions, authority | NFR-001 to NFR-009 |

Coverage rules:

1. Every mandatory `FR` appears as one feature leaf and in at least one use case.
2. Every mandatory `NFR` constrains named features and observable use-case
   conditions; quality is not represented as an optional checkbox.
3. Every high-impact path reaches UC-03 before UC-04.
4. Every failure or uncertainty path waits for information, revises, rejects,
   or escalates; it never silently becomes approval.
5. Optional features preserve all governing business rules and inherit the
   applicable NFRs.

## 6. Model findings carried into the implementation backlog

Lab 3 completes the requirements model, not the Stage 2 implementation. The
modelling exercise exposed these traceable implementation gaps:

- The Stage 2 Pydantic implementation must supply trusted authentication and
  authorisation identity; `ApprovalRecord.approver` cannot remain an arbitrary
  client string.
- The Stage 2 approval implementation must bind to a proposal version and
  either an approved action plan or an explicit set of permitted commands.
- The approval schema must allow reject, revision, and escalation decisions
  without requiring a permitted remedy or command; only an approve decision
  grants a precisely scoped permission.
- The Pydantic models must implement the conceptual `EvidenceAssessment`
  structure for required, present, missing, and conflicting evidence.
- The Pydantic `PolicyPassage` must implement reproducible source version,
  content hash, and retrieval metadata.
- `ToolCommand` must carry case/proposal bindings and an allowlist version; the
  dispatcher must validate them before every initial call and retry.
- `AuditEvent` must add correlation, component/source version, outcome, typed
  error, and redaction metadata from the conceptual class model.
- Case transitions need an enforced transition service; direct status
  assignment is not sufficient evidence for the state model.
- Clarification, order-not-found, provider-failure, stale-approval, duplicate,
  retry-limit, prompt-injection, unauthorised-tool, and approval-bypass paths
  need automated tests.
- Evaluation labels that imply an automatic legal conclusion should be changed
  to neutral approved-guidance and source-conflict labels before the benchmark
  is treated as ground truth.

These findings should become separate implementation issues. They do not add
new autonomous authority or expand the current Lab 3 scope.

## 7. Laboratory 3 completion checklist

- [x] One coherent stakeholder-language ad-hoc specification is recorded.
- [x] Ambiguities, conflicts, assumptions, and non-scope are resolved explicitly.
- [x] A FODA model records mandatory/optional features, XOR variation points,
  option groups, attributes, and cross-tree constraints.
- [x] A use-case boundary diagram records external actors, `include`, `extend`,
  and authority boundaries; the UC-03 approval action is specified as UC-04's
  trigger rather than as a sequence edge.
- [x] Six actor-goal use cases specify trigger, authority, preconditions,
  success, failure, main flow, and extensions.
- [x] FR-001 to FR-012 and NFR-001 to NFR-009 are traceable across all views.
- [x] The human approval and no-legal-determination boundaries are preserved.
- [x] No course PDF, credential, or real customer data is included.
- [ ] Team peer review and tutor feedback are still required before the Stage 1
  baseline is frozen.
