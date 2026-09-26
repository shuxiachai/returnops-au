# A1 initial-record storage groundwork

This candidate starts bounded A1.01/A1.02 work from actual main
`08292520c54be75b162f8e69c8ba8798aff801ea`, following the lead's 26 September
authorization. It does not complete either work package or record B/C or joint
acceptance. The four earlier candidates have been merged; the batch exception
does not authorize automatic merging of this new candidate.

`returnops_domain` is an installable internal package. Frozen scalar records hold
initial case metadata and the ORIGINAL statement's historical acceptance facts.
`StatementContent` separately holds raw text, requested outcome and the optional
original order reference. Identifiers, owner, store, versions and aware datetimes
must all be supplied explicitly by a trusted caller. Initial status is SUBMITTED
and all initial versions are one. No identifiers, clock or authority are inferred.

Migration `0002_initial_records` follows the unchanged environment baseline. It
adds `case_records`, `original_statement_records` and
`original_statement_contents`; readiness requires exactly that migration head.
IDs, initial versions/status/kind, duplicate original statements, outcomes and
foreign-key relationships have database constraints. Historical accepted versions
are not foreign keys to mutable current case versions. Exact codepoint lengths
are validated by the domain; database byte limits add a coarse secondary bound.
No transition is implemented, and extending these initial-only constraints needs
a later reviewed migration. Automatic downgrade refuses destructive data removal.
The existing disposable `returnops_f02` database guard remains in force.

The private content codec v1 is Python UTF-8 with `surrogatepass` in both
directions, stored as BYTEA. It preserves NUL, line endings, whitespace, combining
characters and Python surrogate codepoints exactly. It is not designated as a
standard UTF-8 wire codec, request fingerprint or audit hash encoding. Pydantic
is used for scalar validation; a Python string validator preserves the frozen
JSON schema's codepoint range instead of silently narrowing it. An absent order
reference stays `None`; empty reference and absent reference are distinct.

The internal time boundary accepts aware Python datetimes and normalizes them to
UTC at Python/PostgreSQL microsecond precision. It is not a public RFC3339 parser
and makes no promise to accept arbitrary fractional precision from a wire string.
The wire schema and OpenAPI remain unchanged and are independent test oracles.

`InitialRecordUnitOfWork` opens one connection and transaction. The repository
only inserts or loads an initial bundle. Explicit `commit()` is required; leaving
without it or raising before commit rolls back all three inserts. Any failed
repository operation prevents commit even when caught. A duplicate is a conflict,
not a successful replay. A failed commit acknowledgement returns
`CommitOutcomeUnknown`: cleanup does not establish whether the server committed,
and the caller must not automatically retry creation. There is no retry loop.

These primitives accept trusted internal inputs only. They do not implement a
customer create service, HTTP routes, authentication, authorization rechecks,
idempotency/fingerprints, evidence binding, history cursors, audit, retention or
deletion policy, state transitions, LLM or provider calls. They do not accept a
CreateCaseRequest and cannot silently drop its evidence IDs. The production API
still exposes health routes only. Missing/corrupt content is a storage failure,
never fabricated empty content or an invented tombstone/HTTP response.

Personal content and its enclosing field are omitted from ordinary repr/str.
Validation and SQL exceptions use fixed safe messages with no retained original
cause/context. Dataclass field extraction is for persistence, not safe logging.
UoW requires SQL parameter hiding and disabled engine/pool echo. Callers must not
log the explicit content or attach arbitrary SQL logging listeners.

Validation commands (from an environment with the existing locked dependencies):

```text
python -B -m pytest tests/storage/test_records.py tests/environment -m "not database" -q
python -B tools/checks/check-installed.py
python -B tools/checks/run.py environment
```

The environment command migrates the explicit disposable database, runs existing
API/environment checks, then runs the storage suite. Real storage acceptance uses
PostgreSQL 17, independent connections, repeat migration with committed data,
database constraints, rollback before later inserts, duplicate conflicts,
content round-trips and before/after-server-commit acknowledgement failures.
The GitHub workflow also builds the runtime image and imports the installed
packages with cwd `/tmp`. Local Docker startup is currently blocked by a Docker
Desktop inference-manager socket error; local pure tests are not represented as
PostgreSQL or container tests. Candidate CI results remain the evidence for those
checks, and the independent review must name the exact tested tree.
