# 35 — Member B: Interactive Demo Walkthrough & Automated UI Test Fixtures

**Deliverable ID:** `B2.05` / `KAN-20` (also fulfilling `B1.05` & `B3.03`)  
**Package:** B2 Founder Review UI & B1 Customer Intake  
**Owner:** Member B (`@ChengsiLi` / `banana`, 27% effort share)  
**Reviewer:** Member A (`@shuxiachai`)  
**Standard:** Stage 2 Milestone Baseline · Australian Consumer Law (ACL Section 54) · Kruchten P01 Untrusted Client Boundary

---

## 1. Executive Summary

This document specifies the deterministic demonstration fixtures, automated UI regression suite, and a choreographed 3-minute in-class demonstration script for Member B's web frontend (`returnops-au/apps/web`).

The frontend operates strictly as an untrusted client in Kruchten's 4+1 package decomposition (P01), delegating domain state transitions, statutory policy evaluations, and cryptographic audit recording to the backend gateway (P02) and core domain (P04). It supports transparent dual-mode execution:
1. **Offline Mock Mode (Default)**: Zero-setup deterministic demo fixtures for resilient live presentation without external network dependency.
2. **Live API Mode**: Reads are issued against the configured API base URL (`VITE_API_BASE_URL`; empty prefix by default, so requests go through the Vite dev-server proxy to the FastAPI gateway). Only operations that actually exist on current backend `main` are served. Founder decision recording (`POST /v1/founder/cases/{id}/decisions`) and Founder analytics (`GET /v1/founder/analytics`) are **planned** contracts with no registered runtime endpoint, so the live client refuses them with an explicit `501 NOT_IMPLEMENTED` gate and both UI surfaces disable the action and instruct the operator to switch to Mock Mode.

> **Current implementation status (must stay accurate).** The frontend is a mock-first prototype: the deterministic fixture store backs every screen. Live reads are implemented for the operations listed in the root `README.md`; live writes beyond case creation and staged uploads are gated as above. This document does not claim a complete live backend integration.

---

## 2. Deterministic Demo Fixtures Map

The offline mock store in `apps/web/src/api/mockData.ts` provides 5 curated lifecycle cases (`case_demo_001`–`005`) that exhibit all major statutory and governance branches, plus 20 generated summary rows (`case_demo_006`–`025`) so that queue pagination and the page-size boundary can be demonstrated.

| Case ID | Status | Category | Statutory Grounding & Risk | Key Interactive Feature |
|---|---|---|---|---|
| `case_demo_001` | `AWAITING_INFORMATION` | `WRONG_ITEM` | Risk: `NEEDS_INFORMATION` · Sydney fulfilment picking mismatch | **Targeted Clarification (`UC-01E`)**: Renders barcode & parcel integrity questions; submits answer with optimistic locking `expected_case_version: 2`; moves to `UNDER_INVESTIGATION`. |
| `case_demo_002` | `RISK_REVIEW` | `FAULTY_OR_QUALITY_ISSUE` | Risk: `PASS_WITH_WARNING` · Ceramic teapot shattered in transit | **ACL Section 54 Guarantee**: Shows statutory safety exception (§4.2) where return shipping is waived; displays photo evidence preview. |
| `case_demo_003` | `AWAITING_APPROVAL` | `CHANGE_OF_MIND` | Risk: `PASS` · 30-day policy applicable | **Double Approval Guard (`UC-04`)**: Displays governed action preview (`prev_demo_003` + `scope_fingerprint`); allows Founder Approval with mandatory rationale. |
| `case_demo_004` | `ESCALATED` | `OUT_OF_SCOPE` | Risk: `ESCALATE` · Commercial misuse claim | **Hard Block on Direct Approval**: Direct approval disabled; forces Founder Manual Handling or formal rejection. |
| `case_demo_005` | `COMPLETED` | `FAULTY_OR_QUALITY_ISSUE` | Risk: `PASS` · Terminal state | **Audit History (`UC-05`)**: Demonstrates complete lifecycle closure and the recorded SHA-256 hash pointer fields (a demo indicator; the chain is not recomputed). |

