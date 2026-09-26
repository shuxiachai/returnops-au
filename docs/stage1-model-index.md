# Stage 1 model, requirements and report navigator

> **Post-submission navigation — 2026-09-26:** The lead confirms that the Stage 1 report, PPT and team-recorded video have been submitted. The current shared report/PPT are nominated submission-content references; a Canvas receipt and exact uploaded bytes were not independently checked. This A-led, AI-assisted index follows main a6c4cbf7bcf7b4df90b2eaf92fdd258ace8a5a72. M-S.03 remains **Owner B / Reviewer A**; personal/shared participation and technical acceptance retain their own evidence. See [Stage 2 entry and dependency handoff](stage2-implementation-readiness.md).

## Reading path and source boundary

| Need | Source |
|---|---|
| Scope, requirements, business rules and traceability | [Project definition](00-project-definition-v1.md); [requirements register](04-requirements-and-backlog.md) |
| Fixed ownership, dependencies and acceptance language | [Frozen allocation](07-frozen-work-allocation.md); [delivery work packages](08-delivery-work-packages.md) |
| Course/report readiness | [Course requirements evidence map](19-course-assessment-requirements.md); [Stage 1 readiness](11-stage1-readiness.md) |
| Shared model sources and static checks | [shared model catalogue](#shared-model-sources); [model-check instructions](../tools/model-checks/README.md) |
| Modular Git report candidate | [Stage 1 team report](reports/stage-1-team-report.md) |
| Canonical shared report | [shared Stage 1 Google Doc](https://docs.google.com/document/d/1xvGO8EA_yZwWj1It3UM7AKDFEoQjsj5eJJXbCz4bcnc) |
| Local-only full-report assembly | `docs/reports/stage1-v0.1/README.md` and `ReturnOps-AU-Stage1-v0.1.md` in the local working tree; neither is a Git-main report source |

The modular repository report is a candidate, not a copy of the canonical Google Doc. The local assembly is report-specific; use the Git model sources below for editable technical artefacts. A green CI or actual Git merge does not establish runtime behaviour, personal explanation, human acceptance, or course submission.

## Requirements and use cases

The authoritative acceptance criteria are in the [project definition](00-project-definition-v1.md#6-functional-requirements), including its [non-functional requirements](00-project-definition-v1.md#7-non-functional-requirements) and [use cases](00-project-definition-v1.md#9-use-cases). The [requirements register](04-requirements-and-backlog.md) is a derived navigation view, not the acceptance authority.

| Group | IDs | Main route |
|---|---|---|
| Intake and assessment | FR-001–FR-005 | [project definition](00-project-definition-v1.md#6-functional-requirements); [derived register](04-requirements-and-backlog.md#mandatory-capabilities); [state model](diagrams/02-state-machine-diagram.md) |
| Grounding, proposal and risk | FR-006–FR-008 | [project definition](00-project-definition-v1.md#6-functional-requirements); [derived register](04-requirements-and-backlog.md#mandatory-capabilities); [C chain](18-member-c-model-chain.md) |
| Founder governance, operations, audit and dashboard | FR-009–FR-012 | [project definition](00-project-definition-v1.md#6-functional-requirements); [derived register](04-requirements-and-backlog.md#mandatory-capabilities); [A chain](12-member-a-model-chain.md) |
| Quality requirements | NFR-001–NFR-009 | [project definition](00-project-definition-v1.md#7-non-functional-requirements); [derived register](04-requirements-and-backlog.md#mandatory-quality-requirements) |
| Use cases | UC-01, UC-01E, UC-02, UC-03, UC-04, UC-05 | [project definition](00-project-definition-v1.md#9-use-cases); [source](diagrams/05-use-case-diagram.md); [derived catalogue](04-requirements-and-backlog.md#laboratory-3-modelling-views) |

## Shared model sources

Each row names an editable Git source. The baseline shared diagrams are Markdown/Mermaid views. The 23 current `.puml` files have paired SVG renderings in their directories; those `.puml` files remain their technical sources of record.

| Concern | Source entries |
|---|---|
| Baseline shared diagrams | [class](diagrams/01-domain-class-diagram.md), [state](diagrams/02-state-machine-diagram.md), [sequence](diagrams/03-sequence-diagram.md), [feature](diagrams/04-feature-diagram.md), [use case](diagrams/05-use-case-diagram.md), [object](diagrams/06-object-diagram.md), [collaboration](diagrams/07-collaboration-diagram.md) |
| B requirements and architecture additions | [URD-1](diagrams/08-user-requirement-diagram.md), [PKG-1 wrapper](diagrams/09-package-diagram.md), [DEP-1 wrapper](diagrams/10-deployment-diagram.md); editable URD source: diagrams/shared/user-requirement-diagram.puml and its paired SVG |
| Shared structure | [composite](13-shared-composite-structure.md), [package/deployment](15-package-deployment-models.md), and `diagrams/shared/{governed-case-composite,governed-analysis-composite,governed-execution-composite,object-diagram,package-dependencies,use-case-diagram,collaboration-diagram,deployment-topology}.{puml,svg}` |
| A governed execution | [A chain](12-member-a-model-chain.md) and `diagrams/member-a/{governed-execution-activity,exact-scope-sequence,recovery-notification-sequence,operation-attempt-state}.{puml,svg}` |
| B intake | [B chain](19-member-b-model-chain.md) and `diagrams/member-b/{member-b-activity,member-b-sequence,member-b-state}.{puml,svg}` |
| C grounding/risk and report views | [C chain](18-member-c-model-chain.md) and `diagrams/member-c/{member-c-activity,member-c-sequence,member-c-state,member-c-activity-report,member-c-sequence-report,member-c-state-report,member-c-object-conflict}.{puml,svg}` |

M-S.03 is B's later integration of requirement classification, Feature/Use-case material, and the full-model index. Its [fixed work-package row](08-delivery-work-packages.md) sets **B Owner / A Reviewer**. The [C chain](18-member-c-model-chain.md) identifies C's classification/trace table as supplied input; it neither completes M-S.03 nor changes B's responsibility.

## Report navigation and active figures

The local-only full-report assembly is the previously verified 21 September export. The cloud report was subsequently clarified and the user nominated its current version as a submission-content reference. A separate 26 September reference archive retains a 53-page native PDF and the nine-slide PPT without overwriting the earlier local assembly. It is not an independently retrieved Canvas submission package, and this archival export was not newly visually reviewed.

B's [VID-1 script](20-stage1-video-script.md), C's unmerged PR20 binary snapshot and the later shared Drive versions are distinct preparation artifacts. Their dates and speaking text differ. The user now confirms submission and manages video work; this index does not schedule recording or require rewriting submitted materials.

The Git [team-report candidate](reports/stage-1-team-report.md) remains separate from the shared Google Doc. Submission, merged source, personal contribution, technical acceptance and runtime implementation are separate facts. Preserve original author/source attribution, and do not infer acceptance or contribution percentages from Git publication.


## Review and integration handoff

1. B reviews this navigation against M-S.03 and records any accepted integration in B-owned work; this draft does not claim M-S.03 is done.
2. A uses the fixed allocation and exact Git/PR history when preparing a repository candidate; only actual merged commits are Git-main evidence.
3. Preserve the user-confirmed submission status. Record remaining model review, actual contribution and environment/runtime acceptance separately; Stage 1 submission does not silently accept F.01 or F.03.