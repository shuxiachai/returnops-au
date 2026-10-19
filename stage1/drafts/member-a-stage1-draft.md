# Member A — Stage 1 report and explanation draft

> **rc.5 publication reference (2026-09-07):** this revision is delivered through [PR #11](https://github.com/shuxiachai/returnops-au/pull/11), identified by the actual commit containing this notice. The PR records the exact source SHA, CI runs and review state; C must reproduce that SHA, not old `57d86fe` or a floating branch. Local-only/unpublished wording, test runs and raw-file hashes below are pre-publication history. Current Git content is recorded in `docs/reviews/rc5-publication-artifacts-20260907.json`. Publication does not establish acceptance, B/C review, C reproduction or a Jira update.

> 2026-09-07；**AI 辅助准备的本地章节草稿，不是已确认的个人独立成果或全组报告成品**。A 须亲自核对、修订、理解并确认实际贡献；C 按原分工评审 M-A，R.04 仍为 C Owner / A Reviewer。没有代写 B/C 的个人贡献，没有录制视频或提交 Canvas。
>
> Published evidence remains F.01 rc.4 / MA-0.2 / CS-0.1 at PR #11 head `57d86fe5bf80e2ed8cb445a6bec30c2ef7d8a577`. The current local review candidates are rc.5 / MA-0.3 / CS-0.2 / [AD-0.2](../../docs/14-member-a-design-decisions.md) / [PD-0.2](../../docs/15-package-deployment-models.md); they are unpublished and not covered by the earlier CI. The deletion/replay and label-artifact corrections do not change feature ownership, the 89 WBS dependencies or human acceptance requirements.

## 1. Intended use and course evidence

This is material for A's personal requirements-to-model explanation and for A's part of the group report. It does not replace the group requirements classification, source summary, shared-model contribution index, or the independently prepared work of B and C. The final report must separate design intentions from implementation and measured results.

The local Stage 1 rubric, pages 1–2, requires each person's individual Ad-hoc requirement, Use Case, Activity, Interaction and State models to derive from the same problem. It also requires each member to contribute to group modelling and to identify their actual contribution. Its group Use Case requirement is 5–10 specifications; ReturnOps AU currently has six specifications, whose final consistency and human acceptance remain to be checked. The Project Description, pages 1–2, asks for requirements, design models, assumptions, adopted and discarded design choices, change/acceptance rationale and contributions. Package/Deployment are Optional in the rubric; they remain planned project deliverables and help explain the architecture.

**Canvas checked on 2026-09-07:** the [Stage One report entry](https://canvas.sydney.edu.au/courses/74323/assignments/695832) shows **25 Possible Points**, and the [video entry](https://canvas.sydney.edu.au/courses/74323/assignments/695833) shows **5 Possible Points**. Both show **Sun Oct 4, 2026 23:59**, and are locked until **Sep 20 at 0:00**. The pages do not explicitly show a timezone; the displayed date must not be silently labelled AEST/AEDT/UTC. The locked body, upload format and group-submission settings have not been verified. The list shows no submission; “Attempt 1” is not a receipt.

The Canvas 25+5 display differs from the local brief's 15-point report plus 15-point presentation/interview breakdown. This needs tutor clarification; it does not remove the rubric's individual interview or justify changing project allocation. The local rubric's video limit is eight minutes, with individual interviews in Week 11/12 practicals. Whether slides are an additional upload, the exact submission formats, current interview arrangements and timezone remain to be checked against the unlocked details/tutor. See [the submission checklist](../../docs/11-stage1-readiness.md).

| A's evidence chain | Current source | What A must explain or confirm |
|---|---|---|
| AH-10 and associated AH-15/19 | [Lab 3 requirements and UC specifications](../../docs/05-lab-3-requirement-modelling.md) | Why exact approval, uncertain effects and separate notification are required |
| Main UC-04, with UC-03 as approval/non-execution boundary | [MA-0.3 traceability and guards](../../docs/12-member-a-model-chain.md) | Actors, preconditions, normal path, extensions and success conditions |
| Activity | [Governed execution SVG](../../docs/diagrams/member-a/governed-execution-activity.svg) / [source](../../docs/diagrams/member-a/governed-execution-activity.puml) | Decision admission → guarded command execution → recovery → outcome-specific notification |
| Interaction: normal and recovery panels | [Exact-scope SVG](../../docs/diagrams/member-a/exact-scope-sequence.svg) / [source](../../docs/diagrams/member-a/exact-scope-sequence.puml); [recovery SVG](../../docs/diagrams/member-a/recovery-notification-sequence.svg) / [source](../../docs/diagrams/member-a/recovery-notification-sequence.puml) | Which participant validates, persists, invokes and observes; why these responsibilities differ |
| State | [OperationAttempt SVG](../../docs/diagrams/member-a/operation-attempt-state.svg) / [source](../../docs/diagrams/member-a/operation-attempt-state.puml) | Seven states, guarded transitions and why unresolved effects are not ordinary failure |
| Shared contribution for review | [System design](../../docs/02-system-design.md), [shared Class](../../docs/diagrams/01-domain-class-diagram.md), [CS-0.2](../../docs/13-shared-composite-structure.md), [PD-0.2](../../docs/15-package-deployment-models.md) | The specific revisions A actually made or reviewed, with commits; B/C confirm their own work separately |

## 2. Problem, scope and A's modelling rationale

ReturnOps AU is a human-governed returns workflow for one Australian online store. Three business Agent roles prepare and review a cited decision packet: the Customer Case Coordinator gathers and clarifies inputs; the Returns Assessment Agent develops a proposal using read-only order data and versioned grounding; the Compliance/Risk Reviewer independently checks its support and authority boundaries. These are planned capabilities. They do not constitute three separate microservices, and their names do not prove that LLM integration is already running.

The Founder is the only authority for high-impact decisions. A deterministic Operations Service may perform only allowlisted, exactly approved simulated commands. The core prototype does not move real money, change inventory, create a real shipment or claim legal correctness. A owns the authoritative lifecycle and governed orchestration/execution; B owns the customer/founder interfaces and analytics optional; C owns grounding, independent Risk and evaluation, with image analysis as C's optional. These responsibilities remain as fixed in [docs07](../../docs/07-frozen-work-allocation.md).

A's personal main chain begins with AH-10:

> Execute only the exact approved simulated action and never perform it twice by accident.

UC-04 is the main execution use case. UC-03 supplies the preceding decision authority and the alternative reject/revise/manual-handling paths. This separates a model-generated suggestion, an accepted human decision, a durable command intent, an external effect, an observed result and a delivered customer notification. Treating them as a single “approve and finish” step would hide the failure cases that AH-10 is intended to prevent.

The Activity model shows control flow across decision admission, command work, recovery and notification. The Interaction model assigns authoritative writes to Domain Service and shows provider calls only after durable intent and final guards. The State model describes **OperationAttempt**, rather than substituting the shared ReturnCase state machine for A's personal object lifecycle. Its seven states are PENDING, EXECUTING, SUCCEEDED, FAILED, UNKNOWN, RECONCILING and BLOCKED. SUCCEEDED records a confirmed effect; FAILED requires authoritative evidence of no effect; UNKNOWN preserves uncertainty. RECONCILING is an active inquiry into the original attempt. BLOCKED does not authorise a new effect and cannot be used to overwrite another worker's valid claim.

## 3. Three model walkthroughs for A to rehearse

These are static explanation scenarios, not executed application tests, formal Gold cases or C's acceptance record. The full model has twenty-one recorded static scenarios in [docs12 §8](../../docs/12-member-a-model-chain.md).

### Scenario A-1 — A valid approval, repeated request and successful return

**Trigger:** an authenticated, authorised Founder approves the current reviewed proposal for one exact order/parcel scope. The independent Risk result permits execution and the server's current preview, version and command parameters match.

1. UC-03 validates identity, case access and request shape before checking the scoped HTTP idempotency key. A previously accepted request with the same canonical body reuses acceptance and returns the original receipt only while its content remains available. After allowed removal, replay returns 409 INVALID_STATE with retryable=false, retains deduplication and never executes again; the UI reads the current case/history without automatically changing the key. The same key with a different body is a conflict. A new intent additionally validates the current target and decision guards.
2. Domain atomically records the decision, ApprovalRecord, required work, audit and accepted-request receipt. An uncommitted decision cannot be reported as accepted or dispatch provider work. HTTP 202 means accepted work, not completed execution.
3. UC-04 claims each unfinished command, persists its intent and rechecks the exact approval, original provider configuration, authority and other dispatch guards. A losing worker yields; it does not mark the winner's attempt BLOCKED.
4. CREATE_RETURN succeeds and its typed result is saved. GENERATE_LABEL uses the saved return identity and approved parcel data. Each command follows PENDING → EXECUTING → SUCCEEDED. Replayed work reuses saved results instead of creating another effect.
5. Only when the current accepted outcome permits execution completion, both valid results and audit are stored, and no contradictory unresolved effect exists, may the RETURN_CREATED notification be saved or reused. After that notification is delivered and stored, the case may become COMPLETED.

**A should point to:** G-REQUEST, G-DISPATCH and G-COMPLETE; MA-T01, MA-T06 and MA-T07; UC-03 main flow and UC-04 1–10/5a; FR-009/010/011/012, NFR-002/004. Explain why the HTTP request key and provider effect key solve different replay problems, and why a green Schema check cannot establish the concurrency guards.

**Forbidden:** agents creating trusted approval, a second approval requirement invented for internal work, dispatch before commit, re-running a successful return, or declaring COMPLETED merely because the approval endpoint returned 202.

### Scenario A-2 — Return succeeds; label outcome is unknown or cannot be saved

**Trigger:** CREATE_RETURN has a durable successful result. The label call times out, or the provider responds but the subsequent database write fails.

1. The successful return remains successful. Recovery concerns the original label command; it cannot repeat the return or switch between core mock and A3 to create a second effect.
2. Recovery first checks durable facts. If the provider label success receipt is persisted but its local artifact is missing, the original attempt stays EXECUTING with artifact-only recovery work; it has no public result yet. It may only retrieve, validate and store the original label. If the receipt write itself failed, the last durable state may still be EXECUTING without that fact; the model must not pretend that a receipt, UNKNOWN or a result was saved.
3. Recovery of an abandoned EXECUTING claim establishes that no valid worker owns it. A known-effect receipt takes the artifact-only path; only without such a receipt may recovery save UNKNOWN and enter the authorised original-identity query path. Independent recovery authority permits reading/retrieving historical facts after creation approval expires, but never creates a new effect.
4. Provider success first becomes a trusted observation, then a complete result saved to the original attempt. GENERATE_LABEL cannot become SUCCEEDED until the bound label_evidence_id and required audit are durable. Conclusive no-effect evidence can yield FAILED only where no known-effect receipt contradicts it; safe new attempts still require current approval and dispatch guards. A temporary NOT_FOUND never erases a recorded label effect or grants permission to recreate it.
5. Once valid command results are stored, notification failure only retries the existing notification. It cannot repeat either successful command. If the Founder has already accepted a manual/rejection outcome, late historical success updates operation facts and audit but must preserve that outcome and its notification.

**A should point to:** recovery Sequence, OperationAttempt State, MA-T08–15, MA-T16–18 and MA-T20/21; UC-04 6a–6e/7a/9a; FR-009/010/011 and NFR-004. Explain the difference between observing an effect and committing that observation, between storing a provider receipt and completing its local artifact, and between confirming absence and failing to find a result.

**Decision status:** [AD-0.2](../../docs/14-member-a-design-decisions.md) proposes concrete attempt-ID/count mapping, claims and no automatic cross-approval dispatch. The local rc.5 semantic correction does not adopt this counter proposal and is not accepted. A must not present its 1-based attempt sequence as a frozen wire guarantee; the existing rc.5 shape still accepts zero and requires a versioned change if the candidate is adopted. Provider-boundary concurrency remains an implementation and verification obligation.

**Forbidden:** treating every timeout as FAILED, issuing a fresh effect key to bypass uncertainty, assuming a failed database write proves no provider effect, or overriding an accepted manual outcome with a late “success” notification.

### Scenario A-3 — An escalated case has no proposal

**Trigger:** before a proposal exists, the case is escalated with exactly one current persisted technical ProcessingFailure or a business OrderLookupBlock such as CONFLICT/AUTHORITY_DENIED. The Founder chooses manual handling.

1. UC-03 validates the trusted Founder and the exact current case/input/target. The no-proposal target is a legitimate decision target; it is not evidence that a proposal or Risk PASS exists.
2. Only MANUAL_HANDLING is accepted for this branch. Domain stores the manual outcome, audit, required outcome notification and accepted-request receipt atomically. A business conflict remains a business block; it cannot be converted into a fictitious technical failure to fit another DTO.
3. No ApprovalRecord or return/label OperationAttempt is created. The notification communicates the accepted manual outcome and next step. After delivery is durably recorded the case reaches MANUAL_HANDLED, not COMPLETED.
4. An invalid/stale target is rejected. If a case with earlier effects is later handled manually, independently authorised history queries may preserve new observations without reopening the case, changing the outcome or creating new work; that is distinct from this pre-proposal example.

**A should point to:** UC-03 1a/1b/3c/3d, Activity A04/A06/A07, MA-T05/06/13/15; FR-003/009/011/012. Explain why the third target preserves a business block without fabricating a proposal or technical failure, and why manual notification still needs retry and audit handling.

**Forbidden:** APPROVE/REQUEST_REVISION without a current proposal, mixed targets, fake PASS, uncommitted acceptance, creating effects from the manual decision, or closing before the required outcome delivery is recorded.

## 4. Design choices and alternatives

| Choice in the candidate design | Reason and requirement link | Cost, rejected shortcut or remaining proof |
|---|---|---|
| Modular monolith with typed ports | Keeps one authoritative workflow while allowing model/provider substitution; FR-009/011, NFR-007 | Avoids three-service deployment overhead; still needs explicit module boundaries and cannot use shared-process access to bypass ports |
| Domain as the sole writer of business state | Makes decision, work, audit and outcome rules reviewable; FR-009/011, NFR-004 | Requires transaction/claim design; direct Agent or UI repository writes are not an acceptable convenience |
| Independent Risk invocation | Separates proposal generation from source, conflict and authority review; FR-008, NFR-009 | More latency/cost; independence of invocation does not itself establish review accuracy or immunity to injection |
| Durable intent, stable effect identity, query before retry | Preserves AH-10 when a worker or network fails; FR-010, NFR-004 | More states than a success/failure flag; crash, claim and provider races still require runtime tests |
| Outcome-specific notification separate from effects | Retry delivery without duplicating a return; preserve accepted manual/rejection decisions; FR-009/010/012 | Requires notification identity and version checks; “both old operations succeeded” is insufficient to choose today's outcome |
| Versioned sources/material and authorised history | Allows reconstruction of what supported a particular decision; FR-006/011/012, NFR-001 | Storage/retention and customer-vs-founder projection must be implemented; reconstructing an old proposal from current material is invalid |
| Simulated core provider, separate A3 test integration | Keeps core behaviour bounded while retaining the selected optional's separate evidence requirement | The team has explicitly stated it has no Australia Post/StarTrack contract or test account. [A3 feasibility](../../docs/17-logistics-sandbox-feasibility.md) records the access dependency; core mock cannot count again as A3 |

PD-0.2 distinguishes actual F.02 API/migration/database artefacts from planned application packages, Agent modules, adapters and storage capabilities. It is a review model, not a claim that all pictured code is deployed. CS-0.2 describes collaborating parts and ports; deployment does not automatically require one process for every part. These views complement, rather than substitute for, the Class and behavioural models.

## 5. What is evidenced and what remains planned

| Evidence available at the reference version | Valid conclusion | Conclusion it cannot support |
|---|---|---|
| rc.4 schemas, OpenAPI, examples and 53 contract checks | Artifact shape/fixture consistency has automated checks | Authentication, approval, retention, legal correctness or runtime safety |
| Rendered MA/CS diagrams and static checks | Sources/references and selected model paths can be inspected | C's human acceptance, complete UML semantics or implementation |
| [PR CI](https://github.com/shuxiachai/returnops-au/actions/runs/34117330147) and [push CI](https://github.com/shuxiachai/returnops-au/actions/runs/34117330053) | Each has successful offline checks and 30 environment tests; full run details in [docs10](../../docs/10-f02-environment-readiness.md#52-已发布版本的真实-github-ci) | Merge, accepted F.01, C's independent reproduction, or CI coverage of this later draft |
| Health endpoints, dependency locks, Alembic `0001_environment`, Compose | A reproducible infrastructure foundation exists; the migration has no business tables | Fifteen `/v1` operations, RBAC, Agent calls, case lifecycle or exact-scope execution implemented |
| Published local PG/Compose health and outage records | Those environment behaviours were observed on the recorded local setup | Production readiness, domain recovery guarantees or another member's execution |
| 30 Gold / B1 vs B4 evaluation protocol | A planned evaluation and labelling process is specified | Measured quality, measured time savings or an observed ten-minute baseline |

No formal Gold evaluation has been run by this document task. C must seal initial Gold labels, reasons and version/hash before seeing timed answers; later review/arbitration and final freeze follow the existing E work packages. The B1-vs-B4 comparison tests the planned end-to-end intervention and does not isolate every architectural choice causally. No empirical score, latency saving or role-specific contribution percentage is invented here.

PR #11 remains open with no submitted review at the latest read-only check. Jira KAN-32 still describes rc.2/PR #9 and requires a later authorised update; this mismatch is retained in the evidence record. A's model and the local design decisions need personal review, C review and corresponding B consumption checks. A3 access is currently absent, not assumed available. B/C must prepare and confirm their own models/contributions. None of these unresolved items should be hidden from the Stage 1 report, and none prevents an on-time, accurately labelled course submission under the actual course rules.

## 6. Honest authorship and AI assistance statement

**Draft disclosure for A to adapt after verifying the facts:**

> AI assistance was used to inspect repository and course materials, compare requirements/contracts/models, draft and revise model descriptions and documentation, prepare code/check candidates, and organise test and review evidence. This chapter and its explanation outline were drafted with that assistance. Automated checks establish only their stated scope. They do not establish independent personal authorship, human review, system implementation or course acceptance. The final submission will identify the decisions, revisions, checks and explanations actually performed by each student and disclose AI assistance in the course's required format.

This statement is not a claim that A independently created every candidate diagram or has already reviewed this chapter. A must replace the following blanks with real contributions and preserve prior author sources. Existing B PR #8 material and C contributions cannot be claimed as A's work merely because A integrates the report. A should be able to explain the three scenarios and design tradeoffs without another person or an agent answering on A's behalf.

| Contribution evidence to complete before using this chapter | Actual record |
|---|---|
| A's own selected/design decisions, accepted or rejected and why | Pending A; cite AD item, date and reasoning |
| A's model or text revisions after personal walkthrough | Pending A; exact file/version/commit and meaningful change |
| A's personally executed checks or reviewed evidence | Pending A; distinguish execution from reading CI logs |
| A's shared-model contribution | Pending A; identify exact scope, preserve B/C sources |
| C's M-A review findings and disposition | Pending C; no signature supplied by this draft |
| B/C's personal/group contributions | Supplied and confirmed by each member; deliberately not authored here |
| Final AI assistance wording required by course | Check current course instructions; do not claim an unverified policy approval |

## 7. Material for A's later video and interview

A will record, integrate and submit the video later. B/C provide and confirm their own models, contributions and required material. The following is a suggested A-focused explanation sequence within the group's eight-minute maximum; it is not a new ownership allocation, agreed duration per person, recorded clip or final script.

| Screen/material | A's explanation cue |
|---|---|
| Scope and three roles; one Founder decision boundary | “Agents produce and review proposals. A trusted human decision is a different object from a generated recommendation.” Identify planned capabilities explicitly. |
| AH-10 → UC-04, linked to UC-03 | State the main requirement, why it belongs to A's chain, and why the shared ReturnCase state model is insufficient for OperationAttempt. |
| Zoomed exact-scope Sequence / Activity | Walk A-1 from auth and replay through durable work to two saved command results and notification. Show why 202 does not mean completed. |
| Zoomed State / recovery Sequence | Walk A-2's uncertain label result and post-provider storage failure. Distinguish FAILED, UNKNOWN and RECONCILING, then explain notification isolation. |
| Manual-handling branch | Walk A-3 without fake proposal, risk pass or approval. Explain the third target's business meaning. |
| Architecture choice and actual evidence table | Explain one accepted/rejected alternative once A has made that decision; show F.02 health evidence with the unimplemented business boundary visible. |
| Contribution and unresolved items | State actual personal edits/review and AI assistance. Show candidate status, missing A3 access and review obligations without implying completed acceptance. |

Use cropped/zoomed views of the existing SVGs so text is readable; do not fit a very tall Sequence into one unreadable frame. Verify the final video's duration, sound, model labels, version and access using R.04.f/h. Prepare to answer: What authorises a new effect? What if the provider succeeded but storage failed? What makes no-effect evidence authoritative? Can an old success overwrite manual closure? Which candidate choices still need review? Which parts actually run today?

## 8. Conditions before this draft becomes submission material

- A personally reviews and revises the chapter/models, explains the three scenarios, and fills a truthful contribution record; C records the original M-A review outcome. B confirms relevant public consumption changes without becoming A's model author.
- A integrates B/C's independently confirmed material, the shared-model/rubric index and the 1–2-page source/assumption summary into a complete report; C performs R.04 evidence checks.
- Confirm the unlocked Canvas instructions, timezone, upload/group settings, slides/video format, scoring difference and individual interview arrangements. The visible report/video deadline is 4 October 2026, 23:59 as displayed; no submission receipt exists yet.
- A later records and submits the final video/report under the actual course rules, and C reopens the submitted artefacts to check the correct version and access. This does not wait for R.04/R.01/F.01 to be globally Done or for Stage 2 evaluation to finish.

This file remains a prepared draft until those people and course evidence close the relevant items; no checkbox or signature in this document records a completed human review.
