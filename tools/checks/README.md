# F.02 check entry points

These local and CI entry points reuse the contract/model checks and the F.02
API/PostgreSQL environment tests. Traceability: F.02; NFR-001/006/007; the
M-A/M-S model chains. No domain migration or business endpoint is certified.
The scripts install nothing, start no services, and perform no Git fetch,
commit, upload, Jira action or model edit.

## Prepare once, in a Python 3.12 virtual environment

Run from the repository root with Python 3.12, Git, Node.js 24 and npm available:

```powershell
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
npm ci --prefix tools/model-checks --ignore-scripts --no-audit --no-fund
```

The Python lock includes transitive runtime, test and build dependencies. The
editable installation uses those installed build tools without resolving more
dependencies. npm uses the separate committed model-tool lock. First installs
can need registry access; the `offline` command itself does not access a
provider, database or package registry.

## Run the checks

```powershell
python -B tools/checks/run.py offline
python -B tools/checks/run.py offline --baseline-ref main
python -B -m unittest discover -s tools/checks -p 'test_*.py' -v
python -B -m pytest tests/security -q -p no:cacheprovider
```

`offline` runs contract artifact unittest discovery, the static document/model
checker, both tools' regression tests, and the Mermaid grammar parser. It stops
at the first failing step and exits nonzero; later steps have not passed by
implication. Python subprocesses use the same interpreter as the runner. The
runner derives the repository root from its own location.

The separate `tests/security` command validates the isolated [F.03 component](../../docs/18-f03-security-component.md) with synthetic registries/resources and in-memory test keys. It does not start HTTP, a database or providers. The local workflow includes this command as a separate step; historical CI runs predate that addition.

WBS ID/Owner/Reviewer/S/F are compared to `HEAD` by default or the existing local
ref given by `--baseline-ref`. To check an archive or explicitly omit only that
comparison, use `offline --skip-baseline`; the underlying checker reports the
skip and still validates WBS structure. Neither mode fetches a missing ref.
See the [model checker limits](../model-checks/README.md): source correspondence
and parsing do not establish rendering quality, UML meaning or human review.

After starting the project's **disposable test PostgreSQL** and explicitly
setting `DATABASE_URL` to its `postgresql+psycopg://.../returnops_f02` connection
URL (CI uses database `returnops_f02_ci`):

```powershell
python -B tools/checks/run.py environment
```

This command changes the configured database by running this project's
`python -B -m alembic upgrade head`, then reports `alembic current` and runs
`python -B -m pytest tests/environment -q`, `tests/storage`, `tests/customer`
and `tests/investigation`, followed by `tests/founder`. The retained0001–0005
migrations are followed by `0006_founder_reads`:4 independent metadata tables,
41 including all earlier tables and `alembic_version`. The suite checks fresh/repeated migration and
upgrade with accepted data, PostgreSQL17 constraints, exact content, atomic
rollback, unknown commits, current authority, retention and lifecycle guards.
The investigation suite also starts and stops its own loopback uvicorn processes
on dynamic ports to verify actual TCP, two workers and durable restart. It does
not use or stop a pre-existing API server. See the
[investigation boundaries](../../docs/23-order-investigation.md) and
[Founder read boundaries](../../docs/24-founder-read-queries.md). The Founder suite
also verifies persisted cursors across independent TCP process restart. Use the local
environment setup in [F.02 readiness](../../docs/10-f02-environment-readiness.md).
The runner rejects a missing/wrong-driver target and database names other than
`returnops_f02` or `returnops_f02_` followed by lowercase ASCII letters, digits
or underscores; the complete database name must be at most 63 characters.
Credentials are not echoed. A user/host is required, and any raw `?` or `#`
character is rejected, including empty query/fragment delimiters, to match
the migration target guard. Percent-encode such characters in passwords.
Naming cannot
establish database ownership. It does not
start Docker, create a database, or fall back to SQLite or a mock database.

## GitHub Actions review candidate

[ci.yml](../../.github/workflows/ci.yml) defines two independent jobs on
`ubuntu-24.04`: offline artifacts/models and the API environment with a fresh
PostgreSQL 17 Bookworm service, pinned to the same verified image manifest as
[Compose](../../compose.yaml). The service's synthetic credentials are confined to that
CI job and injected through environment variables. There are no deploy steps,
external provider credentials, `pull_request_target`, or ignored failures.
The token has only `contents: read`; checkout does not retain credentials.
New runs cancel older runs for the same event ref or PR.

For a PR, checkout includes history and the WBS check compares the checked
merge result to that PR's base SHA. For a push, the workflow explicitly skips
the independent WBS baseline comparison while retaining structural checks;
an arbitrary branch push has no selected agreed baseline. This is not a
replacement for review of allocation changes.

Official release refs and action manifests were read on **2026-09-07**:

| Action release | Verified commit used in workflow |
| --- | --- |
| [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| [setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0) | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| [setup-node v7.0.0](https://github.com/actions/setup-node/releases/tag/v7.0.0) | `820762786026740c76f36085b0efc47a31fe5020` |

Actions are pinned to those commits. PostgreSQL is pinned to manifest digest
`sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`,
verified from the official image on 2026-09-07 for the shared local/CI setup.
Python `3.12`, Node `24` and the runner image select maintained platform lines;
capture their resolved versions with a real run when recording reproducibility
evidence. The complete execution environment is not an immutable image.

The workflow is part of the [PR #11 review candidate](https://github.com/shuxiachai/returnops-au/pull/11).
Use its exact commit and actual GitHub run for CI evidence. Local passes do not establish remote runner compatibility, CI status,
branch protection, B/C review, F.01 acceptance or F.02 completion. Contract
artifact tests do not validate live business authorization; the old domain
tests are deliberately outside these F.02 groups and remain separate legacy
evidence. Record the checked revision and any uncommitted changes with results.
