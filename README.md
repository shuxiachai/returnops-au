# ReturnOps AU

## C evidence follow-up — 2026-09-20

This dated C-owned follow-up supersedes only the current setup/evidence status in the September 18 section; all earlier records remain below. Main is still the published candidate `da1a09fe7704bdb2fd2f989a44ab62bd7f089a41`. C's model/report sources are unchanged. [PR #17 progress correction](https://github.com/shuxiachai/returnops-au/pull/17#issuecomment-5748904252) records the installed Docker Desktop 4.91.0 / Engine 29.8.0 / Compose v5.5.1 and the September 18 saved Jira comments on KAN-22/12/33. Their status was left In Review; this is dated evidence, not a new Jira status board.

The old statement that Docker installation and those Jira comments are still pending is superseded. The [dated C F.01 technical review](docs/reviews/member-c-f01-review-20260920.md) covers all six scopes requested in Issue #10 against exact A source `3dd1ff637693a826990eee5712cfb239a3c3da7b`: source/order conflicts, historical provenance, capacity, Risk hand-off, known-label recovery and notification precedence. A fresh 58-test contract run and [eight focused artifact probes](docs/reviews/member-c-f01-probes-20260920.py) passed. One low-severity fixture issue remains for A: the SENT/customer-history examples still contain failed-delivery/operator-resend text. This is an AI-assisted technical review, not a personal signature, joint acceptance or executed business guards.

**PG17 Compose technical reproduction passed:** the [dated report](docs/reviews/member-c-pg17-reproduction-20260920.md) and [sanitized logs/scripts](docs/reviews/member-c-pg17-reproduction-20260920.zip) document exact A `3dd1ff6`, PostgreSQL **17.11**, **32/32 environment tests** (two retained dependency warnings), repeated migration and the same API process's live/ready **200/200 → 200/503 → 200/200** across the owned DB outage/recovery. After a disclosed Desktop file-read interruption, an independent no-hardlinks Git clone outside Desktop passed a fresh locked installation, the complete five-stage offline suite, final clean status and Git integrity checks; all nine runtime image source/lock files match that exact checkout. Only this test project's containers were stopped; its volume/logs remain. These results supersede the old unexecuted-PG17 status, but establish health-only infrastructure—not business routes, C's personal performance or joint F.02 acceptance.

