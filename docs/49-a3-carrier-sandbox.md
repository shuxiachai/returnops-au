# 49. A3 carrier sandbox adapter and recovery path

Owner: A Jingbo Chai. Prepared on 1 November 2026 (Sydney). Work packages A3.01 to A3.03 in [docs/08](08-delivery-work-packages.md); frozen definition in [docs/07](07-frozen-work-allocation.md) section 2.3.

## 1. What A3 is now, and why

The frozen definition of A3 is: put an independent logistics provider's test environment behind the stable core provider interface; map requests, IDs, results and errors; support result verification and a controlled recovery demonstration; keep the same approval and idempotency rules whichever adapter is used; show provider test calls and recovery (failure, unknown, verified recovery) with request correlation IDs and no duplicate effects; keep secrets out of the repository.

The team has no carrier contract and no carrier test account. [docs/17](17-logistics-sandbox-feasibility.md) records that Australia Post / StarTrack testbed access needs an existing contract, and that the lead answered "none" when asked. A carrier's own test environment therefore cannot be called.

On 1 November 2026 the lead decided to deliver A3 as a **contract-test carrier sandbox that this repository runs locally**, reached over real HTTP by a real adapter, and to say so plainly. This page is that plain statement:

- It is not a carrier's test environment. No carrier is contacted, and no real shipment, label or charge exists.
- Tutor acceptance of this substitute is **not yet recorded**. A3.01 asks for a reviewable substitute to be put to the tutor, and A3.03 accepts a contract-test environment only when the tutor explicitly accepts it. Until that acceptance is recorded, A3.03 stays open.
- The core label mock (`CoreLabelMock`, part of A2) is unchanged and is not renamed as A3. The A3 increment over it is: real HTTP to a separate server, request/response and ID mapping, error mapping, idempotency keys enforced by the provider, per-request timeouts sized from the dispatch deadline, and a recovery path that verifies by key.

## 2. Files

| File | Role |
|---|---|
| [packages/returnops_domain/carrier_sandbox.py](../packages/returnops_domain/carrier_sandbox.py) | The sandbox: stdlib `ThreadingHTTPServer` on 127.0.0.1 (port 0 by default), in-memory state, synthetic data, fault injection |
| [packages/returnops_domain/carrier_adapter.py](../packages/returnops_domain/carrier_adapter.py) | Request mapping, the HTTP client with the recovery path, `SandboxCarrierLabel` and `SandboxLabelFactory` |
| [tests/unit/test_carrier_sandbox_offline.py](../tests/unit/test_carrier_sandbox_offline.py) | Sandbox contract, idempotency, 401/409/422, every fault |
| [tests/unit/test_carrier_adapter_offline.py](../tests/unit/test_carrier_adapter_offline.py) | Adapter outcome per scenario, one label per key, request IDs, no key in records |
| [tests/lifecycle/test_label_carrier_sandbox_postgresql.py](../tests/lifecycle/test_label_carrier_sandbox_postgresql.py) | The actual label execution on PostgreSQL 17 with the sandbox factory |
| [tools/carrier_sandbox/run_recovery_demo.py](../tools/carrier_sandbox/run_recovery_demo.py) | Offline evidence command (no database) printing one JSON receipt |

## 3. Sandbox contract

All requests need `Authorization: Bearer <test key>`. The key in the code, `sandbox-test-key-not-secret`, is a fake test key for the local sandbox; it is not a credential for any service. Every response, including errors, carries an `X-Request-Id` (`SBXR` plus 12 hex characters). A valid `X-Correlation-Id` sent by the client is echoed and logged.

| Request | Answers |
|---|---|
| `POST /v1/labels` with `Idempotency-Key` and the JSON body below | 201 and the new record on first use; 200 and the same record for the same key and the same body; 409 for the same key with a different body; 401 for a missing or wrong test key; 422 for an invalid body or a missing or invalid `Idempotency-Key` |
| `GET /v1/labels/by-key/{idempotency_key}` | 200 and the record, or 404 |
| `GET /v1/labels/{label_id}` | 200 and the record, or 404 |

Request body (exactly these fields): `client_reference`, `parcel_reference`, `return_reference` (each 1 to 128 of `A-Z a-z 0-9 _ . : -`), `label_format` = `PDF`, `service` = `RETURN`, `chargeable` = `false`. A record is `label_id` (`SBXL` plus 10 hex), `tracking_number` (`SBXT` plus 10 hex), `status` = `CREATED`, `created_at` and the three references. Generated identifiers never contain six digits in a row, so evidence files never hold a nine-digit number.

Faults are set only by the test or demo that owns the sandbox (`CarrierSandbox.inject(fault, times=1, delay=...)`), never by request content. `times=None` keeps the fault until `clear()`.

| Fault | Effect on the next POST |
|---|---|
| `error_before_commit` | 503, nothing stored |
| `timeout_after_commit` | The label is stored, then the answer is delayed longer than the client timeout |
| `reject_auth` | 401 even with the right test key |
| `invalid` | 422 even with a valid body |
| `delay_before_commit` | The request waits before storing (a late original); a later request with the same key may store first, and the late one then replays with 200 |

