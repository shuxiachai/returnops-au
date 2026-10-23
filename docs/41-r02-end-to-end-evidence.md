# R.02 no-LLM end-to-end run evidence

Owner: A Jingbo Chai. Designated human reviewer: C Yuwei Tao. This document records how work package R.02 produces its Gate 1 run evidence, the first actual CI result of that evidence and the lead's decisions about its dependencies. It does not accept R.02, A2.06, A2.07 or Gate 1, and it changes none of the frozen [work packages](08-delivery-work-packages.md). Technical delivery is [PR #89](https://github.com/shuxiachai/returnops-au/pull/89) (branch `feat/r02-no-llm-driver`). The operating instructions are in the driver's own [README](../tools/r02/README.md).

## Purpose and work package

R.02 is the "no-LLM Gate 1 safety run evidence" row of [docs/08](08-delivery-work-packages.md): Owner A, Reviewer C, start dependency A2.07, finish dependencies R.01, F.02, F.03, F.05, F.07 and E.10. Its acceptance asks for a clean environment that completes Create Case, Mock Order, Fixed Proposal/Risk Stub, Founder Approval, simulated Return/Label and Notification/Audit in that order, with PostgreSQL migration, RBAC, guard, idempotency, negative-test and Docker/CI evidence. The Gate table accepts Gate 1 with a fixed proposal and a fixed risk result, and no LLM may join an execution chain that can trigger simulated operations before R.02 passes.

Requirements: FR-009, FR-010, FR-011, FR-012; NFR-001, NFR-002, NFR-003, NFR-004, NFR-006, NFR-007, NFR-008. Models: [governed-execution-activity](diagrams/member-a/governed-execution-activity.puml) and [exact-scope-sequence](diagrams/member-a/exact-scope-sequence.puml). The run receipt records both lists.

## Composition (route C)

The private driver [`tools/r02/driver.py`](../tools/r02/driver.py) starts the real API itself. [`api_child.py`](../tools/r02/api_child.py) runs `create_app(engine, auth_config, enable_processor=False, enable_fixed_proposal=False, enable_founder_decisions=True)` in a child process on an ephemeral loopback port, polls `/health/ready` and terminates the child at the end, following [tcp_support](../tests/founder/tcp_support.py). The composition is one constant (`api_child.COMPOSITION`) that the receipt also records. The child receives an allow-listed environment, not every variable of the caller.

Production code is unchanged: `main.py`, `demo.py` and the installed packages `returnops_api` and `returnops_domain` are not edited, and no flag, route or grant is added to the default application. `tools/r02` is not packaged (pyproject and the Dockerfile cover only the two packages), is never imported by `apps/` or `packages/`, and imports nothing from `tests/` at run time. PR #89's implementation commit adds the five driver modules, the driver README and `tests/founder/test_r02_driver_offline.py`, adds the separate CI job to `.github/workflows/ci.yml` with its guard in `tools/checks/test_run.py`, and adds one sentence to [docs/33](33-a201-pass-review.md) naming the unpackaged copy of the controlled scenario in `tools/r02/scenario.py`.

`demo.py serve` was not used because:

- It cannot switch off the intake and investigation workers that `main.create_app` starts. Those workers use the builtin order catalogue, while the controlled PASS family needs the synthetic cups catalogue; a catalogue mismatch makes investigation report a configuration change and pause the work.
- Its fixed-proposal worker claims any store's case awaiting a proposal and builds the default manual-handling proposal, which cannot pass the controlled review. Installing the cups builder in the server would give every case a fabricated supported proposal visible to the Founder, contrary to [docs/33](33-a201-pass-review.md), and would require production changes and document revisions.

Route C needs no production change, adds no switch, has no worker competing for the case and leaves default behaviour unchanged. Its cost is recorded as limitations: the API is composed by the driver, not started by `demo.py serve`, and the image default CMD is not exercised. The background-worker path keeps its own existing real-database evidence (`tests/lifecycle/test_proposal_tcp_postgresql.py`).

## Driver steps

Each step is one of four kinds: **HTTP** (a real request to the API child over loopback TCP), **in-process** (the same processor classes the API workers use, run by the driver for this one case), **private service** (an existing `compose_private_*` Domain service with no public route) and **trusted setup or read** (registry/policy provisioning, grant rows, read-only database checks).

