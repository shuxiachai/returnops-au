# A1.01 nonpersistent intake-preparation candidate

This isolated experiment exercises two pure functions against the frozen
`contracts/v1/schemas.json` named `$defs`. It is preparation only and has no
production import, API route, persistence, authorization, case creation,
provider, LLM, clock, random value, or state transition.

`validate_create_case_request` returns a deep-copied request after validation.
It applies only the documented absent-field defaults: `requested_outcome` to
`UNSPECIFIED`, and `evidence_ids` to `[]`. Explicit `null`, unknown fields, and
other schema violations remain invalid. The documented whitespace-only message
rule is deliberately a supplementary domain rule, evaluated without trimming
or rewriting the preserved `original_message`.

`project_original_statement` receives a request plus caller-supplied
`statement_id` and `submitted_at`, validates both its input and its generated
`CustomerStatement`, and returns a deep-copied `ORIGINAL` statement. IDs are
validated as contract data only; they carry no authorization meaning.

Validation errors expose only the fixed contract name, an allowlisted field
name (or `object`), and an allowlisted validator rule (or `schema`). Raw values,
unknown property names, schema representations, and the underlying validation
exception are excluded from the exception message and ordinary traceback.

Activate the existing project Python 3.12 environment first, then run the
focused tests from the repository root (the root of this checkout):

```powershell
python -B -m unittest discover -s experiments/a1_intake_candidate/tests -p 'test_*.py' -v
```

`python` must resolve to that activated environment with the project's locked
dependencies already installed. An isolated worktree can reuse the existing
environment by invoking its actual absolute Python path instead; no relative
virtual-environment location is assumed here.

The existing offline CI job discovers `tests/contracts`. The test-only bridge
`tests/contracts/test_a1_intake_preparation.py` re-exports the same
`IntakePreparationTests`, so that job also selects these eight candidate tests
without a workflow or production-import change. Run the same discovery locally:

```powershell
python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v
```

On this candidate based on main `a6c4cbf`, that discovery selects 66 tests:
58 existing contract tests plus the eight intake-preparation tests. The earlier
separate 58-test log predates the bridge; it is not evidence that CI selected
these candidate tests. Remote CI evidence still requires a published revision.
