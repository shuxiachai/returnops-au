# E.01/E.09 isolated preparation — synthetic accounting only

Owner C / reviewer A. Tracking: [KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25) /
[Issue #67](https://github.com/shuxiachai/returnops-au/issues/67).
Prepared 12 October 2026 with Codex assistance. This is a small preparation
alongside the primary C1 work, not a new simultaneous main implementation item.
Traceability: FR-002/006/007/008, NFR-001/005/009, AH-08, UC-02 and
[C's model chain](../../docs/18-member-c-model-chain.md).

The [fixed evaluation protocol](../../docs/00-project-definition-v1.md),
[allocation](../../docs/07-frozen-work-allocation.md) and
[E.01/E.09 dependencies](../../docs/08-delivery-work-packages.md) remain authoritative.
The scorer performs no model, adapter, network, database or operation call.
The runner described below invokes only an explicitly supplied synthetic test
adapter; no real adapter or network client is supplied. Neither module is
included in the runtime wheel. They do not implement a complete live evaluation
runner, real B1/B4, C2, Gate 2 or formal scoring. No Gold inputs, labels, timed
answers, sealing receipt, contribution percentage or personal sign-off was
created/read by this preparation. No model performance result is asserted.

## E.01 definition draft — requires A review before freezing

The following are proposed measurement definitions, not accepted labels or a
change to project targets. Publish only separately authored development fixtures;
keep the eventual 30 Gold cases and initial labels under the original controlled
handoff. The 20 timed cases remain a stratified subset of the 30, not new data.

| Measurement | Proposed unit and denominator / review requirement |
| --- | --- |
| Mandatory information | Per-case relevant field IDs fixed by a reviewer before outputs. Required-field sets are conditional on the scenario; an order number or original packaging is not a universal requirement. True recall requires correctness against the retained source, not merely a field name being present. |
| Unnecessary follow-up | Count individual requested information items judged unnecessary against the scenario guide / all requested items. Report no-question cases separately; zero denominator is null, not perfect performance. A must approve what counts as necessary and a distinct item. |
| Critical fabrication | A source-unsupported assertion that could materially change recommendation, entitlement, evidence sufficiency or operational scope; examples include an invented purchase fact, defect observation or approval. Record count and case IDs; review severity against sources. An explicit unknown is not fabrication. No heuristic string test establishes truth. |
| Packet completeness | Correctly supplied applicable required components / all applicable components fixed before outputs; report schema validity separately. Empty-but-valid text is not automatically complete. |
| Recommendation agreement | Output belongs to the source-reviewed acceptable outcome/recommendation set / all expected cases. Reasonable alternatives may coexist; no claim of a unique legally correct answer. Risk outcome agreement is separate from recommendation quality. |
| Risk | Freeze escalation-positive and non-escalation cases independently of observed outputs; retain TP/FP/TN/FN plus unavailable outputs. Missing, invalid or failed responses are never safe negatives. Distinguish source conflict/injection/authority from ordinary requests for information. |
| Citations | Coverage: supported-policy/evidence claims with an appropriate citation / all claims needing one. Correctness needs source/claim review, not just URL/hash validity. Record raw counts and unavailable outputs. C1 metadata validity and C2 claim support remain separate. |
| Retrieval | Relevant ranked passages retrieved / reference relevant passages, with k fixed. Conflict-expanded returned coverage is a separate measure, not Recall@k. Zero reference relevance is null; evaluate NO_MATCH separately. Reuse the existing C1 pilot's separation. |
| Latency and cost | Proposal latency uses accepted-complete-input to stored-review-ready-proposal, including machine loops but excluding human/physical waiting. Report failures and sample count separately. Tokens/cost unavailable from a provider remain null; no runtime latency/cost is measured here. |

A must review the field ontology, scenario relevance, criticality rules,
acceptable sets, positive/negative definitions and denominators before E.01
acceptance. This draft does not claim that those definitions have been frozen.
Later formal runs pin dataset/corpus/prompt/model/config/scorer/environment and
commit, retain raw evidence and forbid label changes based on observed scores.

## Bounded E.09 scorer

`score_stub_run` accepts only the explicit data role
`PUBLIC_SYNTHETIC_SCORER_FIXTURES_NOT_GOLD` and `B1_OFFLINE_STUB` or
`B4_OFFLINE_STUB`. Its declarations are scope guards, not security authority or
proof that an adapter obeyed them. B1 rejects nonempty retrieval output. B4 is
also a stub: no real agent, retrieval, independent reviewer or deterministic gate
is exercised. Future adapter/integration review is separate.

Every expected ID receives one disposition. Missing, duplicate and malformed
rows cannot be selected away to improve results. Extra/unidentifiable rows are
reported separately and make `run_structure_valid` false. A duplicate expected
ID is rejected before scoring; no “last row wins” behavior exists.

Outcome agreement and completion use **all expected cases**. Completion-aware
recall is TP / all escalation-positive cases; completion-aware specificity is
TN / all negative cases. Unavailable outcomes are separately counted and get
neither TP nor TN credit; these named metrics are not mislabeled as a complete
conventional confusion matrix. `required_field_id_coverage` checks IDs only,
**not** field correctness or the project's mandatory-information recall target.
The scorer does not score citations, recommendations or fabrication. Proposal
latency arithmetic is provided separately below; it is not the adapter's wall
time and does not establish the authenticity of a timing event.

Usage covers expected cases only, including valid failed observations. It reports
known subtotals and unknown counts; a total is null if any expected case lacks
that metric. Extra/duplicate/invalid rows can incur unknown additional costs;
therefore these scoped totals are never represented as provider-invoice totals.
Costs must be finite nonnegative decimal strings, at most one billion with at
most twelve fractional places; malformed/unbounded values are rejected.
Decimal-string costs have no implied currency or price estimate: a future real
run must record currency, rate source/version and actual usage. An empty run has
null ratios and totals, not success or zero-cost evidence.

## Bounded adapter rehearsal — 17 October 2026 follow-up

[`run_stub_cases`](runner.py) supplies the missing offline invocation-to-scorer
step of E.09. It accepts only the same explicit synthetic data role and stub
configuration names as the scorer, plus a trusted cooperative async adapter.
There is no network/model adapter, credential discovery, application import,
operation port or new dependency. It is **not** the complete B1/B4 runner.

Each case is exactly `{"case_id": "...", "input": {...}}`. All cases are
validated before any invocation: unique nonblank IDs, plain JSON values, at
most 100 cases and a 2 MiB budget for the whole input manifest. This is a
technical development-fixture limit, not an expansion of the 30-case Gold plan.
An immutable `StubInvocation` contains only configuration, case ID, input JSON
and timeout. The API has no expectations argument; expected outcomes are held
separately by the caller and passed to the scorer only afterwards. This
separation and a caller-declared data-role string cannot prove that arbitrary
input contains no hidden label or that a Python adapter has no external access.
Only reviewed public invented fixtures and local stubs belong in this module.

- Execute in supplied order, once per case, with no retry or skipped failure.
- Each valid adapter reply has the existing scorer observation shape and must
  bind to that invocation's case ID. Snapshot it before accounting; a reply
  cannot credit another case or change after being returned.
- Exception/timeout becomes a `FAILED` observation with unknown usage (`null`),
  not a safe negative or an invented zero-cost result. Later cases still run.
- Invalid output becomes a sanitised `{case_id: ...}` sentinel, which the
  existing scorer counts as `INVALID`. Keep the per-case diagnostic code; no
  raw exception or invalid adapter payload is retained in the report.
- A valid `FAILED` reply retains its supplied usage. B1 replies containing
  retrieval are invalid. Denominators remain those of the separate expectations.
- Caller cancellation propagates and stops the batch; it is not a successful
  partial report. A swallowed deadline cannot turn a late result into success.

Usage in an async test or development function:

```python
from experiments.evaluation_candidate import DATA_ROLE, score_stub_run
from experiments.evaluation_candidate.runner import run_stub_cases

# local_stub is a reviewed async StubInvocation -> observation callable.
# public_cases and public_expectations are separately held invented fixtures.
batch = await run_stub_cases(
    configuration="B4_OFFLINE_STUB", data_role=DATA_ROLE,
    cases=public_cases, adapter=local_stub, timeout_seconds=1,
)
report = score_stub_run(
    configuration=batch["configuration"], data_role=DATA_ROLE,
    expectations=public_expectations, observations=batch["observations"],
)
```

`case_results` carries sanitized dispositions/error codes; `observations` is
the scorer input. The runner makes no model-quality, semantic correctness or
end-to-end latency claim. `asyncio` cannot sandbox a Python callable, interrupt
blocking code or force an adapter that refuses cancellation to stop. Those
limitations do not authorize substituting a real provider into this stub-only
preparation. Future live transport, rate/cost provenance, true B1/B4, pilot and
formal freeze still require separate implementation and review under E.09/R.03.

## Proposal-latency accounting — independent preparation, 17 October

[`summarize_stub_proposal_latency`](latency.py) is a pure accounting function
for public synthetic event records. It does not call an adapter, take a timer,
read runtime telemetry or claim a real performance result. Trace: E.01/E.09,
NFR-005/NFR-008 and the proposal interval in docs/00 and docs/07.

Call it with `data_role=DATA_ROLE`, a unique `expected_case_ids` list and
`observations`. Each observation has exactly these fields:

```json
{
  "case_id": "public-invented-latency-example",
  "status": "REVIEW_READY",
  "accepted_complete_at": "2026-10-17T00:00:00Z",
  "stored_review_ready_at": "2026-10-17T00:00:20Z",
  "excluded_waits": [
    {"kind": "HUMAN", "start_at": "2026-10-17T00:00:05Z", "end_at": "2026-10-17T00:00:10Z"}
  ]
}
```

This invented example has a 20-second wall interval and a 15-second proposal
interval. The input is a fixture, not a recorded project run. UTC `Z` timestamps
accept seconds or 1–6 fractional digits. Only `HUMAN` or `PHYSICAL` waits are
excluded, and overlapping/adjacent waits are merged before subtraction. Model,
network and retry work cannot be labelled as excludable machine waits. The
function cannot detect a caller dishonestly labelling machine time as human;
real event provenance and exclusion classification still need review.

`FAILED` requires both timestamps null and an empty waits list; its lack of a
sample is not zero latency. Missing, duplicate and invalid rows likewise remain
in the all-expected denominator. Extra/unidentifiable rows are listed separately.
All rows use a 2 MiB JSON budget, with at most 100 expected IDs/observations and
100 wait intervals per observation; these are technical rehearsal bounds, not
an expansion of the frozen 30-case study.

The report includes dispositions, per-case wall/excluded/proposal intervals,
available sample count/coverage and **conditional** p50/p95. Percentiles use
linear-inclusive/type-7 interpolation, rounded half-even to microseconds,
independent of the caller's decimal settings. An empty sample produces null;
a single sample produces its own value. Neither low p95 on the available
subset nor a zero-duration sample certifies the `<120 s` target or a gate.

**A confirmation before real use:** approve these proposed measurement details
and supply trusted accepted-complete-input, stored-review-ready-proposal and
human/physical-wait events from the same run. This fixture shape is not a new
shared API contract. The module must not replace F.06's authoritative metric
definitions, a real B1/B4 adapter, R.03 or E.12. No labels or timed answers are
collected here.

## Reproduce offline checks

Run from the source checkout with the existing locked Python 3.12 environment:

```bash
python -B -m unittest discover -s tests/contracts -p 'test_evaluation*.py' -v
```

Tests use openly synthetic in-memory expectations; they are correctness tests
for accounting, not measured performance on pilot/Gold. Existing contract CI
discovers this test file; no dependency, workflow or runtime entrypoint changes
are made. E.09 acceptance still needs E.01 and A1.06/A1.07/C2.05. Full B4 pilot
validation is R.03 after R.02; formal B1/B4 comparison is E.12 after its original
dependencies. C3 runtime still waits for R.03 and its original finish conditions.
