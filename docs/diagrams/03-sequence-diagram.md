# Sequence Diagram - Multi-Agent Governed Execution

> **MBSE model type**: Dynamic behavioural sequence diagram
>
> **Course requirement**: Agent collaboration, normal and failure paths,
> human-in-the-loop authority, and typed tool invocation
>
> **Traceability**:
> [FR-001 to FR-012; NFR-001 to NFR-009](../04-requirements-and-backlog.md)

## 1. Mermaid sequence model

```mermaid
sequenceDiagram
    autonumber
    actor Customer
    actor Founder as Authorised Founder
    participant Portal as Customer Portal
    participant Dashboard as Founder Dashboard
    participant API as ReturnOps API
    participant Domain as Domain Service
    participant Coordinator as Customer Case Coordinator Agent
    participant Assessment as Returns Assessment Agent
    participant Reviewer as Compliance & Risk Reviewer Agent
    participant Guard as Approval Guard
    participant Ops as Deterministic Operations Service
    participant Order as Mock Order Provider
    participant Corpus as Versioned Policy Corpus
    participant Logistics as Mock Returns and Logistics Provider
    participant Notify as Mock Notification Provider
    participant DB as Case and Audit Store

    Note over Assessment: One lifeline. The superseded Order, Evidence, Policy and Remedy roles
    Note over Assessment: are all responsibilities of this single agent under definition section 4.2

    Customer->>Portal: Submit return/remedy request
    Portal->>API: Create case with message, order ID, and evidence metadata
    API->>DB: Persist original statement and SUBMITTED case
    API->>Domain: Start intake for case ID
    Domain->>Coordinator: Extract typed facts and missing fields
    Coordinator-->>Domain: Facts, confidence, and open questions

    alt Mandatory information missing
        Domain->>DB: Set AWAITING_INFORMATION and append audit event
        Domain->>Coordinator: Compose targeted clarification request
        Coordinator->>Portal: Send targeted information request
        Portal-->>Customer: Request only missing facts/evidence
    else Minimum information present
        Domain->>DB: Set UNDER_INVESTIGATION
        Domain->>Assessment: Verify order through provider interface
        Assessment->>Order: Query read-only order snapshot

        alt Provider failure below retry limit
            Order-->>Assessment: Typed timeout/provider failure
            Assessment-->>Domain: No snapshot, safe retry requested
            Domain->>DB: Keep authoritative state, audit retry count
        else Provider retry limit reached
            Order-->>Assessment: Repeated typed provider failure
            Assessment-->>Domain: Retry limit reached, no snapshot invented
            Domain->>DB: Set ESCALATED with provider-failure reason
            Domain-->>Founder: Manual handling packet with failure history
        else Order identifier missing or plausibly mistyped
            Order-->>Assessment: Not found with no confirmed mismatch
            Assessment-->>Domain: Clarification required
            Domain->>DB: Set AWAITING_INFORMATION
            Domain->>Coordinator: Compose targeted clarification request
            Coordinator->>Portal: Send order-correction question
            Portal-->>Customer: Request corrected order detail
        else Confirmed order/customer conflict
            Order-->>Assessment: Conflicting verified facts
            Assessment-->>Domain: Confirmed conflict risk
            Domain->>DB: Set ESCALATED with both fact sources
            Domain-->>Founder: Manual handling packet
        else Order matched
            Order-->>Assessment: Versioned read-only OrderSnapshot
            Assessment-->>Domain: Verified order and affected line item
            Domain->>DB: Set POLICY_ASSESSMENT and append order-match event
            Domain->>Assessment: Assess required, present, missing, and conflicting evidence
            Assessment-->>Domain: Versioned EvidenceAssessment matrix with source references

            alt Required diagnostic evidence is missing
                Domain->>DB: Set AWAITING_INFORMATION with explicit evidence gaps
                Domain->>Coordinator: Compose targeted clarification request
                Coordinator->>Portal: Send targeted diagnostic-evidence questions
                Portal-->>Customer: Request only the missing diagnostic evidence
            else Evidence assessment is ready
                Domain->>Assessment: Retrieve approved grounding
                Assessment->>Corpus: Query versioned store-policy and guidance corpus
                Corpus-->>Assessment: Passages with source, version, and location
                Assessment-->>Domain: Cited passages and source-conflict flags
                Domain->>Assessment: Draft non-executable typed proposal
                Assessment-->>Domain: Proposal version, alternatives, confidence, and questions
                Domain->>Reviewer: Verify evidence, citations, conflicts, and untrusted content

                alt Source conflict, unsupported claim, injection, or unresolved high risk
                    Reviewer-->>Domain: Escalate with findings and preserved sources
                    Domain->>DB: Set ESCALATED and append review evidence
                    Domain-->>Founder: Manual handling packet, no approval request
                else Independent review passes
                    Reviewer-->>Domain: Pass for current proposal version
                    Domain->>DB: Set AWAITING_APPROVAL
                    Domain-->>Dashboard: Present current proposal, evidence, citations, and risks
                    Dashboard-->>Founder: Render proposal, evidence, citations, and risks
                    Founder->>Dashboard: Approve exact action plan for current proposal
                    Dashboard->>API: Submit trusted session, proposal version, commands, amount, reason, expiry
                    API->>Guard: Validate actor, role, state, case, proposal, scope, amount, expiry
                    Guard->>DB: Load authoritative proposal, approval state, and allowlist
                    DB-->>Guard: Current records
                    Guard-->>API: Exact-scope approval is valid
                    API->>DB: Append immutable ApprovalRecord, set APPROVED, append audit event
                    API->>Domain: Resume with trusted approval reference
                    Domain->>Ops: Dispatch approved plan with trusted approval reference
                    Ops->>Guard: Revalidate case, proposal, command set, amount, expiry, and allowlist

                    alt Dispatch guard is invalid or stale
                        Guard-->>Ops: Block before every provider call
                        Ops->>DB: Keep APPROVED and append BLOCKED_NO_APPROVAL security event
                        Ops-->>Founder: Show exact blocking reason
                    else Complete dispatch guard passes
                        Guard-->>Ops: Exact approved plan may enter execution
                        Ops->>DB: Set ACTION_IN_PROGRESS and append dispatch audit event

                        loop Each approved command in dependency order while ACTION_IN_PROGRESS
                            Ops->>DB: Load prior result for command and stable idempotency key
                            DB-->>Ops: Prior success or unfinished status

                            alt Prior successful result exists
                                Ops->>DB: Reuse stored result and audit skipped duplicate call
                            else Command remains unfinished
                                Ops->>Guard: Validate exact command, parameters, approval, and key
                                Guard-->>Ops: Command remains allowlisted and exactly approved

                                alt Command is CREATE_RETURN
                                    Ops->>Logistics: Invoke CREATE_RETURN with stable key
                                    Logistics-->>Ops: Success result or typed provider failure
                                else Command is GENERATE_LABEL
                                    Ops->>Logistics: Invoke GENERATE_LABEL with stable key
                                    Logistics-->>Ops: Success result or typed provider failure
                                end

                                alt Provider reports success
                                    Ops->>DB: Persist successful result before next command
                                else Provider timeout or typed failure
                                    Ops->>DB: Set ACTION_FAILED with command, key, and failure
                                    loop Safe retry remains and case is not escalated
                                        Ops->>Guard: Revalidate same approval, command, and key
                                        Guard-->>Ops: Retry remains exact-scope and allowlisted
                                        alt Failed command is CREATE_RETURN
                                            Ops->>Logistics: Retry only CREATE_RETURN with the same key
                                            Logistics-->>Ops: Typed retry result
                                        else Failed command is GENERATE_LABEL
                                            Ops->>Logistics: Retry only GENERATE_LABEL with the same key
                                            Logistics-->>Ops: Typed retry result
                                        end
                                        Ops->>DB: Persist each retry result without repeating prior success
                                    end
                                    alt Retry eventually succeeds
                                        Ops->>DB: Persist success and restore ACTION_IN_PROGRESS
                                    else Retry limit reached
                                        Ops-->>Domain: Escalate with completed and failed command results
                                        Domain->>DB: Set ESCALATED, preserve all prior successful results
                                        Domain-->>Founder: Manual recovery packet
                                    end
                                end
                            end
                        end

                        Ops->>DB: Check every approved command has one successful result
                        DB-->>Ops: Complete or incomplete plan status
                        opt All approved commands are complete and case is not escalated
                            Ops-->>Domain: Approved action plan complete once
                            Domain->>DB: Set RESOLVED
                            Domain->>Ops: Send approved outcome and next-step notification
                            Ops->>Notify: Send approved outcome and return instructions

                            alt Notification delivered
                                Notify-->>Customer: Approved next step and simulated label
                                Notify-->>Ops: Delivery result
                                Ops-->>Domain: Delivery result
                                Domain->>DB: Append delivery event and set CLOSED
                            else Notification failure
                                Notify-->>Ops: Typed delivery failure
                                Ops-->>Domain: Typed delivery failure
                                Domain->>DB: Keep RESOLVED and schedule notification-only retry
                            end
                        end
                    end
                end
            end
        end
    end
```

## 2. Architectural checks demonstrated

1. **Uncertainty is a normal branch**: missing facts, order/provider failure,
   source conflict, unsupported claims, and prompt injection do not fall through
   to approval.
2. **Human authority is exact**: the trusted founder approves the current
   proposal and explicit command set with applicable amount and expiry.
3. **Dispatch revalidates authority**: every typed command is checked against
   case, proposal, approval, allowlist, scope, and idempotency key before use.
4. **Partial and repeated work is safe**: results persist per command, retries
   reuse the same key, and a prior success is never executed again.
5. **Notification is independent**: message retry cannot repeat a remedy, and a
   delivery failure leaves the completed operation visible in `RESOLVED`.
