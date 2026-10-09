"""AP01-AP20 PostgreSQL acceptance collection — prepared, deliberately unexecuted.

Local DB/Docker startup, migration and all ``flow_engine`` execution are
prohibited for this task.  These nodes are future acceptance coverage, not
evidence of a local result.  Run only after a separately authorized database
environment and a completed independent source review are available.
"""
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from sqlalchemy import delete, select, text, update

from returnops_domain import customer_tables as old, lifecycle_tables as lifecycle
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.preview_profile import APPROVAL_COMPONENT, COMPONENT
from returnops_domain.preview_tables import previews
from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_domain.founder_service import FounderQueries
from approve_helpers import (approve, assert_approved_without_effects, no_execution_grant,
    preview, provision, ready)
from manual_helpers import business, evidence, now, rows, snapshot
from test_manual_postgresql import installed_manual


def accept(engine, identities, case, request, key='approve-key'):
    return approve(engine, identities).accept(case, request, key, 'approve-correlation')


@pytest.mark.parametrize('outcome', ['PASS', 'PASS_WITH_WARNING'])
def test_AP01_retained_pass_chain_generates_only_two_server_owned_commands(flow_engine, identities, enabled, request, outcome):
    case, action_preview, body = ready(flow_engine, identities, outcome=outcome)
    commands = action_preview['scope']['commands']
    assert [command['type'] for command in commands] == ['CREATE_RETURN', 'GENERATE_LABEL']
    assert action_preview['scope']['currency'] == 'AUD'
    assert not rows(flow_engine, lifecycle.effects)
    evidence(request.node.nodeid, case=case, preview=action_preview, approve_request=body)


def test_AP02_stored_preview_rejects_scope_fingerprint_or_command_tampering(flow_engine, identities, enabled, request):
    case, action_preview, body = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    for field, value in [('scope_fingerprint', '0' * 64), ('preview_id', 'wrong_preview')]:
        result = accept(flow_engine, identities, case, {**body, field:value}, 'tamper-' + field)
        assert result.status == 'DENIED'
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), preview=action_preview)


@pytest.mark.parametrize('outcome', ['ESCALATE', 'REVISE'])
def test_AP03_non_pass_review_cannot_create_approvable_preview(flow_engine, identities, enabled, request, outcome):
    from pass_review_helpers import ControlledPassReviewer, ready_pass, receiver
    case, version = ready_pass(flow_engine, identities); provision(flow_engine, identities)
    result = receiver(flow_engine, ControlledPassReviewer(outcome)).accept(case, version, 'review-' + outcome, 'corr')
    assert result.status != 'ACCEPTED'
    before = snapshot(flow_engine)
    assert preview(flow_engine, identities).accept(case, version, 'preview-' + outcome, 'corr').status == 'DENIED'
    after = snapshot(flow_engine)
    assert business(after) == business(before)
    assert len(after['customer_audit_events']) == len(before['customer_audit_events']) + 1
    evidence(request.node.nodeid, outcome=outcome, before=before, after=snapshot(flow_engine))


def test_AP04_preview_is_persisted_once_and_reads_do_not_extend_it(flow_engine, identities, enabled, request):
    case, action_preview, body = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    reader = FounderQueries(flow_engine, CurrentRequestAuthority(identities.auth_config,
        'Bearer ' + identities.tokens['founder']))
    detail = reader.read('getFounderCase', case).body
    assert detail['action_preview'] == action_preview
    after_get = snapshot(flow_engine)
    read_metadata = {'founder_read_snapshots','founder_read_cursors'}
    assert {name:value for name,value in after_get.items() if name not in read_metadata} == {
        name:value for name,value in before.items() if name not in read_metadata}
    assert len(after_get['founder_read_snapshots']) == len(before['founder_read_snapshots'])+1
    assert len(after_get['founder_read_cursors']) >= len(before['founder_read_cursors'])
    replay = preview(flow_engine, identities).accept(case, body['expected_case_version'] - 1,
        'approve-preview-key', 'replay')
    assert replay.status == 'ACCEPTED' and replay.receipt['action_preview'] == action_preview
    assert snapshot(flow_engine) == after_get
    evidence(request.node.nodeid, preview=action_preview, before=before, after_get=after_get,
        after_replay=snapshot(flow_engine), permitted_read_metadata=sorted(read_metadata))


