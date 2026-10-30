# Gate 2 roadmap and deferred scope

Owner: A Jingbo Chai. Work package R.05 ("Stage 2 final course delivery, demo and follow-up route") in the unchanged [work packages](08-delivery-work-packages.md) (Owner A, Reviewer C; start E.12; finish R.04, A3.03, B3.03, C3.03). This page states what the Gate 1 scope delivered for the Stage 2 submission, what Gate 2 would add, what must be true before it starts, and the status of the optional features that are not delivered. It records no acceptance of any work package or Gate and changes no Owner, Reviewer or S/F value. Written 22 October 2026 (Sydney).

## 1. What the Gate 1 scope delivered

Delivered means merged into main with its own CI record, or published for merge where stated. It does not mean accepted.

| Item | Document | State on 22 October 2026 |
|---|---|---|
| R.02 no-model end-to-end run: customer HTTP case, synthetic order, fixed proposal, controlled PASS receiver and risk stub, Founder HTTP approval after negative tests, simulated return, label, PDF and mock notification, audit read-back; demo mode for the live demo | [docs/41](41-r02-end-to-end-evidence.md) | PR #89 merged; first result CI run 39634415393, receipt `PASSED`, 32 of 32 checks; demo mode merged with PR #93 (offline tests only) |
| Founder decision HTTP boundary (A2.07): the frozen decision POST behind an explicit flag | [docs/40](40-founder-decision-http-boundary.md) | In main; A2.07's PR #78 was merged on 22 October 2026 ([docs/41](41-r02-end-to-end-evidence.md)) |
| F.06 Founder analytics read API | [docs/43](43-f06-analytics.md) | PR #90 merged; latency Tier 0 (no samples) |
| A1.06 advisory Coordinator showcase (extraction half only, default off, outside the execution chain) | `docs/44-coordinator-showcase.md`, added by [PR #94](https://github.com/shuxiachai/returnops-au/pull/94) | Merged 22 October 2026 (PR #94; private-HTTP opt-in #98); first live result recorded on 22 October 2026 ([docs/44](44-coordinator-showcase.md#first-live-result-22-october-2026)) |
| B's web frontend (customer portal, Founder console, analytics page) | [apps/web README](../apps/web/README.md) | PR #60 merged; live Founder decisions and live analytics in the client since #102 (merged 23 October 2026 through #107, closing Issue #91); open follow-ups in Issues #104, #111 and #122 |
| C's offline candidates: C1 grounding, C2 risk reviewer, evaluation accounting | [experiments](../experiments) | Offline; not connected to the execution chain |

The Gate 1 condition itself, "Before connecting an LLM, demonstrate:" the chain Create Case to Audit ([docs/00](00-project-definition-v1.md), Gate 1), and the Gate 1 row of docs/08 are not claimed as met: R.02 and Gate 1 have no acceptance record.

## 2. The rule that governs Gate 2

The docs/08 Gate 1 row, translated from the Chinese original (the original line is authoritative): before R.02 passes, an LLM must not be connected to an execution chain that can trigger simulated operations; offline AI without execution authority may proceed in parallel. A1.08's acceptance repeats it: AI output is connected to the executable system only after Gate 1 safety acceptance.

Consequences for this roadmap:

- No model output may feed a proposal, a review, an approval, a preview or an operation until R.02 is accepted.
- The advisory showcase in PR #94 does not change this. It was built as a dated exception by the lead on 22 October 2026, argues only the "no execution authority, no guard path, no ApprovalRecord path" boundary, and is not Gate 1, Gate 2 or A1.06 acceptance (docs/44, Gate position).

## 3. What Gate 2 would add

The Gate 2 row of docs/08: after Gate 1, connect the three roles, validate them in an independent pilot, then freeze the formal evaluation version; C3's image work starts after the text path is stable.

| Work package | Owner / Reviewer | What it adds | S / F in docs/08 |
|---|---|---|---|
| A1.06 full Coordinator | A / C | Beyond the showcase: clarification questions written by the model, pilot validation of missing, conflicting and not-applicable information, reasonable purchase-proof substitutes, prompt and model versions kept | S F.01; F A1.01, F.07, E.01 |
| A1.07 Assessment and evidence matrix | A / C | PRESENT / MISSING / CONFLICTING / NOT_APPLICABLE per criterion, using C's versioned retrieval and verification; a non-executable DecisionPacket that cites sources | S F.01; F A1.01, C1.05, F.07, E.01 |
| A1.08 bounded three-role orchestration | A / C | Coordinator, Assessment and reviewer joined to the executable system after Gate 1; five risk outcomes and Founder revision routed correctly; bounded machine loops with versions and timings; no model path to a provider or to a trusted approval | S R.02; F A1.05, A1.06, A1.07, C2.05 |
| C1.04 excerpt check (remaining part) | C / A | A check that a quoted excerpt matches the cited passage, which the metadata-only `verify_citations` cannot do. Decided on 28 October 2026 ([#67](https://github.com/shuxiachai/returnops-au/issues/67#issuecomment-6458606959)): Assessment hands the exact asserted text and its packet binding to an internal adapter, whose separate record goes to C2. `Citation`, `CitationCheck` and the public contract stay unchanged; a public field would first need an F.01 change review. Until then quoted text is checked only by offline annotation | S C1.03 |
| C2 real reviewer (C2.02 to C2.05) | C / A | An independent reviewer model call replacing the controlled PASS receiver and risk stub; adversarial cases; routing contract; handover pack for A1.08 | C2.02 S C2.01, F C1.05, F.07; to C2.05 |
| E.09 runner | C / A | Single-model B1 / B4 evaluation runner with call adapter, counts, errors, scoring, tokens and cost; a stub does not count as a full B4 or safety-gate run | S E.01; F A1.06, A1.07, C2.05 |
| R.03 pilot | C / A | 10 to 20 pilot cases through the complete B4 after R.02, checking the three model outputs, retrieval and citations, independent review, deterministic gates and version tracking; stubs cannot stand in | S A1.08; F C1.05, C2.05, E.09 |
| E.12 formal evaluation | C / A | Frozen 30-case B1 / B4 comparison: raw counts, denominators, confusion matrix, citations and risk, p50 / p95, failure rate and cost | S E.08, R.03; F E.09, E.10, E.11, F.06 |

## 4. Preconditions before any Gate 2 model enters the chain

| Precondition | Status on 22 October 2026 | Source |
|---|---|---|
| R.02 accepted (Gate 1) | Not accepted; evidence run recorded | [docs/41](41-r02-end-to-end-evidence.md) |
| Provider record: provider, model, dialect, usage shape, permitted fields, deadline and errors, adapter owner, call and budget permission, credentials handling | Drafted for the course proxy in docs/44; base URL, exact model name, VPN or proxy needs and quota unknown until the connection guide is supplied | docs/44, Provider record; [C2 candidate README](../experiments/c2_risk_candidate/README.md) |
| Data flow (F.07): field allowlist, redaction, retention | Defined for the Coordinator extraction only; Assessment and reviewer inputs not yet defined | docs/44, Data flow |
| Trusted latency events (start, ready, wait) | Open E.01/E.09 item for C; analytics latency stays Tier 0; C's answer of 22 October 2026 on the Tier 1 candidate: keep Tier 0 until the episode/readiness mapping is resolved ([evaluation candidate README](../experiments/evaluation_candidate/README.md#22-october-f06-tier-1-technical-disposition)) | [docs/43](43-f06-analytics.md) |
| Pilot (R.03) | Not started; depends on A1.08 | [docs/08](08-delivery-work-packages.md), R.03 |
| Model audit trace | The planned MODEL-actor audit event is withheld because the label-artifact claim compares case head and audit rows across transactions; needs a status-gated design and PostgreSQL tests | docs/44, Audit event: withheld |

## 5. A3 logistics sandbox (OF-004)

- A3 is A's selected optional: an independent logistics provider sandbox or test-mode adapter ([docs/07](07-frozen-work-allocation.md)).
- Status: **unmet**. The team has no Australia Post or StarTrack contract or test account, and an ordinary developer or student account is not testbed access ([docs/11](11-stage1-readiness.md), section 2; [docs/17](17-logistics-sandbox-feasibility.md)). No call to that API has been made.
- A3.01 asks that, without access, the external dependency is recorded and a reviewable alternative is put to the tutor; the core mock is not renamed as a completed OF-004. R.05's acceptance asks that an unresolved external permission is recorded explicitly as unmet with the tutor's disposition, and not assumed accepted ([docs/08](08-delivery-work-packages.md), A3.01 and R.05).
- Tutor disposition: **none recorded in the repository** as of 22 October 2026. Action for A: ask the tutor how A3 should be treated for Stage 2 and record the answer, with its date, in the [submission runbook](47-stage2-submission-runbook.md) known-gaps list.
- A3.02 cannot start before A3.01 and R.02 are accepted; A3.03 follows A3.02.

## 6. C3 image evidence (OF-001)

C3 is C's selected optional. C3.01 starts only after R.03 (the Gate 2 pilot), and C3.02 / C3.03 follow it ([docs/08](08-delivery-work-packages.md), C3). Because R.03 depends on A1.08, C3 has not started and is not part of the Stage 2 submission. The C2 candidate already accepts optional synthetic image observations as reviewer input, which is not a vision model ([C2 candidate README](../experiments/c2_risk_candidate/README.md)).

## 7. Deferral decisions of 22 October 2026

| Decision | Content | Reasons (from docs/08, docs/28 and the Stage 2 rubric) |
|---|---|---|
| Morning: defer the Gate 2 model roles past 1 November 2026 (Jira KAN-39) | The Stage 2 submission is the Gate 1 scope: the R.02 no-model chain, the A2.07 decision interface, F.06 analytics, B's frontend and C's retrieval and evaluation material. A1.06 / A1.07 / A1.08, the real C2 reviewer, E.09 and E.12 move to this roadmap. No model is connected to the execution chain. | The docs/08 Gate 1 rule (no model in the execution chain before R.02 passes) while R.02 has no acceptance; the S/F chain A1.08 -> R.03 -> E.12 cannot complete before the 1 November source deadline. |
| Afternoon: build one advisory model showcase outside the execution chain | Default-off typed extraction of the customer statement for the Founder view only (A1.06 extraction half), fail-closed, recorded as the lead's dated exception in docs/44 (PR #94). Everything else in the morning decision stands. | The Stage 2 rubric gives 4 of 20 marks to AI agent capabilities and the Project Description asks to show how the model enhances perception, decision-making and interaction; the course provides a model endpoint (Lab 9, [docs/28](28-stage2-submission-checklist.md)); the showcase holds no execution authority, guard path or approval path. |

These decisions do not change docs/08: Owners, Reviewers, S/F dependencies and acceptance texts stay as they are, and the deferred items remain open, not cancelled.

## 8. Hardening backlog from the review of 23 October 2026

Three independent read-only reviews of main on 23 October 2026 (decision boundary; customer, privacy and notification paths; analytics, driver and deployment tooling) found no exploitable authorization, upload, token or notification defect. The small fixes landed the same day (LF attributes, the API statement timeout, the R04 probe, `demo.py` error reasons, the interrupted driver receipt, strict query integers). The structural findings are scheduled after the 1 November submission because each changes a shared read path or a guard and needs its own PostgreSQL tests; they are tracked in GitHub issue #106 and are listed in [docs/47](47-stage2-submission-runbook.md) section 7 as known gaps:

| Finding | Why it is deferred | Direction |
|---|---|---|
| Every customer case view scans the whole audit table for notification markers and fails closed with 409 above 16,384 audit rows (a few thousand cases) | Changes `history.case_view` and the notification marker discovery used by 36 guard modules | Scope marker discovery to the case with an index; keep the per-case bound; pin with a test that lowers the limit |
| History snapshots and cursors are inserted on every read and never pruned | Touches the retention sweep and the read path | Prune expired rows in the sweep; test that reads do not grow the tables without bound |
| Customer reads take the global exclusive fence because of those inserts | Follows from the previous item | Shared fence for reads once the inserts move |
| Clarification rounds have no cap | New typed refusal in the customer contract path | Documented cap with a test |
| Authority loss during a decision's service body is reported as 409 rather than 401/403; replay receipts are JSON-equal but not byte-identical; acceptance facts store 200 for the 202 route | Consistency, no data or safety effect | One PostgreSQL test each, then the mapping and `sort_keys` changes together |

## 9. Cloud deployment (decided 30 October 2026)

On 30 October 2026 the lead asked whether the demonstration could run on Railway. The first answer, recorded here in #156, was "not for Week 13". Later the same day the lead decided to use Railway for the Week 13 demonstration and to keep the local deployment of PD-02 as the fallback. This section records that decision and how it was carried out.

The rule of the Stage 2 Marking Criteria still holds: the source is downloaded from Canvas and deployed on site ([docs/47](47-stage2-submission-runbook.md) section 1). At the venue, the downloaded folder is deployed with `railway up`, so Railway builds the downloaded package. Two things are added to the deployment slot: the venue network and a remote build. If either fails, the presenter double-clicks `tools/demo/start-demo.cmd` instead ([README, Demo machine script](../README.md#demo-machine-script-windows)).

| Area | Before (PD-02 only) | Railway (PD-03, [docs/15](15-package-deployment-models.md) section 4.1) |
|---|---|---|
| Demo API | `demo.py serve` binds `127.0.0.1` only | Unchanged: it still binds loopback inside the container, and Caddy in the same container is the only public listener |
| Web frontend | The Vite dev server proxies `/v1` and `/health` to `127.0.0.1:8000`; the API registers no CORS middleware | A production build served by Caddy on the same origin as `/v1`, so no CORS is needed (`tools/railway/Caddyfile`) |
| Database | Compose PostgreSQL 17 on loopback; the password lives in the ignored `.env` | PostgreSQL 17 as a Railway image service, the same image as Compose (Railway's own template was PostgreSQL 18, where migration 0010 refuses); its `DATABASE_URL` stays a platform variable. Each start drops and creates `returnops_f02`, then migrates (`tools/railway/start.py`) |
| Demo identities | `demo.py provision` on the machine | `demo.py provision` inside the container at each start. The sessions are copied to the presenter's machine through `railway ssh` and never shown (`demo.ps1 cloud-tokens`) |
| Exposure | Loopback only | A public HTTPS address with synthetic data only; the service runs only for the rehearsal and the demonstration (NFR-003, NFR-009) |
| Models | PD-02 | PD-03 added in docs/15 |

What is not on Railway:
- S4's live model showcase: the course proxy is on a private VPN address that the platform cannot reach, so S4 uses its fallback wording.
- S5's R.02 driver: it runs on PD-02.

Owner: A. Still open: a real Railway run from the Canvas download (rehearsal pass 2), and rate limiting for the public address.

AI-assisted implementation and metadata preparation; author shuxiachai.
