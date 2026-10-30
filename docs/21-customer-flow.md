# Customer flow and private demo

This candidate starts at main `4fcfa25047f5f07cfe89e77cdb72d20c1e5a65dd` after the separately authorized PR22 merge. Issue #23 covers this customer slice; it references #5 and #10 without closing the baseline or claiming A1 as a whole accepted. KAN-14 is the existing recorded A1.01–03/F.05 mapping, not a fresh Jira state check. The frozen `contracts/v1` schemas/OpenAPI, original WBS and B/C model text remain unchanged.

## Implemented operations

| Operation | Response |
|---|---|
| `GET /v1/session` | Current authenticated principal |
| `POST /v1/evidence` | 201 staged JPEG/PNG/PDF metadata |
| `GET /v1/evidence/{evidence_id}/content` | Current authorized original bytes, no-store, constant attachment header |
| `POST /v1/cases` | 201 original SUBMITTED case/version1/input1 receipt |
| `GET /v1/cases/{case_id}` | Current customer view and registered collection windows |
| `GET /v1/cases/{case_id}/history` | Scoped stable history page or retention tombstones |
| `POST /v1/cases/{case_id}/clarifications` | 202 exact admitted supplement receipt |

Only the two existing health operations accompany these seven routes. There is no public login/issuer, role selector, Founder case API, provider or LLM endpoint. Missing private authentication configuration fails closed with503. The app does not provision identities or migrate databases at startup.

## Acceptance and processing

Create and clarification admission save the immutable original statement or individual clarification answers, evidence binding, case/input versions, case-owned intake session, durable work, history, audit and original receipt in one transaction. The original201 stays SUBMITTED/version1 even after processing. Clarification admission advances case/input, replaces a remaining question set with a new ID bound to the new input, and stores its own202. Replay returns that original receipt without creating work or changing business state.

A lifespan-owned polling thread claims persisted PENDING or expired-lease work in a fenced transaction, computes outside the transaction and rechecks policy/content/claim/input/version in a separate result transaction. Claims have random tokens, increasing epochs and30-second leases. Multiple processes serialize through PostgreSQL. Scheduling alone changes no business version; a committed result advances case version, not input version. Startup resumes persisted work; GET never triggers processing. Stop waits at most5seconds, with bounded lock waits and API database statement timeouts.

Accepted work uses SERVICE authority `deterministic-intake-v1`, not the original HTTP JWT. Session expiry/revocation denies new HTTP access without canceling already accepted input. Disabled accounts, changed store/owner, removed/corrupt input or unavailable receipts pause work without consuming a technical failure budget. Two actual deterministic computation exceptions exhaust a separate local budget and persist a sanitized COORDINATOR ProcessingFailure plus ESCALATED state. It does not send notifications or create Founder approvals.

The deterministic policy checks only structural collection: an explicit order reference or currently authorized bound file means material is available for further investigation. Without either, it asks for an order reference or alternative purchase context. A nonblank answer or relevant new file can satisfy this collection question. Since 31 October 2026 "blank" means no visible character: a statement, an answer or an order reference made only of spaces, control or format characters (such as zero-width spaces) is refused with 422, where `str.strip()` used to let the invisible ones through; a blank order reference used to be looked up and reported as not found. It never verifies purchase, invents extracted facts, or marks a case COMPLETED. Multiple-question partial handling retains remaining question IDs/text and does not impose a three-round cap.

## Storage, authority and privacy

Migration0003 adds customer heads/identities/sessions, acceptance facts, separate receipts, evidence, history, registered snapshots/cursors, intake sessions/work and processing failures. Migration0004 adds an internal principal/evidence audit chain for events before a case exists. The three0002 tables retain their meanings as immutable initial facts. Existing rows are imported with actual migration-time SERVICE provenance; no customer acceptance, identity, JWT or intake work is fabricated for legacy data. Downgrades require a separate data plan.

Every supported write, including trusted registry and legacy storage writes, takes the same transaction advisory fence. Customer operations use READ COMMITTED and reread current F.03 identity/resource authority after acquiring the fence and before commit. Snapshot/cursor-registering GETs take the exclusive fence but change no case/input/business audit/work. Pure reads use a shared fence. This coarse serialization is intentional for the small demo; it is not a high-throughput architecture.

Idempotency scope is principal/method/operation/target/key. Current authority precedes fingerprint conflict, which precedes receipt availability and fresh state guards. Retained exact receipts are separate from permanent acceptance facts. Removed receipts return explicit nonretryable INVALID_STATE; they never recreate accepted content. Unknown commit outcomes reconcile the same key under a new fenced transaction; absent/uncertain facts return503 while preserving the original key. Illegal current-state/version transitions are rejected with a safe audit event and no accepted receipt/work/partial revision.

