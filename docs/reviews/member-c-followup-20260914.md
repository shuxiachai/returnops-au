# C follow-up — C-F01 retest, model/report hand-off

Date: **2026-09-14**. WBS F.01 reviewer C; M-C.01–.06 / R.04 contribution C, reviewer A. Jira [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22), [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32). Publication: existing [C PR #12](https://github.com/shuxiachai/returnops-au/pull/12), not a new parallel implementation or main merge. This is an **AI-assisted technical evidence record**, not a student signature, personal explanation or joint acceptance.

## 1. Remote changes verified today

| Item | Exact observed version | Consequence for C |
|---|---|---|
| main | `9eb7b0b46b1b28cfec300a59b03bba6a1d60c3bf` | Historical rc.2 publication, not current rc.5 acceptance |
| A PR #11 | `3dd1ff637693a826990eee5712cfb239a3c3da7b`, parent `64582a3007fea0fa3d1b1c3c212168b96af6b607` | A added three review records and corrected one contract-test file for C-F01; no schema, runtime or UML change |
| B PR #8 | `21f390f07bb3ce7e6dbdeee9c8a341748044ccd3` | B history retained and rc.5 alignment published; not proof of personal consumer acceptance or integration of C's classification table |
| C PR #12 before this update | `68e5e4b6569508c1988fa099eabbec8222ea5c0b` | Eleven C files retained; this follow-up updates two C documents and adds this record, a probe and evidence ZIP |

A's [C-F01 publication notice](https://github.com/shuxiachai/returnops-au/blob/3dd1ff637693a826990eee5712cfb239a3c3da7b/docs/reviews/c-f01-publication-20260914.md) and [C artifact technical review](https://github.com/shuxiachai/returnops-au/blob/3dd1ff637693a826990eee5712cfb239a3c3da7b/docs/reviews/pr12-followup-20260914.md) were read. The no-P1/P2 static review concerns the old C revision, not this follow-up, a formal A approval or runtime verification. Its local snapshot's 18 model-tool tests include unpublished checker changes; do not present that as the published suite's count. The three A review additions were read through GitHub, not reproduced as C-authored files.

The C branch retains its existing ancestry from `64582a3`; its PR targets A's branch, currently `3dd1ff6`. A's fix is **not copied into C's remote changes or attributed to C**. The independent retest below selects the reconstructed A source explicitly. A push-only run of the C branch and a PR merge-ref run can therefore test different upstream content; record the actual head/base/checkout when using CI. No branch rewrite or merge is performed by this task.

## 2. C-F01 result and source boundary

**Narrow technical disposition: the published test-oracle correction passes C's independent artifact regression matrix.** This resolves the reproduced binding/coverage defect at the verified test text, not all F.01 acceptance conditions.

GitHub commit and file views at `3dd1ff6` were accessible. The normal ZIP download instead displayed `ERR_BLOCKED_BY_CLIENT`; it was not bypassed. Command-line Git lacked authentication, and `gh` was unavailable. The local source was reconstructed from the previously retained exact `64582a3` archive plus A's displayed test-file change. Of 101 parent files, 100 were unchanged; only that test file differed. The three new A review documents are not present in the reconstructed test tree. This is **not a complete new source archive or clean Git checkout/ref reproduction**.

The entire GitHub `file content` text was compared by digest, not just visually sampled:

- File: `tests/contracts/test_contract_v1_rc4.py` at A's `3dd1ff6`.
- Browser text: 15,178 characters; 266 split lines.
- LF text, terminal LF stripped for browser comparison: SHA-256 `4fe46ea8b10869aabd9a587c65a2fa22bf45930236ff35eff0e95735a9b1bf9a`.
- Reconstructed LF-terminated local file: SHA-256 `e95714ae7d64d6555234656a33de8629e3bf337bdedecea6e6e80ed0c14c269d`.
- Parent source archive: SHA-256 `8eb49ccc0bae03171b23342e1f7ff3d03626dc52e17735db078b3f77f49bbe14`.

Fresh execution on Python **3.12.7**, macOS ARM64, at **09:03 UTC**:

| Check | Observed result | Scope |
|---|---|---|
| Complete contract unittest discovery | **58 passed**, exit 0 | Reconstructed published contract-test content; no HTTP/DB/provider |
| Independent C matrix | **15/15 passed**, exit 0 | Every input first passes the existing history schema |
| Eight malformed cases | New oracle rejects all eight; historical oracle accepts all eight | Stale packet/verification version, wrong proposal ID, missing/extra/replaced/duplicate checks, duplicate packet citation |
| Seven retained-history positive cases | Accepted | Original, coherent newer proposal, all four schema-legal non-VALID citation results, zero citations with zero checks |
| Original three C-F01 failures | Reproduced against old helper, rejected by new helper | Exact historical function extracted from old source, not a rewritten approximation |
| Source/fixture immutability | Passed | Probe deep-copies synthetic data and checks source hashes afterward |

The helper still does not implement a history service, enforce runtime Domain authority, judge claim support, or prove prompt independence. Legitimate failed citation evidence is intentionally retained. A safe historical record can contain a failed citation result; it does not become an executable recommendation.

## 3. Reproduction and retained evidence

- [Independent probe](member-c-cf01-probe-20260914.py), separate from A's test suite.
- [Sanitized evidence ZIP](member-c-followup-evidence-20260914.zip), SHA-256 `97261066b6054dea960cf6d0681e0a3439bd05785e0334506b6897dc94373796`.
- ZIP contains command timestamps/exit codes, 58-test log, full 15-case JSON/log, parent-file comparison, A's displayed test diff and a SHA-256 manifest. It contains no environment credentials, database, Gold labels or installed dependencies.

With the documented contract dependencies installed, run from the **selected A source**, not silently from the old C ancestry:

```sh
python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v
python -B /path/to/member-c-cf01-probe-20260914.py --source .
```

Optional old/new demonstration: add `--baseline-source /path/to/64582a3-source`. The probe verifies schema identity before comparing the old helper. Use `--output /path/to/result.json` to retain the actual new result. The recorded source hash, environment and limitations above apply to this run only; another source or future fix needs a new record.

## 4. C model and report update

[MC-0.1.1 documentation](../18-member-c-model-chain.md) and [MC-RPT-0.2 report](../reports/member-c-stage1-draft.md) now identify the current A fix, separate original evidence from new tests, and give A/B a precise next hand-off. MC-ACT/SEQ/SM remain **0.1**, with all six diagram files unchanged. The correction strengthens existing UC-02 C04 and UC-05 historical binding; it requires no diagram or public-contract change.

A separate AI-assisted static recheck found no blocking mismatch in the C models' five outcomes, authority boundaries, version bindings, original retrieval path and proposed round guards. This is not a human review or new runtime test. C must personally walk MC-T01 (pass), T02 (blocking conflict), T03 (clarification) and T09 (stale events). MC-D01–03 remain proposals requiring A/C disposition, not accepted wire fields or proven concurrency controls. B owns M-S.03; C's classification table is supplied for integration, not already credited as B's completed work.

The [Sep 12 review](member-c-rc5-review-20260912.md), [native F.02 record](member-c-f02-reproduction-20260912.md) and old evidence ZIP remain unchanged historical records. Their two PG16.2/native runs and same-API recovery do not become Sep 14 PG17/Compose evidence.

## 5. Jira and remaining gates

On today's live read, KAN-22 was still Ready with an old “no C PR” description, although PR #12 was published. KAN-32 was In Review but its title/link still pointed to rc.2/PR #9. These are synchronization gaps, not evidence of missing publication or acceptance. Current updates belong on the existing cards with real timestamps, preserving Owner/Reviewer, original estimates, dates and dependencies. No retrospective In Progress history or Done is manufactured.

A focused `project = KAN AND text ~ "F.02"` Jira search returned nine related cards but no distinct verified F.02 delivery card. KAN-14 is the downstream lifecycle umbrella, not automatically F.02. Ask A to identify/map the correct F.02 item; do not guess a key or create a duplicate under C's name.

Still open:

1. C's personal understanding/decisions and A's exact-revision non-author review; B consumer confirmation; joint F.01 accepted-version record.
2. A/C disposition of MC-D01–03 and B's exact C-classification integration link.
3. Authorized clean Git checkout and Docker/PostgreSQL 17 Compose reproduction, migration/full environment tests, same-API healthy→DB outage→recovery evidence. Docker was not on PATH; no new DB/container action was attempted. Native PG16 remains a disclosed alternative observation, not the requested platform acceptance.
4. F.02 acceptance, business implementation, Gate 1/2, Gold sealing/timing/evaluation and actual course submission remain separate. No C1/C2/C3 implementation, A/B edits, formal review approval, merge or course receipt is claimed.

GitHub/CI/Jira publication results will be recorded in the corresponding PR/card activity after the writes are verified, rather than predicted in this file. A remains the integrator; these prepared materials can support an honestly qualified Stage 1 report without waiting for complete business runtime acceptance.
