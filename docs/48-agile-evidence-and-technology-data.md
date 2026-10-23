# 48. Agile evidence and technology data for the Stage 2 demonstration

Owner: A Jingbo Chai. Prepared on 23 October 2026 (Sydney) for the Week 13 demonstration and the two rubric rows that are judged from records rather than from the running system: "Agile Development Experience" (4 marks) and "Incorporation of Advanced Technologies" (5 marks) in the Stage 2 marking criteria ([docs/28](28-stage2-submission-checklist.md), [docs/47](47-stage2-submission-runbook.md) section 1). Every number below is taken from a record that is named next to it; nothing is estimated. Where a record does not exist, this page says so.

How to use it in the demo: segment S7 of [docs/45](45-stage2-demo-script.md) ("Agile and engineering practice") points here. The presenter reads the two tables in sections 3 and 6 and shows one feedback loop from section 4 live on GitHub.

## 1. What the rubric asks for and where the evidence is

| Rubric wording (Stage 2 criteria) | Evidence in this repository and its systems |
|---|---|
| "detailed documentation of all iterations" | Section 3 (iteration table from merged pull requests), the dated README chapters, [docs/08](08-delivery-work-packages.md) work packages, [docs/11](11-stage1-readiness.md) planning record |
| "burn-down charts" | Section 3 cumulative delivery table (a burn-up built from pull-request adoption dates; see the note on why Jira resolution dates are not used) |
| "user stories" | Section 2: the six Jira epics E1 to E6, the twelve functional requirements FR-001 to FR-012 and the per-member use cases in the Stage 1 report ([docs/00](00-project-definition-v1.md), [docs/12](12-member-a-model-chain.md), [docs/19](19-member-b-model-chain.md), [docs/18](18-member-c-model-chain.md)) |
| "feedback loops" and "iterative improvements" | Section 4: six recorded review-to-change loops with their pull-request and comment links |
| "team collaboration" | Section 5: the frozen allocation ([docs/07](07-frozen-work-allocation.md)), Owner/Reviewer pairs, the delegated review and adoption flow, Jira board |
| "advanced technologies (at least 6) ... supported by data" | Section 6: ten technologies with the measurement each one is tied to |

## 2. User stories: epics, requirements and work packages

The product definition fixes twelve functional requirements (FR-001 to FR-012) and nine non-functional ones (NFR-001 to NFR-009) in [docs/00](00-project-definition-v1.md). They are grouped into six Jira epics, each with a short user story, and broken down into the work packages of [docs/08](08-delivery-work-packages.md) (89 WBS rows, checked by `tools/model-checks/check.py`).

| Epic | User story (one line) | Requirements | Work packages | Owner |
|---|---|---|---|---|
| E1 Problem discovery and requirements | As the founder of a small Australian shop, I want a clear, bounded promise for returns handling so the team builds the right thing | FR-001 scope, NFR-001 to NFR-003 | M, F.01, R.01 | A (lead), B and C review |
| E2 Domain model and mock environment | As a developer, I want one authoritative case lifecycle with typed contracts and an audit spine so every later feature is governed | FR-002, FR-003, FR-009, FR-010 | F.02, F.03, A1.01 to A1.04 | A |
| E3 Case investigation workflow | As a customer, I want to lodge a return in plain language and be asked only for what is missing | FR-001, FR-002, FR-004, FR-005 | A1.03, A1.05, B1 | A backend, B portal |
| E4 Policy and guidance grounding | As the founder, I want the system's guidance tied to our own policy text with exact citations | FR-006, FR-007 | C1 | C |
| E5 Resolution and human control | As the founder, I want to approve exactly one previewed action, with nothing executed without my decision | FR-008, FR-011, FR-012, NFR-004, NFR-005 | A2.01 to A2.07, B2, C2 | A backend, B console, C risk review |
| E6 Evaluation and evidence | As the team, I want every claim about safety and behaviour backed by a repeatable test or run | NFR-006 to NFR-009 | E.01 to E.12, F.06, R.02, B3 | A, C evaluation, B analytics page |

Jira: project KAN, 37 issues on 23 October 2026 (epics KAN-6 to KAN-11, stories and tasks KAN-12 to KAN-43). The board is a Kanban board without sprints; iterations were weekly, aligned to the course's practical sessions (Monday 13:00 to 15:00), with the practical's planning conversation recorded in the dated README chapters and the handover notes.

## 3. Iterations and cumulative delivery

