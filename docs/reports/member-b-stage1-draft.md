# Member B — Stage 1 Report and Explanation Draft

> **Candidate Reference (2026-09-14):** Prepared for Member B (`ChengsiLi`, @ChengsiLi) for inclusion in the Stage 1 final report and individual defence. WBS M-B.01–.06 and M-S.03; Jira [KAN-17](https://lucastaooo.atlassian.net/browse/KAN-17).
>
> **Scope:** Provides the complete draft for Member B's report contributions: personal requirement modelling (`AH-01` → `UC-01` / `UC-01E`), behavioural models (Activity, Sequence, State Machine; Criteria C8–C10), frontend interface boundaries, and oral defence rationale.

---

## 1. Role, Ownership, and Assessed Contribution

Under the group work allocation (§10.1, §10.2):
- **Role:** Member B — Frontend, UX, Customer Portal, and Founder Dashboard (27% workload share).
- **Personal Ad Hoc Requirement:** `AH-01` — *"Let me describe the return or product issue without navigating internal systems."*
- **Primary Use Cases:** `UC-01` (Lodge a return/remedy request) and `UC-01E` (Provide requested clarification or evidence).
- **Individually Assessed Models (4.5 marks):**
  1. *Activity Diagram:* Customer Request Submission & Clarification (`MB-ACT-0.1`, Criterion C8, 1.5 marks)
  2. *Sequence Diagram:* Customer Portal Submission & Clarification (`MB-SEQ-0.1`, Criterion C9, 1.5 marks)
  3. *State Machine Diagram:* `IntakeSession` Lifecycle (`MB-STM-0.1`, Criterion C10, 1.5 marks)
- **Shared Deliverable Contributions:**
  - `UC-01` and `UC-01E` formal specifications (Report §4).
  - Use Case overall diagram alignment (Report §4).
  - Design-time class model intake entities (`IntakeSession`, `CustomerStatement`, `EvidenceAttachment`).
  - Frontend consumption boundaries for Founder and Customer views.

---

## 2. Personal Requirement and Use Case Specification

### 2.1 Ad Hoc Requirement `AH-01`
Traditional e-commerce return processes force users through rigid multi-tiered category trees, demanding precise merchant policy knowledge before a claim can even be registered. `AH-01` shifts this cognitive burden to the AI intake pipeline:
- The customer expresses the grievance in natural language, attaching supporting images or receipts.
- The system accepts free-form text while safely extracting typed structured facts (`FR-001`).

### 2.2 Use Case `UC-01` & Extension `UC-01E`
- **Main Goal (`UC-01`):** Accept customer statement and optional evidence, validate basic format constraints, assign a permanent Case ID, and initiate qualification.
- **Clarification Extension (`UC-01E`):** When facts are insufficient or contradictory (e.g., missing order number or ambiguous fault description), the system generates targeted clarification questions rather than rejecting the case.
- **Append-only Preservation (`FR-011`):** Subsequent statements are appended with incremented versions (`CustomerStatement` v1, v2, ...); the original customer statement is never overwritten or mutated.

---

## 3. Behavioural Modelling Analysis

### 3.1 Activity Model (Criterion C8)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C8  

![Member B Activity Diagram](../diagrams/member-b/member-b-activity.svg)

The activity model separates user interaction from authoritative system state across four swimlanes:
- **Client Pre-flight Validation:** File size and MIME checks occur locally in Next.js to prevent unnecessary server load.
- **Atomic Registration:** The API handles idempotency checking before writing state.
- **Concurrent Notification & Question Persistence:** Fork/join executes simultaneous DB question persistence and customer notification dispatch.
- **Targeted Questioning Loop:** If mandatory facts are incomplete, `UC-01E` triggers a bounded clarification flow that loops back into fact evaluation.
- **Escalation Bounds:** Exceeding 3 clarification rounds transitions the session to `ESCALATED_MAX_ROUNDS` for manual Founder intervention, preventing endless automated loops.

### 3.2 Interaction Sequence Model (Criterion C9)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C9  

![Member B Sequence Diagram](../diagrams/member-b/member-b-sequence.svg)

The sequence model formalises the API and component interactions across three distinct phases:
- **Evidence Staging:** Files are uploaded via `POST /v1/evidence` to establish validated hashes before case submission.
- **Idempotency Guarantees:** Replaying a request with the same `Idempotency-Key` and identical body returns the cached `CustomerCaseView`, preventing accidental duplicate dispute creation.
- **Iterative Clarification Loop:** Modelled as `loop [Clarification Round 1..3 while facts incomplete]`, linking new evidence and statements to the existing case entity without resetting prior statements.
- **Timeout Exception Path:** Models the background timer expiration after 7 days of inactivity, safely archiving the session.

### 3.3 State Machine Model (Criterion C10)

> **Owner**: Member B (Chengsi Li, @ChengsiLi)  
> **Chain**: AH-01 → UC-01 / UC-01E → this diagram  
> **Criterion**: C10  

![Member B State Machine Diagram](../diagrams/member-b/member-b-state.svg)

The state machine tracks the dedicated lifecycle of `IntakeSession`:
- **States:** `DRAFT` → `SUBMITTED` → `EVALUATING` → `AWAITING_CLARIFICATION` → `CLARIFICATION_RECEIVED` → `COMPLETE`.
- **Exception Terminals:** `TIMED_OUT` (inactivity > 7 days), `CANCELLED` (customer withdraws), `ESCALATED_MAX_ROUNDS` (round >= 3 exhausted), and `ESCALATED_FAILURE` (unrecoverable AI processing failure).
- **Design Independence:** By isolating `IntakeSession` from the global `ReturnCase` state machine, the intake phase remains decoupled from backend risk evaluation, merchant approval, and provider execution.

---

## 4. Key Architectural Choices and Discarded Alternatives

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

## 5. Defence and Examiner Preparation (Interview Preparation)

- **Q: How does your UI prevent untrusted customer input from compromising the backend?**
  - **A:** Customer statements and attachments are treated as untrusted data. Attachments are validated against strict MIME and size limits (10MB), stored in an isolated bucket, and accessed by downstream agents only via sanitised text representations and structured fact DTOs.
- **Q: Why are clarification rounds capped at 3?**
  - **A:** To prevent customer frustration and unbounded AI token consumption. If a customer cannot supply the necessary proof in 3 rounds, automated qualification has failed, and human compassion/judgement (Founder triage) is required.
- **Q: How do you demonstrate that your diagrams were created independently?**
  - **A:** The models strictly reflect my allocated ad hoc requirement (`AH-01`) and use cases (`UC-01`/`UC-01E`), modelling the exact boundary between the Customer Portal (which I own) and the Domain Service API, with full git commit history on my dedicated branch.
- **Q: In your activity diagram and state machine, a customer can explicitly cancel or withdraw (`B19` / `CANCELLED`). Why is there no customer cancellation message in your sequence diagram?**
  - **A:** The sequence diagram strictly formalises the wire REST endpoints specified in our frozen team interface contract F.01 rc.5 (`docs/09-interface-contract-v1.md` §5). F.01 rc.5 defines public customer endpoints for evidence staging (`POST /v1/evidence`), case creation (`POST /v1/cases`), and clarifications (`POST /v1/cases/{id}/clarifications`), but omits a public customer cancellation endpoint. In our activity and state machine models, customer withdrawal is captured as an essential business domain event; when exposed over the wire in Stage 2, it will map to an explicit `DELETE /v1/cases/{id}` or `POST /v1/cases/{id}/withdraw` REST endpoint.
