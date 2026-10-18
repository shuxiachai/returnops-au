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

## Review correction — 18 October 2026

A's review found that known-cost addition could round or raise under a caller's
Decimal context. Aggregation now uses integer coefficients and scale, preserving
all validated fractional places without changing that context. Costs remain
decimal strings; unknown costs remain unknown and prevent a complete total.
Failed attempts retain known usage. Four regressions cover low precision,
different rounding modes, traps, scientific zero, fractional bounds and mixed
known/unknown observations. The earlier fixed five-case demo has null costs;
this correction does not change its Gold/quality definitions or establish real
model performance. Focused local checks pass 139 evaluation tests (including
19 accounting tests); broader exact-source receipts accompany the PR update.
This addresses the reported defect, not A's re-review or E.01 approval.

## Independent increment — runnable evidence and human-time accounting (17 October)

C has added a single-command public synthetic evidence bundle and a separate
local human-time import/statistics command. Both reuse the existing accounting
modules; neither invokes a real model, reads Gold, authenticates a person or
completes a delivery gate. The commands and boundaries are below. This is C's
independently implementable tooling, not a substitute for E.01 agreement,
E.02 sealing, actual A/B timed work, R.03 integration or E.12 formal evaluation.

Local verification: **135 evaluation tests within 263 contract tests** pass,
including 20 evidence-command and 27 human-timing tests. The locked local run
also passed six static groups, 12 checker/seven tool tests, 14 Mermaid blocks,
64 synthetic-order, 244 security and 36 records tests. Counts overlap.
Receipt `oct17-e09-6hqsnljg` records parent `4986274` plus six exact file hashes,
unchanged during 09:11:17–09:11:32 UTC on 17 October. This results paragraph was
added afterwards; final-source verification is retained with the PR. Independent
AI-assisted review corrected a toy fixture's initially incomplete claim inventory
and added a regression; that review is not A's acceptance. No cloud Actions,
live model, database, Gold or actual human timing was used.

### Run the complete offline evidence rehearsal

From a Git source checkout, with Python 3.12 and Git available, on macOS/Linux:

```bash
scratch="$(mktemp -d)"
scratch="$(cd "$scratch" && pwd -P)"
python -B -m experiments.evaluation_candidate.evidence --output-dir "$scratch/evidence"
```

Keep output **outside the checkout**. The destination must be new; its parent
must already exist, and all path components must be physical directories,
not symlinks. The second line resolves macOS temporary-directory aliases.
The command uses only Python stdlib, the tracked evaluation modules and local
read-only Git commands. It needs no application installation, `.env`, provider
key, database, corpus download or network access. It does not replace the
repository's existing `python tools/checks/run.py offline` test entrypoint.

The fixed five invented cases cover an available response, unknown semantic
judgments, adapter failure, conflicting sources and malformed output. Both
stub configurations actually call `run_stub_cases`. Quality evidence comes
from the **same invocation**, bound to input/risk/rich-output hashes; a failed
or invalid runner result cannot be filled with a separate successful example.
Predefined fixture annotations are bound before execution. Changing output
does not automatically rebind the old positive judgments. These controls test
consistency, not truth or the real multi-agent architecture.

The new directory contains 13 JSON files: inputs and fixture expectations;
source/environment manifests; B1/B4 raw structured runner outputs; bound quality
evidence; explicitly synthetic latency events; losslessly encoded paired
manifests; metric/error summaries; a reproducible-content manifest; actual
creation metadata; and a file-hash index. `manifest.json`'s `content_id` identifies
the deterministic content for the same exact source, environment and working-tree
state. `creation.json` records actual bundle creation time separately; it is
excluded from that ID and is **not a seal**. `index.json` hashes every other file.
Source identity includes actual module hashes and whether they match Git HEAD;
a dirty source is disclosed, not silently described as a clean commit.