def test_AP05_preview_key_replay_conflict_and_expiry_replacement_rules(flow_engine, identities, enabled, request):
    case, action_preview, body = ready(flow_engine, identities)
    caller = preview(flow_engine, identities)
    assert caller.accept(case, body['expected_case_version'] - 1, 'approve-preview-key', 'replay').receipt['action_preview'] == action_preview
    assert caller.accept(case, body['expected_case_version'], 'approve-preview-key', 'conflict').status == 'DENIED'
    before = snapshot(flow_engine)
    active_new_intent = caller.accept(case, body['expected_case_version'], 'active-new-key', 'corr')
    assert active_new_intent.status == 'DENIED' and active_new_intent.audit == 'RECORDED'
    assert business(snapshot(flow_engine)) == business(before)
    assert len(rows(flow_engine, previews)) == 1
    evidence(request.node.nodeid, preview=action_preview)


def test_AP05_explicit_expired_preview_replacement_preserves_exact_chain(flow_engine, identities, enabled, request):
    case, original, body = ready(flow_engine, identities)
    expiry = datetime.fromisoformat(original['scope']['expires_at'].replace('Z', '+00:00'))
    caller = preview(flow_engine, identities, clock=lambda:expiry)
    before = snapshot(flow_engine)
    replacement = caller.accept(case, body['expected_case_version'], 'replacement-key', 'replacement-corr')
    assert replacement.status == 'ACCEPTED'
    saved = replacement.receipt['action_preview']
    assert saved['preview_id'] != original['preview_id']
    versions = sorted(rows(flow_engine, previews), key=lambda row:row['post_case_version'])
    assert len(versions) == 2 and versions[1]['previous_preview_id'] == versions[0]['preview_id']
    assert versions[1]['pre_case_version'] == versions[0]['post_case_version']
    assert versions[1]['post_case_version'] == body['expected_case_version']+1
    stale = approve(flow_engine, identities, clock=lambda:expiry).accept(case, body, 'old-preview', 'corr')
    assert stale.status == 'DENIED'
    replay_before = snapshot(flow_engine)
    replay = caller.accept(case, body['expected_case_version']-1, 'approve-preview-key', 'replay')
    assert replay.receipt['action_preview'] == original and snapshot(flow_engine) == replay_before
    approve_request = {**body, 'expected_case_version':replacement.receipt['case_version'],
        'preview_id':saved['preview_id'], 'scope_fingerprint':saved['scope_fingerprint']}
    accepted = approve(flow_engine, identities, clock=lambda:expiry).accept(case, approve_request, 'new-preview', 'corr')
    assert_approved_without_effects(flow_engine, case, approve_request, accepted)
    evidence(request.node.nodeid, before=before, replacement=asdict(replacement), accepted=asdict(accepted))


@pytest.mark.parametrize('outcome', ['PASS', 'PASS_WITH_WARNING'])
def test_AP06_current_preview_approval_is_atomic_and_creates_one_execution_intent(flow_engine, identities, enabled, request, outcome):
    case, _, body = ready(flow_engine, identities, outcome=outcome)
    before = snapshot(flow_engine); result = accept(flow_engine, identities, case, body)
    assert_approved_without_effects(flow_engine, case, body, result)
    assert len([row for row in rows(flow_engine, old.history) if row['kind'] == 'DECISION']) == 1
    assert len([row for row in rows(flow_engine, old.history) if row['kind'] == 'APPROVAL']) == 1
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result))


@pytest.mark.parametrize('name', [None, 'customer_a'])
def test_AP07_non_founder_or_missing_identity_cannot_approve(flow_engine, identities, enabled, request, name):
    case, _, body = ready(flow_engine, identities); before = snapshot(flow_engine)
    result = approve(flow_engine, identities, name).accept(case, body, 'forbidden', 'corr')
    assert result.status == 'DENIED' and result.receipt is None and snapshot(flow_engine) == before
    evidence(request.node.nodeid, result=asdict(result), before=before, after=snapshot(flow_engine))


def test_AP08_expired_preview_never_renews_during_approval(flow_engine, identities, enabled, request):
    case, action_preview, body = ready(flow_engine, identities)
    expiry = datetime.fromisoformat(action_preview['scope']['expires_at'].replace('Z', '+00:00'))
    before = snapshot(flow_engine)
    result = approve(flow_engine, identities, clock=lambda:expiry).accept(case, body, 'expired-key', 'corr')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, result=asdict(result), before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('final_change', ['expiry', 'profile'])
