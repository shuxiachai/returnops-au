# Team and GitHub Workflow

## 1. Team structure and planned workload

The team has three students. The project lead intentionally owns the central
product, architecture, implementation, and integration path. The other two
members own small, bounded support packages that can be reviewed and integrated
without creating parallel architectural centres.

The planning allocation across the three team members is approximately:

- Member A, Project Lead & System Architect (Backend & Agent Core): ~48%;
- Member B, Frontend & User Experience Lead (Client & Operations Dashboard): ~25%;
- Member C, QA & AI Evaluation Lead (Benchmark & Evaluation Pipeline): ~27%;

This structure satisfies the ELEC5620 Lab 2 requirement that every member individually implements at least two core features and one optional feature.

### Member A: Project Lead, System Architect & Backend/Agent Core Lead (~48%)

Primary responsibilities:

- product scope, requirement classification, and traceability matrix;
- principal architecture and MBSE UML models (Package, Domain Class, State Machine, Sequence diagrams);
- domain model, Pydantic schemas, database schemas, and FastAPI service;
- LangGraph multi-agent orchestrator (Intake, Order, Policy, Remedy, Risk nodes);
- deterministic approval rules, audit event recording, and mock adapters;
- system integration, CI/CD foundation, Docker containerization, report integration, and presentation narrative.

**Lab 2 Deliverables**:
- *Core Feature 1*: Domain API, PostgreSQL database, and ReturnCase lifecycle state machine.
- *Core Feature 2*: Multi-agent orchestration and governed decision flow.
- *Optional Feature*: Mock Shopify GraphQL & AusPost adapters with Docker environment.

### Member B: Frontend & User Experience Lead (~25%)

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

### Member C: QA & AI Evaluation Lead (~27%)

Primary responsibilities:

- acceptance criteria definition, quality metric thresholds, and requirements traceability;
- curated store policy corpus and ACCC statutory warranty guidance;
- 100 synthetic return cases with ground-truth labels (faulty, wrong item, change of mind, missing evidence, escalations);
- automated AI evaluation pipeline comparing 4 configurations (No-RAG vs RAG vs Multi-Agent vs Governed Multi-Agent);
- safety and prompt injection test suite, failure analysis, and benchmark reports.

**Lab 2 Deliverables**:
- *Core Feature 1*: 100-case synthetic benchmark dataset & ground-truth labeling.
- *Core Feature 2*: Automated AI evaluation pipeline and comparison reporting.
- *Optional Feature*: Security, prompt injection guardrail testing, and automated CI test runner.

## 2. Shared responsibilities

All members must still:

- participate in problem interviews and requirement reviews;
- understand the principal customer workflow and human-approval boundary;
- review assigned pull requests and respond to review feedback;
- test their own deliverables and provide integration evidence;
- rehearse the presentation and interview;
- record their individual contribution evidence.

## 3. Lightweight RACI

| Deliverable | Lead | Research/Evaluation | Interface/Mock Data |
|---|---|---|---|
| Problem validation | A | C | C |
| Requirements and traceability | A/R | C | C |
| UML and architecture | A/R | C | C |
| Domain API and database | A/R | C | C |
| Agent workflow and guardrails | A/R | C | C |
| Policy corpus | A | R | C |
| Evaluation case labels | A | R | C |
| Evaluation framework and analysis | A/R | C | C |
| Customer and founder screens | A | C | R |
| Synthetic order and shipment fixtures | A | C | R |
| Provider adapters | A/R | C | C |
| CI and deployment | A/R | C | C |
| Report integration | A/R | C | C |
| Demo walkthrough | A | R | R |
| Presentation and interview | A/R | R | R |

Legend: A = accountable, R = responsible/reviewer, C = consulted.

## 4. Bounded work packages

Support work should be assigned as complete packages with inputs, outputs, and
acceptance criteria, not as open-ended responsibility for a subsystem.

### Package B1: Policy corpus

Input from lead:

- source-selection rules;
- metadata schema;
- approved request types.

Output from Member B:

- 20-30 versioned policy/guidance passages;
- source URL, title, access date, location, and request-type tags;
- a short note for ambiguous or conflicting passages.

Acceptance:

