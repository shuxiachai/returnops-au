# Team Assignments

> Snapshot: 2026-09-02. Use the linked Jira items for live status, dates, assignee, estimates, and blockers. This file records stable ownership and hand-off intent only.

## Member A — System Architect and Backend / Agent Lead

**Identity:** Jingbo Chai / GitHub `@shuxiachai` / Jira `Jingbo Chai`  
**Epic ownership:** [KAN-6](https://lucastaooo.atlassian.net/browse/KAN-6), [KAN-7](https://lucastaooo.atlassian.net/browse/KAN-7), and [KAN-10](https://lucastaooo.atlassian.net/browse/KAN-10)

Immediate Jira action: KAN-6 currently occupies A's primary In Progress slot and is blocked on the remaining baseline reviews. Keep KAN-12, KAN-13, and KAN-28 in review, record Member B/tutor disposition, preserve the `#2 -> #4 -> #6` adoption order, and do not pull another primary item until the WIP slot is available.

| Jira item | Required outcome | Planned due date |
| --- | --- | --- |
| [KAN-12](https://lucastaooo.atlassian.net/browse/KAN-12) | Adopt Baseline v1.0 and freeze traceability | 2026-09-06 |
| [KAN-28](https://lucastaooo.atlassian.net/browse/KAN-28) | Freeze and summarise desk-research evidence and assumptions | 2026-09-06 |
| [KAN-13](https://lucastaooo.atlassian.net/browse/KAN-13) | Complete shared MBSE models and the AH-10 chain | 2026-09-13 |
| [KAN-29](https://lucastaooo.atlassian.net/browse/KAN-29) | Implement the mock commerce adapter and typed order lookup | 2026-09-20 |
| [KAN-14](https://lucastaooo.atlassian.net/browse/KAN-14) | Enforce the authoritative lifecycle, typed contracts, and audit spine | 2026-09-27 |
| [KAN-30](https://lucastaooo.atlassian.net/browse/KAN-30) | Implement typed case extraction, order matching, and the evidence-gap path | 2026-10-04 |
| [KAN-31](https://lucastaooo.atlassian.net/browse/KAN-31) | Generate versioned, non-executable decision proposals | 2026-10-11 |
| [KAN-15](https://lucastaooo.atlassian.net/browse/KAN-15) | Build exact-scope approval and governed simulated execution | 2026-10-25 |
| [KAN-16](https://lucastaooo.atlassian.net/browse/KAN-16) | Optional logistics sandbox/test adapter and recovery path | Portfolio / unscheduled |

## Member B — Frontend and User Experience Lead

**Identity:** Chengsi Li / GitHub `@ChengsiLi` / Jira `banana`  
**Epic ownership:** [KAN-8](https://lucastaooo.atlassian.net/browse/KAN-8)

Immediate Jira action: review the Baseline v1.0 candidate and its `#2 -> #4 -> #6` stack without opening another primary WIP item. KAN-27 currently occupies B's In Progress slot; finish, park, or explicitly reclassify it before moving KAN-17 from Ready to In Progress.

| Jira item | Required outcome | Planned due date |
| --- | --- | --- |
| [KAN-17](https://lucastaooo.atlassian.net/browse/KAN-17) | Review journeys and author the AH-01 to UC-01 personal model chain | 2026-09-13 |
| [KAN-18](https://lucastaooo.atlassian.net/browse/KAN-18) | Deliver the customer submission and clarification portal | 2026-10-11 |
| [KAN-19](https://lucastaooo.atlassian.net/browse/KAN-19) | Deliver the Founder review and approval dashboard | 2026-10-25 |
| [KAN-20](https://lucastaooo.atlassian.net/browse/KAN-20) | Complete UI end-to-end tests and repeatable demo fixtures | 2026-11-01 |
| [KAN-21](https://lucastaooo.atlassian.net/browse/KAN-21) | Optional operations analytics dashboard | Portfolio / unscheduled |

KAN-27 is B-owned and must not be edited by another member. It is excluded from this delivery allocation unless B and the team explicitly reclassify it in Jira.

## Member C — Grounding, Risk, and AI Evaluation Lead

**Identity:** GitHub `@lulucas-tao` / Jira `Lucas Tao`  
**Epic ownership:** [KAN-9](https://lucastaooo.atlassian.net/browse/KAN-9) and [KAN-11](https://lucastaooo.atlassian.net/browse/KAN-11)

Immediate Jira action: confirm the Ready gates on KAN-22, then move only KAN-22 to In Progress while the team WIP limit allows it. After its review, deliver the versioned corpus, independent risk review, and reproducible Gold-set evaluation evidence in priority order.

| Jira item | Required outcome | Planned due date |
| --- | --- | --- |
| [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22) | Review grounding/evaluation and author the AH-08 to UC-02 chain | 2026-09-13 |
| [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) | Build the versioned runtime corpus and citation verification | 2026-10-11 |
| [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) | Implement independent risk review and escalation | 2026-10-25 |
| [KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25) | Freeze the 30-case Gold set and run B1 versus B4 evaluation and safety suites | 2026-11-01 |
| [KAN-26](https://lucastaooo.atlassian.net/browse/KAN-26) | Optional product-image evidence analysis | Portfolio / unscheduled |

## Cross-team hand-off gates

1. **Baseline gate:** A owns the adoption record; B and C review the candidate and unresolved assumptions before implementation treats it as canonical.
2. **Contract gate:** A publishes the domain, lifecycle, provider, case-extraction, and proposal contracts before B or C depend on them. Interface changes require downstream-owner review.
3. **Experience gate:** B supplies customer/Founder flows and repeatable UI fixtures; A confirms API compatibility and C confirms that evidence, warnings, and escalation states remain visible.
4. **Grounding and risk gate:** C publishes versioned passages, citation checks, risk outcomes, and evaluation labels; A integrates them without granting an agent approval authority, and B presents them without implying an unapproved action is complete.
5. **Evaluation gate:** B's repeatable fixtures and A's deterministic services feed C's Gold-set and parameterised suites. Failures remain documented; unsafe or materially conflicted proposals cannot reach Operations.
6. **Review gate:** the owner moves work to In Review only with linked evidence. A different member reviews it, and Jira moves to Done only after merge/artefact approval and final evidence linking.

## Daily rule for every member

1. Check Jira, not this file, for the live highest-priority Ready item.
2. Keep no more than one primary item In Progress.
3. Record blockers in Jira immediately; do not leave scope or safety decisions only in chat.
4. Link the GitHub Issue, branch, PR, tests, and review evidence back to the same Jira key.
5. Before finishing, run the Definition of Done checklist in [README.md](README.md).
