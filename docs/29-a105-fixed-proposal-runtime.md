# A1.05 fixed synthetic proposal runtime

This bounded integration tracks [Issue 42](https://github.com/shuxiachai/returnops-au/issues/42)
and starts from adopted PR41/main `7df2afae85877ef40dfaae0e76dbacb9f6db2b0b`.
The user approved a one-time integration-start exception while the original
A1.03 Owner/C personal review and predecessor accepted-version records remain
incomplete. This is not whole A1.03 acceptance, a C1/C2 implementation, Gate 1,
personal review, a future merge approval, or a Jira status change. The original
89 WBS rows, ownership, S/F dependencies, public schemas, purposes and migrations
remain unchanged.

## Runtime boundary

The new packaged `FixedProposalProcessor` reads actual retained customer
statements, complete BOUND attachment metadata and bytes, and the accepted order
projection using the existing same-connection provenance checks. It constructs a
`HistoricalProposalBundle` and persists it through `ProposalAccepted`; success
ends at `RISK_REVIEW`. The existing Founder list/detail/history/audit operations
read the actual current packet and complete immutable history.

The generator is explicitly synthetic and fixed. Its only passage states that
the integration establishes no entitlement, legal conclusion, approval or
execution permission. The packet uses `provider-fixture`,
`fixture-no-live-model`, zero tokens, uncertain facts and the non-executable
recommendation `REFER_FOR_MANUAL_HANDLING`. This is a model metadata placeholder
required by the unchanged DTO; no model is invoked. Synthetic guidance is not
claimed as an accepted C1 retrieval or a reviewed production corpus. No Risk
result, Founder decision/approval, operation or notification is produced.

No production module imports the offline assembler or test producers. Original
and clarification text stays distinct from the generated summary. The order
receipt retains source input n and every original byte/hash/status/time/message;
only the derived context uses current input m, backed by the accepted projection
and its persistent PRIMARY binding. Attachment bytes are checked independently
without adding them to the unchanged wire DTO. No GET preview window is used as
the source inventory, and no collection is truncated to fit a packet.

## Explicit synthetic opt-in

Default startup adds no grant and runs no fixed-proposal worker. Two independent
actions are required:

1. Trusted local demo provisioning explicitly grants the fixed component's
   existing `PROPOSAL` purpose for the selected synthetic store, using
   `--fixed-proposal` (and `--order-investigation` for the existing synthetic
   order path). The private Python bootstrap requires
   `synthetic_demo=True, enabled=True`. No HTTP grant endpoint exists.
2. The API runtime explicitly enables the worker with
   `RETURNOPS_FIXED_PROPOSAL_DEMO=1`, the demo serve flag `--fixed-proposal`, or
   trusted Python composition `enable_fixed_proposal=True`. Enabling a worker
   never creates or repairs grants. The ordinary Docker default CMD is retained.

The current enabled customer/store scope and component-purpose revision are
checked under the exclusive Domain fence. A revoked owner, disabled grant,
changed target or retained-source loss cannot be substituted by an old grant.

## Durable intent and transaction result

The first transaction saves only a PENDING work intent. Its work identity is a
domain-separated canonical fingerprint of the original store, owner, component,
case, purpose, input version, generation and target hash. Existing default
LifecycleGuards callers keep their random work identity behavior. The controlled
optional identity path checks collisions against the complete original target.

The second fenced transaction claims that work and constructs the complete
source inventory, fixed packet, immutable history, finite-v2 encoding metadata,
origin audit and PRIMARY binding. The same transaction applies the guarded
event, advances the current pointer/case version, saves the event receipt and
marks the work DONE. There is no independently committed RUNNING claim. Lease,
authority, source bytes, exact binding, work and state are checked again before
commit. Producer proposal/source/event IDs derive from the persisted work ID.

An unknown commit is resolved only after the original connection is closed,
using a fresh exclusive fence and the original key/ID. An exact DONE receipt is
verified and reused; a completely absent intent/attempt is reported as proven
rollback; an untouched PENDING work can continue with its same identity. A
database/lock failure remains UNKNOWN. No unknown operation is described as a
denial or retried using a replacement identity. A restarted process discovers
the persisted PENDING intent, and exact completed receipts remain replayable.

Definite guard rejection rolls back staged business data. A separate production
helper may then save a fixed bounded denial audit only after current
case/owner/store/PROPOSAL authority is independently rechecked. Loss of current
authority yields `NOT_RECORDED`; uncertain audit commit yields `UNKNOWN`. A
separate authorized operational transaction may pause that unaccepted work to
avoid an endless background denial loop. It does not advance business state.

Only proved business guard denials qualify for this audit/pause path. A closed
rollback with a retryable statement error or unexpected local failure returns
`RETRYABLE`, leaves the durable intent PENDING, and schedules the same intent
with an exponential delay bounded from one to sixty seconds. Before retrying,
the worker re-resolves the original identity under a fresh fence. A private
processor UoW preserves a payload-free classification flag when the unchanged
base UoW sanitizes commit-check errors to `INVALID_STATE`; a query timeout during
that final check therefore cannot accidentally park work forever. An unknown
commit never takes this retryable-rollback shortcut. The DONE replay path also
records its commit acknowledgment before context exit, so a subsequent close
error resolves the original receipt rather than reporting a false denial.

## Capacity failure

Frozen DTO validation is the capacity oracle. A complete inventory above its
limits produces no partial packet. The private typed `ProposalFailed` event
uses existing `PROPOSAL` authority, but has a distinct `PROPOSAL_FAILED`
fingerprint and receipt kind. It stores a sanitized `ProcessingFailure` at
stage `ASSESSMENT`, code `REQUEST_TOO_LARGE`, `retryable=false`, then atomically
sets the failure pointer and moves `POLICY_ASSESSMENT` to `ESCALATED` with no
current proposal/review/approval/outcome. It does not execute manual handling.

The guard independently re-proves actual full-input capacity overflow and the
fixed failure origin/body/identity, including at commit. A caller cannot merely
assert an overflow to obtain an escalation. Failure history uses the existing
default history/v1 encoding, while proposal bundles opt into the existing
finite-v2 profile. No codec default or old migration changes. Earlier immutable
statements, receipts, proposals, approvals and effects are retained; retention
continues to remove all derivative personal bodies atomically.

## Verification status

The exact candidate source passed the new targeted suite: 51 tests comprising
eight non-database tests and 43 real PostgreSQL/TCP cases, with no failure, skip
or warning. The eight established suites also passed in separate commands:
244 security, 74 storage, 32 environment, 153 customer, 64 orders,
41 investigation, 158 Founder and 163 lifecycle tests, totalling 929.
The targeted 51 are contained in the lifecycle 163 and are not added again.
PostgreSQL was 17.11 with the unchanged `0007_lifecycle_guards` migration in
the task-owned `returnops_f02_a105_20261005` database. The environment, customer
and Founder calls each displayed the same two existing dependency warning
types, six displays in total. This is a sequence of commands, not a single
pytest invocation.

The executed cases cover complete retained sources and attachment bytes,
capacity boundaries, tampering, current authority, duplicate workers, lease and
commit barriers, actual commit versus rollback uncertainty, interpreter restart,
real HTTP clarification through background production, Founder reads and
Customer denial. Independent preliminary review found two P2 issues: transient
failures could permanently pause work, and DONE replay could report denial after
an acknowledged commit followed by a close error. The fixes passed their actual
SQLSTATE `57014` statement/final-check and post-commit-close regressions; each
problem has zero failed fix/validation attempts. Independent source review of
the complete 14-path candidate then reported no remaining actionable finding.

A retained wheel was built without network dependency resolution and installed
outside the checkout. Its SHA-256 is
`f279b63e987badbe84e9178fa81bdd8e24699ca14a34ea1c078c187b6a1e6b22`.
An isolated interpreter verified installed API/domain/security modules, the
synthetic order resource and all five new production modules, including opt-in
composition without database access or grant creation. The Linux runtime image
`sha256:2f9f37da64ac80c9ca572eff50bf7d44874299be126dc2297860ca3db54eaef9`
also passed a separate installed probe as actual UID 10001, with no network,
a read-only filesystem and all 65 package files checked against the exact
source/wheel bytes. This import probe did not execute the database workflow.

The same immutable image then passed the real workflow in two separate
UID-10001 containers using the unchanged default CMD and a read-only filesystem,
without a source-code mount. In the fresh task-owned
`returnops_f02_a105_container03_20261005` database, a PDF upload returned 201 and
an initial case without bound evidence returned 201. The ordinary workers
reached `AWAITING_INFORMATION`; a real clarification containing `SYN-1001` and
the staged PDF returned 202 and reached `POLICY_ASSESSMENT`. No proposal work or
event existed while the fixed worker was disabled. A new container enabled the
fixed worker and reached `RISK_REVIEW`, input version 3 and case version 7.

The persisted complete history contained both actual statements and the one
BOUND PDF with matching metadata, SHA-256 and retained bytes. The original order
receipt remained at source input 2; its accepted projection was input 3 and the
derived packet context was current input 3. Exact original receipt and projection
bytes, hashes and fields remained unchanged, and the current packet, immutable
history, event, completed work and PRIMARY source binding all matched. Four
Founder GET operations returned 200; the same four operations as Customer
returned 403. Their reads left all 43 non-Founder-table fingerprints unchanged.
There was exactly one DONE work and one PROPOSAL event, only PROPOSAL authority,
and zero Risk/review, decision, approval, operation, notification or effect
records. Both new API containers were stopped and removed by exact ID/name/image
guards. The original PostgreSQL container and all three task databases were
retained. Read-only comparisons proved every table count and content fingerprint
in the two earlier databases unchanged after the successful flow.

The verification history is retained without claiming a first-attempt pass.
The first container attempt stopped at the pristine-database guard because the
929-test database legitimately retained five committed initial-record bundles
from the storage tests. A new isolated database was created and migrated
successfully, but a helper postcheck incorrectly compared unordered inspector
table names with a sorted list. A read-only finalizer verified the exact 47
unique table names, migration 0007 and 46 empty non-version tables; no migration
or database creation was repeated. These are two recorded setup-condition
failures. The next runtime attempt bound a PDF at initial creation without an
order reference, correctly selecting the existing alternative-proof verification
branch and pausing investigation. That helper fixture had one failed validation.
The successful fresh-database scenario instead bound the PDF alongside the valid
order-reference clarification, with the same state assertions and 45-second
limits. The failed case and both earlier databases were preserved; no production
source fix, state override, truncation or assertion weakening was needed.

The candidate passed 92 contract tests, five independent existing static model
groups, the exact 89-row WBS field comparison against
`7df2afae85877ef40dfaae0e76dbacb9f6db2b0b`, 23 SVG/source comparisons,
12 checker regressions, seven runner regressions and 14 Mermaid parses.
The full local document-link step remains blocked by the intentionally sparse
checkout and preserved removal of old Stage 1 report/audit artifacts. Its first
attempt failed with three of six static groups completed; the failed output is
retained. Sixty missing generic baseline documentation/ignore files were then
materialized from exact existing Git blobs; excluded reports/audits were not
restored. The five independent groups passed afterward without altering any
checker or assertion. This does not claim a complete offline-runner pass. The
unchanged complete document-link check must pass on the normal full CI checkout
before adoption. Locked npm installation displayed two deprecation warnings and
an update notice; no dependency lock or version was changed.

Earlier interpreter setup failures remain recorded: two validations stopped
before database access because the originally instructed root interpreter lacked
existing `pypdf` and `python_multipart` dependencies. The parent subsequently
provisioned the task-owned interpreter from the unchanged hash-checked lock.
Earlier three/four/eight-test and 40/43-case collection results are historical
subsets, not additional executed coverage. The environment failure ledger is
preserved separately; no prior Docker, shared temporary-directory or unexplained
migration-delay history is reset by the passing tests.

The task-owned implementation evidence directory stores per-command source
manifests, stdout/stderr bytes and receipts. No future feature or teammate
acceptance follows from these results. Jira mapping remains unverified under
the explicit temporary exception; no key or Done status is inferred from Issue
42. Owner Jingbo Chai and designated reviewer Yuwei Tao personal acceptance and
the original predecessor accepted-version records remain separate and pending.
This implementation authorization does not approve a merge; a separate scoped
merge decision is required.
