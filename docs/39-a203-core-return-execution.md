# A2.03 one core SQL mock return execution

This private component continues the actual retained [N1 preparation](38-a203-execution-preparation.md)
through one core SQL mock `CREATE_RETURN` and a durable Domain result. Its
technical issue is [Issue 75](https://github.com/shuxiachai/returnops-au/issues/75),
under the existing KAN-15 mapping. Owner A remains Jingbo Chai and designated
human reviewer C remains Yuwei Tao. No member, original predecessor, joint,
whole A2.03/A2.04 or Gate1 acceptance is inferred from code or CI.

The 14 October 2026 human grant permits this bounded isolated implementation,
normal push and Draft/cloud validation, including a limited start while the
actual adopted-main run 38484911606 was still running. A failed baseline run
stops dependent implementation for diagnosis. Running metadata is not a PASS.
Ready/merge, local DB/Docker, Jira/permission changes and teammate messages are
outside this grant. Original nine features, 89 WBS fields and S/F are unchanged.

## Private entry and identity

`compose_private_return_execution` is unregistered. No HTTP execution route,
default producer, label, artifact, outcome, notification, sender, model or
external/A3 adapter is introduced. The core mock is an actual SQL implementation
of the simulated return, not an external provider substitution.

`execute_prepared_create_return` takes the existing case/version/execution work,
original approval key, complete candidate command and correlation ID. Domain
reloads the complete retained approval/preparation and exact server-owned
command; supplied parameters, provider and original key must match. Stable
preparation/operation/effect key/fingerprint algorithms remain unchanged.
The original A2.02 work remains unclaimed and its N1 first operation remains
version1/attempt1. A separate control row owns dispatch and query claims.

`reconcile_create_return` accepts only the original case/work/key/correlation.
It cannot supply a replacement command, fingerprint, provider result or key.
Committed `EXECUTING`, including a crash before the mock call, is query/manual
only. `NOT_FOUND`, timeout and uncertain commit never authorize redispatch.
Query epochs do not increment the business attempt count. Expired old query
workers cannot overwrite a later claim.

The private results distinguish `COMMITTED`, `REPLAYED`, `IN_PROGRESS`,
`DENIED`, `UNKNOWN`, and retention-only `FACT_RECORDED`/`FACT_REPLAYED`.
`DENIED` describes the guarded entry/acceptance phase; it is not a claim that an
already existing reservation has no provider effect. `UNKNOWN` never promises
a persisted UNKNOWN marker. Identity information is returned only after its
current authorization/proof and confirmed transaction/close.

Every read-only observation, including known result/fact replay, `IN_PROGRESS`
and missing-result `UNKNOWN`, shares a final guard under its original fence.
It freshly checks F.03, signed-session registry bounds, current EFFECT/query
grants and exact source/control/ledger rows. Strict DB time is sampled after
the last potentially slow proof/ledger read. A session that expires during
that read cannot receive a successful fact response. Commit and context close
must both complete; an uncertain outcome remains `UNKNOWN`. Existing execute
replay is query-only and needs neither renewed create permission nor a renewed
historical approval window.

## Three transactions and the effect boundary

1. T1 runs under the existing cross-process exclusive fence. It checks current
   F.03 Founder/case/owner eligibility, Operations EXECUTION and EFFECT grants,
   provider create and query permissions, complete current approval/source and
   strict dates. Both permission paths are rechecked before its commit. It
   saves the immutable control, version2 `EXECUTING` history/audit and
   `ACTION_IN_PROGRESS`. T1 commit and connection close must both be confirmed
   before the mock is called.
2. T2 opens its own transaction and then acquires that same fence. It reloads
   the original control/claim and complete source proof and current authority.
   The actual ledger INSERT contains a materialized DB wall-clock sample and
   predicates for the original deadline, live session dates/revocation,
   Founder/owner, current EXECUTION/provider permission revision/configuration,
   original control epoch and current case/generation. This guarded INSERT is
   the core SQL mock acceptance point. The only T2 writes are ledger writes;
   its ledger has no Domain FK. The hash is finalized in this same transaction
   before commit. A known no-effect failure is a typed failed ledger fact,
   never permission for another attempt.
3. After T2 closes, T3 freshly checks F.03, EFFECT/query permission, original
   provenance, durable ledger hash and current dispatch/query claim. It
   atomically saves version3 typed `OperationAttempt`, audit, effect reference
   and control result. A T3 rollback cannot erase a committed T2 effect.
   Success stops the operation at `SUCCEEDED`; the case remains
   `ACTION_IN_PROGRESS` and the label/outcome/notification remain incomplete.

There is never a Domain transaction holding the fence while another connection
tries to acquire it. Supported registry/source/configuration changes use the
same fence. This does not claim atomic authorization of an external provider or
protection against a DBA bypassing the trusted adapters.

## Explicit 0011 and compatibility

`0011_return_execution` requires the exact complete 0010 schema and adds only
three tables: `lifecycle_return_execution_controls`,
`return_provider_permissions`, and `core_mock_return_ledger`. It creates no
grant, backfill, command-body copy or old-table alteration. Exact columns,
nullability/defaults/collations, primary/unique keys, CHECK expressions, immediate foreign
keys and indexes are checked without caching. Partial, extra or counterfeit
descriptors fail closed. Old 0007–0010 migration bytes and metadata remain.

The original strict N1 verifier continues to reject later OPERATION/effect
rows. Only an explicit 0011 continuation reader validates the immutable N1
root, exact dispatch/result chain, audit bindings, control and ledger. N1's
0011 historical replay uses that reader when a control exists; it grants no
dispatch permit. Original approval replay retains its unclaimed-intent rule.
Legacy EFFECT dispatch proof and its compatibility tests are not rewritten as
modern N2 execution evidence. Application readiness requires exact 0011.

Provider create/query permissions are separate current grants. Migrations and
composition provision neither. Cloud fixtures explicitly provision synthetic
permissions; that is not a production permission change.

## Retention, invalidation and known facts

Actual retention marks N2 source/result content unavailable, invalidates query
epochs, and keeps original identity/hash records. It never restores PENDING or
erased bodies. Invalidation prevents new effects through the generation/claim
checks. Historical query may outlive natural approval expiry, but still needs
current F.03/case/EFFECT/query permission.

After bodies have been purged, a successful original ledger may be recorded
only as a minimal control confirmation and one
`RETURN_EFFECT_CONFIRMED_RETAINED` safe audit. Its payload binds preparation,
operation, control binding, ledger hash, provider operation identity and typed
effect status, explicitly with `content_available=false`. It refers to the
existing dispatch metadata without becoming a second OPERATION origin.
There is no command, `OperationAttempt` or `OperationResult` reconstruction,
new history/encoding/effect row, or replacement result pointer. A provider fact
known under retention is distinct from a materialized complete OperationResult.

If a full result existed before retention, its original result/audit/effect
references remain exact tombstones. Replay verifies raw-body absence, retained
hashes and the same ledger/audit binding. Existing outcome, notification and
terminal state are not advanced or replaced. Only current authorized first
confirmation may add its safe audit and control metadata.

Rollback means stopping this private entry while retaining compatible 0011
readers, recovery and data. No automatic downgrade, deletion of ledger facts or
0010 binary over an 0011 database is supported.

## Validation boundaries

Local DB/Docker remain paused. Local static/import/offline results and collected
PostgreSQL nodes are recorded separately. Collection is not executed persistence,
concurrency, migration or installed-process evidence. Actual cloud validation,
exact source/checkout/PG metadata, raw logs and independent review are required
before claiming those results. This source document makes no cloud PASS claim.

| Group | Required evidence | Authored test entrance |
| --- | --- | --- |
| G1 | Real empty/retained0010 upgrade, exact descriptors, old approval/N1 replay | `test_create_return_execution_postgresql.py` |
| G2 | Actual full retained chain → SQL mock → typed Domain result | `test_create_return_execution_postgresql.py` |
| G3 | Role/store/key/source/time/config/permission denials, zero effects | PostgreSQL and offline files |
| G4 | T1 uncertainty never calls mock; T2 durable effect survives T3 rollback; every Domain write fault | `test_create_return_execution_postgresql.py` |
| G5 | Two actual OS processes and observed PostgreSQL advisory waiters, changed parameters | `test_create_return_execution_process_postgresql.py` |
| G6 | Installed wheel bytes, PENDING restart, pre-call crash, effect-before-result crash | process file and installed probe |
| G7 | Real fence orders, actual INSERT DB-clock deadline, final observation session expiry and revocation, lock/connection failure | `test_create_return_execution_late_postgresql.py` |
| G8 | Original identity query, stale epochs, typed no-effect, genuine approval expiry | PostgreSQL and late files |
| G9 | Actual retention, no reconstruction, current permission, late workers, atomic minimal confirmation | `test_create_return_execution_late_postgresql.py` |
| G10 | Ledger-only T2 full-table delta, no other effects/routes, unchanged legacy contract boundaries | PostgreSQL, offline and existing regression suites |

The exact G1–G10 node inventory and source snapshots belong to the task evidence
directory. Repeated runs, collection, subset tests and combined/step log copies
are not added as distinct coverage. Existing failure histories are preserved.

The terminal/outcome/notification preservation fixture is explicitly synthetic
metadata seeded after the actual N2 chain and real retention. It tests that a
historical query does not overwrite protected state; it does not claim a real
post-APPROVE manual transition, HUMAN acceptance or notification delivery.