| Step | Kind | What happens |
|---|---|---|
| 0 | trusted read | Environment fingerprint: PostgreSQL major version 17, `alembic_version` exactly the API's expected revision, Python version, source-tree digests; refuses a database with case rows or existing driver identities. The driver never migrates. |
| 1 | trusted setup | Trusted registry: two customers and one Founder in one synthetic store, 899 s sessions (the `demo.py` fields). Deterministic cups catalogue and its read grant. `FixedProposalPolicy.grant(store, synthetic_demo=True, enabled=True)`. |
| 2 | process | API child with the composition above. |
| 3 | HTTP | Customer `POST /v1/evidence`, then `POST /v1/cases` with the synthetic two-cups statement, `RETURN` and order `SYN-CUPS-PASS`. A read-only check confirms the case is still `SUBMITTED` with one `PENDING` intake work, so the API child ran no worker. |
| 4 | in-process, then HTTP | `IntakeProcessor.run_once()` and `InvestigationProcessor(catalogue=cups).run_once()` (both refused if another case has pending work), then `FixedProposalProcessor(build=build_positive).process(prepare(case))`. Founder `GET /v1/founder/cases/{case_id}` shows `RISK_REVIEW` and the current proposal. |
| 5 | private service, then HTTP | Controlled PASS receiver + risk stub (`compose_private_pass_review` with the controlled synthetic adapter), then `compose_private_preview` accepts the action preview. Founder GET reads `case_version`, the current proposal and `action_preview`. |
| 6 | HTTP | Founder `POST /v1/founder/cases/{case_id}/decisions`, negative cases first: a customer bearer gets 403 with no write; a wrong scope fingerprint under another key gets 409 `INVALID_STATE` with no business change and one `FOUNDER_APPROVE_DENIED` audit. Then APPROVE with key K gets 202, and a same-key same-body replay returns the identical receipt. A read-only snapshot follows. |
| 7 | private service | With the Founder's bearer and K as the original approval key: approval admission check, execution preparation, CREATE_RETURN, return-to-label bridge, GENERATE_LABEL, label PDF artifact, notification `produce_return`, then `send`. The case version is re-read before each versioned step. |
| 8 | HTTP, then trusted read | Founder GET of the case, DECISION/APPROVAL/OPERATION/NOTIFICATION history and the complete audit, every page. Read-only checks of the return and label ledgers and the notification control and fact. |
| 9 | output | `run-receipt.json`, the catalogue document and, with `--keep-api-log`, the screened API child log. |

A primary call is accepted only as `PREPARED`, `COMMITTED`, `ACCEPTED`, `READY` or `SENT`. `UNKNOWN` gets exactly one same-key recover or reconcile call and only that path may answer `REPLAYED`; `DENIED` stops the run; nothing is retried with a replacement key. The receipt's `produced_by` names the path that produced each accepted result.

## Grants inserted just before use

No production composition creates these grants, and no HTTP grant endpoint exists. `tools/r02/grants.py` inserts each group immediately before the step that first needs it, field for field like the `tests/lifecycle` provision helpers and with constants imported from the packages. Inserting them all at once is untested and is not done. The receipt lists every inserted row.

| Before | Purpose / table rows |
|---|---|
| Step 1 provisioning | Investigation service and provider read grant for `synthetic_commerce`; `PROPOSAL` authority for `fixed-synthetic-proposal-v1` |
| Controlled PASS review | `REVIEW` for `controlled-pass-review-v1` |
| Action preview | `PREVIEW` for `action-preview-v1`; `APPROVAL` for `founder-approve-v1` |
| Approval admission | `EXECUTION` for `founder-approve-v1` |
| CREATE_RETURN (after preparation) | `EXECUTION` and `EFFECT` for `operations-return-v1`; return provider permission `CREATE_RETURN`, `provider-mock-return`, `core-return-sql-v1` |
| GENERATE_LABEL | `EXECUTION` and `EFFECT` for `operations-label-v1`; label provider permission `GENERATE_LABEL`, `provider-mock-label`, `core-label-sql-v1` |
| Label PDF artifact | `EFFECT` for `operations-label-artifact-v1`; artifact permission with PDF profile `mock-label-pdf-v1` |
| Notification | `NOTIFICATION` for `notification-delivery-v2`; `OUTCOME` for `notification-outcome-v2` |

