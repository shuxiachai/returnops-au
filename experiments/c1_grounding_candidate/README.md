# C1 — versioned retrieval and citation verification candidate

Latest preparation: [27 October excerpt-check proposal](#c104-excerpt-check-handoff-proposal--27-october-2026)
specifies a review record and negative cases without changing the frozen wire
contract. It remains a proposal; corpus admission and C1.04 acceptance are open.

## Current status (submission) — 24 October 2026

Owner C (`lulucas-tao`), reviewer A; [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23),
[Issue #58](https://github.com/shuxiachai/returnops-au/issues/58).
This source-checkout component provides offline, contract-shaped retrieval and
citation checks. Its synthetic pilot and exact-byte admission preparation were
delivered through [PR #59](https://github.com/shuxiachai/returnops-au/pull/59)
and [PR #68](https://github.com/shuxiachai/returnops-au/pull/68).
Merged code is not an approved real corpus, production integration or feature
acceptance. This README addresses [A's Issue #123](https://github.com/shuxiachai/returnops-au/issues/123).

### Requirement and model trace

| Requirement / model | Implemented component boundary |
|---|---|
| FR-006; NFR-001 | `GroundingCandidate.retrieve` returns versioned passage provenance and registered conflicts; `verify_citations` checks exact reference identity/version/hash/location. The pilot corpus is synthetic, not the reviewed runtime corpus required for full FR-006 acceptance. |
| FR-007 | C1 supplies grounding and citation-check results for A's non-executable packet. It does not implement Assessment, accept a current packet or create approval authority. |
| NFR-009 | Retrieval text stays literal data; strict schemas, immutable snapshots and negative tests reject authority-shaped extra fields. This is not a measured frozen-adversarial-suite success rate. |
| AH-08 → UC-02 → MC-ACT/SEQ | Preserve registered material conflicts for C2; do not silently choose source precedence. [C's model chain §13](../../docs/18-member-c-model-chain.md#13-stage-2-implementation-trace--24-october-2026) maps C02/C03 and the C2 handoff to exact test nodes. |

The [project definition](../../docs/00-project-definition-v1.md) and frozen
[C1.01–05 work packages](../../docs/08-delivery-work-packages.md)
remain the acceptance authority; no owner, dependency or target is changed here.

## Run the public synthetic pilot

From the repository root, using the existing locked Python 3.12 development
environment (including `jsonschema`):

```sh
python -B -m experiments.c1_grounding_candidate.pilot
```

This prints the complete JSON report to stdout: file hashes, configuration,
per-query results/misses, citation outcomes and a contract-shaped handoff.
It uses only the committed `data/` fixtures; no model, network, database,
credential or private Gold data is accessed. For a short terminal demo:

```sh
python -B -c "import json; from experiments.c1_grounding_candidate.pilot import run_pilot; r=run_pilot(); print(json.dumps({k:r[k] for k in ('retrieval_summary','citation_summary')}, indent=1))"
```

Observed locally on **24 October 2026**, CPython 3.12.7, source
`e424f6d2283a51e0f9b031d7a3a395fcebed8c0b`, with unchanged `synthetic-pilot-v1`
fixture bytes pinned by [data/manifest.json](data/manifest.json):

| Output field / denominator | Result |
|---|---|
| Queries / queries with expected relevance | 12 / 10 |
| Expected / actual / correct `NO_MATCH` | 2 / 2 / 2 |
| Status / registered-conflict mismatches | 0 / 0 |
| Ranked micro Recall@2, before conflict expansion | 16 / 22 = 0.7272727272727273 |
| Returned-set recall, after conflict expansion | 20 / 22 = 0.9090909090909091; **not Recall@2** |
| Ranked seeds / returned passages, summed across queries | 17 / 21; two queries return more than two passages |
| Query still missing expected passages | `pilot-10-unclear-category` |
| Citation outcomes | `VALID` 2; `NOT_FOUND` 2; `VERSION_MISMATCH` 2; `HASH_MISMATCH` 1; `LOCATION_MISMATCH` 1 |
| Exact citation outcomes / invalid fixtures rejected | 8 / 8; 6 / 6; invalid accepted 0 |

These are public development-fixture results, including the retained miss, not
formal performance, claim-support, legal-correctness or Gold results. Expected
labels remain `PENDING_HUMAN_REVIEW`; `human_approval` is false. The emitted
`checked_at` / retrieval time `2026-10-09T00:00:00Z` is a **fixed test clock**, not
the execution date above. The in-memory no-conflict probe measures ranked seeds
separately from actual conflict-expanded returns; zero-relevance queries have
null per-query recall and separate `NO_MATCH` counts.

## Implementation and limits

- [grounding.py](grounding.py): **keyword-overlap ranking, not BM25**. It counts
  shared unique case-folded tokens after stop-word/short-token removal; ties use
  passage ID. `top_k` bounds ordinary ranked seeds, not required conflict
  counterparts. Closure starts from all positive matches and preserves every
  linked passage of explicitly registered conflicts. It does not discover
  arbitrary semantic conflicts.
- `verify_citations` returns `VALID`, `NOT_FOUND`, `VERSION_MISMATCH`,
  `HASH_MISMATCH` or `LOCATION_MISMATCH`. A Citation contains no quoted excerpt,
  so C1 **cannot check a separately invented quotation**. Matching provenance
  does not prove support, applicability or legal correctness. Those semantic
  questions belong to C2's review design; the current stub tests do not prove a
  real model handles them. The excerpt case in C1.04 is not waived or claimed
  complete by these metadata checks.
- [data/](data/) is wholly invented synthetic source material, even where a
  frozen enum says `REVIEWED_CONSUMER_GUIDANCE`. No human review or external
  guidance authenticity is implied by that enum or by a content hash.
- [admission.py](admission.py) is a separate exact-byte loading boundary.
  `ReviewedGroundingCandidate.from_directory` requires a trusted external
  manifest pin and reviewed metadata. Integration must not use a caller-uploaded
  hash as permission: the loader checks integrity/metadata, not the real identity
  of a reviewer. Passing synthetic approval fixtures is not authentic approval.
  The [ACCC contextual capture](candidates/accc-20261012/README.md) remains
  **captured and hashed, not admitted** (`PENDING_EXACT_BYTES_REVIEW`): A's exact
  byte review, approved manifest and separately trusted runtime pin are absent.
- The admission loader is **macOS/Linux only**: it requires `O_DIRECTORY`,
  `O_NOFOLLOW` and `O_NONBLOCK` and fails closed with `UNSUPPORTED_FILESYSTEM`
  when unavailable. Native Windows is not supported for admission. This does
  not prevent the synthetic pilot/ordinary grounding tests from running on
  Windows; capability-dependent admission tests skip, not pass.
- This directory is not an installed runtime service. There is no production
  corpus selection, three-role wiring, independent live Risk invocation,
  lifecycle persistence, operation authority or Gate 2/Gold acceptance here.

## Tests and review handoff

```sh
python -B -m pytest tests/contracts/test_c1_grounding_preparation.py tests/contracts/test_c1_corpus_admission.py -q -p no:cacheprovider
```

The first file collects [GroundingCandidateTests](tests/test_grounding.py) and
[PilotReportTests](pilot.py); the second covers admission, pending-capture
rejection and supported-filesystem security boundaries. Use the capability
result honestly on each host; neither synthetic approvals nor skipped tests
admit the real capture. The [candidate review instructions](candidates/accc-20261012/README.md#review-requested-from-a)
identify the exact-byte review and integration steps still needed from A.

AI-assisted C documentation and local verification; not C's personal explanation,
A's non-author acceptance or a Jira Done claim.

## C1.04 excerpt-check handoff proposal — 27 October 2026

**C-owned design preparation for A's review, not an adopted port or completed
C1.04.** FR-006/NFR-001 and AH-08 → UC-02 → MC-SEQ require both resolvable
references and an explicit disposition of quoted content. The frozen
`Citation` has identity/version/hash/location, but no quotation or claim text;
`CitationCheck.result` has five metadata outcomes only. Adding a fabricated
quotation to a packet's rationale does not change its metadata result. Do not
rename `VALID`, overload it as semantic approval, or add unreviewed wire fields.

### Proposed compatible review record

Keep `verify_citations` and all F.01 request/response shapes unchanged. For an
offline review, C can record the following **annotation columns**, separately
from the runtime packet. These are not a new public API or trusted authority:

| Annotation | Binding and interpretation |
|---|---|
| Source identity | Exact reviewed source commit, corpus manifest hash, passage ID, document ID/version/location and exact UTF-8 content hash. A hash establishes integrity, not human admission. |
| Packet identity | Case/input/proposal ID and version plus hash of the exact retained packet bytes; identify the JSON text field and zero-based, end-exclusive Unicode code-point range in that field (not UTF-16 code units or grapheme clusters). The selected text must equal the recorded asserted quotation. |
| Quotation kind | Explicit direct quotation, paraphrase or no quotation. Do not silently treat a paraphrase as a failed literal quotation, or an absent quote as a successful match. |
| Source span | For a direct quotation, a nonempty zero-based, end-exclusive Unicode code-point range within the complete pinned `PolicyPassage.content`; exact equality, without case folding, punctuation repair or whitespace normalization. Record UTF-8 hashes separately from code-point offsets. |
| Literal disposition | Match, mismatch, unavailable source, invalid binding, or not applicable (no direct quotation). These are proposed annotation labels, **not additions to `CitationCheck.result`**. |
| Semantic disposition | Separate C2/source-review judgment: supports, contradicts, insufficient context or unresolved. Preserve the full source context, reasons, reviewer and version; literal equality alone gives no semantic credit. |

An omitted sentence, an ellipsis joining disjoint spans, or a paraphrase requires
explicit review; it cannot be presented as a single contiguous exact quote.
If normalization is desired later, version its algorithm and retain the original
bytes and span. Missing bindings/source text remain unavailable, never `VALID`.
The record must not be copied into a trusted approval or used to bypass Domain.

### Development checks required before implementation acceptance

These are proposed checks using invented public passages/packets, not results
already obtained by a quotation checker. The current metadata tests remain the
only implemented C1 verification evidence.

| Case | Metadata check | Additional quotation/support judgment needed |
|---|---|---|
| Correct identity and exact quoted span | `VALID` | Literal match; C2 still checks context and applicability. |
| Same citation, one invented word in quoted rationale | May remain `VALID` | Literal mismatch; do not credit citation correctness. |
| Exact short quote omits a condition in the next sentence | `VALID` | Literal match can coexist with unsupported/misleading claim; C2 reviews the complete passage. |
| Correct text bound to a different proposal/input version | Metadata alone cannot bind the asserted text | Invalid packet binding; retain both versions rather than checking the convenient one. |
| Paraphrase expressing a claim | May remain `VALID` | Literal check not applicable; independently assess claim support. |
| Missing pinned content, invalid range or empty quotation | Metadata result does not supply missing text | Unavailable/invalid annotation; no automatic semantic success. |
| Altered source version/hash/location | Existing mismatch outcome | Resolve provenance first; a matching substring cannot override rejection. |

### Decision requested from A

C can prepare and review these annotations without changing the shared
contract. To integrate a deterministic excerpt checker, A/C must agree where
Assessment supplies the exact asserted text and its packet binding, whether an
internal adapter consumes this separate record, and how the result reaches C2.
Any new public field/outcome needs F.01 change review first. That decision is
separate from reviewing/admitting the ACCC capture's exact bytes and configuring
its trusted runtime pin. The proposed record does not admit that corpus.

The concrete evaluation definitions and separate public development examples
are maintained in [C's E.01 guide](../evaluation_candidate/README.md#e01-definition-draft--requires-a-review-before-freezing).
After the mapping decision, C can implement the selected pure check and its
negative tests locally; runtime adoption, semantic correctness and final
C1.04/C1.05 acceptance still need their original evidence and reviewer.
