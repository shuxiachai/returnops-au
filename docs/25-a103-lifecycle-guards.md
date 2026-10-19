# A1.03 persisted lifecycle guard component

Delivery: [KAN-14](https://lucastaooo.atlassian.net/browse/KAN-14),
[Issue31](https://github.com/shuxiachai/returnops-au/issues/31). Owner A Jingbo Chai;
designated human Reviewer C Yuwei Tao. Trace: A1.03 in docs/08, FR-001/003/006/008/009/010/011/012,
NFR-001/003/004/006/008/009, docs/09 sections6–8, Domain/state class models and the
recovery/notification sequence. The Jira mapping is historical evidence.

This delivery is a deterministic component plus the two existing input-entry
hooks. It does not register future proposal, review, decision, approval,
operation or notification producers. Tests stage explicitly synthetic saved
sources; no Risk service, Founder decision HTTP endpoint, provider or message
sender is implemented or exercised. Component tests are not A2 consumer evidence,
human review, acceptance of the original predecessors, whole A1.03 acceptance,
or permission to start A1.05 integration. Original WBS/Owner/S–F gates remain.

## Internal boundary

`LifecycleGuards` accepts typed references from `lifecycle_events.py`, never a
requested status. The caller owns one `CustomerUnitOfWork(write=True)` and stages
source history, its exact original audit, and limited causal source bindings on
that same transaction. `prepare` and `claim` create only internal target/lease
metadata. No application composition polls or invokes them. Migration0007 starts
with no lifecycle authorities; capability is scoped by store, component and event
purpose. There is no public provision/attach-source API.

The gate reads complete source DTOs through the existing ten-kind Founder proof:
record/kind/object/version, same case, complete body digest/profile, unique origin,
audit chain, recorded time and exact history references. The existing finite-v2
codec remains unchanged. These proofs establish saved causality; current authority
also requires case owner/store, present principal role/enabled state, the configured
service capability, input, generation and exact current target. Saved model metadata
never grants capability. Saved HUMAN decisions must match their Founder principal.

Making a proposal current also compares its complete necessary statements with the
real original/clarification records, and every attachment with current BOUND
same-case/store/owner metadata and actual byte hash/size. It verifies the current
accepted order projection back to its original receipt/work/claim and durably pins
that projection ID on the proposal source binding. The bundle's current-input order
context preserves every original result field, including message and snapshot, and
maps only the copied input version to current m; the source receipt stays n and its
accepted projection stays n+1 <= m. It does not claim another provider lookup at m.
Citation IDs/version/hash/location/content must match the complete saved retrieval;
conflicts remain intact. These are source consistency checks, not C2 support judgment.

The existing exclusive transaction fence remains held through commit. Authority,
owner and causal human rows are additionally locked `FOR UPDATE`; even a direct
concurrent update must serialize on those rows. Private UoW commit callbacks recheck
lease, current capability, current case/input/generation and saved source integrity
immediately before committing. A failed guard or callback poisons the complete UoW.
The caller cannot catch a rejection and commit previously staged source mutations.
Safe denial auditing must use a separately reauthorized transaction after rollback.

## Current references and invalidation

Independent migration `0007_lifecycle_guards` creates six empty metadata tables:
current references/generation, purpose capabilities, durable work/claims, limited
source bindings, immutable event receipts and historical effect references. They
hold IDs, typed state and hashes, not copies of messages or proposal bodies.
`case_heads` remains the status/case/input authority; old migrations0002–0006 and
`customer_tables` are unchanged. There is no latest-history backfill, old-work
backfill, preview producer or copied preview body. The preview pointer stays empty
in this component; generation is available to a later real preview producer.

Actual clarification and newly accepted order facts call invalidation inside
their original transaction. Input and generation each increase once; current
proposal/review/preview/unexecuted approval refs clear and old lifecycle work/claims
become superseded. The currently accepting intake/order work is a different table
and is not superseded by its own result. Original order receipts stay on source
input n; accepted order projection remains n+1. Replaying the original observation
or an already accepted snapshot does not repeatedly increment input/generation.

Accepted complete proposals advance the persistent proposal counter. Current
REVISE reviews and legal REQUEST_REVISION decisions return to POLICY_ASSESSMENT,
increment generation and clear current analysis refs while leaving input unchanged.
Old same-input claims cannot restore old refs. A current failure/block without a
proposal can only take its frozen manual path, not revision/restart. Source-event
acceptance is unique independently of generation, and exact receipt replay occurs
before new-generation checks after current authorization.
The already verified work accepting the revision preserves its original claim,
epoch and pre-transition generation; the invalidator only supersedes other work.

## Outcome, notification and historical effect rules

A saved REJECT/MANUAL_HANDLING decision and its initial PENDING notification are
bound atomically to one outcome and a stable PENDING work ID/internal key. Later
prepare only reuses that intent. An unclaimed notification work has no authority
revision; its first real claim binds the current NOTIFICATION capability, and an
absent grant never borrows OUTCOME permission. The notification ID, outcome, message and next
steps are hashed and frozen. Notification work retries keep their original work ID;
claim epoch is separate from DTO delivery `attempt_count`. PENDING and FAILED remain
distinct, and only a saved matching SENT revision selects REJECTED, MANUAL_HANDLED
or COMPLETED. FAILED must first save the PENDING retry before SENT. Notification binding is internal; the public NotificationRecord gains
no input-version field. An unrelated historical effect case-version increment does
not revoke a current notification claim.

RETURN_CREATED additionally requires the current execution branch's same proposal,
review and saved exact approval. The original approval/decision/review/proposal
chain, restricted ASCII/integer JSON scope/operation fingerprints, ordered command
links and parcel are checked. Both latest saved typed return/label successes are
required, with no contradictory unresolved or additional successful effect. Label
evidence must match the original causal artifact ID/hash and pass the existing
bounded PDF validator. An arbitrary same-case uploaded PDF is not a label receipt.
The original dispatch proof binds its work/claim/generation/authority revision;
approval expiry is compared with that original dispatch, not a later observation.

Historical effect observations may update saved effect facts and audit. Once manual
or rejected outcome is accepted, they cannot replace it, reopen its status or create
a replacement notification, including while that notification is PENDING or FAILED.
This package verifies explicit synthetic pre-existing dispatch facts; it does not
authorize or execute a dispatch. Tests clearly label future A2 starting conditions.

Retention removes derivative future history bodies atomically, clears current refs,
pauses active work with a new epoch and retains identity/digests/terminal facts and
event deduplication. Future late observations cannot restore deleted bodies. Founder
reads use validated current refs without initializing lifecycle rows; all four GETs
remain business-metadata read-only.

## Verification and operation

Use a guarded disposable PostgreSQL17 database and the locked environment:

```text
python -B tools/checks/run.py environment
python -B -m pytest tests/security tests/orders -q
python -B tools/checks/run.py offline --baseline-ref <verified-main>
python -B tools/checks/check-installed.py
```

The environment runner now includes `tests/lifecycle`. Its private producers stage
future sources in isolated generated schemas and exercise actual component/CAS/
audit/commit effects. Migration coverage upgrades real0006 intake/order records,
checks exact old-table fingerprints, repeats upgrade and requires all six sidecars
to remain empty. Existing older-migration tests remain meaningful: only explicitly
recognized0003–0006 schemas with *none* of the new tables can use old input behavior.
A partial schema, unknown revision or missing0007 table fails closed. Runtime
readiness requires0007.

Installed wheel/image probes verify packaging/composition and six-table metadata;
they do not claim container database execution or actual default-CMD lifecycle
events. Actual test counts and source hashes belong to the delivery evidence.
Stopping adoption disables future component callers and preserves data; no downgrade,
table drop, old-state rewrite or notification resend is an automatic recovery step.
