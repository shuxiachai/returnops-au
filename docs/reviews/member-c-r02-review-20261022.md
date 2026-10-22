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
