# Shared Interactions - Assessment, Decisions and Governed Execution

> **Status:** Shared design candidate aligned to [docs/00](../00-project-definition-v1.md)
> and [docs/07](../07-frozen-work-allocation.md); not runtime or individual-model
> completion evidence.
> **Local synchronisation:** 2026-09-07, pending review rather than an adoption date.
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
implements each route. The separately revised rc.2 contract still needs joint
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
        Domain-->>API: Replay prior receipt without new writes or work
        API-->>Portal: Prior receipt, then read current authorised case
    end
    Domain->>Store: Atomically preserve original statement and accepted evidence
    Note over Domain,Store: Same key and content replay the prior receipt, no duplicate case or work
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
                Domain->>Store: Record ESCALATED and actual reason
            else PROVIDER_FAILURE
                Domain->>Store: Keep safe state and bounded read-retry, or ESCALATED when exhausted
            end
            Note over Domain,Store: No fabricated proposal is required for a failed lookup, manual handling remains possible
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
        Domain->>Store: Save valid new proposal version, invalidate stale review and approval
        Orch->>Retrieval: Check proposal citations against the versioned passages
        Retrieval-->>Orch: Citation identity, location and content verification results
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
    Domain->>Store: Load authoritative input, proposal, review, operations and history
    Store-->>Domain: Current records and cited sources
    Domain-->>API: Read model, allowed choices and exact approvable scope when eligible
    API-->>Dashboard: Evidence, versions, warnings and permitted choices
    Dashboard-->>Founder: Separate requested outcome, recommendation and actual result
    Founder->>Dashboard: Choose APPROVE, REJECT, REQUEST_REVISION or MANUAL_HANDLING
    Dashboard->>API: Current context, choice, reason, request key and scope confirmation if approving
    API->>Domain: Verified Founder identity and untrusted decision request
    Domain->>Store: Resolve replay and read current case/proposal/review
    Domain->>Guard: Validate identity, freshness, state and decision-specific conditions
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
    else REJECT
        Domain->>Store: Record reason and rejection outcome, queue notification, NOTIFICATION_PENDING
    else REQUEST_REVISION
        Domain->>Store: Record reason, invalidate prior permission, POLICY_ASSESSMENT
        Domain->>Orch: Prepare a new version within the bounded analysis workflow
    else MANUAL_HANDLING
        Domain->>Store: Record actual human outcome, queue notification, NOTIFICATION_PENDING
        Note over Domain,Store: No ApprovalRecord and no return/label command are created
    end
    Domain-->>API: Authoritative decision receipt and pending state
    API-->>Dashboard: Show the accepted decision separately from later execution and notification
