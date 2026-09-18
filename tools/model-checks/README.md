# Reproducible static document and model checks

These tools replace the temporary check scripts with reviewable repository
sources. They are development tools for FR-011/012, NFR-001/006/007 and the
existing M-A/M-S model chains. They do not implement a product feature, change
ownership, approve a model, or install a GitHub Actions workflow.

## Run from the repository root

Python 3.10+ and Git are sufficient for the main checks; no Python packages,
virtual environment, Java, renderer or running application are needed:

```powershell
python -B tools/model-checks/check.py
python -B -m unittest discover -s tools/model-checks -p 'test_*.py' -v
```

The root is derived from the script location, so the script also works from
another current directory. Use `--root PATH` to check another checkout. Exit 0
means the listed static groups passed; a failed group exits 1 and reports the
reason. Other independent groups still run after a failure.

WBS ID, Owner, Reviewer, S and F are compared with `HEAD` by default. To compare
with an agreed revision without fetching or changing refs:

```powershell
python -B tools/model-checks/check.py --baseline-ref main
```

The named ref must already exist locally. In a source archive without Git,
`--skip-baseline` explicitly skips this comparison; dependency validation still
runs and the output discloses the skip. No persistent Git configuration changes
are made; `safe.directory` is scoped to the single read-only Git command.

## What Python checks

- Markdown in root files, `docs/`, `contracts/` and this tool directory: existing
  local inline/image-link targets and reference-definition targets. Code
  examples are excluded. Heading anchors, external URLs and application/file
  URIs are not checked. This is a focused parser, not complete CommonMark
  validation; escaped/nested label syntax may need manual inspection.
- FR/NFR/BR and use-case IDs in the derived indexes match the current
  [project definition](../../docs/00-project-definition-v1.md). Counts are
  derived, not fixed to a previous report.
- [WBS](../../docs/08-delivery-work-packages.md): unique rows, non-author
  reviewers, existing dependencies, no combined S/F cycle, and unchanged
  ID/Owner/Reviewer/S/F against the chosen Git revision. Acceptance prose and
  titles are not frozen by this comparison.
- Every current `.puml` under `docs/diagrams` has a readable SVG and matching
  embedded PlantUML source. Model counts are discovered dynamically.
- [Member A](../../docs/12-member-a-model-chain.md): scenario IDs are unique and
  sequential, referenced activity IDs exist, and the named OperationAttempt
  states and the project definition's `OperationStatus` row match the current
  contract enum. Adding MA-T16 or further scenarios
  does not require changing an expected count in this tool.
- [Composite structure](../../docs/13-shared-composite-structure.md): the
  `*-composite.puml` views only (Package/Deployment use the common SVG check);
  supported component/port/connector notation has declared endpoints, the
  documented D/A scope and P/R pairing, complete unique connector registry,
  sequential scenarios, and the five existing Domain/store, Domain/audit,
  Orchestrator/Risk, Operations/effect and Operations/notification adjacency
  restrictions. Part/port aliases for these deliberate project checks are
  named in the tool; a reviewed rename must update them too.

The CS reader supports the project's explicit `component "..." as Alias { }`,
`port`/`portin`/`portout`, local `(P)/(R)` annotations, and `-- : Dxx/Axx`
conventions. Spaces/tabs before a connector and optional spaces around `--`
or `:` do not change its checks. Suspected connectors with unsupported arrows,
decorations, missing registry IDs or quoted endpoints fail explicitly instead
of being ignored. Whole-line apostrophe comments and `legend`/`endlegend` prose
are excluded from connection parsing. It is not a general PlantUML or UML
metamodel parser. It checks
local connection shape, not full interface compatibility, behavior or security.

These connection regressions support FR-009/010/011 and NFR-002/006/007 through
the existing CS-01 Domain/store boundary and MA OperationAttempt state model;
they do not prove that runtime authorization or effect guards are implemented.

## SVG/source correspondence without mtime

Git checkout and file copies can change mtimes independently of content. The
checker instead decodes the SVG's `plantuml-src` metadata (or legacy `SRC`
comment), normalizes line endings and compares it with the current PUML body.
PlantUML omits the outer `@startuml`/`@enduml` lines in that metadata. No
timestamps are compared and neither source nor SVG is rewritten.

Missing metadata or changed source fails with a re-render instruction. The
current self-contained diagrams are supported; include/macro expansion requiring
an external file is rejected rather than silently called current. Embedded
source correspondence is not a cryptographic attestation that a renderer ran,
and it does not prove that visible SVG geometry matches the source. After
rendering, inspect the actual figures for overlap, cropping and legibility.
The existing model documents contain their local PlantUML rendering commands.

## Optional Mermaid parser

Use Node.js 20+ and npm. The committed `package-lock.json` locks the full
dependency tree; `package.json` also pins the two direct parser dependencies.
This lock belongs only to this development tool, not the future application:

```powershell
npm ci --prefix tools/model-checks --ignore-scripts --no-audit --no-fund
node tools/model-checks/check-mermaid.mjs
```

Installation may need registry access on first use. Parsing afterward is local;
no model is uploaded and no browser or external URL is opened. `node_modules`
is covered by the repository's existing ignore rule and must not be committed.
No installation is performed by either check script.

The optional parser discovers Mermaid fences in the same document directories;
the number of files and diagrams is not hard-coded. It checks grammar only,
not rendering, diagram layout or UML meanings. Exact direct dependency
versions are checked before parsing.

For an already-installed matching dependency tree, an explicit offline override
is available: `node tools/model-checks/check-mermaid.mjs --dependencies PATH`.
`PATH` must contain the matching `package.json` and `node_modules`; this option
does not install or copy packages. Prefer the committed lock and `npm ci` for a
fresh teammate reproduction.

## Interpreting a result

Record the checked Git revision plus working-tree changes, commands and actual
output. Counts describe the files present at that run, not course completion.
Do not present a pass as a render, UML semantic proof, HTTP/provider test,
CI run, C's review, B/C contribution, or tutor acceptance. During concurrent
editing, an SVG/source mismatch may be a real in-progress update: let its author
finish rendering and rerun, without changing the model to satisfy this tool.

The checker regression tests use temporary synthetic inputs to verify that a
changed SVG source, invalid connector, WBS cycle and missing reference fail,
while timestamps, normal line endings and added scenario rows do not create
false failures. They are tests of this tool, not product safety tests.
An indented extra CS connection must fail both when it is absent from the
registry and when it is registered but violates the named Domain/store boundary.
The vocabulary regression also rejects the stale `RUNNING` status in place of
the contract's `EXECUTING`.
