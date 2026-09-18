# Laboratory 3 - Requirements Modelling

> **Course activity**: ELEC5620 Week 4, Laboratory 3
>
> **Project**: ReturnOps AU
>
> **Tracking**: [GitHub Issue #1](https://github.com/shuxiachai/returnops-au/issues/1)
>
> **Status (2026-09-07)**: v1.0 alignment draft of the completed v0.2 Lab 3
> modelling artefact. This revision and individual contributions still require
> peer/tutor review; historical completion is not current acceptance. The
> rc.2 alignment was published in [PR #9](https://github.com/shuxiachai/returnops-au/pull/9).
> The current `1.0.0-rc.5` contract/model review candidate for
> [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32) uses
> [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) as its review entry;
> check that PR for the actual head and reviews. rc.3 is an earlier candidate,
> and current human acceptance remains pending.
>
> **Product authority**: [Lead-approved v1.0 candidate](00-project-definition-v1.md).
> [Requirements and backlog](04-requirements-and-backlog.md) is a derived index;
> [frozen allocation](07-frozen-work-allocation.md) and
> [work packages](08-delivery-work-packages.md) govern ownership and delivery.

The Laboratory 3 note asks the team to model the same project requirements
through three complementary approaches: ad-hoc, feature-oriented, and use case.
It does not prescribe a page count or submission template. This document keeps
one stable requirement baseline and shows how each approach adds a different
kind of precision.

The course PDF was reviewed locally and is intentionally not copied into this
repository. Only the team's original project analysis is committed.

## 1. Modelling objective and system scope

ReturnOps AU helps one Human Founder operating a single Australian online store handle physical-goods
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
- `OF-xxx`: product option; selected A3/B3/C3 options are course deliverables,
  integrated after their respective prerequisites rather than all postponed;
- `UC-xx`: actor-goal use case.

## 2. Part One - Ad-hoc approach

### 2.1 Informal stakeholder narrative

In the desk-research-informed synthetic reference workflow, a founder receives a customer message, searches for an
order, checks fulfilment and payment data, reads a store policy, considers the
customer's evidence, and decides what to do. These facts are spread across
several systems. The process is slow, repeated for every case, and vulnerable
to inconsistent interpretation. This narrative and the quoted needs below are
team-authored modelling inputs, not interview quotations or observed merchant
timings. The measured student-operator baseline remains future evaluation work.

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
| AH-03 | "Show whether the order and affected items really match the request." | FR-003 |
| AH-04 | "Separate the issue category, what the customer wants, the possible basis, and what the evidence supports." | FR-004 |
| AH-05 | "Show which evidence supports the case, which evidence conflicts, and what is still absent." | FR-005 |
| AH-06 | "Show the actual policy or approved-guidance passage behind a recommendation." | FR-006, NFR-001 |
| AH-07 | "Give the founder a proposal with reasons, alternatives, uncertainty, and unresolved questions." | FR-007 |
| AH-08 | "Show material source conflicts; if they prevent a safe proposal, stop and hand the case to me." | FR-008, BR-002, BR-005 |
| AH-09 | "The founder must control every decision that can affect money, an order, inventory, or paid logistics." | FR-009, NFR-002, BR-003 |
| AH-10 | "Execute only the exact approved simulated action and never perform it twice by accident." | FR-010, NFR-004 |
| AH-11 | "Let a reviewer reconstruct who or what decided, changed, approved, and called a tool." | FR-011, NFR-008 |
| AH-12 | "Give the founder one reliable view of current cases and pending decisions." | FR-012 |
| AH-13 | "Prepare a reviewable packet promptly, and measure the processing time instead of assuming how long manual work takes." | NFR-005 |
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
| "Policy grounding" | Could hide disagreement between store policy and approved guidance. | Preserve both passages and findings in a version-bound `RiskReview`; a non-blocking difference may warn, an unresolved blocking conflict must escalate. BR-002 prohibits silent precedence. |
| "Automatic handling" | Could imply autonomous refund, replacement, repair, or shipment. | Investigation may be automated; every high-impact command requires risk review and exact-scope human approval. |
| "Fast" | Has no reproducible measurement boundary. | Target p95 <120 seconds from accepted complete input to stored review-ready proposal; include machine revision/risk loops, exclude human/physical waiting only. Report p50/p95, failures and environment. |
| "Correct citations" | Mixes whether a citation exists with whether it supports the claim. | Citation coverage target is 100%; benchmark citation correctness target is at least 90%. |
| "Integration" | Could require unsafe production credentials and real transactions. | Read-only mock orders and mock return/label/notification are core. A3 is a selected independent logistics sandbox/test adapter, subject to actual test access and no real shipment/charge; production integration is excluded. |

### 2.4 Assumptions, constraints, and explicit non-scope

- The prototype supports English-language requests about Australian physical
  goods and an existing or claimed order.
- The three supported request types are faulty product, wrong item, and change
  of mind. Ambiguous and other requests wait for information or escalate.
- Orders, customers, policies, attachments, payments, returns, and labels are
  synthetic or de-identified.
- One case references one order with one or more relevant line items; one
  return shipment has one parcel and one simulated label, not split shipments.
- The approved guidance corpus is curated and versioned offline by the team;
  the MVP does not include a policy-administration UI.
- The prototype does not give legal advice, make a definitive ACL entitlement
  determination, move real money, or mutate a production order.
- A3 logistics test integration, B3 limited analytics and C3 image observations
  are selected course work, subject to their own prerequisites. Other product
  options and portfolio middleware are not current delivery commitments.
- Domain Service is the sole business-state write entry point. Coordinator and
  Assessment (A), independent Risk Reviewer (C), and thin orchestration return
  results/requests to deterministic validation and persistence services. The
  Operations Service is deterministic, not a fourth AI role.

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
| Commerce Adapter | XOR `1..1` per deployment | Mock selected for MVP; OF-003 development-store adapter unselected | Preserves a stable order interface while changing provider. |
| Logistics Adapter | XOR `1..1` per configured execution | Core mock; OF-004 independent sandbox/test adapter selected as A3 | Demonstrate adapter substitution under the same approval/recovery rules, never two providers for the same effect. |
| Retrieval Strategy | XOR `1..1` per retrieval-enabled configuration | Keyword/BM25 selected; semantic/hybrid portfolio only | Required experiment B1 has no retrieval; B4 uses the selected strategy. |
| Product Extensions | Option group `0..*` in the product family | OF-001/C3 and OF-006/B3 selected; OF-002/005/007 unselected | This team's selected options are required course work after their prerequisites. |

### 3.2 Important feature constraints

- A typed proposal requires both an evidence matrix and approved-source
  grounding (`FR-007 requires FR-005 and FR-006`).
- Risk review requires a versioned typed proposal (`FR-008 requires FR-007`).
- Operational execution requires a current `PASS` or `PASS_WITH_WARNING` review and a valid, exact-scope
  founder approval (`FR-010 requires FR-008 and FR-009`).
- The founder dashboard requires authoritative audit and state data
  (`FR-012 requires FR-011`).
- A3 requires independent sandbox/test access, provider interfaces, approval
  enforcement, reconciliation, idempotency, credential protection and allowlisting.
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
modified Cockburn approach, the textual scenarios below give detail beyond an
oval. They remain subordinate to `docs/00` for product requirements and must
be reviewed alongside the diagrams; this alignment does not freeze new scope.

### 4.1 Actors and actor goals

| Actor | Goal | Boundary decision |
|---|---|---|
| End Customer | Lodge a request and supply missing information or evidence | May write only customer statements/evidence; cannot approve or invoke tools |
| Human Founder | Make an informed, accountable, scoped decision | The single store operator; server-authenticated authority and one current proposal or manual-only no-proposal target |
| Mock Order Provider | Supply read-only order facts | Lookup cannot mutate orders or perform a remedy |
| Mock Returns Provider | Execute an approved simulated return command | No real refund, order/inventory mutation, remedy decision or unapproved command |
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
| UC-02 | Obtain an evidence-grounded packet and risk assessment | Human Founder; customer submission/clarification triggers internal preparation | FR-002 to FR-008, FR-011 |
| UC-03 | Review a proposal or record a no-proposal manual outcome | Authorised Founder | FR-009, FR-011, FR-012 |
| UC-04 | Execute exactly the approved simulated return and label | Founder approval from UC-03; Returns/Logistics/Notification Providers support | FR-010, FR-011 |
| UC-05 | Inspect case status and audit history | Authorised Founder | FR-011, FR-012 |

Specification ownership is A: UC-03/04; B: UC-01/01E; C: UC-02/05.
Individual model chains remain A `AH-10 → UC-04`, B `AH-01 → UC-01`,
C `AH-08 → UC-02`, each with their own activity, sequence and state-machine
model. Shared diagrams are not substitutes for these individual artefacts.
Existing authored work is reused with its history; this lead-led alignment does
not count as another member's independent authorship or completed review.

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

1. Customer enters the original problem description, optionally supplying a
   requested outcome, known order identifier and evidence.
2. The system validates input formats, file restrictions, and untrusted-content
   boundaries.
3. The system preserves the original statement and accepted evidence.
4. Domain Service creates a unique `ReturnCase` in `SUBMITTED`; repeated
   submission keys return the same case rather than creating another one.
5. The system extracts typed facts and identifies missing mandatory information.
6. With sufficient information, the case moves to `UNDER_INVESTIGATION`.
7. The system returns the case ID and the next expected step.

Extension and failure scenarios:

- **2a - Invalid or unsafe attachment:** reject that attachment, explain the
  restriction, retain safe form data, and do not pass its content to tools.
- **3a - Persistence failure:** create no partial duplicate; return a retryable
  error and a correlated diagnostic event.
- **4a - Lost response or duplicate click:** retry the same submission key;
  do not infer failure and generate a new case key automatically.
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
2. The system validates case access, `AWAITING_INFORMATION`, the current
   `question_set_id`, `expected_case_version`, requested answers/evidence,
   format, attachment restrictions and the untrusted-content boundary.
3. The system append-only preserves the new statement and accepted evidence.
4. Domain Service validates and persists typed facts and the `PRESENT`,
   `MISSING`, `CONFLICTING`, or `NOT_APPLICABLE` evidence assessment without
   overwriting the original statement. Affected old proposals/reviews/approvals
   cannot remain valid for changed input.
5. When mandatory information is sufficient, the case returns to
   `UNDER_INVESTIGATION` and resumes UC-02.

Extension and failure scenarios:

- **2a - Unsafe or unsupported attachment:** reject that attachment, retain
  safe text, and explain the restriction.
- **2b - No current question set, wrong state or stale version:** reject the
  fresh request without accepting input or starting analysis; show the current
  authorised clarification view. Same-key accepted replay remains a replay,
  not permission to submit a new answer to a replaced question set.
- **4a - Information is still incomplete:** keep `AWAITING_INFORMATION` and ask
  only the remaining questions; the customer may repeat UC-01E.
- **4b - New information creates a confirmed conflict:** preserve both versions
  and let UC-02 create the risk finding or escalation.
- **5a - Persistence or notification failure:** do not lose the accepted
  statement or create a duplicate; expose a retryable, correlated error.

This extension supplies requested clarification only. It does not add a general
customer edit/upload endpoint after intake. Material-input transitions from
`AWAITING_APPROVAL` or `APPROVED` refer to controlled internal updates, such as a
refreshed authorised order snapshot: Domain Service checks source provenance,
authority and current version before invalidating dependent proposal, review
and approval. Existing or unresolved effects remain in history; an accepted
manual/rejection outcome is not silently reopened by an observation.

### 4.5 UC-02 - Assess case and prepare proposal

| Field | Specification |
|---|---|
| Goal | Have an eligible request assessed and prepared for a responsible human decision without taking a high-impact action. |
| Level | User goal |
| Primary actor | Human Founder, who needs the reviewed decision packet. |
| Primary trigger | UC-01/UC-01E supplies sufficient information, or an authorised revision resumes assessment; no extra customer assessment button is implied. |
| Supporting actor | Mock Order Provider |
| Preconditions | Case exists; provider interface and versioned approved corpus are available. |
| Success condition | A versioned non-executable packet and current `PASS/PASS_WITH_WARNING` review are stored; the case reaches `AWAITING_APPROVAL`. |
| Failure condition | No proposal is represented as actionable; the case waits for information or escalates with an explicit reason. |
| Authority | Agents read authorised inputs and return structured outputs only. Domain Service validates, persists and routes them; agents cannot write business state, create approvals or dispatch operations. |
| Traceability | FR-002 to FR-008, FR-011; NFR-001, NFR-003, NFR-005 to NFR-009; BR-001, BR-002, BR-005 |

Main success scenario:

1. The accepted case or revision enters the bounded assessment workflow.
2. Assessment obtains a read-only order snapshot and relevant line items. The
   system separately records `IssueCategory`, `CustomerRequestedOutcome`,
   `PossibleBasis` and `AssessmentStatus`; recommendations cannot overwrite them.
3. Assessment builds a criterion-level evidence matrix using `PRESENT`,
   `MISSING`, `CONFLICTING` and `NOT_APPLICABLE`.
4. The system retrieves relevant versioned store-policy or approved-guidance
   passages through C1. Results contain source ID/type, version when available,
   access date, location, content hash and retrieval time. Conflicts remain visible.
5. Assessment drafts a versioned, non-executable `DecisionPacket` referencing
   the original statement, with a conditional recommendation, rationale,
   alternatives, confidence, citations, questions and relevant return-cost facts.
6. An independent Risk Reviewer verifies claims, citation support, conflicts,
   authority boundaries and untrusted-content handling in a separate invocation
   and system prompt, without the generator's hidden reasoning or edit authority.
7. Domain Service validates and stores the proposal and version-bound review,
   rejecting stale results and malformed outputs.
8. Only `PASS` or `PASS_WITH_WARNING` permits `AWAITING_APPROVAL`; the packet
   and any warning become visible to the Founder without granting execution rights.

Extension and failure scenarios:

- **1a - Unauthorised assessment request:** deny access and preserve the case.
- **2a - Likely typo or insufficient order detail:** move to
  `AWAITING_INFORMATION` and request correction rather than labelling the
  customer as risky.
- **2b - Confirmed order/customer conflict:** Domain Service preserves the
  accepted `OrderLookupResult.CONFLICT` as an `OrderLookupBlock`, bound to
  the current case/input, and moves to `ESCALATED` before any proposal exists.
  Show a safe conflict summary; do not invent a technical failure or a Risk
  review. UC-03 permits only a manual outcome targeting this current block.
  Suspicion requiring proposal-level assessment remains evidence for Risk;
  it is not sufficient to fabricate an order-provider `CONFLICT` result.
- **2c - Provider unavailable:** preserve authoritative state and retry within
  policy; if the retry limit is reached, move to `ESCALATED` with the provider
  failure reason and do not invent an order snapshot. If there is no current
  proposal, preserve the actual technical error in `ProcessingFailure` for
  UC-03 manual handling.
- **2d - Provider authority denied:** record `AUTHORITY_DENIED`, do not retry
  as if it were a transient match failure, and escalate with the denial reason
  without inventing a snapshot. Persist the accepted result as an
  `OrderLookupBlock` with status `AUTHORITY_DENIED`; it is a provider lookup
  block, distinct from a caller's unauthorised API request and from a technical
  processing error. The same manual-only UC-03 branch applies.
- **3a - Missing evidence:** invoke UC-01E and resume from the interrupted step.
- **4a - Missing source or source conflict:** preserve absence/conflicting
  passages; C1 verifies citation resolvability/content and C2 checks claim support
  and significance. Non-blocking differences can warn; an unresolved material
  conflict preventing a safe recommendation must escalate. Never silently choose
  source precedence or invent a citation. Preserve that conflict in the
  conditional packet and independent review; it cannot create an
  `OrderLookupBlock` or substitute a technical failure for a business finding.
- **5a - Invalid typed output:** reject it and retry within the configured
  limit; if the limit is reached, move to `ESCALATED` with a typed validation
  failure and no actionable proposal.
- **6a - `REVISE`:** return to Assessment, create a new proposal version and
  independently review it again; previous approval cannot carry over.
- **6b - `NEEDS_INFORMATION`:** return to Coordinator/UC-01E; preserve the
  question and input history, then regenerate and review the affected proposal.
- **6c - `ESCALATE`:** route the reasons to the Founder for manual handling.
  This proposal cannot be approved for execution; a resumed executable path
  requires a new proposal and new `PASS/PASS_WITH_WARNING` review.
- **6d - Reviewer timeout, malformed or stale output:** fail closed; bounded
  recovery may retry review but cannot turn a technical failure into `PASS`.
- **7a - Machine revision limit reached:** retain the trace and escalate. No
  infinite loop or silent fall-through to approval is allowed.

Acceptance targets: category macro-F1 ≥0.85 (stretch ≥0.90), information recall
≥95%, unnecessary follow-up ≤15%, packet completeness ≥95%, citation correctness
≥90%, risk recall ≥95% and specificity ≥80%; critical-fact fabrication is zero
on the frozen negative set. p95 accepted-complete-input to stored-review-ready
proposal is <120 seconds, including machine revision/risk loops and excluding
human/physical waiting only. These are targets, not results. Apply the 30-case
Gold protocol and raw-count/denominator rules in `docs/00` and `docs/07`.

### 4.6 UC-03 - Review a proposal or record a no-proposal manual outcome

| Field | Specification |
|---|---|
| Goal | An accountable human records an informed and precisely scoped decision. |
| Level | User goal |
| Primary actor | Human Founder |
| Supporting actor | Simulated Notification Provider for a rejected or manually resolved customer outcome |
| Preconditions | Actor is authenticated and authorised. A proposal-target decision uses the current proposal. `APPROVE` additionally requires `AWAITING_APPROVAL` and current `PASS/PASS_WITH_WARNING`. An `ESCALATED` proposal may be revised or manually handled, never directly approved. Without a current proposal, the case must be `ESCALATED` with exactly one current `ProcessingFailure` or `OrderLookupBlock`; only `MANUAL_HANDLING` is available. |
| Trigger | Founder opens a pending decision item or an escalated case requiring manual handling/revision. |
| Success condition | The decision records a trusted actor, case, reason/outcome, timestamp and exactly one current target: proposal ID/version, processing failure ID or order-lookup block ID. Only proposal-target approval grants exact-scope permission; both no-proposal targets record only a manual outcome and notification work. |
| Failure condition | The requested decision cannot be safely recorded because authorisation, freshness, validation, or persistence fails; no new permission or workflow transition is created. |
| Authority | Only the authenticated human may approve. Navigation, silence, prior approvals, and model confidence never imply approval. |
| Traceability | FR-009, FR-011, FR-012; NFR-001, NFR-002, NFR-003, NFR-004, NFR-008, NFR-009 |

Main success scenario:

1. Founder opens the pending case.
2. The system shows authoritative state, statements, order facts, evidence
   matrix, source passages, proposal version, confidence, risks, and questions.
3. Founder chooses `APPROVE`, reviews the exact proposed command set and
   parameters, applicable amount ceiling and expiry, and supplies a reason.
4. The server verifies trusted actor authority, current case/proposal/review,
   state and exact scope. Browser flags or a submitted role are not authority.
5. Domain Service records the decision and `ApprovalRecord` binding actor,
   case ID, proposal ID/version, commands, parameter fingerprint, applicable
   amount ceiling and expiry.
6. Domain Service moves the case to `APPROVED` and records the audit event.
7. UC-04 becomes eligible for the approved scope only.

Extension and failure scenarios:

- **3a - `REJECT`:** record the customer-facing reason and intended rejected
  outcome, execute no return/label, enter notification processing and reach
  terminal `REJECTED` only after notification succeeds and is audited.
- **3b - `REQUEST_REVISION`:** record the instruction and return to
  `POLICY_ASSESSMENT` with no continuing action permission; require a new
  proposal and independent review.
- **3c - `MANUAL_HANDLING`:** record the manual outcome, execute no return/label
  through this decision, and notify it; terminal `MANUAL_HANDLED` requires a
  recorded outcome and successful notification. An unresolved escalation is not
  a completed manual outcome.
- **4a - Stale proposal or changed case:** block the decision and require a
  refresh and re-review.
- **4b - Unauthorised actor:** deny the action and record a security event.
- **4c - Missing command scope, reason, expiry, or required amount limit:**
  reject the approval as incomplete.
- **4d - `ESCALATE`, missing/stale review or changed parameters:** block approval
  before effects. An escalated proposal or material input/proposal/scope change
  requires a new proposal and passing review. A purely technical review failure
  may retry review of unchanged inputs/version within policy; no result is
  treated as a pass by default. High confidence cannot override the guard.
- **5a - Decision persistence failure:** no permission is created; retry with
  the same request key and show a correlated error rather than claiming success.
- **3d - Rejection/manual notification fails:** retain `NOTIFICATION_PENDING`
  or `NOTIFICATION_FAILED`; retry notification only, without executing a remedy.
- **3e - Historical operation is later confirmed:** preserve the accepted
  rejection/manual outcome and its notification identity. Store the historical
  observation and audit without new commands, execution notification, case
  reopening or automatic `COMPLETED`; successful delivery of that outcome
  still selects `REJECTED` or `MANUAL_HANDLED`.
- **1a - No current proposal after technical failure or an order-lookup block:**
  show the server-recorded safe summary and actual manual-outcome entry.
  Submit `expected_case_version`, `MANUAL_HANDLING`, the outcome in `reason`,
  and exactly one `processing_failure_id` or `order_lookup_block_id`.
  Domain Service loads the authoritative case and target, checks `ESCALATED`,
  absence of a current proposal, current case/input/target identity and trusted
  Founder access, then atomically records the outcome, audit and notification
  work. It creates no proposal, review, preview, approval or return/label work.
  `APPROVE`, `REJECT` and `REQUEST_REVISION` are unavailable on this branch;
  no new revision or restart endpoint is introduced. Preserve historical
  approvals, completed operations and unknown effects. After notification
  succeeds, the terminal state is `MANUAL_HANDLED`, not simulated completion.
- **1b - Missing, mixed, stale or wrong-case no-proposal target:** reject the
  new decision without a state change or new work. A prior accepted request
  replay first requires current authentication/access and reuses its acceptance
  fact: return the original receipt only while its body remains readable. After
  permitted deletion return 409 INVALID_STATE/retryable=false, with no new write,
  scheduling or automatic new key; B reads current/history views. This does not
  make a historical target valid for a new decision.

### 4.7 UC-04 - Execute approved simulated action

| Field | Specification |
|---|---|
| Goal | Complete exactly the authorised simulated return and single parcel label once, then notify and retain a traceable result. |
| Level | User goal |
| Primary authorising actor | Human Founder |
| Supporting actors | Mock Returns Provider; Mock Logistics Provider (or A3's authorised no-charge test configuration); Simulated Notification Provider |
| Preconditions | Case is `APPROVED`; approval is current, unexpired, and scoped to the exact case, proposal, commands, and applicable amount. |
| Trigger | Founder's approve action in UC-03 commits the exact action plan and trusted approval reference. No second approval or submission is implied. |
| Success condition | Approved simulated return/label effects occur at most once, typed results/audit are stored, outcome notification succeeds, and the case reaches `COMPLETED`. No physical or financial completion is claimed. |
| Failure condition | No unapproved action executes; provider failures remain retry-safe and visible. |
| Authority | The system may call only the mock commands listed in the approval and never moves real money. |
| Traceability | FR-010, FR-011; NFR-002 to NFR-004, NFR-006 to NFR-009; BR-003, BR-004 |

Main success scenario:

1. UC-03 commits the trusted approval and exact action plan; the deterministic
   workflow consumes that reference without requiring a second approval.
2. Approval Guard revalidates trusted actor, case, current proposal/review,
   command set, parameter fingerprint, applicable ceiling and expiry.
3. Operations Service independently checks provider authority and the command
   allowlist; only simulated return and parcel-label operations are eligible.
4. Domain Service persists typed commands and operation-attempt records with
   stable idempotency keys, provider IDs and operation fingerprints.
5. The dispatcher checks stored results and confirmed-effect receipts first.
   A succeeded command is not repeated; a confirmed label awaiting its artifact
   uses G-ARTIFACT only. Without a receipt, query an unknown/orphaned attempt
   before considering another dispatch.
6. Operations Service invokes the provider only for authorised unfinished work.
   One case may include several line items from one order, but one shipment
   produces one label. Core mock and A3 providers are alternatives, not two effects.
7. Domain validates the original provider observation; HTTP success alone is
   insufficient. A confirmed label observation is not OperationResult: Domain
   first saves its minimal original effect receipt, audit and artifact-only work.
   Operations stores the original label under current G-ARTIFACT authority; only
   a validated label_evidence_id and full result committed with audit permit
   SUCCEEDED. Pending artifact work uses existing EXECUTING without result.
8. When all approved return/label results are stored and execution completion
   remains eligible, Domain Service atomically rechecks the current case and
   accepted outcome before persisting/reusing `RETURN_CREATED` notification
   work and entering `NOTIFICATION_PENDING`. An already accepted rejection or
   manual outcome takes priority; the Founder inspects operation facts separately.
9. The simulated notification provider sends the outcome, next steps and relevant
   packaging, drop-off, responsibility and cost information.
10. Domain Service rechecks the current notification and accepted outcome,
    records notification success/audit, and moves to `COMPLETED` only for
    `RETURN_CREATED` with the valid return/label results still saved.

Extension and failure scenarios:

- **1a - Unauthorised execution request:** deny the request and record a
  security event.
- **2a - Missing, expired, stale, or mismatched approval:** block before any
  provider call and record `BLOCKED_NO_APPROVAL` or an equivalent typed result.
- **3a - Provider authority denied or command not allowed:** block before any
  effect, record a typed denial and display it; approval does not imply provider permission.
- **5a - Duplicate request:** reuse stored acceptance/effect facts without a new
  provider invocation. For HTTP replay, authenticate/authorise first; return the
  original receipt only while readable, otherwise after permitted deletion return
  409 INVALID_STATE/retryable=false. Do not write/schedule or automatically change
  keys; B reads current/history. Original artifact recovery is not a second effect.
- **6a - Definite failure/no effect:** record `FAILED` and `ACTION_FAILED`;
  revalidate approval/authority and retry only if retry policy allows it, using
  the same command key and unchanged parameters.
- **6d - Ambiguous timeout:** record attempt `UNKNOWN`, then `RECONCILING`;
  query the provider by its ID/fingerprint. If success is confirmed, persist
  it without another effect; only confirmed absence/no effect permits a guarded
  retry. If the result remains unknown, retain that uncertainty and escalate
  for manual handling rather than labelling it safe to retry.
- **6b - Partial composite execution:** preserve successful results and resume
  unfinished commands only.
- **6c - Retry limit reached:** move to `ESCALATED` and show the Founder the
  exact completed, failed and uncertain steps, unless a rejection/manual outcome
  has already been accepted; preserve that outcome and its case/notification
  state. No fresh key may bypass reconciliation.
- **6e - Historical lookup after an accepted manual/rejection outcome:** update
  only the old attempt facts and audit. For example, return `SUCCEEDED`, label
  `UNKNOWN`, escalation and accepted `MANUAL_HANDLING` with notification pending
  must remain a manual outcome when the label later proves successful. Deliver
  the existing manual notification and reach `MANUAL_HANDLED`, never
  `COMPLETED`. If already sent, retain the terminal state with no resend; if
  lookup remains unknown, preserve uncertainty without reopening/escalating the
  closed outcome. A new effect still requires current dispatch authority.
- **7a - Provider success but local persistence failed:** reread durable receipt
  and original intent first. A confirmed-label receipt selects artifact recovery,
  never a new invoke or UNKNOWN due to file failure. Without reliable confirmation
  (including an unconfirmed receipt commit), query only the original provider
  identity; do not claim the external effect failed or a new status was saved.
- **7b - Label generated but artifact missing or storage fails:** retain the
  confirmed original effect receipt, audit and artifact-only work in EXECUTING,
  with no incomplete OperationResult. Current recovery identity/access, original
  binding, claim, provider read permission and retention govern query/retrieve/store
  of that label only. Expired creation approval does not grant new effect authority
  or block this independently authorised read/store work. A saved file with unknown
  result commit is verified/reused, never recreated; full label_evidence_id/result
  and audit must commit before SUCCEEDED. Preserve receipt/EXECUTING on failure;
  bounded exhaustion uses 6c without rewriting accepted manual/rejection outcome.
  Never restore deliberately deleted content or issue a second GENERATE_LABEL.
- **9a - Notification failure after return/label success:** keep
  `NOTIFICATION_PENDING/NOTIFICATION_FAILED`, retry notification independently,
  and never repeat an operational command.

Acceptance targets are zero unauthorised effects, zero duplicate effects and
zero illegal transitions across the parameterised suite, with explicit
provider-uncertainty and notification-failure evidence. Existing schema checks
alone cannot establish these runtime properties.

### 4.8 UC-05 - Inspect case status and audit trail

| Field | Specification |
|---|---|
| Goal | Understand the authoritative state, pending decision, and history of a case. |
| Level | User goal |
| Primary actor | Human Founder |
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
   citations, version-bound risks, exact approval scope, operation attempt/results,
   independent notification state and event chronology, subject to privacy rules.
   The accepted customer-facing outcome is shown separately from historical
   effects: a late successful label does not change an accepted manual outcome,
   and manual closure does not claim that an unknown effect never happened.
4. Founder can open the applicable UC-03 decision view; executable approval is
   offered only for the current approval-eligible proposal, not an escalation.

Extensions:

- **2a - Unauthorised actor:** deny access and record a security event.
- **2b - Read failure or incomplete audit data:** show an explicit unavailable
  state and correlation ID instead of a stale or fabricated result.
- **3a - Historical lookup changes operation facts:** refresh those facts and
  audit while retaining the accepted outcome and notification state. Read access
  and new historical knowledge do not authorise commands or a new terminal outcome.

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

The original Lab 3 artefact completed an initial requirements model, not Stage 2.
This aligned draft retains the implementation gaps below; actual resolution
requires code, tests and review under existing work packages, not just diagrams:

- The Stage 2 Pydantic implementation must supply trusted authentication and
  authorisation identity; `ApprovalRecord.approver` cannot remain an arbitrary
  client string.
- The Stage 2 approval implementation must bind to a proposal version and
  either an approved action plan or an explicit set of permitted commands.
- The decision schema must allow rejection, revision and manual-handling outcomes
  without requiring a permitted remedy or command; only an approve decision
  grants a precisely scoped permission.
- The Pydantic models must implement the conceptual `EvidenceAssessment`
  structure with present, missing, conflicting and not-applicable criteria.
- The Pydantic `PolicyPassage` must implement reproducible source version,
  content hash, and retrieval metadata.
- `ToolCommand` must carry case/proposal bindings and an allowlist version; the
  dispatcher must validate them before every initial call and retry. Separate
  `OperationAttempt` captures provider ID/fingerprint, typed results and
  `UNKNOWN/RECONCILING`; notification recovery cannot replay an operation.
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

Historically, the F.01 `1.0.0-rc.3` clarification preserved
rc.2's technical-failure target, complete retrieval-conflict hand-off, compatible
passage/citation capacities and analytics denominators. It added a separate
pre-proposal order-lookup block target and aligned the public idempotency header
with the shared identifier boundary. Actual state, authority, source-integrity
and aggregation guards still need implementation. Joint B/C contract/model
review of the current [F.01 `1.0.0-rc.5` candidate](09-interface-contract-v1.md)
at the exact reviewed PR head is pending; historical rc.2/rc.3 evidence does not establish that acceptance,
and no schema test authorises a fabricated proposal or technical error.

Map these findings to existing `docs/08` work packages and Jira items before
creating new tasks. They add neither autonomous authority nor new product scope.

## 7. Historical Laboratory 3 completion checklist (v0.2)

The checked items record the original Lab 3 deliverable's existence. They do not
claim that this v1.0 alignment has passed review, that every individual authored
their required models, or that Stage 1 is complete. Git history preserves the
original version and contributor record.

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

### v1.0 alignment review still required

- [ ] B verifies customer submission/clarification and the overall feature/use-case views.
- [ ] C verifies grounding/risk, conflict handling and the evaluation mapping.
- [ ] A/B/C review consistent vocabulary, guards and completion/notification semantics
  across this text, the five shared diagrams and the pending interface contract.
- [ ] Each member personally completes and explains their assigned requirement,
  use-case specifications and three individual behaviour models; shared class
  and complex-structure work also needs recorded participation from all three.
- [x] The earlier rc.2 alignment was published in PR #9, with B/C review requests.
- [ ] The `1.0.0-rc.5` candidate and its three decision targets receive
  B/C contract/model review at the exact reviewed PR head; original authorship remains attributable.
- [ ] Tutor feedback is recorded and dispositioned; the published revision
  receives current peer review and the required adoption evidence.
  Publication does not imply Jira acceptance or completion of individual models.
