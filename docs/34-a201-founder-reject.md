# A2.01 private Founder REJECT

Owner A Jingbo Chai; designated human Reviewer C Yuwei Tao. [Issue 53](https://github.com/shuxiachai/returnops-au/issues/53) records this component under the existing partial KAN-15 mapping. Original S=F.01 and F=A1.03,F.03 remain unchanged. The leader authorized this component's limited start exception, isolated local implementation, offline checks and independent technical review on 8 October 2026. This does not establish predecessor, participant, joint, whole A2.01 or Gate 1 acceptance.

## Private interface and boundary

`compose_private_reject(engine, auth_config, authorization, **options)` returns a `FounderRejectService` with `accept(case_id, request, original_key, correlation_id)` and `recover(case_id, request, original_key)`. The request uses the frozen `FounderDecisionRequest` with `decision=REJECT`, expected case version, proposal ID/version and reason. Identity, current authorization, review, timestamp and target status are server-derived.

A new rejection requires exact modern `0008_review_escalation`, an available current `AWAITING_APPROVAL` case and its actual accepted PASS or PASS_WITH_WARNING review. It verifies the complete retained input, order, proposal, review and acceptance proof, rather than trusting a review outcome string. A missing review is not a modern compatibility path. The current trusted HUMAN request and the independently preconfigured `founder-reject-v1` OUTCOME capability are both required; this entry creates neither grant.

The transaction records the human decision and bounded causal audit, PRIMARY binding to the actual review, original idempotency receipt, OUTCOME work/claim/event, `REJECTED` outcome, `PENDING` notification and stable unclaimed notification work. Case version increments once; input, generation, proposal and review remain unchanged. The case stops at `NOTIFICATION_PENDING`. Notification work begins at epoch zero without a claim, lease or authority revision.

This private component exposes no public route or default producer and creates no approval, return, label or sender operation. It does not implement C's risk reasoning, call a live model or make a legal determination. `REJECTED` is the recorded human business decision; the pending notification is not evidence of delivery.

## Replay, current authority and retention

The `recordFounderDecision` operation uses a distinct `founder-reject-request/v1` fingerprint domain. A key cannot be reused across manual handling, revision and rejection. An exact replay returns the stored original receipt after checking original history, work, claims, bindings, audits and event identity. Original notification identity comes from the original OUTCOME notification binding, not a mutable current-notification pointer.

Current HUMAN/session/owner/store and OUTCOME authority, original claim/epoch, unextended lease, sealed state/work/bindings, retained source and exact schema are checked before commit, including after expensive source reads. Failure rolls the business transaction back. An ambiguous commit remains `UNKNOWN`: no automatic business retry, replacement key or reconstructed receipt. Missing retained facts do not become a successful recovery.

A deterministic denial can produce a separate bounded audit only after leaving the original transaction and independently rechecking current authority. Missing current authority does not permit a case audit. Retention and deletion cannot be bypassed by rebuilding original content from fixtures, cached source or current views.

## Verification boundary

The planned R1–R8 groups cover complete PASS/WARNING acceptance; absent, stale or tampered source proofs and direct guard bypass; current authorization and claim/lease fences; idempotency and concurrency; rollback and both actual outcomes of ambiguous commits; retention, replay and read views; installed-package execution with zero external effects; and explicit exact-0007 compatibility plus current regression.

Local database work remains paused by the user. PostgreSQL tests, including transaction/concurrency and installed-child database calls, are prepared for later execution and have **not** been run for this component. Offline collection, syntax/import checks, offline tests and independent static review must be reported separately from those pending runtime results. Previous main CI validates the previous baseline, not this new source.

No schema/OpenAPI or migration change is part of this component. Legacy exact-0007 assertions remain compatibility evidence; modern positive rejection must use an actual accepted PASS chain with equivalent notification identity, retry, completion and zero-effect assertions.

The local offline REJECT suite passed 25 tests. The final lifecycle collection found 913 tests, including 169 new PostgreSQL REJECT tests and those 25 offline tests; collection is not execution. The 169 prepared cases map to R1=2, R2=78, R3=47, R4=7, R5=10, R6=21, R7=3 and R8=1. Six new or modified test files passed syntax parsing. Production modules also passed syntax/import checks. Independent static review corrected a stale post-write head, a missing final replay schema check and a vacuous denial-event assertion; it also verified the additional missing-review bypass and source/install/wheel proof cases.

The existing CI-selected offline security, record, customer-codec/parser and synthetic-order regressions passed 426 tests in one corrected runner invocation. Its earlier invocation had 424 passes, one child-import failure and one temporary-directory setup error. Only the local runner was corrected: subprocess import paths and a unique unused pytest temporary directory. Test assertions and project source were unchanged for this correction; original failure logs remain. This success does not establish PostgreSQL acceptance or cloud CI for the new component.

The scope follows [A2.01](08-delivery-work-packages.md), the [frozen interface](09-interface-contract-v1.md), [Member A model chain](12-member-a-model-chain.md) and [state model](diagrams/02-state-machine-diagram.md): FR-009, FR-011, NFR-002, NFR-004 and NFR-009; UC-03. Original fixed ownership and dependencies are unchanged. Source push, PR publication, Ready, merge, Jira changes and teammate messages are outside this local grant.
