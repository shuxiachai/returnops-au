# Team, Jira and GitHub Workflow

> **Allocation update — 2026-09-06:** New work follows
> [Frozen Work Allocation v1.0](07-frozen-work-allocation.md) and
> [Detailed Work Packages](08-delivery-work-packages.md). Those are the single
> source for nine-feature ownership, subtask acceptance and dependencies.
> The packages below are workflow context, not a second backlog. This file
> describes team rules, not verified live Jira or GitHub settings.

## 1. Team structure and planned workload

The team has three students. The lead owns backend, agent orchestration and
integration. B and C each own two independently demonstrable core functions and
one selected optional, with bounded interfaces and their own models, code,
tests and evidence.

The planning allocation across the three team members is approximately:

- Member A (`@shuxiachai`), Project Lead & System Architect (Backend & Agent Core): ~45%;
- Member B (`@ChengsiLi`), Frontend & User Experience Lead (Client & Operations Dashboard): ~27%;
- Member C (`@lulucas-tao`), Grounding, Risk & AI Evaluation Lead: ~28%;

This allocation plans for the Lab 2 requirement of at least two core features
and one optional implemented by each member. Actual compliance requires
individual implementation and evidence, not a table. All three selected
optionals remain course deliverables.

### Member A: Project Lead, System Architect & Backend/Agent Core Lead (~45%)

Primary responsibilities:

- product scope, requirement classification, and traceability matrix;
- architecture integration and A's own MBSE chain; every member authors their
  own behavioural models and participates in shared models;
- domain model, Pydantic schemas, database schemas, and FastAPI service;
- Coordinator and Assessment implementations and bounded orchestration;
  C supplies independent Risk Reviewer and retrieval modules;
- deterministic approval rules, audit event recording, and mock adapters;
- system integration, CI/CD foundation, Docker containerization, report integration, and presentation narrative.

**Lab 2 Deliverables**:
- *Core Feature 1*: Authoritative ReturnCase lifecycle, API, and PostgreSQL state.
- *Core Feature 2*: Exact-scope Founder approval and governed simulated execution.
- *Optional Feature*: Logistics sandbox/test adapter and recovery path.

### Member B: Frontend & User Experience Lead (~27%)

Primary responsibilities:

- user journey mapping, use case diagrams, and detailed use-case descriptions;
- UI/UX wireframes, design tokens, component architecture, and responsive design;
- Customer Submission and Clarification Portal (natural language input, evidence upload, real-time follow-up questions);
- Founder Operations & Approval Dashboard (case timeline, evidence/policy citation inspector, Approve/Reject/Revise actions);
- component tests, end-to-end user experience, and demo walkthrough.

**Lab 2 Deliverables**:
- *Core Feature 1*: Customer Return & Clarification Portal.
- *Core Feature 2*: Founder Review & Approval Dashboard.
- *Optional Feature*: Operations Analytics Dashboard (return trends and handling time metrics).

### Member C: Grounding, Risk & AI Evaluation Lead (~28%)

Primary responsibilities:

- acceptance criteria definition, quality metric thresholds, and requirements traceability;
- curated store policy corpus and reviewed ACCC consumer-guarantee guidance;
- 30 double-reviewed Gold return cases covering the supported categories,
  missing evidence, conflicts, and escalations;
- automated AI evaluation comparing the required single-LLM (`B1`) and governed
  multi-agent (`B4`) configurations on the same frozen cases;
- safety and prompt injection test suite, failure analysis, and benchmark reports.

**Lab 2 Deliverables**:
- *Core Feature 1*: Versioned Guidance Retrieval & Citation Verification.
- *Core Feature 2*: Independent Risk Review & Escalation.
- *Optional Feature*: Product-image Evidence Analysis.

Member C coordinates the Gold set, evaluation runner, `B1` versus `B4` report
and cross-system QA. A owns backend/state/approval/provider tests; B owns UI
tests; C owns grounding/risk/image tests. All three participate in independent
label review under the timing/blinding protocol in `docs/07`.
`B2`/`B3` ablations and any expansion towards 100 scenarios are portfolio work,
not course-release conditions.

## 2. Shared responsibilities

All members must still:

- participate in desk-research, scenario, and requirement reviews;
- understand the principal customer workflow and human-approval boundary;
- review assigned pull requests and respond to review feedback;
- test their own deliverables and provide integration evidence;
- rehearse the presentation and interview;
- record their individual contribution evidence.

## 3. Lightweight RACI

