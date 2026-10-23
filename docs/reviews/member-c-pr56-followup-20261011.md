# C technical follow-up: A private preview / approval

Date: 2026-10-11 (Australia/Sydney). [PR #56](https://github.com/shuxiachai/returnops-au/pull/56),
[Issue #55](https://github.com/shuxiachai/returnops-au/issues/55),
[KAN-15](https://lucastaooo.atlassian.net/browse/KAN-15).
Owner A; designated human reviewer C unchanged. Requirements FR-009/010/011/012,
NFR-002/003/004/006, AH-10, UC-03/04/05; A2.01 and
[A model chain](../12-member-a-model-chain.md).

## Source and review method

Reviewed adopted implementation `d2e809d1a127e0e38bab4111394752541ad6b8c6`,
with diff base `cdfc3c1193eea0a5f106f2e066c0b7dcce23942a`, against
[the private component specification](../35-a201-preview-approval.md).
Four read-only review roles examined intent/regressions, security/privacy,
reliability, and contracts/coverage. Codex performed this work at C's request;
these are AI-assisted technical observations, **not C's personal signature,
independent oral explanation, teammate APPROVED review, or joint acceptance**.
No A/B code was changed. The earlier merge used A's scoped exception and does
not retrospectively acquire C's approval from this document.

## Findings

No confirmed blocking defect was found in this bounded source review. This
does not establish absence of defects or complete A2.01/Gate 1 acceptance.

| Checked boundary | Source evidence / disposition |
| --- | --- |
| Preview/proposal/source identity | `preview_sources.py`, `approve_sources.py`: retained synthetic PASS provenance, exact version/backlink and current references are checked |
| Current authority and exact scope | `approve_decision.py`, `preview_service.py`: real Founder/current service permissions and saved scope/expiry are rechecked before commit |
| Replay, replacement and competing writers | Same-key replay retains original receipt/expiry; explicit expired-preview replacement follows the exact predecessor; supported writes use the Domain fence |
| Privacy and historical behavior | Changed lifecycle/reject/projection paths preserve no-preview REJECT behavior, clear consumed pointers, and erase preview/derived history bodies with affected receipt unavailability |
| Non-execution boundary | APPROVE persists a PENDING, unclaimed EXECUTION intent; existing lifecycle loading rejects EXECUTION and does not provision its authority or call a provider |
| Migration and contracts | 0009 requires the exact preceding schema; separate preview metadata leaves 0007/0008 unchanged; public schemas/routes are not expanded |

Source paths in the table are under `packages/returnops_domain/`; private
composition is under `apps/api/returnops_api/`, and migration under `alembic/`.
AP tests cover authority/source/expiry, rollback, UNKNOWN/replay, retention,
actual-fence races and installed-runtime probes. Presence of those tests is
separate from their execution evidence below.

One non-blocking measurement question remains: `preview_sources.accepted_preview`
walks prior expired-preview replacements and reconstructs predecessor proofs.
Measure long replacement chains/fence contention before scaling beyond the
private prototype; no workload failure was reproduced, so this is **not** a
confirmed defect, a requested semantics change or a new acceptance gate.

## Verification ledger

| Evidence | Exact source / result | Scope |
| --- | --- | --- |
| C local offline approval rerun | `d2e809d`; `python -B -m pytest tests/lifecycle/test_founder_approve_offline.py -q`: **29 passed** | Builder, request and UNKNOWN/private-composition checks; no database |
| C local contract rerun | `d2e809d`; `python -B -m unittest discover -s tests/contracts -p 'test_*.py' -q`: **128 passed** | Includes the existing 36 C1 tests; do not add them again |
| Actual main CI | [37931297595](https://github.com/shuxiachai/returnops-au/actions/runs/37931297595), head `d2e809d`: offline and API/PostgreSQL jobs **SUCCESS** | Remote execution, not a new C-local PostgreSQL/Compose reproduction |

Local interpreter: Python 3.12 in the previously hash-locked task environment.
No database, migration, Docker or installed-wheel execution was performed by C
in this follow-up. Earlier failing PR #56 checks remain historical failures:
environment passed, storage failed, subsequent business/image validation skipped.

## Remaining acceptance / downstream work

- C must personally inspect/understand the relevant design before supplying
  human review or interview evidence. This document does not fill that field.
- Original A2.01 S=F.01 and F=A1.03,F.03 obligations remain. The merge exception
  is not whole A2.01 or Gate 1 acceptance.
- A2.02/A2.03 execution consumers, public Founder write routes, provider effects,
  labels and notifications remain separate work; a stored APPROVED state is not
  a completed return or present execution authority.
- C1/C2 integration must preserve full retrieval/conflicts, exact membership and
  current case/input/proposal bindings. No C1 VALID result grants approval.

Publish a COMMENT referencing this record, not an APPROVED review that could
be mistaken for the outstanding personal/joint acceptance.
