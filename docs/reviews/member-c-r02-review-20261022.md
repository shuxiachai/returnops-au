# C R.02 technical review and C2 handoff — 22 October 2026

Prepared with Codex assistance for C / Yuwei Tao. This is a technical review
packet, **not** C's personal review signature, A/B confirmation, a Gate 1
decision or course completion. A owns R.02/E.10 and the reviewed tooling; C is
the designated reviewer. No A/B implementation was changed.

## 1. Exact scope and evidence

- Reviewed main: `4aec7c0de6536075f6691567a3f609b8f3093279` (PR #93).
- Scope: `tools/r02/`, its two offline test files, `docs/41`, `docs/42` and the
  R.02 workflow artifact path. C2 contract/handoff tests were also rerun.
- Executed local checkout: PR #17 `b6dcc7552c2e52ca4dafd9d4b9400ad860db9365`;
  `apps/`, `packages/`, `tools/`, `tests/`, `.github/` and `contracts/` are
  unchanged from the reviewed main. The review-publication branch starts at
  that main and changes only C-owned documentation/reproduction material.
- Independent review perspectives: intent/regression, security/privacy,
  reliability and contracts/coverage. Findings below were checked by the main
  reviewer; parallel tool output is not a human sign-off.

Local command with the existing locked Python environment:

```sh
env -u TMPDIR PYTHONPATH=apps/api:packages PYTHONDONTWRITEBYTECODE=1 \
  python -B -m pytest tests/founder/test_r02_driver_offline.py \
  tests/founder/test_r02_demo_mode_offline.py \
  tests/contracts/test_c2_risk_preparation.py \
  tests/contracts/test_c_handoff_rehearsal.py -q -p no:cacheprovider
```

Result: **100 passed, 82 subtests passed in 2.87s**. `TMPDIR` was unset only for
this command's child environment to avoid the inherited macOS fixture path;
no machine setting changed. Tests use synthetic local fakes, not a database,
user credentials or model calls. Counts overlap earlier suites; do not add them
to 371 contract tests as independent new scenarios.

### Independently downloaded CI receipt

[Run 39724718286, R.02 job 119645897403](https://github.com/shuxiachai/returnops-au/actions/runs/39724718286/job/119645897403)
finished successfully at `2026-10-22T04:54:19Z`:

- PR head: `b6dcc7552c2e52ca4dafd9d4b9400ad860db9365`.
- Actual CI merge checkout in receipt: `a6c825faf7ae4914da933ef8b699a916dc97b656`.
- Artifact ID `12402194418`, name `r02-end-to-end-39724718286-1`, 5936 bytes;
  expiry listed as `2026-11-05T04:54:16Z`. C retains a separate local copy.
- `run-receipt.json` SHA256:
  `83c816d04c4fb3783baca12399a4176b5a7b2d3ea56989c22ebb3405a6a3f9a3`.
- `PASSED`, **32/32 checks true**, 36 step records, 11 primary paths, no recovery
  path used; private-directory removal recorded true. Default fresh-data mode,
  not `demo_mode` and not a locally executed PG reproduction.
- PostgreSQL 17.11 / schema `0014_notification_delivery` / CPython 3.12.15.
- Final case `COMPLETED` version 13; one approval, one decision, seven operation
  and three notification history rows, 28 audit events. The preview-to-artifact
  interval was 27.17 seconds against the 300-second preview limit.

Each digest was recomputed from the reviewed local source using the
`source_trees()` file-selection/canonical line algorithm, without importing or
running the services; all three exactly match the receipt:

| Tree | Files | SHA256 |
|---|---:|---|
| `returnops_api` | 31 | `3d868feb76fdf014b6aa21a35ed059456176c8b5c08b78484209b0846b5d628e` |
| `returnops_domain` | 122 | `2d7d1fffd445281399fa3c4f0d40dc0d3bdf6d60f006018fa1b3218e85e24a71` |
| `tools_r02` | 6 | `1126a074737e58589ef68ec0026fb6e0a021065c53308588d5df395b215d6ab3` |

This validates receipt/source correspondence, not all workflow jobs, the Python
dependency environment as a whole, browser integration or formal acceptance.
The scripted Founder-token action proves the tested authorization path; it is
not a live human approval click or the designated reviewer's signature.

## 2. Findings for A

### R02-C-01 — P2: cancellation leaves a nonterminal final receipt

At the reviewed source, `tools/r02/driver.py:875,883–886` catches `Exception`,
not `KeyboardInterrupt`. Interrupting a business step propagates cancellation
and still runs `finish()`, but the published receipt remains `result=RUNNING`
with no stop reason. It is no longer running and does not satisfy the documented
terminal PASSED/FAILED/REFUSED interpretation. Normal Ctrl+C during the later
demo `hold()` is handled separately and is not the reported case.

**Reproduction:** the linked in-memory probe substitutes the API/client and
raises `KeyboardInterrupt` from `customer_create`. API stop/private removal are
attempted; the captured receipt is RUNNING with no `stop`.

**Follow-up for A:** define a sanitized interrupted terminal result, preserve
cleanup/cancellation behavior and add a regression for interruption during the
chain (not only during hold). Do not turn cancellation into PASS.

### R02-C-02 — P2: cleanup and log publication are not failure-isolated

`driver.py:917–940` executes engine disposal, log reading/screening/writing,
private-directory removal and receipt publication sequentially. An exception
in disposal or log I/O skips the later cleanup/publication. The in-memory probe
raises from `engine.dispose`; private removal and publication are never called.

The privacy consequence is reinforced by `driver.py:860`: `--keep-api-log`
writes raw API stdout/stderr directly into the output/artifact directory
(`api_child.py:156–158`). It is screened only in `finish()`, while
`.github/workflows/ci.yml:194–202` uploads that directory with `always()`.
An interruption/kill or screening/cleanup exception can therefore leave an
unscreened log eligible for upload. **No actual credential leak was observed**;
this finding concerns the failure-path guarantee, not the successful receipt.

**Follow-up for A:** capture raw logs only in the private directory, publish a
screened/withheld copy after child exit, and attempt cleanup independently of
dispose/log errors. Regress disposal failure, log read/write/screen failure,
and interruption: no raw log in the artifact directory; cleanup still attempted;
safe failure evidence where writable. This requires A-owned tooling changes,
not a public schema change. C has not applied them.

### Reproduce the two control-flow findings without services

With locked dependencies, at the repository root:

```sh
python -B docs/reviews/member-c-r02-failure-probe-20261022.py .
```

The probe uses in-memory replacements and writes no files. Its assertions
confirm the **current defects**, not a fixed regression. It should fail or be
superseded after A fixes the source; do not add it as a permanent expected-bug
CI test. No user credential files, database, subprocess or provider is used.

## 3. What is supported, and what remains unverified

The private no-LLM successful path has reproducible technical evidence and
consistent code-tree provenance. Mock providers, same-key recovery boundaries,
no automatic approval authority for C2, and demo `evidence:false` are explicit.
The E.10 map correctly distinguishes HTTP snapshots from provider ledgers and
documents that DH04 may return 503 rather than always 202. No additional
high-confidence contract drift was found in the bounded reading.

Keep the already disclosed gaps visible: real HTTP client-read timeout coverage;
fault/recovery paths in the complete R.02 chain; demo-mode PG/browser validation;
default CMD/deployment/clean submission reproduction. The positive CI run did
not exercise recovery and is not proof of all parameterized E.10 behavior.
This review does not exhaustively re-run E.10 or inspect all predecessor evidence.

## 4. Remaining human/owner dispositions — not prefilled

Additional live read: [A's PR #94](https://github.com/shuxiachai/returnops-au/pull/94)
at `93ff6603c32b9673a7e4f0e05fe9177fc3a8e2d5` is a Draft advisory-only,
default-off Coordinator showcase, not an independent Risk implementation. Its
body says no live call has occurred and B's `facts` card is still separate.
KAN-39's afternoon comment permits this limited showcase while deferring full
three-role orchestration, real Risk and formal evaluation. That candidate is
not in main `4aec7c0` and its implementation is **not reviewed by this packet**.
It does not turn the R.02 fixed PASS result into AI evidence or waive course
requirements. No key was read, configured or sent and no live call was made.

- [ ] A acknowledges/disposes R02-C-01/C-02 against an exact fix SHA with local
  tests and required final CI. No unrelated A/B code is requested.
- [ ] C personally reads/reproduces the relevant behavior and records an actual
  technical disposition; AI preparation is not a substitute signature.
- [ ] Verify R.02's original A2.07 start and R.01/F.02/F.03/F.05/F.07/E.10 finish
  conditions. A's one-time permission to develop R.02 before the designated
  A2.07 review did not accept A2.07 or Gate 1.
- [ ] A reviews C2.04/C2.05's exact handoff and identifies production consumer
  routing/post-await owner. The [C2 README](../../experiments/c2_risk_candidate/README.md)
  and [Issue #66 draft](https://github.com/shuxiachai/returnops-au/issues/66#issuecomment-6333101141)
  separate component tests from actual route integration.
- [ ] A clarifies the [KAN-24 deferral note](https://lucastaooo.atlassian.net/browse/KAN-24?focusedCommentId=10141):
  do Gate 2, Gold and selected C3 remain intended course deliverables before the
  deadline, or is there a specific tutor-approved scope disposition? Please link
  the authoritative response if one exists. Team scheduling alone is no waiver;
  the nine features and 89 WBS rows are unchanged.
- [ ] Approved exact corpus/pin, model/adapter/data flow, real R.03 pilot, private
  Gold/independent human timing and C3 runtime evidence remain separate. No live
  call, private labels, measured model quality, personal explanation, booking,
  Jira Done or main merge is claimed by this packet.

## 5. C publication checks

The C-only review checkout passed the repository's six-step offline entry point
against baseline `4aec7c0`: 371 contract tests, six static groups (including the
89-row WBS baseline), 12 model-checker regressions, 32 runner regressions,
14 Mermaid blocks, and 64 synthetic-order tests. The focused 100-test/
82-subtest command was repeated there and passed in 1.02 seconds; both
failure-probe findings reproduced. These are overlapping local checks, not a
new remote CI pass or new PostgreSQL evidence. `git diff --check` passed.

Publication is to a C review branch and the existing discussion threads only;
PR #17/#61 heads and in-progress checks are left intact. No workflow is disabled
or skipped. A later PR/merge must still receive its own required exact-source
checks and review. Do not infer merge approval from this branch publication.

## 6. Local proof follow-up — 22 October 2026

Tracking KAN-23 / KAN-41. Codex-assisted technical verification, not C's human
review signature. This closes selected evidence-reading/reproduction gaps,
not the original E.10/R.02 acceptance dependencies. No A-owned implementation,
test, timeout, database target whitelist, workflow or public contract changed.

### Exact source, isolation and current CI

Executed a fresh local Git clone, detached and clean at PR #61 head
`be21f39bc502100ddd96c129bc9116b6fdcfceba`. The C publication branch remains a
separate older-base documentation branch; the tests below identify the source
actually run, not its publication head. Runtime tree IDs at the executed head
and checked main `f6de49d6252527fe875f1658b3954e05705099f1` are identical:

| Subtree | Git tree ID |
|---|---|
| `packages` | `8b97d11d2c108be95a2ae27b6d7f19285e2dab51` |
| `tests` | `f41b521a69683a733a4ce5480371a8bc57b6ebc3` |
| `tools` | `5df6039a6e993a38bc79c8c0d755a7a40034f1dd` |
| `.github` | `2a275981dc158c47cc364da6200bfbbe5616da92` |

At 12:54 UTC, [PR #61 run 39770369525](https://github.com/shuxiachai/returnops-au/actions/runs/39770369525)
is completed/failure: 11 successful jobs; Founder revision failed; the final
gate failed because not all eight environment parts succeeded. The gate is
the consequence, not a second independently diagnosed defect. Main's
[Founder revision job 119808171760](https://github.com/shuxiachai/returnops-au/actions/runs/39773813972/job/119808171760)
passed 513 tests, including both R04 parameters, on the same relevant source.
Neither that job nor local passes repair PR #61's failed check or prove a fix.

Local PostgreSQL used the already-cached pinned image
`postgres@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`
(17.11), new task-owned containers/databases and tmpfs storage. No existing
database or volume was reused. Linux test image
`returnops-c-offline-check:20261018` used CPython 3.12.14, pytest 9.1.1,
SQLAlchemy 2.0.52 and psycopg 3.3.5; this is not claimed identical to CI's
whole environment. Source was mounted read-only; test installation fixtures
build the local source offline into their own temporary target, without
dependency downloads or machine installation. Networks were internal/none,
with no provider access. Only synthetic fixture identities were generated.

### R04: five bounded repetitions, failure not reproduced

Ran the existing node without edits, five times, each with its same-key and
different-key parameter:

```sh
python -B -m pytest \
  tests/lifecycle/test_founder_reject_postgresql.py::test_R04_independent_process_competition \
  -q -p no:cacheprovider
```

Results: **2 passed** in each of 7.62, 7.64, 7.70, 7.96 and 7.72 seconds;
10 successful parameter executions. Separate evidence destinations retain
each pair's original JSON outputs/snapshots and logs. No local lock timeout
was seen. No load injection, assertion relaxation or timeout change was used.
These bounded isolated runs do not estimate a flake rate or replicate CI load.

The failed CI reports a 5-second advisory-lock timeout and fails the
same-key all-ACCEPTED assertion. `CustomerUnitOfWork.__enter__` sets that
timeout; failure before assigning `uow` can produce a safe denial through the
reject error path. A database-global fence plus scheduling/load is a plausible
explanation, **not a confirmed cause**: the failed job does not retain both
caller outputs or identify the holder and duration. Preserve the strict
same-key receipt expectation; ask A for a bounded diagnostic of the exact
holder/returned outcomes rather than accepting DENIED as success or blindly
increasing timeouts. PR #61's pending head was left unchanged.

R04 also has two evidence limits already disclosed in docs/42: its file-start
barrier does not observe actual PostgreSQL waiters, and its function-name
profiler does not cover current `CoreReturnMock.perform`, `CoreLabelMock.perform`
or `CoreMockNotification.deliver`. Zero counters alone therefore do not prove
zero provider calls. This confirms a test-evidence limit, **not observed duplicate
effects or a new proven business defect**. A can strengthen actual-entry/ledger
observation separately without weakening receipt/state assertions.

### E.10 follow-through: two specific reading gaps resolved

| Existing tests at executed SHA | Verified evidence | New local result |
|---|---|---|
| EP_G4_G8_G9, both parameters | Outcomes PREPARED/REPLAYED or PREPARED/DENIED; observed PG waiters; exact full-table deltas; a third installed process replays the durable identity without changing the snapshot | 2 passed |
| LE_G6_G11, four parameters | `launch`/`completed` use separate installed processes and parent/child DB identity; observed PG waiters; actual `CoreLabelMock.perform` dispatch/query counters; exact ledger/history/audit deltas | 4 passed |
| LE_G8_G11, absent/confirmed | New installed-process observation is read-only and source-bound | 2 passed |

Commands selected the existing files
`test_execution_preparation_process_postgresql.py` and
`test_label_execution_process_postgresql.py`. Initial combined run:
**2 passed / 6 failed** in 43.33 seconds because the generic isolated DB
address was outside the label probe's explicit allowed targets. This setup
failure is retained. After creating a new, still isolated database matching
the existing local label profile (`127.0.0.1:55433`, allowed database name and
observed OID), unchanged label tests passed **6/6 in 60.76 seconds**. No target
guard was bypassed. The eight successful evidence JSON files include the
observed waiters, real mock counters and installed-source hashes.

This narrows docs/42's "outcome assertions/helpers not read" items; it does not
change A's document or assert all E.10 scenarios, real carriers, R.02 recovery,
browser integration or clean final application deployment have passed.

### C delivery and remaining R.02 defects

On the clean executed checkout, host Python 3.12.7 with existing locked
dependencies passed 34 grounding, 36 corpus-admission and 46 C2 tests; stdlib
`-S` execution passed 147 evaluation tests (263 unittest methods in total).
The pilot ran, the synthetic evidence command produced 13 files, and the
synthetic human-time example ran. Evidence manifest SHA256:
`f55e658777b6cec3e7b48dc9492266c3d2a8ad651c327147f23fb3961e8cca63`.
The 12 indexed file hashes are independently checked in the local checkpoint.
A same-source archive without `.git` passed the 116 C1/C2 tests, pilot and
human-time example but correctly refused evidence generation with exit 1.
The [C README](../../experiments/evaluation_candidate/README.md#clean-checkout-versus-source-archive--22-october-2026)
now makes that packaging boundary explicit.

The focused R.02/C2 suite passed **100 tests / 82 subtests in 1.18s** on the
clean source; counts overlap the other suites. The existing in-memory failure
probe still reproduced **R02-C-01 and R02-C-02**. Their previous successful-path
tests do not establish these defects are fixed. No user key, live model, private
Gold or actual participant timing was used. Corpus admission, C2 production
routing, real Risk/C3 evidence, joint acceptance and C's personal explanation
remain separate outstanding items. A's owner disposition is still required.

## 7. Adoption and owner-fix follow-up — 23 October 2026

This section supersedes section 6's pending/failed PR status and R02-C-01
disposition, without deleting the original observations. It does not close
R02-C-02 or claim personal/team acceptance.

### Exact source and adoption chronology

1. A [approved PR #61](https://github.com/shuxiachai/returnops-au/pull/61#pullrequestreview-5622537263)
   at 00:27:16 UTC for exact head
   `be21f39bc502100ddd96c129bc9116b6fdcfceba`, limited to the four C documents.
2. A retried failed jobs on that same head. [Run 39770369525, attempt 2](https://github.com/shuxiachai/returnops-au/actions/runs/39770369525/attempts/2)
   finished successfully at 01:01:46 UTC: 13 effective jobs successful, including
   the replacement Founder revision job 120168070410 and final gate.
3. A merged #61 at 01:04:56 UTC with lead-written squash
   `29fd233a520bd37ee1c9aa2c61302b0417a25853`. No C rerun or main merge occurred.
4. Later, [PR #108](https://github.com/shuxiachai/returnops-au/pull/108) was adopted
   at 03:13:44 UTC as `b04d0a327ded021b030ad803662bc2c62719d9e7`.
   This later fix did **not** cause the earlier PR #61 rerun to pass.
   C's current reviewed runtime source is main
   `c4d08799adf555604a235e61ca325f50a2218618` (includes #107–#110).

The C review branch uses an ordinary merge of that main, preserving its README,
A/B implementation and fixed allocation. Branch publication is not an approval
of the new C review commit and does not bypass required checks for later adoption.

### R.02 dispositions after #108

| Finding | Current C observation | Remaining limit |
|---|---|---|
| R02-C-01 | FIX VERIFIED, BOUNDED: interruption yields FAILED/INTERRUPTED and attempts cleanup, both with keep-api false and true | Fake API/context only; not a real-process SIGINT or PostgreSQL/HTTP end-to-end cancellation acceptance |
| R02-C-02 | OPEN: a synthetic dispose exception still prevents later private cleanup and receipt publication; keep-api-log still selects the public output path before screening | No real secret was used or leaked; A must disposition the cleanup/log failure matrix and artifact-upload boundary |

New reproducible C-only diagnostic:

```sh
PYTHONPATH=apps/api:packages python -B \
  docs/reviews/member-c-r02-followup-probe-20261023.py .
```

It patches external effects in memory, uses dummy paths, prints no credentials
and performs no database, process or file-write operation. **Exit 1 is expected
while R02-C-02 remains open**, not a claim that the fixed interrupt path failed.
The original 22 October failure probe is retained as historical evidence; use
the new probe for the current disposition.

The owner fix should ensure cleanup stages are independently attempted, private
logs stay outside publishable artifacts until validated, and a safe terminal
receipt survives cleanup/log/read/write failures. Test these paths rather than
silently treating them as successful acceptance. C has not changed A's driver.

### R04: improved evidence, not a proven flake cure

#108 records each child attempt's safe status/code/audit and elapsed duration,
and permits one bounded same-key retry only for DENIED / INTERNAL_ERROR /
NOT_RECORDED with no receipt. The test still requires both final same-key
results ACCEPTED, one durable claim/acceptance/outcome and zero observed effects.
It now measures eventual success within that bounded retry, not two guaranteed
first-attempt successes. The previously disclosed effect-observation limits
remain.

[Issue #103](https://github.com/shuxiachai/returnops-au/issues/103) / KAN-43 owns
the concurrency follow-up. A's lock-holder/load explanation is still a hypothesis
without both failed caller outcomes and holder timing. A useful remaining
diagnostic is to force the transient failure and cover NOT_RECORDED versus
RECORDED/UNKNOWN, proving retries stay safe and bounded; the ordinary happy-path
run does not establish that classification. This is a review request, not an
authorised change to A's acceptance conditions.

**New observed failure after #108:** main
`c4d08799adf555604a235e61ca325f50a2218618` completed
[run 39900838149](https://github.com/shuxiachai/returnops-au/actions/runs/39900838149)
with 11 successful jobs, failed
[Founder revision job 120242146957](https://github.com/shuxiachai/returnops-au/actions/runs/39900838149/job/120242146957)
and a dependent failed final gate (120263074076). At 04:59:06 UTC the same-key
R04 test failed line 188's all-ACCEPTED/identical-receipt assertion:
351 passed / 1 failed in 1503.52 seconds. PG logs again report a lock timeout.
The public traceback does not expose the two safe attempt records or holder
duration, so C cannot identify which retry classification or outcome occurred.
This disproves a blanket "the failure is solved" statement but does not by
itself diagnose a business duplication or prove the same root cause.
Do not rerun repeatedly or weaken the assertion; A should retain safe per-attempt
diagnostics even when the assertion fails and disposition the failing outcome.

### Local check receipt

On the main-equivalent runtime files, the focused R.02/C1/C2/handoff pytest
selection passed **137 tests / 136 subtests in 1.19 seconds**. The full offline
runner then passed **all six steps**: 371 contracts, six static groups,
12 model-checker regressions, 32 runner regressions, 14 Mermaid parses and
64 synthetic-provider tests. WBS ID/owner/reviewer/S/F matched origin/main.
Counts overlap; they are not independent new business scenarios.

The first offline attempt lacked Node on PATH; the second reached the provider
test but picked up the older editable package from the reused environment.
The final run explicitly selected the current checkout with
`PYTHONPATH=packages:apps/api` and the already installed Node path. Both earlier
failure records are retained; no package installation or source workaround was
used. The package/lock-identical Mermaid cache was linked temporarily only.

The additional PG17 reproduction **did not execute**. A fresh pinned PG17.11
container became ready, but the task-owned test container stayed Created with
Pid 0, zero StartedAt and no daemon Error. A no-bind/tmpfs control also did
not start. This is a local container-start blocker, not a failed/passed R04
test and not proven to be a permission or network problem. No settings or
permissions were changed. Both unstarted task containers and the temporary
PG container/tmpfs data were removed; no existing database, volume or older
backup was changed.

These are local offline and review results, not live Risk/C3, Gold, measured
human time, clean final application deployment or named personal/team acceptance.
AI-assisted C preparation and verification; no A/B implementation edits.

## 8. PR114 bounded review and receipt-publication finding — 23 October 2026

Primary delivery: KAN-41; this section is AI-assisted C technical review,
not C's personal signature or R.02/E.10 acceptance. It supersedes section 7's
current-state conclusions only at the exact sources identified below.

### Sources and owner response

- A merged [PR #112](https://github.com/shuxiachai/returnops-au/pull/112) into main
  `2a4d3ae258734ab91c90d9e27e3da14eccbde0c6` at 06:54:17 UTC. C's publication
  branch ordinary-merges that source; all main README lines and A/B runtime
  contents are preserved. No #114 implementation is included in this branch.
- [A's Issue #103 response](https://github.com/shuxiachai/returnops-au/issues/103#issuecomment-6359315096)
  explains the previously missed RECORDED-denial retry classification.
  #112 now retries DENIED / INTERNAL_ERROR with no receipt irrespective of
  denial-audit persistence, still with a bounded attempt count and unchanged
  final receipt/claim/effect assertions. This is A's code-path diagnosis;
  C did not reconstruct the two original failed cloud callers.
- [A's PR #93 response](https://github.com/shuxiachai/returnops-au/pull/93#issuecomment-6359315535)
  points to [PR #114](https://github.com/shuxiachai/returnops-au/pull/114)
  exact head `590b4229ca20cd6e6ad34f026fd32d6ae93e421b`.
  C inspected an isolated archive of that head, not a floating branch.
  The candidate moves raw API logs into the private directory and independently
  attempts dispose, screening, private removal and receipt publication.
- [A requested a PR for this six-file C review packet](https://github.com/shuxiachai/returnops-au/pull/61#issuecomment-6359315897).
  Publication still requires A's exact-new-head review and lead-written
  squash; #17/#61's adoption does not adopt this separate packet.

### Independent offline verification

On the isolated #114 source, with existing locked dependencies and explicit
source-local imports:

```sh
env -u DATABASE_URL -u TMPDIR PYTHONPATH=packages:apps/api \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -B -m pytest tests/founder/test_r02_driver_offline.py \
  tests/founder/test_r02_demo_mode_offline.py \
  tests/lifecycle/test_founder_reject_offline.py -q -p no:cacheprovider
```

**105 tests passed.** An initial command used the wrong directory for the
reject test and collected no tests (exit 4); the corrected command above is the
passing run. Both records are retained. No dependency install, database,
real child process, provider call, credential or private Gold input was used.

The original follow-up probe's interruption/disposal paths now show terminal
FAILED/INTERRUPTED, private raw-log targeting, and later cleanup/publication
attempts even when disposal raises. This narrows **R02-C-01** and the original
**R02-C-02** observations; it is not complete filesystem/permission/signal/PG
failure-matrix acceptance. A's forced-PG RECORDED/NOT_RECORDED tests and claimed
local results are distinct from C's offline execution.

### R02-C-03 — P2: an unwritable final receipt can still report PASSED

At exact #114 head, `tools/r02/driver.py:958–961` catches receipt-publication
exceptions and prints a fixed safe message but leaves the successful result
unchanged. `publish()` also sets `receipt_written=True` before attempting
the write. `main()` at lines 1051–1053 then prints PASSED and returns 0.

C reproduced this using the actual execute/main/finish/publish control flow,
a successful synthetic chain and a patched `write_receipt` raising OSError.
All API, client, directory and cleanup effects are replaced in memory. The
observation is successful process status despite failed receipt persistence,
not a real disk-full event, leaked secret or failed business operation.
The same probe against main-equivalent `2a4d3ae` propagates OSError and does
not claim PASSED/exit 0; the new false-success observation is specific to the
#114 candidate, not retrospectively assigned to the older source.
The safe stderr message and continued cleanup are improvements; they do not
make the missing receipt a successful evidence-producing run.

Use the updated C-only diagnostic against the exact candidate:

```sh
PYTHONPATH=packages:apps/api python -B \
  docs/reviews/member-c-r02-followup-probe-20261023.py /path/to/pr114-exact-source
```

The output names each finding separately. An open C03 makes the overall probe
exit nonzero even when C01 and the original C02 paths improved. Do not count
that diagnostic exit as a new failed PostgreSQL run or add the historical
expected-bug probe to normal CI.

**Requested owner disposition:** keep cleanup stages independent, but make an
unsuccessful final receipt write yield a sanitized non-success result/exit;
do not claim receipt-written success before durable publication. Add regressions
for the CLI exit/stdout/receipt-state combination, including the keep-api path,
with no exception payload/DSN leakage. C has not changed A's driver.

### C publication checks and remaining boundary

On C's main-equivalent runtime at `2a4d3ae`, the focused R.02/C2/handoff command
passed **101 tests / 82 subtests**. The full offline runner passed all six steps:
371 contracts, six static groups, 12 model-checker tests, 32 runner tests,
14 Mermaid parses and 64 synthetic-provider tests. Counts overlap earlier
checks and are not additional independent business scenarios. The inherited
WBS ID/owner/reviewer/S/F and A/B runtime remain unchanged.

#114's required PG/final checks must be read from its actual CI run
[39914418314](https://github.com/shuxiachai/returnops-au/actions/runs/39914418314);
the local 105-test result does not stand in for them. The new P2 still needs
A's disposition and an exact-fix recheck even if that run becomes green.
At the 07:21 UTC check, the PostgreSQL lifecycle_core job
[120284664998](https://github.com/shuxiachai/returnops-au/actions/runs/39914418314/job/120284664998)
was FAILURE while other PG jobs were still running. A first log request
mistakenly targeted notification job 120284664997 and returned HTTP 503 /
account egress limit. The later job-list check corrected that ID; no failing
lifecycle_core log was obtained. C therefore does not name a failing test or
attribute that failure to C03 or R04. No repeated download or CI rerun was made.
No workflow was disabled or manually rerun. C's own PR needs its separate
required checks and non-author review before adoption.

Still outstanding: original Gate 1 dependencies/acceptance, approved exact
corpus/runtime pin, real independent C2 and five-branch integration, pilot/Gold,
C3, C's own-words explanation/contribution confirmation and joint rehearsal.
This packet supplies review-to-fix evidence, not a completion percentage or
a tutor waiver for deferred work.
