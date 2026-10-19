# A2.01 private PASS manual handling

Technical tracking: [Issue 64](https://github.com/shuxiachai/returnops-au/issues/64)
under the existing KAN-15 mapping. Base: `72ffd043dbd400b7ae81c3b1d23085ae0be1743b`.
Owner A Jingbo Chai, designated human reviewer C Yuwei Tao, S=F.01 and
F=A1.03,F.03 remain unchanged. The lead's current instruction to continue this
recommended component authorizes this bounded implementation. Original
accepted-version, personal, joint, whole A2.01 and Gate 1 acceptance remain
separate; neither this document nor synthetic tests supply a human signature.

## Entry and current source

The existing private `compose_private_manual` and
`FounderDecisionService.accept(case_id, request, original_key, correlation_id)`
remain the entry. The frozen FounderDecisionRequest supplies MANUAL_HANDLING,
proposal ID/version, expected case version and reason. It supplies no principal,
preview, review, source claim, permission or execution scope. The service needs
actual current F.03 HUMAN Founder authorization and independent OUTCOME
authority. It does not need PREVIEW or APPROVAL authority.

A new proposal request selects its source family from the current persisted
review event. REVIEW requires the complete accepted ESCALATE proof and
ESCALATED state. REVIEW_PASS requires the complete actual accepted
PASS/PASS_WITH_WARNING proof and AWAITING_APPROVAL state. Missing, unknown or
failed family proof is a denial, with no generic or alternate-family fallback.
Both proofs retain the actual input/order/proposal/review work, claim, binding,
audit and accepted event relationships. Historical grants are provenance,
not current permission.

Without a preview, expected case version equals the review's accepted version.
With a preview it equals the exact current tail's post version. Every predecessor
and explicit expired replacement must validate back to that same review.
The current tail must have no other consumer. A preview may be valid, exactly
at expiry or expired: manual handling does not dispatch its commands. Decision
time must be timezone-aware and no earlier than the review or preview issuance.

## Atomic result and final checks

One fenced transaction records the HUMAN decision, its PRIMARY review binding,
OUTCOME work/claim/event, the original idempotent receipt and retention refs,
the MANUAL_HANDLED outcome, SERVICE notification body/audit/binding and one
stable unclaimed PENDING notification work item. When present, exactly the
proved preview tail is consumed at the decision time, with both decision and
notification audits bound to that preview. The case version increments once;
input, generation and proposal versions and retained proposal/review refs stay
unchanged. Current preview and approval pointers are cleared. The case stops
at NOTIFICATION_PENDING; no message is sent.

The Domain consumer independently validates the source and keeps the original
state, request, source and preview context before the transition. Its commit
check proves the accepted manual fact, repeats current input/order provenance,
then verifies current Founder/OUTCOME authority, original claim/epoch/lease,
state and small retained rows. The outer service separately repeats the proof
and checks its original acceptance/receipt. Neither layer renews or substitutes
the original lease. A failed check rolls the complete business transaction back.

## Replay, retention and ambiguity

Historical family selection uses the original DECISION PRIMARY binding, not
the current head. Replay proves the original decision, HUMAN audit, OUTCOME
work/event, full review/proposal, unique consumed preview and replacement chain,
original SERVICE notification body/binding/audit and stable notification work.
The original notification is located through its outcome work and immutable
target, so later lawful notification transitions do not invalidate the original
receipt. Initial acceptance alone requires the notification work to be PENDING,
epoch zero, with no claim, claimed version, lease or authority revision.

Service replay cross-binds original request/key, actor, reason, proposal/version,
expected pre-version, acceptance identity, event and receipt version/time.
Direct accepted OutcomeAccepted replay independently proves the same original
history and rechecks current actor/authority and retained row seals.
Erased bodies or receipts cannot be rebuilt. UNKNOWN remains unknown without
an automatic business retry or replacement key; recovery with no acceptance
record stays UNKNOWN. A definite denial closes the old transaction before the
existing fresh, currently authorized denial-audit transaction.

## Preserved boundaries and verification

The existing 0009 schema is reused. No migration, new purpose, capability grant,
public route, default producer, APPROVAL, EXECUTION, provider/model call, return,
label or notification sender is introduced. Frozen DTOs, operation/key
fingerprints, event/target/hash kinds and exact 0007 metadata remain unchanged.
The original ESCALATE and no-proposal flows remain regression requirements.

Implementation is prepared under the explicit local PostgreSQL/Docker/migration
pause. AST/import/collection checks are offline evidence only. The new scenarios
cover both PASS outcomes, preview chains and consumption, source corruption,
direct Domain bypass, final authority/source/lease checks, original replay,
UNKNOWN, rollback, retention, observed competing backends and installed private
calls. Their preparation is not a passed PostgreSQL result. Disposable cloud
CI, independent source review and exact source/run evidence are recorded
separately by the task; historical test totals are not recounted as new tests.