def test_AP08_final_preview_expiry_and_profile_are_rechecked(flow_engine, identities, enabled, request, monkeypatch, final_change):
    import returnops_domain.approve_decision as implementation
    from returnops_domain import preview_profile
    case, _, body = ready(flow_engine, identities)
    caller = approve(flow_engine, identities)
    original = implementation.read_target
    def read_target(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get('original_state') is not None:
            if final_change == 'expiry':
                caller.clock = lambda: now() + timedelta(seconds=1000)
            else:
                changed = preview_profile.profile(); changed['allowlist_version'] = 'changed-profile'
                monkeypatch.setattr(preview_profile, 'profile', lambda: changed)
        return result
    monkeypatch.setattr(implementation, 'read_target', read_target)
    before = snapshot(flow_engine); result = caller.accept(case, body, 'final-' + final_change, 'corr')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, final_change=final_change, result=asdict(result),
        before=before, after=snapshot(flow_engine))


@pytest.mark.parametrize('mutation', ['input', 'proposal', 'review'])
def test_AP09_current_source_chain_must_remain_exact(flow_engine, identities, enabled, request, mutation):
    case, _, body = ready(flow_engine, identities)
    with flow_engine.begin() as connection:
        if mutation == 'input': connection.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(input_version=99))
        else: connection.execute(update(lifecycle.state).where(lifecycle.state.c.case_id == case).values(
            **{mutation + '_record_id':'forged_' + mutation}))
    before = snapshot(flow_engine); assert accept(flow_engine, identities, case, body).status == 'DENIED'
    assert business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, mutation=mutation, before=before, after=snapshot(flow_engine))


def test_AP10_same_key_replays_and_different_key_cannot_duplicate_approval(flow_engine, identities, enabled, request):
    case, _, body = ready(flow_engine, identities)
    gate = Barrier(3)
    def invoke(key):
        gate.wait(); return accept(flow_engine, identities, case, body, key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        same = [pool.submit(invoke, 'same-key') for _ in range(2)]; gate.wait()
        first, replay = [future.result(timeout=30) for future in same]
    assert first.status == replay.status == 'ACCEPTED' and first.receipt == replay.receipt
    before = snapshot(flow_engine); conflict = accept(flow_engine, identities, case, body, 'different-key')
    after = snapshot(flow_engine)
    assert conflict.status == 'DENIED' and business(after) == business(before)
    assert len(after['customer_audit_events']) == len(before['customer_audit_events']) + 1
    evidence(request.node.nodeid, first=asdict(first), replay=asdict(replay), conflict=asdict(conflict))


def test_AP11_approve_and_reject_compete_on_the_same_preview(flow_engine, identities, enabled, request):
    from reject_helpers import service as reject_service, provision as provision_reject
    case, _, body = ready(flow_engine, identities); provision_reject(flow_engine, identities)
    reject_body = {key:body[key] for key in ('expected_case_version','proposal_id','proposal_version')} | {
        'decision':'REJECT', 'reason':'Reject the same preview.'}
    gate = Barrier(3)
    def approve_call():
        gate.wait(); return accept(flow_engine, identities, case, body, 'approve-race')
    def reject_call():
        gate.wait(); return reject_service(flow_engine, identities).accept(case, reject_body, 'reject-race', 'corr')
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = [pool.submit(approve_call), pool.submit(reject_call)]; gate.wait()
        results = [future.result(timeout=30) for future in calls]
    assert sorted(result.status for result in results) == ['ACCEPTED', 'DENIED']
    assert len([row for row in rows(flow_engine, old.history) if row['kind'] == 'DECISION']) == 1
    evidence(request.node.nodeid, results=[asdict(result) for result in results])


@pytest.mark.parametrize('component,purpose', [(COMPONENT, 'PREVIEW'), (APPROVAL_COMPONENT, 'APPROVAL')])
def test_AP12_current_authority_is_rechecked_at_entry(flow_engine, identities, enabled, request, component, purpose):
    case, _, body = ready(flow_engine, identities)
    with flow_engine.begin() as connection:
        connection.execute(update(lifecycle.authorities).where(lifecycle.authorities.c.component_id == component,
            lifecycle.authorities.c.purpose == purpose).values(enabled=False))
    before = snapshot(flow_engine); result = accept(flow_engine, identities, case, body)
    assert result.status == 'DENIED'
    after = snapshot(flow_engine); assert business(after) == business(before)
    if purpose == 'APPROVAL':
        assert result.audit == 'NOT_RECORDED' and after == before
    else:
        assert result.audit == 'RECORDED'
        assert len(after['customer_audit_events']) == len(before['customer_audit_events']) + 1
    evidence(request.node.nodeid, component=component, purpose=purpose)


@pytest.mark.parametrize('change', ['preview_revision','preview_revoked','approval_revision','approval_revoked',
    'claim','epoch','lease_renewal','preview_pointer'])
def test_AP12_final_authority_and_original_work_are_rechecked(flow_engine, identities, enabled, request, change):
    case, _, body = ready(flow_engine, identities)
    class Changed(CustomerUnitOfWork):
        def commit(self):
            if change.startswith(('preview_', 'approval_')) and change != 'preview_pointer':
                component = COMPONENT if change.startswith('preview_') else APPROVAL_COMPONENT
                values = {'revision':2} if change.endswith('revision') else {'enabled':False}
                self.execute(update(lifecycle.authorities).where(
                    lifecycle.authorities.c.component_id == component).values(**values))
            elif change == 'preview_pointer':
                self.execute(update(lifecycle.state).where(lifecycle.state.c.case_id == case).values(preview_id='forged_preview'))
            else:
                values = {'claim':{'claim_id':'forged_claim'}, 'epoch':{'epoch':9},
                    'lease_renewal':{'lease_expires_at':now()+timedelta(seconds=3600)}}[change]
                self.execute(update(lifecycle.work).where(lifecycle.work.c.case_id == case,
                    lifecycle.work.c.purpose == 'APPROVAL').values(**values))
            return super().commit()
    before = snapshot(flow_engine)
    result = approve(flow_engine, identities, uow_factory=Changed).accept(case, body, 'final-'+change, 'corr')
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, change=change, result=asdict(result), before=before, after=snapshot(flow_engine))


