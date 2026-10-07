# A2.01 private no-proposal manual component

Local candidate for technical Issue [44](https://github.com/shuxiachai/returnops-au/issues/44),
based on main `32ad419d7f0f51e0f390ef80b9b6974cb88270ee`. This document describes
the private component and its verification boundary; it is not whole A2.01 or
Gate1 acceptance. Owner A Jingbo Chai, designated human Reviewer C Yuwei Tao,
S=`F.01` and F=`A1.03,F.03` remain unchanged. The lead's 7 October 2026 limited
implementation exception permits this local candidate to start; scope-specific
human acceptance and the original completion dependencies remain pending.
The primary Jira key is temporarily unverified under that exact exception.
No PR publication, Ready or merge is authorized by this component's implementation.

## Explicit private composition

`returnops_api.private_manual.compose_private_manual(engine, auth_config,
authorization)` composes `FounderDecisionService`. The server supplies its
trusted AuthConfig and actual request authorization. This factory is installed
with the application package but is not called by default application startup,
the worker or any public route. It does not create a grant. The frozen public
decision POST remains unregistered; private results are not public HTTP 202s.

The private call is `accept(case_id, FounderDecisionRequest, original_key,
correlation_id)`. It accepts only `MANUAL_HANDLING` with the frozen
`expected_case_version`, `reason` and one `processing_failure_id` or
`order_lookup_block_id`. It accepts no injected principal, scope, input version,
source version or preview. No new wire DTO is introduced.

Current F.03 `getSession` and **`recordFounderDecision`** authorization derives
the HUMAN Founder/session/store identity. Read authorization is not a decision
permission. A separate existing `founder-manual-v1` SERVICE `OUTCOME` capability
is required. SERVICE provenance never supplies the HUMAN principal. Session,
Founder, case-owner/store and OUTCOME revision are checked on the same actual
fenced connection at entry and again immediately before commit.

## Current accepted target and atomic result

New intent requires `ESCALATED`, no current proposal/review/preview/approval or
outcome, the expected case version, and exactly one current failure or block.
The source must be retained and bound to the current case/input/generation.
For an accepted order block, the original lookup body/hash, receipt, claimed
work, current investigation identity and original accepted input are verified.
For a processing failure, the actual intake, order-failure or fixed-proposal
failure acceptance is verified. Fixed-proposal failures retain their original
lifecycle binding/event and accepted order projection; original input bodies
and capacity proof are checked through the existing source validator.

Intake-origin checks reuse the real intake content validator, including the
original `CustomerCaseView` receipt, case/input/accepted version, principal and
retained source references. Create and clarification acceptances use their
actual audit event type and exact payload hash/reference binding. AuditEvent
stores a payload hash, not raw request text. An available but malformed or
unrelated receipt is not proof of accepted input.

Everything below is written in one exclusive `CustomerUnitOfWork` transaction:

- Necessary OUTCOME prepare and claim, the HUMAN decision and safe causal audit.
- Decision/notification history, source bindings and domain acceptance receipt.
- `MANUAL_HANDLED` outcome, PENDING notification and its stable unclaimed
  NOTIFICATION work and idempotency key.
- The original idempotent decision receipt and its retention references.
- One case-version increment, with input unchanged and status
  `NOTIFICATION_PENDING`. This is not a terminal case.

An input=1 intake/order failure may have no lifecycle sidecar yet. The private
new-intent transaction may initialize the existing 0007 sidecar after authority,
state and version checks; rejection rolls it back. GET, replay and denial
auditing do not initialize it.

All source seals are read again before commit. After potentially expensive
retained-history/attachment/capacity checks finish, the final callback rechecks
the actual HUMAN authorization, original OUTCOME grant, exact accepted work
and original claim/epoch/lease. It never renews or substitutes a lease. Failed
checks poison and roll back the complete original transaction.

## Replay, ambiguity and denial audit

After current authorization, the original key and canonical parameters are
looked up before new-intent state/version guards. The same available original
receipt can replay after later state advance. Changed valid parameters conflict;
a replacement key cannot repeat an accepted intent. Missing or retention-erased
original receipts produce `INVALID_STATE`, without reconstruction. The derived
receipt references all retained statements/evidence so their controlled
retention also erases this receipt copy. Existing Founder GETs remain reads;
their existing cursor/snapshot/encoding metadata writes are allowed.

`accept` returns private `ACCEPTED`, `DENIED` or `UNKNOWN` results. Acceptance
commit UNKNOWN always keeps audit `NOT_ATTEMPTED`; it does not auto-retry,
change key or fabricate a denial. Once the old UoW has closed, `recover` takes a
fresh fence, reauthorizes and queries the original key. A retained actual
acceptance and available original receipt can resolve to ACCEPTED. No record
means UNKNOWN, not proven rollback. Independent actual rollback proof can
justify a new **caller-initiated** same-key/same-parameter `accept` attempt,
which runs all new-intent guards again. Recovery itself never initiates it.

A definite rejection first leaves the original transaction. A separate fresh
UoW may then revalidate current HUMAN and OUTCOME authority and append the
bounded `FOUNDER_MANUAL_DENIED` event. Only audit rows and audit sequence/head
can change in that transaction. Lost authority gives zero case audit and
`NOT_RECORDED`. Audit commit ambiguity is independently `UNKNOWN` and never
auto-retried. No raw exception, SQL, request reason or private token is copied
into an audit event or public result.

## Frozen scope and verification

This component reuses migration `0007_lifecycle_guards`. Public schemas,
OpenAPI, default codecs, existing migrations, locks, nine features and 89 WBS
fixed fields are unchanged. It creates no purpose grants, approval, commands,
execution work, RETURN/LABEL effect, NOTIFICATION claim/send/retry or LLM call.
Future APPROVE, REJECT, revision, preview/Risk, public POST and notification
delivery stages remain separate work. The private factory is integration code,
not an end-user flow or a production producer registration.

`tests/lifecycle/test_manual_postgresql.py` maps the reviewed manual-first
IDs A201-01,02,13,14,15,16,17,18,22,23,24,25,27,28,29,30,32,34 to actual
parameterized tests. Positive ESCALATED targets come from real processor
acceptance entries using explicit synthetic source fixtures. SQL corruption
and forced state changes are labeled negative fixtures, not positive runtime
production. Test evidence includes every physical table, binary-body hashes,
original/current identities, grant preservation, fault-point rollback and
observable effect-boundary counters. Independent process callers exercise the
same original key; injected commit-loss tests distinguish actual commit,
actual rollback and unresolved absence.

Actual local verification on PostgreSQL 17.11 and unchanged 0007:

| Executed scope | Result |
| --- | --- |
| New manual PostgreSQL module | 168 passed; no failure, skip or warning in the final full run |
| Existing lifecycle tests, excluding the new module | 163 passed |
| Existing Founder tests | 158 passed; two existing dependency warnings |
| Existing Customer tests | 153 passed; the same two warning types displayed again |
| Existing offline F.03 security | 244 passed |
| Frozen contract tests | 92 passed |
| Model-checker regression tests | 12 passed |
| Exact-base physical static/model check | 5/6 groups passed; document links fail on intentionally unmaterialized Stage1 paths |

The physical static check independently passed all 89 frozen WBS fields against
the exact base, 23 SVG/source pairs, requirement/use-case IDs, Member A and
Composite references. Its remaining document-link failure is retained, not
silenced: this authorized sparse candidate deliberately leaves 106 baseline
paths unmaterialized, including `docs/11-stage1-readiness.md`. A separate
Git-object document check, if supplied, is a different evidence layer.

An offline wheel build/install and isolated import outside the checkout passed;
all four installed new runtime files matched the candidate bytes. Two actual
installed private calls over the dedicated database passed. Four subprocess
cases were subsequently strengthened with counters inside each child and
passed again: six actual child processes reported RETURN, LABEL, notification
send, LLM, outbound and NOTIFICATION-claim counters all zero. This test-only
delta did not change the runtime package. Those four, the four smoke tests,
48 authority checks and 16 earlier partial-run passes overlap the 168 and are
not added to its count. The 29 failure-source and 30 block-source injected
write points are loops within two tests, not 59 extra pytest cases.

Two earlier test-configuration failures are retained: the smoke read omitted
the frozen history query's required `kind`, and the expiry fixture initially
advanced the resource-TTL clock instead of the actual F.03 session clock.
Only the fixtures were corrected, with unchanged acceptance assertions and
production authentication. Both fixes passed their targeted checks and the
full module. Independent source review also identified and prompted the
accepted-intake proof and final post-source-read authority checks described
above; their real positive/negative regressions passed. Technical review of
the final exact candidate remains separate from the author's verification.

The dedicated database is `returnops_f02_a201_manual_20261007`, created only
after proving that name absent. Its final public schema has 47 tables: one
Alembic row and no rows in the other 46; no test schemas remain. The database
is retained. Historical business databases and the old interpreter environment
were not modified. Credentials were read only from the exact authorized test
container's two keys into memory; captured database-command logs are explicitly
sanitized streams, not claimed original process bytes.

The 18 IDs are not a pytest count. The other 16 design IDs remain planned and
unrun. The local implementation receipt records exact source hashes, commands,
per-node table snapshots and attempt history; these results do not supply the
pending human accepted-version records or authorize publication.