## 4. Adapter, mapping and recovery path

`SandboxCarrierLabel` subclasses `CoreLabelMock` and overrides only `_outcome(control, command)`, the point where the core mock decides the effect. The tests check that `perform` and `_insert` are the core functions.

Request and ID mapping:

| Core value | Sandbox field |
|---|---|
| control `effect_key` | `Idempotency-Key` header (never logged or recorded) |
| command `command_id` | `client_reference` |
| command `parameters.parcel_id` (must equal the control's `parcel_id`) | `parcel_reference` |
| control `provider_return_id` | `return_reference` |
| command `parameters.label_format` = `PDF`, `parameters.chargeable` = `false` | `label_format`, `chargeable`; `service` = `RETURN` |

A command that is not a non-chargeable PDF `GENERATE_LABEL` for the control's parcel is not sent; `_outcome` returns `FAILED` (no effect).

Result and error mapping:

| Sandbox answer | `_outcome` result |
|---|---|
| 201 or 200 with a record whose references equal the request | `SUCCEEDED`; the fenced insert then writes the label ledger exactly as before |
| 401 or 403 on the first attempt | `FAILED` (`CARRIER_AUTH_REJECTED`) |
| 409 on the first attempt | `FAILED` (`CARRIER_IDEMPOTENCY_CONFLICT`) |
| 422 on the first attempt | `FAILED` (`CARRIER_INVALID_REQUEST`) |
| Timeout, connection error, 5xx, any other status, or a record that does not verify | Recovery path |

Recovery path, all with the same key and the same body:

1. Look the key up with `GET /v1/labels/by-key/...`, at most 3 times with pauses of 0.05, 0.1 and 0.2 seconds. A verified record gives `SUCCEEDED`. A record that does not match the request gives an unknown outcome.
2. If no label was found, retry the POST once with the SAME key. The provider's idempotency means this cannot create a second label, also when a delayed original arrives later (it replays with 200). A plain 404 is never taken as proof that nothing happened.
3. If the retry does not return a verified record, look the key up once more. A refusal after an uncertain first attempt is not proof of no effect, so it never becomes `FAILED`.
4. Still unconfirmed: `_outcome` raises `CarrierOutcomeUnknown`; `perform()` returns its existing `UNKNOWN` reply, the transaction rolls back and no ledger row is written.

Timeouts. `label_execution.py` sets `dispatch_deadline = min(reservation time + 30 s, preview expiry)`. The carrier call may use at most `min(12 s, time to the deadline - 5 s)`; each request's timeout is `min(2 s, remaining budget)`, and no attempt starts with less than 0.2 seconds left. The 5 seconds left over are for the fenced insert and the final checks. When less than 0.2 seconds are available nothing is sent and `_outcome` returns `FAILED` (`CARRIER_NOT_SENT_DEADLINE`). The client only accepts `http://127.0.0.1:<port>`, so it cannot be pointed at a real carrier.

Evidence on the instance. `adapter.carrier_result` holds the outcome, the mapped error, whether recovery was used, the synthetic `label_id` and `tracking_number`, one correlation ID per call (`A3C` plus 12 hex, sent on every attempt) and the attempts. Each attempt records phase, method, route template (`/v1/labels/by-key/{idempotency_key}`, never the key), status or transport error, `X-Request-Id` and elapsed milliseconds. The sandbox keeps its own log of method, route template, status, request ID, correlation ID and fault, so a timed-out request still has a server-side request ID.

## 5. How it plugs in under the same approval and idempotency rules

`LabelExecutionService` already takes `mock_factory` and calls `mock_factory(engine)` once per dispatch or query (`label_execution.py`, `_perform`). The adapter is switched in through that parameter, with no change to `label_execution.py`:

```python
from returnops_domain.carrier_adapter import SandboxLabelFactory
service = LabelExecutionService(engine, authority, mock_factory=SandboxLabelFactory(sandbox.base_url))
```

Everything before and after `_outcome` is the unchanged core code: the current Founder session, the exact approval chain, the execution and effect grants, the provider permission, the dispatch claim and deadline, the fenced insert with its live re-checks, the confirmation and the existing `FAILED`, `UNKNOWN` and `DENIED` handling. The adapter cannot widen any of these. The core effect key is the provider idempotency key, so a repeated dispatch cannot create a second ledger row (unique `effect_key`) or a second sandbox label (same `Idempotency-Key`).

## 6. Evidence commands and results

Commands (Linux container, from the repository root, with the locked dependencies installed and `PYTHONPATH=apps/api:packages`):

```text
python -B -m pytest tests/unit/test_carrier_sandbox_offline.py tests/unit/test_carrier_adapter_offline.py -q
python -B tools/carrier_sandbox/run_recovery_demo.py
DATABASE_URL=postgresql+psycopg://...@.../returnops_f02_ci python -B -m pytest tests/lifecycle/test_label_carrier_sandbox_postgresql.py -q
```

Candidate run on 1 November 2026, before integration, in Linux containers: python:3.12-slim-bookworm at the digest pinned in the Dockerfile with `requirements-dev.lock`, and postgres:17-bookworm at the digest pinned in ci.yml and compose.yaml. Since the integration on 1 November 2026, CI runs them: the two offline files and the demo in the offline job, and the PostgreSQL file in the lifecycle part label_execution_bridge_3.

| Check | Result |
|---|---|
| Offline sandbox and adapter tests | 29 passed, 48 subtests passed |
| Recovery demo receipt | exit 0; 7 scenarios as expected; 4 labels stored in total, at most one per key |
| PostgreSQL label execution with the sandbox factory | 8 passed: normal label and confirmed replay without a second carrier call; `timeout_after_commit` recovered with one sandbox label and one ledger row; `reject_auth` ending in the existing FAILED handling; persistent failure ending in the existing UNKNOWN with no ledger row; missing grants, a customer caller and a wrong approval key denied with zero carrier requests; a session revoked after the reservation denied inside the fence before the carrier call |

Demo scenarios and what each one shows:

| Scenario | Adapter attempts | Outcome | Labels for the key |
|---|---|---|---|
| normal | POST 201 | SUCCEEDED | 1 |
| error_before_commit | POST 503, GET 404, POST 201 | SUCCEEDED (verified recovery) | 1 |
| timeout_after_commit | POST timeout, GET 200 | SUCCEEDED (verified recovery, no second POST) | 1 |
| reject_auth | POST 401 | FAILED | 0 |
| invalid | POST 422 | FAILED | 0 |
| late_original | POST timeout, GET 404, POST 201; the late original then replays 200 | SUCCEEDED | 1 |
| still_unknown | POST 503, GET 404, POST 503, GET 404 | UNKNOWN | 0 |

## 7. Limits

- This is a contract-test sandbox in this repository, on 127.0.0.1, in memory. It is not a carrier's environment and it proves nothing about a particular carrier's API, idempotency window or error behaviour.
- It is not in the S5 driver path: `tools/r02`, the Railway demonstration and the HTTP API still use the core mock. No route or startup code builds the adapter.
- The fenced insert is unchanged, so the ledger keeps the core's own stable `provider_label_id` and, for `FAILED`, the error code `INTERNAL_ERROR`. The sandbox `label_id`, tracking number and mapped carrier error exist only as evidence on the adapter instance.
- The carrier call runs inside the fenced dispatch transaction, where the core mock decides the effect. The provider-permission row stays locked for the call, at most 12 seconds; another label dispatch in the same store meanwhile waits on its 5-second lock timeout.
- A later reconcile reads only the core ledger: the query path never calls `_outcome`. If the sandbox stored a label but the adapter could not confirm it within the budget, the case stays `UNKNOWN` and that sandbox label is not linked. Querying the provider during reconcile would need a change to the fenced mock, which A3 does not make.
- The per-request timeout is a socket timeout (connect and each read); the call budget bounds the total. The budget compares the application clock with the database-set deadline; the 5-second margin also covers a small clock difference between the two.
- CI runs the tests since the integration on 1 November 2026: the offline job of `.github/workflows/ci.yml` runs the two `tests/unit` files and the recovery demo, and the PostgreSQL file is registered in `tools/checks/lifecycle-groups.json` (group `label_execution_bridge_3`), with the group count in `tools/checks/run.py` and the file count in `tools/checks/test_run.py` (69) raised to match.

## 8. Traceability

`FR-010` (execute only allowlisted, exactly approved commands; a repeated key has at most one effect; an ambiguous timeout is reconciled with the provider before any retry), `OF-004` (independent logistics sandbox/test-mode adapter with recovery), `UC-04` (execute exactly the approved simulated return and label action), `NFR-004` (idempotent operations, no duplicate effects; duplicate-effect count 0 in every test and demo scenario), `NFR-007` (logistics behind a typed, versioned interface; replacing the provider does not change approval rules; provider contract tests pass). Model: the OperationAttempt state machine in [docs/12](12-member-a-model-chain.md) and the Governed Approval and Execution activity of [docs/00](00-project-definition-v1.md), with the provider-specific adapter and recovery extension that [docs/08](08-delivery-work-packages.md) section 5 names for A3. The recovery path is the provider-specific reconciliation step of that state machine; it does not add a state.

## 9. How a real provider would replace the sandbox

1. Obtain authorised test access first (A3.01): a contract or programme that grants a test environment with no shipment or charge, and written scope for this project. Record only non-sensitive references.
2. Re-derive the mapping and error tables from the provider's own documentation, and confirm that it offers an idempotent create with a stable client key and a lookup by that key ([docs/17](17-logistics-sandbox-feasibility.md) section 2). Without both, remove the retry step: an uncertain result must stay `UNKNOWN`.
3. Write a client for that contract with the same `create_label` result shape, HTTPS, an explicit host allowlist and the test credential read from the environment or a secret store at run time, never from the repository, logs or evidence.
4. Keep `SandboxCarrierLabel`'s single `_outcome` override and the factory, so the approval and idempotency rules stay the core code. A new provider identity in the label configuration and permissions would be a domain change with its own review.
5. Keep this sandbox and its tests as the contract-test double, and add recorded-response tests for the real provider.

AI-assisted implementation and metadata preparation; author shuxiachai.
