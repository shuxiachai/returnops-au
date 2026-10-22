# C F.01 technical review — 20 September 2026

Status: AI-assisted technical review completed with one low-severity fixture finding for A/C disposition; not Lucas's personal explanation/signature, A/B/C joint acceptance, F.01 Done, or runtime business-guard acceptance.

- Issue: https://github.com/shuxiachai/returnops-au/issues/10
- Jira / WBS: KAN-32 / F.01. Owner A; designated Reviewer C; B frontend consumer confirmation remains separately recorded.
- Exact review target: `3dd1ff637693a826990eee5712cfb239a3c3da7b` (F.01 rc.5; merged through PR #11 and present in main `da1a09fe7704bdb2fd2f989a44ab62bd7f089a41`).
- Source used: the environment agent's new pinned checkout at `sep20-pg17/source`, not the stalled September 18 cloud-placeholder checkout. Source files were only read; no product source, model, branch or GitHub/Jira item was modified by this review subtask.
- Authority read: AGENTS.md; docs/00, 07, 08, 09; contracts/README; current Issue #10; relevant MA-0.3/CS-0.2/AD-0.2 design clauses; schemas/examples and contract tests.

## Assessment

The six requested contract/design scopes are internally consistent in the reviewed material. No blocking wire-contract or safety-design contradiction was established. One concrete customer-facing fixture-content issue should be corrected by A before it is reused for UI demonstration or acceptance. This is not proof of runtime safety: the main application remains health/infrastructure-only, and the contract suite explicitly exercises artifacts and test-only oracles.

## Coverage and limits

All line references below refer to the exact source commit above, not a floating branch. Use `https://github.com/shuxiachai/returnops-au/blob/3dd1ff637693a826990eee5712cfb239a3c3da7b/<path>#L<line>`.

| Requested scope | Technical conclusion and precise evidence | Still required at runtime / acceptance |
|---|---|---|
| Source vs order conflicts | docs/09:129–147 keeps the complete original retrieval result, including uncited passages/conflicts, distinct from order lookup. docs/09:213–232 reserves OrderLookupBlock for accepted CONFLICT/AUTHORITY_DENIED and allows only manual handling of a current non-proposal target. tests/contracts/test_contract_v1_rc2.py:320–389 detects dropped conflicts and mismatched source/input/corpus links; rc3.py:37–152 checks source/target mismatch, target exclusivity, forbidden authority and preserved historical effects. | A must validate actual case/input/lookup identity and atomically store decisions/notification work; C1 must preserve real retrieval receipts and C2 assess semantic conflict impact. A schema-valid string is not evidence that the source actually conflicts. |
| Historical provenance and deletion | docs/09:312–327 specifies trusted ActorProvenance, immutable original review bundles, role-isolated history, frozen snapshots and deletion-over-replay precedence. rc4.py:109–173 rejects stale/rebuilt/duplicate citation material while allowing failed/zero-citation historical evidence; rc4.py:175–264 checks constructed pagination, tombstones and role-specific payloads; rc5.py:30–67 checks deleted accepted-receipt fixtures, including leaked text inside an otherwise valid error. | Real authorization, signed/server-held cursor binding, immutable persistence, atomic cleanup/cache behavior and zero-effect replay remain F.03/F.05/F.07/A1/A2 work. Synthetic page fixtures are not database pagination. |
| Capacity | docs/09:131–143 distinguishes per-review 100-item limits from lifetime history, requires full material preflight before current-proposal acceptance, prohibits silent truncation and retains old history on non-retryable REQUEST_TOO_LARGE. rc2.py:285–318 checks 21/100 versus 101 citations; rc4.py:175–198 checks 101 revisions across pages. Additional local probes check 100/101 statement and attachment array shape limits. | Actual atomic preflight, stage-correct technical failure, invalidation of old current references and preservation of accepted history need integration tests. Repeated synthetic entries in the added array-count probe test shape capacity only, not unique/valid business inputs. |
| Independent Risk hand-off | docs/09:122–147 requires packet, original statements, order snapshot, attachments, complete retrieval/conflicts and citation verification; no generator hidden reasoning. schemas.json:1352–1633 closes extra fields, binds required versions and constrains the five outcomes, RISK_REVIEWER role, warning/block/revision/question semantics. rc2.py:27–69/273–389 checks full origin-preserving hand-off and cross-object linkage. Added probes reject approval/command fields, ASSESSMENT role metadata and a hidden_reasoning extra field. | A must validate received version/source bindings; C must run a genuinely independent prompt/model invocation, not merely set role metadata. Semantic support, prompt injection, stale output rejection and five-way actual routing remain implementation obligations. |
| Known-label recovery | docs/09:238; docs/12:68–75/129–135; docs/14:114–118 consistently separate confirmed provider effect from saved local artifact. Original attempt stays EXECUTING without a public result, with durable receipt/artifact-only work; recovery retrieves/stores the original label and never creates it again. rc5.py:69–85 checks incomplete versus complete success shapes. The unadopted 1-based counter proposal remains unadopted. | Durable receipt/work transaction, current artifact-recovery authority, crash/claim recovery, expiry, content-retention rules and observed provider-effect counts must be tested in A2/F.04/F.07. Schema acceptance does not show that a provider call was prevented. |
| Notification outcome precedence | docs/09:240–242 and docs/12:72/119–121 require an accepted MANUAL_HANDLED/REJECTED outcome and its notification to survive late historical operation success/failure/unknown observations. Only a still-valid completed execution may create RETURN_CREATED; notification retry never repeats operations. docs/14:135 explicitly specifies the late-label/manual-outcome counterexample. | This was a design walkthrough, not an executed business transition. A2.05/.06 must test late callbacks during PENDING/FAILED/SENT manual/reject notification states, retain outcome/work identity and show zero duplicate return/label effects. |

## Finding C-F01-20260920-01 — customer-facing success fixture retains retry instructions

Severity: low / non-blocking for the wire-contract review; actionable fixture/UI demonstration correction, owned by A. No real customer incident or runtime failure is claimed.

- `contracts/v1/examples.json:1675–1679`: `notification-sent` is SENT but its message says “Notification delivery failed.” and its next step instructs the reader to resend the message.
- `contracts/v1/examples.json:3038–3040`: the same internal delivery/retry wording appears in `customer-history-outcome`, which is the safe, already-sent customer view.
- `contracts/v1/schemas.json:3645` describes CustomerOutcomeMessage as an already-SENT safe customer message, excluding retry/error metadata. docs/09:316 likewise limits this view to safe sent outcomes.
- Suggested fix: use a stable customer business-outcome message and actual customer next steps across initial delivery/retry/sent snapshots; keep transport failure and retry instructions in internal status/error/operator context. Update related synthetic history records together. Add a fixture semantic check that the already-sent customer sample contains no operator-only resend instruction.
- Do not “fix” this by changing the saved outcome from RETURN_CREATED or altering manual/reject precedence. Delivery state and business outcome remain independent.

## Actually executed evidence

Interpreter: the environment agent's fresh hash-locked `.venv/bin/python`, Python 3.12.14, with bytecode writes disabled (`-B`).

1. `python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v`: **58 tests passed**, 11.124 seconds, exit 0. This is a new local run, not reuse of an older CI receipt.
2. The extra-probe command below: **8 tests passed**, 0.037 seconds, exit 0.

```text
<hash-locked-python> -B docs/reviews/member-c-f01-probes-20260920.py <verified-pinned-checkout>
```

The additional script does not independently verify Git. The caller verifies the pinned checkout first; the script records the actual loaded artifact hashes below. A direct later Git/HEAD reread stalled due to local file availability during the initial review. This interruption is retained, not presented as a completed final check.

**Same-day verified retry:** the [F.02 evidence](member-c-pg17-reproduction-20260920.md) records an independent no-hardlinks Git checkout outside Desktop, exact `3dd1ff6`, clean initial/final status and passing object-integrity checks. The root agent reran this published eight-probe script against that checkout: **8 passed in 0.037 seconds**, with all three hashes below identical; the subsequent Git status was empty and HEAD still the exact target. This closes the source-availability verification gap without changing the initial run or claiming personal/joint acceptance.

| Artifact | SHA-256 of bytes used by the eight extra probes |
|---|---|
| contracts/v1/schemas.json | `8057d4569f470c0dc6933d5368dad5480291abfcaa2fb8950fe1b8fcf136a8c2` |
| contracts/v1/openapi.json | `da7a3fcb6fce889631689c4a3a18d6aeb6a8c09d10421cd248c823babe084ad6` |
| contracts/v1/examples.json | `6ebbf9c905397aa3f3824cfcfacd4338a14fe24d4b768fcca85ff57da11f0290` |

## Recommended publication wording and retained gates

“On 20 September, at C's request, an AI-assisted technical review of exact A `3dd1ff6` covered source/order conflicts, historical provenance, capacity, independent Risk hand-off, known-label recovery and notification outcome precedence. The local artifact suite passed 58/58 and eight focused artifact probes passed. No blocking contract/design contradiction was established; the customer-facing notification example needs the separately identified low-severity correction. This records the actual delegated technical scope only. It does not assert Lucas's personal explanation, A's personal understanding, A/B/C joint acceptance, live business-guard completion or course submission. F.01 remains open until the participants record their own confirmation and the accepted revision.”

Publishing this note does not merge PR #7/#17, check another person's acceptance box, replace the existing B frontend confirmation, change WBS ownership, or complete Stage 2 C1/C2/C3/evaluation work. F.02 Compose evidence is a separate record.