The approval itself grants nothing: the receipt checks that no enabled `EXECUTION` authority exists immediately after APPROVE.

## Mock boundaries

No real money, message, carrier or model is involved.

- **Money:** the action preview is `SIMULATED`, AUD, amount ceiling 0 minor units, and the label command is not chargeable (`preview_profile.PROFILE`).
- **Carrier and return provider:** return and label run against `provider-mock-return` and `provider-mock-label` with the core SQL mock configurations; the PDF is the mock label profile.
- **Message:** the notification channel is `CORE_MOCK`; no email, SMS or chat is sent.
- **Model:** the fixed proposal records `fixture-no-live-model` with zero tokens; the controlled PASS receiver + risk stub is a fixed synthetic adapter with zero tokens. No LLM is called.
- **Data:** synthetic identities (`r02_synthetic_store`, `r02_customer_one`, `r02_customer_two`, `r02_founder`) and the synthetic catalogue `synthetic-cups-pass-v1` from provider `synthetic_commerce` (`mock-orders-v1`).

The controlled PASS receiver + risk stub is Gate 1's fixed risk result. It is not C's review and not an independent risk assessment. [docs/35](35-a201-preview-approval.md) forbids a default preview/review producer, and none is added. No public preview, grant, reconcile or retry endpoint, no revoke-approval action and no client-supplied trusted approval is introduced.

## Receipt format `r02-run-receipt/v1`

