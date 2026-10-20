# A2.06 notification candidate — Issue 86 / KAN-15

This is an AI-assisted implementation candidate for A2.06, owned by A (Jingbo
Chai), with C (Yuwei Tao) as the original human reviewer. The adopted starting
commit is `a885cff474c41ccda1bb7ef82bb0f6e21a216bb0`. The technical task is
[Issue 86](https://github.com/shuxiachai/returnops-au/issues/86). The original
S=A2.01 and F=A2.05/F.05 relationships remain those in
[docs/08](08-delivery-work-packages.md). The lead authorized a bounded start
exception for the unverified A2.01 acceptance; this does not sign that
acceptance or waive the completion dependencies.

The private composition is `returnops_api.private_notification`. It exposes
`produce_return(case_id, expected_case_version)`, `send(notification_work_id)`,
`reconcile(notification_work_id)` and the current-Founder-only
`retry(notification_work_id, expected_case_version)`. Application startup and
public HTTP mutation routes do not register a sender. Existing authorized GET
routes provide current and historical views. Public POST integration is A2.07.

Migration `0014_notification_delivery` creates exactly two empty tables:
`notification_delivery_controls` and `core_mock_notification_facts`. It
requires the exact 0013 descriptor, verifies the new structural and owner/ACL
descriptor, and performs no data, grant or capability backfill. A migration
inheriting wider default privileges fails transactionally. Original v1 work
retains its owner, key, bodies and receipt identities; it cannot become a v2
delivery intent and remains HOLD.

Fresh rejection and supported manual producers save a fixed profile, original
source inventory, recipient identity and logical key with the original outcome.
The RETURN_CREATED producer reads the genuine retained approval acceptance and
the complete modern return, bridge, label and certified PDF chain. It has no
caller-supplied approval key and does not create a Founder identity. Existing
execution entry points continue to require their actual caller and key.

Sending has three separate transactions. T1 accepts a PENDING reservation
revision and closes successfully before invoking the mock. T2 owns an
independent fenced transaction and commits only an actual CORE_MOCK fact. T3
accepts that exact fact through `LifecycleGuards`, including final commit
checks. Uncertain acknowledgement remains UNKNOWN; recovery queries the same
reservation and may finish T3. It cannot send again. Only an accepted durable
NO_EFFECT_FAILED followed by a current Founder retry authorizes another
reservation with the same logical identity. Lease epochs and send attempt
counts are separate.

Customer content is fixed and explicitly simulated. The PDF is invalid for
postage; no real shipment, payment, legal-rights decision or shipping-cost
promise is made. Packaging and drop-off are not applicable to this mock flow;
responsibility, costs and further arrangements require human confirmation.
Only a proven SENT fact produces a customer OUTCOME_MESSAGE. Current GET
exposes its message string; history exposes the existing safe structured DTO.
Notification/PDF source withdrawal removes derived message bodies and leaves
verified tombstones, hashes and independent facts. No recovery path rebuilds
removed content.

## Requirement and model trace

| Requirement | Implementation responsibility |
|---|---|
| FR-009 | Preserve actual Founder reject/manual/approval provenance; current Founder retry |
| FR-010 | Exact approved simulated result proof, independent sending, no business-effect replay |
| FR-011 | Original receipts, finite history, audit, safe reads and retention |
| FR-012 | Three outcomes, fixed safe message, correct terminal status after SENT |
| NFR-001/003 | Explicit private composition, frozen DTOs, safe current/history views |
| NFR-002/004 | Same-case/store/recipient proof, fencing, no-effect retry and fail-closed uncertainty |
| NFR-006/007/008 | Exact source identity, reviewed migration, isolated offline/cloud evidence |

The model chain remains AH-10 → UC-04, with UC-03 admission and UC-05 reads:
[governed execution activity](diagrams/member-a/governed-execution-activity.puml),
[exact scope sequence](diagrams/member-a/exact-scope-sequence.puml),
[recovery and notification sequence](diagrams/member-a/recovery-notification-sequence.puml),
and [operation attempt state](diagrams/member-a/operation-attempt-state.puml).
See [Member A model chain](12-member-a-model-chain.md) and the shared contracts.
No new member acceptance or personal authorship claim is implied.

## Acceptance evidence status

The following is an oracle map, not a test-pass report. All PostgreSQL and
actual HTTP cases require the exact candidate's fresh cloud PostgreSQL job;
local PostgreSQL and Docker remain paused.

| AC | Candidate evidence / remaining work |
|---|---|
| 01–02 | `test_notification_delivery_postgresql.py`: actual completed return, rejection, PASS/ESCALATE manual, order failure/block, intake and assessment failure producers |
| 03 | `test_notification_execution_proof_postgresql.py`: actual complete chain, corrupt/missing proof, stale generation and independent fact aliases |
| 04 | `test_notification_guards_postgresql.py`, fact-alias tests: direct guard bypass and final receipt/authority closure |
| 05–06 | `test_notification_transactions_postgresql.py`: T1/T2/T3 commit/close uncertainty and rollback; independent installed recovery still pending |
| 07 | Delivery tests: real no-effect fact, current Founder retry, original identity and one success |
| 08 | Actual installed two-process contention, barrier and stale lease oracles still pending |
| 09 | Closed profile and independent fact offline files: 62 tests passed locally on their recorded exact hashes; recipient/source integration remains cloud evidence |
| 10 | Existing explicit legacy late-effect regressions retained; modern late-observation coverage still pending |
| 11–12 | `test_notification_reads_retention_postgresql.py`: existing real HTTP GET paths, safe SENT, scopes, snapshots and source/PDF tombstones; cloud execution pending |
| 13 | Schema and legacy tests: exact migration preservation, ownership/ACL negatives, empty new tables and explicitly labelled v1 compatibility samples |
| 14 | Updated exact lifecycle inventory and normal CI; actual full cloud outcome and final independent review pending |

The CI inventory retains the original 54 lifecycle files and adds the ten
notification test files exactly once. The new `notification` group is separate
from the six original groups. Explicit historical fixtures keep the original
0013/0007 assertions where they synthesize v1 notification transitions. Such
fixtures are not evidence of a historical real sender. Latest-head actual
producer checks use 0014 and assert the fixed v2 work owner/control.

An installed package import/profile probe is included, but it does not prove
installed business execution or concurrent processes. Publication as a Draft,
static review and offline success do not complete AC08/10/14, whole A2.06,
member review, original S/F acceptance, or Ready/merge.
