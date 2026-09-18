# B model compatibility disposition — 2026-09-14

> **Latest status override — 2026-09-14:** The independent non-author `route_reviewer` completed the final narrow re-review and reported PASS: both formal-model P2 findings are resolved, with no new P1/P2 in the corrected scope. This is not a claim that every possible P3 is absent, a human/member signature, or business/runtime acceptance. The review inspected the corrected state/sequence sources and synchronized documents, verified 9/9 manifest entries and the exact nine-file change scope, and visually checked the state figure and the actual two-page assembled sequence view. Historical pending-review statements below describe earlier snapshots and are superseded by this status and the final review receipt. The shared unsuccessful fix/validation count remains **3**. B personal revision/explanation/acceptance, shared contribution/integration and runtime/F.01/F.02 acceptance remain pending.

Historical preparation status: MB-0.2 local compatibility candidate; independent review and B personal acceptance were pending at that snapshot. See the latest override and final receipt for current review status.

## Source and attribution

The exact original B delivery is [PR #14](https://github.com/shuxiachai/returnops-au/pull/14) source [92cd717a87a1aff745044342498d4caae196dc15](https://github.com/shuxiachai/returnops-au/commit/92cd717a87a1aff745044342498d4caae196dc15), preceded by B's 31fa250 model/report commit. The correction starts from that source on `fix/kan-17-b-model-compatibility` in an isolated worktree. The original B commits, authors and shared-model history are preserved.

This change is **A-led, AI-assisted compatibility correction**, not B's personal revision or independent completion. Owner B / designated reviewer A and M-B.01–.06 dependencies remain fixed. A later independent review of this correction must not be described as the implementation author's own review. B must inspect the resulting model, make any substantive revisions needed and explain it personally. The 27% allocation remains a planning share, not measured contribution or marks. M-S.03's shared index and real shared contributions remain separate and pending.

Technical references are frozen [A 3dd1ff637693a826990eee5712cfb239a3c3da7b](https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b), [F.01](../09-interface-contract-v1.md) sections 5, 7.1/7.3, 8.1, 9 and 10.4, [UC-01E](../05-lab-3-requirement-modelling.md) extension 4a, [shared IntakeSession composition](../diagrams/01-domain-class-diagram.md), [allocation](../07-frozen-work-allocation.md) and [work packages](../08-delivery-work-packages.md). The correction changes no shared source, schema, endpoint, enum, feature Owner/Reviewer or WBS S/F field.

## Findings and bounded correction

| Finding in original B source | Disposition in MB-0.2 |
|---|---|
| P2: sequence 131–146 / activity 95–116 escalate ordinary missing information after three rounds without a proposal, real ProcessingFailure or OrderLookupBlock. | Remove the round-cap escalation. Missing/ambiguous facts remain AWAITING_INFORMATION with remaining targeted questions; UC-01E is repeatable. Do not invent a failure/block or Founder outcome to satisfy the schema. Actual accepted processing failures alone use bounded recovery and the existing exact-target path. |
| P2: activity 81–84 makes customer withdrawal REJECTED; model index 162 promises a future DELETE/withdraw route. | Leaving the page closes/pauses only local IntakeViewSession, with no server transition. Business withdrawal is an unapproved extension requiring the existing scope/interface process; no Stage 2 endpoint is promised. |
| P2: state 13–26 mixes browser DRAFT with the case-owned IntakeSession. | Keep the M-B.04 subject as the durable shared IntakeSession, created only with an accepted case. Explain a separate UI-only IntakeViewSession. Internal lifecycle_state refinements do not introduce a wire enum or replace ReturnCase. Correct the prior M-B.03 state-machine label to M-B.04. |
| B also asserted a seven-day archival timeout without an adopted retention/UC-01E policy. | Remove it from active transitions; no response causes no authoritative mutation. F.07 retention still applies; no indefinite-content retention promise replaces the timeout. |
| Replay skipped guards and always returned a cached success; clarification omitted current admission/owned-evidence rules. | Add auth/schema before scoped replay; readable original receipt vs changed payload vs removed content; no automatic new key; GET current view. Fresh clarification atomically checks owner/state/question/version, binds available owned STAGED evidence, appends input and advances versions without duplicate analysis. |
| Question persistence and notification dispatch were concurrent with no commit dependency. | Persist accepted questions first; notification follows committed state. Failure does not erase accepted input or create another intake intent. No new runtime/outbox dependency is introduced. |
| Sequence used CustomerStatement.version, an invented DAMAGED_ITEM classification and top-level questions; report incorrectly described FR-002 as attachment handling. | Use exact statement_id/kind/raw_text, CoordinatorResult, frozen IssueCategory, CustomerCaseView.clarification and collection_windows. Correct FR-002 to typed fact extraction and distinguish conceptual shorthand from wire DTOs. |
| Draft framed Git history as an already independent personal defence and called modelling resolved. | Preserve original B attribution and sources, disclose this A/AI correction, replace first-person completion with prompts and pending personal/shared acceptance. |

The activity and sequence now include initial or accepted-clarification COORDINATOR failures. Domain verifies the selected current case/input/work; stale results do not overwrite current facts. An existing proposal and history are preserved under the original target rules. With no current proposal, exactly one real current failure/block is required for ESCALATED. The modeled branch persists a real ProcessingFailure, not an OrderLookupBlock. A later trusted Founder decision, not intake processing, records MANUAL_HANDLING; no approval/return/label authority is created.

## Files in this candidate

Only these eight B delivered files plus this disposition are intended for publication review:

- [Activity PUML](../diagrams/member-b/member-b-activity.puml) and [SVG](../diagrams/member-b/member-b-activity.svg).
- [Sequence PUML](../diagrams/member-b/member-b-sequence.puml) and [SVG](../diagrams/member-b/member-b-sequence.svg).
- [State PUML](../diagrams/member-b/member-b-state.puml) and [SVG](../diagrams/member-b/member-b-state.svg).
- [B model index](../19-member-b-model-chain.md).
- [B report/explanation draft](../reports/member-b-stage1-draft.md).

The integrated team report/stage1-v0.1 directory, F.03 candidate, root dirty worktree and all shared model/contracts/allocation files are outside this correction. No commit, push, PR/Jira/Google Doc change, member message, service/database/configuration change or course submission is performed by preparation of this local candidate.

## Review walkthroughs

These are static paths to inspect, not executed product tests:

| Scenario | Expected model path |
|---|---|
| MB-T01 Complete fresh input | Authenticated atomic admission → selected current Coordinator result → UNDER_INVESTIGATION / intake COMPLETE; no business completion claim. |
| MB-T02 Fourth incomplete clarification | Current owner/question/version admission → append/re-evaluate → AWAITING_INFORMATION with remaining questions; no failure/ESCALATED/manual target. |
| MB-T03 Leave UI / no reply | Local IntakeViewSession closes/pauses; no request, rejection, cancellation, timer archive or deletion; reopen GETs current authorised case. |
| MB-T04 Actual initial or accepted-clarification error | Current processing and bounded recovery exhausted → real ProcessingFailure with current bindings → existing escalation target rules; later exact Founder decision only. |
| MB-T05 Stale question/version, wrong owner or invalid attachment | Safe correlated rejection; no input acceptance/analysis and no forged processing failure; authorised reload where applicable. |
| MB-T06 Same-key original readable replay after state advances | Auth/schema → trusted acceptance lookup → original receipt, no fresh admission or duplicate work → GET current view. |
| MB-T07 Same-key altered payload / removed original receipt | IDEMPOTENCY_CONFLICT / non-retryable INVALID_STATE respectively; no original-body resurrection, replacement-key auto-retry or new work. |
| MB-T08 Obsolete Coordinator result / recoverable real error | Discard obsolete binding; bounded selected-work recovery remains distinct from a new customer request. |
| MB-T09 Notification failure after accepted questions | Accepted input/questions remain; delivery state does not roll back input or duplicate case work. |
| MB-T10 Bounded/removed history content | Use collection_windows and authorised history start_cursor; tombstones/retention do not restore old content from a receipt or UI cache. |

## Validation and review handoff

Actual validation results are recorded below after rendering and checks. No local pass represents live API/DB guards, CI, B's personal explanation or F.01/F.02/shared-model acceptance. Same-problem unsuccessful fix/validation count at handoff start: **0**.

Validation completed for the local candidate:

- Existing Java/PlantUML 1.2026.8 rendered the three SVGs successfully (`-tsvg -charset UTF-8`, exit 0); the activity/state were re-rendered after visual corrections. Three temporary PNG previews were rendered with the same source/runtime (`-tpng`, exit 0).
- All three previews were actually inspected. The first candidate visual check found overlapping state self-transition labels and a PlantUML branch swimlane carry-over putting initial commit actions under the Portal. These were corrected by internal state event descriptions and an explicit Domain lane; the changed activity/state previews then passed reinspection. These are source figures for zoomed review, not a claim that they are already legible when compressed into a one-page team report layout.
- `python -B tools/model-checks/check.py --baseline-ref 3dd1ff637693a826990eee5712cfb239a3c3da7b`: **6/6** groups passed after those corrections. This included **12 SVG/source pairs**, **89 WBS fixed-field rows unchanged**, 37 Markdown files / 384 existing local targets, and the existing A/shared references. Logs: `tmp/b-compatibility-qa/static-final.txt`.
- `python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v`: **58 tests passed**. These are offline schemas/fixtures/oracles, not executed product guards. Log: `tmp/b-compatibility-qa/contracts.txt`.
- `python -B -m unittest discover -s tools/model-checks -p 'test_*.py' -v`: **12 tests passed**. Log: `tmp/b-compatibility-qa/model-regressions.txt`.
- `node tools/model-checks/check-mermaid.mjs --dependencies <existing-root-repository>/tools/model-checks`: **15 blocks parsed, 0 failures**. No dependency installation. Log: `tmp/b-compatibility-qa/mermaid.txt`.
- `git diff --check`: exit 0. Git reports only its normal LF-to-CRLF working-copy warnings; no persistent Git configuration was changed.

Python was the already available root repository `.venv/Scripts/python.exe`; Java was the installed Android Studio JBR and the JAR was the existing root `tmp/uml-tools/plantuml-1.2026.8.jar`. No services, databases, accounts, network source, permissions or shared configuration were changed. The ordinary image-view helper failed with the existing `helper_sandbox_lock_failed`; visual inspection used an authorised escalated read of the generated PNG bytes, without ACL or sandbox configuration changes.

**Initial attempt accounting (historical, before independent review):** Initial candidate render/static/contract/parser checks passed; first actual visual validation failed on the two issues above; its bounded correction and final visual/source checks passed. The same-problem unsuccessful fix/validation count at that point was **1**; the latest count is recorded below. The image-helper environment failure is reported separately, not disguised as a model/test pass.

Remaining review questions: independently verify the exact corrected candidate against the frozen source, including the shared case-owned session/episode interpretation and actual-failure target guards; B must personally revise/explain/accept the candidate and disclose assistance. M-S.03 and team-report integration, runtime persistence/concurrency behavior, F.01/F.02 joint acceptance and course submission remain outside this local correction. The next step is the independent non-author review handoff; this document does not self-approve the implementation.


## Independent-review formal corrections and current handoff

The independent reviewer found two P2 formal-model defects in the first MB-0.2 candidate: episode finals terminated the durable IntakeSession despite later legal clarification, and the inline common sequence fragment admitted an apparent processing path after replay/rejection. This was a failed independent validation; combined count became 2. The root authorised the same expert writer to make the smallest correction within the existing nine-file scope.

- State: COMPLETE and ESCALATED_FAILURE are now quiescent states of the durable session. G-REENTRY adopts only questions from an already committed legal shared-case AWAITING_INFORMATION transition with current case/input/question and existing guards. The failure branch additionally requires lawful proposal-bound recovery; no-proposal failure has no restart/revision path. Only actual authoritative terminal states satisfy G-TERMINAL and reach final. No route, field, CaseStatus or business policy was added.
- Sequence: sd CustomerIntake and sd ProcessAcceptedIntake are separate named/framed interaction definitions. The second definition is invoked only by refs in the fresh-acceptance branches and has its own accepted-work precondition. It has no lifeline continuation from the first interaction. Both PlantUML-rendered pages are included in the existing sequence.svg, not just the first output. Source metadata is preserved, element IDs are unique, and the model index contains the assembly recipe.
- Evidence: affected source, both raw sequence SVG/PNG pages, corrected state preview, actual assembled SVG raster, assembly script and page inventory are in `tmp/b-compatibility-qa/formal-review-fix`. The unchanged activity/source was not reworked. The earlier 58 contract/12 model-tool/15 Mermaid results are retained; these unrelated suites were not re-run for this framing-only correction.

During the first affected-page visual check, PlantUML left optional page-number placeholders literal in the footer. That visual failure is retained as attempt 3; the footer was replaced by plain text before final re-render. **Current shared unsuccessful fix/validation count: 3.** This remains expert work; no model substitution or reset of history occurred. Independent re-review of the final corrected files remains pending and is not claimed by this author.


Final author-side validation after the formal corrections: SVG/PNG rendering exited 0; the affected state and both final sequence pages were actually viewed, and the assembled SVG was rasterized and inspected with both frames present. The assembled view is 2135 × 4015 and retains both complete current-source metadata blocks. The Python recipe embedded in the model index reproduced the canonical SVG byte-for-byte; XML inventory confirmed two nested page viewports and zero literal page placeholders. The temporary Sharp raster uses a different local font fallback from the Java PNGs; raw Java pages and the actual SVG remain available, and no same-font/pixel-equivalence claim is made. The final static run passed 6/6 groups, all 12 SVG/source pairs and 89 fixed WBS rows against A3dd1ff6; `git diff --check` exited 0. Log: `tmp/b-compatibility-qa/formal-review-fix/static-final.txt`. These outcomes do not replace the pending independent narrow review. Failure history remains 3.


## Final independent review receipt — 2026-09-14

Reviewer: the separate non-author `route_reviewer` working as `/root/b_pr14_readiness`; this implementation author did not perform or self-approve that independent review. The review was read-only and AI-assisted, not B's personal acceptance or a substituted human signature.

The reviewer actually read the corrected state and sequence PUML sources and synchronized model/report/disposition prose; independently verified all 9/9 candidate-manifest file hashes, the exact nine-file change set and both complete nested SVG page viewports; and visually inspected the new state PNG and the actual assembled sequence-SVG raster containing both interaction definitions. The reviewer read the final 6/6 static-check log, including 12 source/SVG pairs and 89 WBS fixed-field rows. The reviewer did not rerun project tests or write files.

Outcome: **PASS for the final narrow re-review.** The two previous P2 findings—premature final-state termination of the durable IntakeSession and inline common processing after replay/rejection—are resolved. The reviewer found **no new P1/P2 in the corrected scope**. This statement does not assert that all possible P3 findings are absent. Quiescent states, guarded existing Domain clarification re-entry, the no-proposal no-restart restriction, and the separately named ProcessAcceptedIntake definition invoked only from fresh-acceptance refs were reviewed as clear.

The reviewed nine-file manifest preceded this receipt-only metadata update; its disposition SHA-256 was `ecf7f3dd77089c170b93ac810b20add150b0d1134b2ed08707fc108b1b7b7e4f`. This latest override/receipt changes only this disposition. The other eight reviewed file hashes remain identical. The refreshed manifest identifies the resulting publication candidate; this metadata update is not a model re-render, new implementation test run or additional independent review of changed model bytes.

The historical shared unsuccessful fix/validation count remains **3**; this final independent re-review passed and does not reset that count. B's own substantive revision/explanation/acceptance, shared M-S.03/team-report integration and contribution acceptance, and runtime/F.01/F.02 joint acceptance remain pending. This author has not committed, pushed, modified a PR/cloud document/Jira item or submitted coursework; publication is handed back to the root agent.