The receipt is one JSON file. Top-level fields: `format`, `work_package`, `gate`, `route`, `result` (`PASSED`, `FAILED` or `REFUSED`; exit codes 0, 1, 2), `started_at`, `finished_at`, `environment` (PostgreSQL version, alembic heads, Python, platform, CI commit, source-tree digests of `returnops_api`, `returnops_domain` and `tools/r02`), `clean_environment`, `options`, `identities`, `catalogue`, `case_id`, `approve_request`, `steps` (status, safe code, HTTP status, correlation ID, idempotency key and case version per step), `produced_by`, `time_budget`, `checks`, `limitations`, `requirements`, `models`, `api_log` and `private_directory_removed`. A failed run adds `stop` with its code and step; a failed cleanup stage adds `cleanup_failures` (codes only). Since 23 October 2026 the raw API child log stays in the private directory until it is screened (C's review finding R02-C-02).

Before writing, the serialized receipt is refused if it contains `Bearer`, a session token, the signing key, the raw `DATABASE_URL`, its password, or the output, private or home directory; a reduced receipt with code `RECEIPT_REDACTION_FAILED` is written instead. The signing key and tokens exist only in memory and in a 0600 file inside a 0700 temporary directory removed at the end of the run; that directory is never uploaded.

`result` is `PASSED` only when every check below is true. Each check proves only the stated fact for this one run and case:

| Check | What it proves |
|---|---|
| `api_process_ran_no_worker` | After HTTP creation the case is still `SUBMITTED` with exactly one `PENDING` intake work: the API child processed nothing. |
| `proposal_no_live_model` | The current proposal's model run is `fixture-no-live-model` with zero input and output tokens. |
| `controlled_reviewer_called_once` | The controlled synthetic adapter was invoked exactly once. |
| `review_no_live_model` | The current review's model run is the controlled fixture provider and model with zero tokens. |
| `preview_environment_simulated` | The approved scope's environment is `SIMULATED`, equal to the preview profile. |
| `preview_amount_ceiling_zero` | The scope's amount ceiling is 0. |
| `preview_currency_aud` | The scope's currency is AUD. |
| `preview_allowlist_profile` | The scope's allowlist version equals the preview profile version. |
| `preview_return_provider_mock` | The first command is `CREATE_RETURN` on the mock return provider. |
| `preview_label_provider_mock` | The second command is `GENERATE_LABEL` on the mock label provider. |
| `preview_label_not_chargeable` | The label command and the profile are not chargeable. |
| `negative_customer_token_no_write` | A customer bearer's decision changed neither the case head nor the audit event list. |
| `negative_wrong_fingerprint_no_business_change` | A wrong fingerprint created no DECISION history and left case version, input version, status and history sequence unchanged. |
| `negative_wrong_fingerprint_one_denial_audit` | That denial appended exactly one audit event, `FOUNDER_APPROVE_DENIED`. |
| `approve_replay_identical_receipt` | The same-key same-body replay returned the identical 202 receipt. |
| `approved_once` | The case is `APPROVED`, its version is the expected version plus one and equals the receipt's, and the receipt carries an approval ID. |
| `execution_work_pending_after_approval` | Exactly one EXECUTION work exists, `PENDING`, epoch 0, unclaimed. |
| `zero_effects_after_approval` | No effect row exists for the case after approval. |
| `no_execution_grant_after_approval` | The store has no enabled `EXECUTION` authority after approval. |
| `prepare_keeps_case_version` | Execution preparation did not change the case version. |
| `within_preview_window` | The label artifact completed before the 300 s preview expired. |
| `within_session` | Notification send finished before the 899 s sessions expired. |
| `final_status_completed` | The Founder GET reports final status `COMPLETED`. |
| `history_order_decision_approval_operation_notification` | The first DECISION, APPROVAL, OPERATION and NOTIFICATION history sequences are strictly increasing. |
| `audit_chain_linked` | Every audit event names its predecessor's hash; the first names none. |
| `audit_chain_hashes_recomputed` | Every audit hash recomputes from the complete ordered pages. |
| `audit_one_approve_denial` | The complete audit holds exactly one `FOUNDER_APPROVE_DENIED`. |
| `operations_mock_providers` | Every OPERATION history entry names the mock return or label provider. |
| `notification_sent_return_created` | The latest NOTIFICATION history entry is `SENT` with outcome `RETURN_CREATED`. |
| `return_ledger_mock_provider` | Exactly one return ledger row, `SUCCEEDED`, with the mock provider and configuration. |
| `label_ledger_mock_provider` | Exactly one label ledger row, `SUCCEEDED`, with the mock provider and configuration. |
| `notification_channel_core_mock` | One notification control and one fact, both `CORE_MOCK`, the fact `SENT`. |

These checks do not exercise fault injection, a second store, concurrency, an independent risk assessment or a deployment. Those properties keep their own tests (see [docs/42](42-e10-coverage-map.md)).

## First actual result

| Item | Recorded value |
|---|---|
| Pull request and head | PR #89, head `510e1acd8f988c9478e13824137c6ac4363a704f`, then based on PR #78 head `fa42acf8ef36c543fee6782b548c10c17af417ae` |
| CI checkout | `fdeca0c9ba4fd9f735bdcdc0d1e9d2bbbe334314`, the pull-request merge commit of that head into its base (receipt `environment.ci_commit`) |
| Run and job | [Run 39634415393](https://github.com/shuxiachai/returnops-au/actions/runs/39634415393), job `end-to-end-no-llm` ("R.02 no-LLM end-to-end driver", job ID 119340936749), conclusion success; driver output `R.02 driver result: PASSED` |
| Receipt | `result` `PASSED`; 36 step records; `produced_by` 11 of 11 `primary` (no recovery path used); 32 of 32 checks true |
| Timing (UTC) | Started 2026-10-21T16:24:37.369379Z, finished 2026-10-21T16:26:29.509284Z (22 October 03:24-03:26 Sydney) |
| Time budget | Preview accepted 16:24:41.499Z, expires 16:29:41.165Z; label artifact completed 16:25:07.872Z (26.707 s of 300 s); chain finished 16:26:10.953Z; sessions 16:24:36Z to 16:39:36Z |
| Case progression | `AWAITING_APPROVAL` at case version 6; approved at 7; notification `READY` at 11; `SENT` and final `COMPLETED` at 13 |
| Read-back | 28 audit events; history DECISION 1, APPROVAL 1, OPERATION 7, NOTIFICATION 3 |
| Environment | PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2); alembic head `0014_notification_delivery`; CPython 3.12.15; Linux x86_64 runner |
| Source digests | `returnops_api` 31 files `b7c017fd282d9d38500c556b67d7f45f737501bcfd821454d52468d3f8d6087e`; `returnops_domain` 121 files `cfd9d008b047f08f9e63cfe17d12be959d49cf7840769e1c2e9d1dcd39b6bbdb`; `tools_r02` 5 files `db09ea750a8197e3bb3272027fee2a26b246b37034de13d5696889ac9dc62f60` |
| Catalogue | `synthetic-cups-pass-v1`, `dataset_sha256` `18333dd06fef6fd411d1ac9f71e16f32957fad168b610950c9996488437244bd` |
| Artifact | `r02-end-to-end-39634415393-1`, 5938 bytes, expires 2026-11-04T16:26:29Z |
| Privacy scan of the receipt | No `Bearer`, database password, JWT prefix or runner home path found; private directory removed |
| Whole run | 12 of 12 jobs success (observed complete 2026-10-21T17:22:17Z) |

The receipt was extracted from the job log's "Show the run receipt" step; the execution record outside the repository tree keeps it with the observation. The whole-run line states job conclusions only; this document does not relabel any other job's node results. After PR #78 was merged, PR #89 was rebased onto main `0758696681cc706fda14ba378b7baa8e8c6580b3` with the same tree; any run on a later head is a separate result recorded by its own CI receipt.

The receipt's five limitations, verbatim:

1. The API child is composed by the driver with create_app(...); demo.py serve and the image default CMD are not exercised.
2. Intake, investigation and the fixed proposal run in the driver process for this case; the API process runs no worker.
3. Docker evidence remains the existing image build and import probe; this run is not a deployment proof.
4. The controlled PASS receiver + risk stub is the fixed risk result of Gate 1, not an independent risk assessment.
5. A PASSED receipt or a green CI job is not human acceptance; R.02 still needs its designated reviewer.

## Dependencies, acceptance and the lead's exception

[docs/08](08-delivery-work-packages.md) lets an item start integration only after its start dependencies pass acceptance. R.02's start dependency is A2.07, and A2.07's own acceptance asks for a complete fixed-proposal execution trace. The lead (A, Jingbo Chai) decided:

- The driver and its CI trace are the deliverable for A2.07's "complete fixed-proposal execution trace" item. R.02's formal evidence is the `end-to-end-no-llm` job output recorded by CI. The same driver serves both, so the trace is not counted as an R.02 product that A2.07 would then depend on.
- PR #78 (A2.07) was squash-merged into main on 22 October 2026 as `0758696681cc706fda14ba378b7baa8e8c6580b3`. The merge is not A2.07 acceptance.
- E.10 remains a finish dependency of R.02. Its coverage map, [docs/42](42-e10-coverage-map.md), is a static mapping prepared for reviewer C, not an acceptance. The acceptance state of R.01, F.02, F.03, F.05 and F.07 is not established by this document.

**One-time exception, 22 October 2026.** The lead approved a one-time exception: R.02 implementation started before A2.07's designated human review by C Yuwei Tao, because of the Stage 2 source deadline (1 November 2026, 23:59) and because no production code was changed. This is not A2.06, A2.07 or R.02 acceptance, Gate 1, personal review, a future merge approval or a Jira status change. The designated human review of A2.06, A2.07 and R.02 remains the acceptance prerequisite and is not claimed. The original 89 WBS rows, ownership, S/F dependencies and the frozen docs/08 table remain unchanged.

## Deferred

- **`demo.py serve` and the image default CMD:** not exercised. The default CMD starts the workers with the builtin catalogue; a server-produced controlled proposal would need a separately reviewed design and document revisions.
- **Docker beyond build and import probe:** CI builds the image and runs its import probe only. This run is not deployment proof; the clean Canvas-package rehearsal remains a separate submission check ([docs/28](28-stage2-submission-checklist.md)).
- **Fault injection of `UNKNOWN` and `REPLAYED` paths:** the driver has one same-key recovery per step, but the first run used only primary paths. Recovery, `REPLAYED`, `produce_return` `UNKNOWN` and the HTTP 503 re-post remain covered only by the existing Domain tests and the offline driver tests, not by a real end-to-end run.
- **Windows permissions:** the 0700 private directory and 0600 auth file were exercised on the Linux runner only; their effect on Windows is not verified.
- **Gate aggregation:** the job is an independent evidence job and is not in the `ci-gate` needs, which `tools/checks/run.py` requires to stay exactly three. Joining the gate needs a separate change to `run.py` and `tools/checks/test_run.py`.

## Re-running

In CI, the `end-to-end-no-llm` job of `.github/workflows/ci.yml` uses a fresh PostgreSQL 17 service, installs the locked development environment, runs `alembic upgrade head` and then `python -B tools/r02/driver.py --output "$RUNNER_TEMP/r02-run" --keep-api-log`. It always prints the receipt and uploads the output directory as an artifact.

Locally the driver needs PostgreSQL 17 at alembic head, a fresh database whose name matches `returnops_f02*`, `DATABASE_URL` as a `postgresql+psycopg` URL with a distinctive password, and the locked development environment (`httpx` is a development dependency):

```text
python -B -m alembic upgrade head
python -B tools/r02/driver.py --output <new directory> [--keep-api-log]
```

Use a new database for every run: the driver refuses existing case rows (unless `--allow-existing-data`) and always refuses its fixed identities if they already exist. A refused, failed or expired run is reported as such and is not re-run with replacement keys. See [tools/r02/README.md](../tools/r02/README.md) for options, outputs, privacy screening and the first troubleshooting step.

## Demo mode (live demo only, not evidence)

Added on 22 October 2026 (Sydney) for the Week 13 live demo. Without the new options the driver, its CI job and the receipt format above are unchanged, and the first actual result above is not affected. Production code is still unchanged: `apps/`, `packages/`, `contracts/`, migrations, the CI workflow and `tools/checks` are not edited. The operating steps, including how to open the case in B's frontend, are in the [driver README](../tools/r02/README.md#demo-mode-live-demo-only).

- `--identities DIR` reuses the `auth.json` and `sessions.json` written by `python -m returnops_api.demo provision --private-dir DIR` ([`demo_identities.py`](../tools/r02/demo_identities.py)). The files must have exactly demo.py's shapes and every token must verify with the file's key, issuer and audience; step 0 then checks that the principals and sessions are registered exactly as written. The driver provisions no principal itself, and the fixed `r02_*` identities are still refused.
- `--api-port N` starts the API child on the fixed loopback port N (refused if the port is in use); `--keep-api` writes the receipt, prints the URL and the case ID and keeps the child running until Ctrl+C, after a completed or a failed chain. The frontend's Vite proxy targets `127.0.0.1:8000`, so the README uses `--api-port 8000`.
- The clean-environment relaxation is explicit: case rows of other stores still need `--allow-existing-data`. Four checks are never relaxed: the chosen store has no case, no investigation service and no lifecycle authority, and no case has `PENDING` or `RUNNING` intake or investigation work. At least 420 s of the 899 s session window must remain at step 0.
- Why a dedicated store: `InvestigationPolicy.configure` binds the store to one catalogue's provider, dataset version and `dataset_sha256`, and every investigation claim pauses with `CONFIGURATION_CHANGED` when the processor's catalogue differs. The workers of `demo.py serve` always use the builtin catalogue, so binding a store that already has (or later gets) builtin-catalogue cases to the cups catalogue would pause them. A merged copy of the builtin catalogue plus the cups order is accepted by `SyntheticCatalogue` but has its own `dataset_sha256`, so it does not avoid the pause. The store therefore has to be new, and it keeps the cups catalogue and the inserted grants afterwards.
- The receipt records `demo_mode` (`enabled: true`, `evidence: false`, `keep_api`, `api_port`), the options and two or three extra limitations. Tokens, the signing key (file form, base64 and hex) and the identities directory are added to the redaction list, so the existing refusal and reduced-receipt behaviour covers them.
- Offline tests: `tests/founder/test_r02_demo_mode_offline.py` runs the real `demo.provision` writer with a fake registry and engine, then checks the loader, the clean-environment rules, the registry comparison, argument parsing, the fixed port, `hold()` with a fake process and the order receipt, hold, stop.

Limitations of demo mode: a demo-mode receipt is not R.02 or Gate 1 evidence and is not a deployment proof; `demo.py serve` and the image default CMD are still not exercised; the UI is read-only against the kept API because the current client refuses live decisions and analytics; the sessions, and therefore the frontend login, expire 899 s after `demo.py provision`. No PostgreSQL run and no browser session in demo mode had been executed when this section was written; only the offline tests ran.

AI-assisted implementation and metadata preparation; author shuxiachai.
