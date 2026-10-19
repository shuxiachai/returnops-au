# Private retained return source bridge

This component accepts a successful retained modern core return as the source of a future label step. It stops with a private label context and a distinct `RETURN_SOURCE` receipt. The label operation, label provider, artifact, outcome and notification steps remain unimplemented here.

The scope supports the exact approval and simulated execution rules in [FR-009 and FR-010](00-project-definition-v1.md), with the reconstructable source and audit requirements in FR-011. It is a bounded part of [A2.03/A2.04](08-delivery-work-packages.md), not completion of those work packages, A2.05/A2.06, A3, or the complete return workflow. The original Owner A and designated human Reviewer C responsibilities and prerequisites remain unchanged. AI technical review does not supply a human acceptance signature.

## Private entry and result

`compose_private_return_label_bridge` builds a caller using the existing F.03 current request authority. No public route, default producer, new grant, new purpose, migration or schema field is registered. The implementation uses the existing exact `0011_return_execution` schema.

The private methods are:

- `accept_return_source(case_id, expected_case_version, execution_work_id, original_approval_key, correlation_id)`
- `recover_return_source(case_id, execution_work_id, original_approval_key, correlation_id)`

First acceptance returns `ACCEPTED`; a fully verified existing receipt returns `REPLAYED`. `DENIED` and `UNKNOWN` contain no label context. `DENIED` describes the current entry or disclosure decision and does not prove that an earlier uncertain attempt never committed. Recovery without an existing receipt returns `UNKNOWN` and creates nothing.

The context contains the approved `GenerateLabelCommand` unchanged and a separate `provider_return_id` derived from the retained successful N2 result. It also identifies the parcel, return operation, result record/hash, approval, dispatch and ledger fact. The frozen [v1 command](09-interface-contract-v1.md) does not gain a provider return identifier in its parameters. The actual profile deliberately uses `provider-mock-return` for CREATE_RETURN and `provider-mock-label` for GENERATE_LABEL; their provider strings are not required to match. The earlier offline DTO packet's same-provider simplification was not evidence of this runtime configuration or actual retained source provenance.

## Source, authority and transaction

The reader calls the existing production N1/N2 continued proof, approval admission and current accepted review readers. It verifies the complete retained customer/order/proposal/review/preview/approval and original receipt relationships, the exact three OPERATION versions and their original producers, one preparation/control/ledger/effect relationship, and the successful return result. It does not accept caller-supplied provider truth, a snapshot classifier verdict, an old claim, or a trust flag.

Current F.03 identity, enabled owner/store scope, EFFECT grant and provider query permission are required. New-create permission is not borrowed or required for observing a completed return. Historical approval expiry alone does not turn observation into a new dispatch; current source availability and current authority are still checked. The full real proof is read through `ProofReads` where its existing readers require a UoW, preventing hidden backfill through those readers.

One exclusive fenced transaction creates a new stable EFFECT work item and obtains a genuine current claim. It consumes that work to DONE, inserts a PRIMARY source binding and `RETURN_SOURCE` receipt, appends one explicit acceptance audit and increments the case version once. Status stays `ACTION_IN_PROGRESS`; lifecycle state, original EXECUTION intent, OPERATION history, N1 preparation, N2 control, ledger and effect index are preserved. The receipt points to the original N2 v3 origin audit, not the new acceptance audit. The bridge does not call the generic `EffectObserved` handler or weaken its legacy dispatch rules.

Before writing, the caller captures the actual source rows, performs the full proof and verifies that the seal is unchanged. It derives the permitted post-state from that original seal plus only the specified new rows and head changes. Before commit it repeats the full source and receipt proof, checks the exact permitted delta and current authority, then samples database time after the last potentially slow read for session and lease validity.

The stable identity binds the full case/store/owner/Founder/source/preparation/approval/dispatch/result/ledger/input/generation/original-key relationship. Current case version, session, claim, authority revision, clock and caller correlation are excluded. The caller correlation is syntax-validated observational input; the persisted acceptance correlation is the stable typed event ID. Duplicate acceptance must use the original receipt's pre-acceptance version. Replay validates the historical saved claim independently of a later valid current authority revision.

No context leaves the caller until commit acknowledgment and connection close both complete. An uncertain commit or close returns `UNKNOWN`. There is no automatic acceptance retry, replacement key, claim repair, return replay or label dispatch. Retention or terminal-state protection prevents disclosure while preserving old receipts and the existing N2 historical recovery behavior.

## Validation and evidence boundary

The test upstream uses the actual current production N1/N2 services with controlled synthetic customer, proposal and review input. It is not real C/model input or original human joint acceptance. PostgreSQL tests require a separately approved new dedicated local database; collection and offline boundary tests do not execute them.

| Group | Test responsibility |
| --- | --- |
| G1 | Actual retained source acceptance, precise changed-table set, version/audit increment, unchanged return chain and copied private context. |
| G2 | Missing or damaged retained proposal/review/approval/decision, preview, customer source, order source and original receipt/ref categories. |
| G3 | Extra OPERATION, missing expected v1/body/origin, duplicate origin, wrong N2 producer, cross-bound control and corrupt ledger/effect relationships. Audit-chain validity is checked separately before the bridge attempt. |
| G4 | Wrong key/version/actor/store/owner, revoked session, current EFFECT/query/configuration and create-permission independence. |
| G5 | Genuine database-clock session/lease expiry after the final read; current authority revoked inside the fenced transaction after full proof. |
| G6 | Late source, control, claim, epoch, binding or receipt tampering rejects and rolls back staged writes. |
| G7 | Two actual OS processes observed waiting on the real PG advisory fence; same identity yields one acceptance and replay, changed key/version cannot create another. |
| G8 | Each write boundary, actual uncommitted/committed-but-acknowledgment-lost/close uncertainty, and read-only recovery. |
| G9 | Natural historical approval expiry, current re-enabled authority revision, stable replay and a new installed process recovering the original identity. |
| G10 | Actual retention before/after the bridge, generic EFFECT rejection and explicitly synthetic protective terminal metadata. The latter is not claimed as a reachable human manual-acceptance path. |
| G11 | Installed-wheel source bytes, caller outside checkout, private invocation, default route absence and observed zero provider/label/model/notification calls plus unchanged effect tables. |

The task-local execution receipts bind exact source hashes, raw or explicitly redacted streams, collected nodes, actual outcomes and warning records. They are the authority for which checks have run; this source document does not claim PG acceptance from collection. Process tests stop and preserve owned children and the new test schema on an abnormal timeout rather than killing a child or letting teardown drop a schema it may still use.

Independent source review and actual local PostgreSQL results are required before runtime acceptance. No GitHub Actions, remote publication, original human sign-off, existing database migration, or whole-workflow completion is implied. Rollback disables this private entry while retaining its immutable receipts; it does not delete accepted records, decrement versions, alter N2 facts or downgrade a database.
