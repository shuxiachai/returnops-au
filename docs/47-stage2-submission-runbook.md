# Stage 2 submission runbook (R.05.a and R.05.b)

Owner: A Jingbo Chai (integrates and submits). Reviewer: C Yuwei Tao. Work package R.05 and its two course sub-checks, R.05.a source submission and R.05.b final-week demo, in the unchanged [work packages](08-delivery-work-packages.md). This runbook turns the open items of the [submission checklist](28-stage2-submission-checklist.md) into steps with owners and dates. Nothing in it has been executed: no tag, package, upload, rehearsal or contribution statement exists yet (22 October 2026, Sydney). A course submission receipt is not R.05 acceptance (docs/08, R.05).

Companion documents: [demo script](45-stage2-demo-script.md), [Gate 2 roadmap](46-gate2-roadmap.md).

## 1. Deadline facts

| Source | Wording | Note |
|---|---|---|
| Stage 2 Marking Criteria, p1 | "The due date for submitting your source code is November 1, 2026, at 11:59 PM." | No timezone stated ([docs/28](28-stage2-submission-checklist.md)) |
| Stage 2 Marking Criteria, p1 | In the Week 13 demonstration the source is downloaded directly from Canvas and deployed on site | Drives the rehearsal in section 5 |
| Project Description, p2 | "uploaded to Canvas before Monday of the final week" | Older, less specific wording |
| TUT-09 | "Sunday, Week 12" with a late penalty of "5 marks per day" | Late-penalty rule |
| Canvas, read 22 October 2026 | Assignment "Stage 2 Code Submission" (course 74323, assignment 695834): online upload, **zip files only**, group assignment on the group set that holds "Mon 13-15 Group 10" (one upload counts for all three members), **opens Monday 26 October 00:00 Sydney**, **due Sunday 1 November 23:59 Sydney** (12:59:59 UTC), accepts late uploads until 6 November 23:59 Sydney, 20 points, rubric "Stage 2: Demonstration" (7 + 4 + 4 + 5) attached, no description text | Timezone resolved: Canvas shows Sydney local time. No Week 13 demo schedule was posted yet; the group's practical class is Monday 13:00-15:00 |

**Plan for the earliest reading:** upload before **12:00 noon Sydney time on Sunday 1 November 2026**, leaving the afternoon for the download-and-reopen check and one re-upload if needed. The Canvas reading of 22 October confirms the day and the Sydney timezone; if a later tutor or Canvas notice gives an earlier time, that notice wins; record it here with its date.

## 2. Dates and owners (plan of 22 October 2026)

| Date (Sydney) | Item | Who |
|---|---|---|
| 26 Oct | Canvas item opens; ask the tutor at the Monday practical how the contribution statement is to be handed in (the item accepts zip files only) and record the answer in section 4; demo script final; each speaker's own wording | A; A, B, C |
| 27-28 Oct | Contribution statement draft sent to the three; A3 tutor disposition requested and recorded; first full rehearsal on A's machine; B's Issues #91, #95, #88 and C's PRs #17, #61 merged or recorded as not merged | A; B; C |
| 29 Oct | Clean-machine rehearsal (section 5, pass 1) | A runs, B checks UI steps, C records |
| 30-31 Oct | Fixes; contribution statement final; tag and package (section 3) | A; all three sign off the statement |
| 1 Nov, before noon | Canvas upload and download-and-reopen check (section 4) | A |
| 1 Nov to Week 13 | Rehearsal from the downloaded Canvas package (section 5, pass 2); demo | A, B, C |

## 3. Packaging (R.05.a)

Preconditions: every pull request intended for submission is merged into main and the CI run of that main commit has finished with all jobs successful; README notices and docs/41, docs/43, docs/45-47 describe the submitted state; anything not merged is listed in the known gaps (section 7).

