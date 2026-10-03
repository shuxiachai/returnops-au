# A1.03 independent denial-audit composition verification

Delivery: [Issue33](https://github.com/shuxiachai/returnops-au/issues/33), historical
[KAN-14](https://lucastaooo.atlassian.net/browse/KAN-14) mapping. Owner A Jingbo Chai;
designated human Reviewer C Yuwei Tao. Trace: A1.03, FR-001/009/011,
NFR-001/003/004/006, the Domain/state model and governed-case composite audit
boundary. See [the adopted lifecycle component](25-a103-lifecycle-guards.md).

This slice adds only a private caller and PostgreSQL tests under
`tests/lifecycle`. Production services, workers, schemas, migrations, permissions,
capability purposes and public history kinds remain unchanged. No application
imports or registers the caller. Saved future proposal material is explicitly
synthetic; no real proposal, Risk PASS, Founder decision, approval, provider,
notification sender or LLM is exercised.

The controlled caller owns a trusted case/owner/store/component/existing-purpose
context, separate from a rejected DTO. A definite guard rejection first exits the
original poisoned transaction. Only after its connection is closed does a new
write UoW acquire the existing exclusive fence, lock and read the current case,
verify availability and original owner/store scope, and resolve the current
service grant and owner. It reads optional lifecycle availability without creating
a sidecar. It never requires the rejected work claim to become valid and never
creates a grant or borrows an `AUDIT` capability.

The new transaction appends fixed internal `LIFECYCLE_GUARD_DENIED` audit metadata:
current authorized SERVICE actor, server-derived correlation/time, empty object
and history references, and a payload hash of only existing purpose plus a finite
safe code. The audit API stores that hash, not a plaintext reason payload. The
caller rechecks current resource, owner, grant and the audit transaction's grant
revision immediately before commit. It reports `RECORDED` only after acknowledged
commit; unavailable authority/resource or a definite audit failure reports
`NOT_RECORDED`. The original business operation remains denied in either case.

Original acceptance commit uncertainty is `UNKNOWN`, never a denial audit or an
automatic retry. Tests retain the original event identity and independently read
whether the fault-injected transaction committed. Only the committed case with
that exact original receipt is separately checked through the existing receipt
recovery semantics, without invoking its producer again. Audit commit uncertainty
is separately `UNKNOWN` in both actual-commit and actual-rollback cases; there is
no new-ID retry or denial-audit dedup/recovery claim.

Tests use real isolated PostgreSQL17 schemas and all current migrations. They
compare every physical table before/after, including all six lifecycle sidecars,
source/history contents, intake/investigation work and acceptance records. A legal
denial changes only audit rows and case audit sequence/head; rejected audit writes
roll back completely. Between-transaction revocation/scope fixtures are committed
before their comparison snapshot, so fixture changes are not attributed to the
caller. Cases also cover immediate illegal state, stale version, real superseded
claim, delayed commit rejection, poison after a caught error, present-authority
changes, SQL/callback failure, both unknown-commit modes, fake actor/sensitive
exception material, missing case and a case without a lifecycle-state row.

Reproduce with an explicitly configured disposable project PostgreSQL17 database
and the locked Python dependencies:

```text
python -B -m pytest tests/lifecycle/test_denial_audit_postgresql.py -q
python -B -m pytest tests/lifecycle -q
python -B tools/checks/run.py offline --baseline-ref <verified-main>
```

Exact source hashes, execution counts, raw logs, warnings, failures and environment
boundaries belong to the delivery evidence. Collection is not execution, and the
previous adopted main's results are not new candidate tests. This private
component-combination proof does not establish future runtime producer wiring,
whole A1.03 or predecessor acceptance, Owner/C/member joint acceptance, Gate1,
or permission to begin A1.05 runtime integration. Fixed WBS ownership and S/F
requirements still apply.
