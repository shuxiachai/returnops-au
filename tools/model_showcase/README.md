# A1.06 Coordinator showcase CLI

`run_once.py` runs the advisory Coordinator showcase
([docs/44](../../docs/44-coordinator-showcase.md)) once for one synthetic case
and writes a local evidence file. Requirements FR-002 and NFR-003/007/008/009;
work package A1.06 (extraction half) in
[docs/08](../../docs/08-delivery-work-packages.md).

This directory is private tooling. It is not packaged, it is never imported by
`apps/` or `packages/`, and it does not touch the R.02 driver or its receipt.

## What it does

- Reads the case's current statements in one read-only unit of work and closes
  it, calls the configured model with no database connection held (one total
  deadline, retries only for transport, timeout, HTTP 429 and HTTP 5xx after
  1 s and 3 s), then re-reads the case to confirm the input digest is unchanged.
- Uses its own in-process store. Nothing is written to the database, and a
  running API does not see this result: the Founder view shows facts only from
  the API's own worker.
- Writes `--evidence` (a new `.json` file): profile, case ID, input digest,
  provider ID, model ID, dialect, prompt version, deadline, outcome, failure
  code, attempts, input/output tokens, latency, statement count, redaction
  counts and, when accepted, the four fact enums with the line-item count and
  summary length. It never contains statement text, the summary text, the base
  URL or the key.

## Running

Configuration comes only from the environment; no argument accepts a key.

```text
DATABASE_URL                       postgresql+psycopg URL of the demo database
RETURNOPS_MODEL_BASE_URL           https base URL, e.g. ending in /v1
RETURNOPS_MODEL_API_KEY            the key (keep it out of files and history)
RETURNOPS_MODEL_ID                 model name, at most 120 characters
RETURNOPS_MODEL_PROVIDER_ID        contract Id naming the provider record
RETURNOPS_MODEL_DEADLINE_SECONDS   optional, 1-50, default 20
RETURNOPS_MODEL_DIALECT            optional, only chat-completions
RETURNOPS_MODEL_PROXY_URL          optional explicit http(s)://host:port proxy
RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP optional 0/1; 1 allows plain http to a private IPv4
                                   address with a port (the course proxy behind the VPN)
```

```text
python tools/model_showcase/run_once.py --case-id case_... --evidence /private/dir/showcase-1.json
```

The installed packages (or `PYTHONPATH=apps/api;packages`) must be importable.
The running API remembers a non-transient failure (any acceptance-chain code,
`HTTP_4XX`, `REDIRECT`, `MALFORMED`, `NO_USAGE`, `TOO_LARGE`) for that input
digest until it restarts, and does not send the same input again. To retry, run
this CLI, which has its own store, or restart the API.

Exit code 0 means `RECORDED`; 2 means another outcome (`REJECTED`, `FAILED`,
`STALE`, `STOPPED` or `NOT_ELIGIBLE`); 1 means configuration or database failure,
with a fixed message only.

AI-assisted implementation and metadata preparation; author shuxiachai.
