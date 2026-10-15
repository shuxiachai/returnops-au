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
| `case_demo_005` | `COMPLETED` | `FAULTY_OR_QUALITY_ISSUE` | Risk: `PASS` · Terminal state | **Audit History (`UC-05`)**: Demonstrates complete lifecycle closure and immutable SHA-256 hash pointer chain. |

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
     - **AI Proposal & Risk Review**: Show the Assessment Proposal (`recommended_action: PROPOSE_REFUND`, `confidence: 0.96`, refund amount `$220.00`, rationale) and Member C's independent Risk Review (`outcome: PASS`, findings, `reviewed_at`).
     - **Order & Facts Projection**: Inspect the contract-shaped `OrderSnapshot` — `order_id ord_7731`, `purchased_at`, `snapshot_version: 1`, and its single `line_item` (`French Linen Sheet Set (Queen, Oatmeal)`, SKU `LN-SHT-QN-OAT`, `unit_price_minor: 22000`). This tab renders **only** fields the contract actually carries; it does not display carrier or order-total fields that the snapshot does not contain.
     - **Tamper-Evident Audit Chain**: Display the SHA-256 hash pointer link ensuring immutable event history.
  4. Click **Approve Return (UC-04)** in footer.
  5. Enter mandatory governance rationale: *"Verified unopened goods within 30-day change of mind window."*
  6. Click **Record & Execute**.
- **Talking Point:**
  > *"Crucially, the UI does not allow arbitrary approval. The approval request strictly binds the preview_id and cryptographic scope_fingerprint generated by the Operations Service. If the proposal changes during review, the domain layer immediately rejects the approval."*

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

### Test Coverage Summary (63 Automated Tests Passing Across 8 Suites):
1. **`src/utils/formatters.test.ts` (19 tests)**: Australian dollar formatting (`$AUD`), en-AU medium date formatting, status badge classes across all 16 `CaseStatus` states, 5 risk badges, issue categories, and safe polymorphic `ActorProvenance` rendering.
2. **`src/utils/idempotency.test.ts` (2 tests)**: RFC idempotency key generation conforming to `^[A-Za-z0-9._:-]{8,128}$` and uniqueness guarantees.
3. **`src/api/client.test.ts` (21 tests)**: Dual-mode toggle persistence in `localStorage`, default mock mode fallback, offline intake creation, clarification version increments, founder case retrieval, tamper-evident audit queries, governed decision execution, and `ApiError` envelope parsing. It also pins the live wire contract with a mocked `fetch`: lost-response retry reuses the original idempotency key, `409 IDEMPOTENCY_KEY_REUSED` surfaces as an error, protected evidence download sends `Authorization: Bearer` with no token in the URL, clarification `evidence_ids` reach the wire, and the not-yet-deployed Founder endpoints return the `501` gate.
4. **`src/pages/CustomerPortal.test.tsx` (7 tests)**: `UC-01` intake form validation, 30-character boundary check, instant receipt card generation, submission blocked while a selected evidence file is unstaged, `UC-01E` clarification question rendering, multi-field answer submission with HTTP 202 acceptance, and non-existent case error alert.
5. **`src/pages/CustomerPortal.download.test.tsx` (2 tests)**: Protected evidence download renders the `403 FORBIDDEN` failure state to the customer, and the authorised path calls the download API with the exact evidence id/filename.
6. **`src/pages/CustomerPortal.idempotency.test.tsx` (2 tests)**: After a lost response, retrying an unchanged payload re-sends the original idempotency key, while a materially changed payload never silently reuses it.
7. **`src/pages/FounderConsole.test.tsx` (7 tests)**: `UC-03` queue rendering, status dropdown filtering, `UC-05` multi-tab deep inspection (Proposal, Order, Statements, Audit Hash Chain), `UC-04` double Approval Guard parameter execution, `OF-006` analytics snapshot calculations, next-cursor pagination up to the 21st case, and reachability of all four governed decisions.
8. **`src/pages/FounderConsole.failure.test.tsx` (3 tests)**: A strictly contract-shaped `OrderSnapshot` (no legacy aliases) renders without crashing or emitting `NaN`, an audit-chain retrieval failure shows its own error state instead of the validated banner, and live mode disables Approve and shows the "not yet deployed" notices.

Every one of these suites runs in the CI `web-frontend` job (`.github/workflows/ci.yml`) after `npm ci`, `tsc --noEmit` and `vite build`.

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
