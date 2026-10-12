# A2.01 private Founder revision of an accepted proposal

## PASS extension candidate — 12 October 2026

Technical tracking: [Issue 62](https://github.com/shuxiachai/returnops-au/issues/62),
existing Jira [KAN-15](https://lucastaooo.atlassian.net/browse/KAN-15).
The current bounded extension accepts an actual retained PASS or
PASS_WITH_WARNING proposal at AWAITING_APPROVAL through the same private
REQUEST_REVISION service. The explicit component start exception covers this
implementation, independent technical review and Draft cloud CI; it does not
authorize Ready/merge or establish original F.01, human C, joint, whole A2.01
or Gate 1 acceptance. Owner A Jingbo Chai, designated human Reviewer C Yuwei
Tao, S=F.01 and F=A1.03,F.03 remain fixed. This maps to FR-009/010/011,
NFR-002/004/009 and UC-03/04 under the existing A model chain.

No preview, valid preview, expiry equality and already expired preview are
supported. An existing preview must be the current exact-version tail of a
complete accepted chain, including every legitimate expired replacement. Only
that tail is consumed by the new decision, with consumed_at equal to its
recorded time and the REVISION event acceptance time. Its HUMAN audit binds
the preview ID, body hash and original preview audit hash. An expired preview
does not authorize approval, but does not prevent a request to revise. A time
before preview issuance or a naive time is rejected.

The frozen request, private composition and accept/recover signatures do not
change. Preview identity is server-derived; callers cannot supply preview ID,
scope, fingerprint, actor or risk outcome. Current HUMAN/F.03 and REVISION
authority are required; PREVIEW/APPROVAL and historical producer permissions
are not borrowed or required. No new grant, migration, default producer,
public route, model invocation, approval, execution, outcome or notification
is introduced. PASS-state MANUAL_HANDLING remains separate future work.

Both the service and modern Domain HUMAN revision require a durable accepted
review event: REVIEW chooses the existing ESCALATE proof; REVIEW_PASS chooses
the full PASS proof. Missing review/state cannot enter the legacy generic
path, and a failed verifier never falls back to the other family. The original
REVISION target hash retains its existing fields. Exact claim version, full
preview chain, unique consumer and audit prove the preview identity separately.

The single fenced write transaction saves the decision, history/encoding,
HUMAN audit, PRIMARY binding to the original review, optional preview
consumption, REVISION acceptance, SERVICE audit and original receipt. It
stops at POLICY_ASSESSMENT: case version and generation each increase once;
input and proposal versions stay; current proposal/review/preview/approval
refs clear. Other unfinished work is SUPERSEDED under the existing invalidate
rules. Historical records and completed work remain, and no follow-up work
or effect is produced.

Commit checks prove the accepted revision and then repeat current retained
input/order verification with server-saved original refs. They subsequently
check current authority, the original claim/epoch/lease, head/state, bindings,
events, preview seals and acceptance/receipt rows. Direct Domain calls prove
persisted HUMAN provenance and the current principal/service capability;
browser-session verification belongs to the private service. Domain accepted
event replay also verifies the complete historical revision proof.

Replay binds the original key and request fingerprint to the saved decision's
proposal ID/version/reason, actor and exact event pre-version, and binds the
receipt identity/version/time to that event and acceptance. It rechecks the
saved acceptance and available receipt after expensive proof reads. Later
generations do not invalidate a retained old fact; erasure does. UNKNOWN,
fresh-authority denial audit and retention keep their existing boundaries.
Safe rollback after new PASS facts exist must retain the new historical
reader/recovery while disabling new admission; deleting facts or blindly
reverting to the earlier runtime is not a safe rollback.

Prepared cloud PostgreSQL coverage is RVP01–RVP08 in
[the primary suite](../tests/lifecycle/test_founder_pass_revision_postgresql.py)
and [the late-check and race suite](../tests/lifecycle/test_founder_pass_revision_late_postgresql.py):
real six-path acceptance and multi-replacement chains; current-source and
low-level negatives; preview/target validation; final authorities and original
lease; exact replay, rollback, UNKNOWN and denial; two-backend observed fence
races; retention/read projections; installed outside-checkout invocation and
legacy regressions. Prepared or collected nodes are not passed tests. The
local database/Docker pause remains in force; exact source and actual cloud
execution evidence must be recorded separately. The older local counts below
describe the original ESCALATE delivery only.

## Original ESCALATE delivery record

Owner A Jingbo Chai; designated human Reviewer C Yuwei Tao. Original S=F.01 and F=A1.03,F.03 remain unchanged. This component maps to existing Jira KAN-15 and technical Issue 48. The leader authorized the exact local implementation and dedicated synthetic PostgreSQL 0008 verification on 7 October 2026, with this component's limited F.01 start exception. It does not establish predecessor, member, joint, whole A2.01 or Gate 1 acceptance.

## Private entry and stop point

`compose_private_revision(engine, auth_config, authorization)` composes `FounderRevisionService.accept(case_id, FounderDecisionRequest, original_key, correlation_id)` and `recover(case_id, FounderDecisionRequest, original_key)`. The frozen DTO is unchanged. Only REQUEST_REVISION with the exact current proposal id/version, expected case version and reason is accepted. The actual request authorization supplies the Founder identity. No actor, grant, review or generation is accepted from the body.

A new intent requires current ESCALATED state and a complete actual accepted fixed proposal plus the accepted controlled synthetic ESCALATE review. Current HUMAN F.03 `recordFounderDecision` and an independently pre-provisioned `founder-revision-v1` REVISION capability must both hold. The factory and service never provision grants and cannot borrow REVIEW or OUTCOME capability.

The transaction creates the HUMAN decision with its causal audit, PRIMARY binding to the accepted review, an existing REVISION work/claim and `RevisionRequested` event, and the original-key DecisionReceipt. It increments case version and generation exactly once, preserves input version, clears old current proposal/review and invalidates unfinished older work while retaining completed work, immutable history and original acceptance facts. It stops at POLICY_ASSESSMENT; it creates no next proposal, outcome, notification or execution work.

The outer service and modern ESCALATED low-level guard independently verify the complete retained review/proposal/input/order chain and actual work/claim/audit/binding/event receipts. At final commit checks, server-derived original state references allow a fresh full current-source verification after invalidation has cleared the current pointers. A historical `current=False` read alone is insufficient for this check. After the expensive source reads, the service rechecks current HUMAN and REVISION authority, final head/state and the original claim/epoch/lease without renewal or replacement.

## Idempotency and recovery

The operation remains `recordFounderDecision`; revision uses a separate request fingerprint domain while preserving the existing manual fingerprint. Reusing one key across different decisions conflicts. An exact replay returns the original stored historical receipt even after an explicitly separate caller advances the generation. Replay checks the accepted revision's work, exact target fingerprint, decision binding, accepted review, event fingerprint and causal audit. It never manufactures a receipt from current state.

An ambiguous commit returns UNKNOWN and never automatically retries, replaces the key or records a rejection. `recover` uses a fresh fence and current authority to query the original receipt; mere absence stays UNKNOWN. Only an independently known actual rollback permits a caller's explicit same-key attempt. Deterministic rejection exits the original UoW before a fresh independently authorized bounded denial audit. Missing current authority records no case denial audit; an ambiguous audit commit remains UNKNOWN.

Retention erases derivative decision/proposal/review bodies and separately erasable original receipts without reconstructing them. Founder GET and history retain their existing current/history semantics and do not advance business state.

## Verification scope

Eight acceptance groups: REV-01 actual proposal→accepted review→new Founder revision; REV-02 source/current authority/final claim and low-level bypass negatives; REV-03 original-key replay and conflicts; REV-04 independent-process same-key competition, both manual/revision serial orders and old-claim invalidation; REV-05 every-write rollback, final failures, UNKNOWN and fresh denial; REV-06 retention and read-only current/history; REV-07 exact wheel-installed outside-checkout service execution and zero effect counters; REV-08 modern and explicitly old 0007 regressions.

`tests/lifecycle/test_founder_revision_postgresql.py` is the new service suite. `revision_helpers.py` and `revision_process_probe.py` are test-only, excluded from the wheel. Existing `test_proposal_manual_postgresql.accepted_revision` remains an explicitly synthetic direct-guard fixture; its modern ESCALATED PRIMARY binding now targets the accepted review. It is not renamed or claimed as the new Founder entry. The existing monotonic revision guard positive retains all assertions and now explicitly covers both 0007 and head.

## Verified local execution

Local QA ran on 7 October 2026. This document records the completed local verification and database closeout as of 8 October 2026 (Australia/Sydney).

| Suite | Actual passing nodes |
| --- | ---: |
| Lifecycle | 591 |
| Security | 244 |
| Storage | 74 |
| Environment | 32 |
| Customer | 153 |
| Orders | 64 |
| Investigation | 41 |
| Founder | 158 |
| **Distinct union** | **1,357** |

All 4,071 setup, call and teardown reports passed, with no failed, skipped or xfailed node in these final eight runs. The targeted revision suite's 112 nodes and the first positive node overlap the lifecycle suite and are not added to this union. REV-01 through REV-07 map to the 112 new nodes; REV-08 maps separately to 12 passing nodes in the full lifecycle run. `StarletteDeprecationWarning` and `DeprecationWarning` are two existing dependency warning types, each displayed in the environment, customer and Founder runs: six displays in total.

The first targeted run stopped before retention processing because its upload fixture used a six-character idempotency key. That run had 99 passing nodes, one failed node and 12 unexecuted nodes. Only the fixture's key literal was corrected to meet the frozen minimum length of eight; the schema, every assertion and all runtime modules stayed unchanged. The corrected 112-node run and the eight final suites passed. The earlier failure remains recorded: its stdout was saved only after one actual credential substitution, while its stderr remained an original stream with zero substitutions. The successful final suites had zero credential substitutions in their recorded process streams. This does not relabel the failed run as a pass or add its overlapping prefix to the final count.

Two actual wheel-installed child calls outside the checkout accepted the new revision entry, once in the targeted run and once in the full lifecycle run. Each made exactly one REVISION claim, preserved the grant rows and recorded zero RETURN, LABEL, notification-send, LLM, outbound and NOTIFICATION-claim effects. Eight runtime module files are byte-identical across source, installed target and wheel. The test fixture and probe are excluded from the wheel.

Fourteen executed lifecycle nodes have an explicit `0007_lifecycle_guards` parameter: seven late-effect compatibility nodes, three direct-guard compatibility nodes, and four upgrade scenarios that start at 0007 and move to 0008. The extra same-input revision guard parameter retains the original assertions. These are identified compatibility or upgrade executions, not modern new Founder-service acceptance. The new service requires exact `0008_review_escalation`; no migration was added for this component.

The evidence scanner paused on 25 broad Bearer-pattern matches. Independent review identified exactly five checked-in static negative-test node IDs repeated in node lists and phase reports. A restricted reconstruction of literal source expressions, the pre-credential collection, exact JSON fields and whole-artifact hashes proved that classification. There are 25 qualified fields and zero unclassified matches; this is not a blanket claim of zero pattern matches. The original evidence-only guard stop and all original artifacts remain preserved.

## Dedicated database closeout

Only the new dedicated synthetic database was initialized and used: `returnops_f02_a201_founder_revision_20261007`, OID 3112961, PostgreSQL 17.11, head `0008_review_escalation`. Its independently recorded pre-test state had 47 public tables, one Alembic row and all 46 business tables empty. No existing project database was migrated.

The post-test read-only inventory found five proven storage-fixture bundles across three tables, 15 rows in total. The two identical default bundles are attributable jointly to the repeat-migration and ACK-true cases; their individual UUID-to-node association was not recorded. This limitation remains even though the exact row sets and payloads were verified.

After a separate explicit human authorization, cleanup was limited to those 15 exact fixture rows. One earlier approval rejection and one actual pre-commit cleanup failure remain recorded. In the failed attempt, inspecting rowcount after result closure produced `-1`; no COMMIT was attempted. A fresh read-only check independently confirmed that the original 15 rows remained. The bounded correction preserved the DBAPI counts before closure and retained all checks. The corrected execution matched five exact `DELETE RETURNING` IDs and a preserved count of five in each table, then completed the only COMMIT attempt with an acknowledgment.

A fresh, distinct read-only connection subsequently verified the retained database: 47 public tables, 70 indexes, one Alembic row, all 46 business tables empty, exact 0008 structure and no extra test schemas. The cleanup and this final seal received independent review. This is a point-in-time observation of the dedicated database; it does not imply permanent health or volume integrity. Implementation QA and cleanup SQL are stopped. UNKNOWN remains distinct from proof of rollback; the observed failed cleanup was resolved using its separate zero-COMMIT evidence and fresh database read.

## Evidence layers and delivery boundary

The immutable initial database proof refers to source-v1. Successful tests refer to source-v2, whose only change from v1 is the fixture key. The installed wheel contains the unchanged runtime, so it was not rebuilt for that test-only correction. This final document-only update changes neither the tested runtime nor its tests.

Local task artifacts are under `tmp/a201-founder-revision-20261007`; these code-literal locators are provenance references, not required repository-file links:

- Initial source-v1 manifest SHA256: `97174a00b0c555faf28a4e9d20e2737e71d4b8cc3e8bfa0387d554a0fc7ab0d8`.
- Tested source-v2 manifest SHA256: `470d442a8ff37f721d3401f5d26b6c04b3c5d69d2370a00c2b5a018876324b1f`.
- Full local QA receipt, `implementation/pg-completion/receipt.json`, SHA256: `5ba6e304cf898f3b1631f2de4e504d8e3900556bda9929a4cd95d1a090892651`.
- Runtime wheel SHA256: `bfef2264478271424a035a4d3ed7bd889fdd59a7442d805615b9079f5dc25843`.
- Corrected cleanup execution receipt SHA256: `1ed1e7362fdee9017c000554f0c038013a82e9bfab5175f45bcb92aedb9edc0f`; commit receipt SHA256: `2422a10ceb5bc0b79dbbf1159464a60c4746b4560ea278f98944f2dbe7cb40ff`.
- Independent final database seal SHA256: `80859ceea5beb051fd9aeb1a5ff5cf3a396b9f6729685410d526c036917bcbea`.

Failure and helper histories are retained at their actual layers. The original QA report's root-helper count of three is historical; the later root ledger records four, with one separate coordination-capacity failure. Author, environment, handoff-helper and reviewer records remain separate, including the environment codec failure and resolved static findings. None is recast as a new business-test failure or erased by the corrected successful runs.

This is local verification of a private component. It is not cloud CI, a real C/model producer, publication or human acceptance. The original scope-specific Owner/C, predecessor and joint acceptance records remain pending within the inspected evidence scope; existing human records retain their original scope. Owner A Jingbo Chai, designated human Reviewer C Yuwei Tao, S = F.01 and F = A1.03, F.03 are unchanged. The limited start exception does not accept the whole A2.01 Story or Gate 1.

That original ESCALATE delivery included no AWAITING_APPROVAL service variant, APPROVE/REJECT, real C/model producer, public POST/default producer, automatic next proposal, notification/provider send, source push, PR, Ready or merge. The PASS extension above supersedes only its AWAITING_APPROVAL revision limitation. The original nine features and 89 WBS fields are unchanged. See [proposal manual baseline](31-a201-proposal-manual.md) and [lifecycle guards](25-a103-lifecycle-guards.md).
