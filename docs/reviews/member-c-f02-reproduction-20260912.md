# C F.02 reproduction evidence — 2026-09-12

Status: **native environment and static checks reproduced; the required clean-Git / PostgreSQL 17 / Docker Compose route remains incomplete.** This is a Codex-assisted machine execution on C's Mac, not a signature that Lucas Tao personally ran, explained or accepted the work. No F.01/F.02 acceptance, Jira Done, business implementation, merge or course submission is implied.

## 1. Version and provenance

- WBS: F.02, Owner A / Reviewer C; F.01 remains its finish dependency. F.02's actual Jira delivery key is still unverified; do not substitute KAN-32 or KAN-14.
- Review: [PR #11](https://github.com/shuxiachai/returnops-au/pull/11), exact source `64582a3007fea0fa3d1b1c3c212168b96af6b607` (F.01 rc.5 / MA-0.3 / CS-0.2 / AD-0.2 / PD-0.2).
- Source was obtained as the authenticated GitHub ZIP, not a Git clone. Its ZIP comment equals that exact SHA and its archive integrity test passed. Archive SHA-256: `8eb49ccc0bae03171b23342e1f7ff3d03626dc52e17735db078b3f77f49bbe14`.
- All **52/52** files in the [publication manifest](rc5-publication-artifacts-20260907.json) matched the manifest SHA-256 values using the archive's raw bytes (the normalized Git-blob contents). No normalization was needed on this archive. This checks listed content integrity, not independently authenticated Git history.
- The source was extracted again into a separate `reproduction/returnops-au-fix-10-kan-32-contract-review` directory before tests. C's concurrently prepared models/reviews were not present there. Upstream scripts, tests, locks and application source were not edited to get these results.
- Since `.git` is absent, `git rev-parse HEAD`, clean Git status and the Git-ref baseline check were **not performed**. The supported archive flag `--skip-baseline` explicitly disclosed this.
- A separate comparison used the repository's `allocation_rows` parser against the actual downloaded main snapshot `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`: all **89** WBS ID / Owner / Reviewer / S / F tuples were equal, and the current dependency graph was valid/acyclic. This is direct snapshot comparison, not a claim that the Git-ref CI comparison ran locally.

## 2. Machine and dependency preparation

Execution window: **2026-09-12 17:30–17:33 Australia/Sydney (UTC+10)**.

| Item | Actual observation |
|---|---|
| OS | macOS 26.6.2, build 25G83, arm64 |
| Python | CPython 3.12.7, Anaconda-packaged build; fresh `venv`, `include-system-site-packages=false` |
| Python dependencies | `requirements-dev.lock` installed with `--require-hashes`; editable package installed `--no-deps --no-build-isolation`; `pip check`: no broken requirements |
| Node / npm | Official task-local Node 24.19.0 / npm 11.17.0; not a global installation |
| Node distribution integrity | Official `node-v24.19.0-darwin-arm64.tar.gz` SHA-256 `8294b7aa9b03997481c06babf1e8b270c859358f27da57a11509afe537ac381d`, matched official versioned SHASUMS256 |
| Model dependencies | `npm ci --prefix tools/model-checks --ignore-scripts --no-audit --no-fund`: 195 packages, exit 0 |
| Native PostgreSQL | Existing `/Library/PostgreSQL/16/bin`, PostgreSQL **16.2**; no software installation or existing-cluster reuse |
| Docker / Compose | No Docker executable was available in PATH and no Docker Desktop app at the standard location; no context, endpoint, engine, Compose build, volume or PG17 checks performed |
| Existing overrides | Checked names only; none of `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DB_PORT`, `API_PORT`, `DATABASE_URL`, `DOCKER_HOST`, `DOCKER_CONTEXT` were present; no values printed or user settings changed |

The Python lock was first installed into the new venv. The retained `locked-install.log` records the subsequent same-lock, already-installed verification; the original first-install output is in the task execution record. There was no global package update. npm reported upstream deprecations for `whatwg-encoding@3.1.1` and `uuid@9.0.1`; its update advertisement was not acted upon.

## 3. Exact source: static and negative checks

`PY` below denotes that fresh venv's `bin/python`; commands ran at the separate pristine archive root, with task-local Node on the child process PATH. `PYTHONDONTWRITEBYTECODE=1` was set. The environment tests used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `PYTEST_ADDOPTS=-p no:cacheprovider` to avoid unrelated globally installed pytest plugins/cache writes.

```sh
PY -B tools/checks/run.py offline --skip-baseline
PY -B -m pytest tests/environment -m "not database" -q
PY -B tools/checks/run.py environment
```

The last command was intentionally executed with `DATABASE_URL` absent. Its expected exit was 2, before any migration; the reviewer wrapper checked that exact exit instead of ignoring a failure.

| Check | Actual result |
|---|---|
| Contract artifacts | **56 tests passed**, exit 0 |
| Static document/model groups | **6/6 passed**; 31 Markdown files / 343 existing local link targets |
| Requirement/use-case coverage | FR=12, NFR=9, BR=12, UC=6 |
| WBS | 89 rows, valid acyclic references; Git comparison explicitly skipped; separate main-snapshot comparison described above |
| SVG/source correspondence | 9 existing PUML/SVG pairs matched embedded source; no rendering or visual inspection by this check |
| A model references | 21 scenarios / 41 activity action IDs / 7 operation states matching the schema |
| Shared composite references | 3 views / 57 port appearances / 29 registered connectors / 13 scenarios / five named boundary adjacencies |
| Model-tool regressions | **12 tests passed** |
| Unified-runner regressions | **5 tests passed** |
| Mermaid grammar | **15 blocks parsed**, 0 failures |
| Unified offline runner | All **5 steps** passed, exit 0 |
| Non-database environment subset | **28 passed, 4 deselected, 2 warnings**, exit 0; not a full environment pass |
| Missing configuration | Child exit **2**, migration not started; not a deliberately failed remote Actions run |

These checks are artifact/tool checks. They neither implement the 15 public business operations nor prove runtime identity, authority, idempotency, material retention, citation completeness, LLM quality or model semantics. Passing existing tests does not override separate C contract-review findings.

## 4. Actual native PostgreSQL runs

### 4.1 Unmodified upstream native runner

```sh
PY -B tools/environment/native_check.py \
  --bin /Library/PostgreSQL/16/bin --db-port 15433 --api-port 18001
```

- The upstream runner verified available loopback ports and created a new cluster `tmp/f02-native-t6vgyl3y/data`, dedicated database `returnops_f02_native`, fresh generated credentials and a new API process.
- It ran the complete environment entry point: migration upgrade/current, then **32 passed, 2 warnings** including all **4 real database tests**, with no skips/deselections.
- Migration was `0001_environment`; the repeated-upgrade test performed two further upgrades and verified that only the environment version table existed. No business tables were created.
- Real TCP initial health: **live=200, ready=200**. After stopping only this new database: **live=200, ready=503**.
- The unmodified upstream native runner does not restart after the outage. This first run alone is not recovery evidence.
- The runner stopped its API and database. A separate `pg_ctl -D <exact-owned-data> status` returned `no server running`; no listeners remained on 15433/18001. Synthetic cluster data/logs were retained, not destroyed.

### 4.2 Additional C reviewer recovery check

The original native runner discards its generated password on exit. To avoid changing that cluster's authentication or recovering secrets, a separate, explicitly C-agent-authored local harness `reviewer-tools/native_recovery.py` created a **second fresh** cluster `tmp/f02-c-recovery-4t8x4f9_/data`, database `returnops_f02_c_recovery`, DB port **15434**, API port **18002**. Both ports were checked before creation. The harness is included with evidence and does not replace or modify the upstream script.

This second run independently executed the complete environment entry point (**32 passed, 2 warnings**) and queried `alembic_version` directly as `0001_environment` before actual HTTP checks:

| Time (Sydney, 2026-09-12) | Same owned API/cluster sequence | Result |
|---|---|---|
| 17:32:54.453 | Initial healthy state | live **200**, ready **200** |
| 17:32:54.585 | Only its database stopped | live **200**, ready **503** |
| 17:32:54.735 | Same database directory restarted; API process unchanged | live **200**, ready **200** |
| 17:32:55.032 | Reviewer cleanup | Own API and cluster stopped; local synthetic data retained |

HTTP requests used `ProxyHandler({})`. Credentials were generated per run, never printed, and never included in evidence. The same API process recovered its pooled database connectivity. This proves only the tested **native PG16 health infrastructure** recovery. It is not Docker/PG17/Compose, provider recovery, or an OperationAttempt runtime test. A separate final status check reported no server running and no listeners on 15434/18002.

### Warnings retained verbatim

Both full runs and the non-DB subset reported these two upstream deprecations:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
```

No dependency or test was modified to suppress them.

## 5. Reviewable evidence bundle

Delivery attachment: [member-c-f02-evidence-20260912.zip](member-c-f02-evidence-20260912.zip) (not the source ZIP). It contains **19 selected log files, three local reviewer scripts, and a per-file SHA-256 manifest**. It excludes `.env`, password files, databases, `node_modules`, venvs, tokens and browser state. Log scanning rejected credential-bearing PostgreSQL URLs / GitHub-token / Bearer-token patterns; both native runners also checked their generated secret was absent. The ZIP integrity test passed.

Bundle SHA-256: `a9fa4f736764f092603f53d135309e8186eb8a98f852bca1f95bfe115e2c1d61`.

| Evidence path inside ZIP | SHA-256 |
|---|---|
| `logs/source-integrity.log` | `95fa9bfd8947b3f129c3243683c2514d79d8201e63a935155bb43ad90ffe9838` |
| `logs/offline.log` | `28a3d5ebd9f94614139996adb3a18d2318785cf81819de5240b49d42cbc6ce38` |
| `native-upstream/commands.log` | `a9c1c544fd84a7ed721928cbbbd14f72a2cb3f86f8153243d01bc0ff29419890` |
| `native-recovery/recovery.log` | `99f6e70b05dc5eabc156940ff824fca662bf6baf630f5c96fb3b3b799a897d55` |
| `logs/missing-config.log` | `52fe6a31f3129e717b0d32c31031836d573ec1858ae64524c5badf579e53857d` |

The bundle is prepared locally alongside the C delivery directory; no assertion that another member can access it is made until publication/attachment access is verified. Its local scripts record this machine's directory layout; a future reviewer must adapt local paths without altering the immutable source under test.

## 6. Remaining acceptance gates

1. Obtain an actual authorized Git checkout of exact source `64582a3…` and record initial/final status and the Git-ref WBS comparison. Do not manufacture Git objects to make an archive look like that checkout.
2. On an available, verified local Linux Docker engine, perform the reproduction packet's pinned-context, new project/volume, **PostgreSQL 17 / Compose build + migration + full tests + real HTTP healthy/outage/recovery** route. Native PG16 evidence does not close this requirement.
3. Complete F.01's B/C review and acceptance separately; resolve the real F.02 Jira key and required-check/failure-evidence conditions with A. Successful local checks cannot establish branch protection or a failed remote run.
4. Lucas personally reviews the evidence, explains the checks and records his own conclusion; A reviews the reproduction record. Agent-assisted execution is not a member signature.

Recommended recorded state: **“Static/native reproduction passed; specified Docker/clean-Git route pending.”** Do not mark F.02 Done on the strength of this document.