| Deliverable | Member A (Lead) | Member C (Grounding/QA) | Member B (Interface) |
|---|---|---|---|
| Problem validation | A | C | C |
| Requirements and traceability | A/R | C | C |
| UML and architecture | A/R | C | C |
| Domain API and database | A/R | C | C |
| Coordinator/Assessment, orchestration and execution guards | A/R | C | C |
| Retrieval and independent Risk Reviewer | A | R | C |
| Policy corpus | A | R | C |
| Evaluation case labels | A | R | C |
| Evaluation framework and analysis | A | R | C |
| Customer and founder screens | A | C | R |
| Synthetic order and shipment fixtures | A/R | C | C |
| Provider adapters | A/R | C | C |
| CI and deployment | A/R | C | C |
| Report integration | A/R | C | C |
| Demo walkthrough | A | R | R |
| Presentation and interview | A/R | R | R |

Legend: A = accountable, R = responsible, C = consulted. These are role letters,
not member names. Non-author reviewers are assigned in `docs/08`. Individual
model ownership and shared contributions follow `docs/07`; the lead does not
author every diagram.

## 4. Bounded work packages

Support work should be assigned as complete packages with inputs, outputs, and
acceptance criteria, not as open-ended responsibility for a subsystem.

### Package B-UX1: Customer submission and clarification

Input from lead:

- API contract;
- intake schema and validation rules;
- shared interface constraints; B owns wireframes and component conventions.

Output from Member B:

- order number, problem description, requested outcome, and evidence inputs;
- clarification-question and evidence-resubmission flow;
- loading, validation, success, and recoverable-error states;
- component and end-to-end tests for the owned flow.

Acceptance:

- the UI follows the typed API contract without embedding remedy rules;
- original customer statements remain distinguishable from extracted facts;
- the lead can run and integrate the flow from a clean checkout.

### Package B-UX2: Founder review and approval dashboard

Input from lead:

- proposal, risk, approval, and case-status API contracts;
- exact-scope approval actions;
- synthetic API fixtures and shared design tokens.

Output from Member B:

- cited evidence, risks, uncertainty, recommendation, and alternative displays;
- approve, reject, request-revision, and manual-handling controls;
- case timeline, pending-notification states, and repeatable demo fixtures.

Acceptance:

- high-impact actions are visibly separated from ordinary navigation;
- the screen never represents an unapproved proposal as completed;
- the full demo can be reset and repeated.

### Package C-AI1: Runtime guidance corpus and citation verification

Input from lead:

- source-selection and conflict rules;
- passage metadata schema;
- the three supported request categories.

Output from Member C:

- a small set of reviewed, versioned policy/guidance passages limited to the MVP;
- source identity, version/access date, location, and content hash;
- keyword/BM25 retrieval fixtures and citation-verification tests;
- documented material conflicts that must route to risk review.

Acceptance:

- every runtime passage is traceable and can be loaded without manual cleanup;
- retrieval returns resolvable citations and exposes material conflicts;
- this runtime corpus is not an evidence-management product or a continuation of
  the frozen requirements-research appendix.

### Package C-QA2: Risk review and coordinated evaluation

Input from lead:

- risk-review contract and escalation rules;
- shared case/proposal, error and metric contracts;
- B4 invocation and telemetry contract from A.

Output from Member C:

- independent `PASS`, `PASS_WITH_WARNING`, `REVISE`, `NEEDS_INFORMATION`, and `ESCALATE` outcomes;
- Gold-case schema, labelling guide and valid/invalid label examples authored
  by C and reviewed by the team; A does not own or write all of this input;
- 30 double-reviewed Gold cases;
- evaluation runner owned by C;
- required `B1` versus `B4` comparison report;
- aggregated safety/workflow results; each member implements the tests for
  their own functionality.

Acceptance:

- every Gold case follows the schema and contains no real personal data;
- each Gold label is authored and independently reviewed;
- unsafe or materially conflicted proposals cannot reach Operations;
- results reproduce from a recorded commit, configuration, and dataset version.

## 5. Repository strategy

Use a dedicated repository for this project. Do not initialise Git at the
ELEC5620 course-folder root because it contains lecture and practical files that
should not be published by accident.

Recommended repository name:

```text
returnops-au
```

Recommended top-level structure after implementation begins:

```text
returnops-au/
|-- .github/
|   |-- ISSUE_TEMPLATE/
|   `-- PULL_REQUEST_TEMPLATE.md
|-- apps/
|   |-- api/
|   `-- web/
|-- packages/
|   |-- agent_core/
|   |-- domain/
|   |-- evaluation/
|   `-- provider_adapters/
|-- docs/
|   |-- diagrams/
|   |-- adr/
|   `-- evidence/
|-- tests/
|   |-- fixtures/
|   `-- evaluation_cases/
|-- docker-compose.yml
|-- README.md
`-- LICENSE
```

