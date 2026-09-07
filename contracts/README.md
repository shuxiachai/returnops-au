# F.01 contract artifacts

Start with [the Chinese hand-off guide](../docs/09-interface-contract-v1.md).
Version `1.0.0-rc.3` is a review candidate for
[KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), not accepted F.01.
Its predecessor rc.2 was merged in
[PR #9](https://github.com/shuxiachai/returnops-au/pull/9); that publication does
not include this revision or establish B/C acceptance. Joint review must name
the exact revision being reviewed. Neither candidate is a running API.

## Contents

- `v1/schemas.json`: shared named JSON Schema candidate definitions (Draft 2020-12).
- `v1/openapi.json`: planned public HTTP operations (OpenAPI 3.1.0).
- `v1/examples.json`: synthetic valid/invalid DTO fixtures and *unexecuted* runtime-guard scenarios.
- `../tests/contracts/test_contract_v1.py`: offline artifact checks; no business service or provider implementation.
- `../tests/contracts/test_contract_v1_rc2.py`: five-gap regressions and test-only cross-object/cohort checks, not runtime guards.
- `../tests/contracts/test_contract_v1_rc3.py`: three-target exclusivity, order-block provenance fixtures and the shared HTTP idempotency rule.
- `requirements.txt`: contract-validator dependencies only, not an application dependency lockfile.

## Run in a separate environment

From the repository root, with Python 3.12:

```powershell
python -m venv .venv-contracts
.\.venv-contracts\Scripts\python.exe -m pip install -r contracts/requirements.txt
.\.venv-contracts\Scripts\python.exe -m unittest discover -s tests/contracts -p "test_*.py" -v
```

On macOS/Linux use `python3` and `.venv-contracts/bin/python` instead.
The environment folder is local tooling; never commit it. No API key, account,
network access, running server, PostgreSQL or live model is required **to run
the checks** after installing dependencies.

The checker resolves only the two local contract documents and constructs an
in-memory OpenAPI bundle for specification validation. It enables JSON format
checks. Validate a selected definition (for example `CreateCaseRequest`), **not
the permissive `$defs` registry root**. Missing validation libraries fail the
test run; they are not silently skipped.

## Read the fixtures

Each `positive`/`negative` entry has `name`, `schema` and `value`.
Use the `schema` definition to validate `value`. Negative entries must fail
validation. The JSON fixtures use no real account, token, order, customer,
provider call or file upload; metadata is demonstrative.

Positive and negative entries are DTO examples, not Gold cases; use the current
fixture file for their counts. They include the five risk outcomes and four
Founder decisions. `runtime_guards` entries contain schema-valid requests and
expected error responses. Checking those entries **does not execute the guards
or prove zero provider effects**. Implement their behavior later in
F.03/A1/A2/F.06 tests. Historical rc.1 test totals are not rc.2 results; rerun
the current artifacts and report the actual output.

Local rc.3 validation on 2026-09-07: 44 contract unittest methods passed in the
isolated validator environment. Fixtures: 64 positive, 36 negative and 16
unexecuted runtime-guard scenarios. These totals are artifact evidence only;
rerun after changes and do not describe them as live API or CI acceptance.

A useful mock flow is:

1. `customer-create` → `customer-submitted-view`.
2. `founder-review-ready-view` shows a later fixed proposal, review, source
   excerpts and exact action preview.
3. `founder-approve` → `decision-accepted`; HTTP 202 is not completion.
4. `operation-unknown` → `operation-reconciling` illustrates result lookup,
   not unconditional retry.
5. `notification-failed` → `notification-retry-accepted` →
   `notification-sent` illustrates notification-only recovery.

These are separate illustrative snapshots, not an already executed end-to-end
trace. Original statement, source hash, multi-item/single-parcel and approval
fingerprints are cross-checked where linked; production foreign-key,
concurrency, authorization and state invariants remain future work.

## rc.2 to rc.3 migration

The 13 public operations, five Risk outcomes and four Founder decisions remain
unchanged. A/B/C must update strict consumers together before adopting rc.3.

- Keep `ProcessingFailure` technical. Add `OrderLookupBlock` for an accepted
  pre-proposal `OrderLookupResult.CONFLICT` or `AUTHORITY_DENIED`, with the same
  case/input/status/sanitised message, a server-created block ID and timestamp.
  `NOT_FOUND` remains clarification; provider faults remain technical recovery.
  Source conflicts remain visible in packet/Risk material, not fabricated order
  blocks or technical failures.
- `CaseView` exposes at most one current `processing_failure` or
  `order_lookup_block`; `ESCALATED` without `current_proposal` requires exactly
  one. A block cannot coexist with a current proposal/review/preview. Keep the
  resolved target visible during notification/manual completion; retain earlier
  targets in the audit trail and preserve historical decisions/operations,
  including uncertain effects. Do not clear history to satisfy a current view.
- `FounderDecisionRequest` and `FounderDecisionRecord` have three exclusive
  targets: proposal ID/version, `processing_failure_id`, or
  `order_lookup_block_id`. Both non-proposal targets allow only `MANUAL_HANDLING`
  and forbid approval/scope/preview or operational command fields. The server
  must authenticate the Founder, resolve current case/input/target, enforce
  expected version and `ESCALATED` state, and atomically save the manual outcome
  with notification work only. A new target invalidates old intent; a replay
  with the same accepted key/body returns its original receipt after auth.
- Manual processing ends in `MANUAL_HANDLED` only after the recorded outcome is
  notified; it never proves return/label success. A pre-proposal business block
  without a review-ready latency measurement is `unmeasured`, not a technical
  `failed` sample. Runtime checks and aggregation are still unimplemented.
- The HTTP `Idempotency-Key` parameter now references the shared schema rather
  than duplicating its character rule. This removes divergent definitions;
  it is not evidence of a demonstrated exploit in a running service.

The rc.3 linked fixture checks reject stale/cross-case/source/target mismatches
in test data. They are not imported by application code and do not authenticate
principals or execute service guards. The application must implement these
behaviours in A1/A2/F.03, with B's corresponding UI handling and C's review.

## Historical rc.1 to rc.2 migration

The following records the earlier migration. Its technical-only no-proposal
target is extended by rc.3 above; it is not the complete current CaseView rule.

The URL major version and 13 public operations are unchanged. Update producers,
consumers, strict validators and mocks together before adopting this candidate:

- **Failure-target manual handling:** `ProcessingFailure` records a typed
  technical failure bound to case/input/stage. `CaseView` must include one when
  `ESCALATED` without a current proposal. The existing decisions endpoint accepts
  either `proposal_id + proposal_version` for the four existing decisions, or
  `processing_failure_id` for `MANUAL_HANDLING` only. Targets are mutually
  exclusive. The latter cannot contain proposal/preview/fingerprint/approval
  fields and cannot dispatch return/label commands. The future server must load
  and verify the current case/input/failure, identity, expected version and
  `ESCALATED` state, then record and notify the manual outcome. Do not invent a
  proposal to make a technical failure look actionable.
- **Complete retrieval hand-off:** replace `RiskReviewRequest.passages` with
  required `retrieval_result: RetrievalResult`; preserve its conflicts and
  provenance, not a second parallel passages field. Deterministic checks must
  enforce case/input/corpus agreement and full citation coverage; C2 separately
  reviews semantic support and conflict impact.
- **Compatible capacity:** retrieved passages now allow up to 100 entries,
  matching packet citations, verification checks and the Founder read model.
  This is an upper bound, not a required retrieval size or a 100-case Gold set.
- **Analytics filters and denominators:** the existing analytics GET accepts
  optional `created_from`, `created_before` and one `status`, represented by
  `AnalyticsQuery`. Use case-created time in `[from, before)` and current status
  at `as_of`; omissions mean no lower bound / the snapshot cut-off / all statuses.
  Both times require `from < before` through application validation; invalid
  values or ranges return 422. Responses require `filters` (or `{}`) and latency
  `unmeasured_count`. Every aggregate uses the same cohort and counts each case
  once. For the latest assessment episode of each case's current input,
  `sample_count + failed_count + unmeasured_count = case_count`; p50/p95 cover
  only successful valid measurements. Missing/in-progress data is not a fake
  zero or silently excluded. Current risk uses the current proposal's latest
  valid review, not a historical PASS. A business ESCALATE with a review-ready
  packet and valid measurement is not a technical failure; known terminal
  technical failures remain counted even without a usable latency value.
- **Identifier validation:** opaque IDs reject trailing newlines and control
  characters. Shape validity remains separate from ownership and authority.

Old risk requests and analytics snapshots need migration; even additive fields
may be rejected by strict clients. The candidate does not add roles, business
decisions, product features or a technology stack. Contract checks can reject
invalid shapes and inspect fixture consistency, but cannot prove live state
guards, cross-record citation completeness, aggregation, identity, durable
idempotency or notification delivery. F.01 still requires joint review and the
later implementation/evidence packages remain outstanding.

## Contribution / acceptance

Owner A; named Reviewer C; B confirms frontend consumption.
Requirement/model mapping and the three-person acceptance checklist are in
docs/09. Do not mark F.01 Done or claim tutor approval from an automated
artifact-validation result. F.01 uses
[KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32); baseline review remains
[KAN-12](https://lucastaooo.atlassian.net/browse/KAN-12), linked to Issue #5.
F.02 environment readiness is recorded separately in
[docs/10](../docs/10-f02-environment-readiness.md); its delivery key is still
unmapped, and a contract test pass does not complete that work package.
