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
This code performs no model, adapter, network, database or operation call. It is
not included in the runtime wheel. It does not implement a complete evaluation
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
The scorer does not score citations, recommendations, fabrication or latency.

Usage covers expected cases only, including valid failed observations. It reports
known subtotals and unknown counts; a total is null if any expected case lacks
that metric. Extra/duplicate/invalid rows can incur unknown additional costs;
therefore these scoped totals are never represented as provider-invoice totals.
Costs must be finite nonnegative decimal strings, at most one billion with at
most twelve fractional places; malformed/unbounded values are rejected.
Decimal-string costs have no implied currency or price estimate: a future real
run must record currency, rate source/version and actual usage. An empty run has
null ratios and totals, not success or zero-cost evidence.

Run from the source checkout with the existing locked Python 3.12 environment:

```bash
python -B -m unittest discover -s tests/contracts -p 'test_evaluation_preparation.py' -v
```

Tests use openly synthetic in-memory expectations; they are correctness tests
for accounting, not measured performance on pilot/Gold. Existing contract CI
discovers this test file; no dependency, workflow or runtime entrypoint changes
are made. E.09 acceptance still needs E.01 and A1.06/A1.07/C2.05. Full B4 pilot
validation is R.03 after R.02; formal B1/B4 comparison is E.12 after its original
dependencies. C3 runtime still waits for R.03 and its original finish conditions.
