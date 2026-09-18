# Member C — focused F.01 rc.5 technical review

Date: 2026-09-12 (Australia/Sydney)  
Delivery context: [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32) / [Issue #10](https://github.com/shuxiachai/returnops-au/issues/10) / [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)  
Related model evidence: [KAN-13](https://lucastaooo.atlassian.net/browse/KAN-13)  
Reviewed source: **`64582a3007fea0fa3d1b1c3c212168b96af6b607`**, branch `fix/10-kan-32-contract-review`; F.01 rc.5 / MA-0.3 / CS-0.2 / AD-0.2.

This is **AI-assisted technical-review preparation for C (`lulucas-tao`)**,
not C's personal signature, a GitHub approval, A/B confirmation, F.01/F.02
acceptance or a runtime-safety certificate. The reviewed source is an exact
downloaded GitHub archive, not a local Git checkout. This newly added review
is not part of that source SHA. No A/B artifact was edited during this review.

## Result and scope

**One reproducible test-oracle/fixture defect was found: C-F01 below.** A should
correct and rerun the historical-bundle checks before citing them as evidence
of full material binding. No running-service exploit or failed business guard
is claimed: those services are not implemented here. The rc.5 deletion/replay
and known-label recovery corrections are expressed consistently in the focused
hand-off, schema, shared class and A operation/recovery paths. This is a bounded
review, not a claim that the entire project is defect-free.

The review covered C1/C2/C3 hand-off shapes, source provenance, full conflict
propagation, independent Risk input, capacity failure, the five Risk outcomes,
role-isolated history, receipt deletion, and known-label/artifact recovery.
It also compared the corresponding shared Composite ports and A's design
decisions. It did not implement or run the planned business HTTP operations,
LLM calls, retention service, provider ledger or concurrency guards. F.02
health-environment reproduction is separate evidence.

Line references below refer to the reviewed source SHA, not later revisions.

## Focused checks

| Check | Reviewed source location | Technical result and remaining proof |
|---|---|---|
| C-R01 — source identity without invented publication version | `contracts/v1/schemas.json:730`; `docs/09-interface-contract-v1.md:145` | PolicyPassage requires source type, URI, access date, source_version (string or explicit null), corpus version, location, exact-content SHA-256, retrieval time and synthetic flag. Store policy and reviewed guidance are distinct. Runtime C1 must verify bytes and reviewed-corpus membership; a URI is not evidence of legal correctness or permission to fetch it. |
| C-R02 — preserve complete retrieval and conflicts | `contracts/v1/schemas.json:846`; `docs/09-interface-contract-v1.md:129`; `docs/13-shared-composite-structure.md:105` | Risk has one required retrieval_result, not an alternative top-level passages list. MATCHED requires passages; NO_MATCH has none but still carries conflicts and provenance. A15/A19 preserve the original result independently of generator prose. NO_MATCH is not a technical exception or automatic PASS. |
| C-R03 — independent review material and trusted acceptance | `contracts/v1/schemas.json:1352`; `docs/13-shared-composite-structure.md:103`; `docs/13-shared-composite-structure.md:111`; `docs/14-member-a-design-decisions.md:101` | Required packet/statements/evidence_matrix/order_lookup/attachments/retrieval_result/citation_verification and optional image observations are visible. The matrix is a claim to audit, not trusted evidence. Raw source receipts require Domain binding checks before use. CS-02 has Orchestrator→Reviewer, not Assessment→Reviewer, and no Risk→effects or repository port. Actual independent prompt/invocation and cross-object consistency remain C2/A1 tests. |
| C-R04 — citation coverage versus semantics | `contracts/v1/schemas.json:926`; `contracts/v1/schemas.json:994`; `tests/contracts/test_contract_v1_rc2.py:29`; `docs/09-interface-contract-v1.md:133` | Retrieval passages, packet citations and verification checks support the same 100-item maximum. The valid-fixture oracle checks original retrieval equality, IDs/versions/hashes, exact citation coverage and evidence bindings. C1 checks resolvability; C2 must separately test whether a source supports the actual claim and how conflicts affect it. The test oracle is not an application guard. |
| C-R05 — complete inputs before current proposal admission | `contracts/v1/schemas.json:1354`; `contracts/v1/schemas.json:3565`; `docs/09-interface-contract-v1.md:139` | Domain constructs the complete bounded historical bundle before atomically accepting the candidate proposal. Internal capacity is not lifetime-history capacity. Exceeding any necessary DTO capacity must stop with actual-stage non-retryable REQUEST_TOO_LARGE, preserve accepted input/history and create no new current proposal. Preview truncation cannot be used as Risk input truncation. This failure path still needs runtime verification. |
| C-R06 — exactly five non-authorising outcomes | `contracts/v1/schemas.json:92`; `contracts/v1/schemas.json:1406`; `docs/09-interface-contract-v1.md:196` | PASS permits INFO only; PASS_WITH_WARNING requires a WARNING and excludes BLOCK. Both exclude revision requests/questions. REVISE requires a revision request, NEEDS_INFORMATION a question, ESCALATE a BLOCK finding. The reviewer cannot approve or execute. Invalid JSON, timeout and port errors are technical failures, not a sixth outcome or PASS fallback. Semantic consistency and actual routing remain C2/A1/A2 responsibilities. |
| C-R07 — C3 is a bounded observation capability | `contracts/v1/schemas.json:1634`; `contracts/v1/schemas.json:1660`; `docs/14-member-a-design-decisions.md:113` | Input uses allowed evidence IDs and case/input binding; output preserves evidence ID, visible observations, limitations, confidence and component version. No arbitrary path/URL, token, legal decision or new AI business role is introduced. Real attachment access/content validation belongs to A's F.04/F.07 services; C must still test blur, irrelevance and image-text injection. C3 remains selected course work, not cancelled by its optional run-time multiplicity. |
| C-R08 — exact historical review evidence and role separation | `contracts/v1/schemas.json:3565`; `contracts/v1/schemas.json:3693`; `contracts/v1/schemas.json:4338`; `docs/09-interface-contract-v1.md:314` | The specified proposal history bundle retains the original complete review input; a review points to its proposal record. Founder and Customer history use separate finite kinds/content, with tombstones rather than arbitrary payloads. Source evidence must not be rebuilt from the latest corpus. **C-F01 finds that the historical test oracle does not fully check this binding.** Immutable snapshot pagination, per-page authorisation and coordinated deletion remain unimplemented runtime requirements. |
| C-R09 — accepted POST replay after allowed deletion | `docs/09-interface-contract-v1.md:181`; `tests/contracts/test_contract_v1_rc5.py:15`; `docs/diagrams/member-a/exact-scope-sequence.puml` | Same-key/same-body preserves the acceptance/deduplication fact. Unavailable receipt content yields 409 INVALID_STATE, retryable=false, without removed text, new work or automatic new key. Different body still conflicts and every replay reauthorises. The rc.5 oracle detects removed text even inside a shape-valid error. This is fixture evidence, not tested live retention or zero-side-effect behaviour. |
| C-R10 — known label effect is not an unknown effect | `contracts/v1/schemas.json:2482`; `docs/diagrams/member-a/operation-attempt-state.puml:34`; `docs/diagrams/member-a/recovery-notification-sequence.puml:31`; `docs/13-shared-composite-structure.md:122` | Provider success without a saved local label keeps EXECUTING, no result, with a durable original-effect receipt and artifact-only work. Recovery reads/stores only the original label; it cannot create a new effect, claim FAILED, or erase the fact as UNKNOWN. Complete Domain persistence including label_evidence_id is required before SUCCEEDED. The original creation expiry does not confer recovery authority: current restricted access, binding, claim and retention still apply. |
| C-R11 — manual/rejection outcomes survive late effects | `docs/09-interface-contract-v1.md:240`; `docs/diagrams/member-a/recovery-notification-sequence.puml:84`; `docs/12-member-a-model-chain.md:172` | Historical reconciliation updates effect facts/audit but must preserve the accepted MANUAL_HANDLED/REJECTED outcome and notification identity. Notification retry cannot replay CREATE_RETURN or GENERATE_LABEL. Two historical successes alone do not justify COMPLETED. Actual late-result/concurrent-notification tests are still required. |
| C-R12 — evaluation denominator and ownership stay distinct | `docs/09-interface-contract-v1.md:278`; `docs/09-interface-contract-v1.md:294`; `docs/08-delivery-work-packages.md:190` | Analytics use one created-at/status cohort at as_of; current input's latest episode is measured, technical-failed or unmeasured, never a fake zero. Business escalation with a valid review-ready measurement is not automatically technical failure. C coordinates evaluation, not every member's tests. Initial 30-case labels must be sealed before C sees timed answers; this review did not create/read Gold answers or claim experimental results. |

## C-F01 — P2: historical-bundle oracle accepts stale or incomplete citation verification

**Location:** `tests/contracts/test_contract_v1_rc4.py:26` and
`tests/contracts/test_contract_v1_rc4.py:96`.

**Expected:** the retained bundle's citation verification must match the packet's
case/input/proposal ID/proposal version/corpus and cover the cited IDs exactly
without duplicates. See `docs/09-interface-contract-v1.md:133`,
`contracts/v1/schemas.json:3571`, and the existing valid-handoff checks in
`tests/contracts/test_contract_v1_rc2.py:41` and `:56`.

**Actual:** `assert_proposal_bundle` checks case/input/corpus but omits the
verification's proposal ID/version and check coverage. Its own
`test_old_proposal_keeps_original_material_and_review_binding` constructs
`newer` by incrementing the packet and history object versions, but leaves the
nested citation verification at the old proposal version, then accepts it.
Two additional schema-valid probes with a different verification proposal ID
or no verification checks are also accepted by that oracle. The existing rc.2
full-handoff oracle rejects all three, exposing the inconsistent test evidence.

**Impact:** the current passing history test can certify a fixture that violates
the documented exact-material invariant. It cannot demonstrate that historical
verification belongs to the reviewed proposal or covers all its citations.
This is a static validation/test-fixture defect, not evidence that a deployed
application has accepted such input.

**Minimal reproduction (repository root, existing contract dependencies):**

```sh
python -B - <<'PY'
import sys
from copy import deepcopy
sys.path.insert(0, "tests/contracts")
from test_contract_v1 import validator
from test_contract_v1_rc4 import value, assert_proposal_bundle
from test_contract_v1_rc2 import assert_valid_citation_handoff

old = value("history-proposal")
newer = deepcopy(old)
newer["record_id"] = "history-proposal-002"
newer["object_version"] += 1
newer["content"]["packet"]["proposal_version"] += 1
missing = deepcopy(old)
missing["content"]["citation_verification"]["checks"] = []
wrong = deepcopy(old)
wrong["content"]["citation_verification"]["proposal_id"] = "proposal-other"
for name, record in [
    ("existing newer-proposal fixture", newer),
    ("missing verification coverage", missing),
    ("cross-proposal verification", wrong),
]:
    print(name)
    validator("FounderHistoryRecord").validate(record)
    assert_proposal_bundle(record)
    print("  shape and rc4 history oracle: accepted")
    try:
        assert_valid_citation_handoff(record["content"], record["content"]["retrieval_result"])
    except AssertionError as exc:
        print("  rc2 full-handoff oracle: rejected:", str(exc))
    else:
        print("  rc2 full-handoff oracle: accepted")
PY
```

Executed on 2026-09-12 against the exact source files with the fresh local
`.venv-c-review/bin/python` (CPython 3.12.7, Anaconda/Clang 14.0.6). The
equivalent `-B -c` invocation used no network/service and wrote no source file.
Actual output:

```text
existing newer-proposal fixture
  shape and rc4 history oracle: accepted
  rc2 full-handoff oracle: rejected: Citation verification proposal_version differs from packet
missing verification coverage
  shape and rc4 history oracle: accepted
  rc2 full-handoff oracle: rejected: Verification must cover exactly the cited IDs
cross-proposal verification
  shape and rc4 history oracle: accepted
  rc2 full-handoff oracle: rejected: Citation verification proposal_id differs from packet
```

**Requested A disposition:** strengthen the history oracle with the exact
verification binding and one-to-one coverage checks; preferably factor those
invariants into a reusable test helper. Correct the intentionally valid newer
fixture's verification version, then add stale proposal-ID/version and
missing/duplicate check regressions. Preserve the ability to represent invalid
citations for Risk to reject: do not indiscriminately require every historical
proposal's citation to be VALID or semantically supported. Rerun all contract
tests and record the actual fixing commit. No A-owned test or contract was
changed by this review.

## Non-blocking documentation observation

**C-N01 — current-versus-historical version wording is unnecessarily difficult
to follow.** `docs/00-project-definition-v1.md:21` still calls rc.4 the current
contract/model review candidate. `docs/09-interface-contract-v1.md:5` and
`contracts/README.md:6` retain unpublished/57d86fe wording below their explicit
rc.5 publication notices. The notices and actual SHA resolve the context, so
this was not treated as a wire/behaviour blocker. Recommend that A make the
current-version summary unambiguous in a later editorial revision and retain
older statements under clearly labelled dated history. No A-owned file was
changed and no historical evidence was deleted here.

## Decisions and evidence still needed

| Topic | Technical-review position for discussion | Who must confirm / prove it |
|---|---|---|
| MA-D01 / MA-Q01 attempt identity/count | One attempt object per invocation is coherent with terminal FAILED/BLOCKED and stable logical-effect identity. The proposed 1-based immutable attempt number is **not adopted** by rc.5: Schema still permits 0. Do not tighten consumers or infer invocation counts from it yet. | A chooses/explains; C reviews audit/evaluation impact; B confirms display. Any adoption requires the documented next contract revision. |
| MA-D02 query phases | UNKNOWN↔RECONCILING and a distinct known-label artifact phase are coherent. Keep query counters/claims separate from attempt count. | A/C confirm design; A2 supplies durable claim/late-worker/outage tests. |
| MA-Q02 / MA-Q03 | Preserve no automatic cross-approval continuation, stable historical effect identity, final-boundary authorisation and expired-claim protections. A static diagram cannot prove at-most-once or close the check-to-call race. | A implements and supplies concrete concurrency/provider-ledger evidence; C reviews it. No runtime guarantee is accepted by this document. |
| CS-D01 / CS-D02 / CS-Q02 | Source wrapper→Domain acceptance, one business/audit work unit, and separate image-read/label-store permissions are suitable candidates for joint review without new public DTOs. | A/C confirm exact internal methods, version/error/claim rules; B confirms attachment/history consumption. |
| Joint F.01 acceptance | Technical observations above can support C's review discussion but do not substitute for a human reading/decision. C-F01 needs an explicit correction or reasoned disposition. | A, B and C explicitly confirm the exact adopted version and remaining findings. Keep KAN-32 out of Done until its real acceptance conditions hold. |
| A/shared and C personal models | C must review A's explanation; A must review C's new personal model chain. File existence and successful parsing are not either person's contribution signoff. | Each member personally revises/explains their own material; original reviewers retain their roles. |

## Reproduction record

The focused reviewer inspected the committed contract-test entry points and
their fixture-only oracles and ran the additional C-F01 probe above. Separately,
the clean local reproduction agent ran
`python -B tools/checks/run.py offline --skip-baseline` on an independent
pristine copy of the exact archive:
56 contract methods, 6 static model/document groups, 12 model-tool regressions,
5 runner regressions and 15 Mermaid parses passed (exit 0). That run used
CPython 3.12.7 and Node 24.19.0/npm 11.17.0. The original 52 publication-manifest
entries matched and 89 fixed WBS tuples matched the downloaded main snapshot.
These passing existing checks do **not** negate C-F01; its negative cases are
not covered correctly by the existing history oracle.

Source-archive mode explicitly skipped the Git-ref baseline comparison;
the independent WBS tuple comparison is separate evidence. SVG/source matching
and Mermaid parsing are not new rendering, human understanding or runtime
proof. Health/environment reproduction and its database/Compose limitations
are recorded separately, not promoted to F.01 acceptance here.

This review changes no feature owner, reviewer, WBS ID/S/F dependency,
permission, Jira status, business implementation or submission record.
