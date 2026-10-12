# C1 next-passage capture — 12 October 2026

**PENDING_EXACT_BYTES_REVIEW — not an admitted runtime corpus.** KAN-23 / Issue #58;
Owner C (`lulucas-tao`), intended non-author reviewer A (`shuxiachai`). This is
AI-assisted capture preparation following the source-selection discussion on
[PR #61](https://github.com/shuxiachai/returnops-au/pull/61), not evidence that A
approved these bytes or their sufficiency. No trusted runtime pin is configured.

The folder contains three short ACCC excerpts, three clearly synthetic store
fixtures and one registered conflict. It is a **minimal review sample**, not
complete consumer-law coverage or an accepted policy for a real store. The enum
`REVIEWED_CONSUMER_GUIDANCE` identifies the intended source kind; it does not
grant approval. Both files explicitly retain a pending-review state.

## Review matrix and required context

| Capture IDs | Source / location | Required non-author disposition |
|---|---|---|
| `accc-faulty-rights-limit`, `synthetic-sale-fault-rule` | [Repair, replace, refund, cancel](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/repair-replace-refund-cancel), consumer rights / rights when guarantees are not met | Check the excerpt against the adjacent remedy qualifications: remedy depends on purchase and severity; the business can assess the product; exceptions are listed. Major and minor defects have different remedies. The fictional blanket sale-item exclusion is deliberately problematic, not an adopted policy. The short quote alone must not become an automatic refund rule. **Pending.** |
| `accc-description-accuracy`, `synthetic-wrong-item-comparison` | [Consumer rights and guarantees](https://www.accc.gov.au/consumers/buying-products-and-services/consumer-rights-and-guarantees), products / description accuracy | Check the adjacent delivered-colour example and application/exceptions sections. A general description rule does not establish this customer's ordered/delivered facts; evidence, applicability and proposed remedy still require assessment. **Pending.** |
| `accc-change-mind-no-general-refund`, `synthetic-change-mind-offer` | [Contacting a business to fix a problem](https://www.accc.gov.au/consumers/problem-with-a-product-or-service-you-bought/contacting-a-business-to-fix-a-problem), conditions on remedies | Check the following policy conditions and the explicit distinction from defective-product remedies. The fictional courtesy offer may not be applied as a barrier to faulty-product rights. **Pending.** |

These context notes are **project paraphrases**, not part of the quoted passage
bytes and not automatically supplied by the retrieval adapter. A must decide
whether fuller, context-complete passages are required before admission; this
sample intentionally does not claim that three brief quotes suffice for C1.02.
Conflict registration exposes a comparison for C2, not legal priority, a risk
outcome, an approval or a claim that every relevant conflict has been found.

## Provenance, attribution and exact bytes

- Each source was accessed on **2026-10-12 (Australia/Sydney)**. Publisher
  version was not established and is therefore `null`; the capture date is not
  misrepresented as a publisher revision. Locations are page headings, not
  invented PDF page numbers.
- `content` holds only the selected plain-text sentence for each real source,
  with punctuation preserved and HTML markup omitted. SHA-256 covers its exact
  UTF-8 value, not surrounding JSON formatting or the entire remote webpage.
  Synthetic store text is separately labelled and is not attributed to ACCC.
- Source: ACCC © Commonwealth of Australia. Excerpts are reproduced from the
  linked official pages under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  as described in the ACCC [copyright and disclaimer page](https://www.accc.gov.au/about-us/using-our-website/disclaimer-and-copyright).
  Changes: selection of short excerpts and removal of HTML presentation;
  accompanying context notes and fixtures are project-authored. No ACCC logos,
  Coat of Arms or third-party material are included. No endorsement is implied.
- ACCC material is general guidance, not case-specific legal advice. Currency,
  context and suitability must be checked before a new publication/admission.
- Whole `corpus.json` SHA-256:
  `52ebe3e701e2bb9a684228ad39df8f82caf4e56499e681527c9a88735d771b0a`.
  Pending `admission-manifest.json` SHA-256:
  `513316cc78e08ec85e9ddeab6ac7d9b911d2368c6bf5e72249dca171c428b5fe`.
  **These are inventory hashes, not trusted runtime approval pins.**

## What A must review before a later admission

1. Review exact passage text, source locations, context and source/store
   distinction; request sufficient contextual additions where needed.
2. Review three-category coverage and each registered conflict, including
   omissions. Preserve store fixtures as fictional and keep legal conclusions
   out of the retrieval adapter.
3. Identify final corpus bytes/hash, record a genuine non-author review and
   only then prepare an exact-byte approved manifest referencing that review.
   A later authentic review must match the final corpus; selection permission
   alone is insufficient. A changed manifest has a new hash.
4. Supply the final manifest pin through reviewed integration configuration,
   never by deriving it from caller uploads, a model response or this folder.
   Hashes check integrity only; they do not authenticate the reviewer.

The current loader must reject this bundle with `UNREVIEWED_CORPUS`, even if its
inventory hash is supplied in an isolated negative test. A missing/mismatched
pin fails with `UNTRUSTED_MANIFEST`. Accepting tests use **only synthetic test
approvals**, never this pending capture. The loader is an offline source-checkout
component with macOS/Linux file-descriptor guards; unsupported filesystem
platforms fail explicitly. No network call, model call, state mutation, Gate 1
or Gate 2 integration, Gold evaluation or feature acceptance is claimed.
