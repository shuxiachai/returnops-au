# 50. Design change of 1 November 2026: advisory AI roles in Stage 2, and the Gate 2 plan

Owner: A Jingbo Chai (lead). Recorded on 1 November 2026 (Sydney), before the Stage 2 source deadline. This is a dated design decision with its reasons and a first measurement. It does not change the submitted Stage 1 report, [docs/00](00-project-definition-v1.md), contract v1 or the frozen allocation ([docs/07](07-frozen-work-allocation.md)), and it accepts nothing.

## 1. What the Stage 1 design says

- Three AI business roles, the Customer Case Coordinator, the Returns Assessment role and the Compliance and Risk Reviewer, produce a cited decision packet and an independent review that gate the Founder's decision ([docs/00](00-project-definition-v1.md), section 4).
- The requirements carry measured acceptance:
  - FR-002: mandatory-information recall of at least 95%;
  - FR-008: risk-escalation recall of at least 95% and specificity of at least 80%;
  - the formal 30-case Gold comparison of B1 and B4 (E.12).
- The Gate rule of [docs/08](08-delivery-work-packages.md) ([docs/46](46-gate2-roadmap.md), section 2): no model output may feed a proposal, a review, an approval, a preview or an operation before Gate 1 is accepted. Gate 2 connects the roles after that and validates them.

## 2. What Stage 2 delivers instead

The governed chain runs with deterministic parts, as Gate 1 defined:

- the fixed placeholder proposal;
- the controlled PASS receiver, which S5 and the R.02 driver use;
- Founder approval;
- simulated return, label, PDF and notification.

The three roles run live and advisory, on the Founder's request and in the order of docs/00, together with the C3 photo check:

| Role | Live since | Pull requests |
|---|---|---|
| Coordinator facts card | 22 October 2026 | #94 |
| C2 risk review | 1 November 2026 | #176, #178 |
| C3 photo check | 1 November 2026 | #177 |
| A1 assessment draft citing a synthetic store policy | 1 November 2026, evening | #182, #184 |

Each later role reads the earlier roles' latest output: the review reads the facts card, the photo check and the assessment draft. Nothing they return is recorded or moves the case (`recorded: false`). The Founder decides.

## 3. Why

1. **The design's own acceptance asks for evidence first.** The design lets a model output gate a decision only after measured evidence, and none exists yet:
   - E.01's definitions are frozen;
   - the 12-case pilot is planned but has not run;
   - the 30 Gold cases are not labelled, and labelling them needs the three members, sealed before any model answers.
2. **Connecting a model changes the reviewed core.** The governed chain re-verifies the review's provenance at every step: approval, execution preparation, label and notification (`pass_review_sources.py` and its callers). Connecting a model is a reviewed change to that core, covered by hundreds of PostgreSQL tests in the fifteen CI parts. It could not be made safely before the 23:59 source deadline of 1 November 2026, the evening before the demonstration.
3. **The first measurement says the reviewer is not ready** (section 5).

## 4. Gate 2 plan, after the submission

| Step | What | Who | Exit criterion |
|---|---|---|---|
| 1 | Label the 30 Gold cases under E.01, sealed before any model answer | A, B and C; C coordinates | 30 labelled cases, frozen |
| 2 | R.03 pilot: 12 cases through the live roles; fix prompts and parsers | A and C | Every role answers in shape; rejections explained |
| 3 | E.09 and E.12: B1 against B4 on the Gold set, with recall, specificity, rejections, latency and cost | C, with A | The FR-002 and FR-008 thresholds, reported with raw counts |
| 4 | Shadow mode: record each AI draft and review next to the Founder's decision, non-authoritative, with model and prompt versions in the audit | A | Needs the withheld model audit event design ([docs/46](46-gate2-roadmap.md), section 4) |
| 5 | Connect, only when step 3 meets the thresholds (detail below) | A, C reviews | The Founder stays the only approver; no model path to a provider |
| 6 | C1 retrieval and citation checks in the runtime, and the C1.04 excerpt check | C, A reviews | As in docs/46, section 3 |

Step 5, connecting, means three changes:

- a trusted receiver for model reviews, with all five outcomes routed;
- an Assessment producer in place of the fixed proposal, with the evidence matrix and C1's retrieval and citation checks;
- approval and execution provenance checks extended to the new sources.

## 5. First measurement: development check on C's ten E01 examples

Run on 1 November 2026 at 21:10 Sydney.

**Setup**

- **Examples:** C's ten development examples, [e01_development_examples.json](../experiments/evaluation_candidate/examples/e01_development_examples.json): invented, public, and labelled by C's proposal (`C_PROPOSAL_PENDING_A_REVIEW`). They are not Gold.
- **Where it ran:** inside the Railway service with `qwen-plus`, once, through [tools/gate2/e01_development_check.py](../tools/gate2/e01_development_check.py). The model key stayed in the service, and the output holds categories, outcomes and timings only.
- **Prompts:** Coordinator `a106-coordinator-showcase-v1`; reviewer `c2-risk-review-advisory-v3`.
- **Adapted reviewer inputs:**
  - the example's candidate sketch is passed as the proposal's rationale;
  - its order text is passed as one order line;
  - its policy and passage texts are passed as an extra `guidance_sources` field.