The new [Stage 1 navigation draft, PR #18](https://github.com/shuxiachai/returnops-au/pull/18), is A-led preparation for **B-owned M-S.03**, with C's existing classification input preserved. It is not yet merged or an accepted final index. [PR #15](https://github.com/shuxiachai/returnops-au/pull/15) now has the separate main-aligned F.03 candidate `a8b480826e9735ef1d741acbc369f760a23732b8`; C's older bounded static comment is historical evidence, not a new-version approval. PR #7 and this PR #17 each require their own A review; do not reuse the merged PR #12 approval.

**Still requiring real user/team evidence:** C's own T01/T02/T03/T09 and D01–03 explanations in the [existing worksheet](docs/reports/member-c-contribution-and-interview.md), actual shared-task participation, the owners' exact-version joint acceptance, and A's final report/video plus actual submission receipts. No personal answer, signature, final submission or Jira Done is inferred.

### Unlocked Canvas report rules verified on September 20

The signed-in [Stage One Report Submission page](https://canvas.sydney.edu.au/courses/74323/assignments/695832) now explicitly resolves the old point-grouping question: **25 points = report 15 + individual interview 10**. One designated member submits **one PDF for the entire Project Groups team**; C supplies and verifies C's portion, not a separate personal report upload. The page displays **Sun October 4, 2026, 23:59** as the due time and September 20–October 11 availability with unlimited attempts. No timezone was shown. October 11 availability is not a deadline extension. No submission receipt was observed and nothing was submitted.

The visible rubric rows total 15 report points: ad-hoc requirements 0.5; Feature 1; overall Use-case 1; Use-case specifications 2; Elementary Structure 3; Complex Structure 3; Activity 1.5; Interaction 1.5; State machine 1.5, plus Interview 10. Nine report-row long descriptions were read: **each member needs at least one informal requirement, one use-case specification and one Activity, Interaction and State-machine model of specific behavior; the group needs 5–10 use cases in total.** The ad-hoc *diagram* is optional, not the individual informal requirement. Retain the existing selected models.

Shared delivery needs one comprehensive Feature diagram (feature-specific NFRs encouraged), one overall Use-case diagram (the page says “all architects and stakeholders”), a detailed design-time Class diagram using appropriate generalization/composition/aggregation/interfaces/multiplicity, and class-based runtime Complex Structure models using Object/Collaboration/Structured Class concepts. The Interview long description could not be opened; its 10 points are confirmed, but specific instructions must still be checked. The declaration requires accurate acknowledgement of generative-AI/other assistance and retention of the submitted work, drafts, AI outputs and research materials for **one year**. Do not pre-sign it for another member or recycle another course's work without permission.

**Video page verified after reconnecting:** the signed-in [Stage One Video Submission task](https://canvas.sydney.edu.au/courses/74323/assignments/695833) requires a **video no longer than 8 minutes**, introducing the project and key agent roles/functions, use cases and design models. Upload the video to Canvas before the deadline; an additional YouTube link is recommended, not a replacement for the upload. The task is **5 points**, counts for all group members and shows the same October 4, 2026, 23:59 deadline, September 20–October 11 availability and unlimited attempts. No explicit file-extension limit or timezone was shown; verify uploader constraints when producing the final file. No declaration was accepted and no submission receipt was observed. A coordinates the final upload; each member verifies their own included material and retains the separate individual interview requirement.

## Post-merge status — 2026-09-18

**Read this section before the dated preparation notes below.** The verified published main snapshot is [main at `da1a09fe`](https://github.com/shuxiachai/returnops-au/commit/da1a09fe7704bdb2fd2f989a44ab62bd7f089a41). Publication and technical review have advanced; personal evidence, joint acceptance and final course submission are separate gates. The September 7/16/17 notes are retained as history, not instructions to repeat completed merges or request the same old review.

| Delivery | Verified publication / review receipt |
|---|---|
| A rc.5 contracts, models and F.02 environment | [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) merged to main on September 18, 18:59 Sydney time. The later C-F01 test correction is retained. |
| Shared course/rubric requirements | [PR #13](https://github.com/shuxiachai/returnops-au/pull/13) merged at 19:06. Use [docs/19](docs/19-course-assessment-requirements.md) and [docs/11](docs/11-stage1-readiness.md), not old unmerged-branch wording. |
| C models, report contribution and review evidence | [PR #12](https://github.com/shuxiachai/returnops-au/pull/12#event-31380761223) merged at 19:34 as `3024e36c770fbb1d5e272dd2fc43eca3fd68e232`, after A approved synchronized source `79dc6630d37d61f18f42cf037b3f51dee23f72b6`; GitHub records four successful checks. It no longer targets an unmerged A branch. |
| B personal/shared models and team-report candidate | [PR #14](https://github.com/shuxiachai/returnops-au/pull/14) merged at 19:43. The [team report](docs/reports/stage-1-team-report.md) is a merged candidate, not an uploaded final PDF or course receipt. |

A's [final C review](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5246362189) records an explicitly delegated, AI-assisted technical approval. It preserves the 26 non-README C contribution files, both README notices and inherited main corrections. The Object Diagram is accepted as a **partial conceptual/DTO snapshot**, not a complete runtime schema. Approval/CI do not certify unaided authorship, personal understanding, runtime implementation, joint acceptance or submission. Three existing Markdown hard-break whitespace diagnostics were retained; do not describe every diagnostic as passing.

### C delivery and the remaining evidence

The C artifacts are available directly in this branch: [model chain MC-0.1.3](docs/18-member-c-model-chain.md), [seven editable PUML/SVG pairs](docs/diagrams/member-c), [report contribution MC-RPT-0.4](docs/reports/member-c-stage1-draft.md), and [delivery/AI-use and interview record](docs/reports/member-c-contribution-and-interview.md). PR #12 merged MC-PER-0.2; this follow-up explicitly updates that record to **MC-PER-0.3** with the merge receipts and a practical explanation/video/final-delivery checklist. The models, diagrams and report source versions are unchanged.

| Remaining gate | Concrete next evidence and owner |
|---|---|
| C personal explanation | C explains T01/T02/T03/T09 and D01-D03 in their own words using the existing worksheet; record actual dates, revisions and reviewer feedback. Rehearse real peer questions and verify the eventual individual interview slot; reference answers and the team video do not replace the interview. No invented signature or percentage. |
| Clean-Git / PostgreSQL 17 Compose reproduction | C uses the [published reproduction procedure](docs/reviews/f02-independent-reproduction.md), an exact reviewed SHA, a new checkout/venv and isolated local project/volume. Record full environment tests, migration and repeat migration, same-API healthy → DB outage → recovery, failed-config exit, sanitized logs and source/checks links. The current [KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33) target is A `3dd1ff637693a826990eee5712cfb239a3c3da7b`; agree and record a different target explicitly before calling it accepted. An archive, CI or native PG run is not a substitute. |
| F.01 / F.02 / F.03 acceptance | Original owners/reviewers record exact-version dispositions and unresolved findings in [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), [KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33) and [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34); F.01 retains B's consumer confirmation and its three-member contract review. [F.03 PR #15](https://github.com/shuxiachai/returnops-au/pull/15) remains separate; the September 18 merge batch did not include it. Preserve each WBS completion dependency. |
| Shared report/model index and course delivery | B verifies/finalizes M-S.03 and returns exact section/figure links; A integrates/submits the final report and ≤8-minute team video; each member verifies their material and actual contribution/AI disclosure; C audits R.04 evidence. C's actual participation must be traceable in every shared task (Feature, overall Use-case, Class and Complex Structure), not only the Object slice. Record final files, duration/readability checks and real Canvas receipt. The merged report candidate does not by itself establish the remaining acceptance/submission checks. |

On September 18, authenticated Git access was established on C's Mac. A separate fresh clone at the exact F.02 target `3dd1ff6` now passes **all 5 offline steps**: 58 contract tests, 6/6 document/model groups with a real 89-row Git-baseline comparison, 12 model-tool tests, 5 runner tests and 15 Mermaid parses. Additional checks: 2 Compose-probe regressions without Docker, and 28 non-DB environment tests (4 DB tests explicitly deselected; 2 retained warnings). Initial/final tracked Git state is clean. See the [dated evidence and sanitized logs](docs/reviews/member-c-clean-git-prerequisites-20260918.md), including npm startup retries. This is AI-assisted technical execution, not C's personal sign-off. The verified Docker installer is ready, but engine/PG17 Compose, migration and actual outage/recovery remain unexecuted. Never include tokens, passwords, `.env` files or private account exports in the evidence.

The last verified Canvas schedule in [docs/19](docs/19-course-assessment-requirements.md) showed September 20 unlock and October 4, 2026 23:59 report/video deadlines. Recheck the unlocked instructions/timezone and unresolved point grouping; this is not a new Canvas verification. Stage 1 submission must disclose open implementation work and must not wait for all Stage 2/Gold work to finish.

### Jira guide and workflow

[PR #7](https://github.com/shuxiachai/returnops-au/pull/7) is a **separate C-authored workflow guide** in the [KAN-12](https://lucastaooo.atlassian.net/browse/KAN-12) baseline context. It was refreshed at `6da67f00a8e9f563f8aa3ed428980467504cd501`, moved out of Draft and sent to A for review; all four new-source CI checks passed. Relative to main it adds only two guide files. It is not C's already-merged model PR, proof of R.01 adoption, or permission to duplicate 89 Jira cards. It follows [frozen allocation](docs/07-frozen-work-allocation.md), [89 work packages](docs/08-delivery-work-packages.md) and [team workflow](docs/03-team-and-github-workflow.md): each selected optional remains course scope; C coordinates evaluation while every member tests their own features. Root README remains the navigation/current-publication entry; Jira remains the live status, dates, estimates and blocker record. A's new approval remains required; inspect the live review/check state before merging.

Record real publication/review/merge evidence in the existing Jira cards without backdating, changing ownership or marking Done merely because files reached main. [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22) remains distinct from baseline R.01 and F.01/F.02/F.03 acceptance. Technical approval is recorded; the remaining personal/acceptance evidence above is not prefilled.

### Historical notes retained below

The earlier wording about unpublished rc.5, pending A review, PR #12's old base and unmerged course/report files describes its original dated snapshot and is superseded for publication state by this section. It remains useful provenance, not current merge instructions.

> **Review handoff — 2026-09-17:** see the [current review entrance](#review-handoff--2026-09-17), including C's populated delivery/AI-use record and A's new report-integration receipt. The [September 16 handoff](#delivery-handoff--2026-09-16) remains a historical delivery snapshot; it is not a live status board or a main merge.

> **Course requirements checked 2026-09-14:** start with the [shared Canvas/rubric requirements and A/B/C evidence map](docs/19-course-assessment-requirements.md), then the [Stage 1 submission checklist](docs/11-stage1-readiness.md). This clarifies personal/shared models, Lab 6 Object Diagram, AI acknowledgement and the visible Oct 4 deadline, without changing feature owners or declaring coursework accepted. Older dated preparation notices below retain their original scope.

> **rc.5 publication reference (2026-09-07):** this revision is delivered through [PR #11](https://github.com/shuxiachai/returnops-au/pull/11), identified by the actual commit containing this notice. The PR records the exact source SHA, CI runs and review state; C must reproduce that SHA, not old `57d86fe` or a floating branch. Local-only/unpublished wording, test runs and raw-file hashes below are pre-publication history. Current Git content is recorded in `docs/reviews/rc5-publication-artifacts-20260907.json`. Publication does not establish acceptance, B/C review, C reproduction or a Jira update.

> Topic status: the project lead approved the Baseline v1.0 candidate on
> 2026-08-31 and published it with the frozen allocation to main on 2026-09-06.
> The document alignment and F.01 rc.2 were merged in
> [PR #9](https://github.com/shuxiachai/returnops-au/pull/9).
> F.01 rc.4 (KAN-32), aligned MA-0.2 / CS-0.1 models (KAN-13), and the F.02
> environment form the published rc.4 review candidate. [PR #11](https://github.com/shuxiachai/returnops-au/pull/11)
> records its exact commits, CI runs and pending reviews; rc.3 is the earlier revision.
> Current team/tutor adoption reviews remain pending; publication is not acceptance.

> Latest local correction: F.01 rc.5 / MA-0.3 / CS-0.2 / AD-0.2 / PD-0.2, plus model-checker and F.02 reproduction fixes. These changes are unpublished; existing PR #11 checks cover rc.4 only. See the [defect closure record](docs/reviews/a-defect-closure-20260907.md).

ReturnOps AU is a human-governed multi-agent returns operations system for a
single Australian online store operated by one Human Founder. It helps the Founder
investigate return and remedy requests, prepare a cited non-executable decision
packet, and perform only an exactly approved simulated return and parcel-label
follow-up.

## One-sentence company brief

ReturnOps AU turns a customer request, synthetic order data, customer evidence,
store policy, and project-reviewed consumer guidance into a cited,
non-executable decision packet; only the Human Founder may approve an exact
proposal, after which the prototype performs only the approved simulated return
and parcel-label operation.

## Narrow promise

Given a supported customer request and synthetic order, ReturnOps AU will
produce a traceable decision packet, identify missing evidence, cite supporting
store-policy or guidance passages, independently review risk, and route every
high-impact simulated action through exact-scope Founder approval.

## MVP boundary

The prototype supports Australian physical-goods e-commerce and three request
types:

- faulty product;
- wrong item delivered;
- change of mind.

The prototype uses simulated commerce, logistics, and notification providers.
Its automated core ends after an approved simulated return and parcel-label
outcome is stored and notified. It does not provide legal advice, move real
money, modify a production order, or autonomously approve a remedy.

## Success measures

- At least 0.85 issue-category macro-F1, with 0.90 as a stretch target.
- At least 95% mandatory-information recall.
- At most 15% unnecessary follow-up questions.
- At least 90% citation correctness.
- At least 95% recall for cases requiring human escalation.
- At least 80% specificity for cases not requiring escalation.
- p95 proposal latency below two minutes in the fixed demo environment.
- Zero unauthorised operations, duplicate operational effects, or illegal state
  transitions in the parameterised safety and workflow suites.

These are prototype targets, not achieved results. Proposal latency runs from
accepted complete input to the stored review-ready packet, includes machine
revision/risk loops and excludes human/physical waiting only.

## Review handoff — 2026-09-17

No separate handoff folder is required. Review the existing [C PR #12](https://github.com/shuxiachai/returnops-au/pull/12), using its **latest exact head and checks**, not the older B approval of `c9f205d` or A COMMENT on `32c704f`.

1. Read [C's delivery and AI-use record, MC-PER-0.2](docs/reports/member-c-contribution-and-interview.md). Section 1.1 links the actual model/figure/report/review artifacts, §2 and §3 explain their technical basis, §4 distinguishes supplied material from pending shared participation, and §6 provides a factual AI-disclosure draft. These are C-owned, AI-assisted candidate deliverables, not a claim of unaided work or a completed personal explanation. Real personal walkthrough dates/feedback and final confirmation remain unfilled.
2. Review [MC-0.1.3](docs/18-member-c-model-chain.md), the [seven C source/view pairs](docs/diagrams/member-c) and [MC-RPT-0.4](docs/reports/member-c-stage1-draft.md). **A:** record the review target SHA, findings or approval, and Object/class consistency disposition in PR #12. If C adds further commits, review the new increment before final approval.
3. Check the new [A-authored correction in B PR #14 at `1b094289`](https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reviews/b-shared-model-followup-20260917.md) and [team-report candidate](https://github.com/shuxiachai/returnops-au/blob/1b094289c219727d9e42e694ade6f13431c34c7b/docs/reports/stage-1-team-report.md). This supplies a candidate receipt for C's six report findings and uses C `15c136a`; it is not a merged final report, the shared Google Doc, completed M-S.03 or a substitute for A's C review.
4. Resolve the stacked merge explicitly. C PR #12 targets A's `fix/10-kan-32-contract-review`, not main. Recommended order: complete the upstream review/acceptance decision for [PR #11](https://github.com/shuxiachai/returnops-au/pull/11), merge that approved dependency, then reconcile C with the resulting main, check the C-only diff and fresh CI, and review/merge the final C revision. Do not retarget the old C head to main merely to display a contributor name: it also carries A's unmerged history and lacks A's later `3dd1ff6` test correction. Preserve authorship and do not silently merge unrelated A/B work.

After actual publication/review/merge events, synchronize the matching Jira evidence and status, keeping [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22) acceptance distinct from [F.01 / KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), [F.02 / KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33) and [F.03 / KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34). Do not backdate transitions or equate a merge/CI pass with Done, clean-Git/PG17 reproduction, personal understanding, runtime implementation or course submission. This text does not itself record a Jira change.

## Delivery handoff — 2026-09-16

Historical snapshot: the current review entrance above supersedes its pending report-receipt wording and worksheet version; original evidence and dates below are retained.

**Published for review, not accepted:** C's delivery snapshot is
[`048bf760`](https://github.com/shuxiachai/returnops-au/commit/048bf76099f9c2828ff2b46c8bda8677b01f8ba1)
in [PR #12](https://github.com/shuxiachai/returnops-au/pull/12), tracked by
[KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22), based on A's
`fix/10-kan-32-contract-review`, not main. The links below open this branch's
files; the snapshot commit fixes the reviewed bytes. This README follow-up is
separate from that five-file delivery. Jira remains the live workflow record.

### Delivered material and reading order

| Material | Entry point / intended use |
|---|---|
| Updated requirements for everyone | [Course/rubric evidence map](https://github.com/shuxiachai/returnops-au/blob/b3b3b5869d33704e9f1da5b777c8c9338de6b565/docs/19-course-assessment-requirements.md) and [shared reading guide](https://github.com/shuxiachai/returnops-au/blob/b3b3b5869d33704e9f1da5b777c8c9338de6b565/README.md), delivered separately in [PR #13](https://github.com/shuxiachai/returnops-au/pull/13); not yet integrated here |
| C models and figures | [MC-0.1.3 model chain, including §12 handoff](docs/18-member-c-model-chain.md) and [editable PUML / SVG figures](docs/diagrams/member-c) |
| C text for the team report | [MC-RPT-0.4, §10](docs/reports/member-c-stage1-draft.md): replacement text for team report §§7.3, 10, 13.4, 14, 16 and 17; A/B integration is still pending |
| Personal contribution / interview record | [MC-PER-0.1.1 worksheet](docs/reports/member-c-contribution-and-interview.md): questions and evidence fields, still to be completed by C personally |
| Report integration findings | [MC-INTEGRATION-0.1](docs/reviews/member-c-integration-followup-20260916.md): six corrections and exact source versions; [handoff to B's PR #14](https://github.com/shuxiachai/returnops-au/pull/14#issuecomment-5696352699) |
| F.03 consumer review | [Dated C review](docs/reviews/member-c-f03-review-20260916.md) and [technical comment on A's PR #15](https://github.com/shuxiachai/returnops-au/pull/15#issuecomment-5696357090): bounded AI-assisted static review, not personal acceptance |

### Still to deliver / confirm

- **C:** explain MC-T01/T02/T03/T09 and MC-D01–03 in your own words; record
  actual decisions, shared-task contributions, dates and AI use in the worksheet.
  Do not fill personal answers or contribution percentages from an AI draft.
- **A:** review C's final exact commit and Object/class consistency. B's earlier
  approval of `c9f205d` does not cover this newer delivery or replace A's review.
  **A/B:** integrate C report §10, resolve the six reported inconsistencies, and
  return exact final report/model-index commit and section/figure links.
- **C, with A:** complete the clean-Git / PostgreSQL 17 Compose reproduction for
  A's PR #11 `3dd1ff637693a826990eee5712cfb239a3c3da7b`, record real results,
  and complete the pending exact-version F.01/F.02 acceptance. Review F.03
  personally; its seven listed Domain-integration checks and acceptance remain
  separate work. Track these through [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32),
  [KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33) and
  [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34), not README checkmarks.
- **A integrates/submits; B/C supply and verify their own material; C audits
  R.04 evidence:** deliver a readable final report PDF, video no longer than
  8 minutes, individual interview preparation, actual contribution and AI
  acknowledgement, final artifact links and a real submission receipt.
  At the Sep 14 Canvas check, report/video showed **Oct 4, 2026, 23:59** and
  unlock **Sep 20, 00:00**; recheck timezone, upload rules and the unresolved
  task-point grouping after unlock. Do not infer those details from the display.

### Important cautions

- **Published ≠ personally explained ≠ reviewed ≠ accepted ≠ submitted.** CI
  evidence belongs to its exact SHA; neither green CI nor the older native-PG
  run replaces C's clean-Git/PG17 Compose reproduction. The F.03 static review
  did not rerun the reported 244 security tests or prove business integration.
- **Keep model names and behavior exact.** Full C figures remain
  `MC-ACT/SEQ/SM-0.1`; report views are `MC-ACT/SEQ/SM-RPT-0.1`, and the Object
  slice is `MC-OBJ-0.1`. Document version `MC-0.1.3` does not create 0.2 figures.
  A real second `REVISE` remains `REVISE` when the machine budget ends; it is
  not silently converted to `ESCALATE` or a no-proposal manual-only failure.
- **No invented completion or scope changes.** C1/C2/C3 implementation, Gold
  execution and runtime safety are not established by these documents.
  The 30-case Gold set, 20-case subset and benchmark thresholds are project
  plans/targets, not course-wide quotas or measured results. Preserve the
  nine features and 89 frozen work packages in [docs/07](docs/07-frozen-work-allocation.md)
  and [docs/08](docs/08-delivery-work-packages.md). Stage 1 submission must disclose
  open items; it need not wait for all Stage 2 work to finish.

## Project documents

### Reading order and member entry points

Start with the course requirements, then the product definition, frozen allocation
and delivery work packages. Use the submission checklist when assembling the final
report/video. The links below are navigation, not a second task or status board.

| What you need | Read here |
|---|---|
| Current course requirements and rubric | [Course requirements and A/B/C evidence map](docs/19-course-assessment-requirements.md) |
| Product scope, ownership and task acceptance | [Project definition](docs/00-project-definition-v1.md) → [Frozen allocation](docs/07-frozen-work-allocation.md) → [Delivery work packages](docs/08-delivery-work-packages.md) |
| Final report, video, interview and submission checks | [Stage 1 readiness / R.04 checklist](docs/11-stage1-readiness.md) |
| A: personal models and design rationale | [A model chain](docs/12-member-a-model-chain.md), [A design decisions](docs/14-member-a-design-decisions.md), [A review PR #11](https://github.com/shuxiachai/returnops-au/pull/11) |
| B: intake/UI work and model-index integration | [B review PR #8](https://github.com/shuxiachai/returnops-au/pull/8); use its actual files/review history, with responsibilities fixed by docs/07–08 |
| C: personal models and report text | [C model chain](https://github.com/shuxiachai/returnops-au/blob/docs/kan-22-c-model-review/docs/18-member-c-model-chain.md), [C Stage 1 report](https://github.com/shuxiachai/returnops-au/blob/docs/kan-22-c-model-review/docs/reports/member-c-stage1-draft.md) |
| C: figures, actual contribution and explanation | [Editable PUML and SVG figures](https://github.com/shuxiachai/returnops-au/tree/docs/kan-22-c-model-review/docs/diagrams/member-c), [Personal contribution / interview worksheet](https://github.com/shuxiachai/returnops-au/blob/docs/kan-22-c-model-review/docs/reports/member-c-contribution-and-interview.md), [Dated course-alignment checks](https://github.com/shuxiachai/returnops-au/blob/docs/kan-22-c-model-review/docs/reviews/member-c-course-alignment-20260914.md) |
| Shared structure and team integration | [Class model](docs/diagrams/01-domain-class-diagram.md), [Composite views](docs/13-shared-composite-structure.md); C's proposed Object slice is in the figure directory above, for A review and B indexing |
| Workflow and evidence | [Jira/GitHub workflow](docs/03-team-and-github-workflow.md), [Model-check instructions](tools/model-checks/README.md) |

C's links deliberately point to the separate [C review branch / PR #12](https://github.com/shuxiachai/returnops-au/pull/12);
the shared course update is [PR #13](https://github.com/shuxiachai/returnops-au/pull/13).
These review locations do not imply a main merge, personal explanation or team
acceptance. Keep full editable models alongside report-sized views; retain actual
contribution and review evidence rather than treating a file's presence as completion.

### Full document catalogue

- [Baseline v1.0 candidate — lead approved, pending team/tutor review](docs/00-project-definition-v1.md)
- [Frozen work allocation v1.0 — owners, nine features and change rules](docs/07-frozen-work-allocation.md)
- [Detailed delivery work packages — dependencies and acceptance checklists](docs/08-delivery-work-packages.md)
- [F.01 API/data contract — review candidate, not an implemented API](docs/09-interface-contract-v1.md)
- [F.02 environment and CI readiness — local checks, pending acceptance](docs/10-f02-environment-readiness.md)
- [Stage 1 readiness — model review, report, video and submission evidence](docs/11-stage1-readiness.md)
- [Member A model chain — AH-10 / UC-04, UML sources, diagrams and walkthrough](docs/12-member-a-model-chain.md)
- [Shared Composite Structure — parts, ports, connectors and review scenarios](docs/13-shared-composite-structure.md)
- [A design decisions — attempt identity, recovery and pending review](docs/14-member-a-design-decisions.md)
- [Package and Deployment candidates — module and runtime placement](docs/15-package-deployment-models.md)
- [Demo identity and authorization design — preparation before F.03 integration](docs/16-demo-identity-authorization.md)
- [Logistics sandbox feasibility — eligibility, recovery evidence and open questions](docs/17-logistics-sandbox-feasibility.md)
- [A preparation delivery record — exact artifacts, checks and remaining acceptance](docs/reviews/a-preimplementation-readiness-20260907.md)
- [Project charter](docs/01-project-charter.md)
- [System design](docs/02-system-design.md)
- [Team, Jira and GitHub workflow](docs/03-team-and-github-workflow.md)
- [Requirements and initial backlog](docs/04-requirements-and-backlog.md)
- [Laboratory 3 requirements modelling](docs/05-lab-3-requirement-modelling.md)
- [Frozen requirements desk-research appendix](docs/06-requirements-desk-research-evidence.md)
- [FODA feature model](docs/diagrams/04-feature-diagram.md)
- [Use-case and actor-boundary model](docs/diagrams/05-use-case-diagram.md)

Documents `01`–`05` and the five existing shared diagrams have a v1.0
alignment draft published in [PR #9](https://github.com/shuxiachai/returnops-au/pull/9)
on 2026-09-07. Requirements come from `docs/00`, ownership
from `docs/07`, and delivery dependencies from `docs/08`; the older documents
are derived views, not competing plans. Original Lab 3 history and B/C source
contributions are retained. This alignment still needs current team/tutor review;
it does not complete the individual behaviour models or complex runtime model.
The frozen research appendix remains supporting evidence, not an ongoing
research-expansion task.

## Delivery systems

- **Jira is required** for Agile planning and timeline evidence: epics/stories,
  sprint or Kanban status, assignee, estimate, blockers, and retrospectives.
- **GitHub remains required** for technical Issues, branches, pull requests,
  reviews, commits, and CI.
- Each delivery item uses one Jira key and links it to the corresponding GitHub
  Issue/PR, avoiding duplicated full descriptions.

## Current phase

Member A's Activity, Interaction (two Sequence panels) and OperationAttempt
state machine now have a `MA-0.3` local review candidate with 21 static walkthrough
scenarios. A's own revision/explanation, C's review and F.01 acceptance remain
pending. The latest model correction is not yet in PR #11;
it does not complete B/C's personal models. The shared Composite Structure now
has a separate `CS-0.2` local candidate with three views, 29 connectors and 13
static review scenarios; human review and original M-S dependencies remain open.

The lead's current priority is to close the documentation, model-review and
Stage 1 preparation gaps before taking on a new implementation package.
The readiness checklist records concrete outputs and reviewers; missing member
confirmation, locked Canvas submission rules and capacity remain open. A maintains Jira and
integrates/submits course materials; C verifies R.04 evidence; each member
authors and explains their own contribution. These are working arrangements,
not completed reviews or a submission receipt.

F.01 rc.5 retains the rc.3 no-proposal manual exception across the requirement,
shared models and contract. It distinguishes technical processing failures from
pre-proposal order conflict/authority denial. Either target permits only an
audited manual outcome and notification, never execution approval. The HTTP
idempotency parameter uses the shared identifier rule. See the
[migration and validation instructions](contracts/README.md). The rc.4 candidate adds
role-isolated historical reads, explicit preview/pagination/retention rules and
notification-outcome precedence. Gold initial labels must be sealed before C
reads timed answers; source submission and the final demo have separate checks.
Use [the tracked model checks](tools/model-checks/README.md) for reproducible
source/SVG, link, traceability and frozen-allocation checks.

[KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32) tracks F.01 review;
PR #9 remains the historical rc.2 publication. B/C must confirm the actual
revised contract/model version before acceptance. Offline checks do not
complete F.01, Gate 1, runtime guards or individual models. F.02 preparation
now has an [environment candidate](docs/10-f02-environment-readiness.md):
health-only API, locked dependencies, migration entry point, Compose and CI
files. Docker Desktop has recovered from stale runtime sockets; the project
Compose stack builds and starts with PostgreSQL 17.11. All 30 environment tests
pass against that database, and actual container HTTP outage/recovery checks pass.
The local API uses port 8001 to preserve an existing service on 8000. PR #11
records actual CI runs separately from the still-pending joint F.02 acceptance. Business API,
case persistence, authorization and provider behavior are still unimplemented.

On 2026-09-06, the lead approved and froze the detailed A/B/C work allocation.
Use `docs/07` for function ownership and `docs/08` for executable work packages;
these are planning commitments, not completed work or live Jira status. Each
member's selected optional feature remains part of the course delivery.

The project is at Gate 0, Definition Freeze. The project lead has approved the
Baseline v1.0 candidate, frozen the research appendix, reduced the course
evaluation to 30 double-reviewed Gold cases plus the required `B1` versus `B4`
comparison, and selected Jira for Agile timeline evidence. Member B, Member C,
and the tutor must now review the current scope, aligned shared models,
individual model chains, verification targets and Jira/GitHub split. Next,
review and accept the revised interface contract and complete the missing Stage 1
models/evidence. Build and verify the deterministic safety spine before
connecting AI outputs to executable operations. Offline AI work and UI mocks
may proceed against reviewed boundaries; portfolio extensions come later.
