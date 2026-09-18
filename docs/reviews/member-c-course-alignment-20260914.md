# C course-alignment preparation — 2026-09-14

> MC-COURSE-0.1. AI-assisted preparation and static/visual verification record for KAN-22. This is not a student's personal explanation, reviewer acceptance, runtime proof, submission receipt or Jira status change.

## Reference boundary

- Course sources: [dated team requirements register](https://github.com/shuxiachai/returnops-au/blob/docs/canvas-requirements-20260914/docs/19-course-assessment-requirements.md), including the current rubric SHA and the limits of preview/download coverage. The shared register is published separately for review, not merged by this task.
- A reference: F.01 rc.5 at `3dd1ff637693a826990eee5712cfb239a3c3da7b`. C pre-update head: `32c704f6bf4b86139b0bcbe53419fe23530fdd97`. A's [technical COMMENT](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5196102404) selected D01–03 at that earlier C head; it does not review these later artifacts.
- Local verification uses an isolated composite directory: prior exact A archive plus the browser-verified A test-file update and previously published C artifacts, then this documentation increment. It is **not a fresh authenticated Git checkout** or Docker/PostgreSQL 17 reproduction. Its checker Git baseline comparison is explicitly skipped.

## What changed in C's increment

| Artifact | Change / evidence scope |
|---|---|
| [MC-0.1.2](../18-member-c-model-chain.md) | Records A's actual D01–03 disposition, preserves public DTO/ownership boundaries, adds course and report-view mapping |
| [MC-RPT-0.3](../reports/member-c-stage1-draft.md) | Updated report argument, shared Object contribution, real contribution/AI and interview requirements; separates Stage 1 from later runtime targets |
| [MC-PER-0.1](../reports/member-c-contribution-and-interview.md) | Unfilled personal decision, four-scenario explanation, per-shared-task contribution and acknowledgement worksheet; no pre-signed answers |
| Three new report PUML/SVG pairs | Readable projections of the complete Activity/Sequence/State models; originals retained byte-for-byte |
| New Object PUML/SVG pair | Synthetic MC-T02 blocking-conflict instance snapshot; named objects, selected slots and instance links; no Founder approval or runtime claim |

## Actual checks performed

1. Four new sources were rendered locally to SVG and temporary PNG using the existing official PlantUML 1.2026.8 jar and Java 17. No model content was sent to an online renderer. All four final PNGs were visually inspected for complete labels, arrows, guards/legends and clipping. Dimensions and recommended insertion widths are in [MC §11](../18-member-c-model-chain.md#11-current-course-alignment-and-report-sized-model-views). Final assembled report/video readability still requires its own check.
2. The first static check detected embedded-source mismatch: PlantUML normalised U+2013 range dashes to ASCII in SVG metadata. Only five range separators in the three **new** report sources were changed to ASCII and the views re-rendered. No checker was weakened and no original model was changed to hide the failure.
3. `python3 -B tools/model-checks/check.py --skip-baseline` then passed **6/6 groups**, including **16 SVG/source pairs**. The pre-record run checked 38 Markdown files / 433 existing local file or directory targets. These counts predate this review record and its final backlinks; the final rerun is reported in the publication PR. Anchors and external URLs are not validated by this checker. Its A-specific checks and source correspondence are not general C UML semantic proof.
4. `python3 -B -m unittest discover -s tools/model-checks -p 'test_*.py' -v` passed **12 published model-tool tests**. This does not reuse the unpublished 18-test count or claim business service tests.
5. A separate read-only comparison checked all **89** unique WBS ID / Owner / Reviewer / S / F entries against the unchanged prior local baseline; the five fields match. Scope review found no change to A/B personal models, contracts, implementation code, original C diagrams or historical evidence.

No new HTTP/provider/LLM, database, concurrency, Docker, Gold, timed-human or B1/B4 test was run by this course-alignment increment. Previous logs keep their original dates and scope. Neither static success nor the synthetic Object view establishes a measured outcome.

## Handoff and remaining real work

- A: review the exact newly published C revision and the Object slice's relationship to shared classes/complex structure; integrate the final report and submit according to the unlocked Canvas instructions.
- B: integrate C's classification and model/Object references into M-S.03, returning exact version/section links. Existing A/B author records and functional ownership remain unchanged.
- C: personally read the final files, explain MC-T01/02/03/09 and D01–03, record genuine decisions/revisions and participation in each shared task, verify the final AI acknowledgement and R.04 submission evidence. The worksheet deliberately leaves these actions pending.
- F.01/F.02 joint acceptance, clean Git/Compose reproduction and C1/C2/C3 implementation/tests remain separate work. No merge, Done transition, Jira permission change, fabricated personal statement or course submission is performed by this record.