Intentional failures remain in all five-case denominators. Unknown tokens,
costs and semantic judgments remain unknown, not zero. Latency is declared
fixture arithmetic, **not observed proposal or model latency**. Different B1/B4
toy outputs do not establish an improvement in real performance. Publication
uses a private staging directory and atomic no-replace rename on macOS/Linux;
existing destinations are never overwritten. A supported atomic primitive is
required; there is no unsafe overwrite fallback. No permission-sandbox,
crash-durability, human-review or acceptance claim is made.

### Validate and summarize human-time records locally

The checked-in example is explicitly invented, not a record of A/B working:

```bash
# Reuse the external scratch directory above, or create a new one first.
python -B -m experiments.evaluation_candidate.human_timing \
  --input experiments/evaluation_candidate/data/human_timing_example.json \
  --output "$scratch/human-time-example.json"
```

Its expected active seconds are A `[60, 120, 180]` and B `[90, 150, 210]`.
Median/IQR are A `120/60`, B `150/60`, pooled `135/75`; pooled Q1/Q3 are
`97.5/172.5`. The two overlapping invented waits for B's last case are removed
once as a 30-second union, not twice. These numbers verify arithmetic only.
Example input metadata hashes the compact three-ID list; the corpus marker
hashes the literal bytes `PUBLIC_SYNTHETIC_TIMING_EXAMPLE_NO_CORPUS`.
Neither marker identifies an admitted corpus or the formal study input set.

[`human_timing.py`](human_timing.py)'s docstring defines the exact import schema.
It requires two distinct fixed A/B permutations of the same 2–100 unique IDs,
source-version/hash references and explicit per-case timestamps/status/pauses.
The bounds (2 MiB, at most 400 rows, 100 pauses per row, a 24-hour case interval)
are technical import limits, **not new course requirements**. The same-operator
wall-overlap and chronological-order checks are conservative validation rules;
they do not claim A has accepted a new timing protocol. A and B may work
concurrently with each other.

Active time includes reading, checking, thinking and writing. Only recorded
customer/provider/Founder/physical waits are excluded by interval union; there
is no generic break exemption. Break handling still needs E.01 agreement.
Missing, duplicate, malformed and failed cases stay in the expected denominator
of `N` per operator / `2N` pooled. Measured failed partial time is retained but
never mixed into completed-case quartiles. Empty statistics are null, not zero.
Median/Q1/Q3/IQR use inclusive Type-7 interpolation with microsecond half-even
rounding, sample count and coverage. Extra rows and unknown IDs remain visible.

For a future authorised import, place records and output in approved **private
storage outside this public checkout**, select `PRIVATE_STUDENT_TIMING_RECORDS`
and explicitly provide `--input` and a new `--output` path. The command refuses
existing output, symlinks/nonregular input, duplicate JSON keys, NaN and oversized
data; it creates a 0600 report and prints no record contents. Reports retain IDs,
counts, pins and derived statistics, not pause reasons or timestamps. Declared
pins are not authenticated against external files. The schema accepts neither
answers nor Gold. It verifies no identity, participation, blindness, seal,
source approval, answer quality, omissions or E.08 acceptance; those require
the original private records and review sequence. Do not publish real timing
input/output simply because this program can process it.

## Earlier 17 October increment — historical verification

Quality-judgment accounting,
paired B1/B4 evidence-consistency validation, their 44 new regression tests,
and the blank private-timing record format below are implemented. All **88
evaluation tests** pass within **216 contract tests** on this individual PR
source. The locked local run also passed six static groups, 12 checker and seven
tool regressions, 14 Mermaid blocks, 64 synthetic-order, 244 security and 36
records tests. Counts overlap; do not add focused tests to contract totals.
An independent AI-assisted code review found and fixed the paired validator's
handling of runner failure diagnostics; it does not replace A's acceptance.