def test_AP13_each_staged_write_rolls_back_atomically(flow_engine, identities, enabled, request):
    case, _, body = ready(flow_engine, identities); trace = []
    class Trace(CustomerUnitOfWork):
        def execute(self, statement, parameters=None):
            if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                trace.append((statement.table.name, 'insert' if statement.is_insert else 'update'))
            return super().execute(statement, parameters)
        def commit(self):
            for check in self._commit_checks: check()
            self.poison(); raise FlowError('INVALID_STATE')
    probe = approve(flow_engine, identities, uow_factory=Trace).accept(case, body, 'probe-key', 'corr')
    assert probe.status == 'DENIED'
    names = {name for name, _ in trace}
    assert {old.history.name, old.audit.name, old.receipts.name, lifecycle.work.name, lifecycle.state.name} <= names
    before = snapshot(flow_engine); outcomes = []
    for ordinal, write in enumerate(trace, start=1):
        class Fault(CustomerUnitOfWork):
            writes = 0
            def execute(self, statement, parameters=None):
                if not getattr(statement, 'is_select', False) and getattr(statement, 'table', None) is not None:
                    self.writes += 1
                    if self.writes == ordinal:
                        self.poison(); raise RuntimeError('injected staged write fault')
                return super().execute(statement, parameters)
        result = approve(flow_engine, identities, uow_factory=Fault).accept(case, body, 'fault-'+str(ordinal), 'corr')
        after = snapshot(flow_engine)
        assert result.status == 'DENIED' and business(after) == business(before)
        outcomes.append(dict(ordinal=ordinal, write=write, result=asdict(result)))
    evidence(request.node.nodeid, trace=trace, outcomes=outcomes)


@pytest.mark.parametrize('committed', [True, False])
def test_AP14_unknown_is_not_retried_or_reclassified(flow_engine, identities, enabled, request, committed):
    from test_manual_postgresql import UnknownCommit
    case, _, body = ready(flow_engine, identities)
    class Unknown(UnknownCommit): actual_commit = committed
    caller = approve(flow_engine, identities, uow_factory=Unknown)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'unknown-key', 'unknown-correlation')
    assert result.status == 'UNKNOWN' and result.audit == 'NOT_ATTEMPTED'
    actual = snapshot(flow_engine)
    if not committed:
        assert actual == before
    recovered = caller.recover(case, body, 'unknown-key')
    if committed:
        assert_approved_without_effects(flow_engine, case, body, recovered)
    else:
        assert recovered.status == 'UNKNOWN' and recovered.receipt is None
    evidence(request.node.nodeid, committed=committed, before=before, actual=actual,
        result=asdict(result), recovered=asdict(recovered))


