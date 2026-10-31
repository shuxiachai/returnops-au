# Coordinator showcase (A1.06 extraction, advisory)

Owner: A Jingbo Chai. Work package A1.06 in the unchanged [work packages](08-delivery-work-packages.md) (Owner A, Reviewer C). This increment covers only the extraction half of A1.06: a model reads the customer's statements and returns typed facts, with the prompt and model versions kept. It does not deliver Coordinator clarification questions, A1.07, A1.08, a real C2 reviewer, E.09 or E.12; those remain deferred (KAN-39). Requirements FR-002, NFR-003, NFR-007, NFR-008, NFR-009, BR-008 and BR-012 in [docs/00](00-project-definition-v1.md). Models: the Coordinator operations `structure_request` / `prepare_clarification` in the [domain class diagram](diagrams/01-domain-class-diagram.md) (lines 397-398), the A11 connector in [docs/13](13-shared-composite-structure.md), and the class-diagram rule (line 527) that malformed or stale output or a failed invocation never becomes a fact or a state transition. This document records no acceptance by C or any other member, and no Gate 1 or Gate 2 acceptance.

## What it does

With `RETURNOPS_MODEL_SHOWCASE=1` the API starts one more background worker, `CoordinatorShowcaseWorker` in `packages/returnops_domain/coordinator_showcase.py`. Every 2 seconds it looks at the 50 most recently updated intake sessions whose status is `COMPLETE` or `AWAITING_CLARIFICATION` on an available case with an original statement, and handles at most 5 cases that have no result yet for their current input. For each case it runs three phases:

1. **Read.** Each case gets its own read-only `CustomerUnitOfWork` (shared fence, SELECT statements only, `lock_timeout` 500 ms). It first reads statement revision metadata only (record IDs, content hashes, retention state), the original requested outcome and whether an order reference exists, and computes the input digest. Stored results of the case for any older digest are retired at this point. Statement content is read, and each content hash verified through `history.read_revision`, only when the current digest has no stored result, lease or remembered failure. The unit of work is closed before the call. A case that cannot be read (an integrity failure, a lock timeout, a corrupt row) is skipped and counted; it never blocks the other cases. The input is capped at 20 AVAILABLE statements and 24000 characters in total; a larger case is not sent and yields no facts.
2. **Call.** With no database connection held, it sends the allow-listed input to the model through `ChatCompletionsTransport` (one total deadline, default 20 s, at most 50 s). Transport, timeout, HTTP 429 and HTTP 5xx failures are retried at most twice, after 1 s and 3 s; nothing else is retried. The 60 s claim lease is renewed before each attempt and again after the call.
3. **Check and keep.** If the stop flag is set the reply is discarded. Otherwise the reply must pass the acceptance chain below; a second short read-only unit of work recomputes the digest from metadata, and only an unchanged digest lets the facts into the in-process `CoordinatorAnnotationStore`. If that re-check cannot read the case (for example a lock timeout), the result is dropped and recorded as the transient failure `RECHECK_UNAVAILABLE`, which may be tried again after 10 seconds. Any unexpected error frees the lease at once.

Each pass also re-checks the metadata of cases that have stored facts but were not in that pass's scan, in a rotating window of up to 50 cases, and evicts every result whose digest is no longer current or whose case has lost its original statement. An accepted clarification or a retention removal therefore retires stored facts within a few passes even if nobody reads the case (at most 500 stored results / 50 per pass x 2 s, about 20 s), and the Founder read below checks again before anything is shown.

When the Founder reads `GET /v1/founder/cases/{case_id}`, `case_view` asks the store through `app.state.coordinator_facts`. It recomputes the digest from the current statements and requires every source revision recorded with the facts to be still AVAILABLE with the same content hash. Only then is `CaseView.facts` (the existing, optional contract field) filled. Otherwise the entry is evicted and the view is exactly what it is with the feature off. With the flag off (the default) the provider is `None` and the response is unchanged.

The input digest is `digest({statement_record_ids, content_hashes, original_requested_outcome, has_order_reference}, "coordinator-input/v1")` over the ordered AVAILABLE statement revisions. It does not include `input_version`, so an `ORDER_MATCHED` investigation result (which raises `input_version` without a new statement) keeps the facts, while an accepted clarification or a retention removal changes the digest and retires them.

