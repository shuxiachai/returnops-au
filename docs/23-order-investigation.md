# Persisted order investigation and clarification

This Issue [#27](https://github.com/shuxiachai/returnops-au/issues/27) / recorded **KAN-14** delivery extends the A1.03 Domain lifecycle on main `4673f9f1372b29dbb753a41e4a029c9382e8f07b` (adopted PR24 customer flow and PR26 read-only synthetic provider). It supports the later A1.05 path. Use the actual pull request and exact-source validation records for publication, review and merge status. It does not declare all of A1.03/A1.05 or their prerequisites accepted, or represent teammate/joint sign-off.

The existing seven [customer operations](21-customer-flow.md) are unchanged. No order endpoint, customer authority field, new login role, Founder view, proposal packet, Risk PASS, approval, operation, model call or real provider is added. The [A1.04 catalogue and typed port](22-a104-synthetic-order-provider.md) remain unchanged.

## Admission, investigation and versions

Customer create still atomically stores its original201 SUBMITTED/case1/input1 receipt and INTAKE work. Clarification still stores an immutable202 admission receipt and distinct accepted source statements. GET never runs either processor and replay never enqueues another job.

A successful new intake with no outstanding questions registers separate `investigation_work` in **that same database transaction**, only when its store has an explicit investigation service binding. Missing configuration leaves the previous intake behavior; disabled configuration creates a paused work item. Migration and startup never backfill old completed cases. A pre-upgrade UNDER_INVESTIGATION case with no investigation work remains there until a separately designed, explicitly authorized future reschedule.

The lifecycle processor takes a short exclusive global-fence transaction to claim work with a random token, increasing epoch and30-second lease. A separate shared-fence transaction resolves current owner/store/account, available sources and receipts, claim/input/case versions, service configuration and provider grant from the same PostgreSQL connection before invoking the immutable provider. It releases the shared lock before opening an exclusive result transaction that checks all of these observations again. Supported registry, policy and retention writers use that same fence; no shared-to-exclusive upgrade occurs.

Each accepted lookup has an immutable internal receipt containing the exact request/result at input n, catalogue metadata and service/grant signatures. The body is separate from the receipt's minimal identity/hash metadata. Outcomes are handled atomically with the state, work and case audit:

| Outcome | Persisted consequence |
| --- | --- |
| MATCHED | Save a separate order projection at input n+1 and advance to POLICY_ASSESSMENT. The raw provider result remains n. |
| NOT_FOUND | Issue the current internal alternative question group and advance to AWAITING_INFORMATION, without advancing input. |
| CONFLICT / AUTHORITY_DENIED | Persist one current safe OrderLookupBlock and advance to ESCALATED, without inventing a technical failure. |
| PROVIDER_FAILURE | Record the actual typed failure receipt; retry after1 second. Two actual provider failures exhaust this local budget and create ProcessingFailure(stage ORDER_LOOKUP)/ESCALATED. |

Scheduling alone does not advance business versions. Accepted business-state changes advance case_version once. Identical snapshot identity/version/content cannot repeatedly advance input; conflicting content for the same identity/version is rejected. Completed source INTAKE session/work remains historical at n after an order projection advances the head to n+1. It is not relabelled or re-enqueued.

The durable worker recovers pending and expired running work on startup. Old tokens/epochs cannot accept. Unknown claim commit is reconciled by the original token. Unknown result commit is reconciled by original receipt/work/hash; an unresolved in-process observation is retained for retry without a new lookup. After a process crash before a receipt exists, an expired claim may perform a new read-only invocation with a new identity; it cannot create a second accepted result for the same completed work.

## Current permissions and clarification

`InvestigationPolicy` is an internal trusted provisioning boundary, not an HTTP route. A service binding fixes store/service/provider/catalogue identity, enabled flag and revision. Its independent provider grant records current read permission/revision. An enabled service with an absent or false grant receives the provider's actual AUTHORITY_DENIED result without reading catalogue records. A revision change after lookup discards the old result and pauses work; it does not convert a previously returned MATCHED response into a denial. Explicit resume rechecks current input and sources through a fresh claim. Merely enabling or granting access never reopens an ESCALATED case. HTTP session expiry/revocation does not retroactively cancel already admitted work; disabling the customer or changing current store scope blocks it.

A newly configured case without purchase material reaches actual NOT_FOUND and gets two internally typed questions: ORDER_REFERENCE and PURCHASE_CONTEXT. Either an eligible reference answer or purchase description/newly bound authorized evidence satisfies the group. Only the reference question supplies the next lookup reference. Its full answer remains an original clarification statement; values longer than120 characters are saved without truncation and prompt targeted correction. Descriptions and files are retained for later verification and produce paused `ALTERNATIVE_PROOF_REQUIRES_VERIFICATION` work in UNDER_INVESTIGATION. They never manufacture a verified order or repeatedly ask the same question. Previously stored ordinary question sets retain AND semantics. Internal kinds/group rules are not public fields.

The same guarded Domain mutation helper serves create, clarification, intake and investigation. Unsupported state transitions fail; an invalid mutation poisons its transaction so caught errors cannot commit preceding partial writes. Authorized invalid HTTP clarification attempts record only a safe rejected-attempt audit, without an acceptance/work/statement. This is not the entire later revision, notification or approval transition matrix.

## Retention and audit

Source deletion removes related customer receipt copies and all investigation reference/receipt/projection payload copies for the case, marks them unavailable, clears the current projection/question pointer, and pauses only active investigation work. Safe hashes/IDs, terminal DONE/FAILED facts and existing sanitized escalation targets remain. The original business status is preserved: retention is not a new POLICY_ASSESSMENT→UNDER_INVESTIGATION or ESCALATED restart transition. Case version advances once; input does not. A late worker or exact accepted-receipt reconciliation cannot restore removed bytes or current facts. Downstream policy assessment must require a currently available projection; this slice implements no assessment or recovery bypass.

Internal service policy changes have a separate per-store hash chain, serialized under the same fence and bound to indexed event ID/store/sequence. Public case AuditEvent and history schemas remain unchanged. Internal lookup receipts are not a new public history kind. Only existing ORDER_LOOKUP_BLOCK and PROCESSING_FAILURE kinds are used for safe historical targets; CustomerCaseView exposes neither internal order facts nor those Founder-only objects. Discarded invocations retain only static reason, identities, policy signatures and time, never request/result/reference bytes or a raw exception.

## Explicit local use and checks

Use a disposable PostgreSQL17 database with an explicit `returnops_f02*` name and the locked environment. Migration0005 owns separate metadata and14 additive tables; old0002–0004 and case_heads columns are unchanged. No migration or API start creates a grant. Existing accepted data is preserved on upgrade and repeated migration.

```powershell
python -B -m alembic upgrade head
python -B tools/checks/run.py environment
python -B tools/checks/run.py offline --baseline-ref 4673f9f1372b29dbb753a41e4a029c9382e8f07b
python -B tools/checks/check-installed.py
```

The environment runner includes `tests/investigation`, whose TCP test starts and stops only owned loopback API processes on dynamic ports, using private synthetic credentials and an isolated schema. Tests cover five outcomes, frozen receipts, both question alternatives, parsed file binding, old AND behavior, upgrade with data, actual lock contention, two worker claims/API processes, restart, stale epochs/input, revocation/deletion, unknown commits, policy audit tampering and unavailable-content retention. Existing customer/storage/security/orders/contracts remain separate regression suites; overlapping focused runs are not additional unique tests.

For a fresh private synthetic demo, after setting the database privately, use the existing issuer with explicit opt-in. Choose a **new absolute** private directory; the command fails closed on Windows older than Python3.12.4 before creating it. Never print or commit its signing key/session tokens.

```powershell
python -B -m returnops_api.demo provision --private-dir <new-absolute-private-directory> --store synthetic_au_store --customer-one synthetic_customer_a --customer-two synthetic_customer_b --founder synthetic_founder --order-investigation
python -B -m returnops_api.demo serve --auth-file <private-directory>/auth.json --port 18081
```

The optional flag explicitly configures the immutable synthetic catalogue and its read grant. Default issuance remains unchanged. `SYN-1001` belongs to synthetic_customer_a; SYN-1003 belongs to customer_b and is an isolation negative for customer_a. An API request cannot choose a provider, dataset, role or permission. Provisioning errors retain private files to reconcile any uncertain registration rather than silently reissuing credentials. The server disables raw access logs. No secrets are supplied in command-line arguments.

Traceability: A1.03/A1.02/F.05 in [delivery packages](08-delivery-work-packages.md), [frozen interfaces](09-interface-contract-v1.md), [domain class](diagrams/01-domain-class-diagram.md), [state machine](diagrams/02-state-machine-diagram.md) and [sequence](diagrams/03-sequence-diagram.md); FR-001/003, purchase alternatives within FR-005, FR-011 and NFR-003/004/006/007/008/009. KAN-14 is based on saved original Jira evidence, not a fresh Jira state check. B/C ownership, all89 WBS fields, Stage1 materials and the separate A3 tutor decision remain unchanged.
