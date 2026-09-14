# Member B — Stage 1 Report and Explanation Draft

> **MB-0.2 compatibility candidate, 2026-09-14.** B (Chengsi Li, `ChengsiLi`) owns M-B.01–.06 / [KAN-17](https://lucastaooo.atlassian.net/browse/KAN-17); A is the designated reviewer. Original B delivery is [PR #14](https://github.com/shuxiachai/returnops-au/pull/14), exact source [92cd717a87a1aff745044342498d4caae196dc15](https://github.com/shuxiachai/returnops-au/commit/92cd717a87a1aff745044342498d4caae196dc15), following B's 31fa250 model/report commit. This is an A-led, AI-assisted compatibility revision of B's files. It is a draft for B to inspect, revise and explain, not B's independent completed work or team acceptance.
>
> [Model-chain index](../19-member-b-model-chain.md) and [correction disposition](../reviews/b-model-compatibility-disposition-20260914.md) contain the technical mapping and evidence boundaries. This file is separate from the integrated Stage 1 team report; editing it does not update the shared report or Google Doc. M-S.03 remains a separate shared integration task.

## 1. Role, ownership and contribution evidence

B owns the customer intake/clarification portal (B1), Founder review UI (B2), and operational statistics page (B3 / OF-006). The 27% allocation is planned effort, not measured contribution, an hours guarantee or a grading percentage. A retains Domain/Coordinator/Assessment and controlled operations; C retains retrieval, Risk and image analysis. Each owner still needs their own implementation, tests and explanation.

The personal model chain is AH-01 → UC-01 / UC-01E → Activity (M-B.02 / C8), Sequence (M-B.03 / C9) and case-owned IntakeSession state machine (M-B.04 / C10). These figures support the individually assessed modelling criteria; their presence does not establish awarded marks or completed M-B.05/.06 acceptance.

Potential shared contributions include UC-01/UC-01E consistency, intake class relationships and frontend consumption boundaries. Concrete B revisions and reviews must identify which parts were contributed, which came from existing shared models and which were A/AI-assisted. Merely naming M-S.03 does not deliver its classification/Feature/Use-case/full-model index; C's classification input and the original M-A.01/M-C.01/M-S.02 dependencies remain required.

## 2. Personal requirement and use cases

AH-01 states: *“Let me describe the return or product issue without navigating internal systems.”* The project assumes that a natural-language form reduces the customer's need to know internal categories; this is design rationale, not measured user research.

UC-01 accepts original_message with optional order reference, requested outcome and evidence. A missing order number, attachment or requested outcome does not by itself prevent initial lodging. The original statement remains independently addressable by statement_id and kind=ORIGINAL; normalisation cannot overwrite it.

UC-01E accepts answers/evidence only for an owned case in AWAITING_INFORMATION with the current question_set_id and expected_case_version. It appends CLARIFICATION statements and binds accepted evidence in the same case. FR-002 concerns typed fact extraction and missing/ambiguous/conflicting distinctions; FR-005 concerns criterion-level evidence and targeted relevant questions, including reasonable purchase-proof alternatives. Neither requires a customer to supply facts the system has invented.

## 3. Behavioural models

### 3.1 Activity (MB-ACT-0.2 / C8)

![Member B Activity Diagram](../diagrams/member-b/member-b-activity.svg)

The activity separates Customer, B's Portal, A's Domain and A's Coordinator. Client validation provides feedback; the server independently authenticates, validates and admits input. Available owned STAGED files are bound atomically with accepted case/clarification input, while the original statement is preserved. HTTP 201/202 confirms resource creation/request acceptance and does not assert AI completion.

The clarification loop persists a current question set before notification dispatch. Missing facts keep AWAITING_INFORMATION and permit another valid UC-01E request even after three rounds. Closing the UI or failing to reply makes no business transition. A notification problem cannot erase accepted input or re-run the entire intake as a new request.

Actual current processing failure after bounded recovery may produce a persisted ProcessingFailure and guarded ESCALATED case. This applies to initial input or an accepted clarification; an invalid HTTP request, missing facts or customer silence cannot be relabelled as a failure. A later trusted Founder decision must use the exact allowed proposal/failure/block target. No automatic manual outcome, approval or execution is generated here.

### 3.2 Sequence (MB-SEQ-0.2 / C9)

![Member B Sequence Diagram](../diagrams/member-b/member-b-sequence.svg)

The linked SVG preserves two complete, independently framed interaction definitions. sd CustomerIntake contains evidence staging, case creation and repeatable clarification; only its fresh-acceptance ref fragments invoke sd ProcessAcceptedIntake. That second definition has a separate title, frame, lifelines and accepted-work precondition; it is not a continuation after rejected/replayed requests. Both PlantUML pages are assembled into the one SVG, with the reproducible recipe in the model index. All HTTP requests require authenticated role/resource access; every POST carries an Idempotency-Key. Unknown response recovery retains the same request and key.

Accepted replay returns its original receipt only while that content remains readable; it is followed by a GET for the current authorised case. Changed payload produces IDEMPOTENCY_CONFLICT. Removed receipt content produces non-retryable INVALID_STATE without resurrecting content or dispatching work; the UI cannot automatically replace the key. Fresh clarification admission atomically rechecks owner, case state, version, question set, answer references and evidence binding. Stale view conflicts require reload and a newly confirmed intent.

The actual DTO names are preserved: CustomerCaseView.clarification and collection_windows, CustomerStatement.statement_id/kind/raw_text, and CoordinatorResult. The earlier statement v1/vN and top-level questions shortcuts were not wire fields. Customer views expose safe customer material, never internal proposal/review/approval or provider credentials. History uses authorised snapshot cursors and tombstones rather than treating bounded previews as complete history.

### 3.3 State machine (MB-STM-0.2 / C10)

![Member B State Machine Diagram](../diagrams/member-b/member-b-state.svg)

The subject remains the shared **case-owned IntakeSession**, represented by an internal lifecycle_state. It starts after accepted durable case creation, passes through SUBMITTED/EVALUATING, and either requests clarification, hands to investigation (COMPLETE), or stops the intake episode on an actual guarded failure (ESCALATED_FAILURE). Recoverable processing errors and obsolete results have distinct guarded handling. Accepted replay causes no new lifecycle transition.

**IntakeViewSession** names a separate UI-only controller/view with local drafting, pending/error display and closing/reopening. It does not own or replace the durable IntakeSession. The figure does not introduce a public IntakeStatus enum or change ReturnCase status values. COMPLETE and ESCALATED_FAILURE remain quiescent durable states, not UML finals. G-REENTRY requires an already committed legal Domain transition to AWAITING_INFORMATION and a current case/input-bound ClarificationSet with existing guards satisfied. A current proposal may follow lawful Founder REQUEST_REVISION and an assessment gap back to clarification; a no-proposal failure cannot restart. Only an authoritative COMPLETED, REJECTED or MANUAL_HANDLED case satisfies G-TERMINAL and ends session behavior. Reopening the browser cannot reopen a reviewed case.

## 4. Choices, limitations and unapproved extensions

Targeted forms and basic local checks support understandable feedback; they do not establish legal compliance or remove server validation. The system preserves missing/conflicting/not-applicable facts and customer-requested outcomes separately from recommendations. Statement/evidence content is append-only during its permitted availability, with F.07 retention and tombstones still applicable.

B's original three-round escalation cap and seven-day archival timer were unapproved policy choices. They are removed from the active model: incomplete facts stay AWAITING_INFORMATION and silence does not generate a technical error. Any future budget/reminder/expiry policy needs explicit design and retention review before it changes behavior.

Business withdrawal is also an unapproved extension. The fifteen-route F.01 contract supplies no customer cancellation/withdrawal API. Leaving the page affects IntakeViewSession only and cannot create REJECTED. This draft makes no promise to add a DELETE or withdraw endpoint in Stage 2. The existing scope/interface approval process would apply to any such proposal.

No UI/API business implementation, live database transaction, provider call, measured usability or latency result, B personal acceptance, F.01/F.02 joint acceptance or M-S.03 completion is claimed. Source/render and contract checks are static design evidence. The original B commits remain attributable to B; this correction and any later B revisions must remain separately identifiable.

## 5. B's personal explanation preparation

B should use the model index and actual source history to prepare an explanation and record their own revisions; the following are prompts, not an already delivered first-person defence:

- Walk a complete intake and a fourth still-incomplete clarification across all three models. Explain why the latter stays AWAITING_INFORMATION.
- Distinguish local UI closing, a rejected stale request, an obsolete Coordinator result and an actual failure after accepted input.
- Identify the immutable statement reference, current question set, case/input versions and allowed evidence-binding step.
- Explain receipt replay after the case advances, receipt deletion, same-key uncertain recovery and why no automatic new key is safe.
- Describe IntakeViewSession versus the case-owned IntakeSession, and why an intake episode ending does not mean a business case completed.
- Show original B contributions, A/AI-assisted corrections and B's subsequent personal reasoning honestly; Git history alone is not proof of independent modelling.

The next acceptance step is B's substantive review/explanation and the designated non-author review of the exact corrected revision, followed by shared integration only where separately authorised and evidenced.