## Acceptance chain

`parse_facts(reply, original_outcome)` accepts a reply only if all of these hold, in this order; the first failure is a closed code and no facts:

| Check | Failure code |
| --- | --- |
| The reply (at most 16000 characters) is JSON with no duplicate keys after trimming whitespace and removing at most one leading `<think>...</think>` block and then at most one surrounding fence of three backticks (optionally followed by `json`). That is the only tolerated wrapping: any other text, a second fence or think block, or a refusal written as prose is rejected | `MALFORMED_JSON` |
| It is a JSON object | `NOT_OBJECT` |
| It has no keys outside the six ExtractedFacts keys | `EXTRA_KEYS` |
| It validates as the contract `ExtractedFacts` | `SCHEMA` |
| `line_items` is `[]` (there is no order data to choose lines from; FR-002 forbids inventing them) | `LINE_ITEMS` |
| `possible_basis` is `UNDETERMINED` (the Coordinator does not decide rights, docs/00 section 4.1) | `BASIS` |
| `assessment_status` is not `SUPPORTED` | `SUPPORTED` |
| `customer_requested_outcome` equals the outcome stored with the original statement (BR-008) | `OUTCOME_MISMATCH` |
| `summary` has at least one visible character (a letter, digit, punctuation mark or symbol; since 30 October 2026 zero-width and control characters alone do not count) and is at most 1000 characters | `SUMMARY_LENGTH` |

The transport's own closed codes are `TRANSPORT`, `TIMEOUT`, `REDIRECT`, `HTTP_4XX`, `HTTP_429`, `HTTP_5XX`, `MALFORMED`, `NO_USAGE` and `TOO_LARGE`. Transient failures (`TRANSPORT`, `TIMEOUT`, `HTTP_429`, `HTTP_5XX` after their retries) may be tried again after 60 seconds, `RECHECK_UNAVAILABLE` after 10 seconds. Every other failure, including every acceptance-chain code, is remembered for that input digest until the API process restarts, so the same input is not sent again. To retry the same input, restart the API, or run the CLI (`tools/model_showcase/run_once.py`), which uses its own store; a new clarification produces a new digest and is tried normally.

## Provider record

The items the [C2 candidate README](../experiments/c2_risk_candidate/README.md) (lines 100-108) asks to record before real calls:

| Item | Record |
| --- | --- |
| Provider | The course's campus AI API proxy (Lab 9: campus Qwen model). Its connection guide is not in the repository; base URL, VPN/proxy needs and quota are unknown until the lead supplies them. `RETURNOPS_MODEL_PROVIDER_ID` names the provider record (contract `Id`). |
| Model | `RETURNOPS_MODEL_ID` (at most 120 characters); the exact campus model name is pending. |
| Dialect | `chat-completions` only: the chat-completions JSON dialect used by common model gateways. `POST {base_url}/chat/completions` with `model`, `temperature: 0` and two messages (system, user), `User-Agent: returnops-au-coordinator/1`. Assumed, not yet confirmed for the campus proxy. `response_format` is not sent. |
| Usage shape | `usage.prompt_tokens` and `usage.completion_tokens` must be non-negative integers; a reply without them is `NO_USAGE` and is never counted as zero. |
| Permitted fields | See the allowlist below. |
| Deadline and errors | One total deadline (`RETURNOPS_MODEL_DEADLINE_SECONDS`, 1-50, default 20, below the 60 s claim lease) over connect and read; response body at most 256 KiB; closed codes only, raised without request or response text. A model refusal is not a code of its own: it fails the acceptance chain as `MALFORMED_JSON`. |
| Adapter owner | A (`ChatCompletionsTransport` in `packages/returnops_domain/model_transport.py`, urllib only; no runtime HTTP dependency was added). |
| Call and budget permission | Lead decision, 22 October 2026 (see the dated decision below). The campus quota and cost limits are unknown. |
| Credentials | `RETURNOPS_MODEL_API_KEY` from the environment only, held as a `SecretStr`; never in files, Git, arguments, logs, errors or evidence. |

## Second provider on Railway (31 October 2026)

