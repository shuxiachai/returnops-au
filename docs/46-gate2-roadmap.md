# Gate 2 roadmap and deferred scope

Owner: A Jingbo Chai. Work package R.05 ("Stage 2 final course delivery, demo and follow-up route") in the unchanged [work packages](08-delivery-work-packages.md) (Owner A, Reviewer C; start E.12; finish R.04, A3.03, B3.03, C3.03). This page states what the Gate 1 scope delivered for the Stage 2 submission, what Gate 2 would add, what must be true before it starts, and the status of the optional features that are not delivered. It records no acceptance of any work package or Gate and changes no Owner, Reviewer or S/F value. Written 22 October 2026 (Sydney).

## 1. What the Gate 1 scope delivered

Delivered means merged into main with its own CI record, or published for merge where stated. It does not mean accepted.

| Item | Document | State on 22 October 2026 |
|---|---|---|
| R.02 no-model end-to-end run: customer HTTP case, synthetic order, fixed proposal, controlled PASS receiver and risk stub, Founder HTTP approval after negative tests, simulated return, label, PDF and mock notification, audit read-back; demo mode for the live demo | [docs/41](41-r02-end-to-end-evidence.md) | PR #89 merged; first result CI run 39634415393, receipt `PASSED`, 32 of 32 checks; demo mode merged with PR #93 (offline tests only) |
| Founder decision HTTP boundary (A2.07): the frozen decision POST behind an explicit flag | [docs/40](40-founder-decision-http-boundary.md) | In main; A2.07's PR #78 was merged on 22 October 2026 ([docs/41](41-r02-end-to-end-evidence.md)) |
| F.06 Founder analytics read API | [docs/43](43-f06-analytics.md) | PR #90 merged; latency Tier 0 (no samples) |
| A1.06 advisory Coordinator showcase (extraction half only, default off, outside the execution chain) | `docs/44-coordinator-showcase.md`, added by [PR #94](https://github.com/shuxiachai/returnops-au/pull/94) | Draft PR #94, pending merge; first live result pending |
| B's web frontend (customer portal, Founder console, analytics page) | [apps/web README](../apps/web/README.md) | PR #60 merged; live decisions and live analytics still refused in the client until Issue #91 is done |
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
| Trusted latency events (start, ready, wait) | Open E.01/E.09 item for C; analytics latency stays Tier 0; a Tier 1 candidate awaits C's agreement | [docs/43](43-f06-analytics.md) |
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

AI-assisted implementation and metadata preparation; author shuxiachai.