Private typed canonical storage encodes JSON values with versioned tags, lengths and UTF-8 surrogatepass. Standard JSON-decoded strings round-trip, including NUL/lone surrogates/combining characters/whitespace. Integral JSON numbers such as2,2.0 and2e0 normalize identically using decimal parsing without rounding; fractional/nonfinite/out-of-range versions are rejected. This does not preserve original JSON escape spelling. HTTP JSON has a4MiB cap, accommodating the maximum20×12000-codepoint clarification in normal ASCII-escaped form while bounding redundant padding.

Attachments use actual Pillow JPEG/PNG verification/full decode and pypdf strict graph/content-stream parsing in a separate process with an8-second wall watchdog,4-second CPU quota and384MiB memory cap. Parser limit setup fails closed. Metadata is display-only, never a path or response filename. Maximum file bytes are10MiB; upload streaming caps actual bytes regardless of Content-Length, bounds part/header/description data, allows two in-flight uploads per API process and applies a30-second stream deadline. Multiplying API worker processes multiplies this documented concurrency budget. Parser workers receive a stripped environment and no request identity. These controls are bounded parsing, not malware scanning, file sanitization or a complete OS security sandbox.

Ordinary errors are static ErrorEnvelope values; correlation headers match their envelopes. Customer responses use escaped JSON. The controlled demo and container disable access logs so cursor query strings do not enter ordinary logs; each multipart parser suppresses only its own raw-byte diagnostics. SQLAlchemy hides parameters. Reverse-proxy or infrastructure logging must preserve this boundary when deployed.

History snapshots freeze membership/highwater/as-of/case version. Previews contain the latest available revision per object (up to100) and retain the readable ORIGINAL. Totals count all revisions including unavailable ones; full history is reachable through registered scoped cursors. Removal changes existing snapshots into tombstones without replacing old content hashes. The internal RetentionService accepts explicit object IDs and atomically removes current bytes/history bodies/affected receipts, updates availability and audit, and pauses work. There is no public deletion endpoint or ownership-transfer-with-purge feature. Tests/demo use only synthetic data.

Audit events bind row/body identity and scope, sequence, previous hash and typed payload hash. The pre-case chain is internal and separate from public case AuditEvent. Hash chains detect checked inconsistencies, not a privileged DBA rewriting every row without an external anchor.

## Reproduce locally

Use an activated **isolated** Python3.12 environment. Do not install into a shared developer environment. Install the committed hash locks, then the package without dependency resolution:

```powershell
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
```

Supply `DATABASE_URL` privately for an explicitly owned disposable PostgreSQL17 database named `returnops_f02` or `returnops_f02_*`. The existing environment helper can read a private env file without printing credentials:

```powershell
python tools/environment/local.py --env-file <absolute-private-env-file> run python -B tools/checks/run.py environment
```

That environment group migrates, tests the32 environment checks,74 initial-storage checks and the complete customer suite. CI also runs244 F.03 checks,68 existing contracts, model/static/tool checks, outside-checkout wheel imports and the runtime image. On Windows, choose a new task-owned `--basetemp` when a shared pytest temp folder is inaccessible; do not change shared ACLs. Run contract/model checks against the actual base commit for the WBS comparison.

For a private synthetic demo, explicitly provide three distinct IDs and a store. Windows demo issuance requires Python3.12.4 or later and rejects earlier versions before creating a directory or generating credentials, because [private0700 directory handling was added in3.12.4](https://docs.python.org/3.12/library/os.html#os.mkdir). The output directory must be new and absolute; use an ignored `data/private/` or `tmp/` location and keep its inherited filesystem permissions private. No credential appears in a command argument or stdout:

```powershell
python -m returnops_api.demo provision --private-dir <new-absolute-private-directory> --store store_demo --customer-one customer_demo_one --customer-two customer_demo_two --founder founder_demo
python -m returnops_api.demo serve --auth-file <absolute-private-directory>/auth.json --port 8000
```

The provision command requires the private database environment. It generates independent high-entropy signing bytes and short-lived registered sessions (at most15minutes); `sessions.json` holds tokens for a private client. Read tokens into memory rather than pasting them into shell commands or logs. The service listens only on127.0.0.1 in this demo mode. Use a new explicit registration after expiry; do not overwrite previous private files or infer an outcome after an uncertain registration.

A normal customer run reads session, uploads optional evidence, submits a case, reads the current view/history, submits answers against the current question set/version and reads the accepted result. Processing is asynchronous; the201/202 admission view and later GET can legitimately differ. This slice ends at structural intake/UNDER_INVESTIGATION. No purchase verification, assessment, Founder decision, return label, notification delivery, A3 integration or course/team acceptance is claimed.