The course proxy is reachable only through the university VPN, so the Railway service cannot use it. The lead decided on 31 October 2026 to run the showcase on Railway with Alibaba Cloud Model Studio (Bailian, China site, Beijing) through its chat-completions compatible endpoint, on the lead's own free quota:

| Item | Record |
| --- | --- |
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` (Railway service variable `RETURNOPS_MODEL_BASE_URL`) |
| Model and provider | `qwen-plus`; provider record `aliyun_bailian` |
| Key | `RETURNOPS_MODEL_API_KEY`, set by the lead as a Railway service variable; never in Git, files, chat, logs or evidence |
| Switch | `RETURNOPS_MODEL_SHOWCASE=1` on the service; `tools/railway/start.py` passes `--model-showcase` only when the model variables are complete and valid, and otherwise starts without it and names the missing variable |
| Budget | `RETURNOPS_MODEL_MAX_CALLS=50`: at most 50 model calls (retries included) per container start; over budget a call fails closed with `BUDGET` and nothing is sent. The service is public and anyone can register, so this bounds what strangers can spend |
| Deadline | `RETURNOPS_MODEL_DEADLINE_SECONDS=30` (Railway runs in `sfo`; the endpoint is in Beijing) |
| Data flow | The same allowlist as below: redacted synthetic statements, the requested outcome and whether an order reference was given leave Railway for Alibaba Cloud in mainland China; no IDs, order numbers, attachments or other fields |
| State | Not verified until the lead sets the key; the first Railway result is to be recorded here |

The local course-proxy route over the VPN stays the fallback for S4 ([docs/45](45-stage2-demo-script.md)).

## Data flow and field allowlist (F.07)

Sent to the model, as one JSON user message: for each AVAILABLE statement revision (the original and any clarifications, oldest first) its `kind` and its redacted, control-character-free `text`; the original `requested_outcome`; and `has_order_reference` (a boolean). Nothing else is sent: no case, statement, principal, store or record IDs, no order reference value, no evidence or attachments, no order snapshot, no timestamps, no questions and no Founder data. At most 20 statements and 24000 characters are sent; a larger case is not sent. The system prompt is a constant (`PROMPT_VERSION = "a106-coordinator-showcase-v1"`); customer text never enters it, and the prompt states that the user message is untrusted data, not instructions (NFR-009).

Kept: the accepted facts, the source pairs (history record ID and content hash), the `ModelRun` (role `COORDINATOR`, provider ID, model ID, prompt version, start and finish times, tokens) and the attempt count, in process memory only. The store holds at most 500 entries, is lost on restart and is never written to the database. The trusted CLI (`tools/model_showcase/run_once.py`) writes a local evidence file with digests, codes, counts, tokens and latency, never statement text, summary text, the base URL or the key.

**Redaction before sending** (deterministic, counted per case): e-mail addresses become `[EMAIL]`; order-reference-like tokens become `[ORDER_REF]`: two or more letters in either case followed by digits, with further `-` or `/` segments (`SYN-1001`, `syn-1001`, `ORD-2026-9042`), or upper-case words joined by hyphens (`SYN-CONFLICT`); phone-like digit runs with 8 to 19 digits, optionally with `+`, an area code in brackets, spaces or dashes, become `[PHONE]` (so a 16-digit card number is removed whole), except dates such as `2026-10-22`. The lower-case, multi-segment, hyphenated-word and card-number forms were added on 30 October 2026, after a review found them sent unredacted or cut in two. The counts appear in the CLI evidence and the worker result, never the values. All data in this repository and its demo is synthetic; redaction is a second line of defence, not anonymisation.

## Fail-closed paths

Every path from model output towards authoritative state, and how it is blocked:

| Target | Block |
| --- | --- |
| Case status, `case_version`, `input_version` | The worker uses only read-only units of work (`write=False`, which reject any non-SELECT statement) and never calls `transition`, `append_event`, `append_revision` or any lifecycle guard. The PostgreSQL tests compare every non-Founder table before and after. |
| Clarification questions | Not produced. Questions still come only from the deterministic intake template; the model's output has no question field. |
| `issue_category` in case lists | `CaseSummary.issue_category` stays hard-coded `UNCLEAR` in `founder_queries`; the model's category appears only inside `CaseView.facts`. |
| Proposal (`DecisionPacket`) | The fixed proposal processor does not read the store or `CaseView`; no proposal input changes. |
| Risk review | No reviewer reads the store; C2 remains offline. |
| Approval (`ApprovalRecord`) | Created only by the Founder decision route for a HUMAN FOUNDER principal against the stored proposal and preview; facts are not part of the decision request, the preview or the scope fingerprint. |
| Execution and notification | The operations services read approvals, previews and their own ledgers only; the worker holds no provider port. |
| Customer view | `CustomerCaseView` has no `facts` field and the customer reads use `history.case_view`, which is unchanged: customers never see model output. |
| Audit chain | No event is written (see below). |
| Founder reading the summary | The summary is at most 1000 characters and must be presented as advisory; it can contain text aimed at the Founder ("approve this"), which grants nothing. |
| Any failure or stale result | No facts; the Founder view is the feature-off view. |

## Audit event: withheld

Design v2 planned one MODEL-actor audit event per result (`COORDINATOR_FACTS_RECORDED` / `COORDINATOR_FACTS_REJECTED`, `history_refs=[]`, hash-only payload) and required withholding it if any guard compares `audit_sequence` across transactions. Such a guard exists, so no event is written:

- `label_artifact_sources.capture_current_artifact_context_0013` (lines 180-185) stores in the label-artifact claim a hash of the whole `case_heads` row (`claimed_head_hash`, which includes `audit_sequence` and `audit_head`) and a hash of the case's source closure (`claimed_source_snapshot_hash`, which includes the `customer_audit_events` rows).
- `label_artifact.py` `_claim` (line 163) records that claim in one transaction; `_complete` (line 220) runs in a later transaction, after the PDF retrieval, and calls `current_claim` (line 227), which recomputes both hashes and rejects on any difference (`label_artifact_sources.py` lines 206-222).

An audit event appended to the same case between those two transactions would make the label completion fail. The worker can reach any eligible case at any time (for example after a restart, when the store is empty), so this cannot be excluded without new status rules. `CaseProof` (`founder_integrity.py` lines 46-76) and the MODEL actor check in `founder_history_types.py` (lines 84-86) would have accepted the event; the cross-transaction claim hash is the only blocker found. Consequence: the only persistent trace of a model run is the CLI evidence file; `ModelRun` metadata is not visible in the Founder audit page.

## Gate position and the lead's decision

The Gate texts, with line numbers (the docs/08 lines are Chinese in the original; the English here is a translation and the original lines are authoritative):

- docs/00 line 765, Gate 1: "Before connecting an LLM, demonstrate:"
- docs/08 line 52, A1.08 acceptance: "AI output is connected to the executable system only after Gate 1 safety acceptance."
- docs/08 line 242, Gate 1 row: "Before R.02 passes, an LLM must not be connected to an execution chain that can trigger simulated operations; offline AI without execution authority may proceed in parallel."

R.02 and Gate 1 are not accepted ([docs/41](41-r02-end-to-end-evidence.md)).

**Dated decision, 22 October 2026.** The lead (A, Jingbo Chai) decided to build this default-off, advisory showcase before R.02 and Gate 1 are accepted, as an exception, in the form of the R.02 exception in docs/41. The condition in docs/00 line 765 is not met and is not claimed to be met. This showcase makes no claim of consistency with Gate 1 and is not Gate 1 acceptance; it does not implement or satisfy A1.08 (docs/08 line 52). It is not A1.06, R.02, Gate 1 or Gate 2 acceptance, a review by C or a Jira status change, and the docs/08 table is unchanged.

The only boundary argued is docs/08 line 242:

- **No execution authority.** The worker has no proposal, decision, approval, preview or operations port, and only read-only database access. Its output reaches one read field, `CaseView.facts`, which no service consumes.
- **No guard path.** It never calls a lifecycle guard, a state transition or an audit/history writer, so it cannot change which guard decisions are possible.
- **No ApprovalRecord path.** Approval needs a HUMAN FOUNDER principal through the decision route; nothing in the showcase writes or feeds an `ApprovalRecord`.

The showcase does call a network model, so it is not "offline" in the literal sense of that line; the lead's decision covers that difference.

## Configuration

| Name | Meaning |
| --- | --- |
| `RETURNOPS_MODEL_SHOWCASE` | `0` (default) or `1`, exactly like `RETURNOPS_FIXED_PROPOSAL_DEMO`; anything else fails startup. `create_app(enable_model_showcase=...)` takes a boolean for tests. |
| `RETURNOPS_MODEL_BASE_URL` | Required when on. https only, no userinfo, query or fragment. Plain http is accepted only for an RFC 1918 IPv4 address with an explicit port, and only with `RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP=1`. |
| `RETURNOPS_MODEL_API_KEY` | Required when on. Secret. |
| `RETURNOPS_MODEL_ID` | Required when on. At most 120 characters. |
| `RETURNOPS_MODEL_PROVIDER_ID` | Required when on. Contract `Id`. |
| `RETURNOPS_MODEL_DEADLINE_SECONDS` | Optional, 1-50, default 20. |
| `RETURNOPS_MODEL_DIALECT` | Optional, only `chat-completions`. |
| `RETURNOPS_MODEL_PROXY_URL` | Optional explicit `http(s)://host:port` proxy. Without it no system proxy is used. |
| `RETURNOPS_MODEL_MAX_CALLS` | Optional, 1-100000. At most this many model calls (retries included) in the process; over it a call fails closed with `BUDGET` before anything is sent. Added on 31 October 2026 for the public Railway service. |
| `RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP` | Optional, `0` (default) or `1`. `1` lets the base URL be plain http to a private IPv4 address (10/8, 172.16/12, 192.168/16) with a port. Added on 22 October 2026 because the course's ELEC5620 API Proxy is published as `http://10.x.x.x:8000/v1`, reachable only through the university VPN, which carries the traffic; the key still goes only to that address and never to a public or loopback http URL. |

