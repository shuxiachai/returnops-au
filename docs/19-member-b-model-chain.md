# B Personal Model Chain — Customer Intake, Clarification, and Session Lifecycle

> **MB-0.2 compatibility candidate, 2026-09-14.** Owner B (Chengsi Li, `ChengsiLi`), designated reviewer A (`shuxiachai`). WBS M-B.01–.06; Jira [KAN-17](https://lucastaooo.atlassian.net/browse/KAN-17). Original B delivery: [PR #14](https://github.com/shuxiachai/returnops-au/pull/14), exact source [`92cd717a87a1aff745044342498d4caae196dc15`](https://github.com/shuxiachai/returnops-au/commit/92cd717a87a1aff745044342498d4caae196dc15), following B's `31fa250` model/report commit. Technical reference: F.01 rc.5 at [A `3dd1ff637693a826990eee5712cfb239a3c3da7b`](https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b).
>
> **Contribution boundary:** The original B files and authorship remain attributable to B. This revision is A-led, AI-assisted compatibility correction of that delivery; it is not B's independent revision, personal explanation, completed coursework or team acceptance. B must inspect, revise as needed and explain the resulting models. [The correction disposition](reviews/b-model-compatibility-disposition-20260914.md) separates original choices, corrections and pending acceptance. M-S.03 is a separate shared integration task and is not completed by listing it here.

## 1. Source and delivery boundary

The personal chain is **AH-01 → UC-01 / UC-01E → Customer Intake Activity (MB-ACT-0.2) → Portal Sequence (MB-SEQ-0.2) → case-owned IntakeSession state machine (MB-STM-0.2)**.

The canonical ad hoc requirement is: *“Let me describe the return or product issue without navigating internal systems.”*

Sources for the model are [project definition](00-project-definition-v1.md), [frozen allocation](07-frozen-work-allocation.md), [work packages](08-delivery-work-packages.md), [UC-01/UC-01E](05-lab-3-requirement-modelling.md), [F.01](09-interface-contract-v1.md), the [shared class model](diagrams/01-domain-class-diagram.md), and the [PR #8 disposition](reviews/pr8-alignment-disposition-20260914.md). The fifteen routes, shared DTOs, nine features and all WBS Owner/Reviewer/S/F fields remain unchanged.

B owns B1 customer intake/clarification, B2 Founder review UI, and B3 operational statistics (OF-006). The 27% allocation is planned effort, not a measured contribution, grade share or hours guarantee. Domain/Coordinator/Assessment remain A responsibilities; Risk/retrieval/image analysis remain C responsibilities. These diagrams focus on B1's boundary without claiming B implemented those other components.

## 2. Requirements and use-case traceability

| ID | Requirement / role in this chain |
|---|---|
| AH-01 | Customer describes an issue without navigating internal systems. |
| UC-01 | Lodge a statement with optional order reference, requested outcome and evidence. |
| UC-01E | Answer the current targeted clarification; accepted additional input stays in the same case. |
| FR-001 | Natural-language intake; original_message alone is mandatory and submission is idempotent. |
| FR-002 | Extract typed facts while distinguishing missing, ambiguous, conflicting and not-applicable information; do not invent facts. Attachment transport is not the definition of FR-002. |
| FR-005 | Criterion-level evidence assessment and relevant questions; reasonable proof-of-purchase alternatives remain available. |
| FR-011 | Reconstructable case/audit history; accepted source statements cannot be overwritten by normalisation. F.07 retention still applies. |
| NFR-003 / NFR-008 / NFR-009 | Privacy, usable error/clarification handling and untrusted-input boundaries, as mapped by UC-01E. |

M-B.02 is the Activity, M-B.03 is the Sequence, and **M-B.04** is the IntakeSession state machine. Their existence supports review preparation; M-B.05 consistency review and M-B.06 personal explanation require their own evidence and original dependencies.

## 3. Activity model (MB-ACT-0.2 / C8)

![Member B Activity Diagram](diagrams/member-b/member-b-activity.svg)

The four lanes separate Customer, B's Portal, A's API/Domain and A's non-authoritative Coordinator. The model is a planned execution specification, not a running implementation.

- **B01–B09 — admission:** Customers compose the original message with optional fields. Local checks improve feedback; the server independently verifies identity, role, payload, actual file format/size and idempotency. JPEG/PNG/PDF, 10 MiB per file and at most ten evidence references are F.01 technical limits. Creation atomically binds available owned STAGED evidence, the case/session, original statement, receipt and accepted intake work. HTTP 201 confirms that commit; it does not promise completed AI processing.
- **B10–B15 — accepted processing:** Coordinator returns a typed CoordinatorResult. Domain verifies the current case/input/work and original statement reference, discards obsolete results, and performs only bounded recovery for actual processing errors. Sufficient mandatory facts lead to UNDER_INVESTIGATION and the end of this intake episode.
- **B16–B18 — missing facts:** Domain stores remaining questions and AWAITING_INFORMATION before notification dispatch. Delivery failure cannot roll back the accepted input, create duplicate intake or imply a business rejection. CustomerCaseView exposes the current clarification for the UI to render.
- **B19 — leaving the UI:** Closing or pausing IntakeViewSession is local. No durable case is rejected, cancelled, withdrawn, archived or deleted by this action. Reopening reads the authorised current case.
- **B20–B25 — repeat UC-01E:** A fresh clarification must match the case owner, AWAITING_INFORMATION, expected_case_version, current question_set_id and requested answers/evidence. Domain atomically appends accepted input, binds evidence, advances case/input versions and invalidates stale derived authority. HTTP 202 denotes acceptance. Re-evaluation can return to the same missing-information branch after three or more rounds.

**Real failure boundary:** Initial intake or an accepted clarification can suffer an actual current COORDINATOR processing failure. Only after bounded recovery is exhausted may Domain persist the real ProcessingFailure and follow F.01 escalation guards. With no current proposal, an ESCALATED Founder view requires exactly one current ProcessingFailure or OrderLookupBlock. This flow supplies a real failure; it does not fabricate an order block. If a current proposal exists, its target/history remain governed by F.01. Escalation does not itself record MANUAL_HANDLING: a later authenticated Founder must decide against the applicable exact target. No approval or return/label command is produced by this intake flow.

## 4. Sequence model (MB-SEQ-0.2 / C9)

![Member B Sequence Diagram](diagrams/member-b/member-b-sequence.svg)

The SVG contains two explicitly framed independent interaction definitions, each with its own title and fresh lifelines. Definition 1, sd CustomerIntake, contains flows 1/2/4 and invokes ProcessAcceptedIntake only through ref fragments in the fresh-acceptance branches. Definition 2, sd ProcessAcceptedIntake, contains flow 3 and states its accepted-work precondition. Its messages do not continue the trace after definition 1 or after replay/rejection. Both rendered pages are included in the single linked SVG; neither is omitted. The six lifelines identify Customer, Portal, Domain, Store, Coordinator and NotificationPort.

The sequence makes the following consumer rules explicit:

1. **Evidence:** Every upload has Bearer authentication and its own scoped Idempotency-Key; only returned evidence IDs enter a case or clarification request. STAGED files are private to their uploader and become case input only through an accepted atomic bind. C receives authorised evidence references through A's bounded internal port, never UI credentials or arbitrary URLs.
2. **Accepted replay:** Authenticate and validate first, then look up principal + method/route + target + key. Identical accepted requests return their original receipt only while every part remains readable. Changed content returns 409 IDEMPOTENCY_CONFLICT. Removed receipt content returns 409 INVALID_STATE with retryable=false and no original body, new input or new work. The UI must not silently change keys; an uncertain response is recovered with the original key and request.
3. **Fresh intent:** Only a new intent reaches the current state/version/question guards. A replay is not rejected merely because the case has since advanced, and is not permission to append to an obsolete question set. A version conflict requires reload and customer confirmation of a new intent.
4. **Current views:** A replayed CustomerCaseView is historical. The UI GETs the authorised current view and renders clarification.questions, case_version and collection_windows. Customer views never expose internal proposal, review, failure details, approval or provider credentials. History paging starts from the relevant collection window's start_cursor, not the preview tail; retained tombstones do not resurrect old content.
5. **Statement identity:** CustomerStatement uses statement_id, kind, raw_text and submitted_at (plus permitted optional fields). ORIGINAL/CLARIFICATION records are appended rather than overwritten. The earlier v1/vN shorthand is not a wire version field; case_version, input_version and historical revision metadata are separate concepts.
6. **Question semantics:** CoordinatorResult carries typed facts, evidence_matrix, questions and exact source references. The HTTP response uses CustomerCaseView.clarification, not a new top-level questions field. IssueCategory uses the frozen values rather than an invented DAMAGED_ITEM enum.

Response snippets in the figure name DTOs and relevant properties; they are not complete JSON fixtures. [The schemas and examples](../contracts/README.md) remain authoritative for required fields. Auth, schema and business admission errors use the existing safe correlated ErrorEnvelope. Admission failure is not a ProcessingFailure. No service, database schema or public API is implemented here.

## 5. State machine (MB-STM-0.2 / C10)

![Member B State Machine Diagram](diagrams/member-b/member-b-state.svg)

### 5.1 Subject and mapping

The subject remains the **durable, case-owned IntakeSession** required by M-B.04 and the shared ReturnCase composition. Its existing lifecycle_state string and clarification_round are refined conceptually by this candidate; these labels are not a new public enum or DTO. A separate **IntakeViewSession** names the UI-only form/view/controller: local DRAFT, pending/error display, closing and reopening. That UI helper neither replaces the shared entity nor owns ReturnCase transitions.

A durable session starts only after accepted case creation. COMPLETE and ESCALATED_FAILURE are quiescent states of that same object, not UML finals: the case continues through investigation or exact-target handling. G-REENTRY requires Domain to have already committed an existing legal shared-case transition to AWAITING_INFORMATION with a current case/input-bound ClarificationSet and all source/state/effect/authority guards satisfied. Examples are a correctable investigation gap, an assessment gap or current NEEDS_INFORMATION review. From ESCALATED_FAILURE, re-entry additionally requires lawful proposal-bound Founder REQUEST_REVISION followed by the existing assessment-gap transition; a no-proposal failure has no restart/revision/re-entry path. Browser reopening cannot create any of these transitions. Only G-TERMINAL, where authoritative ReturnCase is COMPLETED, REJECTED or MANUAL_HANDLED, reaches the UML final; permitted persisted records remain governed by F.07. This figure does not claim a new session persistence implementation or shared-model adoption.

### 5.2 Transition summary

| From | Event and guard | Domain action / destination |
|---|---|---|
| Initial | Fresh creation atomically committed | Create the case-owned session → SUBMITTED. |
| SUBMITTED | Selected current intake work starts | Invoke Coordinator → EVALUATING. |
| EVALUATING | Recoverable real error and recovery budget remains | Retry selected work; remain EVALUATING without duplicate customer input. |
| EVALUATING | Obsolete case/input/work result | Discard it without overwriting current facts. |
| EVALUATING | Valid current result, sufficient mandatory facts | Persist and hand to investigation → COMPLETE. |
| EVALUATING | Valid current result, remaining missing/ambiguous facts | Persist targeted questions; case AWAITING_INFORMATION → AWAITING_CLARIFICATION. No round-limit guard. |
| EVALUATING | Current actual processing error, recovery exhausted, legal target | Persist ProcessingFailure and guarded escalation → ESCALATED_FAILURE. No automatic Founder decision. |
| AWAITING_CLARIFICATION | No response, UI closed, or fresh clarification rejected | No accepted-input transition; retain current case. Return safe errors for rejected requests. |
| AWAITING_CLARIFICATION | Fresh owner request matches current state, question set and version | Atomic append/bind/version advance → CLARIFICATION_RECEIVED. |
| CLARIFICATION_RECEIVED | Selected current input work starts | Evaluate newly accepted input → EVALUATING. |
| COMPLETE | Domain commits current questions under G-REENTRY | Re-enter AWAITING_CLARIFICATION in the same durable session; no new case or UI authority. |
| ESCALATED_FAILURE | G-REENTRY after lawful proposal-bound recovery | Re-enter AWAITING_CLARIFICATION; no-proposal failure cannot satisfy this path. |
| COMPLETE / ESCALATED_FAILURE | Authoritative case terminal under G-TERMINAL | End session behavior; retain records as permitted by F.07. |
| Any state | Previously accepted POST replay | No new state transition or work; apply auth and receipt-retention rules. |

## 6. Choices and unapproved extensions

Client format checks and targeted forms improve usability; Domain remains responsible for trusted validation. Clarification supports relevant proof alternatives and explicit uncertainty; a structured form does not establish legal compliance or final entitlement.

A stable key belongs to one logical request and its original payload, rather than all future form submissions. It supports safe uncertain retries; deliberate changed input becomes a new intent only after resolving any accepted prior request and current view conflicts.

B's original three-round cap and seven-day archival timer lack an adopted F.01/UC-01E policy and are not active transitions in MB-0.2. Missing facts stay AWAITING_INFORMATION; customer silence is not a technical failure. A future interaction budget, reminder or expiry policy needs explicit design/retention review and approval before it can alter behavior. No numeric business deadline is approved by this model.

**Business withdrawal is an unapproved extension.** The fifteen-route contract has no customer cancellation/withdrawal operation. Leaving the UI preserves the server case and is not a Founder REJECT. This candidate makes no Stage 2 promise to add DELETE or a withdraw route; any such change requires the existing scope/interface approval process.

## 7. Disposition and evidence status

The original CP-005/007/010 labels are retained as B's review references, not asserted to be accepted global dispositions. This correction preserves original-statement identity subject to F.07; replaces the unsupported round-limit escalation with repeatable UC-01E; and separates client/request errors from actual accepted processing failure. The PR #8 disposition still applies: shared-model alignment is not sole B authorship or acceptance of a separate IntakeStatus design.

The [compatibility disposition](reviews/b-model-compatibility-disposition-20260914.md) records exact changed scope, static walkthroughs and actual validation commands. Source/render checks and contract tests are design evidence only, not a UI/API implementation, running transaction proof, personal contribution completion, F.01/F.02 acceptance or shared M-S.03 delivery.

## 8. Personal explanation prompts for B

These are preparation prompts with candidate rationale, not first-person statements already made by B.

- Explain why IntakeSession belongs to ReturnCase while IntakeViewSession is local; closing a page does not reject the case.
- Walk a fourth incomplete clarification through all three figures. Identify the persisted current question set and explain why no ProcessingFailure or MANUAL_HANDLING target can be invented.
- Walk an actual failure after an accepted clarification. Identify the current input, bounded recovery and the exact Founder target; distinguish an HTTP admission error.
- Show why replay is checked before fresh state/version admission, why deleted receipt content returns INVALID_STATE and why a new key is not automatic recovery.
- Demonstrate statement IDs/kinds, the current ClarificationSet and case/input versions without inventing wire fields.
- Record B's own substantive revisions, source commits and explanation, disclose A/AI assistance, and identify what remains planned or shared. A Git history entry alone is not proof of independent work.


## 9. Rendering both sequence definitions without losing a page

PlantUML `newpage` emits two images for this source; this follows the [official sequence rendering syntax](https://plantuml.com/sequence-diagram). Each page has an independent sd frame and title. Render the sequence into a temporary directory (here `tmp/b-compatibility-qa/formal-review-fix`) using the existing PlantUML command with `-tsvg -charset UTF-8 -o <absolute-output-directory>`. The expected files are `member-b-sequence.svg` and `member-b-sequence_001.svg`. A direct copy of only the first image would lose the ProcessAcceptedIntake definition and is not the delivered figure.

Run the following Python assembly from the repository root after rendering. It keeps both unscaled SVG viewports, separates their frames by 80 pixels, makes element IDs unique and retains each page's complete PlantUML source metadata. This is vector assembly, not a change to the interaction. Re-render a PNG of the assembled SVG for layout inspection and run the existing static source-correspondence checker. Temporary raw pages and `sequence-assembly.json` are preserved with this correction's local evidence.

```python
from pathlib import Path
import re
import xml.etree.ElementTree as ET

qa = Path("tmp/b-compatibility-qa/formal-review-fix")
pages = []
for number, name in enumerate(("member-b-sequence.svg", "member-b-sequence_001.svg"), 1):
    raw = (qa / name).read_text(encoding="utf-8")
    node = ET.fromstring(raw)
    width, height = map(int, node.attrib["viewBox"].split()[2:])
    for old in sorted(set(re.findall(r'\sid="([^\"]+)"', raw)), key=len, reverse=True):
        new = f"page{number}-{old}"
        raw = raw.replace(f' id="{old}"', f' id="{new}"')
        raw = raw.replace(f"url(#{old})", f"url(#{new})")
        raw = raw.replace(f'href="#{old}"', f'href="#{new}"')
    pages.append((raw, width, height))
width = max(page[1] for page in pages)
height = sum(page[2] for page in pages) + 80
parts, y = [], 0
for raw, w, h in pages:
    parts.append(raw.replace("<svg ", f'<svg x="{(width-w)//2}" y="{y}" ', 1))
    y += h + 80
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}px" '
       f'height="{height}px" viewBox="0 0 {width} {height}">'
       '<title>Two independent sequence interactions: CustomerIntake and ProcessAcceptedIntake</title>'
       '<rect width="100%" height="100%" fill="white"/>' + "".join(parts) + "</svg>\n")
ET.fromstring(svg)
Path("docs/diagrams/member-b/member-b-sequence.svg").write_text(svg, encoding="utf-8")
```
