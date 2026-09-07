# F.01 contract artifacts

Start with [the Chinese hand-off guide](../docs/09-interface-contract-v1.md).
Version `1.0.0-rc.2` and the prior document/model alignment are published for
review in [PR #9](https://github.com/shuxiachai/returnops-au/pull/9), not merged
into main or accepted by B/C. Confirm the rc.2 hand-offs jointly rather than
treating either artifact as a running API or course-acceptance evidence.

## Contents

- `v1/schemas.json`: shared named JSON Schema candidate definitions (Draft 2020-12).
- `v1/openapi.json`: planned public HTTP operations (OpenAPI 3.1.0).
- `v1/examples.json`: synthetic valid/invalid DTO fixtures and *unexecuted* runtime-guard scenarios.
- `../tests/contracts/test_contract_v1.py`: offline artifact checks; no business service or provider implementation.
- `../tests/contracts/test_contract_v1_rc2.py`: five-gap regressions and test-only cross-object/cohort checks, not runtime guards.
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

Local rc.2 validation on 2026-09-07: 35 contract unittest methods passed in the
isolated validator environment; the full local suite passed 39 tests including
4 unchanged legacy domain tests. Fixtures: 56 positive, 24 negative and 8
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

## rc.1 to rc.2 migration

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
artifact-validation result. Jira mapping is pending; reuse or map the actual
delivery item rather than inventing a KAN key.
