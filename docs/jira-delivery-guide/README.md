# Jira Delivery Guide

This is a compact workflow reference, not a second backlog or a live status
snapshot. Start at the [repository README](../../README.md) for current
delivery, review and submission receipts. Earlier guide revisions remain in
Git history; their dates, WIP assignments and pending-merge instructions must
not be reused as current facts.

## Sources and responsibilities

| Source | Authority |
|---|---|
| [Team workflow](../03-team-and-github-workflow.md) | Branch, review, Jira and evidence conventions |
| [Frozen allocation](../07-frozen-work-allocation.md) | Nine feature owners, default reviewers and hand-offs |
| [Work packages](../08-delivery-work-packages.md) | All 89 stable WBS IDs, Owner/Reviewer, S/F dependencies and acceptance |
| [Stage 1 readiness](../11-stage1-readiness.md) / [course requirements](../19-course-assessment-requirements.md) | Submission checks and dated Canvas/rubric evidence |
| [Team assignments](team-assignments.md) | Small ownership/WBS navigation index, not replacement allocation |

Jira holds live status, estimates, dates, blockers and Timeline. GitHub holds
technical scope, models/code, commits, PR reviews and CI. A coordinates Jira
maintenance; each member supplies their real progress; C verifies R.04
evidence. Do not duplicate a GitHub Project status board, copy every long
description, invent historical transitions, or turn 89 WBS checks into 89 new
cards. Group only related checks with the same owner and reviewable outcome;
retain each check's ID, dependencies and evidence.

## Workflow and review packet

The [docs/03](../03-team-and-github-workflow.md) team convention is
`Backlog → Ready → In Progress → In Review → Done`. These are workflow rules,
not a claim that the live Jira columns or any item currently have those states.

| State | Evidence required |
|---|---|
| Backlog | Agreed outcome; prerequisites and blockers remain visible. |
| Ready | Owner, estimate, priority, stage, dependencies, acceptance and linked technical Issue for repository work. Verify the actual delivery key; do not substitute a parent Epic or guess a new key. |
| In Progress | Work actually started. Follow docs/03: one primary item per member, three across the team. Small review/preparation work is not a fabricated extra implementation start. |
| In Review | Focused PR or reviewable non-code artifact, exact version, expected/actual checks and explicit limitations. Passing old CI does not validate a new revision. |
| Done | Original S/F dependencies and acceptance satisfied, normal/principal failure evidence, clean documented reproduction, non-author review, merged PR or approved artifact, and final evidence linked in Jira. Merge alone is insufficient. |

Every review packet identifies the actual Jira key, WBS IDs, owner/reviewer,
FR/NFR, AH/UC/UML, exact commit or artifact version, scope/non-scope,
reproducible commands/results, unresolved issues and next hand-off. Distinguish
static checks, mock/stub evidence, native execution, Compose reproduction,
business integration and measured evaluation. One does not silently prove
another. Never include secrets, real customer data or course PDF copies.

For repository changes, link the technical Issue, put the Jira key in the
Issue/PR, and use the Issue-based branch convention in docs/03. Keep the diff
focused; the author resolves feedback. Preserve the normal review/check/merge
policy and teammates' authorship; this guide grants no approval or authority
to merge another person's branch.

Default reviewers are **A → C, B → A, C → A**. Add affected producer/consumer
owners for interface or safety changes. Self-approval, AI-generated review
notes and syntax checks are not a teammate's personal acceptance.

## Course and acceptance boundaries

- Each member retains two core features and one **selected course optional**.
  Each member tests their own features; C coordinates evaluation, not all tests.
- Each member explains their own AH/UC/Activity/Interaction/State chain and
  records real participation in all shared tasks. The Lab 6 named-instance
  Object Diagram is distinct from Composite roles/ports. Acknowledge actual AI
  assistance without inventing personal walkthroughs, signatures or percentages.
- A integrates/submits the report and video; B/C supply and confirm their
  material; C verifies R.04 artifacts and receipts. Use docs/11 and current
  official instructions, not old guide/Jira dates. Submit honestly by the
  course deadline without waiting for Stage 2/Gold or all internal gates to close.
- For Gold evaluation, preserve docs/07–08 blinding: C seals the initial 30
  labels/sources/hash before reading any timed answers; both independent A/B
  outputs lock before E.05 hand-off, A review, B arbitration and E.08 final
  freeze/scoring. Pilot data is separate. This guide contains no Gold labels.

PR [#7](https://github.com/shuxiachai/returnops-au/pull/7) is supporting Jira
workflow documentation in the KAN-12 baseline context. Its publication does
not complete R.01, C's personal models/features, F.02, or course submission.
