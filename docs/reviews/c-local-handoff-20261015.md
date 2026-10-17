# C dependent review handoff — 15 October 2026

Tracking: [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) (C1),
[KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) (C2);
[KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25) is related evaluation
preparation, not formal evaluation completion.

## 17 October follow-up — updated reconstruction, historical receipt retained

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

## Review boundary

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

## Reproduce in an isolated checkout

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
