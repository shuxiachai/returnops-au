# State Machine Diagram (ReturnCase Lifecycle)

> **Status — 2026-09-07:** v1 alignment draft; Member B/C review remains pending.
> `1.0.0-rc.5` review candidate for [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), not accepted. [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) is the review entry; check its actual head and reviews. `57d86fe` published rc.4 is the prior snapshot; rc.3 is an earlier candidate; [PR #9](https://github.com/shuxiachai/returnops-au/pull/9) is the rc.2 historical publication.
> Earlier modelling contributions and their Git history are retained. This
> revision does not claim product-baseline adoption, F.01 acceptance, or a
> running implementation.
>
> **MBSE model type:** Shared behavioural state machine for `ReturnCase`.
> **Traceability:** [v1.0 candidate, FR-001–FR-012 and NFR-002/004/009](../00-project-definition-v1.md).
> **Ownership:** [Frozen allocation and individual model chains](../07-frozen-work-allocation.md).

## 1. Shared lifecycle model

**Domain Service alone commits authoritative case transitions.** AI roles return
typed analysis; API, orchestration, and the deterministic Operations Service
submit results/events for Domain Service to validate and persist. Arrows below
describe guarded business transitions, not permission for an AI or provider
adapter to write case state directly.

This shared overview does not replace the three individual state-machine
subjects: A's `OperationAttempt`, B's `IntakeSession`, and C's `RiskReview`
(the earlier conceptual subject name was `ProposalReview`).

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED : Request accepted and original statement preserved

    SUBMITTED --> AWAITING_INFORMATION : Relevant facts missing or ambiguous
    SUBMITTED --> UNDER_INVESTIGATION : Sufficient information for read-only lookup
    AWAITING_INFORMATION --> AWAITING_INFORMATION : Partial answer and remaining questions
    AWAITING_INFORMATION --> UNDER_INVESTIGATION : Current requested clarification accepted and dependent decisions invalidated

    UNDER_INVESTIGATION --> POLICY_ASSESSMENT : Authorised mock order snapshot matched
    UNDER_INVESTIGATION --> AWAITING_INFORMATION : Correctable reference or purchase-proof gap
    UNDER_INVESTIGATION --> UNDER_INVESTIGATION : Read-only provider failure and bounded safe retry
    UNDER_INVESTIGATION --> ESCALATED : Accepted lookup CONFLICT or AUTHORITY_DENIED and OrderLookupBlock saved
    UNDER_INVESTIGATION --> ESCALATED : Technical retry exhaustion and ProcessingFailure saved

    POLICY_ASSESSMENT --> AWAITING_INFORMATION : Relevant evidence gap
    POLICY_ASSESSMENT --> RISK_REVIEW : Complete bounded source bundle and versioned proposal atomically accepted
    POLICY_ASSESSMENT --> ESCALATED : Cannot produce a usable result after bounded recovery

    RISK_REVIEW --> POLICY_ASSESSMENT : REVISE and create a new proposal version
    RISK_REVIEW --> AWAITING_INFORMATION : NEEDS_INFORMATION
    RISK_REVIEW --> ESCALATED : ESCALATE or unrecoverable review failure
    RISK_REVIEW --> AWAITING_APPROVAL : PASS for current input and proposal
    RISK_REVIEW --> AWAITING_APPROVAL : PASS_WITH_WARNING and non-blocking warnings displayed

    AWAITING_APPROVAL --> APPROVED : APPROVE and bind exact scope to trusted Founder
    AWAITING_APPROVAL --> POLICY_ASSESSMENT : REQUEST_REVISION and invalidate approval
    AWAITING_APPROVAL --> NOTIFICATION_PENDING : REJECT and save reason and customer outcome
    AWAITING_APPROVAL --> NOTIFICATION_PENDING : MANUAL_HANDLING and save customer outcome
    AWAITING_APPROVAL --> UNDER_INVESTIGATION : Controlled internal input update invalidates proposal review and approval
    ESCALATED --> POLICY_ASSESSMENT : Current proposal exists and Founder REQUEST_REVISION requires fresh proposal and review
    ESCALATED --> NOTIFICATION_PENDING : Current proposal or exact current failure or order block targeted by MANUAL_HANDLING

    APPROVED --> ACTION_IN_PROGRESS : Current risk scope expiry provider-authority and idempotency guards pass
    APPROVED --> AWAITING_APPROVAL : Approval expired before any effect and fresh approval required
    APPROVED --> UNDER_INVESTIGATION : Controlled internal input update before dispatch invalidates dependent decisions
    APPROVED --> ESCALATED : Dispatch blocked without an external effect

    ACTION_IN_PROGRESS --> ACTION_FAILED : Confirmed no-effect failure and completed results preserved
    ACTION_IN_PROGRESS --> ACTION_IN_PROGRESS : Confirmed label receipt saved and original artifact recovery pending
    ACTION_IN_PROGRESS --> ESCALATED : Artifact recovery exhausted and no accepted rejection or manual outcome
    ACTION_IN_PROGRESS --> RECONCILING : Ambiguous effect without confirmed receipt and OperationAttempt UNKNOWN
    ACTION_FAILED --> ACTION_IN_PROGRESS : Safe unfinished-command retry with valid approval and same key
    ACTION_FAILED --> ESCALATED : Retry unavailable or configured limit reached
    RECONCILING --> RECONCILING : Effect still unknown and lookup only
    RECONCILING --> ACTION_FAILED : Lookup confirms no effect and recoverable failure
    RECONCILING --> ACTION_IN_PROGRESS : Confirmed label receipt saved and original artifact recovery required
    RECONCILING --> ACTION_IN_PROGRESS : Complete prior result saved and current guards allow next command
    RECONCILING --> NOTIFICATION_PENDING : Eligible RETURN_CREATED outcome and both effects saved
    RECONCILING --> ESCALATED : Unresolved effect preserved for manual handling
    ESCALATED --> RECONCILING : Authorised lookup and no accepted rejection or manual outcome
    ACTION_IN_PROGRESS --> NOTIFICATION_PENDING : Eligible RETURN_CREATED outcome and both effects saved

    NOTIFICATION_PENDING --> NOTIFICATION_FAILED : Delivery failed and outcome retained
    NOTIFICATION_FAILED --> NOTIFICATION_PENDING : Retry notification only
    NOTIFICATION_PENDING --> COMPLETED : Saved outcome RETURN_CREATED and notification SENT and both effects saved
    NOTIFICATION_PENDING --> REJECTED : Notification SENT for saved rejection outcome
    NOTIFICATION_PENDING --> MANUAL_HANDLED : Notification SENT for saved manual outcome
    COMPLETED --> [*]
    REJECTED --> [*]
    MANUAL_HANDLED --> [*]
```

`UNKNOWN` belongs to an individual `OperationAttempt`; it is not a case state.
The case's `RECONCILING` state reflects lookup of that attempt while its result
is unknown. A historical-status lookup may remain authorised after execution
approval expires; it does not authorise a new command, a replay, or continuation
under an expired approval.

Once a rejection/manual outcome has been accepted, a historical lookup updates
only the attempt facts and audit. It preserves the accepted outcome, its
notification identity and the current pending/failed/terminal case state; it
does not move that case back to `RECONCILING` or `ESCALATED`. Even if both old
commands later prove successful, the saved manual/rejection notification still
selects `MANUAL_HANDLED`/`REJECTED`, never `COMPLETED`. The three notification
terminal guards are mutually exclusive by `NotificationRecord.outcome`.

Confirmed label effect with missing artifact is an internal phase of attempt
`EXECUTING`, not an eighth wire state or uncertain effect. Domain stores the
minimal original receipt, audit and artifact-only work before content storage;
crash recovery checks that receipt before any UNKNOWN transition. G-ARTIFACT
requires current recovery identity/access, original provider binding, claim and
retention permission. Original creation expiry neither grants new effects nor
blocks independently authorised original-artifact recovery. Storage failure or
missing permission retains EXECUTING/known effect; exhaustion escalates the case
only without an accepted manual/rejection outcome. Recovery cannot restore
deliberately deleted content. Only a saved full label result permits completion.
Historical artifact work, like historical lookup, preserves an accepted outcome.

## 2. Guard conditions and invariants

| Boundary | Required guard or rule |
|---|---|
| Intake and clarification — FR-001/002 | Preserve the original customer statement. An order number and desired remedy are not universally mandatory at initial submission. Clarification requires AWAITING_INFORMATION, the current question_set_id and expected_case_version, plus case access and requested answer/evidence validation. Ask targeted questions and allow relevant alternative proof; no unsolicited post-intake upload route is implied. |
| Order lookup — FR-003 | Distinguish match, correctable missing information, confirmed conflict, authority denial, and provider failure. A timeout never becomes an invented matched order. Retry only read-only lookup within a configured bound. |
| Assessment — FR-005/006/007 | Complete material/DTO-capacity preflight precedes current proposal acceptance; persist proposal and bundle atomically. Capacity failure creates no new current proposal, preserves old history and follows the existing technical manual branch. Keep customer claims, verified facts, evidence gaps, citations, and uncertainty distinct. A versioned conditional packet can report missing or conflicting grounding; packet creation alone is not approval eligibility. |
| Risk gate — FR-008 | Only a current-input/current-proposal `PASS` or `PASS_WITH_WARNING` supports approval. The other results are `REVISE`, `NEEDS_INFORMATION`, and `ESCALATE`. A single confidence threshold is not a substitute for these decisions and findings. |
| Escalation recovery — FR-003/008/009 | Founder cannot approve an escalated proposal directly. REQUEST_REVISION requires a current proposal and creates a new version needing a fresh passing review. Without a current proposal, exactly one current ProcessingFailure or OrderLookupBlock is required; only MANUAL_HANDLING can target it. No no-proposal revision/restart endpoint is added. |
| Founder approval — FR-009 | Bind authenticated Founder identity, case/input/proposal/review versions, exact commands and parameter fingerprint, applicable amount ceiling, reason, and expiry. Record `APPROVE`, `REJECT`, `REQUEST_REVISION`, or `MANUAL_HANDLING` distinctly. |
| Dispatch — FR-010, NFR-002/009 | Recheck current passing review, valid approval, parameter scope, provider authority, allowlist, and stable command idempotency before each new effect. Course commands are simulated `CREATE_RETURN` and `GENERATE_LABEL`, not refunds, charges, or inventory changes. |
| Provider result — FR-010/011 | HTTP 200 alone is not business success. Validate original provider facts, operation identity and scope. Persist a confirmed-label receipt/audit/artifact work first; keep the attempt EXECUTING without result until a complete OperationResult including label_evidence_id is committed. Storage failure is neither no-effect failure nor UNKNOWN. |
| Partial failure and unknown effect — NFR-004 | Preserve completed commands and confirmed-effect receipts. Recovery reads receipts first: known labels use G-ARTIFACT/current access to retrieve/store only original content; absent confirmation, query an `UNKNOWN`/`RECONCILING` attempt before considering retry; retry only a confirmed-safe unfinished command with the same idempotency key and valid approval. Never replay a successful return because its label or notification failed. |
| New information — FR-002/009 | An accepted current clarification or a provenance/authority/version-checked internal material update invalidates dependent proposal/review/approval before further effects. The AWAITING_APPROVAL/APPROVED arrows refer only to controlled internal updates, not an additional customer endpoint. No old result or unresolved effect is erased; in-flight effects require reconciliation. |
| Notifications and terminal states — FR-009/010/011 | Recheck the current accepted outcome and notification identity when claiming work and saving delivery. Only saved `RETURN_CREATED` plus valid saved return/label results and `SENT` permits `COMPLETED`. Saved `REJECTED`/`MANUAL_HANDLED` selects its own terminal after delivery, irrespective of historical operation success. Notification retry cannot change outcome kind or replay operations. |
| Manual closure — FR-009/011 | Persist the actual outcome and unresolved uncertainty. Later historical lookup updates facts/audit without replacing the accepted outcome or its notification, reopening the case or automatically resubmitting work. `MANUAL_HANDLED` does not assert that an unknown provider effect never happened. |
| No-proposal manual target — FR-003/009/011 | Domain Service checks trusted Founder identity, expected case version, ESCALATED state, no current proposal and exact case/input/current failure or block ID. OrderLookupBlock can represent only an accepted pre-proposal lookup CONFLICT/AUTHORITY_DENIED; it cannot replace a technical error or source-policy conflict. Create only audited outcome/notification work; do not create approval/commands or erase historical effects. A retained resolved target after notification processing is readable, not newly actionable. |

## 3. Verification and implementation boundary

A implements and self-tests lifecycle, approval, and operation guards; B
self-tests the corresponding UI behaviours; C self-tests retrieval/risk and
coordinates cross-system evaluation. The [work packages](../08-delivery-work-packages.md)
define the individual deliverables and cross-review responsibilities.

This is a modelling draft, not proof that runtime guards exist. In particular,
the Founder manual path **before any current proposal exists** distinguishes
actual technical `ProcessingFailure` from an accepted order `CONFLICT` or
`AUTHORITY_DENIED` stored as `OrderLookupBlock`. Neither needs a fabricated
proposal, review or technical error. The [F.01 rc.5 review candidate](../09-interface-contract-v1.md)
defines both manual-only targets; runtime state checks and joint contract/model
acceptance remain outstanding. Source-policy conflicts continue through a
conditional packet and independent Risk, not through an order-block shortcut.
