# PR #8 model alignment and contribution disposition — 2026-09-14

This is an A-led, AI-assisted conflict-resolution record for
[PR #8](https://github.com/shuxiachai/returnops-au/pull/8), tracked by its existing
KAN-12 reference. It preserves B's original commits and their authorship; it is
not B's personal revision/signature, joint model acceptance, or completion of
B's remaining M-B work packages. Nine feature owners and all 89 WBS
ID/Owner/Reviewer/S/F dependencies remain unchanged.

## Exact sources and integration boundary

- B's original [three-agent rebaseline commit](https://github.com/shuxiachai/returnops-au/commit/cbba595e69ab5e7100f3f023ad15497d4774dc60)
  and [class-model commit](https://github.com/shuxiachai/returnops-au/commit/e32d5e7c461775610dee2ca6480f5343ad3b0f6b)
  are retained as ancestors without rewriting or changing their author metadata.
- The integration input is [PR #11 source](https://github.com/shuxiachai/returnops-au/commit/3dd1ff637693a826990eee5712cfb239a3c3da7b).
  Its four affected model files are byte-identical Git blobs to rc.5
  `64582a3007fea0fa3d1b1c3c212168b96af6b607`.
- The source branch receives a normal merge whose first parent is original B
  `e32d5e7...` and second parent is `3dd1ff6...`. The resolved tree equals the
  reviewed integration input except for this disposition record. Selecting the
  newer model text here does not claim B authored its later additions.
- PR #8 depends on PR #11's contract/model/environment candidate. The intended
  review target is `fix/10-kan-32-contract-review`, with main publication still
  separate. Neither PR is merged to main by this alignment. Check the actual
  target again after PR #11 is resolved before any later retargeting.
- C's PR #12 at `68e5e4b6569508c1988fa099eabbec8222ea5c0b` remains a separate
  candidate; it is not pulled into this merge.

## Contribution disposition

All line references below are to the exact Git source specified, not a later
working-tree line number. Source authorship, adapted integration by A, and
personal understanding/acceptance are separate facts.

| B contribution | Current representation and disposition |
| --- | --- |
| Three agents, deterministic OperationsService, replaceable interfaces | Preserved and adapted in [rc.5 class model lines 390–484](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L390). Retain role-specific DTOs and separate WorkflowOrchestrator/Domain authority rather than a universal Agent input/output signature. Existing B attribution at lines 10–15 remains. |
| Dashboard and separate read-only order / governed effect providers | Preserved in [system design lines 20–26](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/02-system-design.md#L20) and the [sequence provenance note](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/03-sequence-diagram.md#L10). Later exact-scope and recovery behavior is A's adapted integration, not original B work. |
| Case / IntakeSession / statements relation | Structural relation retained at [class-model lines 290–293](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L290). This does not accept B's separate lifecycle detail. |
| Review / Proposal / Finding relation | Retained with Finding composition owned by the review at [lines 309–311](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L309); explicitly an adaptation. |
| Command subtypes / Command-to-Attempt relation | Retained at [lines 321–324](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L321), with the later exact-scope, seven-state and recovery constraints. |
| PolicyDocument subclass proposal | **Subclass expression not adopted.** B [lines 111–132 and 282–283](https://github.com/shuxiachai/returnops-au/blob/e32d5e7c461775610dee2ca6480f5343ad3b0f6b/docs/diagrams/01-domain-class-diagram.md#L111) proposed StorePolicyDocument / ApprovedGuidanceDocument. rc.5 [lines 103–110](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L103) retains source-category semantics via PolicyDocument.source_type. Do not claim these structures are identical. A future subclass change requires an explicit design decision and must preserve wire source-type/provenance constraints. |
| Three-value IntakeStatus / initial-only session proposal | **Lifecycle detail not adopted.** B [lines 443 and 462–487](https://github.com/shuxiachai/returnops-au/blob/e32d5e7c461775610dee2ca6480f5343ad3b0f6b/docs/diagrams/01-domain-class-diagram.md#L443) remains an attributed historical candidate. rc.5 [lines 53–58](https://github.com/shuxiachai/returnops-au/blob/64582a3007fea0fa3d1b1c3c212168b96af6b607/docs/diagrams/01-domain-class-diagram.md#L53) and its lifecycle guidance leave personal refinement open. Later clarification is not closed, and minimum-information presence alone is not the full admission guard. |

## Four-file conflict resolution

1. [Project charter](../01-project-charter.md): retain the reviewed rc.5 text,
   including the three roles and human/deterministic-service boundaries.
2. [System design](../02-system-design.md): retain rc.5 architecture and existing
   source attribution. Do not restore multi-component direct database writes,
   Founder-to-notification shortcuts or Domain as a replacement for all orchestration.
3. [Class model](../diagrams/01-domain-class-diagram.md): retain current DTOs,
   methods, authority and recovery constraints; use the explicit dispositions
   above for B's adjusted or non-adopted proposals.
4. [Sequence model](../diagrams/03-sequence-diagram.md): retain question-set and
   version binding, ActionPreview, unknown-effect queries and independent
   notification recovery. B's old immediate retry after ambiguous timeout is
   not restored. Clarification continues through the API/Domain boundary.

No Mermaid or PlantUML model is re-authored by this resolution; the four files
match their reviewed integration-input blobs. This is a history-preserving
alignment with explicit provenance, not a claim that every original B proposal
was accepted or that all current model content is B-authored.

## Verification and remaining acceptance

Traceability remains FR-001–012 / NFR-001–009 through the shared Class/Sequence
and architecture models, docs/09 contracts, and the fixed docs/08 work packages.
The alignment requires a clean index with no unmerged paths, original B commits
as ancestors, exact four-file equality, an integration-input diff containing
only this record, unchanged WBS fields, offline contract/model checks and
independent review of the final candidate. The exact resulting source commit
and its own CI results are recorded in PR #8 after publication.

Existing F.01/F.02 and personal/shared model acceptance gates remain open. This
work introduces no runtime, wire-schema, database or dependency change. The
local F.03 candidate and full shared report are excluded. No Jira completion,
Google Doc modification, member signature or course submission is inferred.
