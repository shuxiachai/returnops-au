# A notification fixture disposition — 21 September 2026

Status: A-led / AI-assisted fixture correction candidate.
The associated PR records the exact published SHA and CI results. This is
fixture evidence, not runtime notification delivery or F.01 acceptance.

- Finding: [C-F01-20260920-01 in Issue #10](https://github.com/shuxiachai/returnops-au/issues/10#issuecomment-5748991365),
  reviewed by C against A `3dd1ff637693a826990eee5712cfb239a3c3da7b`.
- Source review: [C's exact published record](https://github.com/shuxiachai/returnops-au/blob/a3679456e1df78d6190e03933f2079d29206ceb7/docs/reviews/member-c-f01-review-20260920.md).
- Patch base: actual main `da1a09fe7704bdb2fd2f989a44ab62bd7f089a41`.
- Delivery mapping: [KAN-32](https://lucastaooo.atlassian.net/browse/KAN-32) / F.01,
  Owner A, designated Reviewer C; FR-010/011/012, UC-04/05 and
  [the notification/recovery and customer-history contract](../09-interface-contract-v1.md).

The `SENT` notification and already-sent customer history contained internal
delivery-failure and resend instructions. The same wording also appeared in
the initial failed delivery, pending retry and Founder history. All five
positive snapshots now share stable customer content: the simulated return
and free label were recorded; the customer can review those details and
contact the Founder for help. The example explicitly requires no real parcel.
The related negative history fixture receives the same customer wording while
retaining its deliberately forbidden internal `error` field.

Only twelve `message` / `next_steps[0]` strings in six examples change.
The `RETURN_CREATED` saved outcome, delivery states, attempt counts, IDs,
timestamps and internal transport error are unchanged. Schema/OpenAPI,
manual/reject precedence, authorization, idempotency, models and fixed WBS
are unchanged. C's branches and technical files are not modified.

The [two new fixture regressions](../../tests/contracts/test_notification_fixtures.py)
check stable customer content across the five positive snapshots and reject
the reported operator wording. Four injected mutations confirm that the old
message or next step remains schema-valid but fails the semantic oracle in
both `NotificationRecord` and `CustomerOutcomeMessage`. This limited oracle
does not establish that arbitrary generated customer text is safe.

Validation used the existing Python 3.12.9 environment, without installation:

- Before the fix, the focused two-test run exited 1 as intended: five snapshot
  subtests exposed the reported text; the mutation-detection test passed.
- After the fix, `python -B -m unittest discover -s tests/contracts -p 'test_*.py' -v`
  passed all 60 tests (the original 58 plus these two), exit 0.
- A structural comparison with the base verified exactly the twelve intended
  text changes; every other fixture value is identical.
- `python -B tools/model-checks/check.py --baseline-ref da1a09fe7704bdb2fd2f989a44ab62bd7f089a41`
  passed 6/6 groups, including all 89 frozen WBS rows and 22 SVG/source pairs.
- `git diff --check` passed; new test and disposition files also have no trailing
  whitespace. No API, database, Docker, provider or runtime guard tests ran.

Two initial shell launches and one later disposition-update launch failed
before execution because of the existing Windows sandbox-helper ACL error. The same scoped commands then ran through
the explicit approval path; no ACL or persistent configuration was changed.
Failure accounting retains one expected pre-fix reproduction command and zero
failed fix attempts; the three launcher failures are separate environment events.

Next: record C's designated follow-up review of the exact correction revision
and A/B/C joint F.01 acceptance when supported by actual evidence. B's existing
frontend confirmation remains; C's earlier feedback is not a personal signature
or joint acceptance. Issue #10, F.01 status, PR #7/#17 and course submission
remain separate actions.