Source: the 65 pull requests merged into `main` by the evening of 23 October 2026, read from GitHub (`gh pr list --state merged --base main`), grouped by ISO week of the merge date. Pull requests merged into another branch are not counted. A pull request is counted when it is adopted into `main`, because adoption is the only event that is independently timestamped and reviewed. Jira resolution dates are deliberately not used for the chart: the lead moved the completed Jira items to Done in one pass on 22 October 2026 when the board was reconciled, so those dates record the reconciliation, not the work.

| Iteration (ISO week, Sydney) | A | B | C | Merged | Cumulative | What landed |
|---|---|---|---|---|---|---|
| Week 36, 31 Aug to 6 Sep | 3 | 0 | 0 | 3 | 3 | Lab 3 requirements model, desk-research evidence, Baseline v1.0 candidate (#2, #4, #6) |
| Week 37, 7 to 13 Sep | 1 | 0 | 0 | 1 | 4 | v1 alignment and interface contract rc.2 for B and C review (#9) |
| Week 38, 14 to 20 Sep | 1 | 2 | 2 | 5 | 9 | B and C personal models aligned with contract rc.5; C review of rc.5; Stage 1 report material (#8, #11, #12 and others) |
| Week 39, 21 to 27 Sep | 8 | 0 | 0 | 8 | 17 | F.03 isolated identity and access; Stage 2 entry; customer notification fixtures (#15, #18, #19 and others) |
| Week 40, 28 Sep to 4 Oct | 5 | 0 | 0 | 5 | 22 | Authoritative lifecycle: Founder case views, persisted guards, denial audit (#30, #32, #34 and others) |
| Week 41, 5 to 11 Oct | 10 | 0 | 2 | 12 | 34 | Stage 1 consolidation; A1.03 acceptance; A1.05 fixed proposal; C1 offline grounding candidate (#40, #41, #43 and others) |
| Week 42, 12 to 18 Oct | 6 | 0 | 1 | 7 | 41 | Jira delivery guide; A2.01 PASS proposal handling; approval admission (#7, #63, #65 and others) |
| Week 43, 19 to 25 Oct (to 23 Oct) | 14 | 2 | 8 | 24 | 65 | A2.06 notification, A2.07 decision boundary, R.02 end-to-end evidence, F.06 analytics, Coordinator showcase and its live result, R.05 documents, B frontend scaffold and live connection, C handoff, receipts and source review, review fixes (#60, #78, #87, #89, #90, #94, #96 to #100, #107, #108, #17, #61 and others) |

Burn-up of adopted pull requests (each block is one pull request):

```text
Week 36  ###                                                             3
Week 37  #                                                               4
Week 38  #####                                                           9
Week 39  ########                                                       17
Week 40  #####                                                          22
Week 41  ############                                                   34
Week 42  #######                                                        41
Week 43  ########################                                       65
```

Reading the shape honestly: delivery accelerated into the last two iterations, and B's frontend adoption started late (first merge 22 October; the live connection, the facts card and the pending-submission fix were adopted on 23 October through #100 and the integration pull request #107). The retrospective in section 7 records why and what the team changed.

Per-member totals of the 65 adopted pull requests: A 48, C 13, B 4. #107 is counted under A because the lead opened it to bring B's reviewed #101 and #102 onto `main`. These are counts of adoptions, not of effort or value; the contribution statement handed to the course is prepared separately and agreed by all three members ([docs/47](47-stage2-submission-runbook.md) section 6).

## 4. Feedback loops: review comment to change

Each loop names the reviewer, the comment or review, and the change it produced. All are visible on GitHub.

1. **Contract review before implementation (Week 37 to 38).** A published interface contract rc.2 (#9) for B and C to review; C's review of rc.5 (#11) and B's model alignment (#8) fed the frozen v1 contract in `contracts/v1`. Change: field names, status set and examples were fixed before any endpoint was coded, and the contract has been frozen since ([docs/09](09-interface-contract-v1.md)).
2. **Independent review of the Coordinator showcase design (22 October).** A's design v1 for the advisory model extraction was sent to a read-only independent review, which rejected it on eleven points (a new migration would break the schema gate; a privacy leak through retention; the wrong input key; lock-holding during a model call; and others). Change: design v2 moved the store in process, keyed by an input digest, split the worker into three phases with no database connection held during the model call, and documented the Gate boundary ([docs/44](44-coordinator-showcase.md), "Fail-closed paths" and "Gate position"). The review record is kept with the lead's evidence and summarised in docs/44.
3. **Review of B's frontend scaffold (#60, 20 to 22 October).** The lead's review asked for the live-mode gates and the mock fallback to be made explicit and for the docs/35 test counts to match the suite. Change: #60 was merged with the documented gates, and B's follow-up pull requests #100 (freeze the draft while a request is pending), #101 (advisory facts card) and #102 (live analytics and decisions) each answer one issue the review opened (#88, #95, #91).
4. **Review of C's receipts (#17 and #61, 18 to 23 October).** The lead's comments asked for placement of C's README sections among the dated notices, correction of a cancelled CI run cited as successful, and removal of a merge SHA that was not on `main`. Change: C re-merged `main` three times as it moved and corrected the wording; #17 was adopted on 22 October and #61 on 23 October after a targeted re-review of each exact head.
5. **CI guard caught a workflow change (22 October).** Adding the `end-to-end-no-llm` job to the workflow tripped the offline guard test in `tools/checks/test_run.py`, whose job-name pattern and job list are asserted. Change: the job was renamed to fit the pattern, the guard test was extended to the new job and, in #93, to B's `web-frontend` job, so the gate still requires exactly the intended set of jobs.
6. **Flaky concurrency test triaged rather than silenced (23 October).** The same-key competition test `test_R04_independent_process_competition[same]` failed in CI on two branches that change no backend code (lock timeout on the global fence under runner load). Change: issue #103 and Jira KAN-43 record the evidence; reading the code showed the server already answers that case with a retryable 503 and no denial audit, so the probe now records every attempt and re-sends the same key once, as the client contract says, and the API's statement timeout was raised to outlast the lock timeout (#108). The receipt assertion itself was not relaxed.
7. **A full technical review before the final week (23 October).** Three independent read-only reviews of `main` produced the fixes in #108 (line endings on Windows clones, the demo tool's error reasons, the interrupted driver receipt, strict query integers, new tests) and the backlog in issue #106, recorded in [docs/46](46-gate2-roadmap.md) section 8 and [docs/47](47-stage2-submission-runbook.md) section 7 rather than hidden.

An eighth loop is external: the tutor's Stage 1 interview feedback and the 13 October Canvas clarification ("deploy on site from the Canvas download") produced the "Deploy from zero" README chapter and the clean-machine rehearsal checklist in [docs/47](47-stage2-submission-runbook.md) section 5.

## 5. Team collaboration and the delivery rules

- **Frozen allocation.** [docs/07](07-frozen-work-allocation.md) fixes nine functions to three owners (A: lifecycle, approval and execution; B: customer portal, Founder console, analytics page; C: grounding, risk review, evaluation) and [docs/08](08-delivery-work-packages.md) gives each work package an Owner, a Reviewer and start/finish dependencies.
- **Review and adoption flow.** Every change reaches `main` by pull request with the CI run on its exact head. Teammates' pull requests are reviewed by the lead (or the lead's delegate, marked as such in the review text) and adopted by squash merge with a lead-written message; A's own pull requests are merged on green CI after the lead's own verification, a decision recorded on 22 October 2026. Approvals are tied to an exact head and do not transfer to later bytes; C's pull requests record this rule in their own text.
- **Jira.** 37 issues; the lead holds the board and reconciled it with the repository on 22 October 2026 (items Done with evidence comments, B's items moved back to In Progress where the scaffold was merged but the live connection was not). Each pull request names its KAN key.
- **Handover notes.** A dated handover summary is kept by the lead outside the repository and the dated README chapters record each adoption; the Stage 1 handover is in [docs/11](11-stage1-readiness.md).
- **Attribution rule.** Commit messages, squash messages and pull-request text carry no AI tool signatures; AI assistance is stated in one fixed sentence and the human author is named.

## 6. Technologies and the data behind each

Each row names the technology, where it is used, and the measurement or record that shows its effect. "Observed" means a value read from a run; "counted" means a value read from the repository on 23 October 2026.

| # | Technology | Where | Data |
|---|---|---|---|
| 1 | FastAPI with Pydantic v2 on CPython 3.12 | `apps/api` | Counted: 25 operations in `contracts/v1/openapi.json`, 85 schema definitions with `additionalProperties: false`; every route fails closed with a typed error envelope. Observed: `/health/ready` answers in well under a second on the demo machine (22 October live run). |
| 2 | PostgreSQL 17 with transactional advisory locks | authoritative lifecycle, global fence | Counted: 14 Alembic migrations (`0001` to `0014`), 8 CI matrix parts. Observed: the fence's 5 s `lock_timeout` is the production value; its behaviour under load is the subject of issue #103 (two timeouts in CI on 22 October, 10/10 local passes). |
| 3 | SQLAlchemy 2.0 and Alembic | schema, migrations, schema gate | Counted: `lifecycle_schema.version()` accepts exactly the listed table set, so a drifted database is refused at readiness (HTTP 503) instead of silently used. |
| 4 | Docker Compose with health-gated start order | `compose.yaml` | Observed (22 October, demo machine): `db` healthy, `migrate` exited 0, `api` healthy within the 180 s wait; a stale volume with a different password was detected by the failing `migrate` step, not by a silent fallback. |
| 5 | GitHub Actions with a planned matrix | `.github/workflows/ci.yml`, `tools/checks/run.py` | Counted: 7 jobs plus an 8-part PostgreSQL matrix; the gate requires exactly offline, plan and all eight parts. Observed: full runs on `main` of 52.5 to 82.0 minutes (last eight completed runs), with the longest single part (`label_artifact`) at 41 to 54 minutes; the matrix runs the parts in parallel, so the wall time is the longest part rather than the sum. |
| 6 | pytest suite with process-level concurrency probes | `tests/` | Counted: 1,355 test functions in 135 files; the R04 probes start two independent operating-system processes against one database to prove same-key idempotency and different-key denial. |
| 7 | React 18, TypeScript, Vite and Vitest | `apps/web` | Observed (CI, 22 October): 134 tests in 14 files on the head of #102, type-check and production build passed; the `web-frontend` job runs outside the PostgreSQL gate so frontend changes are checked in minutes. |
| 8 | Chat-completions model gateway with fail-closed acceptance | `packages/returnops_domain/model_transport.py`, `coordinator_showcase.py` | Observed (22 October, course proxy, model `campus-qwen`): two live calls, 1 attempt each, 441 and 444 input tokens, 599 output tokens each, 6,437 and 6,625 ms; a statement carrying an injected instruction produced `OUT_OF_SCOPE` and no line items ([docs/44](44-coordinator-showcase.md), "First live result"). |
| 9 | Idempotency keys end to end | customer and Founder POST routes, web client | Counted: every write route requires `Idempotency-Key`; the R.02 driver exercises same-key retry and recovery paths (`UNKNOWN` gets exactly one same-key recover call). Observed: the R.02 CI job passed on `main` for every adoption since 22 October. |
| 10 | BM25 retrieval with exact citation verification | `experiments/c1_grounding_candidate` | Counted: an offline candidate with its own tests adopted in Week 41 and reviewed in #61; it does not yet run inside the API (Gate 2, [docs/46](46-gate2-roadmap.md)). No live retrieval latency is recorded. |

What is not claimed: no load test, no production traffic, and no comparison against an alternative stack were run. The "performance improvement" the rubric mentions is shown where it was measured: the parallel CI matrix against serial execution, the fail-closed schema and health gates against silent drift, and the model call's bounded latency and token cost.

## 7. Retrospective (truthful)

What worked:

- Freezing the contract and the allocation early (Weeks 37 to 38) let A build the backend to the contract while B and C modelled against the same text; no contract change was needed after the freeze.
- Gate 1 before any model: the whole no-model path was proven by the R.02 driver and its CI job before the advisory model extraction was added, and the model was then added in a place where it cannot execute anything.
- Reviews that produced changes rather than approvals: the showcase design was rejected once and rebuilt; C's receipts were corrected three times; the flaky test was triaged rather than retried blindly.

What did not work and what the team changed:

- The frontend's live connection came late. The scaffold merged on 22 October and the live analytics, decisions and facts card arrived as three stacked pull requests on 23 October. Adopting them in order exposed a process error: the two upper pull requests targeted the branch below them, not `main`, so their squash merges landed on B's branches and had to be brought onto `main` by an integration pull request (#107). The team's rule since then: check the base branch before every merge, and rehearse the whole path on a clean machine on 29 October.
- Jira was reconciled in one pass on 22 October rather than continuously, which is why the burn-up uses adoption dates. The team changed to naming the KAN key in every pull request and moving the item when the pull request is adopted.
- The full LLM three-role orchestration (Gate 2) was deferred past 1 November by the lead's decision of 22 October; the roadmap is in [docs/46](46-gate2-roadmap.md), and the demonstration says so in S8 rather than implying otherwise.

Each member's own contribution is stated in the course's contribution form, not here.

AI-assisted implementation and metadata preparation; author shuxiachai.