**Results**

| Measure | Coordinator | Risk reviewer |
|---|---|---|
| Matches C's proposed label | Issue category 10 of 10 | Acceptable outcome 2 of 10 |
| Answers discarded by the fail-closed parser | 0 | 5 (3 broke C2's outcome conditions, 2 had an over-long or empty item) |
| Expected escalations found | | 2 of 3 (the third answer was discarded) |
| Non-escalation cases kept below ESCALATE | | 3 of 7 (the other 4 answers were discarded) |
| Time per answer | 2.3 to 4.0 s | 6.5 to 11.1 s |

**Per example**

| Example | C's category | Coordinator | C's acceptable review | Reviewer |
|---|---|---|---|---|
| DEV-E01-01 | FAULTY_OR_QUALITY_ISSUE | same | PASS | REVISE (CITATION, SUPPORT and CONFLICT warnings) |
| DEV-E01-02 | FAULTY_OR_QUALITY_ISSUE | same | NEEDS_INFORMATION | REVISE |
| DEV-E01-03 | WRONG_ITEM | same | PASS | discarded (LENGTH) |
| DEV-E01-04 | CHANGE_OF_MIND | same | PASS | discarded (OUTCOME) |
| DEV-E01-05 | UNCLEAR | same | NEEDS_INFORMATION | REVISE |
| DEV-E01-06 | FAULTY_OR_QUALITY_ISSUE | same | ESCALATE | discarded (OUTCOME) |
| DEV-E01-07 | FAULTY_OR_QUALITY_ISSUE | same | ESCALATE | ESCALATE (INJECTION, AUTHORITY, CONFLICT) |
| DEV-E01-08 | OUT_OF_SCOPE | same | ESCALATE | ESCALATE (SCOPE, AUTHORITY, CONFLICT) |
| DEV-E01-09 | FAULTY_OR_QUALITY_ISSUE | same | REVISE | discarded (LENGTH) |
| DEV-E01-10 | WRONG_ITEM | same | PASS_WITH_WARNING | discarded (OUTCOME) |

**What it shows**

- The Coordinator's classification is ready for the pilot.
- The reviewer is not ready. On visible examples it reaches neither FR-008 threshold, and three of its accepted answers chose REVISE where C expected PASS or NEEDS_INFORMATION. The adapted input, which carries the proposal only as text, may push it that way; the pilot has to separate the two.
- The fail-closed parser stopped every answer that broke C2's rules, so none reached the Founder in a wrong shape.

**Limits**

- Ten visible examples with proposed labels, one run, and adapted inputs.
- Not E.12, not Gold, and not evidence for or against acceptance.

### After prompt v4 and one corrective retry

Run on 1 November 2026 at 21:31 Sydney, three times. It ran inside the Railway service with `qwen-plus`, the reviewer prompt `c2-risk-review-advisory-v4` and the retry of `founder_assistant._ask`, both carried in the script before they were deployed. Inputs were adapted as above, and the service's unchanged `parse_risk_review` judged every answer. The v3 columns are the first check above (21:10) and a read-only diagnosis run of the same inputs (21:27).

| Reviewer measure | v3, 21:10 | v3, 21:27 | v4 with retry, runs 1 / 2 / 3 |
|---|---|---|---|
| Acceptable outcome (of 10) | 2 | 4 | 4 / 4 / 4 |
| Answers kept (of 10) | 5 | 9 | 9 / 10 / 10 |
| Of those, kept only after the retry | | | 1 / 1 / 3 |
| Expected escalations found (of 3) | 2 | 2 | 3 / 3 / 3 |
| Non-escalation cases kept below ESCALATE (of 7) | 3 | 6 | 6 / 6 / 6 |
| Slowest answer, retry included | 11.1 s | not timed | 20.0 s / 19.1 s / 19.3 s |

**What it shows**

- Escalation now holds on these examples: every expected escalation was found in every run, including DEV-E01-06, the unresolved source conflict, which v3 missed twice.
- The retry turns most discarded answers into kept ones. It costs one more call (up to about 20 s), and a second discarded answer is still a 503.
- The acceptable rate did not move. Cases C labels PASS or NEEDS_INFORMATION mostly came back REVISE. The adapted input gives each proposal only as C's one-line sketch of it, so asking for a revision is a reasonable reading. A fair test of the reviewer needs the runtime's own structured proposals, which is what the pilot (step 2) is for.
- One new false escalation: DEV-E01-05, an unclear request that C labels NEEDS_INFORMATION, was escalated in two of the three runs. DEV-E01-10 came back PASS each time where C labels PASS_WITH_WARNING.
- The same limits apply: ten visible examples with C's proposed labels, adapted inputs; not Gold, not E.12.

## 6. Records

- Jira: KAN-39 (the 22 October 2026 deferral) and KAN-44 (the A1 assessment draft).
- [docs/46](46-gate2-roadmap.md) remains the roadmap. This page records the 1 November 2026 decision and the first measurement.

AI-assisted implementation and metadata preparation; author shuxiachai.