---

## 3. Choreographed 3-Minute Live Demonstration Script

### Scene 1: Customer Natural Language Lodgement (`UC-01`, 45 Seconds)
- **Actor Role:** Customer (`customer_demo_one`) on `http://localhost:5173`.
- **Action:**
  1. Open the Customer Service Portal (Lodge Return tab).
  2. Input natural language statement: *"I received the espresso machine yesterday but the heating element trips the safety circuit immediately upon turning it on."*
  3. Select Requested Outcome: `REFUND`.
  4. Attach staged proof: Upload receipt image `delonghi_invoice.png`.
  5. Click **Submit Return Request (HTTP 201)**.
- **Talking Point:**
  > *"Notice how the customer describes their issue in natural everyday language. The frontend enforces RFC-compliant idempotency keys and packages staged multipart evidence attachments without evaluating business rules locally."*

### Scene 2: Targeted Supplementary Clarification (`UC-01E`, 45 Seconds)
- **Actor Role:** Customer switching to **Track & Clarify** tab.
- **Action:**
  1. Select quick demo case `case_demo_001` (Awaiting Information).
  2. Highlight the amber **Supplementary Clarification Requested (UC-01E)** card displaying Question Set ID `qset_demo_001`.
  3. Fill in answers:
     - Barcode question: *"Barcode is 9312345678901, tag attached."*
     - Parcel integrity question: *"Outer StarTrack parcel was intact."*
  4. Click **Submit Supplementary Clarification (HTTP 202)**.
- **Talking Point:**
  > *"Rather than forcing customers to re-fill generic forms, the Intake Coordinator Agent extracts targeted questions. The frontend submits answers bound to the expected case version (v2), preventing lost updates if concurrent updates occur."*

### Scene 3: Founder Governed Review & Double Approval Guard (`UC-04`, 60 Seconds)
- **Actor Role:** Store Founder navigating to **Founder Console & Governance**.
- **Action:**
  1. Review queue table; filter by status `AWAITING_APPROVAL`.
  2. Click **Inspect** on `case_demo_003`.
  3. Cycle through modal tabs:
     - **AI Proposal & Risk Review**: Show the Assessment Proposal (`recommended_action: PROPOSE_REFUND`, `confidence: 0.96`, refund amount `$220.00` — a demo-only display field, since the v1 `DecisionPacket` carries no refund amount — and rationale) and Member C's independent Risk Review (`outcome: PASS`, findings, `reviewed_at`).
     - **Order & Facts Projection**: Inspect the contract-shaped `OrderSnapshot` — `order_id ord_7731`, `purchased_at`, `snapshot_version: 1`, and its single `line_item` (`French Linen Sheet Set (Queen, Oatmeal)`, SKU `LN-SHT-QN-OAT`, `unit_price_minor: 22000`). This tab renders **only** fields the contract actually carries; it does not display carrier or order-total fields that the snapshot does not contain.
     - **Tamper-Evident Audit Chain**: Display the recorded event history and its SHA-256 hash pointer fields, which the demo presents as an immutable-event indicator. The banner reflects recorded events; the demo does not recompute the chain (see the limits in Section 4).
  4. Click **Approve Return (UC-04)** in footer.
  5. Enter mandatory governance rationale: *"Verified unopened goods within 30-day change of mind window."*
  6. Click **Record & Execute**.
- **Talking Point:**
  > *"Crucially, the UI does not allow arbitrary approval. The approval request is designed to strictly bind the preview_id and cryptographic scope_fingerprint generated by the Operations Service — if the proposal changes during review, the domain layer rejects the approval. Be precise about this prototype, though: that binding is the backend design, not wired UI behaviour. The live `POST /v1/founder/cases/{id}/decisions` route is gated with `501 NOT_IMPLEMENTED`, so the approval is recorded against the mock store, and the client neither sends nor asserts those parameters. Section 4 lists exactly what this suite does and does not evidence."*

