# B Personal Model Chain — Customer Intake, Clarification, and Session Lifecycle

> **MB-0.1 repository candidate, 2026-09-14.** Owner B (`ChengsiLi`), designated reviewer A (`shuxiachai`). WBS M-B.01–.06 and M-S.03; Jira [KAN-17](https://lucastaooo.atlassian.net/browse/KAN-17). Technical reference: F.01 rc.5 at [`3dd1ff637693a826990eee5712cfb239a3c3da7b`](https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b), [PR #11](https://github.com/shuxiachai/returnops-au/pull/11).
>
> **Scope:** Defines Member B's individually assessed model chain (`AH-01` → `UC-01` / `UC-01E` → Activity, Sequence, State Machine), resolving the personal modelling deliverables for Stage 1 (Criteria C8, C9, C10; 4.5 marks).

---

## 1. Source and Delivery Boundary

The individual model chain for Member B covers:
**`AH-01` → `UC-01` / `UC-01E` → Customer Intake Activity (`MB-ACT-0.1`) → Customer Portal Sequence (`MB-SEQ-0.1`) → IntakeSession State Machine (`MB-STM-0.1`)**.

The canonical ad hoc requirement `AH-01` states:
> *"Let me describe the return or product issue without navigating internal systems."*

Authoritative sources:
- [Project Definition v1.0](00-project-definition-v1.md) (§4.1 Customer Case Coordinator Agent, §10.2 Role allocations, §10.3 Model chains)
- [Frozen Work Allocation](07-frozen-work-allocation.md) (Member B: Frontend, Customer Portal, Founder Dashboard, 27% share)
- [Requirements & Use Case Specifications](05-lab-3-requirement-modelling.md) (§4.3 `UC-01`, §4.4 `UC-01E`)
- [Interface Contract v1.0 rc.5](09-interface-contract-v1.md) (§5 Public endpoint inventory, §10.4 History & Bounded Previews)
- [PR #8 Model Alignment & Disposition](reviews/pr8-alignment-disposition-20260914.md)

---

## 2. Requirements & Use Case Traceability

| ID | Title | Primary Actor | Role in Member B's Chain |
|---|---|---|---|
| `AH-01` | Simplified customer intake | End Customer | Primary user problem: frictionless submission without knowing merchant logistics or backend rules. |
| `UC-01` | Lodge a return/remedy request | End Customer | Main success scenario: intake submission, format validation, fact extraction, and case initiation. |
| `UC-01E` | Provide requested clarification or evidence | End Customer | Extension scenario: targeted clarification questions, multi-round evidence submission, and escalation guards. |
| `FR-001` | Natural-language customer intake | System | Enables raw text intake without pre-forcing rigid classification. |
| `FR-002` | Evidence attachment & validation | System | Multi-attachment staging, SHA-256 integrity, mime-type & size bounds. |
| `FR-005` | Dynamic targeted clarification | System | Generates questions strictly for missing or ambiguous facts; bounds clarification rounds. |
| `FR-011` | Immutable role-isolated audit | System | Customer statements are append-only; prior statements are never mutated. |

---

## 3. Activity Model (`MB-ACT-0.1`)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C8  

![Member B Activity Diagram](diagrams/member-b/member-b-activity.svg)

### 3.1 Overview and Responsibilities
The Activity Model traces the intake process across four distinct swimlanes:
1. **End Customer:** Originates problem statements, selects return categories, uploads photographic evidence, responds to clarification requests, or withdraws requests.
2. **Customer Portal (Next.js):** Performs immediate pre-flight client validation (message presence, file size <= 10MB, permitted MIME types) and manages staged uploads via `POST /v1/evidence`.
3. **API & Domain Service (FastAPI):** Authoritatively validates Bearer sessions, handles idempotency replays (`409 IDEMPOTENCY_CONFLICT` on body mismatches, cached response on match), registers `ReturnCase` and `IntakeSession`, and coordinates case progression.
4. **Coordinator Agent (AI Intake Role):** Executes non-authoritative natural-language fact extraction, identifying order references, return reasons, and evidence completeness.

### 3.2 Walkthrough of Execution Paths
- **Normal Flow (Steps B01–B14):** The customer submits a complete statement and evidence. The API confirms idempotency, persists `ReturnCase` (status `SUBMITTED`), logs `CustomerStatement` v1, and requests fact extraction. The Coordinator Agent verifies all mandatory facts. The Domain Service transitions the case to `UNDER_INVESTIGATION` and `IntakeSession` to `COMPLETE`, returning HTTP 201 Created with tracking details.
- **Clarification Extension Flow (Steps B15–B29, UC-01E):** If facts are missing or ambiguous, the case transitions to `AWAITING_INFORMATION` and `IntakeSession` to `AWAITING_CLARIFICATION`. A concurrency fork executes saving targeted questions while dispatching customer notifications via `NotificationPort`. The portal receives HTTP 202 Accepted and displays targeted inputs. When the customer replies, a new immutable statement (vN) is appended, the Coordinator Agent re-extracts facts, and the flow cleanly loops back for completeness re-evaluation.
- **Exception & Boundary Paths:**
  - *Client Validation Failure (B04b):* Caught immediately in UI; no invalid network requests sent.
  - *Idempotency Conflict (B07c):* Replay with modified body returns 409 without mutating state.
  - *Fact Extraction Failure (B11b):* Generates a `ProcessingFailure`; routes directly to manual triage (`MANUAL_HANDLING`).
  - *Customer Withdrawal (B19):* Customer can explicitly cancel; `IntakeSession` and `ReturnCase` transition to `CANCELLED`.
  - *Timeout Expiry (B20):* If 7 days elapse without customer reply, `IntakeSession` enters `TIMED_OUT`. Case remains safely frozen in `AWAITING_INFORMATION` without automated rejection.
  - *Exceeded Clarification Rounds (B23, B30):* If clarification attempts exceed 3 rounds, `IntakeSession` enters `ESCALATED_MAX_ROUNDS` and transfers to Founder triage via HTTP 202 Accepted (`status=ESCALATED`).

---

## 4. Interaction / Sequence Model (`MB-SEQ-0.1`)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C9  

![Member B Sequence Diagram](diagrams/member-b/member-b-sequence.svg)

### 4.1 Structural Lifelines and Message Dynamics
The Sequence Model coordinates 6 components:
- `Customer`: External human actor.
- `Customer Portal UI`: Next.js frontend managed by Member B.
- `Domain Service & API`: Sole authoritative state modifier.
- `Authoritative Store`: PostgreSQL persistence holding immutable revisions.
- `Coordinator Agent`: AI role providing intake fact extraction and question composition.
- `Notification Port`: Outbound mock communication adapter.

### 4.2 Key Invariants Verified in Sequence
1. **Pre-submission Staging:** Attachments are staged via `POST /v1/evidence` before case submission, generating isolated `evidence_id` tokens with SHA-256 hashes.
2. **Idempotency Guarantee:** Repeated clicks or network replays using the same `Idempotency-Key` return cached `CustomerCaseView` payloads without duplicating cases.
3. **Iterative Clarification Loop:** Formalised under `loop [Clarification Round 1..3 while facts incomplete]`. When clarification is provided, `CustomerStatement` v1 remains byte-identical; the reply is stored as `CustomerStatement` vN with incremented version. The loop models the successful resolution (`status=UNDER_INVESTIGATION`, `202 Accepted`), the iterative re-questioning branch (`round=round+1`, `202 Accepted`), and the exhaustion branch when round limit (3) is reached with facts still incomplete (`status=ESCALATED`, `202 Accepted`).
4. **Timeout & Inactivity:** If the 7-day timer expires without customer response, an internal DS timeout event transitions `IntakeSession` to `TIMED_OUT` and enqueues a safety notification.
5. **Clean Boundary Separation:** The Customer Portal communicates strictly through `/v1/cases` and `/v1/cases/{id}/clarifications`. It never accesses internal agent orchestrators, risk reviews, or provider execution ports.

---

## 5. State Machine Model (`MB-STM-0.1`)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C10  

![Member B State Machine Diagram](diagrams/member-b/member-b-state.svg)

### 5.1 Subject: `IntakeSession`
The state machine models the lifecycle of `IntakeSession`, the entity allocated to Member B under §10.3 and defined in the domain class model. `DRAFT` represents client-side session state before submission; persistent states are governed authoritatively in PostgreSQL.

### 5.2 States and Transition Table

| Current State | Event / Trigger | Guard | Action | Target State |
|---|---|---|---|---|
| `[*]` | User opens portal | — | `initialise_local_form()` | `DRAFT` |
| `DRAFT` | `submit_case` | Client validation passed | `POST /v1/cases`, `persist_statement(v1)` | `SUBMITTED` |
| `DRAFT` | `validation_error` | Missing text / invalid file | `show_client_error()` | `DRAFT` |
| `SUBMITTED` | `start_intake_eval` | Fresh case registered | `invoke_coordinator_agent()` | `EVALUATING` |
| `EVALUATING` | `eval_pass` | All mandatory facts verified | `advance_case(UNDER_INVESTIGATION)` | `COMPLETE` |
| `EVALUATING` | `eval_incomplete` | Missing facts, round < 3 | `generate_targeted_questions()`, `increment_round()`, `advance_case(AWAITING_INFORMATION)` | `AWAITING_CLARIFICATION` |
| `EVALUATING` | `eval_incomplete` | Missing facts, round >= 3 | `advance_case(ESCALATED)`, `notify_founder()` | `ESCALATED_MAX_ROUNDS` |
| `EVALUATING` | `eval_error` | Unrecoverable syntax/timeout | `create_processing_failure()`, `advance_case(ESCALATED)` | `ESCALATED_FAILURE` |
| `AWAITING_CLARIFICATION` | `validation_error` | Invalid clarification / file | `show_clarification_error()` | `AWAITING_CLARIFICATION` |
| `AWAITING_CLARIFICATION` | `submit_clarification`| Valid customer input | `POST /v1/cases/{id}/clarifications`, `append_statement(vN)` | `CLARIFICATION_RECEIVED` |
| `CLARIFICATION_RECEIVED` | `resume_eval` | — | `invoke_coordinator_agent()` | `EVALUATING` |
| `AWAITING_CLARIFICATION` | `timer_expired` | Inactivity > 7 days | `freeze_session()`, `notify_customer_timeout()` | `TIMED_OUT` |
| `AWAITING_CLARIFICATION` | `customer_withdraws`| Explicit cancellation | `cancel_case()`, `close_session()` | `CANCELLED` |
| `COMPLETE` | — | Terminal | Case proceeds to investigation | `[*]` |
| `ESCALATED_MAX_ROUNDS` | — | Terminal | Founder manual review | `[*]` |
| `ESCALATED_FAILURE` | — | Terminal | Founder manual review | `[*]` |
| `TIMED_OUT` | — | Terminal | Session archived | `[*]` |
| `CANCELLED` | — | Terminal | Case closed | `[*]` |

---

## 6. Key Architectural Choices and Discarded Alternatives

1. **Client-Side Validation vs Server-Side Authority:**
   - *Choice:* Next.js performs basic client-side format checks for UX responsiveness, but the FastAPI Domain Service authoritatively re-validates all payloads.
   - *Alternative Discarded:* Relying solely on client validation (security risk) or solely on server validation (poor UX latency).
2. **Clarification Handling (Interactive Chat vs Targeted Form):**
   - *Choice:* Targeted question form bound to specific missing facts.
   - *Alternative Discarded:* Open-ended conversational chatbot. A free-form chatbot introduces unpredictable hallucination risks, whereas structured targeted questions ensure verifiable compliance with Australian Consumer Law (ACL) criteria.
3. **Idempotency Strategy:**
   - *Choice:* Client-supplied UUID `Idempotency-Key` with payload hash verification.
   - *Alternative Discarded:* Database auto-increment deduplication, which cannot distinguish accidental double-clicks from intentional distinct submissions.

---

## 7. Review Dispositions and Design Consistency

- **CP-005 (Customer Statement Immutability):** Resolved. Customer statements are versioned (`version=1..N`). Clarifications append new records; earlier statements are never overwritten or mutated.
- **CP-007 (Targeted Clarification Bounds):** Resolved. Clarification questions target only missing mandatory facts. Multi-round clarifications are hard-capped at 3 rounds before triggering `ESCALATED_MAX_ROUNDS`.
- **CP-010 (Client Error vs Failure Distinction):** Resolved. Client-side input errors (file size/format) stop at `DRAFT`; server-side processing errors create traceable `ProcessingFailure` records without silently dropping requests.
- **PR #8 Model Alignment:** Incorporates the disposition in `docs/reviews/pr8-alignment-disposition-20260914.md`. Retains shared class model relationships while detailing the internal states of `IntakeSession`.

---

## 8. Viva & Oral Exam Defence Preparation

* **Q: Why does your model distinguish between `ReturnCase` status and `IntakeSession` status?**
  * **A:** `ReturnCase` tracks the overall macro-lifecycle of the dispute (from `SUBMITTED` through `AWAITING_INFORMATION`, `UNDER_INVESTIGATION` to `COMPLETED`/`REJECTED`). In contrast, `IntakeSession` is the micro-lifecycle of the customer interaction phase. Once intake qualification completes (either by fact sufficiency or escalation), `IntakeSession` enters a terminal state (`COMPLETE` or `ESCALATED_MAX_ROUNDS`), while `ReturnCase` moves into investigation and risk assessment.
* **Q: How does your UI prevent duplicate return requests if the customer clicks "Submit" multiple times?**
  * **A:** The portal generates a cryptographically random `Idempotency-Key` upon form initialisation. The Domain Service uses an atomic lookup-and-insert transaction: identical subsequent requests return the cached `CustomerCaseView` without spawning a new case or re-invoking the Assessment Agent.
* **Q: What happens if a customer never responds to clarification questions?**
  * **A:** Rather than executing an unfair automated rejection, `IntakeSession` transitions to `TIMED_OUT` after 7 days of inactivity. The case remains safely stored in `AWAITING_INFORMATION`, preserving the customer's initial statement and allowing manual customer support intervention if contacted.
* **Q: In your activity diagram and state machine, a customer can explicitly cancel or withdraw (`B19` / `CANCELLED`). Why is there no customer cancellation message in your sequence diagram?**
  * **A:** The sequence diagram strictly formalises the wire REST endpoints specified in our frozen team interface contract F.01 rc.5 (`docs/09-interface-contract-v1.md` §5). F.01 rc.5 defines public customer endpoints for evidence staging (`POST /v1/evidence`), case creation (`POST /v1/cases`), and clarifications (`POST /v1/cases/{id}/clarifications`), but omits a public customer cancellation endpoint. In our activity and state machine models, customer withdrawal is captured as an essential business domain event; when exposed over the wire in Stage 2, it will map to an explicit `DELETE /v1/cases/{id}` or `POST /v1/cases/{id}/withdraw` REST endpoint.
