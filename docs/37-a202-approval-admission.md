# A2.02: private retained-source approval admission

This first A2.02 slice checks a future simulated CREATE_RETURN using actual
persisted source proof. It does not execute a command or consume execution work.
Owner: A Jingbo Chai; designated human reviewer: C Yuwei Tao. Original S: A2.01.
The lead approved one bounded start exception on 13 October 2026; original
personal, predecessor, joint and whole-package acceptance remain separate.

[Technical Issue #71](https://github.com/shuxiachai/returnops-au/issues/71)
maps to the verified [KAN-15 story](https://lucastaooo.atlassian.net/browse/KAN-15).
Jira status is unchanged. Frozen requirements: FR-009/010/011/012;
NFR-002/003/004/006/008; UC-03/04/05. See
[work packages](08-delivery-work-packages.md) and
[allocation](07-frozen-work-allocation.md).

## Starting evidence

Base main `7fc30856b8053dca6c297f7a799204a3b66f70fe`, tree
`52cc2b7d2dccbd0a24a6689f44a9a9e8d00bd458`, was adopted by
[PR #65](https://github.com/shuxiachai/returnops-au/pull/65).
Its [new-main CI](https://github.com/shuxiachai/returnops-au/actions/runs/38331528059)
passed 2262 core regressions, including 1495 lifecycle cases, on PG17.11/exact
`0009_preview_approval`. This is baseline evidence, not this increment's tests.

[Private APPROVE](35-a201-preview-approval.md) saves an exact scope and a
specialized unclaimed execution intent. Historical approval alone does not
establish current authority or permission to dispatch. Original approval
proof/replay and generic EXECUTION rejection stay intact.
[Manual handling](36-a201-pass-manual.md) still stops at pending notification.

## Proof and identity

The private caller receives case ID, expected case version, execution work ID,
original approval key and candidate command. Saved approval facts are
reconstructed server-side; customer-built scope or a synthetic trusted flag
cannot replace actual source proof.

The retained chain includes approval/proposal/review/input/order/preview,
original work/claim, audit/events/bindings, acceptance and DecisionReceipt.
Immutable original approval acceptance and separately current review/input/order
proof are both required. The original approval request key differs from the
derived stable execution work key.

Current session/case checks must establish the original Founder. The current
EXECUTION grant for the original approval component is checked independently;
PREVIEW permission is not execution authority. Specialized execution work must
be PENDING, epoch zero and entirely unclaimed. The complete saved ordered
two-command mock scope is validated, with only its first CREATE_RETURN
candidate supported here.

Restricted canonical ASCII JSON bytes and existing parameter/scope fingerprints
remain exact. Unsupported floats and boolean/integer substitutions cannot be
accepted through normalization. No migration, grant backfill, policy enum or
fingerprint algorithm is introduced.

## Finality and zero writes

The existing UnitOfWork exclusive fence covers the prototype store.
Its `write=True` mode selects the existing fence/final-check protocol; it
does not authorize business mutations or introduce a new per-case lock.

Some legacy proof reads lazily insert encoding metadata. A SELECT-only proof
facade prevents those trusted-helper writes and fails closed when source
encoding is unavailable. This is not database-level hard isolation. Tests
compare physical business tables, including metadata, around the guard call.

After expensive reads, current input/order, identity, independent EXECUTION
grant, relevant raw source leaves/availability and the state seal are checked
again. Trusted session registry bounds remain bound to the verified original
Actor. A final real session check is the last database I/O; aware UTC time is
then sampled once to check session and approval/preview deadlines together.
This guard adds strict session freshness to F.03's configurable clock leeway;
the existing authentication policy and historical approval replay are unchanged.
CHECKED is returned only after confirmed transaction completion and describes
the final check before commit, without promising continued validity during a
slow commit or later response.

Frozen CHECKED/DENIED/UNKNOWN results contain no receipt, scope or permission
token. CHECKED describes only this completed check's time and cannot serve as
cacheable execution authority. UNKNOWN stays unknown, grants no admission and
allows no automatic command retry or replacement key. A later dispatcher needs
its own current checks.

Any earlier OPERATION history or effects reference prevents this first-operation
admission, including when approval/provider/key changes. FAILED/BLOCKED retries
are later work; UNKNOWN/RECONCILING remains uncertain. GENERATE_LABEL requires
actual return-result proof and is outside this slice.

## Validation and delivery

New disposable-cloud PostgreSQL acceptance covers:

- Full persisted PASS/PASS_WITH_WARNING positives and zero business writes.
- Real identity and independent EXECUTION authority.
- Complete original receipts/current source and missing encoding.
- Exact scope, version, expiry, key and retention negatives.
- Pending/unclaimed specialized identity and original rejection/replay.
- Prior operation/effect history and UNKNOWN preservation.
- Late source/authority/time changes and uncertain completion.
- Observed two-backend fence serialization and installed private calls outside
  checkout.

The existing complete regression remains required. The earlier standalone
16-method synthetic guard draft is offline preparation, not actual-source PG
proof. Consult this increment's exact-source PR/cloud CI for its validation;
this document makes no new CI-result claim.

After independent source review and exact version freezing, normal push,
Draft PR and disposable cloud PG/container CI are authorized. Ready/merge,
execution consumption, provider effects, OperationAttempt, notification,
public producer and local migration are separate work. Local DB/Docker remains
paused.