With the flag on, missing or invalid settings stop startup with a message that names the variable but never its value. The worker starts only when the API also starts its other processors (an auth configuration is present and `enable_processor` is true); it is stopped last at shutdown, in its own `try`, and `stop()` returns within one second without waiting for an in-flight model call, whose reply is then discarded. `demo.py serve --model-showcase` sets only the flag; there is no key argument. `compose.yaml` passes the variable names, without values, to the `api` service only, not to the shared anchor that `migrate` also uses.

## Logs and counters

The worker writes one fixed-format line per outcome through the standard `logging` module, logger `returnops_domain.coordinator_showcase`:

```text
coordinator_showcase outcome=<RECORDED|REJECTED|FAILED|STALE|STOPPED> failure_code=<code or -> attempts=<n> digest=<first 12 hex> latency_ms=<ms or ->
```

`RECORDED`, `STALE` and `STOPPED` are logged at INFO, failures at WARNING; an unexpected error is logged as `outcome=ERROR` or `outcome=PASS_ERROR` with fixed text only. No line contains statement text, summary text, the URL, headers, the key or a full digest. `demo.py serve` runs uvicorn at log level `warning`, so by default only failures reach the console. For the demo, `app.state.coordinator_showcase.counters` returns a copy of the counts since start: `recorded`, `stale`, `stopped`, `skipped` (unreadable cases), `errors`, `failed` (per failure code) and `last` (outcome, code, attempts, digest prefix).

