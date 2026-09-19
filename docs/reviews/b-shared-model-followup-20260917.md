# B shared-model and report follow-up — 2026-09-17

> AI-assisted technical correction, authorised by the project lead. This record does not supply B/C personal explanation, student authorship percentages, team acceptance or permission to merge. The containing Git commit and PR #14 publication receipt identify the resulting revision; it deliberately does not claim its own future SHA or CI.

## Exact sources and scope

- B source: `6ddd8aa0c8b0c52d2d84b97143896cea4917165b`, PR #14, based on PR #8 `21f390f07bb3ce7e6dbdeee9c8a341748044ccd3`. Earlier B and A/AI compatibility commits remain ancestors; no original history is rewritten.
- A contract/design source: PR #11 `3dd1ff637693a826990eee5712cfb239a3c3da7b`, rc.5 / MA-0.3 / CS-0.2 / AD-0.2. Nine features, the fixed ID/Owner/Reviewer/S/F fields of all 89 WBS entries, public DTOs and 15 routes are unchanged.
- C integration source: PR #12 `15c136a1f717ba074d4aa77a0572d159c28cda8c`, `docs/reports/member-c-stage1-draft.md` §10 and `docs/reviews/member-c-integration-followup-20260916.md`. The correction text is byte-identical to the supplied `048bf76099f9c2828ff2b46c8bda8677b01f8ba1` revision; the later head adds navigation. [C's six findings](https://github.com/shuxiachai/returnops-au/blob/15c136a1f717ba074d4aa77a0572d159c28cda8c/docs/reviews/member-c-integration-followup-20260916.md) and [PR comment](https://github.com/shuxiachai/returnops-au/pull/14#issuecomment-5696352699) remain original records.
- Edited only the three new shared PUML/SVG views and their Markdown companions, the B team-report candidate and this disposition. B's personal three diagrams, docs19 and personal report are retained unchanged. Root's existing dirty work is outside this worktree and not included.

## Findings and disposition

| Finding | Correction |
|---|---|
| COL-1 authority and audit | API enters Domain; Guard returns a verdict, not authority. Operations returns observations to Domain. Domain alone calls CaseRepository/AuditPort and accepts state, required non-personal audit and applicable work in one transaction context. External effects remain outside that transaction. Current-state checks, durable claims, effect/artifact recovery and independent notification are explicit; the diagram is not concurrency proof. |
| OBJ-1 version mismatch | Explicit synthetic progression input v1 initial statement → v2 new accepted order snapshot → v3 accepted clarification. Current case/facts/proposal/review bind v3; proposal v2 and illustrative case v8 are separate counters. Both original statements are linked. Old objects are omitted, not deleted. |
| OBJ-1 authority/legal overclaim | Object absence is an illustrative moment, not a formal permission proof. All IDs, passages, hashes, content references and outcomes are synthetic. The non-blocking warning assumes an in-window conditional recommendation; unresolved blocking conflict would require ESCALATE. No legal entitlement or real guidance quotation is asserted. |
| UCD responsibility and unsafe proposal | Group labels distinguish B UI, A authoritative services and C grounding/provenance. Escalation means Founder disposition; unsafe current proposals retain lawful revision/manual paths and cannot be directly approved. Only actual no-proposal failure/block targets are manual-only. Actual second REVISE/current proposal survives automatic-budget exhaustion; ordinary clarification has no fixed cap. |
| Retention/result-work conflation | Composition is not blanket child purge. Preserve permitted non-personal integrity, minimal deduplication and tombstones; do not replay removed content. Shared ProposalReview corresponds to the immutable RiskReview result; C's seven internal phases are separate from five outcomes/public case states. |
| C integration and evidence | Use full MC-ACT/SEQ/SM-0.1, readable MC-ACT/SEQ/SM-RPT-0.1 and distinct MC-OBJ-0.1; retain UC-02/05 and keyword/BM25. Integrate versioned-source/removal and 30/20/pilot limitations. Separate dated reconstructed 58+15 evidence, 12 published checker tests, older 15 Mermaid parses and unpublished 18-test snapshot. No formal Gold results claimed. |
| Runtime and authorship overclaims | PG17 health-only environment does not implement business persistence, cryptographic audit or full agent stack. A3 provider access remains unresolved. Per-model invented author percentages removed; planned 45/27/28 effort retained. Personal decisions, shared participation and acceptance remain pending. Suggested test names in report traceability are marked planned, not completed evidence. |
| Course/review claims | September 25 remains B's proposed internal target; Canvas 25-point interpretation remains unresolved. Technical comments/AI review do not become personal signatures. No original GitHub review or approval comment is edited. |

