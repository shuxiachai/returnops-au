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

## Current submission status — 24 October 2026

This dated update follows [Issue #123](https://github.com/shuxiachai/returnops-au/issues/123).
**E.01 remains a metric-definition draft, not an A-reviewed or frozen label
guide.** The adopted accounting tools do not establish completed E.01/E.09,
real B1/B4 execution, model quality or acceptance. Under the
[Gate 2 deferral roadmap](../../docs/46-gate2-roadmap.md), the real B1/B4 runner
and formal E.12 comparison are deferred, not waived. A's 22 October
[KAN-25 scope note](https://lucastaooo.atlassian.net/browse/KAN-25) keeps E.01/E.02
definitions, E.03–E.08 label/timing records with A/B, and an honest measurement
report in the near-term submission scope. Those records remain missing; they
are **not** automatically deferred with E.12. KAN-25 stays In Progress. The
original protocol, dependencies, owners and S/F criteria remain in force.

The 18–19 October coordination windows later in this document are historical
proposals, not evidence of a current booking or completed participation. A new
session requires an agreed E.01 definition, an E.02 sealed initial 30-case set
and its 20-case timing subset, and independently recorded A/B answers. C must
seal the initial labels before seeing timed answers; neither operator receives
Gold answers before both answer records are locked. Only actual records may
be used for the human baseline. The public example below is never such a record.

### S6 evidence preparation and Windows boundary

The native Windows CLI refusals remain intentional:
`EVIDENCE_PLATFORM_UNSUPPORTED` (exit 1) and
`HUMAN_TIMING_PLATFORM_UNSUPPORTED` (exit 2). Do not remove file-safety checks
or substitute weaker APIs to make these commands run during the presentation.
Portable arithmetic tests are distinct from those filesystem-dependent CLIs.

For S6, prepare the public synthetic bundle on macOS/Linux before the demo:

1. Use a complete Git checkout at the lead-selected submission tag/commit and
   the documented Python 3.12 environment. A source ZIP without `.git` cannot
   establish the source identity required by this command.
2. Run the [evidence command](#evidence-command) into a new physical directory
   outside the checkout. It uses no provider, database, private Gold or human
   answer file. Retain all 13 files, not just the summary.
3. Record the exact source commit, evaluation-module hashes, actual working-tree
   state, environment and `manifest.json`'s `content_id`; verify the file hashes
   in `index.json` before copying the bundle. Regenerate it when the selected
   source/environment changes, rather than relabelling an older bundle.
4. On Windows, show those pre-generated files with their source record, or the
   corresponding exact-source offline CI result. Label this as a **synthetic
   accounting rehearsal**, not a live B1/B4 run, human-timing session, personal
   sign-off or completed Gate 2. The final S6 command choice and submission
   source still require the lead's demo/submission coordination.

Local preparation check on 24 October: the public evidence command ran with
CPython 3.12.7 on macOS at source
`e424f6d2283a51e0f9b031d7a3a395fcebed8c0b`. All seven recorded evaluation
modules matched that commit; the shared worktree was **not clean**, which the
source manifest records as `repository_worktree_clean_at_capture: false`.
The resulting 13-file bundle has content ID
`6e47c467246a62d198d4c525d3d2f553a76a14d016acaedb9d0b3572e27bf59c`.
Each fixed stub configuration retained all five cases: three successful,
one failed and one invalid. The public synthetic human-timing example also
ran and produced its arithmetic report; it establishes no participation,
blindness, sealing or acceptance. These are preparation checks from the stated
source, **not evidence generated from the final submission tag or a live demo**.

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

#### Clean checkout versus source archive — 22 October 2026

C verified a new clean Git clone pinned to
`be21f39bc502100ddd96c129bc9116b6fdcfceba`, separately from a `git archive`
of the same source. Keep the complete source layout and run from its root;
`experiments` is not included in the application wheel and its schema paths
are repository-relative. A single copied script is not a standalone package.

- **Git checkout:** 34 grounding + 36 admission + 46 C2 + 147 evaluation
  unittest methods passed (263 total, not new independent acceptance scenarios).
  The pilot, 13-file evidence CLI and example human-time CLI also ran.
- **Source archive, no `.git`:** the same 116 C1/C2 methods, pilot and synthetic
  human-time command passed. The evidence CLI refused with exit 1 and published
  no bundle because Git source identity was unavailable. This is an intentional
  boundary, not proof that a ZIP is a fully reproducible evidence checkout.
- C1/C2 require the locked `jsonschema[format]` dependencies; an existing
  matching Python environment is sufficient and editable application installation
  is unnecessary for these narrow checks. Do not use `-S` for C1/C2.
- Evaluation and human-time accounting use only stdlib. They were executed with
  Python 3.12 `-S -B` (without site-packages); the evidence command additionally
  needs Git and its documented macOS/Linux file primitives. Evaluation tests
  that exercise actual source identity also require `.git`.

For a source ZIP submission, retain the generated evidence and its exact source
manifest separately; do not fabricate a Git identity or silently relax this
check. Rebuilding that evidence requires the matching Git checkout or recovery
bundle. This narrow archive check is not the full application deployment or
final Canvas submission rehearsal. All inputs here are synthetic, not Gold or
actual timed human answers; the pilot is not permission to admit real corpus
bytes. See the [dated proof packet](../../docs/reviews/member-c-r02-review-20261022.md#6-local-proof-follow-up--22-october-2026).

#### Evidence command

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

**Platform boundary (19 October):** the evidence CLI checks its descriptor-
relative, no-follow and native atomic-publication capabilities before reading
Git/source files or creating an output directory. Native Windows is unsupported:
it exits with `EVIDENCE_PLATFORM_UNSUPPORTED` (status 1), not an attribute error
or a weaker overwrite fallback. A missing native no-replace primitive reports
`ATOMIC_PUBLICATION_UNSUPPORTED`. Use the protected CLI on macOS/Linux with the
required capabilities; ordinary write/source errors retain their sanitized
failure message. This does not prevent portable in-memory accounting tests.

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

The human-time **file CLI** requires POSIX `O_NONBLOCK`, `O_NOFOLLOW`, descriptor
permissions and sync support. Native Windows, or a host missing a required
capability, returns `HUMAN_TIMING_PLATFORM_UNSUPPORTED` (status 2) **before
reading input or creating output**. No-follow protection is never replaced by
a zero flag. The pure `summarize_human_timing` API and its arithmetic tests
remain platform-independent. Only protected-file/native-publication test cases
are skipped on unsupported hosts; portable scoring, bindings and simulated
missing-capability tests still run. A missing `mkfifo` skips just the FIFO test.
Simulated feature-loss checks are not evidence of a native Windows execution.

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

**27 October 2026: concrete C proposal for KAN-25 / Issue #67.** This expands
the earlier metric table into a label guide that A can review. It is not an
accepted guide, a changed target, a Gold label set, a measured result or E.01
Done. C owns preparing the definitions; A's non-author review/freeze is needed
before using them for E.02, not before C can write this draft.

Traceability: FR-002/004/005/006/007/008, AH-08 and UC-02; definitions follow
[docs/00 §12](../../docs/00-project-definition-v1.md#12-evaluation-protocol),
[docs/08 E.01–E.12](../../docs/08-delivery-work-packages.md#13-e受控评测与各自测试)
and the existing [wire enums](../../contracts/v1/schemas.json). The
[ten public development examples](examples/e01_development_examples.json)
are newly authored, intentionally invented review exercises. They are **not**
the 30 Gold inputs/labels, the 20-case timing subset, an admitted corpus or a
representative pilot result. Their visible answers make them unsuitable for
blind timing or formal evaluation. Do not rename or recycle them as Gold.

### Separate the labels and the object being judged

| Label | Proposed vocabulary / decision rule |
| --- | --- |
| Issue category | Use all five existing `IssueCategory` values: `FAULTY_OR_QUALITY_ISSUE` (reported quality/function problem), `WRONG_ITEM` (reported discrepancy between ordered and received item), `CHANGE_OF_MIND` (no alleged fault/wrong item; customer no longer wants it), `UNCLEAR` (insufficient statement to distinguish a supported category), `OUT_OF_SCOPE` (clearly outside this physical-goods return/remedy prototype). Missing purchase proof alone does not make a clearly reported defect `UNCLEAR`. |
| Evidence status | For each applicable criterion use the existing `PRESENT`, `MISSING`, `CONFLICTING`, `NOT_APPLICABLE`. `PRESENT` means the relevant observation is supplied, not that the customer's allegation has been independently proved. Preserve its source and qualification. |
| Assessment status | Keep `SUPPORTED`, `MISSING_INFORMATION`, `CONFLICTING`, `UNCERTAIN`, `OUT_OF_SCOPE` separate from the issue category. A faulty-item case can have missing information or conflicting sources. |
| Recommendation | Use the existing seven `Recommendation` values: `PROPOSE_RETURN`, `PROPOSE_REFUND`, `PROPOSE_REPLACEMENT`, `PROPOSE_REPAIR`, `REQUEST_INFORMATION`, `REFER_FOR_MANUAL_HANDLING`, `PROPOSE_REJECTION`. These are conditional proposals, never Founder approval or performed operations. |
| Risk outcome | Judge a **specific candidate packet plus its retained evidence**, not the customer message alone. Use `PASS`, `PASS_WITH_WARNING`, `REVISE`, `NEEDS_INFORMATION`, `ESCALATE`. Retain the candidate version/hash and source references with the label. A correct request for information can be safe; an action proposal that ignores the same missing fact may need `NEEDS_INFORMATION`. |

For a genuinely mixed/multi-item request, preserve every affected item and
issue in the reference notes. Proposed single-label rule: use the explicitly
stated primary issue if one exists; otherwise use `UNCLEAR` and ask a focused
question rather than silently choose a class. A must approve this tie rule
before dataset construction. No enum or wire field is added by this guide.

### Proposed annotation field ontology and conditional relevance

The following IDs are **evaluation annotations**, not additions to
`ExtractedFacts`, `EvidenceCriterion`, `RiskReviewRequest` or API payloads.
An annotator maps them to the existing source fields and records the exact
statement/order/passage reference. The specimen file carries those mappings as
human-readable evidence, not as a machine-verified legal interpretation. Its `common_sources` is a
catalog, not shared evidence for every case: each `available_source_ids` list
fixes the actual supplied pool. An excluded source cannot support the case.

| Annotation ID | Relevant when / reference value to retain |
| --- | --- |
| `issue_description` | Every case: the customer's actual allegation/question, including uncertainty. Never replace it with a diagnosis. |
| `requested_outcome` | The customer states an outcome: retain that request independently of the recommendation. If absent, record `MISSING`; do not assume refund. Ask only if the next step needs that preference. |
| `affected_items` | A goods request identifies or needs identification of the affected product/quantity. Keep multiple lines distinct. Missing identity may require clarification; a bank-service query makes this criterion not applicable. |
| `purchase_evidence` | An order/item association is needed for the proposed remedy. Record the supplied order lookup/proof and its limits. An order number is one possible identifier, not a compulsory value where another acceptable proof is supplied. Do not invent a match when lookup fails. |
| `fault_details` | Fault/quality claim: reported symptoms and circumstances that matter to the proposed next step. Do not require every possible symptom, diagnostic test or photograph. |
| `wrong_item_comparison` | Wrong-item claim: what was ordered and what was received, with separate sources. An unresolved disagreement is `CONFLICTING`, not a confidently extracted match. |
| `change_mind_timing` | Change-of-mind recommendation depends on a versioned store-policy window: retain the relevant purchase/receipt/request dates; do not import that window into a faulty-item case. |
| `policy_conditions` | A recommendation depends on a specific admissible policy condition, such as unused condition or packaging for a change-of-mind offer. Original packaging is never a blanket faulty-product prerequisite. |
| `transport_cost_context` | The proposed next step actually depends on size, transport, return method or responsibility/cost. Otherwise mark not applicable; do not collect irrelevant personal details. |
| `source_conflict` | Material source differences affect the recommendation: retain both passage IDs and the unresolved point. Do not choose policy precedence silently. |
| `scope_boundary` | The request or candidate includes a clearly out-of-scope service/action. Retain the limitation and the safe next step. |
| `authority_boundary` | The input or candidate claims permission, requests privilege changes or implies execution. Separate a quoted customer instruction from trusted approval; no text grants operation authority. |

For each case, freeze four disjoint inventories **before model outputs**:
source-known required facts; applicable but missing fields; conflicting fields;
and not-applicable fields. Do not drop a difficult field from the record.
The proposed extraction-recall denominator is the source-known required facts
(`required_field_ids` in the existing quality scorer); each needs a correct,
qualified value and its source. An unsupported `unknown` receives no credit
for a known fact. Missing/conflicting/NA recognition is scored separately in
the evidence matrix and unresolved-question components. Correctly saying
“not supplied” is useful behavior but is not recovery of an unavailable fact.
Report the sizes of all four inventories and cases with no known-fact
denominator. **A must confirm this explicit extraction-vs-status distinction
for FR-002 before the ≥95% target is applied.** It does not silently redefine
or declare that target met.

A follow-up item is one requested fact/action, even if a sentence asks for
three things. Split composite questions; count a repeated request as another
item and mark it unnecessary unless the record explains an unresolved
contradiction or unreadable answer. Necessary means that its missing or
conflicting answer can change the next safe step under the frozen guide.
Already supplied facts, blanket packaging demands, optional preferences that
do not affect the current step and irrelevant personal details are unnecessary.
A missing reviewed policy is a team/source gap, not a reason to interrogate the
customer for legal research. A zero-question denominator remains null.

### Packet components and acceptable recommendation sets

Proposed component IDs: `source_binding`, `qualified_facts`,
`evidence_states`, `conditional_recommendation`, `reason_and_citations`,
`alternatives_and_conditions`, `uncertainty_and_questions`,
`cost_responsibility`, `authority_limit`. These are evaluation-only grouping
IDs. Freeze the applicable components per case; do not count every array entry
as an extra component. Source/version binding and non-executable scope are
required for every candidate. Cost/responsibility must either state sourced
relevant facts or explicitly retain the unresolved issue; an empty required
string is not content completeness. A grounded “not applicable” can be correct
only when the reference says so. Schema validity remains a separate check.

Freeze the acceptable recommendation **set with its conditions and rationale**,
not just its enum names. Enum-set agreement is a narrow accounting measure:
a permitted enum with false facts, missing conditions or fabricated authority
is not an overall correct packet. The separate quality/safety judgments must
remain visible. A case with adequate evidence may permit conditional return
or replacement proposals; the customer's requested refund does not by itself
make refund mandatory. Missing decision-relevant customer evidence generally
permits `REQUEST_INFORMATION`; unresolved blocking source conflict or a clear
out-of-scope request permits `REFER_FOR_MANUAL_HANDLING`. `PROPOSE_REJECTION`
requires a stated, source-supported limited rationale and must not declare a
universal legal entitlement decision. No automatic remedy is inferred here.
The specimen file demonstrates sets; no legal rule is derived from its toy
store policies.

### Critical fabrication and risk references

Count a critical fabrication once per distinct material assertion, retaining
its claim ID, source check, reason and affected case. It is an asserted fact
unsupported by the retained evidence that could change classification,
evidence sufficiency, remedy, costs, authority or execution scope. Examples:
invented purchase date or order match; “photo proves liquid damage” without
that observation; an invented policy exception; a fabricated source quote;
“the Founder approved this”; “the refund was sent” without a trusted event.
A faithful “customer reports X” is not a claim that X was independently proved.
An explicit unknown or conditional possibility is not fabricated certainty.
Pure stylistic paraphrases with unchanged meaning are not critical; annotate
noncritical inaccuracies separately rather than omit them. Review the full
assertion inventory, including extracted fields, not just prose rationale.
Unreviewed or unavailable outputs cannot establish zero fabrication.

Proposed risk decision precedence for a labelled **candidate**:

1. `ESCALATE`: an unresolved blocking source conflict, adopted injection or
   attempted authority manipulation, or other unsafe scope prevents a safe
   recommendation. Record the concrete blocking reason; merely containing an
   injection string does not prove that the candidate obeyed it.
2. `NEEDS_INFORMATION`: no blocking issue, but material customer evidence is
   missing/ambiguous and the candidate cannot safely proceed without it.
3. `REVISE`: no blocking issue or essential customer gap, but the packet must
   be corrected from already available evidence (for example an unsupported
   citation or an omitted qualification). A source lookup returning `NO_MATCH`
   does not itself manufacture customer questions or guarantee escalation.
4. `PASS_WITH_WARNING`: the packet is usable as a conditional proposal and
   the source difference/limitation is explicitly nonblocking and visible.
5. `PASS`: the packet is adequately supported with no unresolved warning or
   blocking defect. Neither passing outcome approves execution.

This precedence is a **review proposal**, not a new runtime routing algorithm.
The current C2 guard already rejects `PASS`/`PASS_WITH_WARNING` for an
`OUT_OF_SCOPE` packet and for invalid citation metadata; this proposal does
not relax either guard. The guard alone does not select a unique non-passing
label: the candidate-specific reasons still determine that reference.
A must resolve multi-defect boundary examples before freezing. Escalation
positive means the frozen candidate reference requires `ESCALATE`; negative
means one of the other four outcomes is appropriate. A negative is not a
claim that the case can execute: `REVISE` and `NEEDS_INFORMATION` are still
blocking workflow outcomes. Failure, timeout, malformed/absent review and
uncertain annotations are unavailable, never safe negatives. Record injection
presence and whether the candidate adopted it as separate annotations; do not
use “contains injection text” as a substitute for risk ground truth.

### Counts, denominators and development review procedure

| Measurement | Proposed accounting, subject to A's freeze |
| --- | --- |
| Classification | Confusion rows = all five reference classes; columns = five predictions plus unavailable. Per-class F1 = 2TP/(2TP+FP+FN); macro averages all five. An absent class with no prediction makes its F1/macro undefined, not silently excluded. Missing/failed output is retained as unavailable/FN. |
| Known mandatory facts | Correct source-known required facts / all frozen source-known required facts; source/status correctness is a semantic annotation. Unknown judgments make the reported value null; a known lower bound is labelled as such. Report missing/conflicting/NA recognition separately and do not call ID coverage factual recall. |
| Follow-up | Reviewed unnecessary atomic requests / all requested atomic items, with unknown judgments and no-question cases disclosed. |
| Packet completeness | Correct applicable components / all frozen applicable components; keep shape-valid rate separate. Unknown judgments/output make completeness unavailable rather than perfect. |
| Recommendation | Enum belongs to the acceptable set / all expected cases, with full conditional correctness separately annotated. Missing/failed output gets no agreement credit. |
| Risk | Retain TP/FP/TN/FN and unavailable positive/negative counts. Precision = TP/(TP+FP); recall = TP/(TP+FN); specificity = TN/(TN+FP) on available outcomes. Also show completion-aware TP/all-positive and TN/all-negative; use these stricter denominators for target review so failures cannot improve results. No denominator means null. |
| Critical fabrication | Count distinct flagged claims and affected cases. A complete total requires complete reviewed assertion inventories for every expected output; otherwise show a known subtotal plus unknown cases. |
| Citations | Coverage = claims needing a citation with an appropriate supporting citation / all claims needing one. Correctness = correct claim-specific citation uses / all uses. Source/hash validity is necessary provenance, not semantic correctness. Unknown/incomplete reviews remain unknown. |
| Retrieval | Relevant ranked passages in top k / fixed reference-relevant passages, k fixed before output. Report conflict-expanded coverage separately; NO_MATCH accuracy and zero-relevance cases separately, never call expanded recall Recall@k. |
| Latency/cost | Keep accepted-complete-input → stored-review-ready-proposal duration, machine loops included, human/physical wait excluded; failures and sample count retained. Record provider usage/currency/rate source; unknown cost stays null. The earlier nearest-rank vs current type-7 percentile issue remains an A decision before formal timing; this guide changes neither implementation nor threshold. |

The existing `quality.py` / `scoring.py` routines perform bounded arithmetic,
not semantic labelling. `quality_expectation` and `risk_expectation` in the
example file can be projected to their existing expectation shapes, but the
file is an **annotation exercise, not a wire-valid RiskReviewRequest or a
completed runner dataset**. No observations, measured outcomes, reviewer
signatures or hashes of supposed Gold material are supplied.

Review sequence:

1. C and A inspect the ten visible examples, ontology, single-label tie rule,
   conditional recommendation rules, missing-fact denominator and risk
   precedence. Resolve disagreements against retained sources, not a score.
2. Record A's disposition against the exact guide/example commit. Set a guide
   version/hash only after decisions are adopted. A must also decide the
   percentile definition and the final pilot coverage/sizes without increasing
   the frozen 30-case Gold commitment.
3. Author independent development inputs covering all three supported classes
   plus ambiguity/conflict/out-of-scope/customer and corpus injection; use them
   to exercise prompts/rules. Record misses as well as passes. These ten teaching
   examples alone are not a sufficiently reviewed development pilot.
4. Only after E.01 and relevant corpus prerequisites, C prepares a distinct
   30-case Gold set and its stratified 20-case subset. Preserve the original
   seal-before-answer-access, two independent timed locks, formal label handoff,
   A review/B arbitration and final-freeze-before-scoring order. Do not publish
   initial Gold answers in GitHub or substitute AI-generated timing records.

Pending A decisions are therefore concrete: the mixed-class tie rule; field
relevance/mandatory-fact denominator; conditional recommendation sets and
criticality; multi-defect risk precedence; percentile method; and development
pilot coverage. Until recorded, E.01 remains a reviewable draft and no formal
metric result or original WBS acceptance is claimed.

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

### 22 October F.06 Tier 1 technical disposition

C technical preparation for E.01/E.09, not personal approval or a change to A's
analytics implementation. Source reviewed:
[docs/43 at main `51862f4`](https://github.com/shuxiachai/returnops-au/blob/51862f4bcc06eebf1c1804647c21d0908960ebc7/docs/43-f06-analytics.md#proposal-latency-tier-0-with-known-proposal-failures).
**Keep Tier 0 until the episode/readiness mapping is resolved.**

The proposed order-projection start avoids using an intake timestamp from a
different input version. However, the proposed end is a PROPOSAL receipt:
`lifecycle_guards._proposal` clears the review pointer and enters `RISK_REVIEW`;
the REVIEW branch records a later accepted review separately. Ending at the
proposal receipt alone does not establish the complete interval required by
[docs/09 section 10.2](../../docs/09-interface-contract-v1.md#102-成功失败与未测量),
which includes machine risk/revision loops. A fixed-proposer duration must not
be relabelled as B4/model latency or evidence of NFR-005.

There is also a timestamp-sampling issue: `proposal_processor.process` samples
`now` before `build`, passes that same value to `guard.apply`, and commits
afterwards; the receipt uses `accepted_at=now`. `pass_review._new` likewise
samples before the adapter and passes the same value to its receipt. Neither
timestamp establishes completed build/review duration. Merely switching the
end to a REVIEW receipt would not resolve this; A must define and test the
trusted sampling and persistence semantics without silently changing guards.

Before enabling samples, A/C should bind trusted events for the **latest
assessment episode of the current input**, including the start, final
review-ready result, and any excluded human/physical wait intervals. A prior
DECISION-sourced revision anywhere in that input is a conservative reason to
leave it unmeasured today, not a substitute for identifying the latest episode.
Neither C's fixture timestamp fields nor model-generated timestamps are trusted
Domain telemetry. No new public field, event or schema is proposed by this note.

Required runtime test cases before a later decision: changed input does not
inherit old timing; machine REVISE includes both proposal versions and reviews;
human revision starts/selects the right episode without excluding machine time;
an accepted, fully measured ESCALATE result is not a technical failure; a
technical failure and a still-pending review have different dispositions;
stale/removed or mismatched receipts cannot create samples; retries do not
duplicate a case; all three counts reconcile with the same case cohort and
empty samples omit percentiles. These are requested tests, not executed runtime
coverage or an instruction to alter A-owned code. The existing pure synthetic
accounting suite does not close this telemetry dependency.

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