## Tests

- `tests/founder/test_coordinator_showcase_offline.py` (no database, no network model): settings validation and secret hygiene; the transport with an injected opener (success shape, unredirected `Authorization`, the error and response matrix, size cap, total deadline) and with owned loopback servers (a refused redirect that the key never follows, an ignored system proxy, status codes, oversized and stalled responses); the retry matrix; the acceptance chain and the one tolerated think block and fence; redaction and the constant system prompt; store bounds, leases and thread safety; digest and projection rules; the three worker phases over an in-memory read-only fake; stop latency; log lines and counters; a corrupt case skipped without blocking others; lease release after an unexpected error; scan-time retirement without a Founder read and no content read for a stored digest; the 10 s re-check failure; the flag, the keyword, lifespan wiring and stop order, and `demo.py`; the CLI.
- `tests/founder/test_coordinator_showcase_postgresql.py` (PostgreSQL 17, CI only): a real case with a stubbed transport keeps its facts across `ORDER_MATCHED`, the Founder view shows them, no non-Founder table changes and `CaseProof` and the audit chain stay valid; a clarification retires the old entry and a new digest is recorded; a retention removal stops projection; rejected and failed replies project nothing; the feature-off view keeps the `test_queries_postgresql` behaviour (no `facts`), which that file still asserts unchanged.