```

An ESCALATED proposal cannot take the APPROVE branch. REQUEST_REVISION may
start a new assessment; the revised proposal must pass independent Risk again.
A failure before any valid proposal can still require recorded manual handling.
That no-proposal request shape is defined in the
[F.01 rc.2 candidate](../09-interface-contract-v1.md), pending joint review:
this conceptual interaction is not evidence of a working endpoint and must not
be implemented by manufacturing an approvable proposal. Exact approval and provider permissions
are separate requirements; the browser cannot create a trusted ApprovalRecord.

## 3. Execution, idempotency and unknown-result reconciliation

```mermaid
sequenceDiagram
    autonumber
    participant Domain as Domain Service
    participant Ops as Deterministic Operations Service
    participant Guard as Approval Guard
    participant Provider as Mock Returns and Logistics Provider
    participant Store as Case and Audit Store

    Domain->>Ops: Process durable work for an approved command set
    loop Eligible command or reconciliation step within the configured recovery budget
        Ops->>Domain: Obtain current scope, dependencies and prior attempt for the logical key
        Domain->>Store: Read durable command/attempt records and enforce single claimant
        Store-->>Domain: Prior success, unknown attempt, or eligible unfinished command
        Domain-->>Ops: Authoritative work context or blocked result

        break Work is blocked, concurrently claimed or dependency is not successful
            Ops-->>Domain: Return existing receipt or safe pending/blocking reason
            Note over Domain,Store: Never dispatch two effects first and deduplicate afterwards
        end

        alt Prior successful result exists
            Ops-->>Domain: Reuse successful provider result, no invocation
        else Prior attempt is UNKNOWN or RECONCILING
            Ops->>Domain: Record reconciliation start
            Domain->>Store: Attempt RECONCILING and visible case reconciliation state
            Ops->>Provider: Authorised status query using saved provider ID or operation fingerprint
            Provider-->>Ops: Confirmed success, confirmed no effect, or still unknown
            Ops->>Domain: Persist typed reconciliation observation
            Domain->>Store: Record facts without discarding historical effects
            alt Confirmed success
                Note over Domain,Ops: Reuse result and advance only to the next unfinished dependent command
            else Confirmed no effect
                Note over Domain,Ops: A later eligible step may retry the same key only after current approval and provider checks
            else Still unknown or lookup unavailable
                break Stop automatic dispatch and retain manual recovery context
                    Domain->>Store: Preserve unresolved attempt, audit reason and escalate when required
                end
            end
        else New or explicitly retry-safe unfinished command
            Ops->>Guard: Revalidate trusted actor, current state/versions, exact scope, expiry and allowlist
            Guard-->>Ops: Valid or blocked
            Ops->>Provider: Check independent provider permission without creating an effect
            Provider-->>Ops: Authorised or denied
            break Any dispatch guard or provider permission fails
                Ops->>Domain: Record blocked attempt with zero provider effect
                Domain->>Store: Preserve facts and blocking reason, do not mark completed
            end
            Ops->>Domain: Reserve the exact logical attempt against current versions
            Domain->>Store: Atomically confirm scope and claim, then record ACTION_IN_PROGRESS
            Domain-->>Ops: Reserved command or typed version/claim conflict
            break Reservation fails or authority changed before invocation
                Note over Domain,Ops: No provider effect, resolve current state before reconsidering work
            end
            alt Command is CREATE_RETURN
                Ops->>Provider: Create simulated return for approved same-order items and one parcel
            else Command is GENERATE_LABEL and return result is already saved
                Ops->>Provider: Generate one non-chargeable label using saved return result and same parcel
            end
            Provider-->>Ops: Typed business success, explicit failure or ambiguous timeout
            Ops->>Domain: Record provider ID, fingerprint, logical key and typed result
            alt Validated business success
                Domain->>Store: Append SUCCEEDED attempt and result before next command
            else Explicit failure with known outcome
                Domain->>Store: Append FAILED and classified recovery conditions
                Note over Domain,Ops: Retry only if known safe, budget remains and current guards pass
            else Ambiguous timeout or unverified outcome
                Domain->>Store: Append UNKNOWN attempt, next eligible step is query, not dispatch
            end
        end
    end
    Domain->>Store: Check both command results and outstanding attempts
    opt Return and label both succeeded and their results are stored
        Domain->>Store: Queue execution-outcome notification and set NOTIFICATION_PENDING
    end
```

UNKNOWN and RECONCILING describe `OperationAttempt` results; the case may expose
RECONCILING while those attempts are checked. HTTP success alone is not proof
of a successful business effect. An expired or superseded approval cannot permit
a new effect, but authorised lookup may still establish what an earlier attempt
actually did. Unresolved partial execution preserves successful steps and never
restarts the whole plan. Recovery budget exhaustion stays visible and requires
manual attention instead of pretending the case succeeded.

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
    Note over Domain,Ops: A notification-only work item contains no return/label dispatch instruction
    Ops->>Notify: Send recorded outcome, next step and relevant responsibility/cost instructions
    Notify-->>Ops: SENT or typed delivery failure
    Ops->>Domain: Record notification result under its own key
    alt Notification is SENT
        Domain->>Store: Record delivery and choose final state from persisted outcome kind
        Note over Domain,Store: Execution success becomes COMPLETED, rejection becomes REJECTED, manual outcome becomes MANUAL_HANDLED
        Notify-->>Customer: Outcome and next step, simulated label only when one actually exists
    else Delivery failed
        Domain->>Store: NOTIFICATION_FAILED with separately retryable notification record
        Note over Domain,Ops: Retry this notification only, never repeat CREATE_RETURN or GENERATE_LABEL
    end
```

COMPLETED requires saved return and label success plus notification delivery.
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
- Verify all state writes originate at Domain Service and all operational
  provider calls originate at Operations Service. AI results remain untrusted
  typed input to deterministic validation.
- Attach actual reviews and eventual model-to-code traces. These shared diagrams
  do not replace A's AH-10, B's AH-01 or C's AH-08 personal three-diagram chains,
  and they do not supply the runtime Composite Structure Diagram.
