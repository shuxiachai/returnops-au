# A1.01 intake-preparation candidate — 2026-09-26

This is a deliberately isolated preparation candidate under
`experiments/a1_intake_candidate/`. It does not implement A1.01 and must not
be integrated before the documented F.01 alignment dependency is accepted.

Recorded delivery mapping: A1.01 is under KAN-14, as recorded in
`docs/11-stage1-readiness.md` and
`docs/reviews/a-preimplementation-readiness-20260907.md`. KAN-32 identifies the
F.01 prerequisite, not this candidate owner. This cites existing repository
mapping; no fresh Jira status check or Jira change was performed here.

It validates `CreateCaseRequest` and projects a nonpersistent `ORIGINAL`
`CustomerStatement` using the frozen named `$defs` in
`contracts/v1/schemas.json` with `jsonschema.FormatChecker`. The only
supplementary domain rule is the documented rejection of whitespace-only
`original_message`; it is separate from schema validity and preserves nonempty
message bytes unchanged.

The candidate has no production imports or changes to domain models, schemas,
OpenAPI, locks, CI workflow configuration, WBS, API, database, authorization, provider, LLM, time,
randomness, or case state. Caller-provided IDs are validated as data and do not
authorize a caller. It does not claim ReturnCase, parcels, multiline items,
idempotency, or state behavior.

The initial review identified a privacy defect: jsonschema error messages and
an explicit exception chain exposed invalid request values. The correction
retains strict frozen-schema validation while reporting only allowlisted field
and validator names. The replacement exception is raised outside the validation
handler without a raw cause or context. Focused regressions inspect both the
exception text and ordinary formatted traceback for original text, unknown
property names and values, invalid IDs, timestamps, and enum values.

The initial focused-test log and malformed hash display are preserved in local
review evidence; the earlier claimed contract pass had no saved execution log.
Fresh focused and frozen-contract test logs, exit codes, source hashes, and
changed-path checks are required for this corrected candidate. These local
checks do not establish F.01 acceptance or authorize production integration.

A test-only discovery bridge in `tests/contracts/test_a1_intake_preparation.py`
re-exports the existing eight-test `IntakePreparationTests` class. The unchanged
offline CI contract-discovery command therefore selects 58 existing contract
tests plus eight candidate tests (66 total on main `a6c4cbf`). The separate
pre-bridge 58-test run remains historical evidence; the combined run has its own
complete stdout, stderr, exit code, and source hashes. This is test selection,
not a production import or a claim that a remote CI run has already occurred.