## Validation and remaining work

Actual local validation on this isolated candidate:

- `python -B tools/model-checks/check.py --baseline-ref 3dd1ff637693a826990eee5712cfb239a3c3da7b`: **6/6 groups passed**, 41 Markdown files, 442 local targets, 15 SVG/source pairs, 89 WBS entries with ID/Owner/Reviewer/S/F unchanged; no Git-baseline skip. The checker does not test external URLs or anchors.
- `python -B -m unittest discover -s tools/model-checks -p 'test_*.py' -v`: **12/12 published checker tests passed**.
- PlantUML `1.2026.8`, `-charset UTF-8 -tsvg` and `-tpng`: all three changed shared diagrams rendered, **exit 0**. Embedded PlantUML copies in all three Markdown companions match the sources exactly.
- Actual PNG review: COL-1 and OBJ-1 text/notes remain readable without clipping. UCD-1 is tall with dense include/extend routing; some connector crossings remain and its SVG should be opened at readable zoom, not reduced to a single report-page thumbnail. This is not a zero-layout-defect or runtime-safety claim. An alternative top-down preview was rejected and not adopted.
- `git diff --check`: **exit 0** after removing three changed metadata lines' Markdown trailing spaces. Git emitted only existing LF/CRLF conversion warnings. B personal diagrams/docs19/report, contracts, apps, tools and docs07/08 have no diff against the B source head. Exactly ten existing files and this new disposition are included.
- No Mermaid, contract, business HTTP/DB/provider, Gold or timing tests were run for this document-only correction; their historical or future CI counts must not be pooled with these checks.

Local preparation logs are `tmp/static-check-final.log`, `tmp/model-check-tests.log`, `tmp/diff-check.log`, `tmp/check-exit-codes.json` and `tmp/prepublication-validation.json` in the isolated worktree. These ignored logs do not claim publication. SVG source metadata and checked-in sources remain reproducible evidence; current-head GitHub CI must be recorded separately.

Attempt accounting: two unsuccessful semantic review/validation attempts were resolved by the expert in this same work package (initial residual report findings, then a UC-05 table-column edit regression). The latter restored the responsibility column and FR-011/FR-012/OF-006 references. A separate edit-script UTF-8 issue failed before writing the report and succeeded on one explicit-encoding retry. The existing sandbox launcher/image helper failed; scoped commands approved through the working launcher completed, including displaying PNG bytes with the image tool. No sandbox/ACL/routing setting changed. Source/render checks and visual inspection remain document evidence, not runtime safety, formal evaluation, acceptance or personal contribution.

- Independent exact-diff review remains required before publication; its outcome and current-head PR/push CI belong to the publication receipt/PR body.
- B/C must still supply their own explanation, genuine edits and shared contribution records. A reviews C's current revision separately. C clean-Git/PG17 Compose reproduction and F.01/F.02/F.03 personal/joint acceptance remain separate.
- The repository team report is not the existing shared Google Doc. Any cloud integration reads the current document and preserves member edits/date objects/links/permissions; it is handled separately by the lead workflow.
- No commit/push/merge, Jira/Google Doc mutation, member notification or course submission is performed by this preparation.
