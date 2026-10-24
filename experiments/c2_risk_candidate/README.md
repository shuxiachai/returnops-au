# C2 independent risk-review candidate

Tracking: [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) /
[Issue #66](https://github.com/shuxiachai/returnops-au/issues/66).

Offline preparation for **C2.01–C2.05**, `FR-008`, `NFR-001/002/009`,
`AH-08 → UC-02 → Grounding/Risk Activity, Assessment–Reviewer Sequence,
ProposalReview state model`. C owns this component; A reviews and integrates.
This is not a live LLM, Gate 2, feature acceptance or semantic-quality result.

## Current status — 24 October 2026 (Sydney)

[Issue #123](https://github.com/shuxiachai/returnops-au/issues/123) tracks this
C-owned documentation/demo follow-up; KAN-41 remains the active handoff card.
The older dated entries below describe their own source and publication time.

- A approved [PR #118 at `f3c4bb42`](https://github.com/shuxiachai/returnops-au/pull/118#pullrequestreview-5629076842)
  and adopted it as `46a8afaa`; [CI 39936383045](https://github.com/shuxiachai/returnops-au/actions/runs/39936383045)
  finished **13/13 successful jobs**. #116/#117 and #119 are also merged.
  #119's exact-source CI was 13/13; its CLI now distinguishes a business result
  from unfinished cleanup. These receipts supersede the pending states below.
- A's [portability finding](https://github.com/shuxiachai/returnops-au/pull/118#issuecomment-6366377086)
  is addressed in C's matrix script by resolving the synthetic private/output/
  identity paths before passing them to the real CLI. This matches the CLI's
  Windows drive qualification. No files are created at those synthetic paths.
  Native Windows re-verification remains with A; a macOS pass is not a Windows
  run. The old saved matrix JSON remains evidence for #116, not a new result.
- C's local macOS recheck against the unchanged driver from main
  `e424f6d2283a51e0f9b031d7a3a395fcebed8c0b` passed **22 matrix rows** and
  **68 driver/demo-mode offline tests**. The S6 selection below passed four
  tests. These are overlapping preparation checks, not new business cases.
  The first driver-test command used an old editable-package lookup and failed
  collection; using this checkout's `PYTHONPATH=apps/api:packages` passed without
  an implementation change. Both logs are retained in the local checkpoint.
- R02-C-02 remains open for full OS/process/second-interruption and actual
  PG/browser failure coverage. The in-memory matrix is shared R.02/E.10 review
  support, not an extra completed C-owned WBS item.
- C2's component contract/handoff is available; real independent Risk and
  semantic-quality evaluation are deferred to Gate 2 / KAN-39 by the 22 October
  planning decision. This is not a course waiver or C2.01–C2.05 acceptance.

### S6 handoff for the Windows demonstration machine

Use the following bounded offline command from the repository root:

```sh
python -B -m pytest tests/contracts/test_c2_risk_preparation.py -k "five_outcomes or blocking_conflict or timeout_and_transport" -q -p no:cacheprovider
```

A reported **4 passed on Windows** in Issue #123. This checks contract-shaped
outcomes, blocking-conflict rejection and technical-error handling with stubs;
it does not run a model or prove that all production consumer routes are wired.
Use the [C1 README](../c1_grounding_candidate/README.md) for the companion
retrieval/citation pilot command. Its citation checks cover an unknown passage,
wrong version, changed text/hash or wrong location, **not a quoted-excerpt or
semantic-support check**. A real reviewer must assess fabricated/support claims;
the current C2 candidate does not itself establish that semantic capability.

E.01 is a **metric-definition draft, not yet reviewed/frozen**, not a completed
label guide. The [evaluation README](../evaluation_candidate/README.md) explains
the optional Mac/Linux pre-generated synthetic bundle. Do not run the secure
evidence/timing/admission commands on Windows or weaken their platform refusal.
Show pre-generated evidence as pre-generated, with exact source and content ID;
do not call it a live result from the submission package. C must still understand,
adapt and time the spoken draft below; no personal rehearsal is recorded here.

### Remaining work and who supplies the evidence

| Area | Existing preparation | Missing before full acceptance / next owner |
|---|---|---|
| C1 | Retrieval/citation candidate and captured-source review packet | A exact-byte admission and trusted corpus pin; C verifies admitted coverage; A integrates authorised runtime inputs |
| C2 | Independent prompt/contract, five outcomes and failure-closed stub tests | Approved provider/data flow and real independent invocation; A post-await/current-state integration; C real pilot and handoff evidence |
| C3 | Separate local mock preparation only; no accepted public runtime | Tutor disposition (A/C), R.03 prerequisite and authorised attachment boundary, then C real image observations and A/B integration |
| Evaluation | Metric/scorer/timing/evidence tools and synthetic rehearsal | A freezes E.01; C seals private labels; A/B blind timing before label handoff; adjudication then real B1/B4 and E.12 evidence |
| Review / Agile | #17/#61/#115/#118 adopted; bounded R.02 reviews | C full R02-C-02 review and R.05 comments; A decides acceptance against exact evidence |
| Personal / final delivery | S6 draft, linked contribution evidence, submission runbook | C own-words explanation and actual contribution/AI-use confirmation; all three rehearse; A packages/uploads and C verifies the final source/download |

The fixed denominator is 20 C-owned Stage 2 WBS rows in docs/08. They have not
all been audited to their original S/F and acceptance criteria, so no accepted
`n/20` or percentage is claimed. Readiness for the reduced near-term demo is
different from satisfying all frozen requirements. Gate 2 deferral does not
close missing Risk, C3, Gold or human-timing evidence. AI-assisted preparation.

## C R.02 follow-up — 23 October 2026, late evening (Sydney)

Tracking: [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41).
A's [new reply](https://github.com/shuxiachai/returnops-au/pull/115#issuecomment-6361803851)
confirms the review-packet adoption, not personal acceptance.

- PR #115 is merged as `33b0a93c`; PR #114 is merged as `55fd717a`.
  Their exact-head CI runs finished with 13/13 successful jobs each.
- C independently ran **110 focused offline tests** against #116 exact
  `aad38db6ce77f0cd108b655d78533a5297d733d1`, then added a
  [22-row in-memory cleanup/receipt matrix](../../docs/reviews/member-c-r02-cleanup-matrix-20261023.json).
  The [reproducible script](../../docs/reviews/member-c-r02-cleanup-matrix-20261023.py)
  covers disposal/log read/screen/write/removal/receipt errors, combined errors,
  and full/reduced/bare/withheld receipts through both CLI modes.
- **These results target #116, not this branch's base main `55fd717a`.**
  That base still fails the withheld-receipt diagnostic. Do not run the script
  against a different source and describe the saved result as its result.
  #116/#117 were still awaiting their final checks/adoption at publication.
- #117's proposed README rearrangement preserves all 44 old section blocks
  byte-for-byte and the 32 delivery-log sections in order. There is no technical
  preservation objection; this is not C's personal sign-off.
- R02-C-02 remains open: ordinary exception paths now have bounded evidence,
  but real OS failure/second-interruption, child/process and PG/browser demo
  evidence and the designated acceptance decision are separate. Cleanup errors
  can retain a business `PASSED` alongside failure codes or
  `private_directory_removed=false`; this is not an all-clean acceptance.
  No A/B implementation or frozen WBS field was changed.

**Final-delivery gap:** this review is shared R.02 support, not completion of
C1/C2/C3. The original 20 C-owned Stage 2 work packages still require a
row-by-row acceptance audit; no completion percentage is inferred from test or
PR counts. Exact-byte corpus admission/runtime wiring, real independent Risk,
R.03 pilot, blind Gold/human timing, C3 image integration, personal S6 and
contribution confirmation, joint rehearsal and final-source submission checks
remain separate evidence obligations. No model, secret access, new local PG
run, personal timing, signature, main merge or Done is claimed here.

AI-assisted C technical preparation. The dated evidence and limitations in
older sections remain unchanged.

## Implemented boundary

`RiskReviewerCandidate.review` validates the existing `RiskReviewRequest`, then
checks exact equality against the current packet and original C1 retrieval
snapshots supplied by trusted orchestration. It checks case/input/corpus and
citation-check coverage, retained statement/attachment references and content
hashes. It never truncates required material. These are local consistency
checks, not proof of database provenance, caller identity or source approval.

The candidate makes one separately awaited call using its own versioned system
prompt. The injected adapter receives immutable JSON, with original statements,
order result, full retrieval/conflicts, citation checks and optional image
observations. The proposal and evidence matrix remain untrusted; there is no
generator hidden-reasoning field. The adapter must be a trusted cooperative
async callable and enforce its own network deadline. A misbehaving adapter that
blocks Python cannot be safely stopped by `asyncio.wait_for` alone.

The model returns risk analysis only. All five outcomes use the frozen wire
schema. Each original conflict requires a materiality disposition and is copied
into a visible finding; materiality is model reasoning, not a keyword rule.
Unresolved blocking conflicts require `ESCALATE`. A nonblocking difference can
warn, but cannot silently disappear into `PASS`. Invalid citation metadata
cannot pass; `VALID` does not establish claim support. Unknown references,
forged extra authority/metadata, invalid JSON, timeout and transport failures
never turn into `PASS`. A failure raises sanitised `RiskReviewError` separately
from business outcomes; A maps it to the existing ErrorEnvelope/processing
failure path. No exception text or input is logged here.

### Cancellation correction — 17 October 2026

Caller cancellation now remains cancellation even if a transport suppresses
`CancelledError` and then returns a valid-looking PASS or raises an ordinary
exception. No completed review is returned after such cancellation. Internal
deadline expiry still produces the existing `MODEL_TIMEOUT`, not a fabricated
business outcome. This preserves the independent review and failure boundary
without changing a wire field, prompt version or A-owned runtime code.

Regression coverage includes normally propagated caller cancellation, suppressed
cancellation followed by a reply or exception, and internal deadline accounting.
These are cooperative local stub tests. They do not sandbox arbitrary Python,
stop a blocking transport, certify a live provider or replace A's post-await
current-version checks and real model/data-flow approval.

### Image handoff and transport conformance — 18 October 2026

This increment exercises the existing optional `ImageObservationResult` input,
not a new vision model. Synthetic observations, original evidence references,
limitations and confidence must survive intact in the immutable request JSON.
Cross-case, stale-input, unknown/unbound evidence and malformed/authority-bearing
inputs are rejected before the model transport runs. Empty visible observations
and low confidence remain valid uncertain data; tests do not invent a rule that
all low-confidence images automatically require a particular Risk outcome.
Image text stays separate from the system prompt. That structural assertion is
not evidence that a real model will resist prompt injection or infer correctly.

Transport regressions also cover configured invocation metadata, nonzero usage
preservation, malformed/provider-shaped responses, capacity limits and failure
without retries. There is still no HTTP client or provider adapter in this
component. The unchanged prompt and production module are not claimed as newly
implemented by these tests. See PR #69 for exact-source verification results.

These tests support C2.02/C2.05 and `FR-008` / `NFR-001/002/009`. They do not
start or complete C3.01–C3.03, prove source admission, run formal Gold, or replace
R.03's actual integrated pilot. The frozen owners, S/F and outcomes are unchanged.

## Adapter and integration contract

- Supply an async `ModelInvocation → ModelReply` callable. Invocation has the
  separate system prompt, immutable input JSON, model/provider IDs and deadline.
- Model JSON has only `outcome`, `findings`, `revision_requests`, `questions`,
  `conflict_assessments`; the last is an internal preparation shape, not a new
  public API field. Every disposition has `index`, `blocking`, and `reason`.
- Transport supplies actual usage counts. Caller supplies unique `review_id`
  and independent `run_id`; output metadata is constructed by the component,
  not accepted from generated JSON. Tests name provider/model as stubs with
  explicitly synthetic zero and nonzero usage values. No live-provider claims
  are inferred from those values.
- A must supply complete authorised retained inputs and recheck current
  case/input/proposal/corpus after the call, before accepting any review.
  IDs and snapshot comparison here cannot prevent a later concurrent revision.
- No database, tool, provider command, approval, state transition or retry
  capability is exposed. `PASS` is not permission to act. Runtime routing and
  exact-scope approval remain A's responsibility.
- Before a real model is used: approve model/provider and allowed data flow,
  implement A's shared adapter, verify independent invocation and timeout
  behaviour, measure semantic support/conflict/injection performance on
  separate pilot data, and satisfy F.07/C1.05 plus the unchanged WBS S/F.
  LLM integration into the executable workflow still requires Gate 1.

### Concrete decision needed before real calls

A's [review of `cfda3a1`](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5562244842)
accepts the preparation interface constraints only. For the next increment,
record the chosen provider and exact model, documented endpoint/API dialect and
structured-output/usage response shape, permitted input fields/data flow, network
deadline/refusal/error handling, and who supplies the shared HTTP adapter.
Credentials stay local and out of GitHub; actual call/budget permission must be
settled before a pilot. A course resource listing alone does not choose a provider.

C can then test that concrete adapter with fake HTTP responses before any live
call, followed by separately recorded real pilot results. Actual retained-input
provenance, current-version/expiry revalidation after await and acceptance into
Domain remain A's integration responsibilities. No extra generic transport
wrapper is needed: `ModelInvocation → ModelReply` is already the internal port.

## 22 October handoff — near-term delivery

[A's KAN-24 scope note](https://lucastaooo.atlassian.net/browse/KAN-24?focusedCommentId=10141)
keeps real-model Risk in deferred Gate 2 / KAN-39 and asks for C2.04 contract/
routing evidence, C2.05 handoff and C's two-minute grounding/risk-design segment.
This is scheduling, not a course waiver or completion of these WBS items.
The frozen owners, reviewers, nine features and all 89 S/F rows stay unchanged.

| Outcome / condition | Consumer obligation from frozen C2.04 | Evidence boundary |
|---|---|---|
| `PASS` | Domain verifies the current retained inputs/review; Founder still approves exact scope | Output shape and bindings tested; no automatic approval |
| `PASS_WITH_WARNING` | Preserve visible findings and the same current-version/approval guards | Warning preservation tested, not semantic correctness of a live model |
| `REVISE` | Return requests to Assessment; generate a new proposal and review | Contract handoff; not proof that the production consumer is connected |
| `NEEDS_INFORMATION` | Coordinator/intake asks questions; reevaluate the new input | Old review must not authorize a changed case |
| `ESCALATE` | Founder manual handling; the escalated proposal cannot be approved | Return to automation requires a new proposal/review |
| Technical failure | Existing processing-failure/ErrorEnvelope path | Not a sixth business outcome; never fallback `PASS` |

Relevant test nodes: `test_five_outcomes_are_structured_without_operation_authority`,
`test_blocking_conflict_cannot_be_warning_only`,
`test_timeout_and_transport_error_are_not_business_outcomes`
([component tests](../../tests/contracts/test_c2_risk_preparation.py));
`test_new_proposal_and_input_versions_reject_old_handoff` and
`test_real_c1_citation_failure_cannot_be_promoted_to_pass`
([handoff tests](../../tests/contracts/test_c_handoff_rehearsal.py)).
These prove local component/binding behavior, not all consumer routes.

The [C review packet](../../docs/reviews/member-c-r02-review-20261022.md)
records 100 tests / 82 subtests across R.02 offline and these C2 files, plus
independently checked no-LLM CI receipt provenance. It does not add a live
provider, qualify the controlled PASS stub as independent Risk, or accept Gate 1.
The [spoken draft and display notes](https://github.com/shuxiachai/returnops-au/issues/66#issuecomment-6333101141)
are ready for C to practise; no rehearsal or duration measurement is claimed.

Before the next runtime increment A must identify the actual admitted corpus
pin, approved model/adapter/data flow and post-await/current-state ownership,
then record the original Gate 1/A1.08/R.03 dependencies. Please also confirm
whether deferred AI/Gold/C3 work is still due for this course delivery or has an
explicit tutor disposition; until then it remains an unresolved requirement,
not cancelled scope. C can maintain local contract tests and review evidence
independently, but cannot manufacture these decisions or personal acceptance.

A's new [PR #94](https://github.com/shuxiachai/returnops-au/pull/94) is a
default-off advisory Coordinator candidate, not this independent reviewer.
At that initial inspection its live result was pending. A subsequently recorded
advisory Coordinator calls in docs/44–47 (published by main `f6de49d6` and its
successors). Those are not this independent C2 Risk invocation; neither that
showcase nor the R.02 stub establishes C2 model-quality or full three-role
integration evidence.

### S6 demo preparation — 22 October evening

Tracking: [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41), Issue #66.
A's [demo script S6 at `51862f4`](https://github.com/shuxiachai/returnops-au/blob/51862f4bcc06eebf1c1804647c21d0908960ebc7/docs/45-stage2-demo-script.md#s6-grounding-risk-contract-and-evaluation-definitions-c-1030-200)
allocates two minutes to C. PR #94 is now merged; it still does not implement
independent Risk. This dated update supersedes the earlier Draft status, not
the outstanding real-call, review or acceptance boundaries.

**AI-assisted spoken draft for C to understand, adapt and practise:**

> My area covers grounding, risk review and evaluation. First, retrieval keeps
> each passage tied to a source, version and content hash. Citation checks reject
> missing sources, wrong versions and changed text. A working URL alone does not
> prove that a claim is supported.
>
> Second, the reviewer has five outcomes: pass, pass with warning, revise, request
> more information, or escalate. For example, an unresolved blocking source
> conflict must escalate. It cannot authorize an operation. Even a pass still
> needs current-version checks and the Founder's exact approval. Invalid output
> and timeouts are technical failures, never an automatic pass.
>
> Finally, our evaluation tools keep failed and invalid cases in the denominator.
> Unknown token costs stay unknown. This display uses five invented cases and
> fixed responses to test accounting, not real model quality. The independent
> live reviewer, formal evaluation and image feature remain unfinished. Our next
> step is reviewed integration and a separate pilot, under the original gates.

Display order: C1 provenance/checks (about 30 seconds), the five-outcome table
above and conflict example (about 45 seconds), synthetic accounting scope and
failure counts (about 30 seconds), leaving about 15 seconds for transitions.
These are planned timings, not measured personal speaking speed.

The accounting command from A's S6 was run on clean C head
`b52a7ca0e11e4e2e03fc2ca01c568d135d07cf0b`, producing 13 local files and manifest
SHA-256 `56ef5af3b208b8a99f6b94bf8c8657f01485c86311746c7d63a0479dccc1e4fe`:

```sh
python -B -m experiments.evaluation_candidate.evidence --output-dir <new-absolute-directory>
```

The parent directory must already exist; the command refuses to replace an
existing output directory. Show `summaries.json` scope flags before any numbers:
each fixture configuration has three successful, one failed and one invalid
case. Declared fixture latency is not a measured runtime result; the paired
integrity check is not proof that B1/B4 agents ran. No Gold labels, timed human
answers, credentials or live endpoint were used. Before demo day, regenerate
from the exact submission source and record the new manifest. C must personally
practise and confirm the final wording; no rehearsal/sign-off is claimed here.

## Reproduce offline checks

From repository root with the existing locked dependencies:

```sh
python -B -m unittest discover -s tests/contracts -p 'test_c2_*.py' -v
```

All model responses in these tests are explicit synthetic stubs. The suite
checks five outcomes, binding/coverage failures, conflict preservation,
structural injection isolation, malformed responses, timeout and no input
mutation. It does **not** measure escalation recall/specificity, run a real
provider, prove prompt-injection immunity or complete the frozen Gold study.
