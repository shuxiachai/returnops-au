# ReturnOps AU — Web Frontend (`apps/web`)

**Owner:** Member B (Chengsi Li, `@ChengsiLi`)  
**Components:** Customer Portal (`B1`), Founder Console (`B2`), Operations Analytics (`B3`)  
**Traceability:** UC-01, UC-01E, UC-03, UC-04, UC-05, OF-006; FR-001, FR-002, FR-005, FR-009, FR-011, FR-012  
**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons

---

## 1. Architecture & Design Principles

The frontend strictly acts as an untrusted client consuming the authoritative backend (`apps/api`):
1. **Clean Architecture Separation (`P01` vs `P02`)**:
   - `apps/web` never produces authoritative approval, case state transitions, or execution commands directly.
   - All state transitions are issued as FastAPI endpoint calls (`/v1/cases`, `/v1/cases/{id}/clarifications`, `/v1/founder/cases/{id}/decisions`); in the default Mock Mode the same call surface is served by the deterministic fixture store instead, so a transition the backend has not registered is never faked.
2. **Idempotency & Optimistic Concurrency**:
   - Every write operation attaches an `Idempotency-Key` header adhering to `^[A-Za-z0-9._:-]{8,128}`.
   - Clarifications and Founder decisions enforce `expected_case_version` optimistic locking to avoid lost updates.
3. **Execution Modes — Mock, Live Reads and Live Writes**:
   - **Mock Data Mode (default)**: built-in synthetic domain datasets back every screen, so the whole demo runs with no PostgreSQL, no API and no network access. The mock analytics snapshot is fixed, so the analytics filters are disabled in Mock Mode.
   - **Live reads — implemented**: with Mock Mode disabled, the client calls the real FastAPI gateway through the Vite dev proxy (`/v1` → `http://127.0.0.1:8000`). Live reads that exist today are `GET /v1/founder/cases` (cursor-paginated), `GET /v1/founder/cases/{id}`, `GET /v1/founder/cases/{id}/audit`, `GET /v1/founder/analytics`, `GET /v1/cases/{id}`, and protected evidence download (`GET /v1/evidence/{id}/content`). Each sends `Authorization: Bearer …` and never places the token in the URL.
   - **Live analytics**: `GET /v1/founder/analytics` is registered by default on backend `main`. The page sends only the contract's optional query keys, each at most once: `created_from` and `created_before` (whole UTC days, sent as `YYYY-MM-DDT00:00:00Z`; the window is half-open, `from < before`, checked before sending) and one current `status`. It shows the server's numbers as they are: buckets with zero cases are omitted and are not drawn, and the echoed `filters` and `as_of` are shown. Proposal latency is at tier 0 today (no samples), so the p50/p95 tiles show `—` with "Not measured", and the measured, failed and unmeasured counts sit beside them.
   - **Live writes — implemented**: `POST /v1/cases` (intake), staged evidence upload (`POST /v1/evidence`) and `POST /v1/cases/{id}/clarifications`. Every write carries an `Idempotency-Key`; the key for one customer intent is minted once, reused on retry while the payload is unchanged, and replaced when the payload materially changes. A `409 IDEMPOTENCY_CONFLICT` response is surfaced to the operator rather than silently swallowed.
   - **Founder decisions — live only when the server serves the route**: backend `main` registers `POST /v1/founder/cases/{id}/decisions` only when the API is started with the decision flag (`python -m returnops_api.demo serve … --founder-decisions`, or `RETURNOPS_FOUNDER_DECISIONS=1`; off by default). The client sends a contract-exact `FounderDecisionRequest` with an `Idempotency-Key` (reused when the same body is sent again, for example after a `503`, and replaced when it changes). Every target value is copied from the server's case view and never invented: **Approve** is enabled only when that view carries the current proposal and its `action_preview` (preview ID and scope fingerprint), and otherwise stays disabled with the reason shown. Each decision is offered only in the case states the server accepts (`APPROVE` and `REJECT` in `AWAITING_APPROVAL`; `REQUEST_REVISION` and `MANUAL_HANDLING` in `ESCALATED` or `AWAITING_APPROVAL`; manual handling of a failure or block only in `ESCALATED`), with the reason in the button tooltip (#104 item 1). The same target and state rules apply in Mock Mode, whose store refuses other states with `409 INVALID_STATE`. The preview card and the Approve confirmation show the preview ID, the scope fingerprint and every field of the contract `ApprovalScope` (case and input version, proposal and review, parcel, the `CREATE_RETURN` and `GENERATE_LABEL` commands with their parameters, the amount ceiling and currency, expiry, environment and allowlist version), so the Founder sees exactly what an approval authorises. The confirm button reads **Record decision**: no decision runs an operation from the browser. A `2xx` counts as success only when its body is a receipt for the same case and decision with `processing_status` `ACCEPTED`; that means the decision was accepted, not that any operation has run. A `4xx` refusal (`401`/`403`/`404`/`409`/`422`) stays in the decision dialog with the server's code and message. For `409 STALE_CASE_VERSION` the console also reloads the case and its audit behind the dialog and says "The case changed; the view was reloaded. Check it and decide again." (docs/09 error table); deciding again sends the new version under a new key. The clarification form does the same for the customer, keeps typed answers when the questions are unchanged, and sends nothing until the customer submits again. Any `5xx`, a lost response, or a `2xx` that is not a matching receipt is reported as an unknown outcome, because the decision may have been recorded. This includes the Vite dev proxy's empty `500` when the API cannot be reached, which the client otherwise words as "the API server did not answer". Submitting the same rationale again reuses the same key. When the flag is off, the server answers `404` with no contract error envelope, and the console reports `DECISION_ROUTE_NOT_SERVED`: the route was not served and nothing was recorded. A wrong `VITE_API_BASE_URL` or proxy gives the same reply, so the message names both causes (#104 item 5).
