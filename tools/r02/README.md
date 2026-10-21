# R.02 private end-to-end driver

`driver.py` produces the no-LLM Gate 1 run evidence for work package R.02
([docs/08](../../docs/08-delivery-work-packages.md)): in a clean PostgreSQL 17
database one synthetic two-cups case goes Create Case -> Mock Order -> Fixed
Proposal and the controlled PASS receiver + risk stub -> Founder approval ->
mock Return and Label -> CORE_MOCK notification -> audit. Requirements
FR-009..FR-012 and NFR-001/002/003/004/006/007/008; models
[governed-execution-activity](../../docs/diagrams/member-a/governed-execution-activity.puml)
and [exact-scope-sequence](../../docs/diagrams/member-a/exact-scope-sequence.puml).

This directory is private tooling. It is not packaged (pyproject only builds
`returnops_api` and `returnops_domain`; the Dockerfile copies only those), it is
never imported by `apps/` or `packages/`, and it never imports `tests/` at run
time. `main.py`, `demo.py` and the installed packages are unchanged; the default
application still starts no fixed-proposal worker, registers no decision route
and creates no grant.

## Route C in one paragraph

The driver starts its own API child process (`api_child.py`, the
[tcp_support](../../tests/founder/tcp_support.py) pattern: ephemeral loopback
port, `/health/ready` poll, terminate then kill) composed with
`create_app(engine, auth_config, **api_child.COMPOSITION)`, where the constant
is `enable_processor=False, enable_fixed_proposal=False, enable_founder_decisions=True`.
The receipt records that same constant, and step 3 observes that the new case
stays `SUBMITTED` with `PENDING` intake work. The child receives only the
environment it needs (`api_child.CHILD_ENVIRONMENT` plus `PYTHON*`, `PG*` and
`LC_*` names).
The customer creates the case and the Founder decides and reads over HTTP. The
intake, investigation and fixed-proposal processors run inside the driver for
this one case (`FixedProposalProcessor(build=...).process(prepare(case))`, as in
[docs/33](../../docs/33-a201-pass-review.md)); the API process runs no worker,
so nothing else can claim the case. The remaining private steps call the
existing `compose_private_*` services. The driver only orchestrates: every
guard, transition and mock effect comes from the Domain services.

## Files

| File | Role |
|---|---|
| `driver.py` | Orchestration of steps 0-9 and `run-receipt.json`. |
| `api_child.py` | API child process and the private 0600 auth file. |
| `catalogue.py` | Deterministic cups order catalogue (fixed snapshot/order IDs and timestamps, so the bytes and `dataset_sha256` are identical on every run). |
| `scenario.py` | `build_positive` and `ControlledPassReviewer`, copied unchanged from `tests/lifecycle/pass_review_helpers.py`, plus the same one-page synthetic PDF. |
| `grants.py` | Every grant/permission row, one function per step, equal field-for-field to the `tests/lifecycle` provision helpers; constants come from the packages. |

Offline checks live in `tests/founder/test_r02_driver_offline.py` (not under
`tests/lifecycle`, whose file counts CI checks).

## Running

```text
alembic upgrade head            # the environment step; the driver never migrates
python tools/r02/driver.py --output <dir> [--keep-api-log] [--allow-existing-data]
```

`DATABASE_URL` must be a `postgresql+psycopg` URL whose database name matches
`returnops_f02*` (`returnops_api.settings.require_environment_database`). The
driver refuses (exit 2, receipt result `REFUSED`) when the URL is rejected, the
server is not PostgreSQL 17, `alembic_version` is not exactly the API's
expected revision, case rows already exist (unless `--allow-existing-data`), or
its fixed identities (`r02_synthetic_store`, `r02_customer_one`,
`r02_customer_two`, `r02_founder`) already exist. Use a fresh database for
every run. It needs the locked development environment (`httpx` is a dev
dependency). Exit codes: 0 `PASSED`, 1 `FAILED`, 2 `REFUSED`.

## Steps