The final public portfolio repository must contain only synthetic or
de-identified data and appropriately licensed reference material.

## 6. Branch and pull-request policy

- `main` must remain demonstrable.
- Do not commit directly to `main`.
- Every repository change begins with a Jira delivery item and a linked GitHub
  Issue. The Jira key appears in the Issue and pull request.
- Branch names include the issue number:
  - `feat/23-case-intake`
  - `fix/41-approval-check`
  - `docs/12-state-machine`
- Keep pull requests small enough to review in about 20 minutes.
- Every pull request links its issue using `Closes #<number>` when appropriate.
- At least one teammate must approve the pull request.
- The author resolves review comments; the reviewer does not silently rewrite
  the author's branch.
- CI, tests, linting, and documentation checks must pass before merge.
- Use squash merge to keep one meaningful commit per issue.

## 7. Jira Agile board and GitHub delivery links

**Jira is required for Agile planning and timeline evidence.** This is a project
governance decision based on the course tutorial identifying a Jira software
timeline as evidence; it does not claim that the formal marking table mandates a
particular vendor.

Use the existing Jira project. These are logical stages, not verified live
column names; C maps existing statuses without recreating the project or
rewriting history:

```text
Backlog -> Ready -> In Progress -> In Review -> Done
```

Add fields:

- Type: feature, model, research, test, documentation, defect.
- Priority: P0, P1, P2.
- Stage: discovery, Stage 1, Stage 2.
- Owner.
- Estimate: 1, 2, 3, 5.
- Requirement ID.
- GitHub Issue / Pull Request link.

Tool responsibilities are deliberately separated:

- Jira records epics/stories, sprint or Kanban selection, assignee, estimate,
  status history, blockers, and retrospective evidence.
- GitHub Issues record technical scope, detailed acceptance criteria,
  requirement/model links, and expected tests.
- GitHub branches, pull requests, reviews, commits, and CI record implementation
  and engineering review.
- Every delivery item uses one Jira key. Its GitHub Issue and PR repeat that key
  and link back to the Jira item.
- Do not copy full descriptions between tools. Update the Jira status and GitHub
  link during the normal planning/review cadence.

Working limits:

- Each member owns at most one primary `In Progress` issue.
- The whole team has at most three `In Progress` issues.
- A blocked item stays visible and records the blocking reason.

## 8. Labels

Recommended labels:

- `area:requirements`
- `area:architecture`
- `area:agent`
- `area:evaluation`
- `area:api`
- `area:web`
- `area:integration`
- `area:documentation`
- `type:research`
- `type:feature`
- `type:defect`
- `risk:high`
- `needs:tutor-feedback`
- `blocked`

## 9. Jira readiness and GitHub Issue quality

A Jira item is `Ready` only when it has an outcome, owner, estimate, priority,
stage, and—for repository work—a linked GitHub Issue.

The linked GitHub Issue is ready for implementation only when it has:

- a problem or user outcome;
- scope and explicit non-scope;
- acceptance criteria;
- related requirement IDs;
- dependencies and risks;
- an owner and estimate;
- its Jira key and backlink;
- expected test or evidence.

Avoid issues such as "work on AI" or "do front end." Prefer a vertical outcome
such as "As a founder, I can see a cited decision proposal for a matched order."

## 10. Definition of Done

A change is Done only when:

- acceptance criteria pass;
- automated tests cover the normal path and principal failure path;
- structured logs and errors are meaningful;
- relevant models and requirements remain consistent;
- no secret, personal data, or copyrighted course file is committed;
- documentation explains any new interface or architectural decision;
- another member has reviewed it;
- it works from a clean documented setup;
- evidence is attached to the issue or pull request;
- the pull request is merged, or the approved non-code artefact is complete; and
- the Jira item links the evidence before it moves to `Done`.

## 11. Meeting cadence

### Weekly planning, 30 minutes

- Review outcome metrics and risks.
- Move only Ready Jira items into the sprint.
- Confirm each member's single primary issue.
- Update planning status only in Jira; GitHub Issues remain technical open/closed
  records rather than a second sprint board.

### Mid-week sync, 15 minutes

- What changed?
- What is blocked?
- Does a requirement, interface, or scope decision need team agreement?

### Weekly review and retrospective, 30 minutes

- Demonstrate working evidence.
- Compare actual progress with acceptance criteria.
- Record one process improvement for the next week.