The actual local receipt `oct17-e09-e2l5er98` records parent `6bc62d6` plus five
file hashes at 08:48:00–08:48:14 UTC; this explanatory paragraph was added after
that run, and a final documentation/source check is retained with the PR.
No cloud Actions, PG17, live model, Gold, human timing or gate result is claimed.
E.01 approval, approved real adapters, sealed data, actual A/B sessions, R.03
and E.12 remain pending; this is implemented preparation, not E.09 Done.

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
| Classification | Freeze the supported class vocabulary and reference class before observing outputs. Report actual/predicted confusion counts and unavailable outputs separately; define absent-class F1 rather than silently averaging only represented classes. |
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
That original scorer does not score citations, recommendations or fabrication;
the separate annotation-accounting module below now covers their arithmetic.
Proposal
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

## Quality accounting from supplied judgments — independent preparation

[`score_stub_quality`](quality.py) adds the missing quality-metric **arithmetic**,
not an automatic truth judge. It takes the explicit synthetic data role, a frozen
`class_labels` vocabulary, separate expectations, observations and annotations.
The complete input shapes/formulas are in its docstring, with invented examples
in [`test_evaluation_quality.py`](../../tests/contracts/test_evaluation_quality.py).
There are no model calls, source lookups, actual labels or personal approvals.

Expectations fix case IDs, class, applicable field/component IDs and acceptable
recommendations before scoring. Outputs contain the values/text as well as
field, component, question, claim and claim-specific citation-use inventories.
`observation_sha256` binds supplied judgments to the exact canonical output,
not merely a reusable case/output ID. A changed output invalidates the old
annotation; a matching digest still does not authenticate a reviewer or sources.
The annotation's claim-inventory-complete judgment must cover all material
assertions, including extracted facts, before citation/fabrication totals can
be complete. Missing/null judgments remain unknown, not implicitly correct.

| Metric | Accounting rule |
| --- | --- |
| Classification | Fixed-class confusion matrix with an `UNAVAILABLE` column. Missing/failed/invalid/duplicate outputs count as FN for the true class. Macro-F1 includes every frozen class; if a class has neither support nor predictions, its F1 and the macro are null, not silently omitted. |
| Required-field correctness / packet completeness | All frozen applicable items stay in the denominator. Absent items are missing; present items need an explicit correctness judgment. Unknown items make the main value null; a clearly labelled confirmed lower bound and judgment coverage are separate. |
| Unnecessary follow-up | Unnecessary requested items / all requested items, using supplied necessity judgments. Report no-question cases; zero denominator or incomplete review is null. |
| Citations | Coverage counts claims needing citation that have at least one explicitly correct citation. Correctness counts correct claim-specific citation uses / all uses. URL/ID/hash validity alone never supplies semantic correctness. |
| Critical fabrication | Count flagged claims once each and report affected case IDs. A zero known subtotal is not a zero total when output, claim inventory or judgments are incomplete. |
| Recommendation | Membership in the predeclared acceptable set / all expected cases. Unavailable outputs get no credit; this is separate from Risk outcome agreement and not a legal correctness claim. |

Missing/duplicate/invalid annotations cannot remove the case or improve its
result. Extra/unidentifiable rows are exposed separately. Inputs are detached
plain JSON, bounded to 2 MiB total and 100 entries per case list/inventory; this
does not expand the formal 30-case plan. No metric produces a target/gate pass.
The semantic definitions, class vocabulary, reference labels, actual review,
live-output adaptation and formal freeze still need their original approvals.

## Paired B1/B4 evidence consistency — independent preparation

[`validate_stub_pair`](reproducibility.py) checks two **supplied synthetic**
manifests. It does not execute them. The tests in
[`test_evaluation_reproducibility.py`](../../tests/contracts/test_evaluation_reproducibility.py)
provide complete invented examples; the module docstring defines the input
shape. Its companion `canonical_stub_json_bytes` uses sorted compact UTF-8 JSON
with finite numbers, not a claim to implement an external canonical-JSON standard.

Each run supplies ordered `{case_id, input}` cases, dataset version/hash, exact
underlying model/settings, timeout/no-retry settings, source commit, architecture
declarations and versioned bytes/hashes for corpus, prompts, configuration,
scorer and environment. Model/settings, ordered inputs, dataset/source and the
shared corpus/scorer/environment pins must match across the pair. Architecture
prompts/configurations may differ; both prohibit network and operation authority
in this stub scope, and B1 declares no retrieval/review/gates. A B4 declaration is
not proof of a working multi-agent system or deterministic runtime gate.