1. Choose the commit: the main commit whose CI run is green. Record its full SHA and the run URL.
2. Tag it (name is a proposal): `git tag -a stage2-submission-v1 <sha> -m "Stage 2 source submission"`, then `git push origin stage2-submission-v1`. The tag message carries no AI tool attribution (repository rule).
3. Zip the tag: `git archive --format=zip --prefix=returnops-au/ -o returnops-au-stage2-submission-v1.zip stage2-submission-v1`. `git archive` packs only files tracked at the tag, so git-ignored local material (`.env`, `.venv/`, `node_modules/`, `tmp/`, `dist/`, `__pycache__/`, `data/private/`) is left out. For a zip given a tag, git stores the commit ID as the archive comment; check it with `unzip -z` **(not verified here)**.
4. Add the contribution statement: unless the tutor named another channel (section 2, 26 Oct), append `CONTRIBUTION-STATEMENT-Group10.pdf` at the root of the zip, next to `returnops-au/`, with Python's `zipfile` in append mode (`zipfile.ZipFile(path, 'a').write(pdf, 'CONTRIBUTION-STATEMENT-Group10.pdf')`); the repository tree inside `returnops-au/` stays untouched. Then hash: PowerShell `Get-FileHash -Algorithm SHA256 returnops-au-stage2-submission-v1.zip`; bash `sha256sum returnops-au-stage2-submission-v1.zip`. Record the value and the size in bytes.
5. Content check: list the archive (`unzip -l`, or `tar -tf` on Windows) and confirm that none of these is present:
   - `.env` (only `.env.example` may appear), `auth.json`, `sessions.json`, `*.pem`, `*.key`, any file holding a value for `RETURNOPS_MODEL_API_KEY` or a database password;
   - private directories (`tmp/`, `tmp/demo-shop`, `tmp/demo-cups`, driver output directories), `node_modules/`, `.venv/`, `dist/`, `__pycache__/`;
   - any student ID inside `returnops-au/` (the repository is public); the statement PDF sits only at the zip root, outside the repository tree.
6. Unzip into a new empty directory and run `python -B tools/model-checks/check.py --skip-baseline` there (an archive has no Git history, so the WBS Git comparison is skipped explicitly). Record the "Static check groups" line.

## 4. Canvas upload and download-and-reopen check

1. Open "Stage 2 Code Submission" from the course's Assignments list (open from 26 October); confirm that it still shows due 1 November 23:59 Sydney and zip files only; record any change.
2. Upload `returnops-au-stage2-submission-v1.zip` (with the statement PDF inside at the zip root, section 3 step 4). A separate PDF cannot be uploaded to a zip-only item; if the tutor named another channel for the statement, use it and record it here. One member uploads for the group; the submission is shared by all three.
3. Record the Canvas receipt: submission time shown by Canvas, attempt number, file names and sizes; keep a screenshot outside the repository.
4. Download the submitted zip from Canvas into a new empty directory. Compute its SHA-256: it must equal the value from section 3 step 4. Check the archive comment (commit ID) and that `returnops-au/README.md` opens with the expected newest notice.
5. Open the statement PDF from the downloaded zip; check group number (10), names, student IDs and that each criterion row totals 100%.
6. If anything differs, re-upload before the deadline and record both attempts; never edit a record afterwards to hide the first.

R.05.a record (to fill): deadline source and wording; tag; commit SHA; CI run URL; package file name, size and SHA-256; Canvas item title; receipt time and attempt; reopen check result; known gaps attached (yes/no).

## 5. Clean-machine rehearsal checklist