def test_AP15_replay_returns_original_receipt_after_preview_expiry(flow_engine, identities, enabled, request):
    case, action_preview, body = ready(flow_engine, identities); first = accept(flow_engine, identities, case, body)
    expiry = datetime.fromisoformat(action_preview['scope']['expires_at'].replace('Z', '+00:00'))
    before = snapshot(flow_engine)
    replay = approve(flow_engine, identities, clock=lambda:expiry).accept(case, body, 'approve-key', 'corr')
    assert replay.receipt == first.receipt and snapshot(flow_engine) == before
    evidence(request.node.nodeid, first=asdict(first), replay=asdict(replay))


def test_AP16_denial_does_not_leak_request_or_write_audit_without_authority(flow_engine, identities, enabled, request):
    case, _, body = ready(flow_engine, identities)
    with flow_engine.begin() as connection:
        connection.execute(delete(lifecycle.authorities).where(lifecycle.authorities.c.component_id == APPROVAL_COMPONENT))
    before = snapshot(flow_engine); result = accept(flow_engine, identities, case, body)
    assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and snapshot(flow_engine) == before
    assert body['reason'] not in str(result)
    evidence(request.node.nodeid, result=asdict(result))


def test_AP17_execution_is_pending_only_and_all_claim_paths_reject_it(flow_engine, identities, enabled, request):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    case, _, body = ready(flow_engine, identities); result = accept(flow_engine, identities, case, body)
    assert_approved_without_effects(flow_engine, case, body, result)
    assert no_execution_grant(flow_engine)
    execution, = [row for row in rows(flow_engine, lifecycle.work)
        if row['case_id'] == case and row['purpose'] == 'EXECUTION']
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        with pytest.raises(FlowError):
            LifecycleGuards(APPROVAL_COMPONENT).claim(uow, execution['work_id'], now())
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, result=asdict(result), effects=rows(flow_engine, lifecycle.effects))


@pytest.mark.parametrize('at_expiry', [False, True])
def test_AP18_reject_remains_available_for_valid_or_expired_preview(flow_engine, identities, enabled, request, at_expiry):
    from reject_helpers import attempt as reject, provision as reject_provision
    case, action_preview, body = ready(flow_engine, identities); reject_provision(flow_engine, identities)
    clock = None
    if at_expiry:
        expiry = datetime.fromisoformat(action_preview['scope']['expires_at'].replace('Z', '+00:00'))
        clock = lambda:expiry
    rejected = reject(flow_engine, identities, case, {key:body[key] for key in ('expected_case_version','proposal_id','proposal_version')} | dict(decision='REJECT', reason='Reject preview.'), **({} if clock is None else {'clock':clock}))
    assert rejected.status == 'ACCEPTED'
    evidence(request.node.nodeid, at_expiry=at_expiry, result=asdict(rejected))


@pytest.mark.parametrize('mode', ['old_version', 'unknown_version', 'missing_preview_table', 'multiple_heads',
    'consumer_unique_nulls_not_distinct', 'preview_fk_not_valid'])
def test_AP19_schema_readiness_fails_closed(flow_engine, identities, enabled, request, mode):
    case, _, body = ready(flow_engine, identities)
    with flow_engine.begin() as connection:
        if mode == 'old_version': connection.execute(text("UPDATE alembic_version SET version_num='0008_review_escalation'"))
        elif mode == 'unknown_version': connection.execute(text("UPDATE alembic_version SET version_num='unknown'"))
        elif mode == 'missing_preview_table': connection.execute(text('DROP TABLE ' + previews.name))
        elif mode == 'multiple_heads': connection.execute(text("INSERT INTO alembic_version VALUES ('unknown')"))
        elif mode == 'consumer_unique_nulls_not_distinct':
            connection.execute(text('ALTER TABLE ' + previews.name + ' DROP CONSTRAINT uq_preview_consumer'))
            connection.execute(text('ALTER TABLE ' + previews.name + ' ADD CONSTRAINT uq_preview_consumer '
                'UNIQUE NULLS NOT DISTINCT (consuming_decision_record_id)'))
        else:
            connection.execute(text('ALTER TABLE ' + previews.name + ' DROP CONSTRAINT fk_preview_case_id'))
            connection.execute(text('ALTER TABLE ' + previews.name + ' ADD CONSTRAINT fk_preview_case_id '
                'FOREIGN KEY (case_id) REFERENCES ' + old.case_heads.name + '(case_id) NOT VALID'))
    before = snapshot(flow_engine); assert accept(flow_engine, identities, case, body).status == 'DENIED'
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, mode=mode)


