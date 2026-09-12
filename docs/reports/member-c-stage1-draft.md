# Member C — Stage 1 report contribution draft

> **MC-RPT-0.1, 2026-09-12; AI-assisted preparation, not an accepted contribution statement.** This refines Chapter 8/Figures 21–23 and relevant evaluation/provenance sections of the existing [Stage 1 Team Review Draft](https://docs.google.com/document/d/1xvGO8EA_yZwWj1It3UM7AKDFEoQjsj5eJJXbCz4bcnc/edit). It preserves that source's preparation history rather than claiming first authorship. Technical reference is F.01 rc.5 at [`64582a3007fea0fa3d1b1c3c212168b96af6b607`](https://github.com/shuxiachai/returnops-au/tree/64582a3007fea0fa3d1b1c3c212168b96af6b607), PR #11. The new C artifacts are a later candidate and have separate validation evidence.

Integration owner A; personal owner C, reviewer A. B integrates the shared model index using C's classification/traceability contribution. C must personally review, revise and explain these materials before describing them as an individual assessed contribution. This document supplies no member signature, tutor acceptance, Gold result or completed runtime claim.

## 1. Project updates relevant to C

The latest reviewed source is not the old main rc.2 contract. PR #11's rc.5 package contains fifteen planned public business operations, strict role-isolated history/material, bounded previews, retention-aware receipts, and a health-only environment. Its publication does not mean the business APIs, Risk Reviewer, retrieval or Founder execution workflow are implemented. Main publication, CI, contract acceptance and personal model acceptance remain different facts.

Two important rc.5 distinctions constrain C's design. First, a valid-shaped RiskReviewRequest must also preserve complete original retrieval conflicts, independent material and exact citation-check bindings. A page preview is not a full review input. Second, business escalation, technical failure and pre-proposal order-provider conflict/authority denial are different paths. Only an actual no-proposal ProcessingFailure or OrderLookupBlock creates a manual-only decision target. A proposal-level ESCALATE can still be revised through a valid Founder REQUEST_REVISION, but cannot be directly approved for execution.

C's fixed deliverables remain C1 versioned retrieval/citation verification, C2 independent risk review and selected optional C3 image observations after the text workflow is stable. Evaluation coordination and Jira evidence checks do not substitute for either core feature. A maintains Jira and integrates/submits the report/video; C supplies this material and verifies R.04 evidence. Each member owns tests for their own implementation.

## 2. Sources, requirements and limitations — report-ready summary

The design uses a frozen desk-research register rather than claiming interviews or market validation. The [register](../06-requirements-desk-research-evidence.md) has a 25 August 2026 research cut-off. Its sources inform requirements; their claims, limitations and dates should remain visible in the final report. This summary does not expand the register or give legal advice.

| Source family in the frozen register | Design consequence | Qualification |
|---|---|---|
| EVD-003–005: reviewed ACCC policy/remedy/evidence guidance | Distinguish store policy from reviewed consumer guidance; preserve conflicts; use conditional proposals and reasonable evidence alternatives; FR-004–008 | Guidance informs project scenarios; the AI does not make a final legal-entitlement or major/minor-failure determination |
| EVD-007–012: platform, returns/logistics and notification references | Typed replaceable providers, separately checked authority, effect identity, simulated outcome and clear next steps; FR-003/009/010/012 | Core mock evidence is not production capability, and cannot be counted again as A3's independent test adapter |
| EVD-013–015 and scoped platform controls: privacy/data handling | Minimise model inputs, use synthetic data, distinguish content retention from non-personal audit integrity; FR-011/NFR-003/009 | Project privacy-by-design is mandatory governance; merchant-specific legal applicability is not determined |
| Course rubric, Lab 3 and frozen allocation | Personally explain AH/UC/activity/interaction/state chain and identify shared contribution | AI assistance and a rendered diagram alone do not satisfy personal contribution or non-author review |
| HYP-001–003 and project governance | Controlled student timing, 30-case Gold comparison, explicit latency/citation/risk targets | Targets and hypotheses are not measured results, industry benchmarks or merchant-efficiency claims |

For C, FR-006/NFR-001 are functional grounding and traceability requirements; FR-008/NFR-009 specify independent risk and robustness; FR-011/012 support explainable authorised history. BR-002/005 prohibit silent resolution of a blocking source conflict and confidence-based bypass. C's [classification table](../18-member-c-model-chain.md#8-cs-requirements-classification--traceability-hand-off-to-b) gives B exact model and planned verification links without taking over B's index.

The small runtime corpus is distinct from this research appendix. It contains only reviewed passages needed for the three supported categories: faulty/quality issue, wrong item and change of mind. Synthetic store policy is labelled as synthetic. Keyword/BM25 is the initial retrieval choice because it is inspectable and inexpensive; vocabulary mismatch remains a limitation. Broader web crawling, vector/hybrid retrieval and research-platform features are not required for this delivery.

## 3. C's model argument

AH-08 asks the system to show material source conflicts and hand an unsafe proposal to the Founder. [MC-0.1](../18-member-c-model-chain.md) connects this requirement to detailed UC-02 and UC-05 specifications and three editable behaviour models:

- [MC-ACT-0.1](../diagrams/member-c/member-c-activity.svg) separates retrieval, proposal/bundle acceptance, independent scrutiny and five-outcome routing.
- [MC-SEQ-0.1](../diagrams/member-c/member-c-sequence.svg) shows Orchestrator obtaining accepted original material from Domain and invoking C2 independently of Assessment.
- [MC-SM-0.1](../diagrams/member-c/member-c-state.svg) follows conceptual ProposalReview work, distinguishing an untrusted pending candidate, an accepted immutable RiskReview and retained historical validity.

Citation verification and claim-support review answer different questions. C1 can prove that a reference resolves to the expected document/version/location/hash but cannot thereby prove that the passage supports the recommendation. C2 compares the actual claim with the original statement, read-only order facts, authorised evidence, source passages and preserved conflicts. It uses a separate prompt and invocation and does not consume Assessment's hidden reasoning. The evidence matrix remains a generator interpretation, not an independent fact.

Domain assembles and validates the complete bounded HistoricalProposalBundle before accepting a new current proposal. It must neither silently truncate necessary material nor reconstruct deleted content. Every accepted review binds case, input, proposal ID/version and corpus, with restricted model/prompt/invocation provenance. PASS and PASS_WITH_WARNING allow consideration for Founder review only. REVISE requires a new proposal and review; NEEDS_INFORMATION returns through the authorised clarification path; ESCALATE prevents direct execution approval. Typed technical errors are never converted into PASS or a sixth business outcome.

The same-version retry design carries forward the shared report's concurrency proposal: every state-changing reply, validation, timeout, retry, exhaustion and retirement event must atomically match selected work/round/invocation. In recovery, it matches the selected failed invocation before selecting a replacement. A late round-1 timeout cannot retire round 2 or change its business audit outcome. These internal correlation guards add no public wire fields; A/C confirmation and runtime concurrency tests remain required.

UC-05 provides a complementary audit view. Founder history uses exact typed historical material, not current sources joined to old results. Previews are bounded and complete paging begins at the prescribed cursor. Every page checks current permission and fixed snapshot/query binding; legitimate removal returns a tombstone even under an older cursor. Customer history has a distinct safe schema, not hidden Founder data. This model/spec work belongs to C, while dashboard implementation remains B's and API/storage/auth remain A's.

## 4. Three explanations C must personally rehearse

**Pass (MC-T01).** A synthetic request has usable order evidence and supporting reviewed passages. C1 returns their provenance and correct citation checks. Domain accepts a complete source bundle; C2 independently returns PASS; Domain accepts it only for the current selected invocation. The Founder can review the packet but there is still no ApprovalRecord or provider permission. Point to C04/C06/C07 and explain why JSON-valid is not trusted.

**Source conflict (MC-T02).** Synthetic store policy and reviewed guidance disagree on a material criterion. Both original passages and the conflict survive retrieval and the independent input. If no safe recommendation can be supported, C2 returns ESCALATE with a BLOCK finding. It is not a provider OrderLookupBlock or technical failure. The escalated proposal can be revised or handled manually under UC-03; it cannot simply be approved. Point to C10 and BR-002, then explain what a genuinely non-blocking warning would change.

**Clarification (MC-T03).** C2 identifies missing relevant evidence and returns NEEDS_INFORMATION with a specific question. Coordinator requests it through UC-01E. Only a valid current question-set answer is accepted; it appends to history and changes input_version. The new packet gets another independent review and the old PASS, if any, is historical. Point to C09 and the ACCEPTED→HISTORICAL transition; explain why arbitrary new upload does not create an allowed post-review append path.

Also rehearse MC-T09: round 2 is selected after a timeout, then round-1 reply/timeout/retry/exhaustion arrives. Explain the atomic identity test for every event, not only successful replies. State clearly that this is a proposed design, not a concurrency guarantee measured by this work.

## 5. Evaluation protocol — prepared explanation, not execution evidence

Required comparison: **B1**, a single LLM without retrieval or operation authority, versus **B4**, the full governed architecture using retrieval, separate risk review and deterministic gates. Use the same underlying model and frozen inputs, retaining that intended architecture difference. The result compares a bundle of interventions; it does not isolate a causal benefit of multi-agent decomposition. Experimental B2/B3 and expansion to 100 scenarios are portfolio work, distinct from member B's feature IDs.

The protocol remains **30 Gold cases**, a **20-case stratified timing subset drawn from those same 30**, and a separate **10–20-case development pilot**. This candidate creates no Gold labels, reads no timed answers and claims no sealing event. Execution must follow the fixed order:

1. Define label guide, denominators, acceptable answer sets and pilot/Gold separation (E.01). C seals all 30 initial labels, reasons, source references, versions/hash and timestamp **before reading any timed answer**, including as reviewer of E.03. The E.02 receipt shown to A/B contains no labels.
2. A and B independently process the same 20 inputs in separately fixed/randomised orders, without Gold labels, the other's answers or Gold-based scoring feedback. Lock both outputs before disclosure; record active time and pause rules.
3. C formally hands over the previously sealed labels only after both timed runs. A reviews each case; B arbitrates unresolved disagreement. Preserve initial labels, edits and source-based reasons; do not adjust reference labels to match timed answers.
4. Freeze the final Gold hash before scoring either human output or formal system output. Freeze corpus, prompts/model/provider/config, scoring code, environment and source commit. Do not tune on Gold or change labels after inspecting comparative scores.
5. E.09 verifies runner/adapters with labelled pilot or explicit stub fixtures. R.03 later verifies complete B4 after the safety spine; stub output is not Gate 2 evidence. E.12 formal comparison depends on the original E/R prerequisites.

| Metric / quantity | Target or defined denominator | Status in this candidate |
|---|---|---|
| Citation coverage / correctness | 100% / ≥90%; report supported/checked claims and frozen denominator | PROTOTYPE_TARGET, not measured |
| Risk recall / specificity | ≥95% / ≥80%; report TP/FN/TN/FP and positive/negative definitions | PROTOTYPE_TARGET, not measured |
| Proposal latency | p95 <120s, from accepted complete input to stored review-ready proposal; include machine revision, exclude human/physical waiting | PROTOTYPE_TARGET, not measured |
| Latency population | Current input's latest episode; successful measurement, technical failure and unmeasured counts are separate and sum to case count | Planned reconciliation, not a dashboard result |
| Safety / duplicate effects | 100% unauthorised-operation blocking, zero duplicate effects | Runtime targets; schema/static models cannot demonstrate them |
| Human baseline | Per-operator and pooled median/IQR, omissions, order and learning effects | No timings collected by this task; not merchant or end-to-end efficiency |
| System comparison | Raw counts, confusion matrices, failures, p50/p95, calls/tokens/cost and exact versions | No formal B1/B4 run claimed |

An ESCALATE result with complete review-ready material can be a successful latency measurement without a passing risk outcome. A technical failure is not the same as a no-proposal business order block; the latter without a review-ready timing is unmeasured, not a fabricated technical failure. All percentages on 30 cases require raw counts and small-sample qualification.

## 6. Prepared evidence and remaining work

| Artifact / evidence | What it supports | What it does not support |
|---|---|---|
| C specs, three editable UML sources/SVGs, twelve static walkthroughs | Reviewable personal-chain candidate and traceability contribution | C's independent understanding, A's acceptance or runtime behaviour |
| rc.5 schema/examples and reported base CI | Reference artifact and health-only environment checks at their recorded SHA | Coverage of these new diagrams or implemented retrieval/risk/business API |
| C's independent environment/review records, when attached by the delivery task | Only the exact commands, environment and observations they contain | Gold evaluation, all F.01 acceptance or proof of model semantic correctness |
| Label/metric explanation above | Evaluation protocol, leakage precautions and target definitions | An executed seal, timed baseline, reviewed Gold set or measured improvement |

C's remaining Stage 1 personal actions: review these exact files, explain the three main examples and stale-round guard, record meaningful personal edits/decisions, confirm shared classification contribution with B, and obtain A's non-author review. A/C must resolve the lifecycle/design questions and F.01 hand-off; these files do not make a signature on C's behalf. The R.04 evidence audit must separately check current course instructions, model index, AI acknowledgement, report/video and submission receipt. A's final course submission may honestly disclose open internal acceptance items rather than waiting past a deadline.

Later C-owned implementation remains C1 retrieval/citation, C2 independent reviewer and their own tests; C3 authorised image observations follows the stable text workflow. Inputs that exceed capacity, removed provenance, stale invocation events, unsupported claims, five routing branches, prompt injection and invalid model outputs need actual tests. The case/API/orchestrator/approval/history work remains A's; UI/E2E work remains B's.

## 7. Truthful contribution / AI assistance record to complete

| Required record | Current entry |
|---|---|
| Prior source | Shared Team Review Draft Chapter 8, Figures 21–23 and evaluation/provenance sections; rc.5 project documents |
| This preparation | AI-assisted extraction/refinement into editable repository model/spec/report candidates, with stated validation scope |
| C's personal decisions and revisions | Pending C: exact decision, reason, changed file/version and date |
| C's own explanation / demonstration | Pending C: walk MC-T01/02/03/09 without agent answering on C's behalf |
| A's non-author review | Pending A: exact artifact revision, findings and resolution |
| B's index integration | Pending B: preserve C's classification/model contribution and existing B material |
| Final AI acknowledgement | C/A adapt to actual course instructions and actual assistance; do not claim unaided authorship |

Suggested disclosure to adapt truthfully: “AI assistance was used to inspect reference material, draft/refine specifications and editable UML, check model consistency and organise evidence. The prior shared report discussion candidates are acknowledged. Each student's actual decisions, revisions, tests and explanations are separately identified; automated checks do not substitute for personal understanding, non-author review or runtime verification.”

## 8. Interview and video cues

Use readable zoomed SVGs instead of shrinking the full sequence into one frame. A integrates/records/submits the team video under the existing arrangement; C supplies personally confirmed material and retains the individual interview obligation. No duration booking or recording is asserted here.

- What does AH-08 require beyond displaying two citations?
- Can a citation be structurally valid but fail to support a claim?
- What makes C2 independent, and what biases can remain despite a separate invocation?
- Why is ProposalReview work phase different from RiskReview.outcome and ReturnCase.status?
- How does a stale timeout differ from a stale successful reply? What must be atomic?
- Why is ESCALATE not always a technical failure, and when is the no-proposal target manual-only?
- Why cannot a history preview or removed source content substitute for full review input?
- Which C features are currently implemented versus modelled? Which tests still need a real runtime?
- When must C seal labels, and why is the 20-case timing subset not a second Gold dataset?
- What can B1-vs-B4 show, and why can it not isolate the causal effect of multiple agents?

The final answer to each question must reflect C's understanding and the exact reviewed version, not simply repeat this prepared draft.
