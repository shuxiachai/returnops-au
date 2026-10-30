# Stage 2 submission runbook (R.05.a and R.05.b)

Owner: A Jingbo Chai (integrates and submits). Reviewer: C Yuwei Tao. Work package R.05 and its two course sub-checks, R.05.a source submission and R.05.b final-week demo, in the unchanged [work packages](08-delivery-work-packages.md). This runbook turns the open items of the [submission checklist](28-stage2-submission-checklist.md) into steps with owners and dates. As of 24 October 2026 (Sydney) only an early rehearsal from a zip of `main` has been run (section 5, pass 0); no tag, submission package, upload or contribution statement exists yet. A course submission receipt is not R.05 acceptance (docs/08, R.05).

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
| 24 Oct | Pass 0: early rehearsal from a zip of `main` on A's machine (section 5) | A |
| 26 Oct | Canvas item opens; ask the tutor at the Monday practical how the contribution statement is to be handed in (the item accepts zip files only) and record the answer in section 4; demo script final; each speaker's own wording. Recorded on 26 October (the tutor's answer as reported by A): the statement is handed in through Canvas directly, inside the submission zip (section 3, step 4); Week 13 slot chosen by A: Monday 2 November 2026, 16:00-17:00 Sydney | A; A, B, C |
| 27-28 Oct | Contribution statement draft sent to the three; A3 tutor disposition requested and recorded; first full rehearsal on A's machine; B's Issue #111 items 1-6 merged or recorded as not merged (B's Issues #88, #91 and #95 were closed and C's PRs #17 and #61 merged by 23 October) | A; B; C |
| 29 Oct, 19:00 | Clean-machine rehearsal (section 5, pass 1), about 2 hours; time set by A on 26 October (Issue #137) | A runs, B checks UI steps, C records |
| 30-31 Oct | Fixes; contribution statement final; tag and package (section 3) | A; all three sign off the statement |
| 1 Nov, before noon | Canvas upload and download-and-reopen check (section 4) | A |
| 1 Nov, 14:00 | Rehearsal from the downloaded Canvas package (section 5, pass 2); the demonstration is the next day, so this pass cannot slip beyond the morning of 2 November | A, B, C |
| 2 Nov, 16:00-17:00 | Week 13 demonstration (slot chosen by A on 26 October) | A, B, C |

## 3. Packaging (R.05.a)

Preconditions: every pull request intended for submission is merged into main and the CI run of that main commit has finished with all jobs successful; the README overview (its Status section re-dated on the packaging day) and docs/41, docs/43, docs/45-47 describe the submitted state; anything not merged is listed in the known gaps (section 7).

1. Choose the commit: the main commit whose CI run is green. Record its full SHA and the run URL.
2. Tag it (name is a proposal): `git tag -a stage2-submission-v1 <sha> -m "Stage 2 source submission"`, then `git push origin stage2-submission-v1`. The tag message carries no AI tool attribution (repository rule).
3. Zip the tag: `git archive --format=zip --prefix=returnops-au/ -o returnops-au-stage2-submission-v1.zip stage2-submission-v1`. `git archive` packs only files tracked at the tag, so git-ignored local material (`.env`, `.venv/`, `node_modules/`, `tmp/`, `dist/`, `__pycache__/`, `data/private/`) is left out. For a zip given a commit or a tag, git stores the commit ID as the archive comment; check it with `unzip -z` or Python's `zipfile` (verified for a commit in pass 0, section 5).
4. Add the contribution statement: the tutor confirmed on 26 October that it is handed in through Canvas directly (section 2), so append `CONTRIBUTION-STATEMENT-Group10.pdf` at the root of the zip, next to `returnops-au/`, with Python's `zipfile` in append mode (`zipfile.ZipFile(path, 'a').write(pdf, 'CONTRIBUTION-STATEMENT-Group10.pdf')`); the repository tree inside `returnops-au/` stays untouched. Then hash: PowerShell `Get-FileHash -Algorithm SHA256 returnops-au-stage2-submission-v1.zip`; bash `sha256sum returnops-au-stage2-submission-v1.zip`. Record the value and the size in bytes.
5. Content check: list the archive (`unzip -l`, or `tar -tf` on Windows) and confirm that none of these is present:
   - `.env` (only `.env.example` may appear), `auth.json`, `sessions.json`, `*.pem`, `*.key`, any file holding a value for `RETURNOPS_MODEL_API_KEY` or a database password;
   - private directories (`tmp/`, `tmp/demo-shop`, `tmp/demo-cups`, driver output directories), `node_modules/`, `.venv/`, `dist/`, `__pycache__/`;
   - any student ID inside `returnops-au/` (the repository is public); the statement PDF sits only at the zip root, outside the repository tree.
6. Unzip into a new empty directory and run `python -B tools/model-checks/check.py --skip-baseline` there (an archive has no Git history, so the WBS Git comparison is skipped explicitly). Record the "Static check groups" line.

## 4. Canvas upload and download-and-reopen check

1. Open "Stage 2 Code Submission" from the course's Assignments list (open from 26 October); confirm that it still shows due 1 November 23:59 Sydney and zip files only; record any change.
2. Upload `returnops-au-stage2-submission-v1.zip` (with the statement PDF inside at the zip root, section 3 step 4). A separate PDF cannot be uploaded to a zip-only item, and the tutor named no other channel (26 October). One member uploads for the group; the submission is shared by all three.
3. Record the Canvas receipt: submission time shown by Canvas, attempt number, file names and sizes; keep a screenshot outside the repository.
4. Download the submitted zip from Canvas into a new empty directory. Compute its SHA-256: it must equal the value from section 3 step 4. Check the archive comment (commit ID) and that `returnops-au/README.md` opens with the project overview, whose Status section carries the packaging date.
5. Open the statement PDF from the downloaded zip; check group number (10), names, student IDs and that each criterion row totals 100%.
6. If anything differs, re-upload before the deadline and record both attempts; never edit a record afterwards to hide the first.

R.05.a record (to fill): deadline source and wording; tag; commit SHA; CI run URL; package file name, size and SHA-256; Canvas item title; receipt time and attempt; reopen check result; known gaps attached (yes/no); C's pre-generated S6 evidence bundle (source commit and manifest `content_id`).

## 5. Clean-machine rehearsal checklist

Derived from the README chapter [Deploy from zero](../README.md#deploy-from-zero---22-october-2026-sydney), with `git clone` replaced by the package. Pass 1 (29 October) uses the zip produced in section 3 on a machine without this repository's ignored files; pass 2 (after 1 November) uses the zip downloaded from Canvas, as [docs/28](28-stage2-submission-checklist.md) requires. Record the package hash, environment, commands, migration, synthetic setup and outcome for each pass.

Since 27 October 2026 the Windows script `tools/demo/demo.ps1` ([README, Demo machine script](../README.md#demo-machine-script-windows)) runs steps 4 to 7 (`prepare`), 9 to 11 (`start`), 17 (`s5`) and the Compose and directory part of step 20 (`stop -RemoveData`); `check` prints the versions for step 1. Passes 1 and 2 use it and record any step where it stops; the commands in the table stay the fallback, and step 8 stays manual. Since 29 October 2026 `tools\demo\start-demo.cmd` runs `stop -RemoveData`, `prepare` and `start` on a double-click (opening Docker Desktop first when needed) and `tools\demo\stop-demo.cmd` runs `stop -RemoveData`; when Windows has reserved 5173, step 11's page is on the port that `start` prints.

Since 30 October 2026 the Week 13 demonstration runs on Railway, and the local steps stay the fallback ([README, Railway deployment](../README.md#railway-deployment-since-30-october-2026); [docs/46](46-gate2-roadmap.md) section 9). Pass 2 adds the Railway path to the table's local steps:
1. `railway link` in the folder downloaded from Canvas;
2. `demo.ps1 cloud` (`railway up`, then the sessions copied to `tmp\railway-shop` without showing them);
3. S2 to S4 on the service's Railway address;
4. `demo.ps1 cloud-fresh` once, to check that new sessions arrive.

Record the build time, the time to ready, and any step where it stops. S5 stays on the local deployment.

| # | Step | Expected output | Who | Date | Result |
|---|---|---|---|---|---|
| 1 | Record machine, OS, CPython (3.12; 3.12.4 or later on Windows), Docker and Compose, Node and npm versions | Versions within README section 0 | A | 29 Oct / pass 2 | |
| 2 | Obtain the zip (pass 1: section 3; pass 2: Canvas download); SHA-256 | Equals the recorded hash | A | | |
| 3 | Unzip into a new directory | `returnops-au/` with README, `compose.yaml`, `Dockerfile`, lock files | A | | |
| 4 | Create `.venv`; `pip install --require-hashes -r requirements-dev.lock`; `pip install --no-deps --no-build-isolation -e .`; `pip check` | Installs without error; `pip check` reports no broken requirements | A | | |
| 5 | `python -B tools/environment/local.py init`; set `API_PORT=8001` in `.env` | `Created ignored local configuration with a fresh password; no secret displayed.` | A | | |
| 6 | First `docker volume ls`: if `returnops-au-f02_postgres-data` exists from an earlier deployment, follow the README pitfall (reuse that deployment's `.env`, add `-p <name>` to every Compose command, or remove the volume deliberately; on the demonstration machine it was removed on 24 October 2026 and must stay absent). Then `docker compose config --quiet`; `docker compose up --build -d --wait --wait-timeout 180`; `docker compose ps -a` | `db` healthy, `migrate` Exited (0), `api` healthy | A | | |
| 7 | `/health/live` and `/health/ready` on port 8001 | `{"status":"alive"}`; `{"status":"ready"}` | A | | |
| 8 | Host migration via `local.py run python -m alembic upgrade head` | Exits 0 (README: not verified) | A | | |
| 9 | `demo.py provision` for `tmp/demo-shop` with `--order-investigation --fixed-proposal --founder-manual` (the last flag only for this store, never for `tmp/demo-cups`) | `Private synthetic demo registration completed. ...` | A | | |
| 10 | `demo.py serve --auth-file ... --port 8000 --fixed-proposal --founder-decisions` (plus `--model-showcase` only with a key) | `http://127.0.0.1:8000/health/ready` ready | A | | |
| 11 | `apps/web`: `npm ci --no-audit --no-fund`; `npm run dev`; open `http://localhost:5173` | Page loads; Vite proxies `/v1` to 8000 | B | | |
| 12 | Token login as customer and as Founder in two browser profiles | **Auth Tokens** shows `Valid: <principal> (<ROLE>)` | B | | |
| 13 | Demo S2: case without order reference, answer `SYN-1001`; a second case with `SYN-CONFLICT` | Question shown; first case reaches `RISK_REVIEW`; second case `ESCALATED` with an order-lookup block | B | | |
| 14 | Demo S3: case list, detail, audit, analytics; **Manual Takeover** on the `SYN-CONFLICT` case | The block reason is shown; the decision is accepted and the case moves to `NOTIFICATION_PENDING`; **Decision & Outcome** shows the manual takeover and a `PENDING` notice; the customer sees "The shop has decided; a notice is on its way" (pass 0, before `--founder-manual`: `MANUAL_HANDLING` refused with 403 `FORBIDDEN`) | B | | |
| 15 | Demo S4 (only with a key; PR #94 is in `main`): facts on the case; one rejected reply | Facts shown, or WARNING `outcome=REJECTED`; record tokens and latency from `run_once.py` evidence | A | | |
| 16 | Latency check on the running `demo.py serve` API, before it is stopped: 100 sequential `POST /v1/cases` as `synthetic_customer_b` (each with a new `Idempotency-Key`) and 100 `GET /v1/cases/{case_id}` of one of those cases, timed on the client with `httpx` from the locked environment | p50 and p95 in milliseconds for each call, the number of non-2xx answers (expected 0), the machine and the time; recorded here as a demonstration-machine observation, not a load test, and copied to [docs/48](48-agile-evidence-and-technology-data.md) row 1 only if the rehearsal passes | A | | |
| 17 | Stop `serve`; provision `tmp/demo-cups` without `--order-investigation`, `--fixed-proposal` and `--founder-manual` (the driver refuses a store that already holds lifecycle authorities); set `DATABASE_URL`; driver with `--identities --api-port 8000 --keep-api --allow-existing-data` | `R.02 demo mode: driver result PASSED (see run-receipt.json).` | A | | |
| 18 | Founder UI with `demo_cups_founder`: inspect the driver's case | Status `COMPLETED`; **Decision & Outcome** shows the approval, both operations `SUCCEEDED`, **Download label (PDF)** and the `SENT` notice | B | | |
| 18a | Demo S6 (C): in Terminal 3 run the C1 pilot summary and the four selected C2 tests (docs/45 S6 item 4); show the evidence bundle pre-generated on macOS or Linux | Pilot: ranked recall 16/22, returned-set recall 20/22, citation outcomes 8 of 8; `4 passed`; the bundle's commit and `content_id` match the R.05.a record | C | | |
| 19 | Timed run of the whole demo script | Within 12 minutes (the limit since 28 October 2026; planned 11:30, [docs/45](45-stage2-demo-script.md) section 3); note overruns per segment | A, B, C | | |
| 20 | Clean up: Ctrl+C; delete `tmp/demo-shop`, `tmp/demo-cups`; **Clear token**; unset model variables; `docker compose down -v` (with the same `-p <name>` if one was used), so that the next fresh deployment does not meet this run's volume and password | No private files left; `docker volume ls` lists no `returnops-au-f02_postgres-data` | A | | |

### Pass 0 record (24 October 2026, Sydney)

An early pass on the lead's machine, which is also the Week 13 demonstration machine, run before pass 1 so that problems surface early. It used a zip of `main`, not the submission tag, so it is not the R.05.a record.

| Item | Record |
|---|---|
| Package | `git archive --format=zip --prefix=returnops-au/` of `main` at `46a8afaa0b284e2528398cb6352469878e562008` (the merge of #118; the main CI run 39963508928 of that commit had not finished when the zip was made); 14,744,474 bytes; SHA-256 `2ce9ed42349e469014f7b8c64ddcd5f159c4163b36097964fbce71416f95539a`; 796 entries |
| Section 3 checks | The zip comment equals the commit ID (read with Python's `zipfile`); no forbidden name; no student ID; no assignment of `POSTGRES_PASSWORD` or `RETURNOPS_MODEL_API_KEY` outside `.env.example`; `python -B tools/model-checks/check.py --skip-baseline`: `Static check groups: 6/6 passed.` |
| Environment | Windows 11 Home China 10.0.26300; CPython 3.12.9; Docker 29.6.2 with Compose v5.3.1; Node 24.14.0 with npm 11.9.0; package unzipped under the user's Downloads folder |
| Passed | Steps 1-14, 16-18 and 20, with the observations below. Times on this machine: Python dependencies 15 s (pip cache present), `docker compose up` 41 s (images cached), driver chain about 100 s |
| Not run | Step 15 (no model key in the environment and no VPN check in this pass); step 19 (needs all three members) |

Observations:

1. **Old Compose volume.** `compose.yaml` fixes the project name `returnops-au-f02`, and this machine still holds the volume `returnops-au-f02_postgres-data` from September. A fresh `local.py init` writes a password that the old data directory does not know (the README pitfall of 22 October), so this pass ran every Compose command with `-p returnops-rehearsal0` and removed its own volume at the end; the old volume was not touched. Decision of 24 October 2026 (lead): remove the old volume and deploy exactly as the README says. The lead removed `returnops-au-f02_postgres-data` by hand the same day, and `docker volume ls` confirmed it gone. Because the project name is fixed, every deployment that follows the README, rehearsal or demonstration, must end with `docker compose down -v` (step 20); otherwise the next fresh unzip meets the same password mismatch. Step 6 now starts with this check.
2. **Node.** 24.14.0 is below the README range (`^24.15.0`). `npm ci` only warned (`EBADENGINE`, from test dependencies) and the dev server ran; upgrade before pass 1.
3. **Step 13.** Without an order reference the case reached `AWAITING_INFORMATION` with the order question; after `SYN-1001` it reached `RISK_REVIEW` (case version 7). The customer page needed a manual refresh and shows raw status names (Issue #111, items 2 and 6).
4. **Step 14.** Case list, detail, audit chain (7 hash-linked events) and live analytics worked. The Founder decision `MANUAL_HANDLING` on that case was refused with HTTP 403 `FORBIDDEN` (not retryable): `demo.py provision` grants no `founder-manual-v1` OUTCOME capability, REJECT and REQUEST_REVISION check their own capabilities (`founder-reject-v1`, `founder-revision-v1`) in the same way, and APPROVE needs the review and preview grants that only the driver inserts. The docs/45 S3 fallback therefore applies (section 7, gap 10).
5. **Step 16.** 100 calls each, 0 non-2xx, client-side with `httpx` on the same machine: `POST /v1/cases` p50 192.7 ms, p95 238.3 ms; `GET /v1/cases/{case_id}` p50 180.8 ms, p95 218.9 ms. Not copied to docs/48 row 1, because that needs a passed rehearsal (step 16).
6. **Steps 17-18.** The driver printed `R.02 demo mode: driver result PASSED (see run-receipt.json).`, and the Founder console showed its case `COMPLETED` (case version 13). Stopping the kept API child let the driver finish its own cleanup (`stopping the API child (it exited by itself)`, final line PASSED, exit code 0, no `r02-private-*` directory left).
7. **Frontend items already in Issue #111 seen live:** a stale "Valid" session and the previous token pre-filled in the Auth Tokens dialog (items 1 and 12); mock demo cases and the hard-coded "Store: store_demo" label in live mode (item 3); "AI Proposal", "Autonomous" and "AI Confidence 0%" on the fixed proposal (item 4); dialogs that do not close with Esc (item 13).

### Local check of the S3 manual decision (26 October 2026, Sydney)

Not a rehearsal pass: a check of the `--founder-manual` change on the lead's machine (the demonstration machine) before its pull request, against a disposable PostgreSQL 17.11 container (same image digest as `compose.yaml`) instead of the Compose deployment.

1. `alembic upgrade head` to `0014_notification_delivery`; `demo.py provision ... --order-investigation --fixed-proposal --founder-manual` wrote two lifecycle authorities for `synthetic_au_store`: the fixed proposal (PROPOSAL) and `founder-manual-v1` (OUTCOME), nothing else.
2. `demo.py serve --fixed-proposal --founder-decisions`; a customer case with `SYN-CONFLICT` reached `ESCALATED` with an order-lookup block (`CONFLICT`, "The authorized order reference is ambiguous.") and no proposal; audit `CUSTOMER_CASE_ACCEPTED`, `CUSTOMER_INTAKE_PROCESSED`, `ORDER_INVESTIGATION_ACCEPTED`.
3. Founder console (Live API, the token handed to the page without being displayed): the block reason was shown, only **Manual Takeover** was enabled, and the confirmation named the case version and the block. The decision was accepted; the case moved to `NOTIFICATION_PENDING` (version 3 to 4) and the audit chain gained `FOUNDER_DECISION_ACCEPTED` (actor the Founder), `NOTIFICATION_REVISION_RECORDED` and `LIFECYCLE_EVENT_ACCEPTED`. The customer page read "The shop has decided; a notice is on its way".
4. Found and fixed before the pull request: after the decision the view still carried the block, so the console still offered Manual Takeover and the "only the Founder can decide" line. The target is now offered only while the case is `ESCALATED` (the server's own rule), and the line is shown only then.
5. Cleanup: services stopped, the private directory deleted, the container removed with its volume.

The same day Docker Desktop first failed to start: undeletable stale Unix socket files from 24 October (`%LOCALAPPDATA%\Docker\run` and `docker-secrets-engine`) crashed its backend, and each crash left a new one. Deleting them from WSL (`rm` under `/mnt/c/...`) worked where Windows tools failed with error 1920; then Docker started in 5 seconds. Check this before pass 1 and the demonstration.

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
| B | Web frontend: customer portal, Founder console, operations analytics page ([apps/web README](../apps/web/README.md), PR #60); [interactive demo walkthrough](35-b205-interactive-demo-walkthrough.md); live wiring: PRs #100, #101 and #102 (the last two reached `main` through #107), closing Issues #88, #91 and #95; open follow-ups #104 and #111 (state on the day) |
| C | C1 grounding and citation checks ([experiments/c1_grounding_candidate](../experiments/c1_grounding_candidate)); C2 risk-review candidate ([README](../experiments/c2_risk_candidate/README.md)); E.01/E.09 evaluation preparation ([README](../experiments/evaluation_candidate/README.md)); [C's model chain](18-member-c-model-chain.md); code PRs #59 and #68 (C1), #69 (C2), #79 (C1 to C2 handoff) and #70 (evaluation); review and receipt records #17, #61, #115 and #118 (state on the day) |

Each member also states their own AI assistance. Student IDs, percentages and task claims are confirmed by the member concerned, never by AI preparation. The final statement is uploaded to Canvas as a PDF and is not committed to the public repository.

## 7. Known gaps to attach

Attach this list (updated on the submission day) with the package, for example as a short PDF next to the contribution statement:

1. No acceptance record exists for R.02, Gate 1 or the other delivered work packages; a merge, a green CI job or a `PASSED` receipt is not acceptance.
2. Gate 2 deferred: full A1.06, A1.07, A1.08, the real C2 reviewer, E.09, R.03 and E.12 ([docs/46](46-gate2-roadmap.md)). There are no evaluation results.
3. A3 (OF-004) unmet: no carrier contract or test account; tutor disposition: **to record** (docs/46, section 5).
4. C3 (OF-001) not started: depends on R.03; tutor disposition: **to record** (as for A3).
5. Advisory model showcase: merged (PR #94, #98); first live call recorded on 22 October 2026 ([docs/44](44-coordinator-showcase.md)); results in memory only; no audit event; customers never see it; the Founder card is in since #101.
6. Frontend (state on 28 October 2026): live Founder decisions and live analytics are in the client since #102 (23 October 2026). Issue #104 is closed.
   - Issue #111: items 1-6, required before the rehearsal, are merged (#128, #130), and so are items 9 and 12 (#148). Still open and optional:
     - item 7, no size, count or text-length checks on the customer's uploads and text;
     - item 8, no copy button for the case ID;
     - item 10 in part: the mock analytics count 128 cases against 25 queue rows, and `case_demo_003` shows a $220 refund beside a $0 approval ceiling;
     - item 11, times without a time zone and an analytics filter that sends whole UTC days;
     - item 13, dialogs that do not close with Esc or manage focus.
   - Issue #122 (still open): the items are merged through #130, #132, #138, #144 and #147, and #148 added tests for #147's part, with these limits:
     - item 6 is an App-level Vitest flow in Mock Mode, not a browser end-to-end test;
     - item 7 keeps the form editable after an uncertain failure; the lodgement key is kept for the tab instead;
     - item 11 retries a staging `503` but does not serialise uploads;
     - review findings' `citation_ids` are shown as IDs, not as passage text;
     - there is no lint script: the frontend CI job runs the type check, the tests and the build.
   - B's status comment on #122 ([27 October](https://github.com/shuxiachai/returnops-au/issues/122#issuecomment-6434667859)) lists further open review findings in the merged mock and client code, none on the S2 or S3 path. Examples: the clarification request still carries `evidence_ids`, which the contract's `CustomerStatement` does not have; the `case_demo_005` fixture chain has no `FOUNDER_APPROVAL_ISSUED` event; mock audit events are not contract-shaped.
   - Left unchanged by #148 because they would change behaviour: the clarification form does not retry a staging `503`, and the lodgement retry also retries a `503` marked not retryable.
7. The only proposer is the fixed synthetic one (`fixture-no-live-model`); the risk result in the end-to-end run is the controlled PASS receiver and risk stub.
8. Proposal latency is Tier 0 (no samples): trusted start and end events are open ([docs/43](43-f06-analytics.md)).
9. The driver composes its own API; `demo.py serve` and the image default CMD do not run the governed chain; Docker evidence is the image build and import probe; the Compose API is health-only ([docs/41](41-r02-end-to-end-evidence.md)).
10. On a `demo.py serve` case only one Founder decision is live: MANUAL_HANDLING of an escalated case without a proposal (the `SYN-CONFLICT` order-lookup block), and only with `demo.py provision --founder-manual` (25 October 2026). The case then waits in `NOTIFICATION_PENDING`, because `serve` runs no notification worker. REJECT and REQUEST_REVISION need grants and states that `demo.py` does not provide (pass 0, section 5: 403 `FORBIDDEN` before the flag existed); APPROVE is shown only through the driver ([docs/45](45-stage2-demo-script.md), S3).
11. Fault injection of `UNKNOWN` and `REPLAYED` paths in an end-to-end run, and Windows file permissions, are not covered (docs/41, Deferred).
12. Scale and consistency findings of the 23 October 2026 review are open (GitHub issue #106; [docs/46](46-gate2-roadmap.md) section 8): the customer case view scans the whole audit table and fails closed above 16,384 audit rows; history snapshots are never pruned; customer reads take the exclusive fence; clarification rounds have no cap; three decision-boundary consistency items. None affects the demonstration volumes.
13. Line endings (resolved): `.gitattributes` (#108) pins LF for every text file; the 24 Python files stored with CRLF from earlier Windows commits were converted by the whitespace-only pull request #109, merged on 23 October 2026.
14. The contract operations `reconcileOperation` and `retryNotification` are not registered as routes (R.05 research record, 22 October 2026).
15. Deploy-from-zero: pass 0 (24 October 2026, section 5) ran the README chapter from a zip of `main` on the demonstration machine, except the model showcase. On 27 October 2026 the lead ran it again on the same machine from a zip of `main` at `5d67231c`, by hand: S2 as in step 13; S3 with **Manual Takeover** accepted (`NOTIFICATION_PENDING`, a `PENDING` notice, `FOUNDER_DECISION_ACCEPTED` in the audit chain); S5 driver `PASSED` and the case `COMPLETED`. The same day the Windows script `tools/demo/demo.ps1` (#146) was tested there from a zip of the same commit plus the script. Neither run is a rehearsal pass; pass 1 (29 October) and pass 2 (from the Canvas download) are still required.
16. C's candidates (C1 retrieval and citation checks, the C2 risk reviewer, the evaluation definitions) are offline and not wired into the API; the E.01 definitions and ten invented examples were merged on 28 October 2026 (#142), A answered the six E.01 decisions and the C1 excerpt question the same day ([#67](https://github.com/shuxiachai/returnops-au/issues/67#issuecomment-6458606959)), and after A confirmed the freeze C recorded it on 29 October 2026 (#152, status `FROZEN_DEFINITIONS_ONLY`): the definitions are frozen, while the pilot, the sealed Gold labels, human timing, B1 versus B4 and the whole of E.01 remain open; C1 checks citation provenance (identity, version, hash, location) but not quoted text, so a fabricated quotation with correct metadata still passes `verify_citations`, and the C1.04 excerpt check is offline annotation only until Gate 2 ([docs/46](46-gate2-roadmap.md), section 3); the ACCC real-source capture is hashed but not admitted (exact-byte review by A pending); C's evidence-bundle and timing commands and the corpus admission loader need macOS or Linux and refuse on Windows (`EVIDENCE_PLATFORM_UNSUPPORTED`), which affects S6 on the Windows demonstration machine (to settle with C before 29 October).
17. `npm audit` on 24 October 2026: no advisory in the frontend's production dependencies; 10 in development tools only (critical: `vitest` and `tinypool`; high: `vite` and `undici`; 6 moderate). `undici` and `postcss-nested` have non-breaking fixes; the others need major upgrades (`vite` 8, `vitest` 5, `tailwindcss` 4), deferred past submission. The Vite dev server listens on localhost only; the demo commands use `npm ci --no-audit --no-fund` only to shorten the install output.

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
| [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41) | C: #17, #61, #115, #118 and the demo segment |
| [KAN-42](https://lucastaooo.atlassian.net/browse/KAN-42) | A: A1.06 showcase (PR #94) |
| [KAN-16](https://lucastaooo.atlassian.net/browse/KAN-16) | A3 logistics sandbox |
| [KAN-18](https://lucastaooo.atlassian.net/browse/KAN-18) | B: customer portal (B1) |
| [KAN-19](https://lucastaooo.atlassian.net/browse/KAN-19) | B: Founder console (B2) |
| [KAN-20](https://lucastaooo.atlassian.net/browse/KAN-20) | B: UI end-to-end tests and demo fixtures |
| [KAN-21](https://lucastaooo.atlassian.net/browse/KAN-21) | B: operations analytics page (optional B3) |
| [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) | C: C1 corpus and citation verification |
| [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) | C: C2 independent risk review (runtime part deferred to Gate 2) |
| [KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25) | C: Gold set and evaluation (E.12 deferred) |
| [KAN-26](https://lucastaooo.atlassian.net/browse/KAN-26) | C: C3 image evidence (optional, not started) |
| [KAN-43](https://lucastaooo.atlassian.net/browse/KAN-43) | A: load-sensitive competition test (closed) |

GitHub pull requests and issues (`https://github.com/shuxiachai/returnops-au`):

| Link | Subject | State on 24 October 2026 (Sydney) |
|---|---|---|
| [PR #78](https://github.com/shuxiachai/returnops-au/pull/78) | A2.07 Founder decision boundary | Merged 22 Oct (`0758696681cc706fda14ba378b7baa8e8c6580b3`) |
| [PR #87](https://github.com/shuxiachai/returnops-au/pull/87) | A2.06 notification outcome ([record](a206-notification-outcome.md)) | In main |
| [PR #89](https://github.com/shuxiachai/returnops-au/pull/89) | R.02 driver and `end-to-end-no-llm` job | In main; first result run 39634415393 |
| [PR #90](https://github.com/shuxiachai/returnops-au/pull/90) | F.06 analytics | Merged 22 Oct; run 39701255799 |
| [PR #92](https://github.com/shuxiachai/returnops-au/pull/92) | E.10 / F.06 documentation close-out | In main |
| [PR #93](https://github.com/shuxiachai/returnops-au/pull/93) | Driver demo mode and Deploy from zero | In main |
| [PR #94](https://github.com/shuxiachai/returnops-au/pull/94) | A1.06 advisory Coordinator showcase | Merged 22 Oct (`6545f206`) |
| [Issue #88](https://github.com/shuxiachai/returnops-au/issues/88) | B: follow-ups from the PR #60 review | Closed 23 Oct; delivered by #100 |
| [Issue #91](https://github.com/shuxiachai/returnops-au/issues/91) | B: live Founder decisions and analytics in the frontend | Closed 23 Oct; delivered by #102 through #107 |
| [Issue #95](https://github.com/shuxiachai/returnops-au/issues/95) | B: Founder facts card and mock facts shape | Closed 23 Oct; delivered by #101 through #107 |
| [PR #59](https://github.com/shuxiachai/returnops-au/pull/59) | C: C1 offline retrieval and exact citation verification | Merged (`cdfc3c11`) |
| [PR #68](https://github.com/shuxiachai/returnops-au/pull/68) | C: reviewed-corpus admission candidate (ACCC capture) | Merged (`437b4eb6`) |
| [PR #69](https://github.com/shuxiachai/returnops-au/pull/69) | C: C2 independent risk reviewer candidate, fail-closed stub tests | Merged (`5006da1a`) |
| [PR #70](https://github.com/shuxiachai/returnops-au/pull/70) | C: evaluation guide and synthetic scorer accounting | Merged (`d9813d6d`) |
| [PR #79](https://github.com/shuxiachai/returnops-au/pull/79) | C: C1 to C2 handoff regression and validation evidence | Merged (`e35c61d2`) |
| [PR #98](https://github.com/shuxiachai/returnops-au/pull/98) | A: explicit opt-in for plain http to a private model proxy | Merged (`51862f4b`) |
| [PR #100](https://github.com/shuxiachai/returnops-au/pull/100) | B: customer edits kept safe while a submission is pending (Issue #88) | Merged (`85e5d944`) |
| [PR #101](https://github.com/shuxiachai/returnops-au/pull/101), [PR #102](https://github.com/shuxiachai/returnops-au/pull/102) | B: Founder facts card (Issue #95); live analytics and decisions (Issue #91) | Merged into B's stacked branches; reached `main` through [PR #107](https://github.com/shuxiachai/returnops-au/pull/107) (`e4afc332`) |
| [PR #108](https://github.com/shuxiachai/returnops-au/pull/108) | A: robustness fixes from the 23 October review | Merged (`b04d0a32`) |
| [PR #109](https://github.com/shuxiachai/returnops-au/pull/109) | A: remaining CRLF Python files normalised to LF | Merged (`c4d08799`) |
| [PR #110](https://github.com/shuxiachai/returnops-au/pull/110) | A: docs/48 agile evidence and technology data | Merged (`c4151a11`) |
| [PR #112](https://github.com/shuxiachai/returnops-au/pull/112), [PR #114](https://github.com/shuxiachai/returnops-au/pull/114) | A: same-key re-send in the competition tests; isolated, fail-closed driver cleanup (answer to C's review) | Merged (`2a4d3ae2`, `55fd717a`) |
| [PR #113](https://github.com/shuxiachai/returnops-au/pull/113) | A: CI speed-up data and the rehearsal latency check | Merged (`0c2de081`) |
| [PR #115](https://github.com/shuxiachai/returnops-au/pull/115), [PR #118](https://github.com/shuxiachai/returnops-au/pull/118) | C: R.02 review, failure probes and cleanup matrix | Merged (`33b0a93c`, `46a8afaa`) |
| [PR #116](https://github.com/shuxiachai/returnops-au/pull/116), [PR #119](https://github.com/shuxiachai/returnops-au/pull/119) | A: driver receipt and cleanup reporting | Merged (`a971978e`, `90fa35ec`) |
| [PR #117](https://github.com/shuxiachai/returnops-au/pull/117) | A: README overview first | Merged (`291cde84`) |
| [PR #120](https://github.com/shuxiachai/returnops-au/pull/120) | A: pass 0 rehearsal record | Merged (`ecf68527`) |
| [Issue #103](https://github.com/shuxiachai/returnops-au/issues/103) | A: load-sensitive same-key competition test | Closed 23 Oct after #114 |
| [Issue #104](https://github.com/shuxiachai/returnops-au/issues/104), [Issue #111](https://github.com/shuxiachai/returnops-au/issues/111) | B: review follow-ups; frontend demo readiness (items 1-6 before 29 Oct) | Open (B) |
| [Issue #106](https://github.com/shuxiachai/returnops-au/issues/106) | A: hardening backlog from the 23 October review | Open (A); deferred past submission ([docs/46](46-gate2-roadmap.md) section 8) |

Also link the CI run of the submission tag (section 3 step 1) and [run 39634415393](https://github.com/shuxiachai/returnops-au/actions/runs/39634415393).

## 9. R.05.b record (after the demo)

Date and time slot; machine and OS; package SHA-256 (must equal section 3); which demo segments ran live and which used fallbacks; refusals or failures with their codes; questions asked; who presented each segment. The demo must use the R.05.a version; any later change is recorded separately under the rules then in force.

AI-assisted implementation and metadata preparation; author shuxiachai.
