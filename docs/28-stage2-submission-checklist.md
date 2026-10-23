# Stage2 submission and contribution preparation

## Live Canvas verification — 12 October 2026

The following original sources were read in the signed-in course UI, not
inferred from a teammate's progress estimate:

- [Stage 2 Marking Criteria, pp1–2](https://canvas.sydney.edu.au/courses/74323/files/52834535?module_item_id=3133247):
  confirms the 7/4/4/5 marks below, **Jira** collaboration, **1 November 2026
  23:59 source deadline**, and **Week 13 Canvas-download/on-site deployment**.
  This is a rubric, not awarded project marks. The contribution statement needs
  group number, names/student IDs, four criterion-specific percentage rows each
  totaling 100%, and actual tasks/deliverables. The note says absent statements
  imply equal contribution; this is not permission to invent percentages.
- [Project Description, pp1–2](https://canvas.sydney.edu.au/courses/74323/modules/items/3245780):
  the Stage 1 architectural prototype should implement most models, demonstrate
  LLM-enhanced perception/decision/interaction, reflect Agile experience and
  justify advanced technology. Its older final-week wording is less specific
  than the Stage 2 rubric's explicit date.
- [Lab 2, p1](https://canvas.sydney.edu.au/courses/74323/modules/items/3133252):
  at least three business AI roles; **each person individually implements at
  least two core and one optional feature**. C1/C2/C3 remain C's fixed allocation;
  evaluation/documentation is not a replacement for a missing feature.
- [Lab 9 / Week 10, p1](https://canvas.sydney.edu.au/courses/74323/modules/items/3133259):
  carry out a sprint review/retrospective, discuss achievements/pending work and
  stakeholder feedback with the tutor, and refine Jira stories. It also introduces
  the ELEC5620 AI Proxy / Campus Qwen with a separate connection guide and
  key/VPN/OpenCode setup. This is an available course resource to investigate,
  not evidence that our project is configured, that model access is approved,
  or a requirement to replace the team's chosen provider. Do not commit keys.
- [Assignments list](https://canvas.sydney.edu.au/courses/74323/assignments):
  at this check it lists the midterm and two closed Stage 1 items, **no visible
  Stage 2 upload item**. Upload types/limits, exact submission options and
  timezone therefore remain unverified. Recheck the eventual final item and
  teacher notices before packaging/submission; do not guess an assignment URL.

The PDF viewer was readable, but this turn's rubric download did not complete.
The SHA256 below remains the **5 October local-copy receipt**, not a newly
computed hash of today's live PDF. No course PDF is added to the repository.
This verification does not check any completion box, change WBS dependencies,
submit coursework, assert personal explanation or authorize a merge.

## Historical preparation — 5 October 2026

Prepared 5 October 2026 from local primary course files. This is an implementation
and submission checklist, not a new Stage1 report, a submitted contribution form
or a claim of completed features. The original nine-feature allocation and89 WBS
Owner/Reviewer/S/F values remain unchanged.

## Verified local course requirements

The newly available two-page `practical/ELEC5620 Project Stage 2 Marking Criteria.pdf`
has SHA256 `21b40026f135debeac05c411440bdb2710ba00616198f6106d0aaf748e8083ea`.
Page1 specifies **1 November 2026,23:59** for source submission and a Week13 demo
that downloads the source directly from Canvas and deploys it on site. The PDF
does not state a timezone. Current Canvas upload options and any later notice
have not been verified; the user reports that Stage2 notices have not arrived.
This specific local rubric supplies the date, rather than a guessed calendar
conversion from the older Project Description's final-week wording.

| Rubric criterion | Marks | Evidence to produce |
|---|---|---|
| Stage1 requirements/design implementation |7| Trace requirements/models to implemented UI, Domain, retrieval/Risk and deterministic execution; demonstrate normal and important failure paths; identify unfinished scope |
| AI agent capabilities |4| Show the three business roles perceiving inputs, making proposals/reviews and interacting; preserve prompt/model/input/output versions and actual LLM evidence; fixed offline packets do not satisfy live-agent evidence |
| Agile experience |4| Actual Jira collaboration, short iterations, feedback and resulting changes, CI/test evidence, and a truthful retrospective with each member's contribution |
| Advanced technologies |5| Explain effective use of selected application framework, database, Docker/CI and AI techniques with actual deployment/run evidence; the examples in the rubric do not mandate Kubernetes or a new cloud service |

AI agent capabilities evidence (22 October 2026): the advisory, default-off A1.06 Coordinator showcase and its provider record, data flow and fail-closed paths are in [docs/44](44-coordinator-showcase.md); its first live result is pending, and it is not three-role or Gate 2 evidence.

The rubric page2 requires names/student IDs, each member's percentage under each
of these four criteria, and specific completed tasks/deliverables. Each criterion
row must total100%; unused member columns stay blank. The frozen45/27/28 planned
effort split is not an observed contribution split.

Local Lab2 page1 requires at least three distinct business AI roles and **each
person individually implementing at least two core features and one optional**.
Lab2 SHA256: `9f4d9f12b4e8da16331a6b422d240de39cdf89b9a245a00b6cb61bd90cbaa6d3`.
Project Description page2 (SHA256
`391e85290bf1c31d4aee61529e1ee132e58b44d4839d15d5fc1ab00446c565f4`)
also calls for implementing most models, LLM-enhanced perception/decision/interaction,
Agile reflection and advanced technology. Lecture8 reinforces iterative feedback,
review/rework and Jira; it does not require every possible Agile practice.

## Ordered completion checks

- [ ] Record genuine A1.03 and original predecessor decisions using the
  [current review sheet](reviews/a103-acceptance-current.md); reuse actual reviews
  only for matching scope/version.
- [ ] After the original S gate, integrate A1.05 fixed current-source packet
  persistence through RISK_REVIEW; complete A2 simulated approval/execution,
  uncertain-outcome recovery, separate notification and audit, then R.02/Gate1.
- [ ] Integrate the real Coordinator/Assessment, C's retrieval/citation/Risk,
  B's customer/Founder UI and the selected A3/B3/C3 optionals under their original
  gates. Record unavailable A3 permission/tutor disposition truthfully.
- [ ] Keep pilot data separate; seal30 initial Gold labels before timed answers;
  retain actual quality/latency/failure evidence and denominators. These evaluation
  sizes are project targets, not numeric quotas newly imposed by this rubric.
- [ ] Retain actual Jira issue/history links, review feedback and fixes, iteration
  notes and member test evidence; do not fabricate Jira Done states or authorship.
- [ ] Freeze the chosen source commit; include source, locked dependencies,
  migrations, synthetic sample setup and portable installation/start instructions.
  Exclude credentials, local virtual environments and personal data.
- [ ] Rehearse from the **actual uploaded/downloaded Canvas package** in a clean
  environment, without relying on this computer's ignored files. Record package
  hash, environment, commands, migrations, synthetic initialization and demo
  outcomes. A GitHub CI pass alone is not this Canvas-package deployment proof.
- [ ] Fill and verify the actual contribution statement, including student IDs,
  row totals and linked completed work; confirm current Canvas format/timezone and
  any individual interview arrangements once notices become available.

No checkbox is pre-filled by this preparation. The last deployment rehearsal and
upload checks occur against the final submission candidate, not today's partial
prototype. Actual video production remains with the team/user.

R.05 working documents (22 October 2026): [demo script](45-stage2-demo-script.md), [Gate 2 roadmap](46-gate2-roadmap.md) and [submission runbook](47-stage2-submission-runbook.md); they check no box above. The Agile evidence and technology data for the rubric's two record-based rows are collected in [docs/48](48-agile-evidence-and-technology-data.md) (23 October 2026).

## Contribution working table — unfilled, not for submission yet

| Criterion | Jingbo Chai (A) | Chengsi Li (B) | Yuwei Tao (C) | Required final total |
|---|---|---|---|---|
| Requirements/design implementation | TBD | TBD | TBD |100%|
| AI agent capabilities | TBD | TBD | TBD |100%|
| Agile experience | TBD | TBD | TBD |100%|
| Advanced technologies | TBD | TBD | TBD |100%|

| Member | Student ID | Completed tasks and deliverables with exact PR/commit/test links | Actual AI assistance and personal work |
|---|---|---|---|
| A / Jingbo Chai | To supply | To record actual scope | To record |
| B / Chengsi Li | To supply | To record actual scope | To record |
| C / Yuwei Tao | To supply | To record actual scope | To record |

A owns planned A1/A2/A3; B owns planned B1/B2/B3; C owns planned C1/C2/C3.
These names and planned ownership are not evidence of individual implementation.
Existing authored work/reviews are reused and attributed to their real contributors.
Student IDs, percentages and completed-feature claims are never inferred from
email addresses, planned effort, AI-generated preparation or technical adoption.
