# Shared Interactions - Assessment, Decisions and Governed Execution

> **Status:** Shared design candidate aligned to [docs/00](../00-project-definition-v1.md)
> and [docs/07](../07-frozen-work-allocation.md); not runtime or individual-model
> completion evidence.
> **Revision:** `1.0.0-rc.5` review candidate for [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), not accepted. [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) is the review entry; check its actual head and reviews. `57d86fe` published rc.4 is the prior snapshot; rc.3 is an earlier candidate; [PR #9](https://github.com/shuxiachai/returnops-au/pull/9) records the earlier rc.2 publication.
> **Traceability:** FR-001–FR-012; NFR-001–NFR-009; UC-01/01E–UC-05;
> shared model review plus M-A/M-B/M-C in [docs/08](../08-delivery-work-packages.md).

The original Lab 3 interactions are retained and corrected using Member B
`@ChengsiLi`'s three-role naming, separate Founder Dashboard, Domain Service and
deterministic Operations Service from [PR #8](https://github.com/shuxiachai/returnops-au/pull/8)
(`origin/docs/6-baseline-uml-rebaseline`, locally inspected). Reuse does not
claim that PR #8 was merged, transfer its authorship, or complete the three
members' separately authored activity/sequence/state-machine chains.

The former single long diagram is divided at persisted hand-offs so each
branch can be reviewed. All business writes shown below go through Domain
Service; the orchestrator chooses bounded AI work and submits results for
validation. Messages are conceptual operations, not promises that F.01 already
implements each route. The rc.5 contract review candidate still needs joint
review and cannot replace docs/00 or docs/07 as the product/allocation baseline.

## 1. Intake, grounding and the five risk outcomes

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant Portal as Customer Portal
    participant API as Authenticated API
    participant Domain as Domain Service
    participant Orch as Bounded Workflow Orchestrator
    participant Coordinator as Customer Case Coordinator Agent
    participant Assessment as Returns Assessment Agent
    participant Retrieval as Versioned Retrieval and Citation Port
    participant Risk as Independent Compliance and Risk Reviewer
    participant Order as Read-only Mock Order Provider
    participant Store as Case and Audit Store

    Customer->>Portal: Submit original request or requested clarification
    Portal->>API: Statement, optional order/outcome/evidence, request key
    API->>Domain: Verified customer context and validated request
    Domain->>Store: Check ownership, request replay and current input version
    break Invalid request, unauthorised reference or replay conflict
        Domain-->>API: Typed error, no new case or operational authority
        API-->>Portal: Safe error and correlation ID
    end
    break Same key and same previously accepted request
        Domain-->>API: Original receipt only while readable, otherwise 409 INVALID_STATE and retryable false after permitted deletion
        API-->>Portal: Reuse acceptance, no new write or work or automatic new key, GET authorised current or history
    end
    opt Fresh clarification of an existing case
        Domain->>Store: Check AWAITING_INFORMATION, current question_set_id and expected_case_version
        break Wrong state, replaced question set or stale case version
            Domain-->>API: Typed denial or conflict, no accepted input or analysis work
            API-->>Portal: Refresh the current authorised clarification view
        end
    end
    Domain->>Store: Atomically preserve original statement and accepted evidence
    Note over Domain,Store: Acceptance is reused on same-key same-body replay, receipt content remains subject to retention
    Domain-->>API: Authoritative case receipt
    API-->>Portal: Current case and clarification state
    Domain->>Orch: Start permitted analysis for current input version
    Orch->>Coordinator: Extract facts and identify relevant missing information
    Coordinator-->>Orch: Typed facts and clarification questions, not state changes
    Orch->>Domain: Validate and record Coordinator result
    Domain->>Store: Save separate facts and guarded case transition

    break Required information is missing or ambiguous
        Domain-->>API: AWAITING_INFORMATION and targeted questions
        API-->>Portal: Show only case-relevant questions
        Portal-->>Customer: Request clarification or alternative proof
        Note over Portal,Domain: Accepted clarification appends a statement and resumes a new permitted round
    end

    loop Permitted assessment round while current input and machine budget allow
        Orch->>Assessment: Assess current original statements and accepted facts
        Assessment->>Order: Authorised read-only order lookup
        Order-->>Assessment: MATCHED, NOT_FOUND, CONFLICT, AUTHORITY_DENIED or PROVIDER_FAILURE
        Assessment-->>Orch: Typed lookup result, no invented snapshot
        Orch->>Domain: Validate and record lookup result
        Domain->>Store: Preserve snapshot or failure and choose legal transition

        break Lookup is not MATCHED
            alt NOT_FOUND with correctable or missing order detail
                Domain-->>API: AWAITING_INFORMATION and correction question
                API-->>Portal: Show correction request
            else CONFLICT or AUTHORITY_DENIED
                Domain->>Store: Save OrderLookupBlock from accepted case/input/status/message and record ESCALATED
            else PROVIDER_FAILURE
                Domain->>Store: Bounded read-retry, or save actual ProcessingFailure and ESCALATED when exhausted
            end
            Note over Domain,Store: No proposal, review or invented technical error and exact current failure or order block permits only manual handling
        end

        Orch->>Assessment: Build criterion-level evidence matrix from accepted material
        Assessment->>Retrieval: Retrieve reviewed passages with source and corpus versions
        Retrieval-->>Assessment: Passages, provenance and no-match/conflict signals
        Assessment-->>Orch: Non-executable DecisionPacket candidate, statement refs and matrix
        Orch->>Domain: Validate proposal schema, facts and version bindings
        break Proposal is invalid or cannot be safely prepared
            Domain->>Store: Record bounded revision, required information or escalation
            Note over Domain,Store: No executable command and no current passing review are created
        end
        Orch->>Retrieval: Check candidate citations against the versioned passages
        Retrieval-->>Orch: Citation identity, location and content verification results
        Orch->>Domain: Assemble complete bounded historical input bundle and validate all bindings
        break Required material exceeds internal DTO capacity
            Domain->>Store: Preserve old history, save actual-stage non-retryable REQUEST_TOO_LARGE failure and ESCALATED with no new current proposal
        end
        Domain->>Store: Atomically save valid new proposal and complete bundle, invalidate stale review and approval
        Orch->>Risk: Separate invocation with proposal, original evidence, order, source passages, citation checks and material conflict signals
        Note over Orch,Risk: No generator hidden reasoning, C3 observations are evidence, never authoritative facts
        Risk-->>Orch: Version-bound review or typed invocation error
        Orch->>Domain: Validate current case/input/proposal/corpus and record review

        alt Invocation error, malformed review or stale version
            Domain->>Store: Audit error only, no accepted review or PASS, bounded retry or escalation
        else REVISE
            Domain->>Store: Save valid REVISE review, POLICY_ASSESSMENT and explicit revision requests
            Note over Orch,Assessment: A new proposal version is independently reviewed on the next permitted round
        else NEEDS_INFORMATION
            break Await customer information
                Domain->>Store: Save valid NEEDS_INFORMATION review and AWAITING_INFORMATION
                Domain-->>API: AWAITING_INFORMATION and requested facts/evidence
                API-->>Portal: Show targeted clarification
            end
        else ESCALATE
            break Await Founder manual handling
                Domain->>Store: Save valid ESCALATE review and ESCALATED, preserve conflict evidence
                Note over Domain,Store: This proposal cannot be approved, an automatic return needs a new proposal and passing review
            end
        else PASS or PASS_WITH_WARNING
            break Analysis is ready for human review
                Domain->>Store: Save valid passing review, AWAITING_APPROVAL only if other guards pass
                Note over Domain,Store: A warning cannot hide a blocking finding, passing Risk grants no operation authority
            end
        end
    end
    Note over Domain,Store: Exhausted machine rounds produce an explicit safe stop or escalation, never implicit approval
```

The order lookup is a read. Only Operations Service may invoke return or label
operations. `CaseLineItem` selections refer to one order and a single planned
parcel; selecting multiple items does not create multiple shipments. Original
customer requests, extracted fields and the recommendation remain independently
stored. The UI reads server-confirmed state and never accepts an agent's text
as an authoritative transition.

At the accepted new-input/revision boundary, previous material loses current
validity but remains immutable history. A returned Assessment candidate becomes
the current proposal only after its complete bounded material bundle passes
Domain preflight; capacity failure cannot resurrect the older packet or delete
its history.

After intake, customer evidence is accepted only through the current requested
clarification with its question set and expected case version. No unrequested
upload or general case-edit endpoint is implied. A controlled internal material
update (for example a refreshed authorised order snapshot) must pass provenance,
authority and version checks in Domain Service, then invalidate dependent
proposal/review/approval before further effects. The shared case-machine input
arrows outside `AWAITING_INFORMATION` describe this internal boundary.

## 2. Founder review and four decisions

```mermaid
sequenceDiagram
    autonumber
    actor Founder as Human Founder
    participant Dashboard as Founder Dashboard
    participant API as Authenticated API
    participant Domain as Domain Service
    participant Guard as Approval Guard
    participant Store as Case and Audit Store
    participant Orch as Bounded Workflow Orchestrator
    participant Ops as Deterministic Operations Service

    Founder->>Dashboard: Open a case requiring review or manual attention
    Dashboard->>API: Read authorised current case
    API->>Domain: Verified Founder query
    Domain->>Store: Load authoritative input, current proposal or failure or order block, review, operations and history
    Store-->>Domain: Current records and cited sources
    Domain-->>API: Read model, allowed choices and exact approvable scope when eligible
    API-->>Dashboard: Evidence, versions, warnings and permitted choices
    Dashboard-->>Founder: Separate requested outcome, recommendation and actual result
    Note over Dashboard,Domain: No-proposal ESCALATED exposes exactly one current failure or order block and only MANUAL_HANDLING
    Founder->>Dashboard: Choose a decision permitted for the displayed current target
    Dashboard->>API: Current context, choice, reason, request key and scope confirmation if approving
    API->>Domain: Verified Founder identity and untrusted decision request
    Domain->>Store: Read scoped accepted-request fact after authentication and case access
    break Same key and canonical body already accepted
        Domain-->>API: Original receipt if still readable, otherwise 409 INVALID_STATE and retryable false after permitted deletion
        API-->>Dashboard: No new write, dispatch or automatic new key, GET current or history separately
    end
    break Same scoped key used for another body
        Domain-->>API: 409 IDEMPOTENCY_CONFLICT without new work
    end
    Domain->>Store: Read current case/input plus exact proposal or failure or block target
    Domain->>Guard: Validate identity, case version, target ownership/freshness, state and decision conditions
    Guard-->>Domain: Validated decision or blocking reason

    break Invalid, stale, over-scope or unavailable decision
        Domain->>Store: Record safe denial evidence without granting authority
        Domain-->>API: Typed conflict/denial and current correlation ID
        API-->>Dashboard: Refresh or explain the blocked action
    end

    alt APPROVE with current PASS or PASS_WITH_WARNING and every guard passed
        Domain->>Store: Atomically record exact ApprovalRecord, APPROVED and durable dispatch work
        Note over Domain,Store: Bind actor, case/input/proposal/review, two commands, item quantities, parcel, parameters, amount ceiling and expiry
        Domain->>Ops: Dispatch only the committed approval/work reference
    else REJECT targeting current proposal
        Domain->>Store: Record reason and rejection outcome, queue notification, NOTIFICATION_PENDING
    else REQUEST_REVISION targeting current proposal
        Domain->>Store: Record reason, invalidate prior permission, POLICY_ASSESSMENT
        Domain->>Orch: Prepare a new version within the bounded analysis workflow
    else MANUAL_HANDLING targeting current proposal or exact current no-proposal record
        Domain->>Store: Record actual human outcome, queue notification, NOTIFICATION_PENDING
        Note over Domain,Store: Atomically save target ID, outcome, audit and notification work and no ApprovalRecord or return/label work, preserve historical effects
    end
    Domain-->>API: Authoritative decision receipt and pending state
    API-->>Dashboard: Show the accepted decision separately from later execution and notification
```

An ESCALATED proposal cannot take the APPROVE branch. REQUEST_REVISION requires
a current proposal; the revised version must pass independent Risk again. An
ESCALATED case without a current proposal instead requires exactly one current
`ProcessingFailure` or `OrderLookupBlock`. Only `MANUAL_HANDLING` may target its
`processing_failure_id` or `order_lookup_block_id`; both exclude proposal,
preview, scope and approval fields. Domain Service must match the persisted
record to the current case/input and, for an order block, the accepted lookup.
`OrderLookupBlock` is only a pre-proposal `CONFLICT/AUTHORITY_DENIED` result;
source-policy conflict remains packet/Risk material. There is no no-proposal
revision/restart endpoint and no fabricated proposal or technical failure.

The [F.01 rc.5 review candidate](../09-interface-contract-v1.md) still needs joint
review. These interactions do not prove a working endpoint. A resolved target
may remain visible while notification is pending/failed or after manual closure;
state checks still reject a new decision. Authenticated same-key/same-body replay
reuses acceptance: original receipt only while readable, otherwise after permitted
deletion 409 INVALID_STATE/retryable=false, no write/work or automatic new key.
B reads current/history views. Notification retry does not replay operations or erase
unknown effects. Exact approval and provider permissions remain separate;
the browser cannot create a trusted ApprovalRecord.

## 3. Execution, idempotency and unknown-result reconciliation

```mermaid
sequenceDiagram
    autonumber
    participant Domain as Domain Service
    participant Ops as Deterministic Operations Service
    participant Guard as Approval Guard
    participant Provider as Mock Returns and Logistics Provider
    participant Artifacts as Scoped Label Artifact Store
    participant Store as Case and Audit Store

    Domain->>Ops: Process committed command or original-recovery work
    loop Eligible command or recovery step within configured budget
        Ops->>Domain: Read current scope, dependencies, original attempts and effect receipts
        Domain->>Store: Read durable records and enforce the appropriate single claimant
        Store-->>Domain: Saved result, confirmed receipt, unresolved effect or eligible new command
        Domain-->>Ops: Authoritative work context or rejection
        break Work blocked, concurrent claimant active or required dependency absent
            Ops-->>Domain: Retain durable facts and safe pending reason, no invocation
        end
        alt Complete prior successful result exists
            Ops-->>Domain: Reuse saved result, no invocation
        else Durable confirmed-label receipt exists but artifact is incomplete
            Note over Domain,Ops: Keep attempt EXECUTING without result, use artifact recovery below, never new create or UNKNOWN
        else UNKNOWN or orphaned intent without reliable confirmed-effect receipt
            Ops->>Domain: Claim original-effect query and record RECONCILING
            Domain->>Store: Preserve original identity and any accepted rejection or manual outcome and case state
            Ops->>Provider: Authorised query using original provider ID or fingerprint
            Provider-->>Ops: Confirmed original effect, confirmed no effect or still unknown
            Ops->>Domain: Submit validated original observation
            alt Confirmed label effect with incomplete artifact binding
                Domain->>Store: Atomically persist original receipt, audit and artifact-only work in EXECUTING
            else Complete confirmed return result
                Domain->>Store: Persist complete OperationResult, SUCCEEDED and audit
            else Confirmed no effect
                Domain->>Store: Persist FAILED and no-effect evidence
                Note over Domain,Ops: Only a later separately guarded retry may use the stable original logical key
            else Still unknown or lookup unavailable
                break Stop automatic dispatch
                    Domain->>Store: Preserve uncertainty and audit, escalate only without accepted rejection or manual outcome
                end
            end
        else New or explicitly retry-safe unfinished command without confirmed effect
            Ops->>Guard: G-DISPATCH current state, passing Risk, trusted authority, exact scope, expiry and allowlist
            Guard-->>Ops: Valid or blocked
            Ops->>Provider: Check configured provider permission without an effect
            Provider-->>Ops: Authorised or denied
            break Any dispatch guard or provider permission fails
                Ops->>Domain: Record actual denial, no effect and no fabricated approval or attempt
            end
            Ops->>Domain: Request claim with expected bindings
            Domain->>Store: Atomically recheck scope and dependencies, claim and persist EXECUTING intent plus audit
            Domain-->>Ops: Claimed command or rejection
            break Claim lost or intent commit unconfirmed
                Note over Domain,Ops: No invocation, losing worker does not change winner
            end
            Ops->>Guard: Final invocation guard with own uninvoked reservation
            Guard-->>Ops: Allowed or blocked
            break Final guard fails
                Ops->>Domain: Persist actual BLOCKED fact without invocation
            end
            Ops->>Provider: Invoke one approved command with stable key, label uses saved return and same parcel
            Provider-->>Ops: Raw effect observation, definite no-effect failure or uncertainty
            Ops->>Domain: Submit original provider observation with operation and command bindings
            alt Confirmed label effect
                Domain->>Store: Atomically save original receipt, audit and artifact-only work, EXECUTING without result
            else Complete confirmed return result
                Domain->>Store: Atomically save full OperationResult, SUCCEEDED and audit
            else Confirmed no-effect failure
                Domain->>Store: Save FAILED and classified no-effect evidence
            else Uncertain effect without a confirmed receipt
                Domain->>Store: Save UNKNOWN if writable, original identity query required
            end
        end
        Note over Domain,Store: Any unconfirmed commit requires rereading last durable receipt or intent before recovery, never another create
        opt Durable confirmed-label receipt exists and full result is still missing
            Ops->>Domain: Request G-ARTIFACT claim under current recovery identity and access
            Domain->>Store: Validate original binding, provider read permission, retention and work generation
            Domain-->>Ops: Original-artifact recovery allowed or denied
            alt Allowed and claim held
                opt Original content needed and retention permits retrieval
                    Ops->>Provider: Query or retrieve original label only, no creation
                    Provider-->>Ops: Original content or retrieval error
                end
                opt Valid original content available and current access allows storage
                    Ops->>Artifacts: Validate and store original label PDF and hash
                    Artifacts-->>Ops: Scoped evidence reference or actual storage failure
                end
                Ops->>Domain: Submit original binding, saved reference or recovery failure
                alt Full label reference validated
                    Domain->>Store: Atomically commit full OperationResult with label_evidence_id, SUCCEEDED and audit
                    Note over Domain,Store: If commit unconfirmed, reread and reuse original receipt or saved artifact, no new invocation
                else Artifact remains missing
                    Domain->>Store: Retain EXECUTING, receipt and artifact-only work with actual error
                end
            else Current recovery authority or retention unavailable
                Note over Domain,Store: Preserve known effect, no retrieve or store and never restore deliberately deleted content
            end
        end
    end
    Domain->>Store: Read current accepted outcome, notification and saved full command results
    alt Accepted rejection or manual outcome exists
        Domain->>Store: Preserve its outcome, notification identity and pending or terminal case state
        Note over Domain,Store: Historical effect or artifact recovery never substitutes RETURN_CREATED or COMPLETED
    else Execution eligible and both full results committed without contradictory uncertainty
        Domain->>Store: Atomically recheck case and outcome version, persist or reuse RETURN_CREATED notification work
    else No deliverable outcome
        Note over Domain,Store: Retain facts and pending work, budget exhaustion escalates only without accepted rejection or manual outcome
    end
```

UNKNOWN and RECONCILING describe `OperationAttempt.status`; the case may expose
RECONCILING while those attempts are checked. HTTP success alone is not proof
of a successful business effect. An expired or superseded approval cannot permit
a new effect, but authorised lookup may still establish what an earlier attempt
actually did. Unresolved partial execution preserves successful steps and never
restarts the whole plan. Recovery budget exhaustion stays visible and requires
manual attention instead of pretending the case succeeded.

Confirmed label effect with missing artifact uses the existing EXECUTING status
with no result. Domain first commits a minimal original receipt, audit and
artifact-only work. Recovery checks that receipt before considering UNKNOWN;
G-ARTIFACT permits only original-label query/retrieval/storage under current
recovery access and retention. Creation-approval expiry is independent of this
read/store permission. File failure does not mean no effect or uncertain effect;
SUCCEEDED requires a committed full result including label_evidence_id.
The internal receipt/work is not a new wire DTO or state.

An already accepted manual/rejection outcome remains authoritative during a
late lookup, whether its notification is pending, failed or sent. Lookup may
confirm old success or preserve uncertainty without reopening or escalating
that case. This historical observation grants no new dispatch permission and
is separate from the unresolved cross-approval design choice MA-Q02.

Durable claiming, approval freshness at invocation, crash recovery and provider
idempotency are implementation obligations of A1/A2, not guarantees supplied by
Mermaid. A3 may replace the mock adapter only with verified no-charge test access
and the same rules. Its independent integration remains a selected optional
course feature, not another claim for the core mock/retry implementation.

## 4. Independent outcome notification

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    participant Domain as Domain Service
    participant Ops as Deterministic Operations Service
    participant Notify as Mock Notification Provider
    participant Store as Case and Audit Store

    Domain->>Ops: Send a persisted execution, rejection or manual-outcome notification
    Note over Domain,Ops: Claim only the current accepted outcome and its existing notification identity
    Note over Domain,Ops: A notification-only work item contains no return/label dispatch instruction
    Ops->>Notify: Send recorded outcome, next step and relevant responsibility/cost instructions
    Notify-->>Ops: SENT or typed delivery failure
    Ops->>Domain: Record notification result under its own key
    alt Confirmed delivery matches the current notification and accepted outcome
        Domain->>Store: Atomically recheck outcome/work identity, record SENT and choose its terminal
        Note over Domain,Store: RETURN_CREATED plus saved return and label becomes COMPLETED, REJECTED stays REJECTED, MANUAL_HANDLED stays MANUAL_HANDLED
        Notify-->>Customer: Outcome and next step, simulated label only when one actually exists
    else Delivery failed, uncertain or current binding changed
        Domain->>Store: Retain current outcome and durable state, save applicable notification failure only
        Note over Domain,Ops: Retry this notification only, never repeat CREATE_RETURN or GENERATE_LABEL
    end
```

COMPLETED requires saved `RETURN_CREATED`, valid return and label success, and
matching notification delivery. An accepted rejection/manual outcome cannot be
overridden by old operations later proving successful; sent work is not resent.
REJECTED and MANUAL_HANDLED do not count as successful simulated operations.
A generic request for more information is not a final outcome notification and
does not close the case. Founder and customer views obtain their authorised
read models through the API; an accepted decision or HTTP 202 is not completion.

## 5. Review checklist and contribution boundary

- Trace one complete case, one clarification, each of the five Risk outcomes,
  and each of the four Founder decisions through persisted hand-offs.
- For stale/expired/wrong-scope decisions and denied provider authority, verify
  that the first business-effect call is never reached.
- For duplicate, partial and unknown results, identify the durable key, claim,
  provider fingerprint, saved result and query-before-retry step.
- For notification failure, show that only notification work repeats and the
  case remains pending rather than entering a false completed state.
- Trace return SUCCEEDED, label UNKNOWN, escalation, then accepted manual outcome:
  a late label-success lookup must retain its pending/sent manual notification
  and select MANUAL_HANDLED, never COMPLETED. Repeat with an inconclusive lookup.
- Reject fresh customer evidence without a current clarification question set;
  distinguish a valid clarification from a controlled internal material update.
- Verify all state writes originate at Domain Service and all operational
  provider calls originate at Operations Service. AI results remain untrusted
  typed input to deterministic validation.
- Attach actual reviews and eventual model-to-code traces. These shared diagrams
  do not replace A's AH-10, B's AH-01 or C's AH-08 personal three-diagram chains,
  and they do not supply the runtime Composite Structure Diagram.
