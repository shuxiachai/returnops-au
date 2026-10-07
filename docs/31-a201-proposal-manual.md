# Private controlled ESCALATE review and proposal manual handling

This local candidate implements two separate explicit transactions. A private
receiver accepts a controlled synthetic ESCALATE review of the complete retained
accepted proposal and enters ESCALATED. A subsequent Founder request validated
by the actual HUMAN/F.03 authorization path, with independent OUTCOME authority,
accepts MANUAL_HANDLING and enters
NOTIFICATION_PENDING. No notification is claimed or sent.

The receiver accepts only case ID, expected version, original key and correlation
ID. The trusted server injects an adapter; no adapter is registered by default.
The only supplied adapter is under tests and labels its invocation as controlled
synthetic, fixture/no-live-model, zero tokens. Its successful invocation proves
A's acceptance component, not C's implementation, a live Risk model or C review.
The frozen DTO and default finite/legacy codecs are unchanged.

Both entries authorize before replay lookup. New review acceptance reads actual
retained proposal sources, original work/claim/binding/audit/event receipt,
current owner/store/input/generation and the original REVIEW lease. It preserves
the complete bundle, retrieval conflicts and citation checks. The review event
uses independent REVIEW authority and a PRIMARY binding to that proposal and
its accepted order projection. Manual handling follows the stored
decision → review → proposal chain; OUTCOME target metadata binds both current
refs. Historical review authority does not become current HUMAN or OUTCOME
authority. Every current authority and original claim remains subject to final
commit checks under the original PostgreSQL fence.

0008 extends only the lifecycle work purpose CHECK with REVIEW. The old 0007
migration and its dynamically imported metadata DDL are unchanged. The runtime
recognizes exact 0007 for its prior components and exact 0008 for REVIEW;
application readiness requires 0008, the complete table set and exact versioned
CHECK. No runtime migration, grant, backfill or new table is introduced. Unknown,
partial, mismatched and multiple revisions fail closed. Downgrade requires a
separately approved data plan.

Acceptance commit ambiguity returns UNKNOWN without denial audit or retry.
Recovery uses a fresh fence, current authority and original key. Record absence
remains UNKNOWN; an explicitly proven rollback is required before the caller
can explicitly retry the same key. Definite denials close the original UoW
before a fresh authorized audit transaction. Revoked authority records no case
audit; ambiguous audit commit is reported separately as UNKNOWN.

Retention removes derived review/proposal/decision/receipt bodies without
rebuilding them. Founder reads verify current accepted review relationships
while preserving historical authority separation and avoiding business writes.
The original no-proposal failure/block manual path remains in scope for
regression, not replacement.

Local validation completed on PostgreSQL 17.11. The final runtime passed all 478
lifecycle tests, including 145 unique new nodes covering the 18 design groups.
Seven unchanged-assertion late-effect scenarios explicitly run on exact 0007:
they depend on the old synthetic PASS/approval/execution starting fixture and
are legacy component regressions, not modern A2.01 execution. Other effect
tests remain on 0008. The original empty-review AWAITING_APPROVAL component
edge is tested on both 0007 and 0008; modern nonempty review mismatches fail
closed. The new private Founder service still admits only actual accepted
ESCALATE reviews in ESCALATED.

The seven other suites passed 766 tests before the final narrow modern
AWAITING/nonempty-review denial was added: security 244, storage 74, environment
32, customer 153, orders 64, investigation 41 and Founder 158. Their source
layer is recorded separately from the final lifecycle layer; 1,244 is a union
of eight suite results, not one pytest invocation or a claim that all eight
were rerun on the final bytes. The environment, customer and Founder calls
each displayed the same two existing dependency deprecations, six displays in
total. Final lifecycle tests had no warnings or skipped tests.

The original offline contract discovery passed 92 tests: 68 existing contracts
plus 24 offline fixed-proposal tests. Model-checker and runner regressions passed
12 and 7 tests. The eight lifecycle fixed-builder tests were also run separately
and overlap the lifecycle total. Parameterized unittest subtests and earlier
targeted runs are not added to these totals. The installed wheel was exercised
outside the checkout by an isolated child that actually called both entries;
each racing/installed child installed its own effect counters. RETURN, LABEL,
notification sends/claims, model and outbound business counters remained zero;
REVIEW and OUTCOME claims were recorded separately. These are local results,
not CI, deployment, human acceptance or a real C review.

The task evidence directory `tmp/a201-proposal-manual-entry-20261007/implementation`
records exact source/test hashes before each invocation, sanitized process
streams, full physical-table snapshots including binary-body hashes, independent
process output, failures and the exact 18-group-to-node map. Group counts overlap
where one actual test proves two groups; there are 145 unique new nodes.

| Group | Actual acceptance focus | Unique nodes within group |
|---|---|---:|
| 1 | Empty and real legacy intake/order/proposal/manual upgrades | 4 |
| 2 | Exact legacy/current schema and corrupt-schema rejection | 12 |
| 3 | Complete fixed proposal to atomic ESCALATE review | 1 |
| 4 | Frozen review DTO, BLOCK, provenance and input references | 16 |
| 5 | Actual proposal work/claim/audit/receipt and retained bytes | 11 |
| 6 | REVIEW entry/final authority, claim and lease checks | 15 |
| 7 | Separate Founder manual acceptance and pending intent | 1 |
| 8 | Proposal targets, accepted review and low-level bypass denial | 24 |
| 9 | Independent HUMAN/OUTCOME entry/final authority | 23 |
| 10 | Original receipt replay, conflicts and replacement-key denial | 1 |
| 11 | Two independent processes competing for each original key | 2 |
| 12 | Legal input/revision serial orders and late original claims | 10 |
| 13 | Actual commit with lost acknowledgement and fresh recovery | 8 |
| 14 | Proven rollback versus unresolved absence | 10 |
| 15 | Every write point and final failure roll back atomically | 2 |
| 16 | Retention and read-only accepted-source relationships | 5 |
| 17 | Fresh denial audits, revoked authority and audit ambiguity | 8 |
| 18 | Default composition boundary and installed actual child calls | 2 |

Group 12 preserves legal state restrictions: real post-review customer input
is denied, and an accepted manual pending outcome cannot be revised through
the old revision edge. It does not fabricate successful input transitions or
claim the APPROVE race. Group 16 does not claim preview expiry.

This local implementation is authorized by the new scoped exception recorded
for technical Issue #46. It does not authorize source publication, a PR, Ready,
merge, whole A2.01/Gate1 acceptance, human signatures, public POST endpoints,
APPROVAL/preview/execution, a real C producer, provider/model calls or sending.
