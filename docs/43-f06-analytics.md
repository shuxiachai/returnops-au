# Founder analytics read API (F.06)

Owner: A Jingbo Chai. Work package F.06 in the unchanged [work packages](08-delivery-work-packages.md) (reviewer C; start F.01; finish A1.08, A2.06, F.05). Requirements OF-006, FR-011, FR-012, NFR-005, NFR-008, as listed on the frozen operation in `contracts/v1/openapi.json`. This component provides the single counting basis and aggregate API that B's analytics page reads instead of computing its own numbers. This document records no acceptance by C or any other member.

## Route and composition

`GET /v1/founder/analytics`, operation `getFounderAnalytics`, is registered by default in `register_founder_routes` next to the four Founder reads and uses the same dispatch: one Authorization header, server correlation ID, worker thread, `Cache-Control: no-store`, static error envelopes and 503 for anything unexpected. `FounderQueries.read` authorizes through F.03 (`getFounderAnalytics` is FOUNDER-only and has no resource), reads in a read-only `CustomerUnitOfWork` (shared fence, SELECT statements only), authorizes again from the current registry after the read, and commits nothing but the read transaction. No snapshot, cursor, encoding row or audit event is written. The store is always the current actor's store; no request field selects it.

## Query

| Parameter | Rule |
| --- | --- |
| `created_from` | Optional inclusive lower bound on `case.created_at`. RFC 3339 UTC with a trailing `Z`, at most six fractional digits (PostgreSQL stores microseconds). |
| `created_before` | Optional exclusive upper bound, same format. Omitted, or later than `as_of`, means `as_of`, so the window is `[created_from, as_of)`. |
| `status` | Optional single CaseStatus, evaluated at `as_of`. |

Both bounds together require `created_from < created_before`. Timestamps accept only an uppercase `T` separator and an uppercase trailing `Z`, with at most six fractional digits. Unknown names, repeated names, comma lists, offsets other than `Z`, naive or impossible times and unknown statuses are 422 `VALIDATION_ERROR`, but only after authentication and authorization (a customer gets 403 even with a bad query). `filters` echoes the validated strings exactly as supplied, `{}` when none were given.

## Counting basis

One SELECT statement returns the cohort: cases whose store is the Founder's store, `available IS TRUE`, and `created_at` in `[created_from, min(created_before, as_of))`, optionally with the given current status. Without `created_before` the window is `[created_from, as_of)`: a case created in the same microsecond as `as_of` is excluded (the contracts' fixture oracle would include `created_at == as_of`; the difference is only that edge). `as_of` is the server time taken immediately before that statement; every count comes from its single result set, including two correlated EXISTS checks on `lifecycle_event_receipts`, so READ COMMITTED cannot mix two moments. Each case is counted once (a repeated case ID in the result is a 503). Cases removed by retention (`available = false`) are excluded, as in `listFounderCases`. Buckets follow the contract enum order and zero buckets are omitted.

**Current review.** A case counts under a RiskOutcome only when its lifecycle state points to an AVAILABLE REVIEW record that has an accepted review receipt (`lifecycle_event_receipts` with that record ID and event kind `REVIEW` or `REVIEW_PASS`, the two kinds `lifecycle_guards` writes for escalation and pass reviews), whose body decodes (finite v2 or legacy v1 encoding, chosen by the stored encoding row as the history reader does), whose digest matches the record, whose outcome is one of the five RiskOutcomes, and whose review ID, case, input version, proposal ID, proposal version and proposal record equal the current lifecycle state, the case head and the current PROPOSAL record. Anything else, including a missing state, a cleared pointer after a new input or revision, a deleted or redacted review, a stale input and an undecodable body, counts in `cases_without_current_review`. This is lighter than the per-case proof used by `getFounderCase` (`lifecycle_projection` with `accepted_review`): the audit chain and component seals are not replayed, so a review that passes these identity checks but would fail the full proof is still counted here. The full proof remains on the case view.

## Proposal latency: Tier 0 with known proposal failures

`proposal_latency` keeps `sample_count = 0` and no `p50_ms`/`p95_ms`. Tier 0 is kept because the trusted start/ready/wait event fields are the open E.01/E.09 item that C has asked A for (README: "Identify trusted start/ready/wait event fields"); this component does not decide them. The design's start event, intake work DONE for the current input, does not exist for the input a proposal is built for: `customer_intake_work` rows are created only by case creation and clarification (`customer_service._enqueue`), and a MATCHED order result creates the next input through `transition(..., input_delta=1)` (`investigation_processor._accept`, `case_state.transition`). The real-producer PostgreSQL test pins this: the fixed proposal's receipt is for input 2 while intake work exists only for input 1.