@pytest.mark.parametrize('consumed', [False, True])
@pytest.mark.parametrize('kind', ['STATEMENT','EVIDENCE'])
def test_AP19_retention_erases_preview_and_receipts_and_pauses_execution(flow_engine, identities, enabled, request, consumed, kind):
    from returnops_domain.retention import RetentionService
    case, action_preview, body = ready(flow_engine, identities)
    if consumed:
        assert_approved_without_effects(flow_engine, case, body, accept(flow_engine, identities, case, body))
    facts = [row for row in rows(flow_engine, old.acceptances)
        if row['resource_kind'] == 'CASE' and row['resource_id'] == case]
    fact_ids = {row['acceptance_id'] for row in facts}
    assert facts and sum(row['operation'] == 'recordFounderDecision' for row in facts) == int(consumed)
    derived_ids = {row['record_id'] for row in rows(flow_engine, old.history)
        if row['case_id'] == case and row['kind'] in {'PROPOSAL','REVIEW','DECISION','APPROVAL','OPERATION','NOTIFICATION'}}
    assert derived_ids
    record = next(row for row in rows(flow_engine, old.history) if row['case_id'] == case and row['kind'] == kind)
    assert RetentionService(flow_engine).remove(kind, record['object_id'])
    saved = next(row for row in rows(flow_engine, previews) if row['preview_id'] == action_preview['preview_id'])
    assert saved['available'] is False and saved['body'] is None and saved['request_key'] == 'approve-preview-key'
    assert bool(saved['consuming_decision_record_id']) is consumed
    state = next(row for row in rows(flow_engine, lifecycle.state) if row['case_id'] == case)
    assert state['preview_id'] is None and state['approval_record_id'] is None and state['available'] is False
    work = [row for row in rows(flow_engine, lifecycle.work) if row['case_id'] == case and row['purpose'] == 'EXECUTION']
    assert len(work) == int(consumed)
    assert all(row['state'] == 'PAUSED' and row['claim_id'] is None for row in work)
    receipts = [row for row in rows(flow_engine, old.receipts) if row['acceptance_id'] in fact_ids]
    assert len(receipts) == len(fact_ids) and all(row['body'] is None and row['available'] is False for row in receipts)
    assert [row for row in rows(flow_engine, old.acceptances) if row['acceptance_id'] in fact_ids] == facts
    assert not any(row['record_id'] in derived_ids for row in rows(flow_engine, old.history_contents))
    assert all(row['retention_state'] == 'DELETED' for row in rows(flow_engine, old.history) if row['record_id'] in derived_ids)
    before = snapshot(flow_engine)
    old_preview = preview(flow_engine, identities).accept(case, body['expected_case_version']-1, 'approve-preview-key', 'corr')
    old_approve = accept(flow_engine, identities, case, body)
    assert old_preview.status == old_approve.status == 'DENIED'
    assert old_preview.receipt is None and old_approve.receipt is None and snapshot(flow_engine) == before
    assert not rows(flow_engine, lifecycle.effects)
    reader = FounderQueries(flow_engine, CurrentRequestAuthority(identities.auth_config,
        'Bearer ' + identities.tokens['founder']))
    detail = reader.read('getFounderCase', case).body
    assert all(field not in detail for field in ('action_preview','current_proposal','current_review','order_snapshot'))
    assert detail['approvals'] == [] and detail['decisions'] == []
    if kind == 'STATEMENT':
        assert detail['statements'] == []
    else:
        assert not any(item['evidence_id'] == record['object_id'] for item in detail['evidence'])
    after_get = snapshot(flow_engine)
    metadata = {'founder_read_snapshots','founder_read_cursors'}
    assert {name:value for name,value in after_get.items() if name not in metadata} == {
        name:value for name,value in before.items() if name not in metadata}
    assert next(row for row in rows(flow_engine, previews) if row['preview_id'] == action_preview['preview_id'])['body'] is None
    assert [row for row in rows(flow_engine, old.receipts) if row['acceptance_id'] in fact_ids] == receipts
    evidence(request.node.nodeid, consumed=consumed, kind=kind, before=before, after=after_get,
        preview_result=asdict(old_preview), approve_result=asdict(old_approve))