### Scene 4: Operations Analytics & SLA Monitoring (`OF-006`, 30 Seconds)
- **Actor Role:** Founder switching to **Analytics Dashboard (OF-006)**.
- **Action:**
  1. Showcase total volume throughput (128 cases), unreviewed backlog (58 cases).
  2. Point out latency percentiles ($p50$ at 11.20s, $p95$ SLA at 46.50s).
  3. Review status distribution progress bars and risk review outcome breakdown.
- **Talking Point:**
  > *"The analytics dashboard aggregates operational facts across the lifecycle, giving store owners real-time visibility into dispute turnaround SLA and risk distributions."*

---

## 4. Automated UI Regression Suite (`KAN-20`)

Member B's automated UI regression suite is implemented in Vitest and React Testing Library (`apps/web/src`):

```bash
cd returnops-au/apps/web
npm test
```

### Test Coverage Summary (119 Automated Tests Passing Across 13 Test Files):

> These entries describe what the assertions actually check. The counts measure
> passing assertions, not behavioural coverage; the explicit limits of this suite
> are listed in "What this suite does not evidence" below.

1. **`src/utils/formatters.test.ts` (20 tests)**: exact AUD strings (`$129.99`, `$0.00`, `$2,450.50`) plus the `—` fallback for `null`/`undefined`; `formatDate` returning `—` for empty, `undefined` and unparseable input, and otherwise matching `Date.toLocaleString('en-AU', { dateStyle: 'medium', timeStyle: 'short' })`; an exhaustive map of **all sixteen** `CaseStatus` values to their expected badge family; the five `RiskOutcome` outcomes across four assertions (`REVISE`/`NEEDS_INFORMATION` share one branch); four `IssueCategory` labels plus the uncategorised fallback; and `ActorProvenance` rendering for the string, `HUMAN`, `SERVICE` and `MODEL` kinds plus the nullish fallback.
2. **`src/utils/idempotency.test.ts` (2 tests)**: RFC idempotency key generation conforming to `^[A-Za-z0-9._:-]{8,128}$` and uniqueness guarantees.
3. **`src/api/client.test.ts` (24 tests)**: mock-mode toggle persistence and first-load default, JWT `localStorage` handling, offline intake creation (`status: 'SUBMITTED'`, retained `raw_text`), non-existent case → `ApiError`, clarification version increment (`3` → `4`), founder queue listing, a contract-shaped founder detail read (`purchased_at`, `line_items[0].unit_price_minor`, `recommended_action`, `confidence`, review `outcome`/`reviewed_at`, and the *absence* of the legacy `order_number`/`items`/`total_amount_cents`/`confidence_score`/`risk_outcome` aliases), audit-trail fields, recorded `APPROVE`/`REJECT` receipts (`processing_status: 'ACCEPTED'`, `approval_id` present for `APPROVE` and **absent** — not present-but-`undefined` — for `REJECT`), analytics snapshot shape, evidence staging, next-cursor pagination (`next_cursor: '20'`, 5 remaining items, `case_demo_021` only on page two), and `ApiError` field construction. It also pins live wire behaviour with a mocked `fetch`: a lost-response retry re-sends the caller's original idempotency key, the same key is carried on the multipart evidence upload as on intake, `409 IDEMPOTENCY_KEY_REUSED` and `409 VERSION_CONFLICT` surface as errors, a `202` clarification admission resolves as success, protected download sends `Authorization: Bearer` with no token in the URL and surfaces `403`, clarification `evidence_ids` reach the wire, and the undeployed Founder decision/analytics routes throw the explicit `501 NOT_IMPLEMENTED` gate. A founder view that falls back to a mock customer case adds no `facts` at all, so no model result is ever shown for a case the model never saw.
4. **`src/pages/CustomerPortal.test.tsx` (8 tests)**: `UC-01` heading, form and placeholder rendering; the submit button disabled on an empty statement; an instant receipt card after submission; submission blocked while a selected evidence file is unstaged (warning text, no receipt on a forced click, unblocked after removal); the `12,000`-character counter reading `12000 / 12,000 chars` at the documented bound and still counting at `12001 / 12,000 chars` with no `maxLength` attribute; `UC-01E` clarification rendering; multi-field answer submission reaching the component's `HTTP 202` confirmation copy; and the `NOT_FOUND` alert for a non-existent case.
5. **`src/pages/CustomerPortal.download.test.tsx` (2 tests)**: Protected evidence download renders the `403 FORBIDDEN` failure state to the customer, and the authorised path calls the download API with the exact evidence id/filename.
6. **`src/pages/CustomerPortal.idempotency.test.tsx` (2 tests)**: After a lost response, retrying an unchanged payload re-sends the original idempotency key, while a materially changed payload never silently reuses it.
7. **`src/pages/CustomerPortal.clarification.test.tsx` (1 test)**: Drives the real UI staging path on the Track & Clarify tab — attach a supplementary file, click **Stage File**, answer the questions — and asserts the `evidence_id` returned by the staging call reaches the clarification wire payload as `evidence_ids: ['ev_clarify_staged_01']` together with a non-empty retry key. This pins Finding 8 at the component level: staged clarification evidence is not silently dropped in the UI.
8. **`src/pages/FounderConsole.test.tsx` (12 tests)**: `UC-03` queue rendering from the mock summaries, status-dropdown filtering, `UC-05` multi-tab inspection (Order & Facts, Customer Statements, Tamper-Evident Audit Chain including `CASE_CREATED`), the `UC-04` `APPROVE` confirmation flow (mandatory-rationale input, modal closure on admission), the `OF-006` Analytics tab rendering `Total Case Volume 128`, `Unreviewed Cases 58` and the `p50_ms`/`p95_ms` fixtures formatted as `11.20s`/`46.50s`; next-cursor pagination making the 21st case reachable and then hiding the control; reachability of all four governed decision confirmations (each confirmation's **Record & Execute** control is asserted disabled before a rationale is typed and enabled after); a blank or whitespace-only rationale being rejected (`Confirm Founder Decision: APPROVE` stays open and the button stays disabled); a real Inspect interaction on the escalated `case_demo_004` (the detail view resolves instead of returning a not-found error, `Approve Return (UC-04)` is disabled, and `Manual Takeover`/`Reject` stay enabled); and a real Inspect on the completed `case_demo_005` whose audit tab renders its full closure (`CASE_COMPLETED`, `FOUNDER_APPROVED`, `REFUND_DISPATCHED`) and the banner sentence `This view does not recompute or verify the chain.` In Mock Mode the advisory facts card is present on `case_demo_001` and absent on `case_demo_002`, which carries no facts.
9. **`src/pages/FounderConsole.failure.test.tsx` (3 tests)**: A strictly contract-shaped `OrderSnapshot`/`DecisionPacket`/`RiskReview`/`ActionPreview` (all backward-compatibility aliases flagged in round 2 have been removed) renders without crashing or emitting `NaN` and degrades every demo-only extension tile to its placeholder, with each assertion anchored to the specific tile so an unrelated `—`/`N/A` on the page cannot satisfy it (`—` for the refund amount and label flag, `N/A` for the risk score, no reviewer-summary or citation block, and a contract-shaped Action Preview whose operation-type row stays empty rather than inventing a value), an audit-chain retrieval failure shows its own error state instead of the "Recorded Audit Events" banner, and live mode disables Approve and shows the "not yet deployed" notices.
10. **`src/pages/CustomerPortal.state-races.test.tsx` (29 tests)**: Mocks only the four client boundaries (`getCustomerCase`, `stageEvidence`, `createCase`, `submitClarification`); the two POSTs reject with `NETWORK_ERROR` by default so that retry identity can be observed.
    - *Upload selection identity, run once for the lodgement form and once for the clarification form (4 × 2 tests).* A removed file whose staging call resolves after a replacement was selected does not reappear, the replacement must still be staged before submit is enabled, and only the replacement's `evidence_id` is submitted. When two uploads finish in reverse order, submit stays disabled while the first is still uploading, then both show as staged and both IDs are submitted in selection order. A removed file's staging failure raises no alert and does not restore its row. Retrying a failed staging call re-sends the same file with the same idempotency key.
    - *Clarification draft scope and pending callbacks (17 tests).* Switching from case A to case B drops A's answers and staged file, and B's submission carries B's case ID, version, question set and answers with `evidence_ids: []`. A late case A staging result (resolve or reject) after the switch raises no alert and adds no row, and B submits only its own evidence. Refreshing an unchanged scope keeps the answers and staged file, and the retry is identical to the first call (same payload and key). Leaving A for B and returning with the same answers sends an identical payload under a **new** key. After a lost POST response, a failed refresh hides the case and its submit button; a recovery lookup that confirms the same scope restores the draft and re-sends the identical payload and key, while one that returns a changed version and question set yields an empty draft, no evidence and a new key. An explicit `401`/`403`/`404` read failure (3 tests) clears the draft and retry key. A same-case refresh with a changed version or question set (2 tests) resets the draft and the next submission binds the new values with a new key. An older lookup (resolve or reject) arriving after a newer case loaded leaves case B displayed with no error. A case A submission that resolves or rejects while case B has its own pending submission leaves B's disabled **Submitting Clarification** button and view untouched with no message; B's own later failure then shows `Failed to submit clarification.` and re-enables submit. An older refresh resolving after an accepted clarification does not overwrite it: `UNDER_INVESTIGATION` and the success message remain and the answer form stays hidden.
    - *Answer-or-evidence contract (4 tests).* Evidence-only clarification is sent with `answers: []`, the staged ID, version 2 and the current question set; one answered question beside a blank one sends only the trimmed answer (`Barcode 123`); a whitespace-only clarification shows `Please provide an answer or supplementary evidence.` and makes no call; and a forced submit with an unstaged file, then with a file still uploading, shows each gate message and makes no call; once staging completes, the staged ID is submitted.
11. **`src/pages/CustomerPortal.pending-submit.test.tsx` (4 tests, Issue #88)**: One success test and one failure test per form. Each holds the `createCase` or `submitClarification` call open on a deferred promise and, while it is pending, tries to change the text fields (and, in the lodgement success test, the outcome), add `late.png` and remove the staged file. All four tests then assert the frozen draft: the statement, order reference and outcome fields (lodgement) or the answer field (clarification), the file input and the staged file's **Remove** button are disabled; the shown values, the staged label and the file list are unchanged; no **Stage File** control exists (every submitted file is already staged and adding is refused); and staging was called only once. *Success tests:* the call carried exactly the values shown at submit time. For lodgement, after **Lodge Another Return** the statement, order reference and files are cleared, the outcome keeps its submitted value (`REFUND`), and the statement field is enabled; for clarification, the `HTTP 202` message shows and the answer form is gone. *Failure tests (`NETWORK_ERROR`):* the error shows, the statement or answer and the staged label remain, every control listed above is enabled again, and the retry sends an identical payload with the same idempotency key. `fireEvent.change` still reaches React's change handler on a disabled field, so the handler guards for text and file selection are exercised (removing either makes the suite fail). Of the two file-row buttons, only **Remove**'s `disabled` attribute is asserted. A **Stage File** button cannot render while a request is pending, so its `disabled` change and both Stage click guards are an untested backup; React does not dispatch clicks to disabled buttons, so the two **Remove** click guards are an untested backup as well.
12. **`src/pages/FounderConsole.facts.test.tsx` (10 tests, Issue #95)**: The advisory card is hidden when the case view carries no facts, and when it does carry facts it shows all six contract fields under an advisory label that says it changes no proposal, review, decision or execution. An empty `line_items` list is stated rather than left blank, and a non-empty one is listed as line-item ID and quantity. The `summary` is rendered as plain text, so markup, Markdown and a URL appear literally and create no elements. The card carries no buttons, links or text inputs, and it stays off the default proposal tab even when facts are present. In Mock Mode the facts are marked as mock data. After the card has been shown, an `APPROVE` and a `REJECT` request are sent with nothing from the facts in the body.
13. **`src/api/mockData.test.ts` (2 tests, Issue #95)**: Every mock `facts` object is checked against the contract's `ExtractedFacts` shape, and against the values the advisory showcase accepts (`docs/44`): the requested outcome matches the customer's original choice, `possible_basis` is `UNDETERMINED`, `assessment_status` is not `SUPPORTED`, `line_items` is empty and the summary stays within the showcase's length limit.

**What this suite does not evidence.** The `OF-006` assertions read fixture values the component renders (plus the `p50_ms`/`p95_ms` → `11.20s`/`46.50s` formatting); they do not verify backend aggregation arithmetic. The `12,000`-character intake bound is a display counter, not a client-side rejection rule — the contract's input-capacity limit is enforced server-side. `UC-04` decisions run against the mock store: the live `POST /v1/founder/cases/{id}/decisions` route is deliberately gated with `501 NOT_IMPLEMENTED` (Finding 4), so approval-guard wire parameters (`preview_id`, `scope_fingerprint`) are neither sent nor asserted. The Customer Portal `HTTP 202` assertion checks the component's confirmation copy in mock mode, while wire-level `202` handling is asserted separately in `client.test.ts`. No component test performs real network I/O, and no suite loads the FastAPI application.

Three further limits are worth stating plainly. First, the Founder detail cards render a small set of **frontend-only demo extensions** that the v1 contract does not carry as fields (`refund_amount_cents`, `return_label_required`, `risk_score`, `summary`, `policy_citations`, `action_preview.operation_type`, `action_preview.details`); `apps/web/src/types/domain.ts` labels them as such, and the contract's citation data lives elsewhere (`DecisionPacket.citations`, `RiskFinding.citation_ids`, the latter already present in the mock findings). A live response leaves them `undefined`, and the tiles degrade per field rather than uniformly: the refund amount and the return-label tile render `—`, the risk score renders `N/A`, the reviewer summary and citation chips render nothing at all, and the Action Preview's operation-type/parameters rows remain empty or render as appropriate. `FounderConsole.failure.test.tsx` asserts exactly this degradation against a contract-shaped response, so no tile can claim a statutory waiver or a risk score the backend never sent. Second, the **Tamper-Evident Audit Chain** panel reflects the presence of recorded audit events and their fixture `event_hash`/`previous_event_hash` values; no test recomputes the hash chain. The banner therefore reads "Recorded Audit Events", uses neutral rather than success styling, and states that the view does not recompute or verify the chain: it shows each recorded hash and, where present, the previous-hash link, not a verified cryptographic linkage. `FounderConsole.test.tsx` asserts that sentence. Third, the confirmation-modal **stacking** fix (Finding 3) is evidenced by the emitted stylesheet (`z-[60]` present in the built CSS), not by the jsdom tests — jsdom does not compute paint order, so the reachability assertions and the CSS check are two separate pieces of evidence. The evidence gate is exercised for an *unstaged* file on both forms. For a file that is still *uploading*, both forms assert the submit button disabled (`CustomerPortal.state-races.test.tsx`), but only the clarification form also forces a submit and asserts the handler's wait message; the lodgement wait message is not asserted.


Every one of these suites runs in the CI `web-frontend` job (`.github/workflows/ci.yml`), whose steps run in this order: `npm ci`, `npm run type-check` (`tsc --noEmit`), `npm test` (`vitest run`), then `npm run build` (`tsc && vite build`). The job runs beside the final `api-environment` gate rather than inside it: it is not in that job's `needs`, which `tools/checks/run.py ci-gate` requires to be exactly `offline-contract-models`, `environment-plan` and `environment-checks`.

---

## 5. Verification Commands

```powershell
# 1. Run unit, component and integration tests
npm --prefix returnops-au/apps/web test

# 2. Verify strict TypeScript compilation (zero errors)
npm --prefix returnops-au/apps/web run type-check

# 3. Verify production build bundle
npm --prefix returnops-au/apps/web run build

# 4. Verify system static model checks
python returnops-au/tools/model-checks/check.py
```
