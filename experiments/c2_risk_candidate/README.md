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

## Adapter and integration contract

- Supply an async `ModelInvocation → ModelReply` callable. Invocation has the
  separate system prompt, immutable input JSON, model/provider IDs and deadline.
- Model JSON has only `outcome`, `findings`, `revision_requests`, `questions`,
  `conflict_assessments`; the last is an internal preparation shape, not a new
  public API field. Every disposition has `index`, `blocking`, and `reason`.
- Transport supplies actual usage counts. Caller supplies unique `review_id`
  and independent `run_id`; output metadata is constructed by the component,
  not accepted from generated JSON. Tests name provider/model as stubs with
  zero usage. No live-provider claims are inferred from those values.
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

## Reproduce offline checks

From repository root with the existing locked dependencies:

```sh
python -B -m unittest discover -s tests/contracts -p 'test_c2_risk_preparation.py' -v
```

All model responses in these tests are explicit synthetic stubs. The suite
checks five outcomes, binding/coverage failures, conflict preservation,
structural injection isolation, malformed responses, timeout and no input
mutation. It does **not** measure escalation recall/specificity, run a real
provider, prove prompt-injection immunity or complete the frozen Gold study.
