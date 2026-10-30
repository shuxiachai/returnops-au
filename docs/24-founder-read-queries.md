# F.05 / F.03: authorized Founder read queries

Delivery: [KAN-14](https://lucastaooo.atlassian.net/browse/KAN-14),
[Issue29](https://github.com/shuxiachai/returnops-au/issues/29). Owner A; designated
Reviewer C. Trace: FR-011/012, the current case/history/audit class and sequence
models, and the relevant NFR-001/003/004/006/008/009 portions. The saved Jira mapping
is historical evidence, not a claim about its live status or whole-item acceptance.

The four existing v1 GETs now read accepted customer and investigation records:

- `/v1/founder/cases`: frozen ordered case summaries for the current store.
- `/v1/founder/cases/{case_id}`: current available statements, evidence, order
  projection, clarification and safe investigation block/failure.
- `/v1/founder/cases/{case_id}/history`: all ten frozen history kinds, with exact
  optional object ID/version filters and ascending revision order.
- `/v1/founder/cases/{case_id}/audit`: the retained, validated event/hash chain.

List and audit accept only `cursor` and `limit`; history additionally requires
`kind` and accepts `object_id` and `object_version` (version requires ID). Default
limit is20, maximum100. Detail accepts no query. Unknown/duplicate parameters and
invalid values fail422. Validly shaped but unknown, mismatched, tampered or expired
cursors fail409 without restarting the snapshot. Responses have no-store caching
and server-issued correlation IDs. The public schema/OpenAPI are unchanged.

## Current authority and transaction boundary

F.03 resolves current identity/session/role/store and case availability from the
same database connection on every request. There is no HTTP role/store selector.
CUSTOMER fails403; foreign-store or unavailable cases fail404; invalid, revoked or
expired sessions fail401. A cursor never grants authority.

Each query starts `CustomerUnitOfWork(write=True)` and acquires the existing
exclusive transaction fence before authorization and reading. This permits the
minimal internal snapshot/cursor/encoding writes without a shared-to-exclusive
lock upgrade. The service rereads authority at completion with fresh authentication
time, rechecks list resources and cursor expiry, and only then commits. Retention,
registry changes and business writers use that same fence. A commit with unknown
outcome yields a safe503; reissuing a GET may register new read metadata but cannot
replay an intake or investigation action.

All existing business tables remain unchanged by these GETs: no case/input version,
audit/history event, work item, proposal, review, decision, approval, operation or
notification is created. Tests fingerprint every non-Founder table before/after
reads, including existing customer cursor metadata.

## Stable pages and current retention

Independent migration `0006_founder_reads` creates four Founder-only tables.
`customer_tables` and migrations0002–0005 are unchanged; migration0003 still imports
its original live metadata. Founder list snapshots retain only ordered membership
and the typed non-personal CaseSummary fields. New cases and subsequent status or
version changes cannot shift the old sequence. Each page still restricts current
case availability and trusted store. Unevaluated classification is `UNCLEAR`;
there is no fabricated facts or risk result.

Since 31 October 2026 each listed case also carries the optional `current_risk_outcome`
when it has a current review: the outcome of an accepted, decodable review bound to the
case's current input and proposal, the same rule as `analytics_queries.current_outcome`
([docs/43](43-f06-analytics.md)). It is read for each page when the page is served, not
frozen in the list snapshot; before, the field was never sent, so the queue showed no
risk outcome even for a reviewed case.

History snapshots freeze case version and sequence high-water. Audit snapshots
freeze sequence and the corresponding chain hash. Opaque random tokens are stored
only by their SHA-256 and bound to purpose, principal, role, store, case, kind,
object filters, limit, position and expiry (default900 seconds). Founder and
customer namespaces are separate. Personal history/lookup bodies are never copied
into Founder metadata; each read uses current retention. A deleted statement or
evidence revision keeps its identity/order/hash and returns its tombstone.

Detail has six real collection windows: statements, evidence, decisions, approvals,
operations and notifications. They share one history snapshot. Previews choose the
latest revision of each object before filtering availability, so deleting its
newest revision cannot resurrect an older body. Up to100 current objects are
shown, retaining the original statement when available. Counts cover all revisions,
including tombstones; every start cursor begins the complete kind at the default
page size, not after the preview. Future collections are genuinely empty, with
consumable cursors. `cited_passages=[]`; absent facts/proposal/review/preview stay
absent. No new public history kind is introduced.

## Provenance and encoding compatibility

The old history rows are immutable. Founder actors come from a unique original
creation event in the verified audit chain, matching case/version/time and exact
record/kind/object/version references. Later retention events cannot replace the
original actor. Imported0002 facts keep the actual migration SERVICE actor,
`a1_storage_import`; they are not retrospectively called customer acceptance.
Missing or conflicting provenance fails503.

The neutral reader also validates nonempty PROPOSAL, REVIEW, DECISION, APPROVAL,
OPERATION and NOTIFICATION history using their frozen DTOs. Its explicit internal
origin-event contract is, respectively, `PROPOSAL_ACCEPTED`,
`RISK_REVIEW_ACCEPTED`, `FOUNDER_DECISION_ACCEPTED`, `FOUNDER_APPROVAL_ISSUED`,
`OPERATION_REVISION_RECORDED` and `NOTIFICATION_REVISION_RECORDED`. These are
reserved producer-to-reader storage names, not evidence that those producers or
events have occurred in a real application. The production append whitelist and
business writers are unchanged. Test-only fixtures persist clearly synthetic
contract records directly in isolated PostgreSQL schemas; their model metadata
describes fixtures and does not claim actual inference or independent Risk work.

Strict DTO checks precede nested identity access. Proposal object revisions equal
the saved packet proposal version; other object revisions retain their own storage
sequence. Approval case identity comes from its scope. Embedded case versions may
precede the saved history boundary. Saved proposal source case/input/corpus,
original-statement identity, evidence references and citation-check coverage must
agree. A review resolves its exact same-case proposal record and version, ordered
no later than that review; available proposal bodies additionally bind input and
corpus. A retained proposal tombstone proves identity without reconstructing its
removed bundle. Human decision/approval actors match the saved Founder principal;
a MODEL actor matches the saved full ModelRun. No read of these records grants
current approval or execution authority, re-evaluates Risk, or invokes retrieval.

Fractional confidence and image-observation values use an explicit private finite
number profile. `founder_codec` keeps the existing `canonical.py` and `wire.py`
bytes and their strict customer behavior unchanged. The new `ROPS\x02` encoding
uses `document/finite-v2` for bodies and `history/finite-v2` for the complete public
content hash of all six future kinds. Strings still preserve UTF-8 surrogatepass
codepoints, map keys are sorted and arrays retain order. Finite nonintegral floats
use a tagged big-endian IEEE754 binary64; integral floats including negative zero
normalize to integers. Integers never pass through floats. NaN, infinity, Decimal,
arbitrary objects, malformed encodings and excessive nesting fail safely. This is
a private typed binary format, not a JSON canonicalization standard. The internal
Founder schema helper keeps the frozen complete schema/format checks and permits
only the listed history/body/output DTOs; requests retain their original validator.

Founder encoding metadata explicitly selects `founder-finite/v2` or
`founder-finite/v2-from-v1`; it never infers permission from a body header. The
first profile binds source and projected hashes to the same full-content v2 hash.
The second preserves a verified legacy v1 body/source hash and records its v2
public hash without rewriting that body, history row or audit. Both profiles have
no receipt ID; the old block profile still requires its exact receipt. An available
legacy body may register this metadata only after all provenance/content checks.
A tombstone must retain its encoding metadata, otherwise the reader cannot invent
the missing public hash. Migration0006 backfills verified available legacy future
records as well as safe blocks; an unresolvable future tombstone rolls the migration
back for a separate data plan. The four old history kinds and block wrapper retain
their original history/v1 encodings and digests.

Existing ORDER_LOOKUP_BLOCK history stored a bare block. Founder v1 requires
`HistoricalOrderLookupBlock {block, order_lookup}`. For accepted CONFLICT and
AUTHORITY_DENIED results the strict source result consists exactly of case ID,
input version, status and safe message, all preserved by the block. The read
projection reconstructs that complete result, verifies the available original
receipt/hash and exact acceptance association, and validates the wrapper schema.
The public hash is the wrapper's actual `history/v1` digest. It is not the old bare
block hash. Hash-only metadata records both hashes, the encoding profile and
receipt ID; original rows/bodies/audit refs are never rewritten.

0006 verifies and registers existing block encodings; later blocks register on
their first verified Founder read. Current retention deliberately retains safe
blocks/failures while removing personal receipt/projection bodies. A safe wrapper
remains verifiable from the retained full block and accepted audit after receipt
removal, without restoring a request/reference/catalogue. Any future implementation
that removes block bodies must register their public encoding before removing
those bodies; missing tombstone encoding fails closed rather than inventing a hash.

Audit validates event IDs, sequence, current head, previous hashes, versioned
`audit/v1` hashes and exact history references. It does not reconstruct the removed
original audit payload and does not claim resistance to a DBA rewriting the entire
chain and head. Current order projection reads verify the retained accepted snapshot
hash/identity, original lookup and acceptance link. They follow only the current
pointer, never fall back to old personal projections after deletion. Reusing an
accepted snapshot does not change its historical source-input version.

## Verification and remaining scope

Run the configured disposable PostgreSQL17 checks with
`python -B tools/checks/run.py environment`. It now includes `tests/founder` after
all existing environment/storage/customer/investigation groups. Security/orders,
contracts/models and installed-package checks retain their existing entrances.
Founder tests cover real five-outcome investigation data, four HTTP routes,
126-revision and126-event pagination, concurrent appends/status changes, exact
filters, authority/cursor negatives, retention, tampering, real0005 data upgrade
and repeat migration. An independent-process TCP test carries a persisted cursor
across API restart and rechecks all five investigation outcomes and deletion.

This increment delivers F.05 reads with F.03 authority. Original F.05 dependencies
remain S=F.01 and F=F.02/F.03; A1.03 includes F.05 as a completion dependency. It
neither accepts the whole A1.03/A1.05 package nor supplies a packet, Risk decision,
approval/decision POST, operation, notification service, LLM or real provider.
B/C contribution and human/joint acceptance remain separate. Stage1 submissions
and A3 tutor feedback are unchanged. Local execution and remote CI results belong
in the exact candidate's evidence/PR record, not a claim that all tests passed
before execution.
