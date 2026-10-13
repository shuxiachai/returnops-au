# A2.03 first durable execution preparation

This component records the first `CREATE_RETURN` preparation for an actual,
retained A2.02 approval. It stops with one `OperationAttempt` at `PENDING` and
one identity sidecar. Owner A is Jingbo Chai; designated human reviewer C is
Yuwei Tao. [Technical Issue 73](https://github.com/shuxiachai/returnops-au/issues/73)
uses the existing [KAN-15 Operations/Founder story mapping](https://lucastaooo.atlassian.net/browse/KAN-15).
Jira status is unchanged. This record does not establish original human
acceptance, whole A2.03/A2.04 acceptance or a member's personal contribution.

The 13 October 2026 scoped authorization permits this component to start while
the original acceptance records remain unverified. The original WBS edges
remain A2.03 S=F.01, F=A2.02; A2.04 S=A2.03, F=A1.02. The trace is
FR-009/010/011/012, NFR-002/003/004/006/008 and UC-03/04/05, the exact-scope execution contract in
[docs/09](09-interface-contract-v1.md), and the operation-attempt state model
in [the member-A model chain](12-member-a-model-chain.md). This slice supplies
bounded durable preparation/replay evidence; dispatch and provider at-most-once
claims require later work and separate authorization.

## Private interface and stop

`compose_private_execution_preparation(engine, auth_config, authorization)` is
an unregistered composition. `ExecutionPreparationService.prepare` accepts
`case_id`, `expected_case_version`, `execution_work_id`,
`original_approval_key`, the complete `candidate_command`, and `correlation_id`.
It returns `PREPARED`, `REPLAYED`, `DENIED`, or `UNKNOWN`. Success includes only
the original preparation/operation/history IDs, creation time, and sidecar
state. It returns no command body, effect key or dispatch capability.

The current F.03 Founder session and case authorization and the independent
`founder-approve-v1` `EXECUTION` grant are required. The entry creates no grant.
An earlier A2.02 `CHECKED` result is never consumed as authority. The original
`approved-execution-intent/v1` work remains unclaimed at epoch zero, with no
claim, lease or authority revision. The generic lifecycle EXECUTION consumer
still refuses claims. There is no HTTP route or default producer.

Fresh preparation checks the complete actual retained proposal, PASS review,
server preview, HUMAN approval, original acceptance/key/receipt and references,
full ordered two-command scope, fixed profile, current inputs and strict UTC
approval/session windows. It rejects prior operations, effects and orphan
preparation records or operation audits. It never invokes a provider, creates
a label or effect reference, writes an outcome, or dispatches a notification.

## Identity, transaction and replay

Separate digest domains derive the preparation ID, operation ID, first record
ID and effect key from the original execution work plus `CREATE_RETURN`.
Changed candidate parameters do not generate replacement identities. A
separate request fingerprint must match the original exact command; the
operation fingerprint retains the docs/09 approval/scope/command algorithm.

One transaction under the original exclusive fence inserts exactly five rows:
OPERATION history, finite body, finite encoding, provenance audit and sidecar.
Only `history_sequence + 1`, `audit_sequence + 1` and the new `audit_head` change
on the case head. Case/input versions, status, `updated_at`, all original work,
source bindings, events, receipts and effects stay unchanged. The first local
producer emits object version 1 and attempt count 1; the public legacy count 0
remains valid. There is no result, error or provider operation ID.

The immutable binding payload contains the original work/acceptance, first
operation/body hash, request fingerprint, fixed profile, prepared authority
revision, IDs and creation time. It excludes the audit output and mutable
sidecar state, removing the circular binding. The audit hashes that payload
and binding, refers to the exact history revision, and uses the verified fixed
EXECUTION component. The sidecar then retains its audit event ID. The full
links are read back using a CaseProof built from the post-write head.

Final validation repeats the full retained/current proof, exact raw source
closure and explicit five-row/three-column delta. It rechecks schema,
authority and session dates. The real F.03 `getSession` is the last I/O;
strict UTC time is sampled after it. `PREPARED` is returned only after commit
and connection close both confirm success.

Replay discovers and validates the existing sidecar before the fresh-entry
prior-operation guard. It proves the original acceptance/key, parameters,
operation, body, audit and all retained approval links and returns the original
identity/time/state without any write. Natural approval expiry permits only
historical replay. Current Founder/case and EXECUTION authority remain
mandatory. `recover_preparation` independently confirms a complete original
preparation and never calls creation; absence stays `UNKNOWN`.

Commit or close ambiguity remains `UNKNOWN`, including errors folded by the
unit-of-work final-check mechanism. There is no automatic retry, recovery call
or replacement key. A rollback that leaves no rows is not a durable UNKNOWN
marker and does not prove that a later explicit new call is prevented.

## Schema and retention

`0010_execution_preparation` requires the exact 0009 descriptor and adds only
`lifecycle_execution_preparations`. It adds no old-table columns, grant,
backfill, claim/lease, result or effect ledger. The sidecar contains identities,
hashes and links; no copied command parameter body is retained. Exact columns,
defaults/nullability, keys, immediate no-cascade foreign keys, validated
nondeferred CHECK constraints and index definitions are verified through a
bounded uncached catalog read. The entire original 0009 preview descriptor is
still checked under 0010.

`APPROVAL=0009_preview_approval` and `PREPARATION=0010_execution_preparation`
are explicit versions. Existing approval semantics support both. New N1 and
application readiness require exact 0010. Original 0007/0008/0009 migration
files, frozen metadata, receipt and hash algorithms stay unchanged. A real
0009 approval followed by upgrade and original APPROVE replay is a dedicated
cloud test, separate from empty-schema checks.

Original fenced invalidation marks the sidecar `SUPERSEDED`; retention marks
eligible preparation rows `PAUSED`. Neither restores `PENDING`. Identity/hash
rows survive while normal body, preview and receipt retention applies. Erased
bodies are never reconstructed. Rollback means stopping the new entry and
retaining readers/data; automatic downgrade or deletion is forbidden.

## Evidence boundaries and acceptance map

Local PostgreSQL and Docker remain paused. Local validation executes only
offline tests and collects PostgreSQL nodes, using isolated Python and blocked
database/network connection attempts. Collected tests are not executed proof.
Real migration, persistence, concurrency, fence and installed-caller evidence
must come from a disposable cloud CI database. No existing local database is
migrated by this source change.

| Group | Required evidence | New test location |
| --- | --- | --- |
| G1 | Exact 0010 and forged descriptors; old versions; retained 0009 approval upgrade/replay | `test_execution_preparation_postgresql.py`, offline legacy-count test |
| G2 | Complete source/key/role/scope/profile/current authority; prior operation denial | `test_execution_preparation_postgresql.py` |
| G3 | Exact five-row/head delta; every write rollback; orphan/corrupt sidecar/history/audit | `preparation_helpers.py`, `test_execution_preparation_postgresql.py` |
| G4 | Stable IDs, changed-parameter conflict; sequential and real cross-process dedup | offline and process tests |
| G5 | Original APPROVE/preparation replay; expiry/invalidation/actual retention | persisted and late tests |
| G6 | Commit before/after fault, close ambiguity, independent confirmation only | persisted and offline tests |
| G7 | Final source/authority/schema/session/time mutations; actual fence order | `test_execution_preparation_late_postgresql.py` |
| G8 | Actual installed caller outside checkout, process restart, Founder history/CaseProof | persisted and process tests |
| G9 | Zero provider/label/model/outbound/claim calls; unchanged outcomes/effects/work | full-table delta and installed process counters |

The installed process test records two distinct PostgreSQL backends genuinely
waiting on the original advisory fence before releasing the holder. Two calls
with equal parameters produce one preparation; conflicting parameters cannot
replace it. A third fresh process replays the original durable identity. These
prove preparation deduplication and zero effects, not provider at-most-once
execution. Existing acceptance assertions and CI timeout/configuration remain
unchanged apart from exact new-table/head expectations needed for 0010.
