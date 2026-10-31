# ReturnOps AU

ReturnOps AU is the Group 10 project for ELEC5620 Model-Based Software Engineering (University of Sydney, 2026): a returns assistant for small Australian online shops. A customer describes a problem in plain words; the system asks only for what is missing, checks the order, prepares a non-executable proposal with a risk review, and the shop's Founder approves exactly one previewed action. Only after that approval does the system run the simulated return, the parcel label and the customer notification. All providers are mocks; no real money moves and no real customer data is used.

**Start here:** [run it](#run-it-week-13-demonstration) · [what is in the system](#what-is-in-the-system) · [where AI is used](#where-ai-is-used-and-where-it-is-not) · [how we worked](#how-we-worked) · [known gaps](#known-gaps) · [deploy from zero](#deploy-from-zero---22-october-2026-sydney)

## Status (30 October 2026)

- The Gate 1 scope is delivered on `main`: the governed case lifecycle, the customer and Founder HTTP APIs, exact-scope approval, the simulated return, label, PDF and notification chain, read-only analytics, the web frontend with a live API mode, and an advisory model extraction that is off by default.
- Since 23 October:
  - the frontend items required for the rehearsal (Issue #111 items 1-6) and most of Issue #122 are merged (#128, #130, #133, #138, #144, #147, #148);
  - on a `demo.py serve` deployment the Founder can take over an escalated case (#132, `--founder-manual`);
  - `tools/demo/demo.ps1` runs the deployment steps on the Windows demonstration machine (#146), and since 29 October `tools/demo/start-demo.cmd` starts the demo on a double-click (#154);
  - C fixed the cleanup of interrupted timing exports (#141), rechecked the R.02 child-stop fix of #136 (#140), added the E.01 definitions (#142) and recorded their freeze as definitions only after A's confirmation (#152, 29 October); C's S6 segment fits its 90 seconds (#155);
  - the Week 13 demonstration runs on Railway, with the local deployment as the fallback (#156, #157, 30 October); S4's live model call and S5's driver stay on the local deployment.
- On 30 October four independent read-only reviews of `main` and a check against the Stage 2 rubric led to the fixes in the pull request that carries this section: a case no longer stays in UNDER_INVESTIGATION after a passing database delay or when a photo is lodged without an order reference; an unmatched reference is asked again with a reason; the Founder queue no longer hides the Inspect column on narrow screens; the Railway upload leaves `.env`, `.venv` and `tmp` behind; the R.02 driver refuses a database clock that is more than 2 s off; and the agile and technology evidence in [docs/48](docs/48-agile-evidence-and-technology-data.md) now runs to 30 October with a burn-down chart of the final iteration.
- Every change reaches `main` through a pull request and the full CI matrix: offline contracts and models, eight PostgreSQL parts, the no-LLM end-to-end driver and the web frontend.
- Rehearsals: pass 0 from a zip of `main` ran on 24 October. Pass 1 (29 October) was not held as planned; the lead's runs on 27 and 29 October and the Railway trial of 30 October cover part of it. Pass 2 from the Canvas download (1 November) is still to run ([docs/47](docs/47-stage2-submission-runbook.md), section 5).
- The full three-role LLM orchestration (Gate 2) is deliberately deferred; see [docs/46](docs/46-gate2-roadmap.md).
- The dated records further down this file keep the history of every adoption verbatim; where they differ from this section, this section is current.

## Run it (Week 13 demonstration)

| Step | Where |
|---|---|
| Week 13 on Railway (the lead's choice since 30 October 2026), the local script as fallback | [Railway deployment](#railway-deployment-since-30-october-2026); `tools\demo\cloud-demo.cmd` |
| Windows demo machine: steps 1 to 5 with one script (or a double-click on `tools\demo\start-demo.cmd`), the steps below as fallback | [`tools/demo/demo.ps1`](tools/demo/demo.ps1); [Demo machine script](#demo-machine-script-windows) |
| Prerequisites, Python environment, `.env`, Docker Compose database | [Deploy from zero](#deploy-from-zero---22-october-2026-sydney), steps 0 to 2 |
| Demo identities, API with workers, web frontend and token login | the same chapter, steps 3 and 4 |
| One governed case from lodging to label and notification | the same chapter, step 5, and the [R.02 driver](tools/r02/README.md) |
| The live presentation, segment by segment | [docs/45 demo script](docs/45-stage2-demo-script.md) |
| Packaging, Canvas upload and the clean-machine rehearsal | [docs/47 submission runbook](docs/47-stage2-submission-runbook.md) |

## What is in the system

| Part | What it does | Details |
|---|---|---|
| Customer portal and API | Lodge a return in plain words, answer targeted questions, upload evidence (JPEG, PNG or PDF), track the case | [docs/21](docs/21-customer-flow.md), [apps/web](apps/web/README.md) |
| Order investigation | Match the case to a synthetic order, and ask for a reference when it is missing | [docs/22](docs/22-a104-synthetic-order-provider.md), [docs/23](docs/23-order-investigation.md) |
| Proposal and risk review | A fixed, non-model proposal and a controlled risk review in the Gate 1 scope | [docs/29](docs/29-a105-fixed-proposal-runtime.md), [docs/33](docs/33-a201-pass-review.md) |
| Founder console and decisions | Case queue, case detail and audit; approve, reject, request revision or take over manually, against the exact previewed scope | [docs/40](docs/40-founder-decision-http-boundary.md), [docs/35](docs/35-a201-preview-approval.md), [apps/web](apps/web/README.md) |
| Governed simulated execution | After approval only: return, parcel label, label PDF and customer notification through mock providers, each checked against the approved scope | [docs/37](docs/37-a202-approval-admission.md), [docs/39](docs/39-a203-core-return-execution.md), [notification](docs/a206-notification-outcome.md) |
| Operations analytics | A read-only snapshot of case counts, risk outcomes and proposal latency | [docs/43](docs/43-f06-analytics.md) |
| End-to-end evidence | A private driver runs one synthetic case through the real API and records a receipt; CI runs it on every change | [docs/41](docs/41-r02-end-to-end-evidence.md) |

## Where AI is used, and where it is not

- **Used, advisory only:** a model reads the customer's statement and fills a typed facts card for the Founder (issue category, requested outcome, assessment and a short summary). The reply must pass a fail-closed acceptance chain; customers never see it; it cannot change any status, proposal, decision or operation. First live result with the course's Campus Qwen model: [docs/44](docs/44-coordinator-showcase.md).
- **Prepared, not yet in the runtime:** retrieval with exact citations and an independent risk reviewer ([experiments/c1_grounding_candidate](experiments/c1_grounding_candidate), [experiments/c2_risk_candidate](experiments/c2_risk_candidate/README.md)), and the evaluation plan ([experiments/evaluation_candidate](experiments/evaluation_candidate/README.md)).
- **Deliberately not used:** no model output reaches the execution chain; approval needs a human Founder and an exact preview; execution is a separate controlled step. Roadmap: [docs/46](docs/46-gate2-roadmap.md).

## How we worked

- Requirements and models: [docs/00](docs/00-project-definition-v1.md) (FR-001 to FR-012, NFR-001 to NFR-009 and the use cases); interface contract [docs/09](docs/09-interface-contract-v1.md) and [contracts/v1](contracts/v1).
- Allocation and work packages: [docs/07](docs/07-frozen-work-allocation.md) and [docs/08](docs/08-delivery-work-packages.md); Jira project KAN.
- Iterations, feedback loops and technology data: [docs/48](docs/48-agile-evidence-and-technology-data.md); test coverage map: [docs/42](docs/42-e10-coverage-map.md).

## Known gaps

The list attached to the submission is in [docs/47](docs/47-stage2-submission-runbook.md), section 7; the hardening backlog is in [docs/46](docs/46-gate2-roadmap.md), section 8.

## Repository map

| Path | Content |
|---|---|
| `apps/api` | FastAPI application, HTTP boundaries and the demo issuer |
| `apps/web` | React and Vite web frontend |
| `packages/returnops_domain` | Domain services, lifecycle guards and PostgreSQL tables |
| `alembic` | Database migrations |
| `contracts/v1` | Frozen OpenAPI and JSON Schema contract |
| `tests` | Contract, customer, Founder and lifecycle suites |
| `tools` | Check runner, model checks, R.02 driver, model showcase CLI and the Windows demo-machine script |
| `experiments` | C1, C2 and evaluation candidates (offline) |
| `docs`, `stage1` | Design documents, models and Stage 1 deliverables |

## Project definition

The sections below define the product and its boundaries; they are unchanged since Baseline v1.0 except where a dated note says otherwise.

## Public access and project scope

This is a synthetic-data course prototype. Use synthetic customer data and
disposable test credentials only; do not supply real customer data or provider
secrets. The actual logistics provider remains subject to tutor disposition and
account access. Simulated results do not establish a live provider integration.

This maintenance change limits branch-push CI to `main` while preserving all
pull-request checks, and removes personal machine paths from selected current
comments and context. Team authorship, assessment materials and review records
remain intact. Retained history, branches and earlier evidence are not anonymized.

Public visibility does not grant an open-source license or establish Stage 2
completion, teammate/tutor acceptance, or production readiness. Dated evidence
below retains its original scope.

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

## Delivery systems

- **Jira is required** for Agile planning and timeline evidence: epics/stories,
  sprint or Kanban status, assignee, estimate, blockers, and retrospectives.
- **GitHub remains required** for technical Issues, branches, pull requests,
  reviews, commits, and CI.
- Each delivery item uses one Jira key and links it to the corresponding GitHub
  Issue/PR, avoiding duplicated full descriptions.

## Project documents

### Stage 1 model and report navigator — 2026-09-19

Start with the [Stage 1 report, drafts and presentation archive](stage1/README.md)
for the repository materials and final PPT source.

For an A-led, AI-assisted navigation draft prepared for B's review, start with
[the Stage 1 model, requirements and report navigator](docs/stage1-model-index.md).
It routes to existing sources only: it does not revise the frozen allocation,
claim M-S.03 completion, replace individual contribution records, or establish
runtime/human acceptance. The shared report remains the
[canonical Google Doc](https://docs.google.com/document/d/1xvGO8EA_yZwWj1It3UM7AKDFEoQjsj5eJJXbCz4bcnc);
the repository's modular team report remains a separate candidate.

The [Stage 1 cloud report v0.4 snapshot](stage1/reports/v0.4/README.md)
is the current repository-readable snapshot of the canonical Google Doc. Its
README records the frozen source and exact retrieval, rendering, and native-format
limitations; the native Google Doc remains authoritative.

The [archived v0.3 cloud snapshot](stage1/reports/v0.3/README.md)
retains the 3 October 2026 PDF/DOCX exports and Markdown rendition as historical
evidence; it is not the current report snapshot.

### Reading order and member entry points

Start with the course requirements, then the product definition, frozen allocation
and delivery work packages. Use the submission checklist when assembling the final
report/video. The links below are navigation, not a second task or status board.

| What you need | Read here |
|---|---|
| Current course requirements and rubric | [Course requirements and A/B/C evidence map](docs/19-course-assessment-requirements.md) |
| Product scope, ownership and task acceptance | [Project definition](docs/00-project-definition-v1.md) → [Frozen allocation](docs/07-frozen-work-allocation.md) → [Delivery work packages](docs/08-delivery-work-packages.md) |
| Final report, video, interview and submission checks | [Stage 1 readiness / R.04 checklist](docs/11-stage1-readiness.md) |
| Final Stage 1 slides and A/B/C script — synced 17 October | [Preserved nine-slide PPTX, 560-word spoken script and Drive source checks](stage1/presentation/README.md); this archive update is not a new course submission |
| A: personal models and design rationale | [A model chain](docs/12-member-a-model-chain.md), [A design decisions](docs/14-member-a-design-decisions.md), [A review PR #11](https://github.com/shuxiachai/returnops-au/pull/11) |
| B: intake/UI work and model-index integration | [B review PR #8](https://github.com/shuxiachai/returnops-au/pull/8); use its actual files/review history, with responsibilities fixed by docs/07–08 |
| C: personal models and report text | [C model chain and Stage 2 implementation trace](docs/18-member-c-model-chain.md), [C Stage 1 report draft](stage1/drafts/member-c-stage1-draft.md) |
| C: figures, actual contribution and explanation | [Editable PUML and SVG figures](docs/diagrams/member-c), [Personal contribution / interview worksheet](stage1/drafts/member-c-contribution-and-interview.md), [Dated course-alignment checks](docs/reviews/member-c-course-alignment-20260914.md) |
| C: current Stage 2 technical preparation | [C1 grounding](experiments/c1_grounding_candidate/README.md), [C2 risk / S6 handoff](experiments/c2_risk_candidate/README.md), [Evaluation definitions and evidence](experiments/evaluation_candidate/README.md); current follow-up [Issue #123](https://github.com/shuxiachai/returnops-au/issues/123) |
| Shared structure and team integration | [Class model](docs/diagrams/01-domain-class-diagram.md), [Composite views](docs/13-shared-composite-structure.md); C's proposed Object slice is in the figure directory above, for A review and B indexing |
| Workflow and evidence | [Jira/GitHub workflow](docs/03-team-and-github-workflow.md), [Model-check instructions](tools/model-checks/README.md) |

C's entry links above now use the adopted files in this checkout (24 October
2026). [PR #12](https://github.com/shuxiachai/returnops-au/pull/12) and
[PR #13](https://github.com/shuxiachai/returnops-au/pull/13) remain historical
review locations; C's later #17/#61/#115/#118 follow-ups are also merged.
Technical adoption does not establish personal explanation, actual contribution
confirmation or team acceptance. Keep editable models alongside report-sized
views and preserve the dated history below.

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
- [Isolated F.03 security component — PR #15 review candidate and reproducible tests](docs/18-f03-security-component.md)
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

## Technical chapters

The dated chapters below describe how to deploy, run and verify the delivered system.

## Deploy from zero - 22 October 2026 (Sydney)

Owner A (`shuxiachai`, Jingbo Chai). This chapter puts in order the commands
that the repository files already define, from an empty machine to the web
frontend showing a live case. Each step names its source. It changes no code,
ownership or acceptance state. docs/10 records the virtual-environment and
Compose steps as executed on 7 September 2026 (then at migration
`0001_environment`); everything else here was derived from the files and is
marked **(not verified)** where no run is recorded. No step below was executed
while this chapter was written.

### 0. Prerequisites

| Need | Source |
|---|---|
| CPython 3.12 (`>=3.12,<3.13`); on Windows 3.12.4 or later, because `demo.py` and the R.02 driver refuse earlier 3.12 releases there (private 0700 directory handling) | `pyproject.toml`, `apps/api/returnops_api/demo.py`, `tools/r02/api_child.py` |
| Docker with Compose v2; images pinned by digest (`postgres:17-bookworm`, `python:3.12-slim-bookworm`) | `compose.yaml`, `Dockerfile` |
| Node.js `^22.22.2 \|\| ^24.15.0 \|\| >=26.0.0`, npm 10 or later | `apps/web/package.json` |
| Free loopback ports: 5433 (`DB_PORT`), the `API_PORT` of `.env`, 8000 (the API the frontend proxies to) and 5173 (Vite; the demo machine script moves to the next usable port when Windows has reserved 5173) | `.env.example`, `apps/web/vite.config.ts` |

### 1. Python environment and `.env` (docs/10 section 2)

PowerShell (Windows):

```powershell
git clone https://github.com/shuxiachai/returnops-au.git
cd returnops-au
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B tools/environment/local.py init
```

bash (Linux/macOS; docs/10 says to replace the interpreter with `.venv/bin/python`):

```bash
git clone https://github.com/shuxiachai/returnops-au.git
cd returnops-au
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/python -B tools/environment/local.py init
```

Line endings: `.gitattributes` checks every text file out with LF on every
platform, so a Windows clone with `core.autocrlf=true` still gets byte-exact
files; the digest-pinned C1 corpus fixtures and the CI "no carriage return"
checks depend on this (a clone made before 23 October 2026 needs
`git add --renormalize .` or a fresh clone).

`requirements-dev.lock` is needed, not only `requirements.lock`: the R.02
driver uses `httpx`, a development dependency. `local.py init` creates the
git-ignored `.env` once (0600, never overwritten, nothing secret printed) with
`POSTGRES_USER=returnops_dev`, `POSTGRES_DB=returnops_f02`, a fresh random
48-hex-character `POSTGRES_PASSWORD`, `DB_PORT=5433` and `API_PORT=8000`.
Expected output: `Created ignored local configuration with a fresh password; no secret displayed.`
Then change `API_PORT=8000` to `API_PORT=8001` in `.env`, so that the Compose
API does not take 8000, which the frontend proxy needs for the demo API (docs/10
records the same change on the lead's machine). Never print `.env` or the full
`docker compose config`.

### 2. Database, migration and health-only API (`compose.yaml`, `Dockerfile`)

```powershell
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps -a
Invoke-RestMethod http://127.0.0.1:8001/health/live
Invoke-RestMethod http://127.0.0.1:8001/health/ready
```

```bash
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps -a
curl -s http://127.0.0.1:8001/health/live
curl -s http://127.0.0.1:8001/health/ready
```

Pitfall seen on 22 October 2026: a volume left by an earlier deployment on the
same machine (the project name is fixed to `returnops-au-f02`, so every checkout
shares the volume `returnops-au-f02_postgres-data`, and PostgreSQL keeps the
password of the existing data directory) makes `migrate` exit 1 while `db`
reports healthy; `docker compose up --wait` only says the dependency failed, and
`docker compose logs migrate` shows the fixed `Database migration failed` line.
Either reuse that deployment's `.env`, or start under another project name
(`docker compose -p returnops-live up --build -d --wait --wait-timeout 180`,
then use `-p returnops-live` on every later command), or remove the old volume
deliberately (`docker compose down -v`, or `docker volume rm
returnops-au-f02_postgres-data`; this deletes its data).

Order inside Compose: `db` (PostgreSQL 17, healthy through `pg_isready`,
published only on `127.0.0.1:DB_PORT`) -> `migrate` (`python -m alembic upgrade
head`, must exit 0) -> `api` (the image CMD, `uvicorn
returnops_api.main:create_app --factory` on container port 8000, published on
`127.0.0.1:API_PORT`). Expected: `ps -a` shows `db` healthy, `migrate` Exited
(0) and `api` healthy; `/health/live` returns `{"status":"alive"}` and
`/health/ready` returns `{"status":"ready"}` (HTTP 503 `{"status":"not_ready"}`
while the database is unreachable). Compose sets no `RETURNOPS_AUTH_FILE`, so
this API starts without an authentication configuration and without workers
(`main.py`), and its customer and Founder routes fail closed with 503 (docs/21).
It is the health-only container check, not the demo API. Stop the project with
`docker compose stop` (keeps the volume).

The same migration can also run from the host against the Compose database:
`local.py run` builds `DATABASE_URL` from `.env` for `127.0.0.1:DB_PORT`
without printing it **(not verified)**:

```powershell
.\.venv\Scripts\python.exe -B tools/environment/local.py run python -m alembic upgrade head
```

```bash
.venv/bin/python -B tools/environment/local.py run python -m alembic upgrade head
```

### 3. Interactive demo identities and API (`demo.py`, docs/16, docs/21)

`demo.py provision` needs a new absolute directory whose parent exists
(`tmp/` is git-ignored) and writes `auth.json` and `sessions.json` there; the
sessions last 899 s. Since 31 October 2026 it also writes `passwords.json` (a
generated password for each of the three people, private like the tokens) and
`credentials.json` (their scrypt hashes and the store); with `RETURNOPS_DEMO_PASSWORD` set
(8 to 128 characters) all three get that password instead (31 October 2026). `serve --accounts` reads
`credentials.json` and adds password sign-in (`POST /v1/auth/login`, a new 899 s
session each time) and customer self-registration (`POST /v1/auth/register`,
which creates only CUSTOMER principals of that store and refuses an ID taken
in any letter case; a Founder is never created there). Both routes are outside contract v1 and off without the flag.
The builtin synthetic orders
(`packages/returnops_domain/order_data/synthetic_orders_v1.json`) belong to
store `synthetic_au_store` and customers `synthetic_customer_a` /
`synthetic_customer_b` (references `SYN-1001` to `SYN-1003`), so these IDs make
order lookups match. **(not verified)**

`--founder-manual` (added 25 October 2026) grants this store one authority,
`founder-manual-v1` OUTCOME, so that the Founder can record MANUAL_HANDLING on an
escalated case that has no proposal. The builtin reference `SYN-CONFLICT` is
held twice by `synthetic_customer_a`: a case lodged with it escalates with an
order-lookup block (CONFLICT), and **Manual Takeover** on it is accepted. The
case then waits in `NOTIFICATION_PENDING`, because `serve` runs no notification
worker. No other decision authority is granted: REJECT and APPROVE stay with the
step 5 driver. Never pass the flag for the step 5 store; the driver refuses a
store that already holds lifecycle authorities (`STORE_AUTHORITIES_EXIST`).

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
.\.venv\Scripts\python.exe -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir "$PWD\tmp\demo-shop" --store synthetic_au_store --customer-one synthetic_customer_a --customer-two synthetic_customer_b --founder founder --order-investigation --fixed-proposal --founder-manual
.\.venv\Scripts\python.exe -B tools/environment/local.py run python -m returnops_api.demo serve --auth-file "$PWD\tmp\demo-shop\auth.json" --port 8000 --fixed-proposal --founder-decisions --accounts
```

```bash
mkdir -p tmp
.venv/bin/python -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir "$PWD/tmp/demo-shop" --store synthetic_au_store --customer-one synthetic_customer_a --customer-two synthetic_customer_b --founder founder --order-investigation --fixed-proposal --founder-manual
.venv/bin/python -B tools/environment/local.py run python -m returnops_api.demo serve --auth-file "$PWD/tmp/demo-shop/auth.json" --port 8000 --fixed-proposal --founder-decisions --accounts
```

Expected provision output: `Private synthetic demo registration completed. Credentials are in the explicit private directory; do not share them.`
`serve` listens only on `127.0.0.1:8000` with the intake, investigation and
fixed-proposal workers and the Founder decision POST; check
`http://127.0.0.1:8000/health/ready`. Ctrl+C stops it.

### 4. Frontend (`apps/web/README.md`, `vite.config.ts`, `src/api/client.ts`, `src/components/SignInPage.tsx`)

```text
cd apps/web
npm ci --no-audit --no-fund
npm run dev
```

`--no-audit --no-fund` only shortens the install output. On 24 October 2026 `npm audit` reported no advisory in the frontend's production dependencies and 10 in development tools (test runner, dev server and CSS toolchain); see [docs/47](docs/47-stage2-submission-runbook.md), known gap 17. The dev server listens on localhost only.

Open `http://localhost:5173`. The dev server proxies `/v1` and `/health` to
`http://127.0.0.1:8000`. Leave `VITE_API_BASE_URL` unset: the client would use
it as a direct cross-origin base URL, and the API registers no CORS middleware
**(not verified in a browser)**. To sign in: the page opens on **Sign in**;
enter the principal ID as **Username** and its password from `passwords.json`
-> **Sign in**. A new customer can use **Create an account** instead (customers
only). The new session is checked with `GET /v1/session` before it is saved,
and the role the server reports opens the page: a customer the Customer Portal,
the Founder the Founder Console. Since 31 October 2026 there is no page switch
while signed in; the header shows the signed-in account. **Use an access key
instead** keeps the earlier route: paste a token from `sessions.json` (`tokens`
-> principal ID), for example for the step 5 driver's API, which has no
password sign-in. The client keeps the session in the browser's
`localStorage`; use **Sign out** afterwards. **Explore with sample data** opens
the built-in sample data (Mock Mode) with no server. Copy a password (or a
token) without showing it:

```powershell
(Get-Content -Raw tmp\demo-shop\passwords.json | ConvertFrom-Json).founder | Set-Clipboard
(Get-Content -Raw tmp\demo-shop\sessions.json | ConvertFrom-Json).tokens.synthetic_founder | Set-Clipboard
```

```bash
.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]], end="")' tmp/demo-shop/passwords.json founder | pbcopy   # Linux: xclip -selection clipboard
```

Since 23 October 2026 (B's #102) the client sends Founder decisions to
`POST /v1/founder/cases/{case_id}/decisions` and reads `GET /v1/founder/analytics`
live; the decision route is served only when the API runs with `--founder-decisions`
(docs/40), and the console shows the approval scope before a decision is recorded.
Mock Mode remains available for a database-free walkthrough.

### 5. The R.02 driver's case in the frontend (`tools/r02`, demo mode)

The driver approves and executes one synthetic cups case end to end and, in
demo mode, keeps its API on port 8000 for the frontend. First stop the step 3
API with Ctrl+C: its workers must not run while the driver runs, and port 8000
must be free. Provision a dedicated store without `--order-investigation`,
`--fixed-proposal` and `--founder-manual`, then start the driver within about 8
minutes. Set
`DATABASE_URL` directly in the shell for the driver: started through
`local.py run`, a Ctrl+C would kill the driver before it stops its API child.
The URL below is assembled from `.env` without being printed **(not verified)**.

```powershell
.\.venv\Scripts\python.exe -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir "$PWD\tmp\demo-cups" --store demo_cups_store --customer-one demo_cups_customer_one --customer-two demo_cups_customer_two --founder demo_cups_founder
$v = @{}; Get-Content .env | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object { $k, $x = $_ -split '=', 2; $v[$k] = $x }
$env:DATABASE_URL = "postgresql+psycopg://$($v.POSTGRES_USER):$($v.POSTGRES_PASSWORD)@127.0.0.1:$($v.DB_PORT)/$($v.POSTGRES_DB)"
.\.venv\Scripts\python.exe -B tools/r02/driver.py --output "$PWD\tmp\r02-demo-run" --identities "$PWD\tmp\demo-cups" --api-port 8000 --keep-api --allow-existing-data
```

```bash
.venv/bin/python -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir "$PWD/tmp/demo-cups" --store demo_cups_store --customer-one demo_cups_customer_one --customer-two demo_cups_customer_two --founder demo_cups_founder
set -a; . ./.env; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${DB_PORT}/${POSTGRES_DB}"
.venv/bin/python -B tools/r02/driver.py --output "$PWD/tmp/r02-demo-run" --identities "$PWD/tmp/demo-cups" --api-port 8000 --keep-api --allow-existing-data
```

`--allow-existing-data` is needed only if step 3 created cases. The driver
prints `R.02 demo mode: driver result PASSED (see run-receipt.json).`, the case
ID and `http://127.0.0.1:8000`, then waits. In the frontend sign in as
**Founder (Merchant)** with the `demo_cups_founder` token, open **Founder
Console** -> **Case Queue & Review** and **Inspect** the case (expected status
`COMPLETED`). Ctrl+C in the driver's terminal stops the API. Delete
`tmp/demo-shop` and `tmp/demo-cups` after the demo: they hold signing keys and
tokens. Refusal codes, the store rules and the limitations are in
[tools/r02/README.md](tools/r02/README.md#demo-mode-live-demo-only) and
[docs/41](docs/41-r02-end-to-end-evidence.md). A demo-mode receipt is not CI
evidence; an evidence run needs a fresh database (docs/41, "Re-running").

### Demo machine script (Windows)

Added 27 October 2026. [`tools/demo/demo.ps1`](tools/demo/demo.ps1) runs the
commands of steps 1 to 5 above in order on the Windows demo machine, checks
each result and stops at the first failure with its reason. The manual steps
above stay the fallback. Run it from the package root;
`-ExecutionPolicy Bypass` applies to this one process only and is needed
because Windows blocks unsigned scripts from a downloaded zip:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\demo\demo.ps1 check
```

Since 29 October 2026 a double-click is enough: `tools\demo\start-demo.cmd`
runs `fresh` (Docker Desktop, then `stop -RemoveData`, `prepare` and `start`)
and `tools\demo\stop-demo.cmd` runs `stop -RemoveData` after a key press. Both
windows stay open to show the result; a desktop shortcut to either file works
the same way.

| Action | When ([docs/45](docs/45-stage2-demo-script.md)) | What it does |
|---|---|---|
| `check` | Any time | Reports Python (3.12.4 or a later 3.12), Docker and Compose, Node and npm, the four ports (including ports that Windows has reserved) and leftover data. Changes nothing. |
| `prepare` | T-40 minutes | Step 1 (`.venv`, locked install, `pip check`, `local.py init`, `API_PORT=8001`), step 2 (Compose up with `--wait`, then `/health/live` and `/health/ready` on `API_PORT`) and `npm ci`. Safe to run again: finished installs are skipped. |
| `start` | T-5 minutes | Step 3: provisions `tmp\demo-shop` once and opens the demo API in its own window on 8000. Step 4: opens the web frontend in its own window on 5173, or on the first usable port up to 5399 when 5173 cannot be opened (Windows can reserve port ranges after Docker or WSL starts), and checks that its proxy reaches the API. Prints the address and when the 899 s sessions expire. `-ModelShowcase` adds `--model-showcase`. |
| `fresh` | T-5 minutes, instead of `prepare` and `start` | Opens Docker Desktop when Docker does not answer and waits up to 3 minutes for it, then runs `stop -RemoveData`, `prepare` and `start`, stopping at the first failure. The data of an earlier run is deleted. `start-demo.cmd` runs it on a double-click. |
| `s5` | S5 | Step 5: sends Ctrl+C to the demo API window, provisions `tmp\demo-cups` once, starts the R.02 driver in its own window and reports the receipt's result and case ID. |
| `stop` | After S5, or between rehearsals | Sends Ctrl+C to the driver and demo API windows, closes the three windows and runs `docker compose stop` (the data is kept). `stop -RemoveData` runs `docker compose down -v` instead and deletes `tmp\demo-shop` and `tmp\demo-cups`; `stop-demo.cmd` runs it on a double-click. |

- **Secrets.** The script never reads, prints or stores a model API key or a
  session token, and prints no `.env` value except the two ports. For the
  driver it sets `DATABASE_URL` from `.env` as step 5 does, only in its own
  process and the driver window. Signing in stays manual (step 4); `start` and
  `s5` print the clipboard commands of step 4. For the model showcase, set the
  `RETURNOPS_MODEL_*` variables in the same PowerShell window before
  `start -ModelShowcase` (docs/45, section 2.3, item 2); they pass to the demo
  API window unread.
- **Compose project.** Each package folder gets its own project name,
  `returnops-demo-` and 8 hex characters of the SHA-256 of the folder path, so
  its database volume is never shared with another checkout (the step 2
  pitfall). `check` refuses a leftover volume of the same folder without its
  `.env`.
- **Stopping.** The three windows are PowerShell consoles that the script
  opened. To stop the demo API or the driver, the script sends Ctrl+C to that
  console, the same as typing it there, so both shut down as in steps 3 and 5
  (the driver stops its API child and removes its private directory). Only
  then is the window closed. Since 29 October the script then checks that the
  window and every process under it have ended; if one is still running, it
  keeps the window's record, stops with an error and deletes nothing, so
  `stop -RemoveData` and `fresh` go no further and a later `stop` can try
  again.
- **Identities.** The database refuses to register a principal twice, so
  `start` and `s5` reuse `tmp\demo-shop` and `tmp\demo-cups` once they exist.
  Fresh 899 s sessions need a fresh database: `stop -RemoveData`, `prepare`,
  `start`, or `fresh` for all three.
- **Tested** on 27 October 2026 on the demonstration machine (Windows 11,
  Windows PowerShell 5.1, Python 3.12.9 through the py launcher, Docker 29.6.2
  with Compose 5.3.1, Node 24.14.0, npm 11.9.0). The package was a zip of
  `main` `5d67231c` plus this script, unpacked to a path with non-ASCII
  characters, with the script marked as downloaded. These ran:
  - `check`, `prepare` (38 s the first time with warm pip and Docker caches,
    17 s again) and `start` (5 s);
  - a customer case lodged through the Vite proxy;
  - `s5` (driver `PASSED`, about 100 s; the Founder read the case as
    `COMPLETED` through the proxy);
  - `stop` (the driver removed its private directory after Ctrl+C) and
    `stop -RemoveData`.

  The refusals were also checked: Compose stopped, a foreign program on port
  8000, `start` or `s5` while the driver runs, and a demo API that exits at
  once (`-ModelShowcase` without the variables). Not tested:
  - a first run without pip, npm and Docker caches;
  - another Windows machine, PowerShell 7, or a machine without the py
    launcher;
  - `-ModelShowcase` with a key.
- **Double-click and port fallback, tested** on 29 October 2026 on the same
  machine (`main` `b5bcfa95` plus this change). There Windows had reserved
  ports 5163 to 5262 after Docker started, so Vite stopped on 5173 with
  `listen EACCES`. These ran:
  - `start-demo.cmd` with Docker Desktop closed: stop, prepare and start
    finished 34 s after the start, with the web frontend on 5263 and its proxy
    reaching the demo API;
  - a desktop shortcut to `start-demo.cmd`, double-clicked: ready in 25 s;
  - `stop-demo.cmd`: containers, volume and identities removed;
  - `check` while the services ran, and the port choice for a reserved, a free
    and a used first port;
  - closing the windows: a graceful stop after Ctrl+C, a window already closed
    from outside (reported, then skipped), and a copy of the script whose
    taskkill did nothing, so the demo API window stayed open: `fresh` stopped
    with exit code 1 and kept the records, containers and identities, and the
    next `stop-demo.cmd` closed both windows and removed them.

  A first attempt hung in `docker version` while Docker Desktop was failing to
  start (a stale `engine.sock` under `%LOCALAPPDATA%\docker-secrets-engine` on
  this machine); the engine check now gives up after 15 s, and `fresh` stops
  after 3 minutes. In Docker's error window choose Quit, never Reset to factory
  defaults. Not tested: a machine where 5173 is free, and the Canvas zip.

### Railway deployment (since 30 October 2026)

The lead chose [Railway](https://railway.com) for the Week 13 demonstration, and
the local deployment above stays the fallback ([docs/46](docs/46-gate2-roadmap.md)
section 9; deployment model PD-03 in [docs/15](docs/15-package-deployment-models.md)
section 4.1).

One Railway service is built from `tools/railway/Dockerfile`. The service
variable `RAILWAY_DOCKERFILE_PATH` selects that file: on 30 October 2026 a
`railway up` built the root `Dockerfile` although `railway.json` named the other
one. `railway.json` keeps the health check and the restart policy; Railway warns
that this file format works until 1 December 2026. The service holds:
- the web build;
- the demo API on `127.0.0.1:8000` inside the container;
- Caddy on Railway's `PORT`, which serves the web build and proxies `/v1` and
  `/health`, so the browser stays on one origin.

A second service runs PostgreSQL 17 (the image of `compose.yaml`). Every start of the demo service is a fresh
demonstration, done by `tools/railway/start.py`:
1. it drops and creates `returnops_f02`;
2. it runs `alembic upgrade head`;
3. it runs step 3's `demo.py provision` into a private folder in the container;
4. it starts the demo API and Caddy.

Nothing it prints contains a credential.

Setup, once per Railway account:

1. Sign in on railway.com and create a project. Add PostgreSQL **17** as an
   image service, the same image as `compose.yaml`. Railway's own database
   template was PostgreSQL 18 on 30 October 2026, and there migration 0010
   stopped with "Preparation upgrade requires exact 0009 approval schema".
   - The service, named `Postgres17`:
     `railway add --service Postgres17 --image postgres:17-bookworm@sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0 --variables "POSTGRES_USER=postgres" --variables "POSTGRES_DB=railway" --variables "PGDATA=/var/lib/postgresql/data/pgdata"`.
   - A volume mounted at `/var/lib/postgresql/data`:
     `railway volume --service <its service ID> add --mount-path /var/lib/postgresql/data`.
   - A random `POSTGRES_PASSWORD` of letters and digits, set with
     `railway variable set POSTGRES_PASSWORD --stdin --service Postgres17`.
     The value must have no trailing newline, space or byte-order mark.
2. Add an empty service for the app and give it three variables:
   `DATABASE_URL = postgresql://${{Postgres17.POSTGRES_USER}}:${{Postgres17.POSTGRES_PASSWORD}}@${{Postgres17.RAILWAY_PRIVATE_DOMAIN}}:5432/${{Postgres17.POSTGRES_DB}}`,
   `PORT = 8080` and
   `RAILWAY_DOCKERFILE_PATH = tools/railway/Dockerfile`. In Settings, Networking,
   generate a public domain on port 8080. With the CLI:
   `railway add --service returnops-demo-app --variables "PORT=8080" --variables "RAILWAY_DOCKERFILE_PATH=tools/railway/Dockerfile"`.
   Add `DATABASE_URL` as above with `railway variable set`, then run
   `railway domain --service returnops-demo-app --port 8080`.
3. On the demo machine: `npm install -g @railway/cli`, `railway login`. Then, in
   the package folder, run `railway link` and choose the project and the app
   service. `demo.ps1` names the app service in every Railway command
   (`-Service`, default `returnops-demo-app`), because `railway add` can leave
   the folder linked to the database service.
4. Register the demo machine's SSH key once, for `railway ssh`:
   - `ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519"` with an empty
     passphrase;
   - `railway ssh keys add --key "$env:USERPROFILE\.ssh\id_ed25519.pub" --name <a name>`;
   - `railway ssh keys list` shows it.

At the demonstration, in the package folder downloaded from Canvas (after
`railway link`):

| Action | When | What it does |
|---|---|---|
| `demo.ps1 cloud` or a double-click on `tools\demo\cloud-demo.cmd` | T-10 minutes | `railway up --ci` builds and deploys this folder. It then waits for the new deployment's sessions and copies them through `railway ssh` to `tmp\railway-shop`, never showing them. It prints when they expire and the clipboard commands of step 4 for that folder. |
| `demo.ps1 cloud-fresh` | Sessions expired | `railway redeploy`: a fresh database and new sessions, copied the same way. |
| `demo.ps1 cloud-tokens` | Any time | Copies the current sessions again, with a warning if they have expired. |

After copying, all three read the service's public address from `railway status`
(or take `-Url https://<the domain>`; a domain without `https://` is accepted), check
that it answers ready, and then try the copied customer session there until it is
accepted: until Railway switches traffic to the new deployment, the old one answers
401 and signing in would fail (added 30 October 2026, after a review).
`.railwayignore` keeps `.env`, `.venv`, `tmp` (demo identities and copied sessions)
and `node_modules` out of the `railway up` upload, because the folder unpacked
from the Canvas zip has no `.git` for `.gitignore` to apply to.

- **Model showcase on Railway (31 October 2026, docs/44):** the course proxy is on a private VPN address, so the service uses Alibaba Cloud Bailian instead. Service variables: `RETURNOPS_MODEL_SHOWCASE=1`, `RETURNOPS_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`, `RETURNOPS_MODEL_ID=qwen3.5-122b-a10b`, `RETURNOPS_MODEL_PROVIDER_ID=aliyun_bailian`, `RETURNOPS_MODEL_DEADLINE_SECONDS=50`, `RETURNOPS_MODEL_MAX_CALLS=50`, and `RETURNOPS_MODEL_API_KEY`, which only the lead sets. Sign-in: the Founder is `founder`, the customers `synthetic_customer_a` and `synthetic_customer_b`; `RETURNOPS_DEMO_PASSWORD` (set only by the lead, 8 to 128 characters) is then the password of all three, otherwise each gets a generated one in `passwords.json`. Without a complete configuration the service starts without the showcase and its log names the missing variable. With the showcase and password sign-in on, the Founder also gets the AI assistant (a reply draft, a queue triage and a weekly summary, each on request; docs/44), whose calls count towards the same `RETURNOPS_MODEL_MAX_CALLS`.
- **Not on Railway:**
  - the course proxy route of S4 (private VPN address): the local fallback.
  - S5's driver: it runs on the local deployment.
- **After the demonstration:**
  - remove the app service's deployment on railway.com;
  - run `demo.ps1 stop -RemoveData`, which also deletes `tmp\railway-shop`;
  - use Sign out in both browser profiles.
- **Tested on 30 October 2026** with Docker on the demonstration machine
  standing in for Railway: a PostgreSQL 17 container, plus this image with
  `DATABASE_URL` and `PORT=8080`.
  - The service was ready in about 6 s.
  - The page, deep links, `/health/ready` and an unauthenticated `/v1/session`
    (401) worked.
  - A customer case was lodged and clarified with `SYN-1001` (RISK_REVIEW). The
    Founder queue, detail and audit read it through the same address.
  - A restart gave a new database and new sessions.
  - A stop request exited 0.
  - The logs held no token, signing key or database URL.
  - `cloud`, `cloud-fresh` and `cloud-tokens` ran against a stand-in for the
    Railway CLI that used `docker exec`.

- **On Railway, 30 October 2026** (project `returnops-demo`, deployed with
  `railway up` from a folder equal to `main` plus this change):
  - The first deployment built the root `Dockerfile` and crashed. The service
    variable `RAILWAY_DOCKERFILE_PATH` fixed the build.
  - The second deployment met PostgreSQL 18 and stopped in migration 0010.
    PostgreSQL 17.11 as an image service fixed it.
  - Then the service was ready 39 s after a redeploy. Through
    `https://returnops-demo-app-production.up.railway.app`:
    - `/health/ready` gave 200, the page and a deep link loaded, and
      `/v1/session` without a token gave 401;
    - `X-Frame-Options` and `Referrer-Policy` were set, and the browser showed
      no console error;
    - the deployment logs held no token, key or database URL.

  - In the evening, after the account's first SSH key was registered from this
    machine:
    - `cloud-tokens` first reached the database container. The folder was linked
      to `Postgres17`, the service `railway add` had last created. A
      `railway up` there would have replaced the database, so `demo.ps1` now
      names the app service.
    - With the app service, `cloud-tokens` copied sessions that had expired at
      13:16; it now says so.
    - `cloud-fresh` redeployed and copied new sessions in 29 s.
    - With those sessions, S2 and S3 ran through the public address by HTTP
      calls from this machine. No token was shown.
      - Without a token the Founder queue gave 401; with the customer's token
        it gave 403.
      - A case without an order reference got two questions; the answer
        `SYN-1001` took it to RISK_REVIEW.
      - A `SYN-CONFLICT` case was ESCALATED with the order-lookup block "The
        authorized order reference is ambiguous."
      - The Founder queue, detail, audit and analytics answered 200.
      - MANUAL_HANDLING on the block was accepted (202): NOTIFICATION_PENDING
        for the Founder and the customer, and `FOUNDER_DECISION_ACCEPTED` in
        the audit chain.

  Not yet tested: pasting a token in the web page on Railway, because the test
  browser could not paste from the clipboard. Also not yet tested: a deployment
  from the Canvas zip.
- 31 October 2026, `demo.ps1 cloud` from the run folder at `main` `5be358ee`:
  - the upload snapshot was 15 MB: `.railwayignore` kept the local `.venv`
    (124 MB), `node_modules` (159 MB) and `tmp` out;
  - build, deployment and the session copy took 243 s; the script read the
    address from `railway status` and reported that it answers ready and
    accepts the copied sessions;
  - over the public address: the page `no-cache`, the bundle files
    `immutable`; a zero-width statement and a blank or invisible order
    reference 422; S2 and S3 as on 30 October, MANUAL_HANDLING 202 and
    NOTIFICATION_PENDING;
  - a missing bundle file came back 404 with the year-long cache header, which
    a browser may keep; corrected the same day so that only existing files get
    it.

### Troubleshooting

- **`Run tools/environment/local.py init first`** from Compose: `.env` or its
  `POSTGRES_PASSWORD` is missing (`compose.yaml`).
- **Port in use:** change `DB_PORT` or `API_PORT` in `.env` (docs/10: adjust
  your own `.env`, do not stop other services). The frontend proxy target
  `127.0.0.1:8000` is fixed in `vite.config.ts`, so the demo API (step 3 or
  step 5) needs 8000; the driver reports `API_PORT_UNAVAILABLE` when it is
  taken. A frontend error `HTTP 500: Backend server unavailable at
  http://127.0.0.1:8000` means nothing answers there.
- **`listen EACCES: permission denied ::1:5173`** from Vite: Windows has
  reserved a port range that includes 5173 (`netsh interface ipv4 show
  excludedportrange protocol=tcp`), although nothing listens there. The demo
  machine script moves to the next usable port; by hand, run
  `npm run dev -- --port <port> --strictPort` with a port outside those
  ranges, or restart Windows.
- **Windows Python older than 3.12.4:** `demo.py provision` prints only
  `Demo setup or startup failed; no credentials are printed. ...`, and the
  driver stops with `PRIVATE_RUNTIME_REQUIRES_PYTHON_3_12_4`. Python 3.13 is
  outside `requires-python`.
- **Database name:** `DATABASE_URL` must be `postgresql+psycopg://` with a host
  and user, and its database must be `returnops_f02` or `returnops_f02_`
  followed by lowercase letters, digits or underscores (at most 63
  characters), with no `?` or `#` (`settings.require_environment_database`).
  Otherwise Alembic, `demo.py` and the driver refuse (`DATABASE_URL_REJECTED`).
- **Statement timeout:** the API engine sets `statement_timeout=10000` (10 s,
  `database.py`, since 23 October 2026; it was 2 s, shorter than the 5 s fence
  `lock_timeout` it has to outlast), the same as the driver's engine and the
  test engines. A slow machine can still turn an HTTP step into 503
  `INTERNAL_ERROR` (retryable, keep the key); see "If a step fails" in
  `tools/r02/README.md`.
- **401 in the frontend after about 15 minutes:** the page shows a red
  "Your session has ended" banner, or the sign-in page says so: the 899 s
  sessions have expired. Provision new principal IDs (the registry refuses existing IDs);
  the same `--store` keeps the store's cases readable for a new Founder.
- **Customer or Founder routes return 503 on the Compose API:** expected; it
  has no authentication file. Use `demo.py serve` or the driver's kept API.
- **Wrong Docker context on Windows:** add `--context desktop-linux` to the
  docker command (docs/10).
- **Driver refusals in demo mode** (`STORE_HAS_CASES`,
  `STORE_INVESTIGATION_CONFIGURED`, `FOREIGN_PENDING_WORK`, `IDENTITIES_*`,
  `IDENTITY_SESSION_WINDOW_TOO_SHORT`): see the driver README. For
  `FOREIGN_PENDING_WORK` after stopping `demo.py serve` mid-work: start
  `demo.py serve` again for about ten seconds so its workers finish or reclaim
  the `PENDING` / `RUNNING` rows, stop it, then rerun the driver with a new
  `--output`.
- **`demo.py` prints "Demo setup or startup failed: ..."**: the sentence after
  the colon is the safe reason (for example a reused `--private-dir`, duplicate
  principal IDs, a missing authentication file or a missing `RETURNOPS_MODEL_*`
  variable); it never contains a key, a database URL or a path.

AI-assisted implementation and metadata preparation; author shuxiachai.

## R.02 no-LLM end-to-end evidence - 22 October 2026 (Sydney)

Owner A (`shuxiachai`, Jingbo Chai); designated human reviewer C (Yuwei Tao).
This notice covers work package R.02 only; the dated notices below keep their
own scope.

- [PR #89](https://github.com/shuxiachai/returnops-au/pull/89) adds the private
  driver [`tools/r02`](tools/r02/README.md) and a separate CI job,
  `end-to-end-no-llm`. The driver starts the real API itself (route C: an API
  child composed with `create_app(...)`) and drives one synthetic cups case:
  customer HTTP case creation, fixed proposal, controlled PASS receiver + risk
  stub, Founder HTTP approval after negative tests, the private mock
  return/label/PDF chain and a CORE_MOCK notification, then Founder read-back of
  history and audit. `main.py`, `demo.py` and the installed packages are
  unchanged.
- First actual result: [run 39634415393](https://github.com/shuxiachai/returnops-au/actions/runs/39634415393)
  on PR head `510e1acd`, job `end-to-end-no-llm` success, receipt `PASSED` with
  32 of 32 checks true and no recovery path used; all 12 jobs of that run
  succeeded. Timings, the receipt format and each check are recorded in
  [docs/41](docs/41-r02-end-to-end-evidence.md).
- PR #78 (A2.07) was squash-merged into main on 22 October 2026 as
  `0758696681cc706fda14ba378b7baa8e8c6580b3`. The lead assigned the driver and
  its CI trace to A2.07's "complete fixed-proposal execution trace" item; R.02's
  formal evidence is the CI output of `end-to-end-no-llm`.

**Limitations:** the API is composed by the driver, not started by
`demo.py serve`, and the image default CMD is not exercised; intake,
investigation and the fixed proposal run in the driver process; Docker evidence
is still only the image build and import probe, not a deployment proof; the
controlled PASS receiver + risk stub is Gate 1's fixed risk result, not an
independent risk assessment; fault injection of UNKNOWN/REPLAYED paths and
Windows permissions are not covered.

**Exception:** on 22 October 2026 the lead recorded a one-time exception: R.02
implementation started before A2.07's designated human review by C, because of
the Stage 2 source deadline (1 November 2026, 23:59) and because no production
code was changed. E.10 remains a finish dependency of R.02; its static
[coverage map](docs/42-e10-coverage-map.md) is prepared for C and is not an
acceptance. The frozen work packages in docs/08 are unchanged.

**Pending:** C's designated human review of A2.06, A2.07 and R.02 remains the
acceptance prerequisite and has not taken place. A `PASSED` receipt, a green CI
job or a merge is not acceptance, and no Jira status is changed.

AI-assisted implementation and metadata preparation; author shuxiachai.

## F.06 Founder analytics read API - 22 October 2026 (Sydney)

Owner A (`shuxiachai`, Jingbo Chai); reviewer C under docs/08. This notice
covers work package F.06 only.

- `GET /v1/founder/analytics` (`getFounderAnalytics`) is now registered by
  default next to the four Founder reads: FOUNDER only, the Founder's own
  store, read-only, one SELECT per response, strict `created_from` /
  `created_before` / `status` validation and enforced count invariants. See
  [docs/43](docs/43-f06-analytics.md) for the counting basis and the changes
  B's frontend needs.
- Proposal latency is Tier 0 (no samples, no percentiles): trusted start and
  ready events remain the open E.01/E.09 item for C. Known proposal-step
  failures (PROPOSAL_FAILED for the current input) count as failed; every
  other case is unmeasured. docs/43 records a Tier 1 candidate for C's
  review. The only proposer is the fixed synthetic one.
- First CI result: PR #90, head 1de70e3d, CI run 39701255799: all 12 jobs
  successful, including the PostgreSQL foundation group that runs tests/founder
  (the 4 analytics PostgreSQL nodes and the TCP call). Squash-merged into main on
  2026-10-22. Contracts, docs/08/09, migrations and `apps/web` are unchanged; no
  acceptance by C or any member is implied.

AI-assisted implementation and metadata preparation; author shuxiachai.

## A1.06 Coordinator showcase (advisory, default off) - 22 October 2026 (Sydney)

Owner A (`shuxiachai`, Jingbo Chai); reviewer C under docs/08. This notice
covers the extraction half of work package A1.06 only.

- With `RETURNOPS_MODEL_SHOWCASE=1` (default `0`; `demo.py serve
  --model-showcase`), a background worker sends redacted, allow-listed
  statement text to a chat-completions endpoint configured only through
  `RETURNOPS_MODEL_*` environment variables, accepts the reply only as a
  contract `ExtractedFacts` with no order lines, an `UNDETERMINED` basis and no
  `SUPPORTED` status, and shows it to the Founder as `CaseView.facts` while the
  same statements are still current. See
  [docs/44](docs/44-coordinator-showcase.md).
- Advisory only: no state, question, proposal, review, approval, operation or
  database write. Results live in memory and are lost on restart. The planned
  MODEL-actor audit event is withheld because the label-artifact claim compares
  the case head and audit rows across transactions (docs/44).
- Built before R.02 and Gate 1 acceptance under the lead's dated decision
  recorded in docs/44; this is not Gate 1, Gate 2 or A1.06 acceptance.
  Contracts, docs/08, migrations, `apps/web` and the R.02 driver are unchanged.
  First live result and first CI result: pending.

AI-assisted implementation and metadata preparation; author shuxiachai.

## R.05 demo script, Gate 2 roadmap and submission runbook - 22 October 2026 (Sydney)

Owner A (`shuxiachai`, Jingbo Chai); reviewer C under docs/08. Documents only.
- [docs/45](docs/45-stage2-demo-script.md): Week 13 live demo script (within 12 minutes, speakers A/B/C, fallbacks).
- [docs/46](docs/46-gate2-roadmap.md): what Gate 1 delivered, Gate 2 preconditions, A3 and C3 status, 22 October deferrals.
- [docs/47](docs/47-stage2-submission-runbook.md): R.05.a/R.05.b packaging, Canvas check, rehearsal and contribution draft.
- No rehearsal, live model call, tag or Canvas upload has happened yet; no acceptance is implied.

AI-assisted implementation and metadata preparation; author shuxiachai.

## Delivery log

Every dated record of this repository, kept verbatim in its original order (newest notices first, then older receipts). These records keep their original scope and wording; the status at the top of this file is current.

> **Current technical checkpoint - 13 October 2026:** [PR #65](https://github.com/shuxiachai/returnops-au/pull/65) is merged at main `7fc30856`. Its [new-main CI](https://github.com/shuxiachai/returnops-au/actions/runs/38331528059) passed 2262 core regressions on PG17.11/head0009. The four private Founder decision components are technically adopted; original personal, predecessor and joint acceptance remain separate.

> **A2.02 first candidate / KAN-15 / Issue #71:** see [private retained-source approval admission](docs/37-a202-approval-admission.md). This read-only slice checks a future CREATE_RETURN against full persisted current approval proof; saved execution work remains unclaimed. Its own exact-source PR/CI records establish publication and validation. Older dated notices below retain their historical scope.

> **A1.03 investigation increment / Issue #27 / recorded KAN-14:** [persisted order investigation and clarification](docs/23-order-investigation.md) now connects the adopted customer flow and synthetic provider through explicit database permissions, durable work, five outcome paths and atomic lifecycle/audit/retention guards. The implementation starts from merged PR26/main4673; use its exact-source PR/CI records for publication and adoption status. No Founder packet, Risk/approval, LLM or real provider is implemented, and no whole-package or teammate/joint acceptance is implied. Earlier component/customer-candidate notices below retain their historical scope.

> **A1.04 / recorded KAN-29:** see the [independent synthetic order provider](docs/22-a104-synthetic-order-provider.md) for its internal port, immutable fixture provenance and installation checks. Customer-worker/Domain acceptance wiring belongs to later A1.05 work.

> **Customer backend candidate (26 September 2026, Issue #23 / recorded KAN-14 mapping):** the isolated implementation now provides the seven frozen customer operations, PostgreSQL admission/receipts/history, current F.03 authorization, bounded attachments and separate durable deterministic intake processing. See [customer flow and private demo](docs/21-customer-flow.md). This remains a scoped implementation candidate; use its actual pull request and exact-source CI records for publication/review/merge status. It does not claim teammate or joint acceptance, verified purchase facts, AI processing, or a Founder/provider workflow. Earlier health-only/component-only notes below describe their historical baselines.

## C review publication follow-up — 23 October 2026 evening (Sydney)

Primary delivery: [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41).
This dated C notice supersedes the current-state wording in earlier C receipts,
without deleting their source-specific findings or test results.

- Following [A's request](https://github.com/shuxiachai/returnops-au/pull/61#issuecomment-6359315897),
  this six-file C review/handoff branch is submitted for A's exact-head review
  and lead-written squash via its PR against main. PR #17 and #61 are already merged;
  this separate review packet is not yet adopted merely because it is published.
- The branch ordinary-merges main `2a4d3ae258734ab91c90d9e27e3da14eccbde0c6`
  (#112), preserving all main README lines and A/B runtime files. #112 widens
  the bounded transient retry classification; the earlier `c4d0879` failure is
  historical evidence, not a check result for this newer source.
- C independently checked [PR #114](https://github.com/shuxiachai/returnops-au/pull/114)
  at `590b4229ca20cd6e6ad34f026fd32d6ae93e421b`: **105 offline tests passed**.
  The original narrow interruption/cleanup/log observations improved. However,
  a new synthetic failure probe shows that an unwritable final receipt can
  still leave the command claiming `PASSED` with exit 0. This is **R02-C-03**,
  sent for A's disposition; no actual filesystem failure or secret leak is claimed.
  #114 is a separately reviewed candidate, not code merged into this C branch.
- The [C review record](docs/reviews/member-c-r02-review-20261022.md#8-pr114-bounded-review-and-receipt-publication-finding--23-october-2026)
  distinguishes exact sources, safe reproduction, remaining failure-matrix/PG
  limits and current review findings. Neither offline tests nor green CI alone
  establish Gate 1 or a personal/team sign-off.

Next independent follow-up: review the owner's response and recheck any fix
against its exact source. Still requiring actual people or approved
runtime evidence: C's own S6 explanation and contribution/AI-use confirmation,
team rehearsal, exact-byte corpus admission, real Risk/pilot/Gold/C3 and final
submission-source acceptance. A's scheduling deferral is not a tutor waiver.
AI-assisted C preparation; no A/B implementation edits, main merge by C,
live model call, invented timing, contribution agreement or Done transition.

## C adoption and review update — 23 October 2026 (Sydney)

Tracking: [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) /
[KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41).
This dated notice supersedes the pending/failed statuses in the older C
snapshots below; their original evidence is retained.

- **PR #61 is merged**, not waiting for adoption: A approved exact source
  `be21f39bc502100ddd96c129bc9116b6fdcfceba` in
  [review 5622537263](https://github.com/shuxiachai/returnops-au/pull/61#pullrequestreview-5622537263).
  A's [attempt 2 of run 39770369525](https://github.com/shuxiachai/returnops-au/actions/runs/39770369525/attempts/2)
  passed all 13 effective jobs without changing that source. A adopted it
  at 01:04:56 UTC as `29fd233a520bd37ee1c9aa2c61302b0417a25853`.
  Attempt 1's lock-timeout failure remains historical evidence; rerun success
  does not prove its cause was fixed.
- This C review branch now integrates main
  `c4d08799adf555604a235e61ca325f50a2218618` by ordinary merge, retaining
  the complete main README and the earlier C receipts. A/B runtime files,
  frozen ownership/dependencies and corpus-admission pins match that main.
  B's stacked #101/#102 changes reached main through #107; #108 subsequently
  added bounded R04 attempt records and the R.02 interruption correction.
- **Latest main is not fully green:** [run 39900838149](https://github.com/shuxiachai/returnops-au/actions/runs/39900838149)
  on that exact `c4d0879` failed the same-key R04 assertion again
  (351 passed / 1 failed; PG lock timeout), followed by the dependent final
  gate. This is a new main failure, not a reversal of PR #61's merge.
  A's existing [Issue #103](https://github.com/shuxiachai/returnops-au/issues/103)
  / KAN-43 remains the concurrency follow-up.
- C independently verified **R02-C-01's terminal FAILED/INTERRUPTED receipt
  in bounded in-memory probes**. **R02-C-02 remains open**: an earlier cleanup
  failure can prevent later private cleanup/receipt publication; raw API logs
  can still target the public output directory before screening. No actual
  secret leak was observed. See the [updated review and evidence limits](docs/reviews/member-c-r02-review-20261022.md#7-adoption-and-owner-fix-follow-up--23-october-2026).
- Local checks: 137 focused tests / 136 subtests; the complete six-step offline
  check passed (371 contract tests, 6 static groups, 12 model-checker tests,
  32 runner tests, 14 Mermaid parses and 64 synthetic-provider tests).
  These overlapping checks are not Gold, a live Risk run, a personal rehearsal
  or acceptance of the whole application.
  The additional PG17 test container did not start (Created/Pid 0), including
  a no-bind control attempt: **no new local PG pass or failure is claimed**.
  Only this task's temporary test containers/data were removed.

Still needed: A's remaining cleanup/log disposition; approved real-corpus
admission and runtime C2 wiring; separately authorised real Risk/C3 evaluation;
blind Gold and actual participant timing; C's own S6 explanation and team
rehearsal/acceptance. Merge is not Done. AI-assisted C verification; no main
merge by C, live model call or teammate signature.

## C local proof follow-up — 22 October 2026, 12:54 UTC

Tracking: [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) /
[KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41).
This dated C-only notice supersedes the older C status snapshots below;
their source-specific results remain history. **PR #17 is merged. PR #61
remains open at `be21f39bc502100ddd96c129bc9116b6fdcfceba`.** Its
[normal CI run](https://github.com/shuxiachai/returnops-au/actions/runs/39770369525)
has finished with 11 successful jobs, one failed Founder revision job and the
dependent failed final gate. It is not ready to claim green/accepted.

C now has [new local proof and E.10 dispositions](docs/reviews/member-c-r02-review-20261022.md#6-local-proof-follow-up--22-october-2026):
five unchanged R04 same/different-key pairs passed on isolated PG17.11;
two preparation/restart and six installed label-process cases passed. This
does **not** reproduce or fix the cloud lock timeout. The R.02 cancellation
and cleanup defects still reproduce in memory; A's disposition remains needed.

The same clean `be21f39` checkout passed 263 focused C offline tests and generated
the 13-file synthetic evidence bundle. A source archive passed the 116 C1/C2
tests, pilot and example human-time accounting; it correctly refused new
Git-provenance evidence without `.git`. See the [C reproduction boundary](experiments/evaluation_candidate/README.md#clean-checkout-versus-source-archive--22-october-2026).

Only C documentation is updated on this separate review branch; PR #61's head,
A/B implementation, source-admission pins and WBS remain unchanged. No Actions
rerun, live model, Gold, measured human timing, personal sign-off, main merge or
Done transition is claimed. Future integration still needs exact-source review
and required checks; these local results do not replace them.

## C follow-up — 22 October 2026 evening (Sydney)

Tracking: [KAN-41](https://lucastaooo.atlassian.net/browse/KAN-41) and
[Issue #66](https://github.com/shuxiachai/returnops-au/issues/66).
This is a C-only preparation branch, **not current main**. The remote-main
snapshot checked was `51862f4bcc06eebf1c1804647c21d0908960ebc7`; A/B runtime
changes from that snapshot have not been merged into this branch.

- PR #17 head `b6dcc7552c2e52ca4dafd9d4b9400ad860db9365` and PR #61 head
  `7bb1f5ad6e95a13a4aaffbae3056794116fedea7` remain OPEN. Their existing
  [39724718286](https://github.com/shuxiachai/returnops-au/actions/runs/39724718286)
  and [39724719271](https://github.com/shuxiachai/returnops-au/actions/runs/39724719271)
  CI runs have now finished: **13/13 jobs successful each**. Older approvals
  concern older heads; this is not approval or CI for current main. Neither
  pending branch was changed by this follow-up.
- A published the advisory Coordinator (#94), demo/roadmap/runbook (#96),
  Canvas packaging clarification (#97), and explicit private-HTTP opt-in
  (#98). These are not C2 Risk integration or permission for C to read keys,
  enable the transport, send data or call a model. No live-model evidence was
  verified in this follow-up.
- C's [S6 speaking draft and display checklist](experiments/c2_risk_candidate/README.md#s6-demo-preparation--22-october-evening)
  now map to A's two-minute segment. The existing synthetic evidence command
  was actually run locally; it is accounting rehearsal, not a human rehearsal,
  Gold result or model benchmark. Contract tests: **371 passed / 1685 subtests**
  (overlapping existing suites, not additional independent scenarios).
- The [C latency-event disposition](experiments/evaluation_candidate/README.md#22-october-f06-tier-1-technical-disposition)
  explains why Tier 0 should stay until the complete episode boundary is
  established. A's R.02 interruption/cleanup findings also remain unresolved;
  `tools/r02` is unchanged between reviewed `4aec7c0` and checked `51862f4`.
- [A's submission runbook at the checked source](https://github.com/shuxiachai/returnops-au/blob/51862f4bcc06eebf1c1804647c21d0908960ebc7/docs/47-stage2-submission-runbook.md)
  records a ZIP-only group submission, opening 26 October and due 1 November
  23:59 Sydney. Its contribution percentages are **A's proposal, not agreed**.
  The student must confirm their own contribution/AI-use statement and practise
  the segment; team rehearsal and tutor scope disposition remain separate.

AI-assisted C preparation; no main merge, A/B code edit, new CI run, personal
signature, contribution-percentage agreement or Done transition.

## C technical review and handoff — 22 October 2026 (Sydney)

C's [R.02 technical review packet](docs/reviews/member-c-r02-review-20261022.md)
checks main `4aec7c0de6536075f6691567a3f609b8f3093279` without changing A/B
code. Local R.02/C2 checks passed **100 tests and 82 subtests**. The downloaded
R.02 receipt from [run 39724718286](https://github.com/shuxiachai/returnops-au/actions/runs/39724718286/job/119645897403)
has 32/32 checks true; all three code-tree digests match that main. This is
CI-artifact verification, not a new local PostgreSQL run or human acceptance.

Two failure-path findings are sent to A: interruption can publish a nonterminal
`RUNNING` receipt; cleanup/log-screening failures can leave private files and
unscreened output behind. The packet includes an isolated reproduction and
acceptance checklist. No actual credential leak was observed.

The [C2 README handoff](experiments/c2_risk_candidate/README.md#22-october-handoff--near-term-delivery)
now separates the five-outcome contract from runtime routing and lists the
remaining decisions. A's Gate 2 deferral is a team scheduling note, not a tutor
waiver: the real Risk model, admitted corpus, pilot/Gold, C3 and original WBS
conditions remain outstanding unless explicitly resolved. Personal explanation,
review signatures and joint acceptance are not prefilled. This C-only review
branch is not a merge request or a replacement for the pending PR #17/#61
heads; any later integration still needs exact-source review and required CI.

## C source-review after PR #17 adoption — 22 October 2026 evening (Sydney)

[A's follow-up](https://github.com/shuxiachai/returnops-au/pull/61#issuecomment-6339234639)
confirms [PR #17](https://github.com/shuxiachai/returnops-au/pull/17) was adopted
by lead-written squash as `9d948600984ccb70ab7f80677a2bf2a6c720fa09`, from
C head `b6dcc7552c2e52ca4dafd9d4b9400ad860db9365`. This supersedes the
historical "if #17 lands" / "still open" wording below, not its source evidence.

PR #61 now ordinarily merges that exact main into prior C head
`7bb1f5ad6e95a13a4aaffbae3056794116fedea7`; no rebase or force-push.
All main README lines remain unchanged and in order, including A's R.05,
Coordinator, deployment and R.02 notices and the adopted #17 receipts.
Both PRs' dated C README/worksheet records are retained in date order; the
canonical worksheet's personal-answer and signature fields are not filled.

The main-relative review scope is still **four C documents**: this README,
`docs/reviews/member-c-c1-source-review-20261011.md`,
`docs/reviews/member-c-pr56-followup-20261011.md`, and
`stage1/drafts/member-c-contribution-and-interview.md`. The six September
artifacts already adopted through #17 and A/B implementation have zero delta.
The two source-status corrections were confirmed addressed by A at
`7bb1f5ad`; neither packet nor corpus/admission bytes are changed here.

[CI 39724718286](https://github.com/shuxiachai/returnops-au/actions/runs/39724718286)
and [CI 39724719271](https://github.com/shuxiachai/returnops-au/actions/runs/39724719271)
passed 13/13 jobs each for the preceding #17/#61 heads. They do **not** validate
this new #61 merge. The PR records the new exact head, local verification,
normal new-head checks and A's targeted re-review separately. Adoption remains
A's lead-written squash decision; this change does not merge main.

Prepared with Codex assistance for KAN-23. Source selection permits passage
capture only; exact-byte review, runtime corpus admission, live-model/Gold/C3
execution, personal explanation and joint acceptance remain separate. No
frozen ownership/dependency, public contract, A/B code or Done status changes.

## C source-review follow-up — 22 October 2026 (Sydney)

Following [A's latest #61 instruction](https://github.com/shuxiachai/returnops-au/pull/61#issuecomment-6330830936),
this review candidate re-merges main
`4aec7c0de6536075f6691567a3f609b8f3093279` by an ordinary merge. It preserves
the adopted deployment, F.06, R.02 and frontend material without editing A/B
implementation, and places C's 21 October notice below the newer 22 October
notices. The earlier preparation to wait for #17 did not publish a change;
this reconciliation follows A's subsequent request to refresh both branches.

The current diff against that main is **four C documentation files**:
README, the C1 source-review packet, the historical PR #56 follow-up, and the
canonical C contribution/interview worksheet. The preceding GitHub five-file
view also included the #85 handoff note because of rewritten ancestry; that
already-adopted note now has no delta from this integration base. Recount the
actual PR diff after any further main update rather than reusing either count.

The intended adoption order remains #17 then #61, with a lead-written squash
message. If #17 lands first, reconcile again against that adopted main and
preserve both dated README/worksheet records before targeted re-review. A's
[approval of #17](https://github.com/shuxiachai/returnops-au/pull/17#pullrequestreview-5600248843)
covers `0137e1e024ec2ca3a3e9ca19028ea196175964d4`, not a later head or #61.
The successful [#61 run 39563374199](https://github.com/shuxiachai/returnops-au/actions/runs/39563374199)
covers `7d617cca808ab81accc7b8c82c15cc91033b8e35`, not this new reconciliation.
The PR records the new exact head, publication, local checks and normal CI
separately; A's targeted new-head review remains required before adoption.

Prepared with Codex assistance for KAN-23. No pending corpus or admission pin,
runtime/model capability, frozen Owner/Reviewer/S/F, personal answer/signature,
joint acceptance or Jira completion is changed by this documentation work.

## C receipt integration refresh — 22 October 2026 (Sydney)

Following [A's new conflict-resolution request](https://github.com/shuxiachai/returnops-au/pull/17#issuecomment-6330830678),
[PR #17](https://github.com/shuxiachai/returnops-au/pull/17) normally merges the
checked main `4aec7c0de6536075f6691567a3f609b8f3093279`. All main README content,
including A's deployment/R.02/F.06 notices and B's adopted frontend, is preserved;
the C October 21 receipt now precedes the October 20 receipt. The canonical
[C worksheet](stage1/drafts/member-c-contribution-and-interview.md), compatibility
pointer and six byte-unchanged September supporting artifacts remain intact.

[A's previous approval](https://github.com/shuxiachai/returnops-au/pull/17#pullrequestreview-5600248843)
and successful [CI 39563682501](https://github.com/shuxiachai/returnops-au/actions/runs/39563682501)
apply only to `0137e1e024ec2ca3a3e9ca19028ea196175964d4`, not this new merge.
The PR records the new exact head, local checks, normal CI and targeted review
separately. A remains the squash-merge decision maker. #61 must preserve this
receipt and worksheet when integrating the actual post-#17 main; neither PR's
old approval transfers to new bytes.

This is Codex-assisted C documentation integration, not a change to A/B code,
contracts, frozen allocation or runtime gates. R.02's new no-LLM evidence does
not establish R.03 live-model/pilot acceptance, corpus admission, C3 execution,
Gold results, personal explanation or joint sign-off. No new PG17 reproduction,
course submission, main merge or Jira Done is claimed.

## C source-review reconciliation — 21 October 2026 (Sydney; historical source)

This Codex-assisted correction addresses [A's 21 October review](https://github.com/shuxiachai/returnops-au/pull/61#pullrequestreview-5596152325)
and incorporated the then-observed main through a normal merge, without
rewriting the C branch history. It preserved every baseline main README line.
The original placement below the 18/19 October notices is historical; A's later
22 October instruction moves this dated section above those older notices.
The earlier 19 October reconciliation used `c85efc0`; that too is historical,
not a claim about today's integration base.

A merged [PR #85](https://github.com/shuxiachai/returnops-au/pull/85) at
21 October 18:16:10 Sydney (07:16:10 UTC), adopting reviewed head
`132692b6b731b4a5cee1ec041c7e3eba0ba25527`. The PR event retains the original
adoption identity, but the lead later rewrote that commit without changing its
tree. Original `55075f05246eb59f27233f5582b276435f1cf60d` and replacement
`4bb7cf0ba04a62ef907d0bfb3ad5e468ee7b3a73` share tree
`1a75c6ebd5aa909aa49692d09d73b607fbfb3fc7` and parent `a885cff4`.
Neither historical identity is presented here as current main.
Its two-file documentation approval is not corpus, live-model or whole-feature
acceptance. [Original run 39560805445](https://github.com/shuxiachai/returnops-au/actions/runs/39560805445)
on `55075f0` was **cancelled**, not successful. The
[replacement-main run 39566117680](https://github.com/shuxiachai/returnops-au/actions/runs/39566117680)
on same-tree `4bb7cf0` **passed**. This is that exact historical main tree's
result, not a substitute for new PR checks or runtime/course acceptance.

The source-selection disposition is **include for next passage capture only**.
[The updated source-review packet](docs/reviews/member-c-c1-source-review-20261011.md)
distinguishes that completed decision and #68's preparation adoption from still
pending exact-byte/context/conflict review and a separately trusted admission pin.
PR #17 and #61 both add dated worksheet receipts: preserve both in date order,
and reconcile/recheck whichever is adopted second against actual main.
No personal confirmation field, A/B implementation or frozen dependency changes.
Use [PR #68](https://github.com/shuxiachai/returnops-au/pull/68) for the later
C1 context candidate and its exact-byte review, not the historical planning
paragraphs below. PR #7 is now merged; other PRs retain their own review/check
records. Normal PR checks and targeted re-review are required before adopting
this branch. No runtime, personal, corpus or whole-feature acceptance is claimed.

## C September receipt reconciliation — 2026-10-21

Historical checkpoint, superseded by the October 22 integration receipt above.
[PR #17](https://github.com/shuxiachai/returnops-au/pull/17) preserves six
September supporting artifacts: the clean-Git note/ZIP, F.01 review/probe,
and PG17 reproduction report/ZIP. Its worksheet increment uses the adopted
[canonical C record](stage1/drafts/member-c-contribution-and-interview.md);
the old `docs/reports/` path remains a compatibility pointer. The intended scope
is those six artifacts plus README and the worksheet; the current exact diff
and file inventory are recorded in the PR. A/B models, runtime, contracts,
allocation and adopted archives are not changed by this C increment.

Following [A's October 21 review](https://github.com/shuxiachai/returnops-au/pull/17#pullrequestreview-5596152615),
the then-current branch merged `55075f05246eb59f27233f5582b276435f1cf60d`
and preserved all main README lines. That historical commit was replaced on main
by same-tree `4bb7cf0ba04a62ef907d0bfb3ad5e468ee7b3a73`; neither is a claim
about today's main. The October 19 path reconciliation used historical
`c85efc07676e58b51f88da5d7c457d79f1f4ad80`. Subsequent exact-head approval and
CI are linked above; those results do not cover later bytes.
[Issue #16](https://github.com/shuxiachai/returnops-au/issues/16) remains bounded
documentation/receipt work, not every KAN-22 acceptance gate.

The October notices remain intact. The September blocks below retain their
historical status and do not override the adopted [Stage 1 archive](stage1/README.md)
or newer project notices. Both the October 19 path/receipt increment and this
October 21 reconciliation were prepared and checked with Codex assistance,
not independently authored or personally confirmed by C. No new PG17 run,
live Jira audit, personal answer/signature, course submission, predecessor,
F.02 or whole-package acceptance is claimed.

## C handoff adopted — 20 October 2026 (Sydney)

This dated receipt supersedes the older C **current-status** statements below;
their source hashes, test results and pending decisions remain historical
evidence. In particular, **PR #79 is merged, not Draft or awaiting approval**.

A (`shuxiachai`) merged [PR #79](https://github.com/shuxiachai/returnops-au/pull/79)
at **20 October 00:41:51 Australia/Sydney** (19 October 13:41:51 UTC):

- Reviewed head: `e6354bf3b881f9c2fa5f8fe011fa34966f9f8e41`, covered by
  [A's exact-source technical approval](https://github.com/shuxiachai/returnops-au/pull/79#pullrequestreview-5570342865).
- Adopted main commit: [`e35c61d272040d2aad18b5931d7bb4eed04e3a34`](https://github.com/shuxiachai/returnops-au/commit/e35c61d272040d2aad18b5931d7bb4eed04e3a34).
  Its tree is `f1e31c1caf7b543ffa5cba46e695c7f726bd9121`, identical to the
  reviewed head; there are no additional implementation changes in the adoption.
- [PR checks 39213546758](https://github.com/shuxiachai/returnops-au/actions/runs/39213546758)
  and the separate [actual-main checks 39262355437](https://github.com/shuxiachai/returnops-au/actions/runs/39262355437)
  both completed successfully, attempt 1. Main's API/PostgreSQL job completed
  at 20 October 01:43:09 Sydney (19 October 14:43:09 UTC). These are distinct
  exact-source runs, not a relabelled local composite or a new C live-model run.

**Adopted scope:** C's four-file handoff documentation and synthetic regression
component, following the earlier C1/C2/evaluation preparation adoptions in
#68/#69/#70. The old local transport/image/capture lab is still **not** imported.
This status-only follow-up changes no A/B implementation, public contract,
workflow, candidate corpus, frozen owner/reviewer or S/F dependency. The earlier
approval covers the recorded component source, not this later documentation edit.

**Still required:** exact corpus/context/conflict disposition and trusted pin;
approved provider/model/input flow and budget; retained-input/current-state
wiring; E.01/private Gold and genuine blind A/B timing/review/arbitration;
prerequisite-qualified R.02/R.03, real C3 image evidence, personal explanation
and joint acceptance. A merge or green CI does not satisfy these conditions.
The remaining-effort estimate below is not reduced merely by this adoption.

Jira [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) records technical
progress separately from feature acceptance. Preserve the existing status and
original acceptance conditions; do not mark the whole feature Done. The existing
[C handoff evidence](docs/reviews/c-local-handoff-20261015.md) retains the earlier
reproduction receipts. No main merge, live invocation or human sign-off is
performed by this Codex-assisted status follow-up.

## C handoff integration on adopted main — 19 October 2026, after 06:34 UTC

This is the newest C status receipt; older dated notices below remain historical.
A [approved PR #69 at exact `f2bf32d`](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5567289418)
and merged it as `5006da1ab0dcf046e34e5d16bb9407941322c574`.
Its [normal PR checks](https://github.com/shuxiachai/returnops-au/actions/runs/39202282951)
both passed. Together with #68 and #70, this removes the component-adoption
blocker for [C handoff PR #79](https://github.com/shuxiachai/returnops-au/pull/79).
It does **not** approve corpus content/pins, real-model use, Gold, runtime gates,
personal contribution or whole-feature completion; Issue #66 remains open.

C reconciled #79 with that actual main in an isolated checkout, preserving
all main README lines and the historical C receipts. Only C's handoff tests
and documentation differ from main; adopted component code, A/B implementation,
public contracts, workflow and the frozen allocation are unchanged. The
unadopted local transport/image/capture lab is not included.

An independent AI-assisted technical check found that the nine handoff tests
needed the same filesystem-capability guard as adopted C1. The test-only fix
keeps all nine running on capable hosts, explicitly skips them on unsupported
hosts, and separately verifies fail-closed rejection without filesystem I/O.
This does not weaken the production loader or claim Windows admission support.
See the [integrated-source evidence and reproduction](docs/reviews/c-local-handoff-20261015.md#19-october-actual-main-integration)
for local validation scope. Exact final source, normal CI and review links are
recorded in the PR thread, not inferred from the older composite runs.

**Still Draft:** A's targeted non-author review and normal checks must cover the
new integrated head before Ready/merge. Local DB/Docker remain paused. C has
not merged main, marked Jira Done, performed real model/image calls or supplied
human timing/sign-off. The earlier 45–55% remaining-effort planning range is
not reduced merely because a preparation PR merged.

## C delivery progress after A's component adoption — 19 October 2026

**Approximately 50% of C's delivery effort remains (planning range 45–55%).**
This is a coarse workload judgement, not a grade, authorship share, measured
completion rate or count of tests/PRs. Planning weights: C1 20%, C2 20%, C3 15%,
evaluation 30%, C's joint-verification/delivery contribution 15%. These are not
changes to the frozen ownership or contribution allocation. Earlier 55%/60%
estimates below are dated history; the remainder is not all waiting for A.

### Newly verified adoption and independent follow-up

- A approved and merged [C1 PR #68](https://github.com/shuxiachai/returnops-au/pull/68#pullrequestreview-5567051891):
  reviewed `4dc60bd`, merged `437b4eb`. This adopts preparation code and explicitly
  PENDING candidate data, **not corpus semantic/context admission or a trusted pin**.
- A approved and merged [evaluation PR #70](https://github.com/shuxiachai/returnops-au/pull/70#pullrequestreview-5567078774):
  reviewed `e5b3e91`, merged `d9813d6`. This adopts the preparation tool, **not
  E.01/Gold/human timing/live-model or whole-feature acceptance**.
- C addressed [A's README-only PR #69 blocker](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5567087122)
  and pushed `f2bf32d184a34d4eddc883150257ba93cf5dc892`, incorporating actual main
  `d9813d6` and preserving every main README line plus both C2 sections. Original
  C2 implementation/prompt/tests are unchanged. Exact local verification passed
  361 contracts, all six offline steps, 244 security and 36 records tests;
  focused 46 C2 tests overlap. Independent AI-assisted read-only review found no
  blocking issue. [Exact-head re-review requested](https://github.com/shuxiachai/returnops-au/pull/69#issuecomment-6260042217).
  Its [fresh normal CI](https://github.com/shuxiachai/returnops-au/actions/runs/39202282951)
  is separate; this receipt does not assume both jobs finished or A adopted it.
- The separate **local-only** backup now includes `08b75126e8e1f8d426c5aa76c9228e080db2bab4`:
  four same-case image-extraction-off/on pairs, preserving packet/retrieval/
  attachment hashes. A vision failure remains visible and stops Risk; no empty
  success or dropped variant. It passed 807 local contract/security/record/order
  tests and 1,933 subtests, plus the six-step offline runner. Clean-source
  rehearsal retained 8 variants, 7 Risk returns and 1 expected vision failure.
  Receipt SHA-256: `279cb440713a7631affd20d7f1623fdf69d0bddab7c606fd89567847f4025feb`.
  All replies are fake HTTP and the Assessment packet is fixed. This is neither
  image-quality improvement nor C3.03/R.03 acceptance, and these local modules
  are **not included in this public dependent Draft**. Only a future narrow,
  reviewed C migration may bring them onto the adopted main.

### Remaining work: independent versus collaborative

| Track | C can do independently / already prepared | Actual decision or collaboration required, followed by more C work |
| --- | --- | --- |
| C1 | Source-context/coverage and retrieval/admission tests already exist; address specific review findings. | A must disposition exact content/context/conflicts and trusted admission pin; C then verifies admitted-corpus quality and hands it into runtime. |
| C2 | Independent prompt/boundary tests and local HTTP transport candidate exist. | Provider/model, permitted data flow, budget and A's retained-input/current-version interface; C still runs real Risk, analyses misses/false positives and fixes measured faults. |
| Evaluation | Accounting, pair consistency, evidence CLI, capture/replay and human-time importer already exist; do not recreate them. | E.01/private inputs agreement; C seals initial labels, A/B genuinely complete blind timing and review/arbitration, then C freezes and scores actual outputs and runs real B1/B4. |
| C3 and integration | The local observer and new off/on plumbing tests are prepared. | R.03/stable real text path, authorized image/attachment and Assessment wiring, then C performs real image-quality checks and a full demonstration with A/B. |
| Delivery | Keep exact-source evidence, README and restorable backups current. | Actual integrated reproduction, independent acceptance and personal explanation; R.05 remains A-owned with C review, not C's solo obligation to finish all team work. |

The 30-case Gold / 20-case timed subset are frozen **team protocol**, not new
teacher-rubric quotas. Original WBS/S/F, optional C3 and private/blind sequencing
remain unchanged. Once inputs are available, C must execute the remaining real
work; approval alone does not complete it. No appointment or personal sign-off
is fabricated. #79 remains Draft until C2 is adopted, the resulting actual main
is reconciled and the nine handoff tests/contracts plus normal checks/review
run on that exact integrated source.

Jira adoption-only updates are saved at
[KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23?focusedCommentId=10107) and
[KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25?focusedCommentId=10108).
No card was marked Done and no A/B implementation or main was changed by C.
This README-only receipt uses `[skip ci]` for quota conservation, never as an
implementation-check substitute. Prepared with Codex assistance.

## C synchronization receipt — 2026-10-19 (later checkpoint)

This dated receipt supersedes only the current-status statements in earlier
blocks. Main advanced to `bbf0869cf23b970078209aee7b9615ac4d9b9902` when A
merged [PR #20](https://github.com/shuxiachai/returnops-au/pull/20); PR #7 is
also merged. These are bounded Stage 1 guide/archive increments, not completion
of C's Stage 2 work or personal/joint acceptance.

Both normal jobs (**offline contracts/models and API/PostgreSQL**) are now
successful for each exact corrected source; no extra rerun was requested for
this synchronization:

| C PR | Exact head | Completed normal run |
| --- | --- | --- |
| #68 C1 | `4dc60bd93b900a579758ec026fb851d0754fdba0` | [39187150566](https://github.com/shuxiachai/returnops-au/actions/runs/39187150566) |
| #69 C2 | `11ca4f08c74885f39f960f89b15e305e1ccaf5ba` | [39186660660](https://github.com/shuxiachai/returnops-au/actions/runs/39186660660) |
| #70 evaluation | `e5b3e91a6e82b3419bbc542c537861eb961988bd` | [39187153134](https://github.com/shuxiachai/returnops-au/actions/runs/39187153134) |
| #61 source review | `b23b7481c083bd7d0805fe9fb20e6b9ca390aaea` | [39186658534](https://github.com/shuxiachai/returnops-au/actions/runs/39186658534) |
| #17 historical receipts | `3ab0e886c752ed3e30b0cdbc0c60097b52a93df2` | [39187151323](https://github.com/shuxiachai/returnops-au/actions/runs/39187151323) |

Those runs cover their recorded branch sources, not a claimed integration with
the later `bbf0869` main. A's earlier reviews remain attributable to their own
heads; the current corrections still need non-author re-review/adoption.

### Local backup, not public adoption

An append-only local checkpoint on `local/c-provisional-oct19` is
`543d0d03e1319f1035df17c4fbc84dcac187ff54` (tree
`43fef3fee1f3f90272af37dd87e7d35faf238a8f`). It preserves the original Oct18
snapshot and unadopted experimental transport/image/capture work. Only the
bounded C1/evaluation corrections were imported; this is **not** a blind merge
of all public branches or a current-main deployment.

The local mock lab also fixes a real source-recording defect: inherited
`GIT_DIR`/`GIT_WORK_TREE` can no longer redirect the recorded commit to another
checkout. It reuses the bounded, isolated Git reader, validates the SHA and
fails before publication if initial/final source identity cannot be established.
The three-file fix received an independent AI-assisted review. It remains in
the local backup, not silently included in this public dependent Draft.

Exact clean-checkpoint verification: **798 tests / 1,923 subtests** across
contracts/security/records/orders; six static groups, 12 checker tests,
7 runner tests and 14 Mermaid blocks pass. The four local component suites
pass 84 tests / 242 subtests (overlapping, not additional counts). A clean-source
12-case mock rehearsal retained 6 reviews and 6 expected failures. Its receipt
SHA-256 is `376a2fbee458b382cd4fb70e22b7a08723483f59ead1dec7a465ee9c17460df1`.
No DB, real provider/model, real image interpretation, Gold or human timing
was used; these checks establish neither R.03 nor B4 acceptance.

### Jira and next decisions

Dated evidence/pending-work comments were saved to
[KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23),
[KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24),
[KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25),
[KAN-26](https://lucastaooo.atlassian.net/browse/KAN-26),
[KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22),
[KAN-12](https://lucastaooo.atlassian.net/browse/KAN-12) and
[KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33).
Their original status, dates, estimates, owners, reviewers and S/F conditions
were retained; no card was marked Done. Technical threads
[#58](https://github.com/shuxiachai/returnops-au/issues/58#issuecomment-6259670017),
[#66](https://github.com/shuxiachai/returnops-au/issues/66#issuecomment-6259670187) and
[#67](https://github.com/shuxiachai/returnops-au/issues/67#issuecomment-6259670385)
now link the same exact-head checks and remaining decisions.

Still needed: A's exact corpus/context admission and trusted pin; approved
provider/input flow and retained-input/current-state integration; E.01/private
Gold agreement and genuine blind A/B timing; prerequisite-qualified real pilot,
C3 authorized-image demonstration and joint acceptance. There is no new A/B
scheduling confirmation or personal explanation record. **#79 stays Draft**
until dependencies are adopted and its exact integrated source is retested.
This README-only receipt uses `[skip ci]` to conserve quota, never to satisfy
required implementation checks. Prepared with Codex assistance; A/B files and
main are untouched by this update.

## C review follow-up — 2026-10-19

A's new reviews have been read and the actionable C corrections are published
below. The checked main is now `c85efc07676e58b51f88da5d7c457d79f1f4ad80`
after [PR #7](https://github.com/shuxiachai/returnops-au/pull/7) merged.
This notice supersedes current-status wording in older dated blocks; it does
not replace their historical evidence or claim a newly measured completion rate.

| Review entrance | New exact C source | Follow-up and remaining boundary |
| --- | --- | --- |
| [#68 C1](https://github.com/shuxiachai/returnops-au/pull/68) | `4dc60bd93b900a579758ec026fb851d0754fdba0` | Fixed platform-aware admission tests while preserving all supported filesystem/security assertions and explicit unsupported-host rejection. Context/coverage expansion was already published at `94c8e55`; the older statement that expansion is still outstanding is obsolete. Final corpus admission, authentic non-author review and a separately trusted pin remain outstanding. |
| [#69 C2](https://github.com/shuxiachai/returnops-au/pull/69) | `11ca4f08c74885f39f960f89b15e305e1ccaf5ba` | Reconciled README/main without changing Risk code or tests. A reported no new P1/P2 in the bounded prior-source review; exact new-source review/normal checks are still required, and no live-model or runtime acceptance follows. |
| [#70 evaluation](https://github.com/shuxiachai/returnops-au/pull/70) | `e5b3e91a6e82b3419bbc542c537861eb961988bd` | File CLIs now reject unsupported platform capabilities before I/O. Pure calculations remain portable; supported-platform safety and whole-bundle privacy checks remain. Definitions/private data, formal Gold, real timing and real model measurements are separate uncompleted gates. |
| [#61 source review](https://github.com/shuxiachai/returnops-au/pull/61) | `b23b7481c083bd7d0805fe9fb20e6b9ca390aaea` | Reconciled README notices with current main. Earlier source-capture approval is not corpus admission; new exact-source review/checks remain necessary. |
| [#17 historical receipts](https://github.com/shuxiachai/returnops-au/pull/17) | `3ab0e886c752ed3e30b0cdbc0c60097b52a93df2` | Migrated the worksheet increment to canonical `stage1/drafts/`, retained the old compatibility pointer and six byte-unchanged September artifacts, corrected scope to eight files, and preserved October notices. Historical PG17 receipts are not a new-main run or a personal/team signature. |

All five source-specific local runs passed the full six-step offline runner,
244 security tests and 36 records tests. Contract counts for #68/#69/#70/#61/#17
were respectively **168/174/275/128/128**; focused suites overlap those counts.
The C1 and evaluation capability-absence simulations are **not native Windows
execution**. Local runs are not PG17 deployment, live-model quality, formal Gold,
runtime gates or team acceptance. One normal PR run per corrected branch was
requested after local verification, as A requested; use each exact PR head's
live checks rather than assuming completion from this README. No workflow or
A/B implementation was modified.

[PR #20](https://github.com/shuxiachai/returnops-au/pull/20) is still open at
`fe77638aac5ad7c82db0ada8ac639815f8c65221`; its normal offline and API/PG checks
passed in [run 39177811043](https://github.com/shuxiachai/returnops-au/actions/runs/39177811043).
That is not a merge or a new C runtime acceptance.

### Dependent Draft and decisions still needed

Per A's latest review, **#79 remains Draft and must not be used as a standalone
implementation**. Its nine rehearsal tests still depend on the separate C1/C2
candidates. The old composite receipts below are historical: this documentation
follow-up did not produce a new combined-source pass. After the dependency
blockers are resolved and their adoption is recorded, reconcile with the
resulting main, rerun the nine tests and all contracts on that exact integrated
source, request normal checks and obtain re-review before changing readiness.
This README-only dependent-Draft update uses `[skip ci]`; it does not satisfy
required checks or waive the later normal run.

The [existing decision checklist](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231733616)
still needs specific answers: final exact corpus/context admission and pin;
provider/model, permitted input flow, trusted packet/current-version integration
and budget; E.01 definitions, private Gold access and blind-timing arrangements;
and the exact integrated source plus original R.02/A1.08 prerequisites before
the real R.03 pilot. C3 retains its original text-pilot/attachment dependencies.
The expanded pending corpus inventory is now SHA-256
`4367be77154fe3db61683d3bd8d8be7d495a997a63cd95e99cae0fba22fe13e2`;
older inventory hashes in comments are historical, not approval pins.

There is still no confirmed A/B reply to the
[18–19 October Sydney scheduling request](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231875735).
Lucas's stated availability is not an agreed meeting or permission to extend it
to other dates. None of these updates creates human timing, Gold labels, a
personal explanation, a Jira transition/Done, a main merge or teammate approval.
Implementation and checks in this follow-up were Codex-assisted.

## Historical C follow-up — 2026-10-18

**Planning estimate: approximately 55% of C's work remains (50–60% range).**
This is a coarse estimate of remaining implementation, integration, evaluation
and delivery effort—not a measured completion rate, grade, authorship share or
test/PR count. The earlier 60% estimate below remains history. The larger
remainder is real model/evaluation/image/integration work, not missing paperwork.

A has now responded. This checkpoint supersedes dated current-status wording
below, not the original evidence. Main remains `17042b4`; no main merge, Jira
transition or human acceptance is claimed.

### Independent work completed in this follow-up

- **Evaluation / [#70](https://github.com/shuxiachai/returnops-au/pull/70):**
  `bacca6a74aee967fa80c74004833fdac0334a155` fixes A's P2 cost-summation finding.
  Integer-scaled aggregation preserves exact decimal strings even under low
  precision, altered rounding and Decimal traps. Unknown costs remain unknown;
  failed attempts retain known usage. Four new regressions pass. The correction
  is ready for A's re-review; it does not itself resolve the requested changes.
- **C1 / [#68](https://github.com/shuxiachai/returnops-au/pull/68):**
  `e15394a05d253d1f5bcdb61aac4559c2a133d604` incorporates current main and resolves
  the README conflict while retaining main's public-scope notice and C's dated
  evidence. A reported no new P1/P2 in the bounded loader/tests review, but did
  **not** admit the corpus. Candidate bytes, pending fields and inventory hashes
  are unchanged; the three short captures are not a sufficient-runtime claim.
- **Local verification:** the corrected #70 passes 267 contract tests, including
  139 evaluation tests. Reconciled #68 passes 162 contract tests. Each host run
  also passes six static groups, 244 security and 36 records tests. The dependency
  composite passes 339 contract tests; its Linux network-disabled run passes
  **619 tests total** (339 contracts + 244 security + 36 records). Counts overlap.
  The two evaluation commands also pass independently from a clean `bacca6a`
  checkout on Linux with Python `-S`, including repeatable bundle hashes and
  invented timing arithmetic. [Exact sources and limits](docs/reviews/c-local-handoff-20261015.md)
  distinguish these checks from PG17 deployment, real models and formal evaluation.
- **C2 / [#69](https://github.com/shuxiachai/returnops-au/pull/69):** A's response
  accepts the preparation boundary for further integration, not a live Risk
  implementation. Preserve the trusted retained inputs and post-await current
  version check; model output cannot approve or dispatch work.

### What C can do alone, and what needs A/B

| Work | C can prepare independently | Required decision, input or joint work |
| --- | --- | --- |
| C1 corpus | Expand exact source context/coverage and its tests within the already selected sources; this substantive corpus expansion is **still outstanding**, not completed by the README conflict fix. | A must review the final passage/context/conflict coverage and exact bytes; integration must supply a separately trusted admission pin. |
| C2 Risk | Existing typed boundary, cancellation/failure tests and offline input/output checks are implemented. After configuration is agreed, C still must implement and test the real separate model invocation. | A confirms provider/model, permitted data flow, shared transport/deadlines, trusted retained inputs and current-version integration point. Credentials stay out of GitHub. |
| Evaluation | Accounting, quality/pair consistency, evidence-bundle and timing-import tools are implemented; public invented rehearsals can run independently. | E.01 agreement precedes C's private initial 30-case Gold seal. A/B independently time the 20-case subset, lock answers, then review/arbitrate in the frozen order; formal B1/B4 also needs the real system. These counts are team protocol, not extra rubric quotas. |
| Runtime pilot and C3 | C keeps the retrieval/Risk evidence and image-test design ready. Do not substitute more toy tests for the missing runtime feature. | A completes R.02 and trusted orchestration; C runs R.03 with the real three-role path once its original prerequisites hold. B's UI integration is separate joint verification, not an added R.03 prerequisite. C3 image implementation starts after R.03 and keeps the original attachment/finish dependencies. |
| Final delivery | C can maintain exact-source instructions and draft the evidence/report sections. | Integrated clean reproduction, demonstration and genuine member/reviewer records require the actual system and people. |

The remaining work is **not all waiting for A**: C still owns substantive corpus,
real Risk, evaluation and image work once their inputs/prerequisites are ready.
The frozen owners and S/F dependencies in docs/07–08 remain unchanged.
[The existing A/B scheduling request](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231875735)
has no confirmed slot; Lucas is available on 18–19 October Sydney time.
[#79](https://github.com/shuxiachai/returnops-au/pull/79) remains a dependent Draft.
All current checks were local; no new Actions run was requested. These updates
were prepared and tested with Codex assistance, not recorded as personal sign-off.

## Historical C follow-up — 2026-10-17

The latest checked main is
[`17042b4`](https://github.com/shuxiachai/returnops-au/commit/17042b4164a0be878c7a0684cf532217ebeb77ee).
This C handoff branch now includes that main revision, preserving the public
scope notice and CI-budget maintenance from
[PR #80](https://github.com/shuxiachai/returnops-au/pull/80). There is no new
business-runtime implementation in that maintenance merge. Older dated notices
below describe their original snapshots, not today's completion status.

- **C review queue:** [#68](https://github.com/shuxiachai/returnops-au/pull/68),
  [#69](https://github.com/shuxiachai/returnops-au/pull/69) and
  [#70](https://github.com/shuxiachai/returnops-au/pull/70) still await A's review;
  [#79](https://github.com/shuxiachai/returnops-au/pull/79) remains a dependent
  Draft, not a standalone or merge-ready implementation.
- **New C work:** #70 at `db45f5f` adds two usable local commands: a single-command
  synthetic evidence bundle and a human-time record validator/statistics tool.
  The former runs both fixture adapters and preserves raw results, output-bound
  quality evidence, failure counts, source/config hashes and separate creation
  metadata. The latter computes A/B/pooled active-time median/Q1/Q3/IQR, checks
  order, pauses, duplicates, overlap and missing records, and never fabricates
  human work. Unknown evidence remains unknown; neither command claims a real
  model result or gate. The earlier quality/pair arithmetic remains included.
  [C's component README](https://github.com/shuxiachai/returnops-au/blob/db45f5f1228598e406d02c10953ed11a2f345cdf/experiments/evaluation_candidate/README.md)
  gives the exact commands, public example, formulas and private-data boundaries.
- **Independent-PR local verification:** #70 now passes 135 focused evaluation
  tests within 263 contract tests (47 new tests). The earlier unchanged #69 at `cfda3a1`
  passed 29 focused Risk tests within 157 contract tests, including the caller
  cancellation correction. Both individual checks also passed 6/6 static
  groups, 244 security and 36 records tests. Counts overlap; do not add them.
  The [reconstruction and evidence](docs/reviews/c-local-handoff-20261015.md)
  separate individual PR source from dependency-composite checks and retain
  historical results. A separate clean clone of `db45f5f` ran both commands with
  Python `-S` (no site-packages); repeated bundles had the same content ID, all
  13 file entries/permissions were checked, timing sample results matched, and
  the checkout remained clean. That verifies these two commands, not the whole
  deployed system. The separate 26-file dependency reconstruction passed 335
  contract tests (including those 135 evaluation tests) and the same remaining
  local suites. No cloud CI or PG17/live-model result is implied.
- **Scheduling:** [C has asked A/B for two Sydney-time windows on 18–19 October](https://github.com/shuxiachai/returnops-au/pull/79#issuecomment-6231875735).
  Lucas confirmed availability on both days; A/B responses and the final booking
  remain pending. Independent 20-case timing and a proposed 45–60 minute joint
  troubleshooting session are separate activities, not completed acceptance.
- **A/B updates:** B has pushed further fixes to
  [#60](https://github.com/shuxiachai/returnops-au/pull/60); it is not merged.
  [C's route-collision feedback](https://github.com/shuxiachai/returnops-au/pull/78#issuecomment-6210008364)
  on A's #78 remains unanswered at this check. Neither fact establishes C's
  runtime integration or a completed shared gate.

### What must happen next

1. A reviews the exact C1 corpus/loader and supplies an independently trusted
   admission pin. Pending source bytes must remain rejected until that review.
2. Agree the model/provider and allowed input flow; implement and test a real
   independent Risk invocation. A supplies trusted retained sources, current
   state checks and orchestration; C supplies retrieval/risk components.
3. Complete the fixed-proposal safety chain (R.02), then the actual three-role
   pilot (R.03). Do not replace either gate with synthetic runner results.
4. Complete the sealed 30-case Gold / 20-case blind timing protocol, review and
   arbitration before freezing and running the formal B1/B4 comparison.
5. After the stable text path, implement C3 image observations and their
   uncertainty/injection/conflict tests; finish clean reproduction, demo and
   genuine contribution/acceptance records.

### A decision checklist — reply on the existing PRs

C's component preparation has now received A's 18 October review. The following
remaining decisions/integration outputs still require A's actual response;
the earlier review does not establish those approvals.
These are handoff questions, not a new task board or changes to WBS ownership.

| Priority / review entrance | What A should provide | C's next action after that evidence |
| --- | --- | --- |
| 1. C1 / [#68](https://github.com/shuxiachai/returnops-au/pull/68), KAN-23 | Review the three-category passages/context and conflict coverage; identify required additions or approve final exact corpus bytes with a non-author review link. Then supply a separately trusted final manifest pin through integration configuration. The current pending inventory hashes are not approval pins; #61 approved capture only. | Make requested source revisions, preserve pending rejection until authentic exact-byte approval, then rerun admission/retrieval and hand off the admitted version. |
| 2. C2 / [#69](https://github.com/shuxiachai/returnops-au/pull/69), KAN-24 | Confirm provider/model, allowed input fields/data flow, shared async transport and deadline/usage sources; supply trusted retained packet/retrieval inputs and the post-await current-version acceptance point. Do not post credentials in GitHub. | Implement/verify the separately invoked Risk adapter against the agreed transport, run adversarial pilot checks and provide five-outcome/failure routing evidence. |
| 3. E.01/E.09 / [#70](https://github.com/shuxiachai/returnops-au/pull/70), KAN-25 | Approve or correct field/label definitions, metric denominators and latency interpolation/exclusion details. Identify trusted start/ready/wait event fields; a stub adapter timer is not proposal latency. Agree private Gold storage/access and A/B blind-timing arrangement. | After E.01 and the original dependencies, prepare the 30 inputs/20-case subset and seal initial labels before reading any timed answer; release only non-label receipts/inputs, then follow review/arbitration/freeze order. |
| 4. Integrated source / [#78](https://github.com/shuxiachai/returnops-au/pull/78) and this [#79](https://github.com/shuxiachai/returnops-au/pull/79) | Reply to the route-collision finding; provide the exact integrated commit and R.02 fixed-proposal safety-chain evidence/entry point once ready. Agree the order for adopting #68/#69/#70 before #79. | Reproduce the approved source, verify real C1/C2 handoffs and then run the actual R.03 pilot once A1.08 and all original conditions hold. Keep #79 Draft meanwhile. |
| 5. C3 / KAN-26 | After R.03, provide the accepted text-pilot record and authorized attachment-reference/model-input boundary, with the original F.04/F.07 conditions. | Implement image observations, uncertainty/conflict/injection tests and integrated demonstration; ordinary upload remains separate from image analysis. |

**Earlier planning estimate, retained as history:** about 60% remaining
(55–65%) was a coarse implementation/integration/evaluation/delivery estimate,
not measured completion, marks, authorship or elapsed time. Do not reuse it as a
fresh measured percentage or reduce it by counting tests. The quality/pair tools,
offline evidence command and timing validator above are now implemented; the five concrete next steps
still need their real inputs and acceptance. C1 has offline implementation, C2
has a stub-tested boundary, evaluation has executable preparation, and C3 plus
runtime/formal/human evidence remain outstanding. Jira remains the workflow
record; this README records no card transition or Done claim.

## C draft review handoff — 2026-10-15

This **dependent draft** adds a nine-test rehearsal, this README notice and
[review/validation evidence](docs/reviews/c-local-handoff-20261015.md), based on
main `a0f7fb884dfbc478c82fffc5912934cb8c0deda2`. It preserves dated evidence below.
Main has now adopted [PR #76](https://github.com/shuxiachai/returnops-au/pull/76)
(private core mock return execution/recovery); that is not the complete
return/label/notification chain. [PR #78](https://github.com/shuxiachai/returnops-au/pull/78)
is still a default-disabled HTTP preparation draft. No A/B runtime code or
workflow configuration is changed by this C rehearsal.

**Do not merge or run this draft as a standalone implementation.** It does not
include the implementation files already under review in
[#68](https://github.com/shuxiachai/returnops-au/pull/68) (`af44d6e`),
[#69](https://github.com/shuxiachai/returnops-au/pull/69) (`2ac0442`) and
[#70](https://github.com/shuxiachai/returnops-au/pull/70) (`7c6739f`). At this
snapshot all three still await A's review. Their earlier checks do not certify
this draft. A fresh checkout of this draft alone lacks the C1/C2 imports used by
the new tests. Review the dependencies first; use the isolated reconstruction
instructions in the review record for preliminary local feedback, then rerun on
the actual integrated source after the dependencies are adopted.
The new [C handoff rehearsal](tests/contracts/test_c_handoff_rehearsal.py)
composes the existing candidates using synthetic, non-Gold inputs and a stub
Risk transport. It does not register an application route or activate a model.

### Run locally before requesting another cloud check

First reconstruct the composite source as described in the
[current review record](docs/reviews/c-local-handoff-20261015.md#current-isolated-reconstruction).
Use an isolated Python 3.12 environment and the locked Node 24 model tools;
one-time installation and the additional offline CI steps are documented in
[the check entry points](tools/checks/README.md) and
[the existing workflow](.github/workflows/ci.yml). After installing once:

```sh
python -B tools/checks/run.py offline --baseline-ref 17042b4164a0be878c7a0684cf532217ebeb77ee
python -B -m unittest discover -s tests/contracts -p 'test_c_handoff_rehearsal.py' -v
python -B -m pytest tests/security -q -p no:cacheprovider
```

The recorded **212 contract tests passed on a local composite**, not this
standalone draft: main `a0f7fb8` plus 13 exact dependency files from #68/#69/#70
and this new nine-test file. The [receipt](docs/reviews/c-local-handoff-20261015.json)
records that historical source and its limits. No new PG17, live-model or gate
acceptance is claimed. Raw logs are retained locally; the published receipt is
a summary, not a substitute for a reviewer's independent rerun.

These commands do not push or dispatch Actions. Keep the exact source inventory,
command outputs, failures and any skipped scope with the local receipt; a local
pass is not a remote required check. Do not disable checks or bypass protection.
Coordinate one reviewed upload after local results, rather than repeated trial
pushes. PostgreSQL checks require an explicitly owned disposable PG17 database;
the offline commands are not a substitute for them.

**macOS note:** the current attachment worker intentionally supports resource
isolation on Linux/Windows only (`evidence_validation._apply_limits`). Native
macOS attachment-parser failures must not be hidden or fixed by removing those
limits. Run that suite in a task-owned local Linux container, retaining its
separate result; a native C subset pass alone is not the entire offline CI job.

| C work remaining | Required next evidence / dependency |
| --- | --- |
| C1 / KAN-23 | A must review exact corpus bytes, context, coverage and loader, then supply an independently trusted manifest pin. PR #61 approved capture only; the pending corpus must continue to fail admission. |
| C2 / KAN-24 | Approved shared model transport/input rules, actual separate Risk invocation and semantic/adversarial pilot evidence; A owns authoritative state checks and runtime wiring. Stub passes are not model-quality results. |
| Joint R.02 → R.03 | Complete fixed-proposal return, label, notification and audit chain first; then A1.08 and the real C1/C2 pilot. This rehearsal does not satisfy either gate. |
| Evaluation / KAN-25 | Seal C's initial 30-case Gold labels before reading timed answers; A/B lock blind baseline outputs before review/arbitration/freeze and scoring. No Gold labels enter runtime/repo fixtures. |
| C3 / KAN-26 | R.03 text path first, then authorized image observations with failure/injection tests; upload support alone is not image analysis. |

Project completion also still needs B's reviewed real-API frontend, A3/B3/C3
selected optional capabilities, clean deployment, demo and genuine contribution/
submission evidence. No Jira status or human acceptance is implied by this draft
update. See the unchanged [allocation](docs/07-frozen-work-allocation.md) and
[delivery gates](docs/08-delivery-work-packages.md).

## C2 follow-up after C1/evaluation adoption — 2026-10-19

A's [latest PR #69 review](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5567087122)
held adoption only for the README conflict after PRs #68 and #70 were adopted.
This reconciliation incorporates main `d9813d6da4a9bf2c7f654a2bea6af34be46a0088`
into the C2 branch and retains main's public-scope notice, C1/history sections
and Stage 1 presentation navigation, together with both dated C2 sections below.
The Risk implementation, prompt and C2 tests remain byte-identical to `11ca4f0`.
The new exact head still needs fresh normal PR checks and A's targeted review;
prior-head CI and reviews do not validate this merged source. Issue #66 remains
open, and preparation-component adoption does not establish corpus admission,
real-provider/model or allowed-data-flow approval, runtime integration, Gold,
personal or whole-feature acceptance. Prepared with Codex assistance.

## C2 review reconciliation — 2026-10-19

[A reviewed the 18 October head](https://github.com/shuxiachai/returnops-au/pull/69)
without a new actionable P1/P2 in the bounded static scope, but held adoption
for the README conflict and missing normal checks. This reconciliation brings
main `c85efc0` into C's branch, preserving main's public-scope notice and the
dated C2 record below. The Risk implementation, prompt and C2 tests are unchanged.
The resulting exact head still requires normal PR checks and targeted A review;
an earlier static review is not approval of these new bytes.
Provider/model, allowed data flow, real invocation and current-version runtime
acceptance remain unconfirmed; no real-model, corpus, Gold or gate result is added.

## C2 preparation follow-up — 2026-10-18

C's [Risk candidate README](experiments/c2_risk_candidate/README.md) records
the image-observation handoff and transport-conformance regression increment
for [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24) /
[PR #69](https://github.com/shuxiachai/returnops-au/pull/69). Review that PR's
exact head and local verification evidence; older dated notices below remain
history. This increment changes C's tests/documentation only, not A/B code,
the shared schema or model prompt. Synthetic image observations and stub model
replies do not implement image extraction or establish real-model quality.

A's [18 October review](https://github.com/shuxiachai/returnops-au/pull/69#pullrequestreview-5562244842)
accepted the preparation interface constraints at `cfda3a1`, not a provider or
runtime gate. The next real-call handoff still needs the selected provider/model,
API/response and usage mapping, allowed data flow and shared transport ownership;
never put credentials in a PR. Formal Gold, post-await runtime integration and
C3's R.03 prerequisite remain separate. No merge, Jira Done or joint acceptance
is implied. Prepared with Codex assistance; no personal sign-off is inferred.

## C1 review follow-up — 2026-10-18

This C branch now incorporates main `17042b4164a0be878c7a0684cf532217ebeb77ee`.
The README conflict is reconciled by retaining both main's public-scope notice
and C's dated implementation/course evidence below. No A/B business code or
frozen ownership is rewritten. A's 18 October bounded static review of
[PR #68](https://github.com/shuxiachai/returnops-au/pull/68) found no new P1/P2
in the loader/tests, but **did not approve the corpus or runtime adoption**.
The three short source captures have now been expanded to contextual source
blocks in **`accc-context-20261018-v2`**, covering faulty/quality, wrong-item and
change-of-mind rules with their selected qualifications. See **C's
[capture README and review checklist](experiments/c1_grounding_candidate/candidates/accc-20261012/README.md)**
for exact source locations, omissions, category/conflict mapping, inventory
hashes and reproducible tests. The three merchant fixtures remain explicitly
synthetic. The manifest stays pending with no reviewer or trusted runtime pin.
New tests check real-candidate provenance/context and mandatory rejection;
positive complete-context, category-isolation, conflict and stale-citation
retrieval tests use only invented synthetic fixtures. No real-corpus admission,
live model/Gold result or feature completion is claimed. A still needs to review
these new exact bytes and coverage before any separately approved integration.
The loader's POSIX-only (macOS/Linux) execution boundary remains explicit.

Local verification of this contextual revision (18 October): **69 C1 tests /
116 subtests**, full offline checks (**167 contract tests**, six static groups,
12 checker/seven tool tests, 14 Mermaid blocks and 64 synthetic-order tests),
244 security and 36 record tests passed. The no-network, read-only Linux
container passed **447 tests / 1,352 subtests** (contracts + security + records).
These suites overlap; they are not a completion percentage, runtime integration
or A's acceptance. Publication uses `[skip ci]` for the local-first budget;
skipped required checks are not passed checks.

## Historical C implementation and Canvas check — 2026-10-12

This dated notice supersedes older *current-status* wording below; it does not
rewrite historical evidence or declare any feature accepted. Main was checked
at [`72ffd04`](https://github.com/shuxiachai/returnops-au/commit/72ffd043dbd400b7ae81c3b1d23085ae0be1743b),
including merged [PR #63](https://github.com/shuxiachai/returnops-au/pull/63)
(A's accepted-PASS revision path). The earlier “main at PR #56” snapshot is no
longer current. A's next private manual-handling increment is
[Issue #64](https://github.com/shuxiachai/returnops-au/issues/64), not C-owned code.

**Course requirement, not an achieved mark:** the live Canvas Stage 2 rubric
was read on 12 October: implementation **7**, AI capabilities **4**, Agile **4**,
advanced technologies **5**, total **20**. It explicitly requires **Jira**, source
submission by **1 November 2026, 23:59**, and a **Week 13 demonstration deployed
on site from source downloaded from Canvas**. The PDF does not specify timezone;
the current Assignments list exposes no Stage 2 upload item, so file extensions,
size limits and submission options remain unverified. Use the
[dated source/requirements checklist](docs/28-stage2-submission-checklist.md).
Each member still implements two core features and one selected optional;
documentation and offline tests alone do not satisfy that implementation rule.

### C's bounded implementation increments

| Work | Review entrance and current boundary |
| --- | --- |
| **C1 / KAN-23 — primary** | [Issue #58](https://github.com/shuxiachai/returnops-au/issues/58): [exact-byte admission loader](experiments/c1_grounding_candidate/admission.py), [pending ACCC capture](experiments/c1_grounding_candidate/candidates/accc-20261012/README.md), [negative/admission tests](tests/contracts/test_c1_corpus_admission.py). External trusted manifest pin, non-author exact-byte review, category/source/conflict coverage and immutable snapshots; no runtime wiring. |
| C2 / KAN-24 — isolated preparation | [Issue #66](https://github.com/shuxiachai/returnops-au/issues/66): separate Risk prompt/invocation, five typed outcomes, exact retained-input checks, conflict preservation and fail-closed stub tests. Live provider/data-flow approval, semantic evaluation and A integration remain separate. |
| E.01/E.09 / KAN-25 — small offline preparation | [Issue #67](https://github.com/shuxiachai/returnops-au/issues/67): draft label/denominator definitions and synthetic scorer accounting; no Gold access, sealing, timed runs or B4 performance claim. |
| C3 / KAN-26 — gated future work | Product-image observations remain required, but runtime implementation waits for R.03/text stability and the original F.04/F.07/C2.05/B1.03 finish dependencies. Do not count an upload UI as image analysis. |

[A's PR #61 source-selection review](https://github.com/shuxiachai/returnops-au/pull/61#pullrequestreview-5486256534)
permits the next capture only. It is **not** approval of the new passage bytes,
coverage or loader. The candidate manifest deliberately stays
`PENDING_EXACT_BYTES_REVIEW`; even its correct hash must not admit it. A must
review sufficient context, exact bytes, category/conflict mapping and the loader
before a trusted integration configuration can pin an approved manifest.
Hash validity is not review authenticity, claim support or legal correctness.

Run the new C1 checks with the existing locked Python 3.12 environment:

```sh
python -B -m unittest discover -s tests/contracts -p 'test_c1_corpus_admission.py' -v
python -B tools/checks/run.py offline --baseline-ref origin/main
```

The original synthetic `GroundingCandidate`/pilot below is unchanged. The new
`ReviewedGroundingCandidate.from_directory` is a separate, source-checkout-only
candidate; it has no network, DB, model, approval or execution capability. Its
file-descriptor protections require POSIX (macOS/Linux, including Linux Docker);
unsupported filesystems fail closed instead of silently weakening validation.
Formal C1/C2 acceptance, Gate 1/2, real LLM evidence, full B1/B4 evaluation,
Canvas-package rehearsal and actual per-criterion member contribution records
remain open. No owner, WBS S/F, deadline or Jira Done transition is implied.
These increments were prepared with Codex assistance; each PR records its own
exact source and tests, and A remains non-author reviewer/integrator.

## C follow-up after A review — 2026-10-11

Main verified for this 11 October snapshot: [`d2e809d`](https://github.com/shuxiachai/returnops-au/commit/d2e809d1a127e0e38bab4111394752541ad6b8c6).
This dated receipt supersedes pending/Draft wording in the October 9 and older
snapshots below without deleting their historical evidence.

| Delivery | Verified disposition | What this does not establish |
| --- | --- | --- |
| C handoff [PR #57](https://github.com/shuxiachai/returnops-au/pull/57) | A approved source `737476d`; merged as `988520b` on October 9; four PR/push checks passed | Personal explanation, whole KAN-22, or acceptance of PRs #7/#17/#20 |
| C1 offline [PR #59](https://github.com/shuxiachai/returnops-au/pull/59) | A approved source `cdf3fb8`; merged as `cdfc3c1` on October 9; four PR/push checks passed; component/test bytes unchanged in current main | Real-source corpus approval, runtime integration, whole C1/F.01, C2/C3, or Gold evaluation |
| A private preview/approval [PR #56](https://github.com/shuxiachai/returnops-au/pull/56) | Merged as `d2e809d` on October 9 under A's scoped merge exception; [main CI 37931297595](https://github.com/shuxiachai/returnops-au/actions/runs/37931297595) passed offline and API/PostgreSQL jobs | C's human signature, executable provider operations, whole A2.01, or Gate 1 acceptance |

Review receipts: [A on #57](https://github.com/shuxiachai/returnops-au/pull/57#pullrequestreview-5468873223)
and [A on #59](https://github.com/shuxiachai/returnops-au/pull/59#pullrequestreview-5469070196).
A's non-blocking clarification is retained: the **original failed PR #56 run**
passed its environment suite, failed storage, and skipped the later business
suites/runtime-image validation. It is separate from the repaired, passing
main run above; do not relabel that historical failure as a pass.

### Next C handoff and review entrance

- **KAN-23 remains the primary C work item; keep [Issue #58](https://github.com/shuxiachai/returnops-au/issues/58) open.**
  The [C1 source-selection and integration review packet](docs/reviews/member-c-c1-source-review-20261011.md)
  proposes a small, attributable source set and explicit review/admission checks.
  It is preparation, not an approved runtime corpus or a new loader. A reviews
  the selected context and exact final passage bytes before admission.
- The [C technical follow-up on PR #56](docs/reviews/member-c-pr56-followup-20261011.md)
  separates source inspection, locally rerun offline tests and remote PG17 CI.
  It does not impersonate C's personal understanding or joint acceptance.
- `VALID` still means exact citation identity/version/hash/location consistency,
  not claim support or membership in an earlier retrieval. A retains the full
  retrieval/conflicts and checks membership plus current case/input/proposal
  bindings; C2 independently checks support and material risk.
- C2 fixed five-outcome fixtures remain a next **offline preparation** option,
  not a newly completed reviewer. C3 waits for R.03/text-workflow stability.
  Gold label preparation/sealing remains governed by E.02–E.08; no completed
  sealing or formal evaluation is claimed here.
- At this 11 October snapshot, PRs #7/#17/#20 were separate open items.
  **21 October correction:** #7 and #20 are merged; #17 remains open for its
  exact-source review. Their evidence remains separate, and their adoption is
  not personal or whole-feature acceptance.
- B owns [PR #60](https://github.com/shuxiachai/returnops-au/pull/60) fixes. C does
  not alter frozen Risk/Proposal DTOs to accommodate frontend mock differences.

No owner, deadline, estimate, wire schema, 89-row WBS field or personal sign-off
is changed by this AI-assisted evidence update. Jira comments link actual
delivery records; a merge alone is not a Done transition.

## Current C handoff — 2026-10-09

This dated update supersedes the **current-status wording**, not the original
evidence, in the September notices above and below. Snapshot audited:
[`e7da2bb`](https://github.com/shuxiachai/returnops-au/commit/e7da2bb481af4e59078eadadb0b198eafbc8ea5a).
Jira remains the workflow record; this is a handoff and navigation guide, not a
second completion board or a claim of personal/course acceptance.

- **Adopted project changes:** PRs [#43](https://github.com/shuxiachai/returnops-au/pull/43),
  [#45](https://github.com/shuxiachai/returnops-au/pull/45),
  [#47](https://github.com/shuxiachai/returnops-au/pull/47),
  [#49](https://github.com/shuxiachai/returnops-au/pull/49),
  [#51](https://github.com/shuxiachai/returnops-au/pull/51) and
  [#54](https://github.com/shuxiachai/returnops-au/pull/54) add fixed synthetic
  proposals, private manual handling, controlled synthetic PASS/ESCALATE
  acceptance, Founder revision and REJECT. These A-owned increments do not
  implement C's real retrieval, independent Risk Reviewer or image analysis,
  and do not establish whole A2.01 or delivery-gate acceptance.
- **Technical evidence:** [main CI 37773655294](https://github.com/shuxiachai/returnops-au/actions/runs/37773655294)
  passed for the snapshot above. [PR #56](https://github.com/shuxiachai/returnops-au/pull/56)
  is still Draft at `892962278d278bb5b21b20d381bb3c37339dcc7b`. Its
  [PR CI](https://github.com/shuxiachai/returnops-au/actions/runs/37877205117)
  has a failing PostgreSQL schema-inventory assertion; later environment suites
  did not execute. [Issue #55](https://github.com/shuxiachai/returnops-au/issues/55)
  already records A's correction work. C must review the repaired exact source
  and its complete checks, not reuse this failed candidate as acceptance evidence.
- **Stage 1 files:** use [the adopted Stage 1 index](stage1/README.md),
  [report v0.4](stage1/reports/v0.4/README.md),
  [presentation archive](stage1/presentation/README.md), and
  [C's contribution/interview worksheet](stage1/drafts/member-c-contribution-and-interview.md).
  PR #40 moved these materials; old `docs/reports/` entries are compatibility
  pointers. An archive or merge is not a new Canvas submission receipt.
- **C review queue:** the original C model [PR #12](https://github.com/shuxiachai/returnops-au/pull/12)
  is already merged. [PR #17](https://github.com/shuxiachai/returnops-au/pull/17)
  remains open against `main` and currently reports a conflict; preserve its
  September review/reproduction receipts while reconciling the new `stage1/`
  paths. [PR #7](https://github.com/shuxiachai/returnops-au/pull/7) and
  [PR #20](https://github.com/shuxiachai/returnops-au/pull/20) also remain open.
  Do not blindly replay their old README/report/video snapshots over the adopted
  files. This update neither merges nor closes those PRs and is not their review.

| C's next delivery | Jira / scope | Next evidence, without changing frozen owners or S/F dependencies |
|---|---|---|
| Retrieval and citations — priority first | [KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23), C1; current due date 11 October | Offline versioned corpus/manifest, typed output and deterministic passage/hash, invalid-citation and conflict tests. Formal integrated acceptance remains separate. |
| Independent Risk Reviewer | [KAN-24](https://lucastaooo.atlassian.net/browse/KAN-24), C2 | All five typed outcomes, exact proposal/evidence binding, unsupported-claim/injection tests and no edit/approval/execution authority. A's synthetic result receiver does not complete this task. |
| Evaluation | [KAN-25](https://lucastaooo.atlassian.net/browse/KAN-25), E.01–E.12 | Prepare offline label definitions, denominators and a separate pilot; preserve formal start/finish prerequisites. Seal initial 30-case Gold labels before A/B timing, keep the 20-case subset blind until both outputs are locked, and never publish Gold labels into the repo/runtime corpus. |
| Image observations | [KAN-26](https://lucastaooo.atlassian.net/browse/KAN-26), C3 / selected OF-001 | Start the runtime work only after R.03/text-workflow prerequisite; preserve C3's F.04/F.07/C2.05/B1.03 finish dependencies. Deliver limited observations and injection/conflict tests, not approval or entitlement decisions. |
| Evidence and non-author review | [KAN-22](https://lucastaooo.atlassian.net/browse/KAN-22), [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32), [KAN-33](https://lucastaooo.atlassian.net/browse/KAN-33) | Refresh exact-source links and use the [A1.03 acceptance sheet](docs/reviews/a103-acceptance-current.md). C's own explanation and genuine human review/acceptance require their own record, not an AI-authored assertion. |

Offline C1.01/C2.01 and evaluation preparation do not require falsely declaring
F.01 or Gate 1 accepted. The formal implementation/integration gates remain those
in [frozen allocation](docs/07-frozen-work-allocation.md) and
[work packages](docs/08-delivery-work-packages.md). No A/B implementation, owner,
reviewer, estimate, deadline, Gold label or personal sign-off is changed here.
This handoff was prepared with Codex assistance from the linked repository and
live Jira records; it is not a new local PG17 reproduction or a runtime review.

## Historical C receipts — September 18–20, 2026

The following records apply to their stated dates and exact source commits only.

## C evidence follow-up — 2026-09-20

This dated C-owned follow-up supersedes only the current setup/evidence status in the September 18 section; all earlier records remain below. The main snapshot recorded on September 20 was the published candidate `da1a09fe7704bdb2fd2f989a44ab62bd7f089a41`. C's model/report sources are unchanged. [PR #17 progress correction](https://github.com/shuxiachai/returnops-au/pull/17#issuecomment-5748904252) records the installed Docker Desktop 4.91.0 / Engine 29.8.0 / Compose v5.5.1 and the September 18 saved Jira comments on KAN-22/12/33. Their status was left In Review; this is dated evidence, not a new Jira status board.

The old statement that Docker installation and those Jira comments are still pending is superseded. The [dated C F.01 technical review](docs/reviews/member-c-f01-review-20260920.md) covers all six scopes requested in Issue #10 against exact A source `3dd1ff637693a826990eee5712cfb239a3c3da7b`: source/order conflicts, historical provenance, capacity, Risk hand-off, known-label recovery and notification precedence. A fresh 58-test contract run and [eight focused artifact probes](docs/reviews/member-c-f01-probes-20260920.py) passed. One low-severity fixture issue remains for A: the SENT/customer-history examples still contain failed-delivery/operator-resend text. This is an AI-assisted technical review, not a personal signature, joint acceptance or executed business guards.

**PG17 Compose technical reproduction passed:** the [dated report](docs/reviews/member-c-pg17-reproduction-20260920.md) and [sanitized logs/scripts](docs/reviews/member-c-pg17-reproduction-20260920.zip) document exact A `3dd1ff6`, PostgreSQL **17.11**, **32/32 environment tests** (two retained dependency warnings), repeated migration and the same API process's live/ready **200/200 → 200/503 → 200/200** across the owned DB outage/recovery. After a disclosed Desktop file-read interruption, an independent no-hardlinks Git clone outside Desktop passed a fresh locked installation, the complete five-stage offline suite, final clean status and Git integrity checks; all nine runtime image source/lock files match that exact checkout. Only this test project's containers were stopped; its volume/logs remain. These results supersede the old unexecuted-PG17 status, but establish health-only infrastructure—not business routes, C's personal performance or joint F.02 acceptance.

The new [Stage 1 navigation draft, PR #18](https://github.com/shuxiachai/returnops-au/pull/18), is A-led preparation for **B-owned M-S.03**, with C's existing classification input preserved. It is not yet merged or an accepted final index. [PR #15](https://github.com/shuxiachai/returnops-au/pull/15) now has the separate main-aligned F.03 candidate `a8b480826e9735ef1d741acbc369f760a23732b8`; C's older bounded static comment is historical evidence, not a new-version approval. PR #7 and this PR #17 each require their own A review; do not reuse the merged PR #12 approval.

**Still requiring real user/team evidence:** C's own T01/T02/T03/T09 and D01–03 explanations in the [existing worksheet](stage1/drafts/member-c-contribution-and-interview.md), actual shared-task participation, the owners' exact-version joint acceptance, and A's final report/video plus actual submission receipts. No personal answer, signature, final submission or Jira Done is inferred.

### Unlocked Canvas report rules verified on September 20

The signed-in [Stage One Report Submission page](https://canvas.sydney.edu.au/courses/74323/assignments/695832) now explicitly resolves the old point-grouping question: **25 points = report 15 + individual interview 10**. One designated member submits **one PDF for the entire Project Groups team**; C supplies and verifies C's portion, not a separate personal report upload. The page displays **Sun October 4, 2026, 23:59** as the due time and September 20–October 11 availability with unlimited attempts. No timezone was shown. October 11 availability is not a deadline extension. No submission receipt was observed and nothing was submitted.

The visible rubric rows total 15 report points: ad-hoc requirements 0.5; Feature 1; overall Use-case 1; Use-case specifications 2; Elementary Structure 3; Complex Structure 3; Activity 1.5; Interaction 1.5; State machine 1.5, plus Interview 10. Nine report-row long descriptions were read: **each member needs at least one informal requirement, one use-case specification and one Activity, Interaction and State-machine model of specific behavior; the group needs 5–10 use cases in total.** The ad-hoc *diagram* is optional, not the individual informal requirement. Retain the existing selected models.

Shared delivery needs one comprehensive Feature diagram (feature-specific NFRs encouraged), one overall Use-case diagram (the page says “all architects and stakeholders”), a detailed design-time Class diagram using appropriate generalization/composition/aggregation/interfaces/multiplicity, and class-based runtime Complex Structure models using Object/Collaboration/Structured Class concepts. The Interview long description could not be opened; its 10 points are confirmed, but specific instructions must still be checked. The declaration requires accurate acknowledgement of generative-AI/other assistance and retention of the submitted work, drafts, AI outputs and research materials for **one year**. Do not pre-sign it for another member or recycle another course's work without permission.

**Video page verified after reconnecting:** the signed-in [Stage One Video Submission task](https://canvas.sydney.edu.au/courses/74323/assignments/695833) requires a **video no longer than 8 minutes**, introducing the project and key agent roles/functions, use cases and design models. Upload the video to Canvas before the deadline; an additional YouTube link is recommended, not a replacement for the upload. The task is **5 points**, counts for all group members and shows the same October 4, 2026, 23:59 deadline, September 20–October 11 availability and unlimited attempts. No explicit file-extension limit or timezone was shown; verify uploader constraints when producing the final file. No declaration was accepted and no submission receipt was observed. A coordinates the final upload; each member verifies their own included material and retains the separate individual interview requirement.

## Post-merge status — 2026-09-18

**Historical September 18 snapshot; later October notices take precedence for current status.** The verified published main snapshot at that time was [main at `da1a09fe`](https://github.com/shuxiachai/returnops-au/commit/da1a09fe7704bdb2fd2f989a44ab62bd7f089a41). Publication and technical review have advanced; personal evidence, joint acceptance and final course submission are separate gates. The September 7/16/17 notes are retained as history, not instructions to repeat completed merges or request the same old review.

| Delivery | Verified publication / review receipt |
|---|---|
| A rc.5 contracts, models and F.02 environment | [PR #11](https://github.com/shuxiachai/returnops-au/pull/11) merged to main on September 18, 18:59 Sydney time. The later C-F01 test correction is retained. |
| Shared course/rubric requirements | [PR #13](https://github.com/shuxiachai/returnops-au/pull/13) merged at 19:06. Use [docs/19](docs/19-course-assessment-requirements.md) and [docs/11](docs/11-stage1-readiness.md), not old unmerged-branch wording. |
| C models, report contribution and review evidence | [PR #12](https://github.com/shuxiachai/returnops-au/pull/12#event-31380761223) merged at 19:34 as `3024e36c770fbb1d5e272dd2fc43eca3fd68e232`, after A approved synchronized source `79dc6630d37d61f18f42cf037b3f51dee23f72b6`; GitHub records four successful checks. It no longer targets an unmerged A branch. |
| B personal/shared models and team-report candidate | [PR #14](https://github.com/shuxiachai/returnops-au/pull/14) merged at 19:43. The [team report](docs/reports/stage-1-team-report.md) is a merged candidate, not an uploaded final PDF or course receipt. |

A's [final C review](https://github.com/shuxiachai/returnops-au/pull/12#pullrequestreview-5246362189) records an explicitly delegated, AI-assisted technical approval. It preserves the 26 non-README C contribution files, both README notices and inherited main corrections. The Object Diagram is accepted as a **partial conceptual/DTO snapshot**, not a complete runtime schema. Approval/CI do not certify unaided authorship, personal understanding, runtime implementation, joint acceptance or submission. Three existing Markdown hard-break whitespace diagnostics were retained; do not describe every diagnostic as passing.

### C delivery and the remaining evidence

The C artifacts are available directly in this branch: [model chain MC-0.1.3](docs/18-member-c-model-chain.md), [seven editable PUML/SVG pairs](docs/diagrams/member-c), [report contribution MC-RPT-0.4](docs/reports/member-c-stage1-draft.md), and [delivery/AI-use and interview record](stage1/drafts/member-c-contribution-and-interview.md). PR #12 merged MC-PER-0.2; this follow-up explicitly updates that record to **MC-PER-0.3** with the merge receipts and a practical explanation/video/final-delivery checklist. The models, diagrams and report source versions are unchanged.

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

> **F.03 publication reference (2026-09-15; F.01 baseline `3dd1ff637693a826990eee5712cfb239a3c3da7b`):** [F03-C0.1](docs/18-f03-security-component.md) is delivered through [PR #15](https://github.com/shuxiachai/returnops-au/pull/15), tracked by [KAN-34](https://lucastaooo.atlassian.net/browse/KAN-34) in **In Review**. Read the PR body and its [GitHub Actions records](https://github.com/shuxiachai/returnops-au/actions) for the exact current source SHA and corresponding CI results. This notice supersedes earlier local/unpublished F.03 snapshots; preparation receipts and first-publication CI records remain historical evidence for their own versions. The component implements isolated JWT/current-session verification and role/resource authorization with synthetic tests; it is not wired to the health-only API, database or business workflow. Publication does not establish F.01/F.02/F.03 acceptance or C's personal review.

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

## C1 offline grounding candidate — 2026-10-09

[KAN-23](https://lucastaooo.atlassian.net/browse/KAN-23) /
[Issue #58](https://github.com/shuxiachai/returnops-au/issues/58) is C's isolated
retrieval/citation preparation increment (C1.01–C1.05; C Owner, A Reviewer).
It starts from main `e7da2bb481af4e59078eadadb0b198eafbc8ea5a` and does not
depend on merging the separate [C documentation PR #57](https://github.com/shuxiachai/returnops-au/pull/57).
That PR's four checks passed at `737476d`; this is not evidence for the new code.

| Material | Location |
| --- | --- |
| Two frozen C1 port implementations | [grounding.py](experiments/c1_grounding_candidate/grounding.py) |
| Synthetic corpus, public development queries and raw-file manifest | [data](experiments/c1_grounding_candidate/data) |
| JSON-only reproducible pilot / handoff output | [pilot.py](experiments/c1_grounding_candidate/pilot.py) |
| Contract, integrity, conflict and negative tests | [test_grounding.py](experiments/c1_grounding_candidate/tests/test_grounding.py) |
| Existing contract-CI discovery bridge | [test_c1_grounding_preparation.py](tests/contracts/test_c1_grounding_preparation.py) |

This is **offline, synthetic-only, PENDING_HUMAN_REVIEW** preparation, not a
reviewed runtime guidance corpus or legal advice. Synthetic
`REVIEWED_CONSUMER_GUIDANCE` entries exercise that existing wire enum; neither
the name nor a passing hash check certifies a human review. HTTPS/external and
non-synthetic sources are rejected by this candidate loader. No A/B application
module, wire schema, WBS allocation/dependency, packaging or workflow is changed;
the application does not import this experiment. No DB, network, LLM, provider,
case mutation, approval, or execution path is present.

### Reproduce and hand off to A

From a clean source checkout, activate a Python 3.12 virtual environment and
install the existing locked dependencies (see [check setup](tools/checks/README.md)):

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -B -m unittest discover -s experiments/c1_grounding_candidate/tests -p 'test_*.py' -v
python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v
python -B -m experiments.c1_grounding_candidate.pilot
```

The pilot prints JSON to stdout, including raw denominators, per-query misses,
known-conflict preservation, citation errors and data hashes. These are public
development fixtures, not the 30 Gold cases, blind timing data, independent
generalisation evidence, C2 accuracy, or Gate 2/B4 results. Do not tune or
publish sealed Gold labels here. Remote checks and the precise reviewed source
must be read from the implementation PR; local passes do not imply CI success.

For an offline consumer, explicitly read the pinned corpus bytes and construct
`GroundingCandidate.from_bytes(raw, top_k=2, clock=...)`, then call
`retrieve(RetrievalRequest)` or `verify_citations(CitationVerificationRequest)`.
The optional injected clock returns a valid RFC3339 UTC `Z` string; the default
is the current UTC time. The class validates the **named** definitions in the
unchanged [F.01 schemas](contracts/v1/schemas.json), never the permissive registry
root. This source-checkout experiment is intentionally not in the runtime wheel.

### Defined semantics and limits

- Ranking uses the number of distinct matching case-folded word tokens of at
  least two characters, excluding the small stopword set in `grounding.py`.
  It reads passage content only; ties sort by passage ID. Category metadata
  filters candidates; `UNCLEAR` searches all three supported categories and
  `OUT_OF_SCOPE` returns typed `NO_MATCH`. There is no stemming or semantic search.
- `top_k` limits ordinary ranked seeds. Every explicitly registered conflict
  touched by **any** positive match in the relevant category, plus its transitive
  counterparts, remains visible even beyond k (maximum 100 passages). A conflict
  registered only for a different category is not asserted for this category.
  This conservative register is not automatic semantic conflict detection; a
  curator must register relevant categories and C2 assesses materiality. The
  pilot separates strict ranked Recall@k from conflict-expanded return coverage.
- Content hashes cover exact UTF-8 bytes; no trimming, newline replacement or
  Unicode normalisation. Corpus generations are pinned; missing generations
  raise `CORPUS_UNAVAILABLE`, not `NO_MATCH` or fallback to latest. Load corruption,
  malformed requests and invalid clocks raise distinct safe component errors.
  A future runtime adapter must map these to the existing ErrorEnvelope rather
  than treating failure as an empty result or passing review.
- Citation-check precedence is `NOT_FOUND` (passage/document identity),
  `VERSION_MISMATCH`, `HASH_MISMATCH`, `LOCATION_MISMATCH`, then `VALID`.
  Duplicate citation IDs are rejected; every input citation receives exactly
  one check in input order. `source_version: null` is preserved, not repaired.
- The Citation DTO contains no quoted excerpt. C1 verifies the stored passage
  hash and citation metadata; it cannot check a separately invented excerpt.
  `VALID` is **not** claim support, legal correctness, an approval or a statement
  that the citation appeared in a prior retrieval. A must preserve the full
  retrieval result/conflicts, enforce that exact membership and current
  case/input/proposal bindings; C2 independently assesses support and risk.

Formal F.01/corpus acceptance, human review of real source provenance, runtime
integration and the original [C1 completion dependencies](docs/08-delivery-work-packages.md)
remain open. C2 independent model review, C3 images, Gold sealing/evaluation and
personal explanation are separate deliverables; this candidate does not close
them or the whole KAN-23 story. Preparation is AI-assisted; no human review,
personal understanding, contribution percentage or Gate acceptance is invented.

## Review handoff — 2026-09-17

No separate handoff folder is required. Review the existing [C PR #12](https://github.com/shuxiachai/returnops-au/pull/12), using its **latest exact head and checks**, not the older B approval of `c9f205d` or A COMMENT on `32c704f`.

1. Read [C's delivery and AI-use record, MC-PER-0.2](stage1/drafts/member-c-contribution-and-interview.md). Section 1.1 links the actual model/figure/report/review artifacts, §2 and §3 explain their technical basis, §4 distinguishes supplied material from pending shared participation, and §6 provides a factual AI-disclosure draft. These are C-owned, AI-assisted candidate deliverables, not a claim of unaided work or a completed personal explanation. Real personal walkthrough dates/feedback and final confirmation remain unfilled.
2. Review [MC-0.1.3](docs/18-member-c-model-chain.md), the [seven C source/view pairs](docs/diagrams/member-c) and [MC-RPT-0.4](stage1/drafts/member-c-stage1-draft.md). **A:** record the review target SHA, findings or approval, and Object/class consistency disposition in PR #12. If C adds further commits, review the new increment before final approval.
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
| C text for the team report | [MC-RPT-0.4, §10](stage1/drafts/member-c-stage1-draft.md): replacement text for team report §§7.3, 10, 13.4, 14, 16 and 17; A/B integration is still pending |
| Personal contribution / interview record | [MC-PER-0.1.1 worksheet](stage1/drafts/member-c-contribution-and-interview.md): questions and evidence fields, still to be completed by C personally |
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
