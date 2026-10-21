# C2 independent risk-review candidate

Tracking: [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) /
[Issue #66](https://github.com/shuxiachai/returnops-au/issues/66).

Offline preparation for **C2.01–C2.05**, `FR-008`, `NFR-001/002/009`,
`AH-08 → UC-02 → Grounding/Risk Activity, Assessment–Reviewer Sequence,
ProposalReview state model`. C owns this component; A reviews and integrates.
This is not a live LLM, Gate 2, feature acceptance or semantic-quality result.

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
