# A1.03 current review and acceptance sheet

Prepared 5 October 2026. Owner **A / Jingbo Chai**; designated non-author human
Reviewer **C / Yuwei Tao**. This is the current readable acceptance sheet, using
the original four A1.03 criteria in [the frozen WBS](../08-delivery-work-packages.md).
It is a review proposal, not a signature, a Jira status change or whole acceptance.
Earlier dated technical packets remain evidence; they are not competing decisions.

## Exact version and evidence

| Layer | Exact reference | Meaning |
|---|---|---|
| Current inspected baseline | `de8c4e423aba75bf69018ac0da55a7d34b0c5bdb`, tree `47332ad64650d87cdf3e367a4efb77e3a4fbc897` | Current main observed for this preparation |
| Reviewed A1.03 source | `c0d9d6a0f0cc7005047ae8b7b315e98967a7ebd6`, tree `461fe0029f2dc3c0dd5b595837ab754f7b431e8a` | [PR34](https://github.com/shuxiachai/returnops-au/pull/34) private denial-audit verification, on the already adopted lifecycle component |
| Actual component adoption | main `6b45b7141126292a06ed783f5e4a3adcf9955210` | Limited PR34 merge authorization; does not sign this sheet |
| Component execution | [main CI37114940915](https://github.com/shuxiachai/returnops-au/actions/runs/37114940915) | Previously verified real PostgreSQL17 execution: eight suites total878 and68 contracts; not a test executed again by this preparation |
| Current baseline CI | [CI37260792303](https://github.com/shuxiachai/returnops-au/actions/runs/37260792303) | Previously verified successful two jobs at exact de8; no fresh test count inferred here |

The 5 October comparison checked161 relevant blob paths by **path, Git mode,
type and blob ID**: all `apps/`, `packages/`, `contracts/`, `tests/`, `tools/`,
`alembic/`, docs08/25/26, and selected root build/runtime files. These current
paths match reviewed c0, with no scoped code removal observed. The comparison
does not assert that unrelated configuration or the entire repository tree is
identical, or that physical CRLF bytes match across checkouts. The local engineering
receipt is `tmp/stage2-next-prep-20261005/current-code-identity.json`.

Existing exact-source evidence remains in
`tmp/pr34-review-readiness-20261003/acceptance-packet-adopted-review-ready.json`
and its referenced receipts. The referenced denial-audit final receipt SHA256 is
`556d065f2b0c3e05bf76a477b9e91451e0692c3b06fa969f6de85116442efdad`.
These ignored local engineering paths are evidence locations, not promised GitHub
downloads. The linked PRs, CI and checked-in code provide the shared review entry.

## Four original acceptance criteria

The named tests below are a map to existing execution evidence, not additional
test counts. Review the complete source at the exact baseline above.

| Original criterion | Implementation and concrete test references | Technical boundary | A decision | C disposition |
|---|---|---|---|---|
| Domain owns state mutation | [LifecycleGuards](../../packages/returnops_domain/lifecycle_guards.py), [state guard](../../packages/returnops_domain/lifecycle_state.py); `test_actual_order_acceptance_invalidates_old_current_refs_and_keeps_source_receipt` in [input tests](../../tests/lifecycle/test_inputs_postgresql.py); `test_founder_current_proposal_and_all_four_reads_do_not_advance_lifecycle` in [read tests](../../tests/lifecycle/test_reads_postgresql.py) | Real existing input hooks and guarded transactions; future sources are explicitly synthetic; reads do not initialize/advance business state | Pending | Pending |
| Illegal transitions rejected with audit | [CustomerFlow](../../packages/returnops_domain/customer_service.py) and [private caller](../../tests/lifecycle/controlled_denial_caller.py); `test_denied_transition_audited_without_acceptance_or_business_mutation` in [customer tests](../../tests/customer/test_processor_postgresql.py); `test_definite_rejection_rolls_back_before_new_authorized_audit` and `test_between_transactions_current_scope_loss_writes_no_audit` in [denial-audit tests](../../tests/lifecycle/test_denial_audit_postgresql.py) | Existing CustomerFlow audit is real. Private future denial proof rolls back first, then obtains current authority in a separate transaction. Unavailable authority means NOT_RECORDED; uncertain commit means UNKNOWN; no guarantee that every denial persists | Pending | Pending |
| Information, revision, escalation and incomplete notification are distinct | [guard guide](../25-a103-lifecycle-guards.md); `test_actual_clarification_invalidates_refs_atomically_and_keeps_old_receipt` in [input tests](../../tests/lifecycle/test_inputs_postgresql.py); `test_risk_revise_consumes_exact_current_proposal_without_increasing_input` and `test_saved_notification_pending_failed_sent_keeps_identity_and_has_no_effects` in [guard tests](../../tests/lifecycle/test_guards_postgresql.py); `test_explicit_resume_after_regrant_never_reopens_accepted_escalation` in [investigation tests](../../tests/investigation/test_recovery_postgresql.py) | Actual clarification/order routes plus synthetic future review/notification/effect fixtures; no real Risk, decision, operation or notification producer delivered | Pending | Pending |
| Real guards, not plain field assignment | [commit guard tests](../../tests/lifecycle/test_transaction_postgresql.py): `test_lease_is_rechecked_at_caller_commit_after_guard_return`, `test_row_lock_serializes_even_raw_authority_revocation_until_commit`; [denial-audit tests](../../tests/lifecycle/test_denial_audit_postgresql.py): `test_original_commit_unknown_is_never_a_denial_or_automatic_retry`, `test_audit_commit_unknown_reports_unknown_without_retry` | Real PostgreSQL version/claim/authority/fence/commit and whole-table invariance evidence. The original and audit unknown outcomes stay separate, without automatic retry or invented denial | Pending | Pending |

The [lifecycle guide](../25-a103-lifecycle-guards.md) and
[denial-audit guide](../26-a103-denial-audit-verification.md) state the full limits.
In particular, private component fixtures are not actual A2 runtime consumers.
There is no additional requirement to finish A2 before accepting A1.03.

## Original predecessor decisions to locate or record

All rows keep their original A Owner / C Reviewer. F.01 additionally requires
the actual three-person contract review. Reuse an existing genuine decision only
for its precise unchanged scope/version; preserve its original author and date.
The bounded record search found technical, AI-assisted or pending packages; it
does not establish that no genuine record exists elsewhere.

| WBS | S before integration | F before acceptance | Actual accepted-version reference |
|---|---|---|---|
| F.01 | None | None | Not located in the bounded packet; actual A/B/C contract review required |
| F.02 | None | F.01 | Pending location/decision |
| F.03 | F.01 | F.02 | Pending location/decision |
| A1.01 | F.01 | None | Pending location/decision |
| A1.02 | A1.01 | F.02 | Pending location/decision |
| F.05 | F.01 | F.02, F.03 | Pending location/decision |
| A1.03 | A1.01 | A1.02, F.05 | Pending this sheet and original predecessors |
| A1.04 | F.01 | A1.01 | Technical mock lookup adopted; actual acceptance reference still to record |
| A1.05 | A1.03 | A1.04, F.03 | Offline preparation only; not whole A1.05 acceptance |

For each genuine decision, supply: **identity, actual date, exact source/version,
scope/criteria, ACCEPT / REJECT / ACCEPT WITH OPEN ITEMS, the open-item disposition,
and the source comment/review/record link**. A merge exception, green CI, AI review
or a copied name does not fill these fields.

## Ready for the two real decisions

A can use this precise proposal: review the four rows at the current baseline,
record the actual disposition and any open items, and attach original predecessor
accepted-version references. Accepting only the proven component must be labelled
component acceptance; it cannot silently become whole A1.03 acceptance.

C can review the same four rows and their referenced source/tests, explicitly
consider current-authority-only audit, UNKNOWN handling and private future fixtures,
and record C's own disposition, exact scope/version and remaining issues. This
sheet is ready to share; no message or review is submitted on C's behalf.

| Decision field | Current value |
|---|---|
| A actual decision, identity/date/source/scope/link | Unfilled |
| C actual non-author review, identity/date/source/scope/link | Unfilled |
| Original predecessor accepted-version references | Unfilled in the current packet |
| Whole A1.03 accepted | **false** |
| A1.05 runtime unlocked | **false** |

## Next permitted work

Use the [offline proposal preparation](../27-a105-offline-proposal-preparation.md)
for contract fixtures, source-preserving assembly and negative tests now. It has
no API/worker/DB/current-source acceptance path and produces no approval or command.
After actual A1.03 acceptance and its original dependencies are recorded, the
first A1.05 runtime slice may save a versioned fixed packet with verified current
full sources and stop at **RISK_REVIEW**. A1.04 and F.03 remain its finish conditions.
Then complete the deterministic A2 loop and R.02/Gate1 before connecting LLM output
to the executable chain. No fixed risk fixture is relabelled as a real PASS.