| Step | What happens |
|---|---|
| 0 | Environment: PostgreSQL version, alembic head, Python version, source-tree digests, clean-database check. |
| 1 | Registry: three people, one store, 899 s sessions (demo.py fields); deterministic cups catalogue with read grant; `FixedProposalPolicy.grant(store, synthetic_demo=True, enabled=True)`. |
| 2 | API child on 127.0.0.1 with the composition above. |
| 3 | Customer HTTP: `POST /v1/evidence`, then `POST /v1/cases` with `pass_scenario.MESSAGE`, `RETURN` and `SYN-CUPS-PASS`; the case must still be `SUBMITTED` with one `PENDING` intake work (no API worker ran). |
| 4 | Intake and investigation `run_once()` (refused if another case has pending work), then the fixed proposal for this case; Founder GET shows `RISK_REVIEW`. |
| 5 | REVIEW grant, controlled PASS receiver + risk stub; PREVIEW and APPROVAL grants, `PreviewService.accept`; Founder GET reads `case_version`, `current_proposal` and `action_preview`. |
| 6 | Founder HTTP, negative tests first: customer bearer -> 403 with no write; wrong fingerprint under another key -> 409 `INVALID_STATE`, no business change, one `FOUNDER_APPROVE_DENIED` audit; then APPROVE with key K -> 202 and a same-key replay -> identical receipt. Snapshot: no effects, one PENDING EXECUTION work, no EXECUTION grant. |
| 7 | EXECUTION grant, admission check, preparation; return grants; CREATE_RETURN; return-source bridge; label grants; GENERATE_LABEL; artifact grants; label PDF; notification grants; `produce_return`; `send`. K is the `original_approval_key` throughout; the case version is re-read before each versioned step. |
| 8 | Founder GET of the case, DECISION/APPROVAL/OPERATION/NOTIFICATION history and the complete audit (every page). |
| 9 | `run-receipt.json`. |

Grants are inserted just before first use, in the order the `tests/lifecycle`
chains use them; inserting them all at once is untested and is not done.
A primary call is accepted only as `PREPARED`, `COMMITTED`, `ACCEPTED`, `READY`
or `SENT`. `UNKNOWN` gets exactly one same-key `recover_`/`reconcile_` call
(preview, review, proposal, preparation, return, bridge, label, artifact,
send), and only that recovery may also answer `REPLAYED`; the receipt's
`produced_by` names the path that produced each accepted result.
`produce_return` has no recovery method, so its `UNKNOWN` stops the run with a
read-only view of the notification control and the lifecycle
`notification_work_id`. An HTTP `APPROVE` that returns 503 `INTERNAL_ERROR` is
recorded as `UNKNOWN` and re-posted once with the same key and body, after a
preview-window check. `DENIED` stops the run. Nothing is ever retried with a
replacement key. An unexpected exception records only its type and its
`tools/r02` frames (file name, line, function), never a message or a value.

## Time budget

The action preview is valid for 300 s (`preview_profile.PROFILE`). Approval,
admission, preparation, return, bridge, label and artifact all check it, so the
driver runs from `PreviewService.accept` to `complete_label_artifact` without
waiting and stops with `PREVIEW_WINDOW_EXPIRED` instead of calling a step after
expiry. Sessions last 899 s; the whole chain must finish inside that window.
The receipt records the session window, the preview expiry, the artifact
completion time and both checks. An expired run is reported as failed and is
not re-run with new keys.

## Outputs and privacy

* `run-receipt.json`: environment fingerprint, each step's status, safe code,
  HTTP status, correlation ID, idempotency key and case version, the time
  budget, the "no real effect" checks (simulated zero-ceiling preview, mock
  return/label providers in history and ledgers, CORE_MOCK channel, no live
  model or tokens) and the limitations below. Before writing, the serialized
  receipt is refused if it contains `Bearer`, any session token, the signing
  key (base64 or hex), the raw `DATABASE_URL`, its password, or the output,
  private or home directory (raw or JSON-escaped); a reduced receipt with code
  `RECEIPT_REDACTION_FAILED` is written instead. The check is a plain substring
  test, so a database password that is an ordinary word of the receipt also
  trips it; use a distinctive password. Existing receipts are never
  overwritten.
* `cups-catalogue.json`: the synthetic catalogue document; no secret.
* `api-child.log` only with `--keep-api-log`: withheld if it contains
  `Bearer`, a token, the key, the database URL or its password; the output,
  private and home directories are replaced by `<output>`, `<private>` and
  `<home>`.

The signing key and tokens exist only in memory and in a 0600 `auth.json`
inside a 0700 temporary directory that is removed at the end of the run. Never
upload that directory as a CI artifact.

## If a step fails

If an HTTP step fails with 503 `INTERNAL_ERROR` on a slow runner, first check
the API child's production engine: `build_engine` sets a 2 s
`statement_timeout` (the driver's own engine uses 10 s, like the tests). The
driver does not change it.

## Limitations

* The API child is composed by the driver, not started by `demo.py serve`; the
  image default CMD (which starts the workers with the builtin catalogue) is
  not exercised.
* Docker evidence remains the existing image build and import probe; this run
  is not a deployment proof.
* The controlled PASS receiver + risk stub is the fixed risk result of Gate 1
  ([docs/33](../../docs/33-a201-pass-review.md)); it is not an independent risk
  assessment. [docs/35](../../docs/35-a201-preview-approval.md) forbids a
  default preview/review producer, and none is added.
* A `PASSED` receipt or a green CI job is not human acceptance; R.02 still
  needs its designated reviewer.
