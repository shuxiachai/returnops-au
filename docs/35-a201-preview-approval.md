# A2.01 private action preview and Founder approval

Technical tracking: [Issue 55](https://github.com/shuxiachai/returnops-au/issues/55).
Owner A Jingbo Chai and designated human reviewer C Yuwei Tao remain unchanged.
The original S=F.01 and F=A1.03,F.03 dependencies remain; the human authorized a
limited start exception for this component. This is not prerequisite acceptance,
C's signature, whole A2.01 acceptance, or Gate 1 acceptance.

## Private component

`compose_private_preview` creates a server-owned preview from the complete
retained, actually accepted synthetic PASS/PASS_WITH_WARNING source chain.
It verifies the fixed two-cup family, original proposal/review work, claims,
bindings, audit, accepted events, current input and order projection. The
request supplies only case ID, expected version, original key and correlation
ID. PREVIEW is a separate current service permission, with no preview queue.

The fixed profile is `mock-v1`: AUD 0, SIMULATED, 300 seconds,
`provider-mock-return` followed by `provider-mock-label`, one server-generated
parcel, a PDF label and `chargeable=false`. Commands and the scope fingerprint
are generated and saved by the server. Item duplicates are rejected before
sorting, and quantities must be actual integers within the accepted order.
The general builder capacity tests do not widen the runtime two-cup family.

Preview acceptance increments case_version exactly once. Same-key replay
returns the original preview and expiry. Every replacement edge must be an
explicit new key/current version after the previous preview expires; the
backlink chain must reach the exact original review version. This delivery
does not support live profile-version changes. A new profile requires a
separately reviewed implementation. No version comparison is weakened to `<=`.

`compose_private_approve` authenticates the real F.03 HUMAN Founder and a
separate APPROVAL service capability. It compares the request with the
original saved preview, verifies current source/authority/profile/expiry,
and saves DECISION, APPROVAL, audit, PRIMARY approval binding, event receipt,
fixed DecisionReceipt and one stable EXECUTION intent atomically. The case
stops at APPROVED. EXECUTION starts PENDING, epoch 0, with no claim, claimed
version, lease or authority revision. Existing claim/prepare/apply paths
cannot consume EXECUTION, even if a caller manually supplies an execution
grant. No execution grant is provisioned by the component.

Final checks repeat current F.03/service permissions, source proof, original
claim/epoch/lease, current references and the exact saved rows. Historical
proposal/review grant revocation does not erase an accepted historical fact.
Current PREVIEW and APPROVAL permissions must still match for a new approval.
The transaction retains the exclusive Domain fence through source validation
and commit; supported input and retention writers use the same fence. This
protects the supported transaction protocol, not arbitrary DBA writes or
replacement of trusted private functions with code that rewrites the database.

## Compatibility and erasure

REJECT accepts a fully proven valid or expired current preview, consumes it
once and clears the current preview pointer. Its new internal audit payload
binds the consumed preview; old no-preview v1 audit/proof behavior remains.
The original PASS receiver replay does not recreate or extend a preview.
Existing ESCALATE revision/manual paths remain scoped as before.
AWAITING_APPROVAL revision/manual handling remain unavailable.

GET verifies preview source provenance and returns only a current unconsumed
unexpired preview. It does not issue, replace or renew a preview. An approved
case does not revert when the scope expires. A historical receipt replay is
an acceptance fact, not present execution authority. UNKNOWN never retries
business or changes the key; recovery absence stays UNKNOWN.

`lifecycle_action_previews` stores the erasable body separately from durable
request/source/transition/consumption identity. Retention removes preview and
derived history bodies under the same fence, clears current references,
pauses pending execution work and makes affected receipts unavailable.
Neither history nor a receipt may reconstruct the erased preview.

## Schema boundary

The explicit `0009_preview_approval` migration adds one independent preview
table and APPROVAL/EXECUTION to the existing work-purpose CHECK. It performs
no data backfill or grant provisioning and refuses automatic downgrade.
The old 0007 migration, its dynamically imported `lifecycle_tables` metadata,
and 0008 migration remain unchanged. Schema descriptors distinguish exact
0007/0008/0009; new runtime readiness requires 0009. New table checks include
column types/nullability, key/FK identity, validated/nondeferred constraints
and ordinary nullable-UNIQUE semantics. Missing/partial/counterfeit schema
fails closed. No implicit startup migration exists.

## Verification status

This is a local implementation under an explicit database pause. No local
database or Docker was connected, started or migrated. PostgreSQL tests,
installed private runtime invocation, container CI, publication and adoption
are not completed by this document. The earlier Founder UNKNOWN run is not
reclassified.

Prepared AP01–AP20 scenarios live in
[test_founder_approve_postgresql.py](../tests/lifecycle/test_founder_approve_postgresql.py).
Additional late-authority and competing-intent scenarios live in
[test_founder_approve_late_postgresql.py](../tests/lifecycle/test_founder_approve_late_postgresql.py).
These prepare AP12 checks after expensive source reads, AP10 different-key
competition, AP11 preview and actual CustomerFlow input-entry competition,
and AP12/AP19 retention-versus-approval ordering using separate PostgreSQL
backends and observed fence waits. Customer clarification remains restricted
to AWAITING_INFORMATION; a competing input request at the approval state is
expected to be rejected, not accepted through a test-only public capability.
They require a separately authorized disposable PostgreSQL environment and
must execute against the independently reviewed final source. A prepared or
collected node is not a passed test. The installed child probe likewise is
prepared only; normal imports and DDL string compilation are not migration
or installed runtime execution.

Offline checks are in
[test_founder_approve_offline.py](../tests/lifecycle/test_founder_approve_offline.py).
Per-attempt raw outputs and final source bindings are retained outside the
candidate in the task verification directory. Earlier failed attempts remain
in the ledger; reruns and subtests are not counted as distinct new coverage.
Independent source review and final PostgreSQL results are separate gates.

No public Founder POST, default preview/review producer, live model, provider,
ToolCommand execution, OperationAttempt, label artifact, business outcome or
notification work is produced by APPROVE. The A2.02/A2.03 consumers remain
future work without becoming a new circular A2.01 start dependency.