Derived from the README chapter [Deploy from zero](../README.md#deploy-from-zero---22-october-2026-sydney), with `git clone` replaced by the package. Pass 1 (29 October) uses the zip produced in section 3 on a machine without this repository's ignored files; pass 2 (after 1 November) uses the zip downloaded from Canvas, as [docs/28](28-stage2-submission-checklist.md) requires. Record the package hash, environment, commands, migration, synthetic setup and outcome for each pass.

| # | Step | Expected output | Who | Date | Result |
|---|---|---|---|---|---|
| 1 | Record machine, OS, CPython (3.12; 3.12.4 or later on Windows), Docker and Compose, Node and npm versions | Versions within README section 0 | A | 29 Oct / pass 2 | |
| 2 | Obtain the zip (pass 1: section 3; pass 2: Canvas download); SHA-256 | Equals the recorded hash | A | | |
| 3 | Unzip into a new directory | `returnops-au/` with README, `compose.yaml`, `Dockerfile`, lock files | A | | |
| 4 | Create `.venv`; `pip install --require-hashes -r requirements-dev.lock`; `pip install --no-deps --no-build-isolation -e .`; `pip check` | Installs without error; `pip check` reports no broken requirements | A | | |
| 5 | `python -B tools/environment/local.py init`; set `API_PORT=8001` in `.env` | `Created ignored local configuration with a fresh password; no secret displayed.` | A | | |
| 6 | `docker compose config --quiet`; `docker compose up --build -d --wait --wait-timeout 180`; `docker compose ps -a` | `db` healthy, `migrate` Exited (0), `api` healthy | A | | |
| 7 | `/health/live` and `/health/ready` on port 8001 | `{"status":"alive"}`; `{"status":"ready"}` | A | | |
| 8 | Host migration via `local.py run python -m alembic upgrade head` | Exits 0 (README: not verified) | A | | |
| 9 | `demo.py provision` for `tmp/demo-shop` with `--order-investigation --fixed-proposal` | `Private synthetic demo registration completed. ...` | A | | |
| 10 | `demo.py serve --auth-file ... --port 8000 --fixed-proposal --founder-decisions` (plus `--model-showcase` only with a key) | `http://127.0.0.1:8000/health/ready` ready | A | | |
| 11 | `apps/web`: `npm ci`; `npm run dev`; open `http://localhost:5173` | Page loads; Vite proxies `/v1` to 8000 | B | | |
| 12 | Token login as customer and as Founder in two browser profiles | **Auth Tokens** shows `Valid: <principal> (<ROLE>)` | B | | |
| 13 | Demo S2: case without order reference, answer `SYN-1001` | Question shown; case reaches `RISK_REVIEW` | B | | |
| 14 | Demo S3: case list, detail, audit, analytics; one Founder decision | Live analytics and decision only if Issue #91 is in the package; record which decision the server accepts or refuses | B | | |
| 15 | Demo S4 (only with PR #94 merged and a key): facts on the case; one rejected reply | Facts shown, or WARNING `outcome=REJECTED`; record tokens and latency from `run_once.py` evidence | A | | |
| 16 | Stop `serve`; provision `tmp/demo-cups` without the two flags; set `DATABASE_URL`; driver with `--identities --api-port 8000 --keep-api --allow-existing-data` | `R.02 demo mode: driver result PASSED (see run-receipt.json).` | A | | |
| 17 | Founder UI with `demo_cups_founder`: inspect the driver's case | Status `COMPLETED` | B | | |
| 18 | Timed run of the whole demo script | 12-15 minutes; note overruns per segment | A, B, C | | |
| 19 | Clean up: Ctrl+C; delete `tmp/demo-shop`, `tmp/demo-cups`; **Clear token**; unset model variables | No private files left | A | | |

## 6. Contribution statement draft

The course form asks for the group number, each member's name and student ID, each member's percentage under each of the four criteria (each row totals 100%) and the specific tasks or deliverables each member completed ([docs/28](28-stage2-submission-checklist.md)). Without a statement, equal contribution is assumed. Percentages are never inferred from planned effort; docs/07's 45 / 27 / 28 is planned effort, not contribution.

Group number: **10** (Canvas group "Mon 13-15 Group 10", read 22 October 2026)

| Member | Name | Student ID |
|---|---|---|
| A | Jingbo Chai | held in the private statement file, not in the repository |
| B | Chengsi Li | held in the private statement file, not in the repository |
| C | Yuwei Tao | held in the private statement file, not in the repository |

**Percentages: the lead's starting proposal of 22 October 2026 (revised the same day after PR #94 merged and the private statement draft was written), for the three members to discuss and agree by 30 October. Not agreed and not final.**

| Criterion | A Jingbo Chai | B Chengsi Li | C Yuwei Tao | Total |
|---|---|---|---|---|
| 1. Implementation of Stage 1 requirements and design | 60 | 20 | 20 | 100 |
| 2. AI agent capabilities | 50 | 15 | 35 | 100 |
| 3. Agile experience | 45 | 25 | 30 | 100 |
| 4. Advanced technologies | 50 | 30 | 20 | 100 |

Tasks and deliverables (starting points from repository records; each member replaces their own row with their own words and exact PR, commit and test links):

| Member | Draft |
|---|---|
| A | A1 case lifecycle, customer backend, order investigation and fixed proposal ([docs/21](21-customer-flow.md), [docs/23](23-order-investigation.md), [docs/29](29-a105-fixed-proposal-runtime.md)); A2 approval admission, execution preparation, simulated return, label, PDF and notification ([docs/37](37-a202-approval-admission.md), [docs/39](39-a203-core-return-execution.md), [A2.06](a206-notification-outcome.md)); Founder decision HTTP boundary ([docs/40](40-founder-decision-http-boundary.md)); F.06 analytics ([docs/43](43-f06-analytics.md)); R.02 driver and demo mode ([docs/41](41-r02-end-to-end-evidence.md)); advisory Coordinator showcase ([docs/44](44-coordinator-showcase.md), PR #94); Jira hosting; R.05 documents |
| B | Web frontend: customer portal, Founder console, operations analytics page ([apps/web README](../apps/web/README.md), PR #60); [interactive demo walkthrough](35-b205-interactive-demo-walkthrough.md); live wiring per Issues #91, #95, #88 (state on the day) |
| C | C1 grounding and citation checks ([experiments/c1_grounding_candidate](../experiments/c1_grounding_candidate)); C2 risk-review candidate ([README](../experiments/c2_risk_candidate/README.md)); E.01/E.09 evaluation preparation ([README](../experiments/evaluation_candidate/README.md)); [C's model chain](18-member-c-model-chain.md); PRs #17 and #61 (state on the day) |

Each member also states their own AI assistance. Student IDs, percentages and task claims are confirmed by the member concerned, never by AI preparation. The final statement is uploaded to Canvas as a PDF and is not committed to the public repository.

## 7. Known gaps to attach

Attach this list (updated on the submission day) with the package, for example as a short PDF next to the contribution statement:

1. No acceptance record exists for R.02, Gate 1 or the other delivered work packages; a merge, a green CI job or a `PASSED` receipt is not acceptance.
2. Gate 2 deferred: full A1.06, A1.07, A1.08, the real C2 reviewer, E.09, R.03 and E.12 ([docs/46](46-gate2-roadmap.md)). There are no evaluation results.
3. A3 (OF-004) unmet: no carrier contract or test account; tutor disposition: **to record** (docs/46, section 5).
4. C3 (OF-001) not started: depends on R.03.
5. Advisory model showcase: only if PR #94 is merged; first live call pending; results in memory only; no audit event; customers never see it; Founder card depends on Issue #95.
6. Frontend: live Founder decisions and live analytics refused with `501` until Issue #91 is in the package; follow-ups in Issue #88.
7. The only proposer is the fixed synthetic one (`fixture-no-live-model`); the risk result in the end-to-end run is the controlled PASS receiver and risk stub.
8. Proposal latency is Tier 0 (no samples): trusted start and end events are open ([docs/43](43-f06-analytics.md)).
9. The driver composes its own API; `demo.py serve` and the image default CMD do not run the governed chain; Docker evidence is the image build and import probe; the Compose API is health-only ([docs/41](41-r02-end-to-end-evidence.md)).
10. Which Founder decision a `demo.py serve` case can reach is unverified; escalation has no live route ([docs/45](45-stage2-demo-script.md), S3).
11. Fault injection of `UNKNOWN` and `REPLAYED` paths in an end-to-end run, and Windows file permissions, are not covered (docs/41, Deferred).
12. The contract operations `reconcileOperation` and `retryNotification` are not registered as routes (R.05 research record, 22 October 2026).
13. Deploy-from-zero steps other than the 7 September virtual-environment and Compose run are unverified until the rehearsal in section 5.

## 8. Jira and GitHub evidence links

Jira (project KAN on `https://lucastaooo.atlassian.net`; copy the board URL from the browser when filling the final list):

| Issue | Subject |
|---|---|
| [KAN-35](https://lucastaooo.atlassian.net/browse/KAN-35) | F.06 analytics |
| [KAN-36](https://lucastaooo.atlassian.net/browse/KAN-36) | R.02 no-model run |
| [KAN-37](https://lucastaooo.atlassian.net/browse/KAN-37) | E.10 coverage map |
| [KAN-38](https://lucastaooo.atlassian.net/browse/KAN-38) | R.05 final delivery package |
| [KAN-39](https://lucastaooo.atlassian.net/browse/KAN-39) | Gate 2 model scope decision |
| [KAN-40](https://lucastaooo.atlassian.net/browse/KAN-40) | B: live interfaces (#91, #95, #88) |
| [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41) | C: #17 / #61 and demo material |
| [KAN-42](https://lucastaooo.atlassian.net/browse/KAN-42) | A: A1.06 showcase (PR #94) |
| [KAN-16](https://lucastaooo.atlassian.net/browse/KAN-16) | A3 logistics sandbox |

GitHub pull requests and issues (`https://github.com/shuxiachai/returnops-au`):

| Link | Subject | State on 22 October 2026 |
|---|---|---|
| [PR #78](https://github.com/shuxiachai/returnops-au/pull/78) | A2.07 Founder decision boundary | Merged 22 Oct (`0758696681cc706fda14ba378b7baa8e8c6580b3`) |
| [PR #87](https://github.com/shuxiachai/returnops-au/pull/87) | A2.06 notification outcome ([record](a206-notification-outcome.md)) | In main |
| [PR #89](https://github.com/shuxiachai/returnops-au/pull/89) | R.02 driver and `end-to-end-no-llm` job | In main; first result run 39634415393 |
| [PR #90](https://github.com/shuxiachai/returnops-au/pull/90) | F.06 analytics | Merged 22 Oct; run 39701255799 |
| [PR #92](https://github.com/shuxiachai/returnops-au/pull/92) | E.10 / F.06 documentation close-out | In main |
| [PR #93](https://github.com/shuxiachai/returnops-au/pull/93) | Driver demo mode and Deploy from zero | In main |
| [PR #94](https://github.com/shuxiachai/returnops-au/pull/94) | A1.06 advisory Coordinator showcase | Draft, pending merge |
| [Issue #88](https://github.com/shuxiachai/returnops-au/issues/88) | B: follow-ups from the PR #60 review | Open (B) |
| [Issue #91](https://github.com/shuxiachai/returnops-au/issues/91) | B: live Founder decisions and analytics in the frontend | Open (B) |
| [Issue #95](https://github.com/shuxiachai/returnops-au/issues/95) | B: Founder facts card and mock facts shape | Open (B); subject to confirm on GitHub |

Also link the CI run of the submission tag (section 3 step 1) and [run 39634415393](https://github.com/shuxiachai/returnops-au/actions/runs/39634415393).

## 9. R.05.b record (after the demo)

Date and time slot; machine and OS; package SHA-256 (must equal section 3); which demo segments ran live and which used fallbacks; refusals or failures with their codes; questions asked; who presented each segment. The demo must use the R.05.a version; any later change is recorded separately under the rules then in force.

AI-assisted implementation and metadata preparation; author shuxiachai.
