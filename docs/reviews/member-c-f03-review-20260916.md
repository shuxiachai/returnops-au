# Member C — F.03 PR #15 bounded technical review

Review date: 2026-09-16. Jira: [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34). This is an AI-assisted static review prepared for C, not C's personal sign-off, an approval recommendation, or F.01/F.02/F.03 acceptance. Owner A / Reviewer C, S=F.01 / F=F.02 remain unchanged.

## Exact source and scope

- Repository/PR: [shuxiachai/returnops-au #15](https://github.com/shuxiachai/returnops-au/pull/15).
- Source reviewed: **`5bc59f5741d35e48f344fc3533889c3655f8823d`** (`feat/f03-security-component`). The live PR body names this exact SHA; its two commits target `fix/10-kan-32-contract-review`, not main.
- PR-declared F.01 base: `3dd1ff637693a826990eee5712cfb239a3c3da7b`. The PR states that the second commit changes publication wording only; code, tests, locks and CI remain from the first component commit. This review does not independently verify full Git ancestry or byte hashes.
- Read through authenticated GitHub source/diff UI: AGENTS; all five security files (`__init__.py`, `authentication.py`, `authorization.py`, `errors.py`, `types.py`); all 362 lines of `tests/security/test_authentication.py`; all 396 lines of `tests/security/test_authorization.py`; `docs/16-demo-identity-authorization.md`; all 74 lines of `docs/18-f03-security-component.md`; and the CI security-test invocation.
- Authentication/authorization implementation and both test files were additionally read at fixed-SHA blob URLs. This was not a full 16-file dependency-lock audit, penetration test or repository-wide review.
- CLI/private connector access and the ordinary ZIP path were unavailable to this task. No access control/download restriction was bypassed. **No local PR #15 installation, test execution, clean-Git reproduction, HTTP request, database test or Compose run was performed by this review.**

## Result

**No actionable defect was established in the inspected isolated authentication/authorization component.** This is a bounded static finding, not proof that the integrated business system is secure or complete. No A/B source file was changed. Publication of this record or a technical comment does not provide C's personal approval, a merge, a Jira transition or acceptance.

## Source and test checks

Line references below refer to the exact reviewed SHA. `S` means `apps/api/returnops_api/security/`; `T` means `tests/security/`. The tests were inspected, not executed by this review.

| Check | Source/test locations inspected | Static assessment |
|---|---|---|
| Fixed cryptographic policy | `S/authentication.py:55–95`; `T/test_authentication.py:95–184` | Bounded Bearer input; fixed HS256, issuer and audience; required claims; strict single audience; signature/time flags; restricted JOSE header; project ID and integer/lifetime checks. Bad algorithm/signature/header and malformed claims have negative tests. |
| Current authority, not token authority | `S/authentication.py:96–125`; `S/types.py:47–54`; `T/test_authentication.py:191–244` | Reads coherent current principal/session snapshot; matches owner/times; checks typed role and enabled/revoked state; registry role/store wins over conflicting signed claims. Empty registry or changed key gives no default identity. |
| Registry latency and error handling | `S/authentication.py:97–123`; `S/errors.py:16–41`; `T/test_authentication.py:247–267,335–362` | Rechecks wall-clock expiry after lookup. Expected outages become generic dependency errors without underlying diagnostics; malformed snapshots fail safely. Returned principal contains no token. |
| Fifteen-operation role matrix | `S/authorization.py:105–124,149–164`; `T/test_authorization.py:108–184` | Authenticate then role-check before resource reads. Independent expectation matrix compares its operation set with OpenAPI. No Founder inheritance of customer routes; unknown operations fail closed. |
| Trusted resource relationships | `S/authorization.py:166–201`; `T/test_authorization.py:193–235,293–304` | Checks addressed record, availability, store and customer ownership. Operation/notification resolve their own case, not caller-supplied case claims. Unavailable/cross-store/unowned resources use a safe not-found category. |
| Evidence lifecycle/origin | `S/authorization.py:203–237`; `T/test_authorization.py:240–289` | STAGED is uploader-only and unbound; BOUND resolves a case and matches its customer; GENERATED resolves a case without fabricating an uploader. Availability, expiry and store are checked. |
| Scoped observations and fresh repeated checks | `S/authorization.py:82–88,156–186`; `S/types.py:57–68`; `T/test_authorization.py:341–396`; `T/test_authentication.py:281–332` | Grants retain store/case/resource scope and no bearer. Tests cover second-call revocation, role/owner change and JWT-plus-authorization composition. These remain test-double/spy scenarios, not transaction/provider evidence. |

The fixed-algorithm/`decode_complete` usage was also compared with the [official PyJWT 2.13.0 API reference](https://pyjwt.readthedocs.io/en/2.13.0/api.html), which recommends selecting allowed algorithms independently of attacker-controlled token data. That documentation is not project runtime acceptance.

## Remote CI is separate evidence

The PR body reports successful current [PR run 34853723972](https://github.com/shuxiachai/returnops-au/actions/runs/34853723972) and [push run 34853718747](https://github.com/shuxiachai/returnops-au/actions/runs/34853718747): 244 security tests, 32 API/PostgreSQL environment tests (4 database tests, 2 existing warnings), 58 contracts and model/runner checks. It identifies synthetic merge `b89cddc10a713e1ac5c230da6fc203457574e521` onto A `3dd1ff6`.

These are **remote results reported by the PR**, not tests rerun or job logs independently audited by this review. The inspected `.github/workflows/ci.yml:43–44` invokes `python -B -m pytest tests/security -q`. A CI invocation/green badge cannot substitute for C's reproduction or personal understanding.

## Pending Domain and integration evidence

These are planned follow-up tests, **not reproduced failures**. They preserve the explicit scope in A's docs/18 lines 45, 66–74 and docs/16 AUTH scenarios. `AccessGrant` is a checked observation, not an ApprovalRecord or durable execution capability.

| Scenario | Evidence needed before integrated acceptance |
|---|---|
| Revoke/disable or change owner/store after authorization but before write/dispatch | Controlled interleaving with real Domain/storage: transaction-time identity/relationship/version revalidation; no unauthorized state write, approval, dispatch or notification. Two sequential component calls are insufficient. |
| Slow/unavailable real identity/resource store | Typed adapter outage, safe HTTP 503/correlation envelope, no fallback identity/cached grant; expiry/revocation at consumption; no token/connection/foreign-content leakage. |
| Cross-case proposal/failure/order-block or operation/notification substitution | Authorized case constrains the actual command and expected version; stale/cross-case body references cannot create approval or redirect effects. Preserve three targets and exact scope. |
| Replay after revocation or permitted receipt deletion | Reauthenticate/authorize before receipt access; isolate principal/operation/resource/fingerprint. Deleted accepted receipt returns safe `409 INVALID_STATE`, `retryable=false`, without restored content, new scheduling or automatic replacement key. |
| F.04 evidence binding and C3 consumption | Real intake/clarification atomically rejects foreign, expired/deleted or conflicting evidence without partial binding. C3 receives only controlled evidence-ID access, never a customer token or arbitrary path/URL. |
| Role-isolated history/pages/lists/analytics | Customer responses exclude Founder material server-side; every page rechecks current authority. Cursor binding, tombstones and store-scoped aggregates need real adapter/HTTP tests. |
| Browser/private bootstrap | A supplies controlled identity/session creation, secret injection/distribution and restart/revocation; B verifies explicit Bearer/error handling and approved origins/CORS. No public role selector or bundled Founder token; no credentials committed. |

C still needs to understand the exact revision and record their own review. A owns implementation/Domain integration; B owns browser consumption. F.01/F.02 prerequisites and personal/joint acceptance remain open unless separately evidenced. This static result is not grounds for Done or merge.
