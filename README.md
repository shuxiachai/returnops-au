# ReturnOps AU

> Topic status: provisional, pending team validation and tutor feedback.

ReturnOps AU is an evidence-grounded multi-agent returns operations service for
Australian e-commerce SMEs. It helps a human founder investigate customer
product-problem requests, propose an appropriate remedy, and coordinate the
approved operational follow-up.

## One-sentence company brief

For Australian e-commerce SME founders handling product-problem requests,
resolution is slow and inconsistent because customer messages, order records,
store policies, consumer-law guidance, and logistics state are fragmented.
ReturnOps AU coordinates intake, investigation, policy, resolution, and audit
agents to produce an evidence-grounded proposed remedy and complete approved
follow-up, while the human founder approves refunds, replacements, repairs, and
other high-impact actions.

## Narrow promise

Given a customer request and an existing order, ReturnOps AU will produce a
traceable proposed resolution within two minutes, identify missing evidence,
cite the supporting store policy or guidance, and route all high-impact actions
through human approval.

## MVP boundary

The prototype supports Australian physical-goods e-commerce and three request
types:

- faulty product;
- wrong item delivered;
- change of mind.

The prototype uses simulated order, payment, refund, and logistics systems. It
does not provide legal advice, move real money, or autonomously approve a
refund.

## Success measures

- At least 90% request-type classification accuracy.
- At least 95% mandatory-information recall.
- At least 90% citation correctness.
- At least 95% recall for cases requiring human escalation.
- Median proposed-resolution time below two minutes.
- Zero executed high-impact actions without recorded human approval.

## Project documents

- [Project charter](docs/01-project-charter.md)
- [System design](docs/02-system-design.md)
- [Team and GitHub workflow](docs/03-team-and-github-workflow.md)
- [Requirements and initial backlog](docs/04-requirements-and-backlog.md)

## Current phase

The team is in problem discovery. The next decision gate is to validate the
problem with potential users, review the scope with the tutor, and confirm that
the three team members can deliver the thin vertical slice before expanding the
feature set.