4. **Demo-only display extensions**: the Founder detail cards also render a few fixture values that the v1 contract does not carry as fields — a refund amount, a return-label flag, a numeric risk score, a review summary, a policy-citation list, and the Action Preview's `operation_type`/`details` — declared as frontend-only demo extensions in `src/types/domain.ts` (the contract's citation data lives elsewhere: `DecisionPacket.citations`, `RiskFinding.citation_ids`). A live response leaves them `undefined`, and then those tiles and blocks are not shown at all (the Action Preview's operation-type/parameters appear only if present) — demo decoration, never contract-backed facts.
5. **Session expiry and auto-refresh**: any `401` shows one banner under the header ("Session expired or not valid. Open Auth Tokens and paste a new token.") and the header badge reads **Signed out**; in Live API mode the badge otherwise shows the role and principal from `GET /v1/session`, not the persona stored in the browser. Coming back to the window (focus or a visible tab) reloads the Founder queue and the open case. The open Founder case and the tracked customer case are read again every 5 s until they reach `COMPLETED`, `REJECTED` or `MANUAL_HANDLED`; nothing is read while the tab is hidden, while a Founder decision is being confirmed, or while the shop waits for the customer's answers (every customer read takes the database fence, #106). A case that cannot be opened is reported on the page, not in a browser alert.

> **Delivery keys and evidence.** The delivery key recorded for this work is `B2.05` / `KAN-20`, also fulfilling `B1.05` and `B3.03`, as written up in [`docs/35 — Interactive Demo Walkthrough`](../../docs/35-b205-interactive-demo-walkthrough.md). That record is **not** a verified Jira board state, and this repository does not maintain a duplicate status board: Member A owns Jira and must confirm the actual Jira-to-technical mapping and supply the linked GitHub Issue for this delivery.

---

## 2. Feature Mapping

| View / Component | Use Case & Requirement | Backend Route / Contract | Description |
|---|---|---|---|
| **Lodge Return** | `UC-01` / `AH-01` (FR-001, FR-002) | `POST /v1/cases`<br>`POST /v1/evidence` | Natural language statement submission, optional order reference, outcome selection, multi-file staged evidence upload (JPEG/PNG/PDF, max 10MB). |
| **Track & Clarify** | `UC-01E` (FR-005, NFR-008) | `GET /v1/cases/{id}`<br>`POST /v1/cases/{id}/clarifications` | Inspect case lifecycle status (16 states), view the targeted questions from the deterministic intake, submit answers & additional evidence (HTTP 202). |
| **Founder Queue** | `UC-05` (FR-011, FR-012) | `GET /v1/founder/cases`<br>`GET /v1/founder/cases/{id}` | Store-scoped case queue, detailed inspection of customer claims, projected order facts, proposals, and risk reviews. |
| **Model extraction (advisory)** | `UC-05` (FR-012 view of FR-002 facts; NFR-009) | `GET /v1/founder/cases/{id}` → optional `CaseView.facts` (`ExtractedFacts`) | A card on the case's **Order & Facts Projection** tab shows the six `ExtractedFacts` fields: `issue_category`, `customer_requested_outcome`, `possible_basis`, `assessment_status`, `summary` and `line_items` (an empty list is shown as "Line items (0)" and "No line items selected (empty list)."). It is labelled advisory: it does not change any proposal, review, decision or execution, and the Founder decides. The model-written `summary` is untrusted and rendered as plain text (no HTML, Markdown or links). The card is absent whenever `facts` is absent: live, the server sends `facts` only when the default-off Coordinator showcase ([docs/44](../../docs/44-coordinator-showcase.md)) holds validated facts for the case's current statements; in Mock Mode only `case_demo_001` has a hand-written, contract-shaped example, labelled "Mock data: not a model result". The audit tab shows no model event, because the showcase writes none (docs/44). |
| **Audit Verification** | `UC-05` (FR-011, NFR-003) | `GET /v1/founder/cases/{id}/audit` | SHA-256 hash-pointer event timeline as recorded by the domain (the console displays the recorded linkage and does not recompute the chain). |
| **Decision & Outcome** | `UC-04` / `UC-05` (FR-010, FR-011, FR-012) | `GET /v1/founder/cases/{id}` → `decisions`, `approvals`, `operations`, `notifications`<br>`GET /v1/evidence/{id}/content` (label PDF) | A case tab showing what happened after the Founder decided, in the contract shapes `FounderDecisionRecord`, `ApprovalRecord`, `OperationAttempt` and `NotificationRecord`: the decision with its rationale, principal, time and target; the exact approved scope (fingerprint, commands, expiry); each simulated operation with its status, attempts and any error, and **Download label (PDF)** for a confirmed `GENERATE_LABEL` result; the notice to the customer with its status, message and next steps. A confirmed decision reopens the case on this tab. Server text is plain text; nothing is inferred (#122 item 4). |
| **Governed Decision** | `UC-04` / `UC-03` (FR-009, FR-010, FR-012) | `POST /v1/founder/cases/{id}/decisions` (served only with `--founder-decisions`) | Four governed actions: `APPROVE`, `REJECT`, `REQUEST_REVISION`, `MANUAL_HANDLING`, each sent with exactly one contract target taken from the server's case view; the Approve confirmation shows the full approval scope; an escalated case without a proposal shows why (contract `OrderLookupBlock` or `ProcessingFailure`) and offers only Manual Takeover bound to that target; the server's guards decide. |
| **Operations Analytics** | `OF-006` (Member B Optional) | `GET /v1/founder/analytics` | Server-computed metrics for one cohort: total volume, case status and risk outcome distribution (zero buckets omitted), proposal latency with measured, failed and unmeasured counts and `as_of`; optional created-at window and current-status filters. |

---

## 3. Getting Started

### Prerequisites
- Node.js as declared in `package.json` `engines`: `^22.22.2 || ^24.15.0 || >=26.0.0` (npm >= 10). CI runs this job on Node 24.

### Installation
```bash
cd apps/web
npm ci          # locked install (package-lock.json is tracked)
```

### Development Server
```bash
npm run dev
```
The app will be accessible at: `http://localhost:5173`.  
Vite automatically proxies `/v1` requests to `http://127.0.0.1:8000`.

### Type Checking, Tests & Build
```bash
npm run type-check   # Verifies TypeScript without emission
npm test             # Runs the Vitest + React Testing Library regression suite
npm run build        # Compiles production bundle to dist/
npm run preview      # Serves production build locally
```
All three checks (`type-check`, `test`, `build`) run in the CI `web-frontend` job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

---

## 4. Demo Credentials & Persona Switcher

Click the **Auth Tokens** button in the top navigation bar to configure personas. The button does not always read "Auth Tokens": once a token is saved it shows a coloured status dot and the label the server reported (`FOUNDER · founder_live`, or `Signed out` after a `401`) in place of the words, and the words reappear only on screens 1280 px and wider. Its accessible name and tooltip stay `Auth Tokens: <label>`, so it can still be found by that name.
- **Customer Role**: Interacts with `UC-01` / `UC-01E` endpoints.
- **Founder Role**: Interacts with `UC-04` / `OF-006` endpoints.
- **JWT Input**: Paste tokens generated by `python -m returnops_api.demo provision` (from private `sessions.json`). The field is masked; **Show** reveals it until the dialog is closed (#111 item 12).
- **Verify**: checks the token in the box against `GET /v1/session` before it is saved, and selects the persona of the role the server reports. Nothing is stored until **Save & Apply**.

---

## 5. Changes of 30 October 2026

A read-only review of `main` at `ea227f48` found these on the demonstration path; each has a Vitest regression test (217 tests in 22 files after the change):

- **Founder queue on narrow screens:** the table scrolls sideways inside its card and the Actions column stays pinned, so **Inspect** is reachable at 1024 px (a projector) and below; the Case ID cell is shortened, with the full ID on hover.
- **Category:** the server sends `UNCLEAR` as a placeholder in every Gate 1 case summary (no classifier runs), so the queue says "Not yet classified" instead of "Unclear Statement"; Mock Mode rows follow the server.
- **Customer form:** after a lodgement the requested outcome starts again from "Not sure", so the next case does not inherit the previous choice; the long case ID wraps in the success card; **Track This Case** reads the case once.
- **Answers received:** the confirmation stays through the 5 s refresh and **Refresh**, until another case is opened or a new one lodged.
- **Decisions:** an ACCEPTED receipt is reported as recorded even when the case cannot be read again straight after it.
- **Paging:** **Load Next Page** reuses the page size of the cursor it continues, so it works after a focus or stale-version reload.
- **Errors:** a failed connection is reported as `NETWORK_ERROR` instead of `[undefined] Failed to fetch`.
- **Keyboard:** **Add File** is reachable with the keyboard; the case window and the decision dialog are modal dialogs that **Escape** closes (never while a decision is being sent); icon-only close buttons and the Mock Data Fallback switch have names.
- **Auth Tokens:** **Clear token** only clears the field; the saved token changes on **Save & Apply**, so **Cancel** keeps the session.

## 6. Changes of 31 October 2026

An edge-case and display review against a real local API (PostgreSQL 17, the demo store, a one-origin proxy like Railway's) at 375, 768, 1024, 1280, 1366 and 1920 px found these; each has a Vitest regression test (232 tests in 24 files after the change):

- **Phones and tablets:** the header wraps instead of pushing **Live API** and **Auth Tokens** off a 375 or 768 px screen; the case window and the decision dialog shrink to the screen, the case ID wraps, the five views scroll sideways as a tab strip and the decision buttons wrap; the customer's case header wraps the long ID and its status.
- **Long words and other scripts:** the customer's words, a decision rationale and the notice break a long unbroken word inside their card, and set their own direction for right-to-left text; long IDs in the approval scope break anywhere.
- **Customer form:** the order reference is held to the 120 characters the server accepts; a file that is not JPEG, PNG or PDF, is empty or over 10 MB, or is beyond the tenth is refused on selection with the reason, on the lodgement and the clarification forms; a refused lodgement is shown next to **Submit Return Request**.
- **Track & Clarify:** **Enter** in the case ID box looks the case up, once; an unknown or malformed case ID is explained in plain words instead of `NOT_FOUND` or `VALIDATION_ERROR`; the box keeps its width in Mock Mode below 1024 px.
- **Founder queue:** an empty store says "No cases in the queue yet."; the search also matches the category words on screen ("Not yet classified").
- **Case window:** the five views are a `tablist` of `tab`s with `aria-selected`.
- **Errors:** a reply without an error envelope (a proxy 5xx) no longer names `127.0.0.1:8000`, and an empty HTTP/2 status text is not printed.
- **Mock Mode:** the completed `case_demo_005` shows the customer the notice that the Founder's Outcome tab shows as sent; long risk outcome names stay inside their analytics tiles.
