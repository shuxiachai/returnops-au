# Stage 2 entry and implementation handoff

Recorded 26 September 2026. Owner A / Jingbo Chai coordinates integration. B / Chengsi Li and C / Yuwei Tao retain their fixed responsibilities. No work-package Owner, Reviewer, start dependency, finish dependency or feature is changed.

## Stage 1 status and preserved source

The lead confirms that the report, PPT and team-recorded video have been submitted, and nominates the [current shared report](https://docs.google.com/document/d/1xvGO8EA_yZwWj1It3UM7AKDFEoQjsj5eJJXbCz4bcnc) and [Drive folder](https://drive.google.com/drive/folders/1bAjQFmkBl-zXthEj2G8a4MybvuaGkfMS) as reference contents. This is a user-confirmed submission status, not an independently retrieved Canvas receipt. The exact upload time and byte identity with uploaded files are unknown. The video is not in Drive and was not copied, edited or scheduled.

A local reference archive captured the unchanged cloud sources on 26 September. The report exported to 53 PDF pages, SHA-256 e1a6b88d695dd68f4e0d0a01d81a53d3a5ed02fc83c56bb6ce276bd3d114ec07. The nine-slide PPT SHA-256 is ffc710f5cf2e9c71ed6c433cae2cd5bced7a6c8afaaca74ac672629df2cc484b. Source metadata and hashes are retained locally in tmp/stage2-entry-20260926/submission-reference/. The archive is outside Git publication and was not a new layout/content approval. Existing report files and shared sources remain unchanged.

The original 21 September local 50-page report, B's VID-1 and C's PR20 snapshot remain dated preparation records; they must not be silently relabelled as the submitted package. Personal interview and actual contributions retain their own requirements.

## Verified technical starting point

Main was a6c4cbf7bcf7b4df90b2eaf92fdd258ace8a5a72 at the entry check; [main CI35704787018](https://github.com/shuxiachai/returnops-au/actions/runs/35704787018) passed. Its five commits since da1 add B's URD-1, package/deployment wrappers, VID-1 and a bounded report wording correction. The seven changed paths contain no runtime, API, schema, dependency-lock or workflow change.

The executable main still provides infrastructure/health endpoints. [PR15](https://github.com/shuxiachai/returnops-au/pull/15) is the isolated F.03 identity/access component; [PR19](https://github.com/shuxiachai/returnops-au/pull/19) is A's notification-fixture wording correction. They remain separate candidates, with current exact-source and CI evidence recorded on each PR after alignment. Neither publication nor green checks establishes integrated business behavior.

B's exact-A frontend review and C's six-scope technical review/PG17 reproduction are existing evidence. C explicitly distinguishes those records from personal explanation and joint acceptance. [Issue10](https://github.com/shuxiachai/returnops-au/issues/10) tracks F.01; [Issue5](https://github.com/shuxiachai/returnops-au/issues/5) tracks broader R.01 adoption. Their acceptance is not inferred from course submission.

## Ordered implementation path

| Step | Concrete work | Completion or promotion condition |
|---|---|---|
| 1. Preserve submitted-material references | Keep user-confirmed status, source revision and current report/PPT hashes; leave submitted sources unchanged | Reference manifest is available; it is not labelled a Canvas receipt |
| 2. Bring A preparation candidates up to current main | Preserve source authors and main additions, validate exact candidate trees, refresh PR source/CI evidence | An independently reviewed candidate and passing exact-source CI; merging and acceptance remain separate |
| 3. Prepare original-intake rules in isolation | Validate CreateCaseRequest and project an unpersisted ORIGINAL CustomerStatement with exact raw text | Pure functions and negative/aliasing tests pass against current schema; no API, database, identity or provider effects |
| 4. Formally align the domain and persist cases | A1.01, then A1.02/A1.03 with F.03 and F.05 according to original dependencies | F.01 is accepted first; satisfy each original S/F dependency and designated review |
| 5. Build the no-LLM governed path | A1 fixed proposal/mock review, current Founder approval, simulated return/label, separate notification and audit | R.02/Gate1 evidence, including unauthorized/duplicate/uncertain/recovery cases |
| 6. Add the actual agent workflow | A's Coordinator/Assessment consume B's UI input and C's retrieval/independent review after the deterministic path is accepted | R.02 first, then A1.08/R.03 pilot evidence; no direct Agent-to-Operations authority |

The isolated preparation in step3 is a candidate contract/rule exercise allowed by Gate0. It does not start formal A1.01 integration or replace packages/domain/models.py. No public request/response shape, legacy model or production entry point is changed by preparing it.

For that slice, accept a valid original request, preserve every character, use only documented defaults and produce a CustomerStatement using explicitly supplied synthetic identity/time. Caller-supplied identifiers confer no authority. Do not create a case, assign state, bind evidence, persist data or call a model/provider. Full multi-item/parcel rules, idempotency and state transitions are later work.

## Decisions and acceptance still needed

- **F.01 / R.01:** retain B's and C's actual review scope, dispose of the notification fixture finding through PR19, and record the genuinely accepted exact revision and remaining participant evidence. Issue10 stays open until its actual acceptance is recorded.
- **F.03:** the designated C review and original F.01/F.02 conditions remain. A technical static comment is not an APPROVED event. Before business writes or dispatch, Domain must revalidate current authority and versions atomically; AccessGrant is an observation, not an approval.
- **B with A:** settle customer recovery when an accepted creation response and receipt are unavailable and no case ID is known. Do not invent a customer case-search API.
- **A with C:** settle attempt ID/count interpretation and compatibility, plus the provider dispatch/concurrency rule. Current rc.5 accepts zero; no new minimum is silently adopted. Database transactions cannot make an external provider atomic.
- **A3:** no new tutor reply or logistics test entitlement was supplied in this turn. Use the existing A3 feasibility and tutor decision brief; preserve the selected optional until an explicit accepted decision. Do not count core mock work twice.
- **C-owned review, modeling, environment and PR work:** remains deferred under the lead's existing instruction. This handoff neither edits it nor requests a new C review. B's M-S.03 ownership is unchanged.

The repository workflow requires at least one teammate approval and passing checks before a merge. Current PR15/18/19 have no such approval at the entry check, so this work prepares and publishes candidates without merging them. This restriction is distinct from the S/F integration and final-acceptance dependencies.

This handoff adds no sprint dates, availability assumptions, Jira Done transitions, new feature allocation or personal sign-off. No member/tutor message is sent on its behalf.
