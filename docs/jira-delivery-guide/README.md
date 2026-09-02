# Jira Delivery Guide

> Snapshot prepared on 2026-09-02 from the ReturnOps AU Jira project. Jira remains the source of truth for live status, assignee, estimate, blockers, and dates. This directory is a delivery guide, not a second project board.

This guide turns the agreed Jira workflow into a small, repeatable GitHub delivery process. For the current ownership snapshot, see [team-assignments.md](team-assignments.md). For the full team agreement, see [`docs/03-team-and-github-workflow.md`](../03-team-and-github-workflow.md).

## Source-of-truth split

| System | Record kept there |
| --- | --- |
| Jira | Epics and Stories, owner, estimate, priority, stage, status history, blockers, and Timeline |
| GitHub Issue | Technical scope, explicit non-scope, acceptance criteria, Requirement IDs, dependencies, and expected tests/evidence |
| GitHub branch, PR, review, commit, and CI | Implementation and engineering-review evidence |

Do not create a duplicate GitHub Project status board or copy full Jira descriptions into this directory.

## Required workflow

`Backlog -> Ready -> In Progress -> In Review -> Done`

| Status | Entry and exit rule |
| --- | --- |
| Backlog | The outcome is agreed but the item is not yet implementation-ready. Keep dependencies and blockers visible in Jira. |
| Ready | Jira has an owner, estimate, Project Priority, Stage, Delivery Type, Requirement IDs, acceptance outcome, and—for repository work—a linked GitHub Issue with a Jira backlink and expected evidence. |
| In Progress | The owner has pulled the highest-priority Ready item, created a correctly based branch, and started producing evidence. Each member may own at most one primary In Progress item; the team limit is three. |
| In Review | A focused PR is open, the Jira key and Jira link are present, acceptance evidence is included, and automated checks are passing or any exception is explained. |
| Done | Acceptance criteria and normal/failure-path tests pass; traceability and documentation are consistent; a teammate has approved; the change is merged (or an approved non-code artefact is complete); and Jira links the final evidence. |

Blocked work stays visible. Add the `blocked` label, record the reason and next decision in Jira, and add `needs:tutor-feedback` when tutor input is the gating dependency.

## GitHub evidence contract

1. Start from one Jira Story and its linked GitHub Issue. Do not begin an untracked implementation item.
2. Include the GitHub Issue number in the branch name, for example `feat/42-case-intake`, `fix/41-approval-check`, or `docs/5-jira-delivery-guide`.
3. Put the Jira key in the Issue and PR title, for example `[KAN-18] Deliver customer submission and clarification portal`.
4. In the PR body, include the Jira link, related GitHub Issue, Requirement IDs, scope/non-scope, tests or artefact evidence, dependencies, and known risks.
5. Keep the PR reviewable in about 20 minutes. Split unrelated outcomes into separate Jira/GitHub delivery items.
6. The author resolves review comments. At least one other member approves; CI, tests, linting, and documentation checks pass before squash merge.
7. Update Jira's GitHub Link and move the item through the workflow as the evidence changes. Do not use GitHub Issues as a second sprint board.

## Review rotation

- Member A work is reviewed by Member B or Member C.
- Member B work is reviewed by Member A or Member C.
- Member C work is reviewed by Member A or Member B.
- The author never provides the only approval for their own PR.
- Changes to scope, interfaces, models, evaluation labels, or human-safety controls require review by the downstream owner as well as a general code review.

## Definition of Done checklist

- [ ] Acceptance criteria pass.
- [ ] Normal and principal failure paths have automated tests or reproducible artefact evidence.
- [ ] Structured logs and errors are meaningful.
- [ ] Requirement IDs and affected MBSE models remain traceable.
- [ ] No secret, real customer data, or copyrighted course material is committed.
- [ ] New interfaces or architectural decisions are documented.
- [ ] Another team member has approved the PR.
- [ ] The change works from a clean documented setup.
- [ ] Jira links the merged PR or approved artefact before moving to Done.

## Current baseline gate

The Baseline v1.0 candidate remains non-canonical until the remaining team/tutor review is recorded and the stacked adoption sequence is completed. Member C's review is complete; Member B and tutor review remain open. [KAN-6](https://lucastaooo.atlassian.net/browse/KAN-6) therefore remains visible and blocked. Preserve the existing PR order [#2](https://github.com/shuxiachai/returnops-au/pull/2) -> [#4](https://github.com/shuxiachai/returnops-au/pull/4) -> [#6](https://github.com/shuxiachai/returnops-au/pull/6); do not treat candidate-only text as merged `main` behaviour before adoption.