Decisions affecting scope, architecture, evaluation, or human safety are written
in the linked Jira/GitHub record rather than being left only in chat.

## 12. Conflict resolution

1. Restate the disagreement as a decision and acceptance criterion.
2. Compare options using user value, course evidence, risk, and delivery cost.
3. Run a time-boxed spike if evidence is missing.
4. The accountable owner makes the decision after consulting the team.
5. Record significant decisions as an ADR.
6. Escalate contribution or conduct problems to the tutor when the team process
   cannot resolve them.

## 13. Contribution evidence

Maintain a contribution log using:

- Jira ownership, estimates, status history, and sprint/timeline evidence;
- linked GitHub Issues;
- pull requests and reviews;
- authored models and ADRs;
- desk-research review notes and evaluation work;
- presentation sections and rehearsal attendance.

Commit count and lines of code are not adequate measures of contribution.

## 14. Example allocation for the first two weeks

This older illustrative sequence is superseded by the first-round selection
and dependencies in `docs/08`; do not create duplicate tasks from it.

### Member A

- lead the tutor checkpoint and confirm the desk-research-informed scope;
- write the requirements baseline and UML drafts;
- define domain schemas and API contracts;
- build the case, mock-order and proposal thin slice, consuming C's retrieval contract;
- establish Jira/GitHub linking, CI, tests, and integration conventions.

### Member B

- review the customer and Founder journeys and `UC-01` chain;
- prepare intake and Founder-dashboard wireframes;
- implement the submission-screen shell using the lead's API contract;
- add component tests and one repeatable customer-flow demo fixture.

### Member C

- review the runtime guidance corpus and `UC-02` risk chain;
- prepare the Gold-case labelling guide and first 10 pilot cases;
- define the independent risk-review output contract;
- prepare the initial parameterised safety/workflow checklist.

## 15. Provisional milestone plan

Use the dependency-based Gate 0–3 checks in `docs/00` and `docs/08`. The older
illustrative calendar is not an authoritative assessment schedule. C records
dates in Jira only after checking the current Canvas/tutor notice; do not infer
interview or submission dates from earlier planning text.

## 16. Existing branch hand-off for the 2026-09-07 alignment

The lead-directed publication of PRs #2/#4/#6 to main on 2026-09-06 did not
complete current B/C/tutor adoption or merge their follow-up work. The aligned
old documents/shared diagrams and F.01 rc.2 were published on 2026-09-07 in
[PR #9](https://github.com/shuxiachai/returnops-au/pull/9), with review requests
to B and C. This is publication to the lead's review branch, not a merge into
main or an update to B/C's branches or Jira history.

- **B / [PR #8](https://github.com/shuxiachai/returnops-au/pull/8):** the charter,
  architecture, class and sequence revisions reuse the three-role/service
  separation and model ideas from B's existing work, with source attribution.
  Compare B's branch against the aligned files before integration; preserve
  authored commits and review the remaining scope/guard differences. Do not
  discard the PR simply because related files were aligned here.
- **C / [PR #7](https://github.com/shuxiachai/returnops-au/pull/7):** its
  `docs/jira-delivery-guide/README.md` and `team-assignments.md` are still branch
  artefacts, not current main files. Keep the 2026-09-02 Jira snapshot labelled
  as historical, and make the following changes on C's branch before review:
  1. Replace the instruction to merge `#2 → #4 → #6` with the publication fact
     above; distinguish it from remaining adoption/model reviews.
  2. Do not treat C's older candidate review as approval of later allocation or
     this alignment. Preserve the original review and obtain current confirmation.
  3. Replace `Portfolio / unscheduled` for A3/OF-004, B3/OF-006 and C3/OF-001
     with selected course deliverables and the prerequisites in `docs/07/08`.
     Verify actual dates in Jira; do not fabricate replacement dates.
  4. Replace snapshot-specific WIP/blocked/Ready instructions with live Jira
     checks. Map existing keys to stable work-package IDs; verify the delivery
     item versus parent key for Issue #5 and PRs #7/#8 without guessing new keys.
  5. Align default reviewers (A reviewed by C, B/C by A, plus relevant consumers),
     C-owned label guide/runner and each member's own feature tests; retain the
     blind human-timing and independent Gold-review rules in `docs/07`.

No update listed here is evidence that a Jira status, date or permission was
queried or changed. C owns that live reconciliation. Issue #5's historical
KAN-6 backlink provides baseline context only; the actual F.01 delivery key
still needs C's verification, as noted in PR #9.