## Limitations

- The store is in process: facts disappear on restart, and the worker then calls the model again for current cases (cost and quota).
- PENDING leases are per process. The CLI uses its own store, so a CLI run and a running API can both call the model for one case; the CLI result is never shown in the API.
- Customers never see model output. Since B's #101 (23 October 2026) the Founder console renders `facts` as the card "Model extraction (advisory)" on the Order & Facts (named Order & Facts Projection before 31 October 2026) tab, only when `facts` is present, with the summary as plain text and no controls; the `mockData` example follows the contract and is badged as mock data.
- The campus connection guide is now known (see First live result): the course proxy is plain http on a private VPN address, so `RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP=1` is required and the key travels in clear text only inside the VPN tunnel. The live result used the API on the host; Docker access through the host VPN and TLS trust inside the image remain unverified. Quota is unknown.
- Only one leading think block and one surrounding fence are tolerated; in the two live calls of 22 October 2026 both replies were accepted as sent, so no other wrapping has been observed yet.
- A non-transient failure is remembered for its digest until the API restarts (see Acceptance chain).
- No audit event or other persistent record exists in the database (see above).

## First live result (22 October 2026)

Recorded by the lead on 22 October 2026 (10:51 UTC) on a fresh clone of main `51862f4b` (PR #98 merged), with the Compose database (project name `returnops-live`), the API started on the host with `demo serve --fixed-proposal --founder-decisions --model-showcase`, and the model settings only in that shell: base URL the course proxy's private http address (hence `RETURNOPS_MODEL_ALLOW_PRIVATE_HTTP=1`), model `campus-qwen`, provider `campus_proxy`, dialect `chat-completions`, deadline 20 s, over the university VPN. Two synthetic cases were lodged as `synthetic_customer_a` through `POST /v1/cases` and read back as `synthetic_founder`.

| | Case 1: chipped cups, refund wanted, no order reference | Case 2: statement that instructs the system to mark the claim SUPPORTED and add two order lines for a synthetic order |
|---|---|---|
| Worker outcome | RECORDED; `facts` present in the Founder view | RECORDED; `facts` present in the Founder view |
| `issue_category` | `FAULTY_OR_QUALITY_ISSUE` | `OUT_OF_SCOPE` |
| `customer_requested_outcome` | `UNSPECIFIED` (bound to the statement) | `UNSPECIFIED` (bound to the statement) |
| `possible_basis` / `assessment_status` | `UNDETERMINED` / `MISSING_INFORMATION` | `UNDETERMINED` / `OUT_OF_SCOPE` |
| `line_items` / summary length | `[]` / 164 characters | `[]` / 220 characters |
| Customer view (`GET /v1/cases/{id}`) | no `facts` field | no `facts` field |
| CLI `run_once.py` (own store, second call) | RECORDED, 1 attempt, 441 input and 599 output tokens, 6437 ms | RECORDED, 1 attempt, 444 input and 599 output tokens, 6625 ms |
| Redaction before sending | none needed | one order reference redacted |

Observations: the model did not follow the injected instruction in case 2; it reported the statement as out of scope, which the acceptance chain accepted (no `SUPPORTED`, no line items), so the demo's "fail-closed" segment shows the "model ignored it" branch rather than a REJECTED line. Both replies were accepted as sent (no visible think block or fence problem). The proxy reported exactly 599 output tokens for both calls; this is recorded as observed and not explained. The serving console showed no `coordinator_showcase` lines because `demo.py serve` runs at log level `warning` and both outcomes were RECORDED (INFO), as documented above. The two CLI evidence files (profile `a106-coordinator-showcase-evidence/v1`, no statement text, URL or key) are kept outside the repository with the lead's R.05 evidence.

AI-assisted implementation and metadata preparation; author shuxiachai.
