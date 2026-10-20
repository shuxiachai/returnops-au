# Private simulated label execution (N3)

This local component starts from the retained `RETURN_SOURCE` bridge and records
one independent SQL mock label fact. A confirmed label remains `EXECUTING`
without an `OperationResult`: its PDF has not been retrieved or stored. A unique,
unclaimed artifact-only intent is saved in the same Domain confirmation
transaction. No artifact worker is registered here.

The fixed owners remain A Jingbo Chai, B Chengsi Li and C Yuwei Tao. Controlled
synthetic service/storage tests do not constitute C review, carrier execution,
personal or joint acceptance, or completion of the whole WBS. There is no HTTP
entry, startup dispatch, real model, carrier, notification sender or external
publication in this change.

## Private entry and original authority

`compose_private_label_execution` exposes `execute_accepted_label(case_id,
expected_case_version, execution_work_id, original_approval_key, correlation_id)`
and `reconcile_label(case_id, execution_work_id, original_approval_key,
correlation_id)`. Neither accepts a command, permission, provider return ID,
effect key, result or claim. The approved label command and the confirmed return
identity are read from the actual saved chain.

Creation independently requires current F.03 Founder/session/case scope, label
`EXECUTION` and `EFFECT`, label create/query configuration, and the return
`EFFECT`/query permission needed for bridge provenance. Provider permissions are
explicit fixtures or separately governed configuration; migration and service
composition add no grants. Historical observation requires current label
`EFFECT`/query and original integrity proof. It neither renews an approval nor
requires create permission to observe an already durable fact.

Stable operation/control/effect identities depend only on original execution
work and the fixed `GENERATE_LABEL` slot. The binding covers the complete
approved command, original key/principal, bridge acceptance, successful N2
record/fact, parcel, return identity and exact provider configuration. Altering
those values conflicts; it cannot create a replacement identity. The frozen
command parameters never gain `provider_return_id`.

## Exact source and version rules

Migration `0012_label_execution` requires the exact complete 0011 descriptor and
adds only four tables: `lifecycle_label_execution_controls`,
`label_provider_permissions`, `core_mock_label_ledger`, and
`lifecycle_label_artifact_work`. The runtime requires exact 0012. No previous
table metadata or migration is altered; previous dynamically imported DDL keeps
its behavior. Downgrade requires a separate data/recovery plan. This work permits
only the separately created N3 test database, not migration of an existing DB.

The 0011 return-only whole-case proof remains exact. The explicit 0012 aggregate
validates the original N1/N2 chain, actual bridge work/claim/binding/receipt/audit,
and label control/history/fact/work, then compares the whole OPERATION inventory
and origins with that verified ordered union. Lower readers never call the
aggregate. Extra, orphan, cross-case, duplicate or missing records fail closed.
N3 adds no completed label effect to `lifecycle.effects`; the return effect is
the only existing effect in this component.

Let V be the label reservation's current version, D=V+1 and O the current version
captured at confirmation. V need not forever equal the original bridge version.
The bridge's original claim/binding/pre-version and its accepted post-version
remain unchanged.

| Transaction | Saved result | Business version |
| --- | --- | --- |
| T1 Domain reservation | label v1 PENDING at V, v2 EXECUTING at D, original control | exactly V→D once |
| T2 independent SQL mock | original-identity label fact only | unchanged |
| T3 full confirmation | v3 EXECUTING/no result for success, or typed FAILED for explicit no effect | body stays D; history/audit bind captured O; head version/status/updated_at unchanged |
| T3 after body retention | minimum fact metadata and safe audit, no new operation body or artifact intent | unchanged; history sequence unchanged |
| Confirmed replay | existing observation only | no history/audit/work/attempt growth |

T1 and T3 compare the original complete source snapshot plus an explicit allowed
delta, including head/audit/history fields. They cannot accept a surprise larger
head version by taking another baseline. Session, approval and lease time are
checked after the final slow reads. The independent mock checks a materialized
`clock_timestamp()` in its INSERT together with actual session, owner/store,
current grants/revisions/configuration, original claim and current input/
generation/approval state.

## Uncertainty and retention

Only confirmed T1 commit and connection close release a dispatch ticket. Every
existing reservation is query/replay-only, including a crash before its first
mock call. T1 uncertainty does not call the mock. T2 response loss does not erase
its independent ledger. T3 rollback preserves that ledger for original-identity
query. `NOT_FOUND`, a timeout, an expired claim or UNKNOWN never permits another
business dispatch. Query epochs have finite leases and do not increase attempt
count; a late epoch cannot overwrite its successor.

The artifact table enforces one work per case and per control, a composite
control/case FK, immutable confirmation binding, and only PENDING/PAUSED with
epoch zero and all claim fields NULL. A current eligible success yields PENDING;
historical confirmation with retained bodies but lost eligibility yields PAUSED.
Explicit no-effect failure creates no artifact work. No orphan work is repaired
or replaced.

Input/generation invalidation pauses artifact work and invalidates label query
claims. Actual retention also marks sources unavailable and clears retained-body
availability. A late first confirmation records only minimum safe metadata/audit;
it does not reconstruct commands, OPERATION bodies, PDF bytes or work. Existing
confirmation/work identities survive as retained metadata and PAUSED intent.
Synthetic terminal-state protection fixtures are labelled as such and do not
claim a reachable human workflow or authorize rewriting outcome/notification.

## Local verification packet

The external task evidence directory records exact source freezes, independent
review and real execution separately. Runtime v01's independent static review
found a missing actual N2 origin and an ineffective orphan-ledger predicate;
v02 fixes both and passed independent delta review. The original failed review
round remains recorded. Offline tests and collection are not PostgreSQL proof.

New tests cover twelve groups: exact upgrade/descriptor, full chain and table
deltas, integrity conflicts, independent current authority, each of the 14 T1
writes and 8 successful retained-body T3 writes, commit/close uncertainty,
separate-process fencing, actual DB-time expiry,
query-only recovery, retention, original-chain replay, installed private calls,
and complete relevant regression suites. A generated node map binds each group
and the five design assertions to exact collected node IDs. Old compatibility
fixtures retain their explicit historical revisions. FAILED and minimum retained
confirmation branches have transaction/retention coverage, not an assertion of
separate fault injection at every write. The stale-epoch test uses private
same-process calls and a DB lease change. Separate OS processes cover duplicate
execute/reconcile and restart observation; no crash-kill or cross-process stale
epoch experiment is claimed.

The new label installed child probe receives synthetic authentication through stdin. Its
files contain only safe process/result metadata, never DB URLs or authentication
payloads. They require the dedicated DB name/OID, local endpoint, expected PG
version and isolated schema. If a child remains live after timeout or assertion,
the existing preservation guard saves process/raw-stream metadata and exits the
pytest child before fixture teardown can drop the still-used schema.

PDF retrieval/rendering/storage, `label_evidence_id`, label `SUCCEEDED` result,
final outcome and notification belong to later components. They are not
implemented or claimed by this packet.
