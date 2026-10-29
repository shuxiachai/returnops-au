# C S6: 90-second practice plan — 29 October 2026 (Sydney)

Tracking: [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41).
Prepared with Codex assistance; this is a plan, not a personal timing result.

[PR #151](https://github.com/shuxiachai/returnops-au/pull/151) changed the team
schedule to 11:30 within a 12-minute limit. The current
[shared script](../../docs/45-stage2-demo-script.md) gives C **8:45–10:15**,
so the complete S6 allowance is **90 seconds**, including commands, waiting,
screen changes and speech. This replaces the former 120-second practice target.
The course/time-limit statement is sourced to A's adopted script; this update
does not claim an independent Canvas or Ed re-verification.

## Spoken draft (76 words)

My work covers grounding, risk review and evaluation.

These twelve synthetic queries show retrieval misses and citation metadata, not model quality or whether advice is correct.

Four tests use fixed risk responses. Blocking conflicts require escalation. Invalid output or timeouts cannot pass. Even PASS needs the Founder's exact approval.

The definitions are frozen as version one. Failures stay in the denominator; unknown costs stay unknown. The live reviewer, image feature, pilot and formal evaluation remain unfinished.

Script file hash (UTF-8, LF, final newline): `01ebed1e31192c017f2f040c61515be07bf983705eee87894ca68313c34541fa`.
This is a new version. Keep any older practice/result with its original script
hash; do not edit an active timer or relabel an old result.

## Screen plan — proposed allocations, not measured durations

| Segment elapsed | Action and explanation |
| --- | --- |
| 0–25 s | Run the C1 summary in a pre-opened terminal. Explain synthetic retrieval, misses and citation checks. |
| 25–60 s | Run the four C2 contract tests. Explain conflict → ESCALATE, fail-closed responses and separate Founder approval. |
| 60–80 s | Show the version/hash manifest. Say definitions frozen, then name the unexecuted work. |
| 80–90 s | Buffer and hand back to A for S7. Do not spend this buffer opening new pages. |

At 80–90 words/minute, the draft alone would take about 51–57 seconds.
This is arithmetic, not a measured reading or proof that the complete segment
fits. The participant must time the complete segment on the demonstration
machine. A separate speech-only practice cannot establish that result.

Keep the terminal and manifest open before the segment; prepare the command
text but do not label a prerecorded output as live. If a command stalls or
fails, keep that outcome and announce any use of a dated fallback. Do not claim
4 passed unless the displayed run actually says so. If time is short, omit
numeric recall explanations and the optional evidence-bundle tour; retain
synthetic/fixed labels, the permission boundary and unfinished-work statement.
Do not add the 13-file evidence-bundle tour to the 90-second core plan.

## Two offline commands

From the chosen source root, use its existing Python environment. On Windows,
replace `python` with `.\.venv\Scripts\python.exe`. No model key, provider,
network call, PostgreSQL or Docker operation is needed for these two commands.

```sh
python -B -c "import json; from experiments.c1_grounding_candidate.pilot import run_pilot; r=run_pilot(); print(json.dumps({k:r[k] for k in ('retrieval_summary','citation_summary')}, indent=1))"
python -B -m pytest tests/contracts/test_c2_risk_preparation.py -k "five_outcomes or blocking_conflict or timeout_and_transport" -q -p no:cacheprovider
```

Codex reran both commands locally on **29 October 2026**, against unchanged
main `b5bcfa95cf752b6e4ac347a5c7bfced93a47ec2f`:

- C1: 12 synthetic queries; ranked-seed recall 16/22; conflict-expanded returned-set
  recall 20/22. These are different measures, not interchangeable Recall@k.
- Eight citation outcomes matched expectations: two valid accepted, six invalid
  rejected. This is identity/version/hash/location verification, not claim-support
  accuracy or a legal decision.
- C2: `4 passed, 30 deselected, 7 subtests passed` using fixed responses.

These are technical preparation results on macOS, not Lucas's practice,
Windows reproduction, a live Risk model or formal evaluation. The C1 developer
fixture's deterministic `checked_at` is not today's wall-clock execution time.
The 12 synthetic C1 queries are also **not** the 12 new development-pilot cases
planned in the E.01 guide.

## Current definition status and questions

[PR #152](https://github.com/shuxiachai/returnops-au/pull/152) adopted the freeze
record at main `b5bcfa95`; its source `b85fe27` and that combined main each passed
13/13 CI checks. A's [explicit confirmation](https://github.com/shuxiachai/returnops-au/issues/67#issuecomment-6462367944)
freezes source `6bb6cd68` definitions only. The
[manifest](../evaluation_candidate/e01-guide-manifest.json) carries the exact
source and hashes. Frozen guide/example bytes stay unchanged. The older S6
paragraph in the shared script still says the definitions are not frozen;
use this dated status correction and ask A to align the shared script.

For questions, understand the distinction: a material source conflict needs
ESCALATE and human handling; even a later PASS is only a review outcome. The
Founder must approve the exact current proposal and permitted operation scope
through the deterministic guard. A valid citation alone does not prove the
recommendation is supported. This explanation is teaching material, not a
record that the participant can already explain it independently.

The actual pilot, Gold/blind timing, B1/B4 comparison, real reviewer, C3,
individual understanding/timing and contribution/AI confirmation remain open.
The participant should retain start/end timestamps, script hash, code SHA,
mode (speech-only or complete), elapsed seconds, failures/fallbacks and their
own explanation. No estimated duration is entered as actual evidence.