@pytest.mark.parametrize('flow_engine', ['0007_lifecycle_guards','0008_review_escalation'], indirect=True)
def test_AP19_exact_old_descriptors_do_not_authorize_new_preview(flow_engine, request):
    from returnops_domain.lifecycle_schema import version
    from returnops_api.database import readiness
    from returnops_api.private_preview import compose_private_preview
    with flow_engine.connect() as connection:
        actual = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert version(connection) == actual
    assert readiness(flow_engine) is False
    before = snapshot(flow_engine)
    result = compose_private_preview(flow_engine).accept('unknown_case', 1, 'preview-key', 'corr')
    assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and snapshot(flow_engine) == before
    evidence(request.node.nodeid, descriptor=actual, result=asdict(result), before=before, after=snapshot(flow_engine))


def test_AP20_installed_private_entrypoint_has_no_effects(flow_engine, identities, enabled, request, tmp_path, installed_manual):
    import json
    import os
    import subprocess
    import sys
    from hashlib import sha256
    from pathlib import Path
    from pass_review_helpers import ready_pass, receiver, ControlledPassReviewer
    case, source_version = ready_pass(flow_engine, identities)
    review = receiver(flow_engine, ControlledPassReviewer('PASS')).accept(case, source_version, 'installed-review-key', 'corr')
    assert review.status == 'ACCEPTED'
    provision(flow_engine, identities)
    proposal = next(row for row in rows(flow_engine, old.history) if row['case_id'] == case and row['kind'] == 'PROPOSAL')
    body = dict(expected_case_version=source_version+2, proposal_id=proposal['object_id'],
        proposal_version=proposal['object_version'], decision='APPROVE', reason='Approve installed preview.')
    root = Path(__file__).resolve().parents[2]
    names = ['approve_decision.py', 'approve_denial.py', 'approve_sources.py', 'preview_sources.py',
        'preview_profile.py', 'preview_tables.py', 'preview_service.py', 'lifecycle_guards.py']
    hashes = {}
    for name in names:
        source, installed = root/'packages/returnops_domain'/name, installed_manual/'returnops_domain'/name
        assert source.read_bytes() == installed.read_bytes()
        hashes[name] = sha256(installed.read_bytes()).hexdigest()
    assert (root/'apps/api/returnops_api/private_approve.py').read_bytes() == (
        installed_manual/'returnops_api/private_approve.py').read_bytes()
    assert (root/'apps/api/returnops_api/private_preview.py').read_bytes() == (
        installed_manual/'returnops_api/private_preview.py').read_bytes()
    assert not (installed_manual/'tests').exists() and not (installed_manual/'approve_helpers.py').exists()
    auth = identities.auth_config
    config = dict(case=case, request=body, preview_version=source_version+1, key='installed-key', correlation_id='installed-correlation',
        schema=flow_engine._customer_test_schema, issuer=auth.issuer, audience=auth.audience,
        signing_key=auth.signing_key.hex(), token=identities.tokens['founder'])
    path = tmp_path/'approve-installed.json'; path.write_text(json.dumps(config), encoding='utf-8')
    before = snapshot(flow_engine)
    completed = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).with_name('approve_process_probe.py')),
        str(path), str(installed_manual)], cwd=tmp_path, env=os.environ.copy(), capture_output=True, timeout=60)
    assert completed.returncode == 0 and completed.stderr == b''
    result = json.loads(completed.stdout)
    assert result['status'] == 'ACCEPTED'
    assert result['preview_result']['status'] == 'ACCEPTED'
    assert result['claims'] == {'APPROVAL': 1, 'EXECUTION': 0}
    assert not any(result['effects'].values())
    action = result['preview_result']['receipt']['action_preview']
    body.update(preview_id=action['preview_id'], scope_fingerprint=action['scope_fingerprint'])
    assert_approved_without_effects(flow_engine, case, body, type('Result', (), result)())
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=result,
        installed_hashes=hashes, isolated_python=True)