- every entry is traceable to its source;
- no copied course material or unlicensed commercial content;
- the lead can load the corpus without manual cleanup.

### Package B2: Evaluation cases

Input from lead:

- case template and labelling guide;
- examples of valid and invalid labels.

Output from Member B:

- 30-40 synthetic cases;
- reviewed labels for request type, missing evidence, citation, and escalation;
- five documented model failures.

Acceptance:

- cases follow the schema and contain no real personal data;
- a second person reviews a sample of labels;
- results can be reproduced from the repository.

### Package C1: Customer submission screen

Input from lead:

- API contract;
- wireframe and validation rules;
- design tokens or component conventions.

Output from Member C:

- order-number, problem-description, and evidence fields;
- client-side validation and clear error states;
- loading, success, and retry behaviour;
- component tests or documented manual test evidence.

Acceptance:

- the screen follows the lead's API contract without embedding business rules;
- validation and error states are demonstrable;
- the lead can run and integrate the screen from a clean checkout.

### Package C2: Founder review screen and demo fixtures

Input from lead:

- proposal and approval schemas;
- allowed approval actions;
- sample API responses.

Output from Member C:

- evidence, citations, risks, confidence, and recommendation display;
- approve, reject, and request-revision controls;
- synthetic orders and a repeatable demo script.

Acceptance:

- high-impact actions are visibly separated from ordinary navigation;
- the screen never represents an unapproved proposal as completed;
- the full demo can be reset and repeated.

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
- Every change begins with a GitHub Issue.
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

## 7. GitHub Project board

Create one GitHub Project with these statuses:

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

## 9. Issue quality

An issue is Ready only when it has:

- a problem or user outcome;
- scope and explicit non-scope;
- acceptance criteria;
- related requirement IDs;
- dependencies and risks;
- an owner and estimate;
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
- evidence is attached to the issue or pull request.

## 11. Meeting cadence

### Weekly planning, 30 minutes

- Review outcome metrics and risks.
- Move only Ready issues into the sprint.
- Confirm each member's single primary issue.

### Mid-week sync, 15 minutes

- What changed?
- What is blocked?
- Does a requirement, interface, or scope decision need team agreement?

### Weekly review and retrospective, 30 minutes

- Demonstrate working evidence.
- Compare actual progress with acceptance criteria.
- Record one process improvement for the next week.

Decisions affecting scope, architecture, evaluation, or human safety are written
down in GitHub rather than being left only in chat.

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

- assigned and completed issues;
- pull requests and reviews;
- authored models and ADRs;
- interview notes and evaluation work;
- presentation sections and rehearsal attendance.

Commit count and lines of code are not adequate measures of contribution.

## 14. Example allocation for the first two weeks

### Member A

- lead problem interviews and confirm the scope;
- write the requirements baseline and UML drafts;
- define domain schemas and API contracts;
- build the case, mock-order, policy-retrieval, and proposal thin slice;
- establish the repository, CI, tests, and integration conventions.

### Member B

- conduct one interview using the lead's question set;
- catalogue the first 10 approved policy/guidance passages;
- produce and label the first 10 synthetic cases;
- record baseline results using the lead's evaluation command.

### Member C

- conduct one interview using the lead's question set;
- prepare 10 synthetic orders using the lead's schema;
- implement the submission-screen shell using the lead's API contract;
- prepare the first repeatable demo fixture and test checklist.

## 15. Provisional milestone plan

| Period | Outcome |
|---|---|
| Weeks 2-3 | User evidence, tutor feedback, scope decision, initial backlog |
| Weeks 3-4 | Baseline requirements, feature model, use cases, evaluation dataset design |
| Weeks 4-5 | Architecture, domain model, state/activity/sequence models, technical spike |
| Weeks 6-7 | Thin vertical slice and model-to-code validation |
| Week 8 | Stage 1 report, presentation, interview, and baseline tag |
| Weeks 9-10 | Core MVP workflow and founder approval |
| Weeks 10-11 | Policy retrieval, risk review, mock operations, evaluation suite |
| Week 12 | Hardening, deployment, documentation, and demo rehearsal |
| Week 13 | Final demonstration and source submission |

Dates must be updated when Canvas confirms the assessment schedule.
