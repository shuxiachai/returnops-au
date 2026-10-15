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
3. **Execution Modes — Mock, Implemented Live Reads, and Planned Writes**:
   - **Mock Data Mode (default)**: built-in synthetic domain datasets back every screen, so the whole demo runs with no PostgreSQL, no API and no network access.
   - **Live reads — implemented**: with Mock Mode disabled, the client calls the real FastAPI gateway through the Vite dev proxy (`/v1` → `http://127.0.0.1:8000`). Live reads that exist today are `GET /v1/founder/cases` (cursor-paginated), `GET /v1/founder/cases/{id}`, `GET /v1/founder/cases/{id}/audit`, `GET /v1/cases/{id}`, and protected evidence download (`GET /v1/evidence/{id}/content`), which sends `Authorization: Bearer …` and never places the token in the URL.
   - **Live writes — implemented**: `POST /v1/cases` (intake), staged evidence upload (`POST /v1/evidence`) and `POST /v1/cases/{id}/clarifications`. Every write carries an `Idempotency-Key`; the key for one customer intent is minted once, reused on retry while the payload is unchanged, and replaced when the payload materially changes. A `409 IDEMPOTENCY_KEY_REUSED` response is surfaced to the operator rather than silently swallowed.
   - **Live writes — planned, not yet registered on backend `main`**: `POST /v1/founder/cases/{id}/decisions` (Founder decisions) and `GET /v1/founder/analytics` (Operations Analytics). The client deliberately refuses these with `501 NOT_IMPLEMENTED`; the Founder Console disables **Approve** and shows a "not yet deployed" notice. Mock Mode stays the demonstration path for governed decisions and analytics.
4. **Demo-only display extensions**: the Founder detail cards also render a few fixture values that the v1 contract does not carry at all — a refund amount, a return-label flag, a numeric risk score, a review summary and policy citations — declared as frontend-only demo extensions in `src/types/domain.ts`. A live response leaves them `undefined` and the tiles render `—`; they are demo decoration, never contract-backed facts.

> **Delivery keys and evidence.** The delivery key recorded for this work is `B2.05` / `KAN-20`, also fulfilling `B1.05` and `B3.03`, as written up in [`docs/35 — Interactive Demo Walkthrough`](../../docs/35-b205-interactive-demo-walkthrough.md). That record is **not** a verified Jira board state, and this repository does not maintain a duplicate status board: Member A owns Jira and must confirm the actual Jira-to-technical mapping and supply the linked GitHub Issue for this delivery.

---

## 2. Feature Mapping

| View / Component | Use Case & Requirement | Backend Route / Contract | Description |
|---|---|---|---|
| **Lodge Return** | `UC-01` / `AH-01` (FR-001, FR-002) | `POST /v1/cases`<br>`POST /v1/evidence` | Natural language statement submission, optional order reference, outcome selection, multi-file staged evidence upload (JPEG/PNG/PDF, max 10MB). |
| **Track & Clarify** | `UC-01E` (FR-005, NFR-008) | `GET /v1/cases/{id}`<br>`POST /v1/cases/{id}/clarifications` | Inspect case lifecycle status (16 states), view targeted questions from Assessment Agent, submit answers & additional evidence (HTTP 202). |
| **Founder Queue** | `UC-05` (FR-011, FR-012) | `GET /v1/founder/cases`<br>`GET /v1/founder/cases/{id}` | Store-scoped case queue, detailed inspection of customer claims, projected order facts, proposals, and risk reviews. |
| **Audit Verification** | `UC-05` (FR-011, NFR-003) | `GET /v1/founder/cases/{id}/audit` | SHA-256 hash-pointer event timeline as recorded by the domain (the console displays the recorded linkage and does not recompute the chain). |
| **Governed Decision** | `UC-04` / `UC-03` (FR-009, FR-010) | `POST /v1/founder/cases/{id}/decisions` | Four governed actions: `APPROVE`, `REJECT`, `REQUEST_REVISION`, `MANUAL_HANDLING` guarded by Approval Guard. |
| **Operations Analytics** | `OF-006` (Member B Optional) | `GET /v1/founder/analytics` | Operational metrics: total volume, case status distribution, risk review breakdowns, and proposal turnaround latency SLA. |

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

Click the **Auth Tokens** button in the top navigation bar to configure personas:
- **Customer Role**: Interacts with `UC-01` / `UC-01E` endpoints.
- **Founder Role**: Interacts with `UC-04` / `OF-006` endpoints.
- **JWT Input**: Paste tokens generated by `python -m returnops_api.demo provision` (from private `sessions.json`).
