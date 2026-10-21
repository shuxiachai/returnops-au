# C1 next increment: source selection and integration review

Date: 2026-10-11 (Australia/Sydney). Jira: [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23).
Technical issue: [#58](https://github.com/shuxiachai/returnops-au/issues/58).
Owner C; Reviewer A. Traceability: C1.01–C1.05, FR-006/007,
NFR-001/007/009, AH-08, UC-02, [C model chain](../18-member-c-model-chain.md)
and [F.01](../09-interface-contract-v1.md).

Status updated 21 October 2026: **SOURCE_SELECTION_DISPOSITION_RECORDED;
EXACT_BYTES_REVIEW_AND_RUNTIME_ADMISSION_PENDING.**

[A's 12 October disposition](https://github.com/shuxiachai/returnops-au/pull/61#pullrequestreview-5486256534)
at `652196224254cc6b59d9463a3a00e8fb45d34359` permits the three selected
ACCC sources **for next passage capture only**, preserving their qualifications;
STORE-C1-01 remains synthetic. It supersedes this packet's old
`PENDING_A_SOURCE_REVIEW` label, not the separate final-byte admission gate.
[PR #68](https://github.com/shuxiachai/returnops-au/pull/68) subsequently adopted
the loader, tests and pending context candidate (reviewed `4dc60bd`, merged
`437b4eb`). Its [exact contextual capture and coverage record](../../experiments/c1_grounding_candidate/candidates/accc-20261012/README.md)
is now the entry point for final review, rather than this historical selection
plan. `accc-context-20261018-v2` still has pending reviewer/evidence fields and
no trusted runtime approval pin. No source, corpus or manifest bytes change in
this Codex-assisted status correction.

The original 11 October selection rationale follows; completed preparation
and remaining admission work are separated in section 3.
Prepared with Codex assistance from live primary sources and main
`d2e809d1a127e0e38bab4111394752541ad6b8c6`. No personal signature or legal
determination is asserted. This does not expand the frozen research appendix.

## 1. Existing accepted scope

[A's PR #59 review](https://github.com/shuxiachai/returnops-au/pull/59#pullrequestreview-5469070196)
accepts only the synthetic offline development candidate at `cdf3fb8`.
Its corpus and public pilot remain unchanged. Ranked Recall@2 is 16/22;
conflict-expanded coverage is 20/22, not Recall@2. Eight citation fixtures are
fixture evidence, not a general accuracy estimate. This packet does not
promote `PENDING_HUMAN_REVIEW` fixture data to approved consumer guidance.

## 2. Bounded primary-source selection

The following official pages were opened on 2026-10-11. These are **selection
notes**, not final PolicyPassage records or verbatim runtime excerpts. Source
publisher versions were not established, so the future source_version must
remain null unless a real published version is identified; a capture date is
not a publisher version. Category mapping and test design below are project
interpretations for A to review, not ACCC approval of this software.

| Candidate | Official source and section locator | Proposed use / critical context |
| --- | --- | --- |
| SRC-C1-01 | [ACCC: Repair, replace, refund, cancel](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/repair-replace-refund-cancel); “Rights when consumer guarantees aren't met”, “Occasions when consumers aren't entitled…”, major/minor problem and return sections | Faulty/quality category; preserve problem-dependent remedy context and distinguish change of mind. No automatic major/minor classification or guaranteed refund. |
| SRC-C1-02 | [ACCC: Consumer rights and guarantees](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees); “Matches description”, with the nearby example and application context | Wrong-item category; compare supplied item evidence with the recorded description. Guidance itself is not proof of what the customer received. |
| SRC-C1-03 | [ACCC: Contacting a business to fix a problem](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/contacting-a-business-to-fix-a-problem); “A business puts conditions on when it will provide any remedies for problems” | Distinguish conditional change-of-mind policy from fault-related remedies; do not apply an original-packaging condition universally to faulty goods. |
| STORE-C1-01 | Existing [synthetic corpus](../../experiments/c1_grounding_candidate/data/corpus.json), pinned at `cdf3fb8` | Reuse only explicitly synthetic store-policy examples. A reviews their category applicability; they do not become external legal guidance. |

An approved small corpus must cover all three supported categories and necessary
conflicts, but this list alone does not prove that coverage. No live customer
data, production store policy, Gold labels, or broad web crawler is needed.

## 3. Review and admission checklist

Updated 21 October: checked entries describe bounded preparation evidence only.
They do not approve a runtime corpus. The original selection gate is distinct
from final context, category/conflict and exact-byte review.

- [x] A dispositions the source selection for next capture only, with the
  exact source, reviewer, date and retained-context conditions linked above.
- [x] C captures candidate (not approved-for-runtime) passage bytes with source ID/type, canonical
  URL, publisher version or explicit null, access date and a stable human-readable
  section locator. Store policy and external guidance remain distinct.
- [x] C records exact UTF-8 passage content hashes and a versioned manifest of
  the candidate file bytes; local snapshot versions never masquerade as publisher
  versions. No hash is claimed for a page that has not been captured.
- [ ] A reviews the final bytes, category mapping and known-conflict pairs; a
  changed source/hash requires renewed review, not silent replacement.
- [x] A technically reviews and adopts the separate preparation loader/tests
  through #68, including rejection of pending/missing/changed/malformed sources
  and wrong versions. This adoption does not admit the pending candidate.
- [ ] Integration supplies a separately trusted pin only after authentic
  exact-byte/context/conflict review; inventory hashes are not approval pins.
- [ ] C reruns typed retrieval/citation and public pilot tests on that separately
  versioned increment and reports raw misses/errors, without changing Gold labels.

Required tests for that increment: three-category positives, UNCLEAR, OUT_OF_SCOPE,
NO_MATCH versus corpus failure, missing provenance, changed content/version,
invalid citation identity/location, complete material conflict retention and
adversarial source instructions with no authority. C2 decides claim support;
C1 does not become a new decision agent. These are test requirements, not
new tests claimed to have run in this documentation update.

## 4. A ↔ C integration checklist

Use the unchanged RetrievalRequest/Result and CitationVerificationRequest/Result
schemas. Existing reproducible four-DTO handoff: `python -m
experiments.c1_grounding_candidate.pilot` (from repository root with locked
dependencies; see README for commands). Keep the synthetic demo distinct from
the proposed real-source increment.

| Responsibility | Acceptance evidence still needed |
| --- | --- |
| C | Approved corpus identity, complete retrieval/conflicts, exact citation checks and explicit failure results; no Domain write, approval or provider capability |
| A | Retain the exact result and verify citations belong to that result; check current case/input/proposal bindings; reject stale/replayed/cross-case output and fail closed on unavailable grounding |
| C2 | Independently assess support, material conflict and injection; VALID metadata alone never creates PASS or approval |
| A + C | Recorded non-author review of exact integrated source and reproducible positive/negative tests; formal F.01/F.02 and original S/F prerequisites remain distinct |

Next review decision requested from A: review the exact contextual candidate
bytes, category/known-conflict coverage and remaining omissions linked above;
request corrections or record a bounded exact-version disposition. Source
selection and preparation-loader adoption need not be requested again. Runtime
admission still needs genuine final review and a separately trusted pin.
No public API, wire field, A/B implementation, deadline or Gold protocol changes
are proposed. KAN-23 remains In Progress, not Done.