Supplied artifact/output bytes are hashed, not accepted solely because a caller
typed a valid-looking digest. Configuration bytes must match the declarations.
Per-case result records bind structured observation bytes to the case and
declared disposition; invalid B1 retrieval cannot be credited as successful.
Missing, failed and invalid results remain counted. If raw bytes are unavailable,
their digest remains null with the appropriate failure/absence record. These are
retained structured observations, **not original provider-response evidence**.
The receipt returns pins/counts/digests, not raw case text or output contents.

Validation is bounded to 100 cases per run, 2 MiB per JSON/byte object and 4 MiB
of paired evidence. These are technical fixture limits, not study-size changes.
No files, network, credentials or environment variables are read. Hash agreement
does not authenticate execution, source semantics, private sealing, identity,
permission isolation or historical freeze; fabricated consistent fixtures also
pass consistency checks. There is no automatic acceptance or quality claim.
Live adapter integration and the original E.01/E.09/R.03/E.12 sequence remain.

## Human timing and joint integration — C preparation, not a booking

[The coordination request to A/B](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231875735)
asks for two available Sydney-time windows on 18–19 October. Lucas has confirmed
availability on both days; A/B's replies and the final booking remain pending.
Availability does not establish E.01/E.02 readiness or a completed session.

These are two separate activities:

- **Independent human baseline:** A and B each process the same fixed 20-case
  stratified subset of the 30, in different recorded random orders. They do not
  collaborate on answers. Before either starts, E.01 and original dependencies
  must hold; C must seal all 30 initial labels, sources and reasons, with input/
  label versions, hashes and actual seal time. A checks only a no-answer receipt.
  C must verify that seal before reading any timed answer, including as E.03's
  reviewer. A/B receive the same inputs/orders/evidence/corpus, not labels.
- **Joint integration:** a separately proposed 45–60 minute troubleshooting
  window, not a promise to complete a gate in that time. A supplies exact
  integrated source, startup entry and R.02 evidence/status; B brings the UI/API
  entry and remaining defects; C brings retrieval/risk/evaluation candidates.
  An interface discussion may happen earlier, but actual R.03 needs A1.08 and
  its original prerequisites. Do not call an interface meeting a passed pilot.

Copy the following **blank field checklist into approved private storage** when
E.02 is ready. It is not a populated data set, signature or sealing receipt:

| Record | Fields to collect privately; leave unavailable values blank |
| --- | --- |
| Session | Status (initially not started), operator, agreed time/timezone, input and corpus versions/hashes, fixed subset/order, no-answer seal-receipt reference, approved access restrictions |
| Each case | Position and input ID; real start/end times; pause start/end and reason; active handling seconds; independent answer reference/hash; submission and lock time; interruption/deviation notes |
| Completion | Actual Gold/other-answer exposure declaration and operator confirmation, only after the activity; immutable locked-output version/hash; do not preselect a successful declaration |

Active handling includes reading, checking and writing the decision packet;
pause simulated customer/provider/Founder/physical waiting and preserve reasons.
Agree break handling in E.01 rather than silently deleting slow cases. A/B must
produce their own timed work; software can prepare and check records, not
fabricate their actions or elapsed time. No cross-answer access or Gold feedback
until **both outputs are locked**. A must finish E.03 and wait for both locks
before reading/reviewing B's E.04. Then retain E.05 label handoff → E.06 A review
of all 30 → E.07 B arbitration → E.08 final freeze → scoring. Preserve initial
labels and source-based revision reasons; do not adapt labels to timed answers.

This repository is public. Only this empty format and the protocol belong here;
Gold labels, timed answers and access-bearing links stay in the agreed private
location. Hashes alone prove neither access control nor historical sealing.
No actual session, seal, human review, contribution or Jira Done is asserted.

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
