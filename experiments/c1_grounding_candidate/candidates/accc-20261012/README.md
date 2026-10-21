# C1 contextual capture — 18 October 2026

**PENDING_EXACT_BYTES_REVIEW — not an admitted runtime corpus.** KAN-23 /
[Issue #58](https://github.com/shuxiachai/returnops-au/issues/58); C owns this
candidate, A (`shuxiachai`) is the intended non-author reviewer.
[PR #68](https://github.com/shuxiachai/returnops-au/pull/68) is the review entrance.
This is AI-assisted preparation, not A's approval, feature acceptance or legal advice.

## What changed

The three short ACCC excerpts have been replaced by **three contextual source
blocks**, alongside the same three explicitly synthetic store fixtures.
Corpus version is **`accc-context-20261018-v2`**. Each real block retains its
selected rules and qualifications together in one `content` field; retrieving
that block returns those paragraphs intact, even at `top_k=1`. A qualifier
is not hidden only in this README or in another ranked passage that may be
dropped. All blocks fit the existing PolicyPassage schema. No shared contract,
retriever algorithm or A/B business code changed.

The directory name records its **12 October origin**, not this revision's
capture date. The original minimal sample remains in
[Git history at e15394a](https://github.com/shuxiachai/returnops-au/tree/e15394a05d253d1f5bcdb61aac4559c2a133d604/experiments/c1_grounding_candidate/candidates/accc-20261012).
Real pages were rechecked on **2026-10-18 (Australia/Sydney)**. Their publisher
versions are unknown (`null`); an access date is not a publisher revision.
Synthetic content, hashes and 12 October provenance are unchanged; their
corpus-version references advance with the bundle.

## Bounded coverage and review matrix

| Category / capture IDs | Context now stored in the source block | Limits A must review |
|---|---|---|
| `FAULTY_OR_QUALITY_ISSUE` — `accc-faulty-rights-limit`; `synthetic-sale-fault-rule` | [Repair, replace, refund, cancel](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/repair-replace-refund-cancel): assessment before remedy; major/minor criteria and different remedies; exceptions including misuse/known defects; responsibility; proof, packaging, returning and conditional return costs. | A query hit establishes neither a defect nor its severity or remedy. The fictional blanket sale-item exclusion is deliberately conflicting, not adopted store policy. |
| `WRONG_ITEM` — `accc-description-accuracy`; `synthetic-wrong-item-comparison` | [Consumer rights and guarantees](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees): description rule and delivered-colour example; household/business applicability and exclusions; private-sale limitation; conditional remedies and manufacturer exception. The remedy block above is also mapped to WRONG_ITEM. | The rule does not prove a customer's ordered/delivered facts. The remedy block may be separately retrieved; there is **no forced companion retrieval** for unregistered relationships. Evidence, applicability and severity remain separate assessments. |
| `CHANGE_OF_MIND` — `accc-change-mind-no-general-refund`; `synthetic-change-mind-offer` | [Contacting a business](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/contacting-a-business-to-fix-a-problem): major/minor remedy distinction; optional change-of-mind policy conditions; explicit prohibition on applying those same conditions to major/minor problems. Also mapped to FAULTY_OR_QUALITY_ISSUE. | The invented 21-day coupon offer is not a real merchant policy or a universal statutory deadline. It must not limit faulty-product rights. |

Common return/proof context is **support for FR-005, not implementation of it**.
The captured source describes non-exclusive proof (a receipt is an example),
not an exhaustive list. It does not enumerate or authenticate bank statements,
customer attachments or actual order facts. A should decide whether this bounded
coverage suffices or a targeted additional capture is needed before admission.

Only the existing **one registered conflict** is carried forward: the invented
faulty-sale exclusion versus the contextual ACCC remedy block. Both full
passages must survive conflict closure even if only one matches the query.
Registration is not a legal conclusion, C2 outcome, approval, or proof that all
relevant conflicts were discovered. The rows above are category inventory and
review targets, **not measured recall or Gold success**.

## Exact selection, provenance and attribution

Source text is separate from these project-authored explanations. Each stored
`location` identifies **selected, non-contiguous sections**, not a fabricated
continuous quotation or page number:

- Remedy block: consumer rights/exception sections; major-product criteria,
  solutions and responsibility (hotel example omitted); minor-problem sections;
  returning a faulty product. The separate major-service section is omitted.
  Original service references remain in mixed headings/paragraphs to avoid
  silently rewriting the source; they do not expand the project's goods scope.
- Description block: product introduction, Matches description and its example;
  applicability introduction, household/business use (business examples omitted);
  Private sales; next-step remedies and Contact the business. Other guarantee
  types and special-rule sections are not claimed as captured.
- Contact block: introduction, major/minor product subsections and the complete
  policy-conditions subsection. The intervening manufacturer subsection and
  complaint-template/escalation material are omitted.

Formatting transformations: HTML and link destinations removed, visible link
text retained, bullet markers and whitespace/newlines normalized. Wording of the
selected source paragraphs is preserved; project interpretations stay in this
README and the separately labelled conflict message. Each `content` SHA-256
binds its exact UTF-8 value, **not the entire remote webpage**. No complete remote
HTML archive, publisher authenticity or independent review is claimed.

Source: ACCC © Commonwealth of Australia. Selected text is reproduced under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as described in the
ACCC [copyright and disclaimer](https://www.accc.gov.au/about-us/using-our-website/disclaimer-and-copyright).
Selection/formatting changes are identified above. No ACCC logos, Coat of Arms
or third-party material are included. No endorsement is implied. This is general
guidance, not case-specific legal advice; verify currency and suitability at
review/admission time.

| Inventory | SHA-256 |
|---|---|
| Exact `corpus.json` file | `4367be77154fe3db61683d3bd8d8be7d495a997a63cd95e99cae0fba22fe13e2` |
| Pending `admission-manifest.json` file | `a7dae3158006d2db1e3e70f4c27efabce11826b441457e65678de8ea810095c8` |

**Inventory hashes are not trusted runtime approval pins.** Both review states
remain pending, reviewer/time/evidence are `null`, and
`conflicts_reviewed` is `false`.

## Tests and reproducible local checks

From the repository root with the existing locked Python 3.12 environment:

```sh
python -B -m pytest tests/contracts/test_c1_corpus_admission.py experiments/c1_grounding_candidate/tests/test_grounding.py -q -p no:cacheprovider
python -B tools/checks/run.py offline --baseline-ref 17042b4164a0be878c7a0684cf532217ebeb77ee
```

- Real-candidate **static/negative** checks bind version, file/content hashes,
  unique IDs, schema, the three source URLs, category mapping, retained qualifier
  markers and unchanged synthetic texts. On supported filesystems, even the
  correct inventory hash must produce `UNREVIEWED_CORPUS`; unsupported platforms
  return `UNSUPPORTED_FILESYSTEM` before reading the bundle. The older
  synthetic-only constructor also rejects these bytes. Marker/schema checks
  are omission guards, not legal review.
- Positive retrieval uses **invented synthetic fixtures only**: qualifier-only
  matching with all paragraphs retained; all three categories isolated at
  `top_k=1`; full nonmatching conflict counterpart retained; stable ordering;
  and exact citation hash/location/version checks. Removing a qualifier or
  using an old corpus citation cannot silently validate.
- No test edits this pending candidate to fabricate approval. No real Gold,
  live model, PostgreSQL run, Gate 1/2 integration or end-to-end recall claim is
  implied. The file-descriptor loader is macOS/Linux only; unsupported filesystem
  platforms fail explicitly.

### 19 October: platform-aware admission tests

Addressed A's [Windows capability review](https://github.com/shuxiachai/returnops-au/pull/68#discussion_r4309279551)
without changing the loader or either candidate JSON file. Tests that require
secure descriptor-based reads now check the same `O_DIRECTORY`, `O_NOFOLLOW`
and `O_NONBLOCK` capabilities as the loader; they do not pretend that native
Windows can admit this bundle. Static corpus/provenance checks, invalid pin and
configuration checks, and explicit unsupported-filesystem checks remain runnable.
Capability-removal tests tolerate an already absent flag and verify that both
loader entry points reject before calling `os.open`, with no retained exception
context. All supported-host security assertions are retained.

Local macOS focused verification: **70 tests / 127 subtests** passed. Separate
capability-namespace simulations (each required flag missing, and all three
missing) each ran the 36 admission tests with **6 passed / 30 capability skips**.
These are simulations, **not a native Windows test run** or Windows runtime
support. Corpus/manifest bytes and their pending-review states remain unchanged;
this test correction supplies no approval pin, runtime wiring or acceptance.

## Review requested from A

Local verification on 18 October: **69 C1 tests / 116 subtests** passed. The
existing host offline runner passed 167 contracts, six static groups, 12 checker
and seven runner tests, 14 Mermaid blocks and 64 synthetic-order tests; separate
security (244) and records (36) tests passed. In a non-root, read-only Linux
container with networking disabled, contracts + security + records passed
**447 tests / 1,352 subtests**. Counts overlap. No GitHub Actions run, PostgreSQL
integration or genuine non-author acceptance is claimed by these local results.

1. Compare the **exact v2 bytes** to the three linked sources and locations.
   Check retained qualifications, selection/omission boundaries, source currency
   and whether this bounded goods-return coverage is adequate.
2. Review category mapping, the synthetic merchant distinction and the registered
   conflict; identify missing or incorrectly implied relationships.
3. Request corrections before approval if needed. If acceptable, record a
   genuine non-author review against the final corpus hash. Source-selection
   permission on [PR #61](https://github.com/shuxiachai/returnops-au/pull/61) and
   an earlier loader review are **not** approval of these new bytes.
4. Only after that review, prepare an approved exact-byte manifest referencing
   the genuine review; its bytes/hash will differ from this pending file.
   Supply the trusted pin via separately reviewed integration configuration,
   never caller uploads, model responses or this README.

This PR does not wire the corpus into A's service, create state/approval
authority, change ownership/dependencies, merge main or mark KAN-23 Done.
