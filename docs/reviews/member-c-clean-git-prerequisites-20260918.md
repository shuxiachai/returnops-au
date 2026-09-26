# C F.02 clean-Git prerequisite evidence — 2026-09-18

**Status: clean-Git and offline prerequisites passed; the PostgreSQL 17 / Docker Compose route is still incomplete.** This is Codex-assisted execution on C's Mac, not a personal signature, model interview, joint F.01/F.02 acceptance or Jira Done.

## Source and execution

- A fresh, authenticated Git clone was checked out detached at exact source [`3dd1ff637693a826990eee5712cfb239a3c3da7b`](https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b), the PR #11 contract correction. This was not a ZIP reconstructed as Git and is not a test of a floating `main`.
- The independent WBS Git baseline was [`9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf`](https://github.com/shuxiachai/returnops-au/commit/9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf).
- Initial and final `git status --porcelain=v1` were empty; connectivity verification and staged/unstaged diff checks exited 0. No tracked application, test, lock or documentation file was modified to obtain the results.
- Execution: **2026-09-18 23:29:38–23:33:53 Australia/Sydney (UTC+10)**; macOS 26.6.2 / arm64; Git 2.50.1; fresh CPython 3.12.14 venv with system packages disabled; Node 24.19.0 / npm 11.17.0.
- Read the pinned checkout's full agent instructions, F.02 readiness and independent reproduction procedure before execution. Existing PostgreSQL/Docker override variable names were checked and none were set; no values were disclosed.

## Actual checks

| Check | Actual result |
|---|---|
| Fresh venv, committed Python hash lock, editable install and `pip check` | All exit 0; no broken requirements |
| Actual Compose healthcheck proxy regression, without Docker/DB | **2 passed** |
| npm lock installation, scripts/audit/funding disabled | **195 packages added**, exit 0 |
| Contract artifact suite | **58 passed** |
| Static document/model groups | **6/6 passed**; 33 Markdown files / 349 local targets |
| Real Git-ref WBS comparison | **89** fixed-field rows unchanged from exact baseline; valid acyclic dependencies; **not skipped** |
| Model-checker / unified-runner regressions | **12 / 5 passed** |
| Mermaid grammar | **15 blocks parsed**, 0 failures |
| Full offline entry point | **All 5 steps passed**, exit 0 |
| Additional non-database environment subset | **28 passed, 4 database deselected, 2 warnings**; not full environment testing |
| Missing configuration negative check | Child exit **2**, before migration; checking wrapper exit 0 |

The full offline entry point was run with the existing Node runtime on the child process PATH:

```sh
.venv/bin/python -B tools/checks/run.py offline \
  --baseline-ref 9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf
```

The checks verified nine embedded SVG/source pairs, not new rendering or UML semantics. Runtime business guards, LLM quality, Gold evaluation and actual user comprehension are outside these results.

## Retry disclosure and warnings

Two npm installation attempts stalled while reading modules from the previous task's tool directory, before any package installation output. Both owned processes were stopped with SIGTERM (exit 143). The exact OS/file-read cause was not established. The same npm files were freshly extracted from the previously verified official Node 24.19.0 archive into a new local tool directory; that archive's SHA-256 was rechecked as `8294b7aa9b03997481c06babf1e8b270c859358f27da57a11509afe537ac381d`. With the existing bundled Node, the unmodified `npm ci` command then succeeded. No global cache, security setting, source or dependency lock was changed, and the old tools were preserved.

The two interrupted attempts are disclosed rather than counted as successful installs. Their empty output logs and a process sample remain local diagnostics. The successful install retained `whatwg-encoding` and `uuid` deprecation warnings; pytest retained the existing Starlette/httpx and AnyIO BlockingPortal warnings. A pip update advertisement was not acted upon.

## Evidence and outstanding work

Evidence archive: [member-c-clean-git-prerequisites-20260918.zip](member-c-clean-git-prerequisites-20260918.zip).

SHA-256: `36487886916fddc615c8ccd2ca4e075a9c15b330b7c690519c1903b1c4667c6c`.

The ZIP contains the execution explanation, 13 selected source/version/install/check/status logs and their SHA-256 manifest. All 13 log hashes and ZIP integrity passed verification. It excludes env files, databases, venvs, node_modules, browser state and the process sample. Credential-pattern scanning found no GitHub tokens, Bearer tokens or credential-bearing PostgreSQL URLs; the negative-check error contains only a literal example placeholder. Local runtime paths in the raw logs are provenance, not repository paths to copy on another machine.

**Not executed in this record:** Docker engine startup, Compose image build, new PG17 volume, database migration, four real database tests, or actual container healthy → outage → recovery HTTP checks. Continue the [F.02 independent reproduction procedure](f02-independent-reproduction.md) with a verified local Linux Docker endpoint and a new isolated project/volume. The earlier [native PG16 evidence](member-c-f02-reproduction-20260912.md) and GitHub CI remain separate and do not substitute for that route.

The completed clean-Git/offline prerequisites remove that specific earlier gap. They do not establish complete F.02 reproduction, required-check/failure-evidence policy, Lucas's personal explanation, A/C joint acceptance, final report/video submission or overall course completion.