`failed_count` counts the known technical failures of the proposal step: a case whose current input has a `PROPOSAL_FAILED` receipt in `lifecycle_event_receipts` (written through `lifecycle_guards` when `proposal_processor` records a failure). docs/09 section 10.2 counts such a failure as known even without a duration. Intake (COORDINATOR) and order-lookup failures happen before the complete input is accepted and stay unmeasured, like every other case: `unmeasured_count = case_count - failed_count`.

**Tier 1 candidate for reviewer C.** The end event is not ambiguous: the current proposal's receipt is unique (`lifecycle_event_receipts.record_id` is unique and equals `case_lifecycle_state.proposal_record_id`), machine REVISE loops belong inside the episode under the contract, and Founder waiting is detectable as a REVISION whose source row is a DECISION (`lifecycle_guards._revision`). Proposed definition: start = `accepted_order_projections.accepted_at` for `input_version = head.input_version`; end = `accepted_at` of the receipt with `record_id = state.proposal_record_id`; unmeasured if a DECISION-sourced REVISION exists for that input; failed = a `PROPOSAL_FAILED` receipt for that input, as now. The percentile and latency-block helpers (linear type-7 percentile in integer milliseconds, exact ratio rounded half-even) are implemented and unit tested as its entry point. It is not enabled until C agrees the events.

The only proposer today is the fixed synthetic proposer (`model_called: false`). Any future latency from this pipeline describes the pipeline, not a model.

## Invariants enforced

Before returning, the response is validated against `AnalyticsSnapshot` (internal mode) and checked for: status buckets sum to `case_count`; risk buckets plus `cases_without_current_review` sum to `case_count`; `sample_count + failed_count + unmeasured_count = case_count`; `p50_ms`/`p95_ms` present exactly when `sample_count > 0`, with `p50_ms <= p95_ms`; no duplicate or zero buckets and enum ordering; every row's status matching the `status` filter; a boolean failure flag per row. A violation is 503 `INTERNAL_ERROR`; a wrong number is never returned.

## Errors

401 `UNAUTHENTICATED` (missing, repeated or invalid token, or a session that changed during the read); 403 `FORBIDDEN` (not a FOUNDER); 422 `VALIDATION_ERROR` (query); 503 `INTERNAL_ERROR` (database, configuration or invariant failure). The contract's 404 and 409 are not produced by this route.

## Evidence

- Offline: `tests/founder/test_analytics_offline.py` (route registration, HTTP query whitelist, query validation matrix, percentile and latency helpers, invariant checks on the contract examples and mutations, current-review identity and accepted-receipt rules, the single compiled statement with its two receipt checks, a scripted PROPOSAL_FAILED row counted as failed, and the service's read-only order of calls with a scripted unit of work).
- PostgreSQL: `tests/founder/test_analytics_postgresql.py` (hand-computed cohort reconciled with the contracts' `assert_analytics_fixture`, a retried proposal counted once, stale, deleted and unaccepted reviews, legacy encoding, a PROPOSAL_FAILED receipt for the current input (failed) and for an older input (not failed), a second store provisioned through the trusted registry and never counted, a full-table no-write fingerprint, the empty cohort shape, a future bound clamped to `as_of`, the 401/403/422 matrix, and real producers: a fixed proposal and an order-lookup failure stay unmeasured, while a capacity failure of the fixed proposer is failed). `tests/founder/test_tcp_founder.py` adds one analytics call over TCP.
- First CI result: pending.

## Changes needed in B's frontend

1. Remove the 501 gate: `getFounderAnalytics` in `apps/web/src/api/client.ts` should call the route in live mode, and the "endpoint not deployed" notice in `FounderConsole.tsx` should go.
2. Send the query parameters `created_from`, `created_before` and `status` and show the echoed `filters`.
3. Fix the mock: `MOCK_ANALYTICS` latency counts (70 + 0 + 2 = 72) must sum to `case_count` (128).
4. Show `sample_count`, `failed_count`, `unmeasured_count` and `as_of`; treat `filters` and `proposal_latency` as required fields.
5. Zero buckets are omitted and buckets come in contract enum order: do not assume 16 status rows, 5 risk rows or fixed positions; look items up by `status`/`outcome`.
6. Send timestamps as RFC 3339 UTC with uppercase `T` and `Z` and at most six fractional digits; anything else is 422.

Contracts, docs/08, docs/09, migrations and `apps/web` are unchanged; the operation's `x-status` label stays as it is until A and C review it.

AI-assisted implementation and metadata preparation; author shuxiachai.
