# C dependent review handoff — 15 October 2026

Tracking: [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) (C1),
[KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) (C2);
[KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25) is related evaluation
preparation, not formal evaluation completion.

## 19 October actual-main integration

This section supersedes current-status statements in the historical receipts
below. Their dependency hashes and results remain unchanged; the JSON summary
beside this file is still the historical composite, not this new run.

A adopted C1 #68 (`4dc60bd` -> `437b4eb`), evaluation preparation #70
(`e5b3e91` -> `d9813d6`), and then C2 #69 (`f2bf32d` ->
`5006da1ab0dcf046e34e5d16bb9407941322c574`). C2's exact-source
[approval](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5567289418)
and [successful normal checks](https://github.com/shuxiachai/returnops-au/actions/runs/39202282951)
are preparation-component evidence only. No corpus semantic admission or
trusted pin, real model, Gold, R.02/R.03 or personal acceptance follows.

Following [A's PR #79 review](https://github.com/shuxiachai/returnops-au/pull/79#pullrequestreview-5565657630),
C merged actual main `5006da1` into source `7addfbbb6284940806c49ffd3971e01b16739dbd`
in a fresh isolated checkout. No dependency overlays are required now. Every
main README line remains present; the diff from main is still limited to
README, these two C handoff receipts, and the C rehearsal test file. The local
HTTP transport, image-pair and capture/replay candidates are not imported.

### Test-only compatibility correction

The nine original handoff tests pass on a filesystem supporting `O_DIRECTORY`,
`O_NOFOLLOW` and `O_NONBLOCK`. An independent AI-assisted review also reproduced
their old unguarded failure when `O_DIRECTORY` is absent. They now use C1's
same capability boundary: capable hosts run all nine; unsupported hosts report
explicit skips rather than pretending admission succeeded. A separate test
still checks missing capabilities and no filesystem I/O. No production loader,
contract, caller authority or safety setting is changed. This review is not A's
non-author approval of the integrated head.

### Reproduce the integrated checks

Use the final exact PR #79 commit named in its thread, a clean checkout and the
existing locked Python 3.12 / Node 24 dependencies. These commands need no
Docker, PostgreSQL, credentials, network model calls or Gold labels:

```sh
export PYTHONPATH=apps/api:packages
python -B -m unittest discover -s tests/contracts -p 'test_c_handoff_rehearsal.py' -v
python -B tools/checks/run.py offline --baseline-ref 5006da1ab0dcf046e34e5d16bb9407941322c574
python -B -m pytest tests/security tests/storage/test_records.py -q -p no:cacheprovider
git diff --check
git status --porcelain
```

The offline runner includes all current contract tests, document/model links,
12 checker regressions, seven runner regressions, 14 Mermaid blocks and 64
synthetic-order tests. Security/records add 244/36 tests; focused tests overlap
the contract total. Final counts, exact source/tree and append-only log hashes
are recorded in the PR evidence reply and local backup after the clean-source
rerun. Native unsupported-host skips are not Windows runtime acceptance.

PR #79 stays Draft pending normal integrated-source checks and A's targeted
review. Normal CI is requested once by publication, not repeatedly dispatched;
required final checks are not skipped to save quota. Local DB/Docker remain
paused. No real provider/Risk, full application path, E.12, C3.03, human timing,
personal sign-off or Done is claimed.

## Latest 18 October follow-up — review corrections and Linux checks

A reviewed #68/#69 on 18 October and requested changes to #70's cost addition.
The latter is corrected at `bacca6a74aee967fa80c74004833fdac0334a155`: validated
decimal coefficients are summed as scaled integers, independent of ambient
precision/rounding/traps. Unknowns stay unknown and failed usage is retained.
Four regressions were added. Independent AI-assisted review additionally checked
600 deterministic Fraction comparisons; this is not A's re-review or acceptance.

#68 now incorporates main `17042b4164a0be878c7a0684cf532217ebeb77ee` at
`e15394a05d253d1f5bcdb61aac4559c2a133d604`. Its README conflict is reconciled,
preserving main's public-scope notice and C history. All non-README incoming A
files are inherited unchanged from main, not newly authored C changes. The
pending corpus/manifest bytes and loader are unchanged. A's no-new-P1/P2 static
review is not corpus admission; fuller retrieval context remains C work, followed
by genuine exact-byte review and a trusted integration pin.

Host checks used the existing locked Python 3.12.7 / Node 24 setup:

| Source / local receipt | Verified scope |
| --- | --- |
| #70 `bacca6a`; `e09-md9it7kp` | 267 contracts, including 139 evaluation tests; six static groups, 12 checker/seven tool tests, 14 Mermaid blocks, 64 synthetic-order, 244 security and 36 records tests. Receipt pins parent `db45f5f` plus the three changed file hashes matching `bacca6a`. |
| #68 `e15394a`; `c1-x9r0gstl` | 162 contracts and the same other host suites. The focused C1 run also passed 70 tests/108 subtests before the merge commit. |
| #79 parent `221adde` plus the 26 dependency files below; `composite-z123uc8p` | 339 contracts and the same other host suites. The new README/record update follows this run; final-document checks accompany publication. |

Source/overlay hashes were unchanged during each recorded run. Counts overlap;
none of these runs used a database, real LLM, formal Gold or real human timing.

The **same 26-file composite** additionally ran `pytest tests/contracts
tests/security tests/storage/test_records.py -q -p no:cacheprovider` on local
Linux aarch64 / Python 3.12.14: **619 passed, 1579 subtests passed**. Docker used
a read-only source/root filesystem, dropped capabilities, no new privileges,
UID 501 and `--network none`; only temporary test files were writable. The local
test image was derived from the existing C test image by installing Git during
build (the build downloaded packages; the tests had no network). Image ID:
`sha256:71669293a3ec1882ebc50ac418c05823616d366ed2ac4d30448760a2e16a550e`.
This is component evidence, not the official deployment image or locked PG17
Compose reproduction. Linux Node/Mermaid checks were not run.

A separate clean clone of exact `bacca6a` ran the two evaluation commands on
that Linux image with Python `-S` at 09:32:59–09:33:00 UTC. Both evidence runs
produced content ID
`cdedef5f787acc773dee267f1e1d79c7b8ac32d3807d21cad3b3822169c65508`
and manifest SHA-256
`2ad46558d7414993e3f7311cfdd0ed151086b04ab4eda7e37e5fb2e41f8cb789`.
All 13 file hashes, private output permissions and clean source identity were
checked. The invented timing example matched A `120/60`, B `150/60`, pooled
`135/75` median/IQR seconds. Docker Desktop presented source mounts as root-owned,
so this separate CLI check ran as container root with all capabilities dropped,
read-only source/root, a dedicated output mount and no network. The first
non-root CLI attempt stopped on source ownership/access; it is not counted as a
successful run. No host Git trust settings were changed. No production non-root
deployment, credential access, semantic performance or acceptance is inferred.

A's #69 review confirms the preparation interface constraints, not provider
configuration or live execution. #79 stays Draft and A/B scheduling has no
confirmed slot. The [C README](../../README.md#c-follow-up--2026-10-18) separates
independent work from approvals/integration and records the coarse 50–60%
remaining estimate. Older evidence and the 15 October JSON receipt stay historical.

## Current dependency reconstruction — 18 October

The latest reconstruction uses the same main `17042b4` and the following
**26 dependency files**. Use a clean disposable worktree, not a teammate's
checkout. Fetch the PR refs, verify the full commits exist, then restore only
these paths with `git restore --worktree --source <full SHA> -- <paths>`:

| PR / exact source | Paths (all required) |
| --- | --- |
| #68 `e15394a05d253d1f5bcdb61aac4559c2a133d604` | `experiments/c1_grounding_candidate/admission.py`; its `candidates/accc-20261012/README.md`, `admission-manifest.json`, `corpus.json`; `tests/contracts/test_c1_corpus_admission.py` (all five bytes unchanged from `af44d6e`) |
| #69 `cfda3a1d7b96e5cd973faff30739f11c57fe0850` | `experiments/c2_risk_candidate/README.md`, `__init__.py`, `reviewer.py`; `tests/contracts/test_c2_risk_preparation.py` |
| #70 `bacca6a74aee967fa80c74004833fdac0334a155` | `experiments/evaluation_candidate/README.md`, `__init__.py`, `scoring.py`, `runner.py`, `latency.py`, `quality.py`, `reproducibility.py`, `evidence.py`, `human_timing.py`, `data/human_timing_example.json`; `tests/contracts/test_evaluation_preparation.py`, `test_evaluation_runner.py`, `test_evaluation_latency.py`, `test_evaluation_quality.py`, `test_evaluation_reproducibility.py`, `test_evaluation_evidence.py`, `test_evaluation_human_timing.py` |

### Current isolated reconstruction

Start in a checkout of this handoff commit. The following preserves that checkout
and creates a separate directory. These commands restore candidates for testing;
they do not merge their branches or approve their content.

```sh
git fetch origin pull/68/head pull/69/head pull/70/head
git cat-file -e e15394a05d253d1f5bcdb61aac4559c2a133d604^{commit}
git cat-file -e cfda3a1d7b96e5cd973faff30739f11c57fe0850^{commit}
git cat-file -e bacca6a74aee967fa80c74004833fdac0334a155^{commit}
c_review_dir=$(mktemp -d "${TMPDIR:-/tmp}/returnops-c-review.XXXXXX")
git worktree add --detach "$c_review_dir/repo" HEAD
cd "$c_review_dir/repo"
git restore --worktree --source e15394a05d253d1f5bcdb61aac4559c2a133d604 -- \
  experiments/c1_grounding_candidate/admission.py \
  experiments/c1_grounding_candidate/candidates/accc-20261012/README.md \
  experiments/c1_grounding_candidate/candidates/accc-20261012/admission-manifest.json \
  experiments/c1_grounding_candidate/candidates/accc-20261012/corpus.json \
  tests/contracts/test_c1_corpus_admission.py
git restore --worktree --source cfda3a1d7b96e5cd973faff30739f11c57fe0850 -- \
  experiments/c2_risk_candidate/README.md \
  experiments/c2_risk_candidate/__init__.py \
  experiments/c2_risk_candidate/reviewer.py \
  tests/contracts/test_c2_risk_preparation.py
git restore --worktree --source bacca6a74aee967fa80c74004833fdac0334a155 -- \
  experiments/evaluation_candidate/README.md \
  experiments/evaluation_candidate/__init__.py \
  experiments/evaluation_candidate/scoring.py \
  experiments/evaluation_candidate/runner.py \
  experiments/evaluation_candidate/latency.py \
  experiments/evaluation_candidate/quality.py \
  experiments/evaluation_candidate/reproducibility.py \
  experiments/evaluation_candidate/evidence.py \
  experiments/evaluation_candidate/human_timing.py \
  experiments/evaluation_candidate/data/human_timing_example.json \
  tests/contracts/test_evaluation_preparation.py \
  tests/contracts/test_evaluation_runner.py \
  tests/contracts/test_evaluation_latency.py \
  tests/contracts/test_evaluation_quality.py \
  tests/contracts/test_evaluation_reproducibility.py \
  tests/contracts/test_evaluation_evidence.py \
  tests/contracts/test_evaluation_human_timing.py
python -B tools/checks/run.py offline --baseline-ref 17042b4164a0be878c7a0684cf532217ebeb77ee
python -B -m pytest tests/security -q -p no:cacheprovider
python -B -m pytest tests/storage/test_records.py -q -p no:cacheprovider
```

Use the locked Python/Node setup in [tools/checks](../../tools/checks/README.md).
If reusing an existing environment, ensure its imports resolve to this review
checkout (root, `apps/api`, `packages`), not an older editable installation.
Do not commit the dependency overlays as part of this handoff PR.

### Historical 17 October runnable-evidence/timing increment

#70 `db45f5f` adds the two commands documented in
[C's component README](https://github.com/shuxiachai/returnops-au/blob/db45f5f1228598e406d02c10953ed11a2f345cdf/experiments/evaluation_candidate/README.md).
The 13-file offline bundle executes both fixed toy adapters, retains their
actual structured results and binds rich quality evidence to the same input and
risk output. Judgments are fixed before invocation; failures cannot inherit
successful quality output. Synthetic latency remains separately labelled, not
observed execution time. Hashes and creation time are not a seal or acceptance.

The separate timing CLI validates explicitly imported local records, subtracts
the union of permitted waits and reports A/B/pooled median, Q1, Q3 and IQR with
coverage. Missing/invalid/failed/duplicate cases stay in the denominator; failed
partial time is not a completed sample. Only invented public records were used.
Real A/B actions, private records, answers, independent locks and Gold review
remain subject to the original E.01–E.08 sequence, not this tool's availability.

Independent AI-assisted review corrected an incomplete claim-inventory
declaration in a toy fixture; every material toy assertion now has a fixed
judgment entry, with unknown judgments retained. New regressions cover this,
annotation/output mismatch, retained success data after failure, exclusive
publication, byte hashes, invalid imports and timing overlap/order/math.

Individual #70 verification: **135 evaluation tests within 263 contract tests**,
including 20 evidence and 27 timing tests; six static groups, 12 checker/seven
tool regressions, 14 Mermaid blocks, 64 synthetic-order, 244 security and 36
records tests passed. Receipt `oct17-e09-6hqsnljg` records parent `4986274` plus
six file hashes during 09:11:17–09:11:32 UTC. After the README result paragraph,
the final unchanged-source rerun `oct17-e09-hcv00v91` passed all four commands;
its six delta hashes match `db45f5f`. No C1/C2 overlays were used in this run.

A separate clean local clone of exact `db45f5f` then ran both commands with
Python 3.12.7 **`-S`**, no site-packages or dependency overlays. At
09:13:05–09:13:06 UTC, two generated bundles had identical content ID
`41a38d41b51782cbb2db143bd9fef12da4aebb51bd783a531e2c0492210a948c`
and manifest SHA-256
`018a819ea7ccc0d44fbf522b933c8544fafdea7a1183e3675402d933164533e8`.
The check independently verified all file hashes, 13-file inventory, private
permissions, exact source hashes and clean checkout before/after. The public
timing example reproduced A median/IQR `120/60`, B `150/60`, pooled `135/75`
seconds; these are invented arithmetic fixtures, not measured human results.
This clean-clone proof covers these two commands only, not PG17 deployment,
live adapters, R.02/R.03, formal evaluation or A's acceptance.

The **26-file dependency reconstruction** also passed **335 contract tests**
(including the 135 evaluation, 29 Risk and nine handoff tests), six static
groups and the same remaining local suites. Receipt `oct17-composite-nmpuefvb`
records exact source/overlay hashes and unchanged files during that run. This
count paragraph was added afterwards; final-source verification accompanies the
PR update. #79 still requires the stated candidate overlays and remains Draft;
these results do not make it standalone or merge-ready.

### Earlier quality/pair increment — historical source and verification

#70 at `4986274` adds pure accounting over supplied, exact-output-bound semantic
judgments and a paired synthetic evidence consistency validator. No caller's
judgment, hash, matching manifest or declared model is treated as authenticated
review, historical freeze, actual execution or acceptance. Independent
AI-assisted review found that the first paired validator rejected a runner's
valid FAILED observation when its adapter error code was also retained. The
final implementation and actual-runner regression preserve both pieces of
evidence. This code review is not A's acceptance.

The individual #70 source passed **88 evaluation tests within 216 contract
tests**, six static groups, 12 checker/seven tool regressions, 14 Mermaid blocks,
64 synthetic-order, 244 security and 36 records tests. Initial receipt
`oct17-e09-e2l5er98` records parent `6bc62d6` plus five file hashes, unchanged
during the 08:48:00–08:48:14 UTC run. Final documentation/source rerun
`oct17-e09-5ionikd_` also passed all four commands with unchanged source; its
five hashes match the committed `4986274` tree. No C1/C2 overlays were used for
that individual-PR verification. The new 44 tests are included, not additive.

[C's timing request](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231875735)
asks A/B for 18–19 October Sydney availability. Lucas confirmed both days;
A/B responses and an actual booking are pending. The component README holds a
blank private record format and the original seal/blind/lock/review ordering.
No real Gold labels, timing answers, seal, human action or signature is created.

The exact 21-file composite separately passed **288 contract tests**, including
the 88 evaluation, 29 Risk and nine handoff tests, plus the same six static
groups and other suites listed above. Receipt `oct17-composite-p5vjyvwz` records
the unchanged source/overlay hashes; this count paragraph was added afterwards
and the final source/documentation rerun is retained with the PR publication.
It remains a reconstruction, not standalone #79 or adopted runtime. No PG17,
real LLM, formal performance, Gate, Jira Done or merge is implied.

### Earlier same-day 17-file increment — historical source and results

The following describes #69 `cfda3a1` and #70 `6bc62d6`, before the quality/pair
addition above; its 17-file counts and receipts remain historical evidence.

#69 preserves external cancellation even when a cooperative transport
swallows it; it cannot become PASS or an ordinary model failure. #70 adds
synthetic proposal-latency arithmetic with wait-union exclusion and p50/p95.
An independent AI-assisted review found an ambient Decimal-context precision
problem; the final code uses context-independent integer half-even arithmetic
and a regression test. This review is not A's non-author acceptance.

Each individual PR was verified on its own exact source plus the committed
three-file delta, using the locked Python 3.12.7/Node 24 environment:

- #69: 29 focused Risk tests within 157 contract tests.
- #70: 44 focused evaluation tests within 172 contract tests.
- Both: `pip check`, 6/6 static groups, 12 checker and 7 tool regressions,
  14 Mermaid blocks, 64 synthetic-order, 244 security and 36 records tests.

The exact local receipts are `oct17-c2-6qikeq3c` and `oct17-e09-lao6bqij`,
both at 08:21:37–08:21:51 UTC on 17 October; source hashes were unchanged
during testing. The focused counts are included in contract totals. These are
not PG17, Linux attachment, installed-wheel, cloud CI, real model, Gold, runtime
gate or human acceptance evidence. No required check is bypassed by `[skip ci]`.

The reconstructed composite separately passed **244 contract tests** (including
44 evaluation, 29 Risk and nine handoff tests), all six static groups and the
same other suites listed above. The `oct17-composite-yuo5b9aw` receipt records
08:23:16–08:23:32 UTC, exact 17-file overlays and unchanged source during that
run; this explanatory paragraph was added afterwards. An additional final
source/documentation rerun is retained with the published PR evidence.

The [README A decision checklist](../../README.md#a-decision-checklist--reply-on-the-existing-prs)
identifies exact corpus approval, model/retained-input handoff, measurement and
private Gold protocol decisions, R.02/R.03 evidence and the later C3 boundary.
Pending corpus remains rejected. This PR still does not duplicate dependencies
or run standalone; keep it Draft until adoption and integrated-source reruns.
The earlier same-day and 15 October receipts below retain their historical scope.

## Earlier 17 October follow-up — historical reconstruction and receipt

This branch now includes main
`17042b4164a0be878c7a0684cf532217ebeb77ee` via merge `da8e7e6`.
PR #80 changed public-scope/path comments and branch-push CI selection, not the
business runtime. Both its README notice and the earlier C handoff are retained.
The JSON receipt below remains **15 October evidence**, not a claim that its
212-test run covered today's source.

For today's composite review, keep the same five files from #68 at `af44d6e`
and four from #69 at `2ac0442`. Replace the four-file #70 restore block below
with this **six-file** block at the new exact E.09 candidate:

```sh
git fetch origin pull/70/head
git cat-file -e 51dbfa0d5d896ad82a2ebaea77aa2de40c681d27^{commit}
git restore --source 51dbfa0d5d896ad82a2ebaea77aa2de40c681d27 -- \
  experiments/evaluation_candidate/README.md \
  experiments/evaluation_candidate/__init__.py \
  experiments/evaluation_candidate/scoring.py \
  experiments/evaluation_candidate/runner.py \
  tests/contracts/test_evaluation_preparation.py \
  tests/contracts/test_evaluation_runner.py
```

Use a clean disposable worktree as described below, not a teammate's checkout.
The composite now contains **15 dependency files**, not 13. For the offline
baseline comparison use `17042b4164a0be878c7a0684cf532217ebeb77ee`; the original
`a0f7fb8` commands and hashes below remain historical. The runner introduces no
live transport, Gold data or API wiring. This Draft still cannot be imported as
a standalone C1/C2 implementation and still awaits dependency adoption plus
non-author review. The source update does not satisfy R.02/R.03 or any Done gate.

Local verification on 17 October passed: 226 contract tests (including the
29 evaluation tests and the nine handoff tests), 6/6 static groups,
12 checker regressions, seven check-runner regressions, 14 Mermaid blocks,
64 synthetic-order tests, 244 security tests and 36 records tests. `pip check`
also passed. This used locked Python 3.12.7 and Node 24, with source snapshots
and full logs retained locally. No source changed during the recorded runs.
The standalone #70 source at `51dbfa0` separately passed 157 contract tests;
its lower total correctly excludes #68/#69 and this handoff's additional tests.
Neither run includes PG17, supported-Linux attachment checks, installed-wheel
probes, actual AI, Gold performance or human acceptance. Older Linux and CI
receipts remain valid only for their own earlier source and are not re-labelled.

## Historical 15 October review boundary

**Draft: do not merge before its dependencies are reviewed and integrated.**
This change publishes only README/review evidence and
[`test_c_handoff_rehearsal.py`](../../tests/contracts/test_c_handoff_rehearsal.py).
It deliberately does not duplicate the 13 candidate files in PRs
[#68](https://github.com/shuxiachai/returnops-au/pull/68),
[#69](https://github.com/shuxiachai/returnops-au/pull/69) and
[#70](https://github.com/shuxiachai/returnops-au/pull/70).
A fresh checkout of this draft alone therefore cannot import the C1/C2 candidate
modules used by the new tests. Preliminary review uses the composite below;
merge readiness requires a new run against the eventual integrated source.

The nine new tests compose synthetic C1 admission, actual offline retrieval and
citation verification, and a **stub** C2 Risk transport. They cover the happy
path, pending admission, source omission/substitution/staleness, blocking and
non-blocking source conflicts, malformed authority-bearing output and transport
failure. Fixture approvals are explicitly synthetic test inputs, not approvals
of the pending ACCC candidate. There is no application route, live model call,
authoritative state mutation, real customer data or Gold label in this change.

Trace: FR-006/FR-007/FR-008 and NFR-001/NFR-002/NFR-009; AH-08 → UC-02 →
MC-ACT/MC-SEQ. Existing allocation and start/finish dependencies in
[docs/07](../07-frozen-work-allocation.md) and
[docs/08](../08-delivery-work-packages.md) remain unchanged.

## Exact evidence and limits

Baseline: `a0f7fb884dfbc478c82fffc5912934cb8c0deda2`.
The [machine-readable summary](c-local-handoff-20261015.json) lists the exact
dependency commits, file hashes and rehearsal hash. The 04:53 UTC run used that
baseline plus those 13 dependency files, the nine-test file, and an earlier
README notice. The README was subsequently clarified for publication; its
historical hash is retained rather than represented as the published README.
The raw logs are retained locally, not included in this PR.

| Check | Observed result | Exact scope |
| --- | --- | --- |
| Dependency consistency | `pip check` passed | Isolated Python 3.12.7 environment |
| Contract discovery | 212 passed | Composite above: 203 existing + 9 new |
| Offline static runner | 6/6 groups passed | Same composite; not the entire CI workflow |
| Markdown / model validation | 84 Markdown files, 676 local targets; 14 Mermaid blocks | Historical composite documentation |
| Checker self-tests | 12 model checker + 7 runner tests passed | Same local environment |
| Synthetic order suite | 64 passed | Same composite |
| Security / records suites | 244 / 36 passed | Same composite |
| Customer attachment suite | 82 passed | Separate local Linux container, **main-only** snapshot, not this composite |
| Installed-wheel probes | 5 passed | Same separate main-only Linux snapshot |

The native macOS customer run had 23 failures and 59 passes because the current
attachment worker's resource isolation supports Linux/Windows, not Darwin.
Those failures were retained, not suppressed by weakening resource limits.
The separate Linux run used an unprivileged, network-disabled, read-only
container with no host data mounts. It does not validate this new draft.

**Not established:** new PG17/HTTP integration, approved real corpus admission,
actual independent Risk invocation, model quality, R.02/R.03 or Gate 1/2,
formal Gold evaluation, C3 image analysis, A/B acceptance or personal sign-off.
The earlier dependency PR checks belong to their own source revisions only.
Publication uses a `[skip ci]` commit to conserve the requested Actions budget;
skipped or pending required checks are not passing checks and must not be
bypassed for a merge. No workflow or protection setting is changed.

## Historical 15 October reproduction only

**The commands below deliberately retain the old 13-file/212-test snapshot.**
For the latest exact-source reconstruction, use the
[current reconstruction](#current-isolated-reconstruction) above, not this
historical restore list or baseline.

Start from a checkout of **this handoff commit** with a clean index. Do not
overlay candidate files onto another member's working directory. The following
creates a disposable detached worktree and restores only the exact dependency
files into it; it does not merge or approve their PRs. Retain the generated
directory and logs until review is complete.

```sh
git fetch origin pull/68/head pull/69/head pull/70/head
git cat-file -e af44d6e02cf479e94b695ee85a8b823540974bf7^{commit}
git cat-file -e 2ac04423f7c8c4cb66094838e08619a2fd65c672^{commit}
git cat-file -e 7c6739fbb27c05f17e5c537e99615a9630e43d2d^{commit}
handoff_review_dir=$(mktemp -d "${TMPDIR:-/tmp}/returnops-c-review.XXXXXX")
git worktree add --detach "$handoff_review_dir/repo" HEAD
cd "$handoff_review_dir/repo"
git restore --source af44d6e02cf479e94b695ee85a8b823540974bf7 -- \
  experiments/c1_grounding_candidate/admission.py \
  experiments/c1_grounding_candidate/candidates/accc-20261012/README.md \
  experiments/c1_grounding_candidate/candidates/accc-20261012/admission-manifest.json \
  experiments/c1_grounding_candidate/candidates/accc-20261012/corpus.json \
  tests/contracts/test_c1_corpus_admission.py
git restore --source 2ac04423f7c8c4cb66094838e08619a2fd65c672 -- \
  experiments/c2_risk_candidate/README.md \
  experiments/c2_risk_candidate/__init__.py \
  experiments/c2_risk_candidate/reviewer.py \
  tests/contracts/test_c2_risk_preparation.py
git restore --source 7c6739fbb27c05f17e5c537e99615a9630e43d2d -- \
  experiments/evaluation_candidate/README.md \
  experiments/evaluation_candidate/__init__.py \
  experiments/evaluation_candidate/scoring.py \
  tests/contracts/test_evaluation_preparation.py
```

If a dependency head has moved and an exact commit is unavailable, stop and
agree a new reviewed snapshot; do not substitute a newer head while retaining
these results. Check each restored file against the receipt's SHA-256 hashes.
Install the locked dependencies in a separate Python 3.12 environment and the
locked Node 24 model tools using [check setup](../../tools/checks/README.md)
and [offline CI setup](../../.github/workflows/ci.yml). Then run:

```sh
python -B tools/checks/run.py offline --baseline-ref a0f7fb884dfbc478c82fffc5912934cb8c0deda2
python -B -m unittest discover -s tests/contracts -p 'test_c_handoff_rehearsal.py' -v
python -B -m pytest tests/security -q -p no:cacheprovider
python -B -m pytest tests/storage/test_records.py -q -p no:cacheprovider
```

Record source hashes, exact commands, outputs and skipped scope. These commands
do not dispatch Actions. PG17 needs its own explicitly owned disposable
database; the supported Linux attachment suite and installed-wheel checks need
separate execution. None may be silently inferred from this subset.

## What A can review now

1. Review the exact C1 admission/source candidates in #68 and C2 interface and
   fail-closed behavior in #69; review #70 as evaluation **preparation** only.
2. Inspect the nine-test composition and reproduce it in the isolated composite
   above. Comment on missing source, authority, failure or handoff cases.
3. Keep exact corpus/content approval separate from PR #61's capture approval.
   A trusted approval pin and approved model transport remain prerequisites.
4. After dependencies are adopted, update this branch from the actual approved
   main, rerun relevant checks and obtain non-author review before merging.

This handoff was prepared with Codex assistance. Test execution is recorded
technical evidence, not a claim that a human reviewed, accepted, independently
explained or completed these tasks. No Jira status is changed by publication.
