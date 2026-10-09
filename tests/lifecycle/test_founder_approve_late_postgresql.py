"""AP10/AP11/AP12 future PG acceptance nodes; deliberately not executed locally.

Every positive setup uses the actual controlled PASS acceptance and preview.
Late SQL injections are test-only faults inside the original transaction, not
claims that an unfenced external writer can bypass the production write fence.
Race evidence requires two distinct PostgreSQL sessions blocked by that fence;
thread launch or elapsed time alone is not concurrency evidence.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import local
from time import monotonic, sleep

import pytest
from sqlalchemy import select, text, update

from returnops_domain import customer_tables as old, lifecycle_tables as lifecycle
from returnops_domain.canonical import decode_document
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.preview_profile import APPROVAL_COMPONENT, COMPONENT
from returnops_domain.preview_tables import previews
from approve_helpers import approve, assert_approved_without_effects, no_execution_grant, preview, ready
from manual_helpers import business, evidence, rows, snapshot


def _case_rows(engine, table, case):
    return [row for row in rows(engine, table) if row['case_id'] == case]


def _change_one(uow, table, column, value, **changes):
    """Prove a real row changed; never count an untriggered hook as coverage."""
    clause = table.c[column] == value
    before = dict(uow.execute(select(table).where(clause)).mappings().one())
    assert any(before[name] != changed for name, changed in changes.items())
    assert uow.execute(update(table).where(clause).values(**changes)).rowcount == 1
    after = dict(uow.execute(select(table).where(clause)).mappings().one())
    assert all(after[name] == changed for name, changed in changes.items())
    return dict(table=table.name, key=column, identity=value, fields=sorted(changes))


def _new_audits(engine, before):
    old_ids = {row['event_id'] for row in before[old.audit.name]}
    return [decode_document(row['body']) for row in rows(engine, old.audit)
        if row['event_id'] not in old_ids]


def _assert_no_approval(engine, case):
    assert not [row for row in _case_rows(engine, old.history, case)
        if row['kind'] in {'DECISION', 'APPROVAL', 'OPERATION', 'NOTIFICATION'}]
    assert not [row for row in _case_rows(engine, lifecycle.work, case)
        if row['purpose'] in {'APPROVAL', 'EXECUTION', 'NOTIFICATION', 'EFFECT'}]
    assert not rows(engine, lifecycle.effects) and no_execution_grant(engine)
    state, = _case_rows(engine, lifecycle.state, case)
    assert all(state[name] is None for name in ('approval_record_id', 'outcome',
        'return_record_id', 'label_record_id', 'notification_work_id'))
    saved, = _case_rows(engine, previews, case)
    assert saved['consuming_decision_record_id'] is None and saved['consumed_at'] is None


def _assert_one_approval(engine, case, body, result):
    assert_approved_without_effects(engine, case, body, result)
    history = _case_rows(engine, old.history, case)
    assert len([row for row in history if row['kind'] == 'DECISION']) == 1
    assert len([row for row in history if row['kind'] == 'APPROVAL']) == 1
    assert not [row for row in history if row['kind'] in {'OPERATION', 'NOTIFICATION'}]
    work = _case_rows(engine, lifecycle.work, case)
    approval, = [row for row in work if row['purpose'] == 'APPROVAL']
    assert approval['state'] == 'DONE' and approval['epoch'] == 1
    assert not [row for row in work if row['purpose'] in {'NOTIFICATION', 'EFFECT'}]
    events = _case_rows(engine, lifecycle.events, case)
    assert len([row for row in events if row['event_kind'] == 'APPROVAL']) == 1
    facts = [row for row in rows(engine, old.acceptances)
        if row['target'] == case and row['operation'] == 'recordFounderDecision']
    fact, = facts
    assert len([row for row in rows(engine, old.receipts)
        if row['acceptance_id'] == fact['acceptance_id']]) == 1
    state, = _case_rows(engine, lifecycle.state, case)
    assert all(state[name] is None for name in ('outcome', 'return_record_id',
        'label_record_id', 'notification_work_id'))


def _hook_after_final_approval(monkeypatch, mutate):
    """Target the service's final full read, after the lower guard has run.

    The service imports aliases; the lower guard imports approve_sources itself.
    Patching only these aliases leaves lower validation active and ensures the
    initial staged seal is not mistaken for the final before-commit seal.
    """
    from returnops_domain import approve_decision
    original_target = approve_decision.read_target
    original_approval = approve_decision.accepted_approval
    stages = []

    def target(*args, **kwargs):
        result = original_target(*args, **kwargs)
        if kwargs.get('original_state') is not None:
            assert stages == []
            stages.append('final_target_returned')
        return result

    def accepted(uow, *args, **kwargs):
        result = original_approval(uow, *args, **kwargs)
        if stages == ['final_target_returned']:
            stages.append('final_accepted_approval_returned')
            assert result['work']['state'] == 'DONE'
            assert result['execution']['state'] == 'PENDING'
            mutate(uow, result)
            stages.append('injected')
        return result

    monkeypatch.setattr(approve_decision, 'read_target', target)
    monkeypatch.setattr(approve_decision, 'accepted_approval', accepted)
    return stages


LATE_CHANGES = [
    'human_revoked', 'human_disabled', 'human_demoted', 'human_store',
    'owner_replaced', 'owner_disabled', 'human_expired',
    'approval_revoked', 'approval_revision', 'preview_revoked', 'preview_revision',
    'claim', 'epoch', 'lease_renewal', 'service_lease_expiry', 'guard_lease_expiry',
    'preview_body_hash', 'approval_history_hash', 'approval_binding',
    'approval_event', 'execution_target',
]


@pytest.mark.parametrize('change', LATE_CHANGES)
def test_AP12_after_final_full_read_current_authority_and_seal_are_rechecked(
        flow_engine, identities, enabled, request, monkeypatch, change):
    case, action, body = ready(flow_engine, identities)
    caller = approve(flow_engine, identities)
    lease = []
    original_claim = caller.guard.claim

    def claim(uow, work_id, at, **options):
        result = original_claim(uow, work_id, at, **options)
        assert result is not None
        lease.append(uow.execute(select(lifecycle.work.c.lease_expires_at).where(
            lifecycle.work.c.work_id == work_id)).scalar_one())
        return result

    monkeypatch.setattr(caller.guard, 'claim', claim)
    injected = []

    def mutate(uow, seal):
        founder = identities.people['founder']['principal_id']
        owner = identities.people['customer_a']['principal_id']
        if change == 'human_revoked':
            detail = _change_one(uow, old.sessions, 'session_id',
                identities.sessions['founder']['session_id'], revoked=True)
        elif change in {'human_disabled', 'human_demoted', 'human_store'}:
            changes = {'human_disabled':dict(enabled=False), 'human_demoted':dict(role='CUSTOMER'),
                'human_store':dict(store_id='late_other_store')}[change]
            detail = _change_one(uow, old.principals, 'principal_id', founder, **changes)
        elif change == 'owner_replaced':
            detail = _change_one(uow, old.case_heads, 'case_id', case,
                owner_principal_id=identities.people['customer_b']['principal_id'])
        elif change == 'owner_disabled':
            detail = _change_one(uow, old.principals, 'principal_id', owner, enabled=False)
        elif change == 'human_expired':
            from returnops_api.security import authentication
            at = datetime.fromtimestamp(identities.sessions['founder']['expires_at']
                + identities.auth_config.leeway_seconds + 1, timezone.utc)
            class ExpiredClock:
                @staticmethod
                def now(tz):
                    return at.astimezone(tz)
            monkeypatch.setattr(authentication, 'datetime', ExpiredClock)
            detail = dict(clock='F.03 post-registry time', advanced_to=at)
        elif change.startswith(('approval_', 'preview_')) and change.endswith(('revoked', 'revision')):
            component = APPROVAL_COMPONENT if change.startswith('approval_') else COMPONENT
            grant = uow.execute(select(lifecycle.authorities).where(
                lifecycle.authorities.c.component_id == component)).mappings().one()
            changes = dict(enabled=False) if change.endswith('revoked') else dict(revision=grant['revision']+1)
            detail = _change_one(uow, lifecycle.authorities, 'component_id', component, **changes)
        elif change in {'claim', 'epoch', 'lease_renewal'}:
            original_lease, = lease
            changes = {'claim':dict(claim_id='late_replacement_claim'),
                'epoch':dict(epoch=seal['work']['epoch']+1),
                'lease_renewal':dict(lease_expires_at=original_lease+timedelta(seconds=60))}[change]
            detail = _change_one(uow, lifecycle.work, 'work_id', seal['work']['work_id'], **changes)
        elif change in {'service_lease_expiry', 'guard_lease_expiry'}:
            original_lease, = lease
            expiry = datetime.fromisoformat(action['scope']['expires_at'].replace('Z', '+00:00'))
            assert original_lease < expiry
            if change == 'service_lease_expiry':
                caller.clock = lambda: original_lease
            else:
                caller.guard.clock = lambda: original_lease
            # The stored original lease is untouched; a real final clock sample
            # reaches its boundary while the action preview is still valid.
            detail = dict(clock=change, advanced_to=original_lease, preview_expiry=expiry)
        elif change == 'preview_body_hash':
            detail = _change_one(uow, previews, 'preview_id', body['preview_id'], body_hash='0'*64)
        elif change == 'approval_history_hash':
            detail = _change_one(uow, old.history, 'record_id', seal['record']['record_id'], content_sha256='0'*64)
        elif change == 'approval_binding':
            detail = _change_one(uow, lifecycle.sources, 'record_id', seal['record']['record_id'], source_hash='0'*64)
        elif change == 'approval_event':
            detail = _change_one(uow, lifecycle.events, 'record_id', seal['record']['record_id'], fingerprint='0'*64)
        else:
            assert change == 'execution_target'
            detail = _change_one(uow, lifecycle.work, 'work_id', seal['execution']['work_id'], target_hash='0'*64)
        injected.append(detail)

    stages = _hook_after_final_approval(monkeypatch, mutate)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'late-'+change, 'late-guard-correlation')
    after = snapshot(flow_engine)
    assert stages == ['final_target_returned', 'final_accepted_approval_returned', 'injected']
    assert len(injected) == len(lease) == 1
    assert result.status == 'DENIED' and result.receipt is None and result.safe_code == 'INVALID_STATE'
    assert business(after) == business(before)
    _assert_no_approval(flow_engine, case)
    if change == 'human_expired':
        assert result.audit == 'NOT_RECORDED' and after == before
    else:
        # In-transaction injected changes roll back. The separate denial UoW
        # must authorize again against the restored real registry and grant.
        assert result.audit == 'RECORDED'
        audit, = _new_audits(flow_engine, before)
        assert audit['event_type'] == 'FOUNDER_APPROVE_DENIED'
        assert audit['actor'] == dict(kind='HUMAN', role='FOUNDER',
            principal_id=identities.people['founder']['principal_id'])
        assert body['reason'] not in str(audit) and body['reason'] not in str(result)
    evidence(request.node.nodeid, change=change, stages=stages, injected=injected,
        original_lease=lease[0], result=asdict(result), before=before, after=after)


@pytest.mark.parametrize('change', ['raw_statement', 'proposal_body', 'review_binding'])
def test_AP12_full_source_is_read_again_after_final_target_read(
        flow_engine, identities, enabled, request, monkeypatch, change):
    from returnops_domain import approve_decision
    from returnops_domain.storage import original_statement_contents
    case, _, body = ready(flow_engine, identities)
    original = approve_decision.read_target
    injected = []

    def changed(uow, *args, **kwargs):
        target = original(uow, *args, **kwargs)
        if kwargs.get('original_state') is not None:
            assert not injected
            if change == 'raw_statement':
                statement = uow.execute(select(old.history).where(old.history.c.case_id == case,
                    old.history.c.kind == 'STATEMENT')).mappings().one()
                detail = _change_one(uow, original_statement_contents, 'statement_id',
                    statement['object_id'], raw_text=b'changed after final target proof')
            elif change == 'proposal_body':
                detail = _change_one(uow, old.history_contents, 'record_id',
                    target['row']['proposal_record_id'], body=b'{}')
            else:
                detail = _change_one(uow, lifecycle.sources, 'record_id',
                    target['row']['review_record_id'], source_hash='0'*64)
            injected.append(detail)
        return target

    monkeypatch.setattr(approve_decision, 'read_target', changed)
    before = snapshot(flow_engine)
    result = approve(flow_engine, identities).accept(case, body, 'source-'+change, 'source-correlation')
    after = snapshot(flow_engine)
    assert len(injected) == 1 and result.status == 'DENIED' and result.receipt is None
    assert result.safe_code == 'INVALID_STATE' and result.audit == 'RECORDED'
    assert business(after) == business(before)
    audit, = _new_audits(flow_engine, before)
    assert audit['event_type'] == 'FOUNDER_APPROVE_DENIED'
    _assert_no_approval(flow_engine, case)
    evidence(request.node.nodeid, injected=injected, result=asdict(result), before=before, after=after,
        hook='after service final read_target; before its independent accepted_approval read')


@pytest.mark.parametrize('fresh_change', ['human_revoked', 'owner_disabled', 'approval_revoked', 'preview_revoked'])
def test_AP12_late_denial_reauthorizes_after_business_rollback(
        flow_engine, identities, enabled, request, monkeypatch, fresh_change):
    case, _, body = ready(flow_engine, identities)
    original_before = snapshot(flow_engine)
    fresh = []

    class FreshAudit(CustomerUnitOfWork):
        def __enter__(self):
            # The failed business UoW has already exited. This separate trusted
            # fixture transaction persists loss of authority before audit entry.
            assert not fresh
            _assert_no_approval(flow_engine, case)
            assert snapshot(flow_engine) == original_before
            with CustomerUnitOfWork(flow_engine, write=True) as changed:
                if fresh_change == 'human_revoked':
                    detail = _change_one(changed, old.sessions, 'session_id',
                        identities.sessions['founder']['session_id'], revoked=True)
                elif fresh_change == 'owner_disabled':
                    detail = _change_one(changed, old.principals, 'principal_id',
                        identities.people['customer_a']['principal_id'], enabled=False)
                else:
                    component = APPROVAL_COMPONENT if fresh_change == 'approval_revoked' else COMPONENT
                    detail = _change_one(changed, lifecycle.authorities, 'component_id', component, enabled=False)
                changed.commit()
            fresh.append(dict(injected=detail, before_audit=snapshot(flow_engine)))
            return super().__enter__()

    def corrupt_claim(uow, seal):
        _change_one(uow, lifecycle.work, 'work_id', seal['work']['work_id'], claim_id='late_audit_claim')

    stages = _hook_after_final_approval(monkeypatch, corrupt_claim)
    result = approve(flow_engine, identities, audit_uow=FreshAudit).accept(
        case, body, 'audit-'+fresh_change, 'fresh-audit-correlation')
    after = snapshot(flow_engine)
    assert stages == ['final_target_returned', 'final_accepted_approval_returned', 'injected']
    item, = fresh
    assert result.status == 'DENIED' and result.receipt is None and result.safe_code == 'INVALID_STATE'
    assert business(after) == business(item['before_audit'])
    _assert_no_approval(flow_engine, case)
    if fresh_change == 'preview_revoked':
        # Denial audit requires HUMAN plus APPROVAL, not the lost PREVIEW grant.
        assert result.audit == 'RECORDED'
        audit, = _new_audits(flow_engine, item['before_audit'])
        assert audit['event_type'] == 'FOUNDER_APPROVE_DENIED'
    else:
        assert result.audit == 'NOT_RECORDED' and after == item['before_audit']
    evidence(request.node.nodeid, fresh_change=fresh_change, stages=stages,
        before=original_before, fresh=item, after=after, result=asdict(result))


def _overlap_at_actual_fence(engine, monkeypatch, calls, *, first=None):
    """Observe both real connections waiting before releasing the holder.

    Normal 5-second lock timeouts and 10-second statement timeouts remain intact.
    On any observation/assertion failure, holder exit releases its fence before
    ThreadPoolExecutor joins workers. No unbounded barrier remains to strand them.
    """
    from returnops_domain import customer_uow
    original = customer_uow.acquire_fence
    participants = Queue()
    context = local()

    def observed(connection, *, write):
        label = getattr(context, 'label', None)
        if label is not None and not getattr(context, 'announced', False):
            assert write is True
            pid = connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            context.announced = True
            participants.put((label, pid))
        return original(connection, write=write)

    def invoke(label, call):
        context.label, context.announced = label, False
        return call()

    def waiters(pids):
        with engine.connect() as observer:
            return [dict(row) for row in observer.execute(text(
                "SELECT pid, wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers "
                "FROM pg_stat_activity WHERE pid IN (:a, :b) "
                "AND wait_event_type='Lock' AND wait_event='advisory'"),
                dict(a=pids[0], b=pids[-1])).mappings()]

    monkeypatch.setattr(customer_uow, 'acquire_fence', observed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        with CustomerUnitOfWork(engine, write=True) as holder:
            holder_pid = holder.connection.execute(text('SELECT pg_backend_pid()')).scalar_one()
            deadline = monotonic()+3
            futures, announced = {}, []
            if first is not None:
                assert first in calls
                futures[first] = pool.submit(invoke, first, calls[first])
                announced.append(participants.get(timeout=max(0.01, deadline-monotonic())))
                assert announced[0][0] == first
                while not waiters([announced[0][1]]):
                    assert monotonic() < deadline, 'First entrant must really queue before second starts'
                    sleep(0.01)
            for label, call in calls.items():
                if label not in futures:
                    futures[label] = pool.submit(invoke, label, call)
            while len(announced) != 2:
                announced.append(participants.get(timeout=max(0.01, deadline-monotonic())))
            assert {label for label, _ in announced} == set(calls)
            pids = [pid for _, pid in announced]
            assert len(set(pids)) == 2 and holder_pid not in pids
            waiting = []
            while len(waiting) != 2:
                waiting = waiters(pids)
                assert monotonic() < deadline, 'Both real advisory-lock waiters must be observed'
                if len(waiting) != 2:
                    sleep(0.01)
            assert {row['pid'] for row in waiting} == set(pids)
            assert all(holder_pid in row['blockers'] for row in waiting)
            if first is not None:
                first_pid = dict(announced)[first]
                second_waiter, = [row for row in waiting if row['pid'] != first_pid]
                # PostgreSQL reports soft blockers ahead in the actual queue.
                # This establishes order without assuming thread scheduling.
                assert first_pid in second_waiter['blockers']
            holder.commit()
        results = {label:future.result(timeout=30) for label, future in futures.items()}
    return results, dict(holder_backend_pid=holder_pid, participants=announced,
        blocked_sessions=waiting, first=first)


def test_AP10_different_keys_have_two_real_overlapping_attempts_and_one_approval(
        flow_engine, identities, enabled, request, monkeypatch):
    case, _, body = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    calls = {key:(lambda key=key:approve(flow_engine, identities).accept(case, body, key, 'different-key-race'))
        for key in ('competing-key-a', 'competing-key-b')}
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, calls)
    assert sorted(result.status for result in results.values()) == ['ACCEPTED', 'DENIED']
    accepted, = [result for result in results.values() if result.status == 'ACCEPTED']
    denied, = [result for result in results.values() if result.status == 'DENIED']
    assert denied.safe_code == 'STALE_CASE_VERSION' and denied.audit == 'RECORDED' and denied.receipt is None
    _assert_one_approval(flow_engine, case, body, accepted)
    denials = [event for event in _new_audits(flow_engine, before)
        if event['event_type'] == 'FOUNDER_APPROVE_DENIED']
    assert len(denials) == 1
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap,
        results={key:asdict(result) for key, result in results.items()})


@pytest.mark.parametrize('boundary', ['valid', 'expired'])
def test_AP11_approve_and_new_preview_really_overlap_at_the_expiry_boundary(
        flow_engine, identities, enabled, request, monkeypatch, boundary):
    case, original, body = ready(flow_engine, identities)
    expiry = datetime.fromisoformat(original['scope']['expires_at'].replace('Z', '+00:00'))
    at = expiry-timedelta(microseconds=1) if boundary == 'valid' else expiry
    # Both entrants use the same time: no fabricated pair of simultaneously
    # valid old-approval and expired-preview replacement clocks.
    caller = approve(flow_engine, identities, clock=lambda:at)
    producer = preview(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        approve=lambda:caller.accept(case, body, 'preview-race-approve', 'preview-race-corr'),
        preview=lambda:producer.accept(case, body['expected_case_version'], 'preview-race-new', 'preview-race-corr')))
    approved, replaced = results['approve'], results['preview']
    assert sorted(result.status for result in results.values()) == ['ACCEPTED', 'DENIED']
    head, = _case_rows(flow_engine, old.case_heads, case)
    assert head['case_version'] == body['expected_case_version']+1
    if boundary == 'valid':
        _assert_one_approval(flow_engine, case, body, approved)
        assert replaced.status == 'DENIED' and replaced.receipt is None and replaced.audit == 'RECORDED'
        saved, = _case_rows(flow_engine, previews, case)
        assert saved['preview_id'] == original['preview_id'] and saved['consuming_decision_record_id']
    else:
        assert replaced.status == 'ACCEPTED' and approved.status == 'DENIED'
        assert approved.receipt is None and approved.audit == 'RECORDED'
        assert head['status'] == 'AWAITING_APPROVAL'
        saved = sorted(_case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])
        assert len(saved) == 2 and saved[1]['previous_preview_id'] == original['preview_id']
        assert saved[1]['pre_case_version'] == saved[0]['post_case_version']
        assert saved[1]['preview_id'] == replaced.receipt['action_preview']['preview_id']
        assert all(row['consuming_decision_record_id'] is None and row['consumed_at'] is None for row in saved)
        assert not [row for row in _case_rows(flow_engine, old.history, case)
            if row['kind'] in {'DECISION', 'APPROVAL', 'OPERATION', 'NOTIFICATION'}]
        assert not [row for row in _case_rows(flow_engine, lifecycle.work, case)
            if row['purpose'] in {'APPROVAL', 'EXECUTION', 'NOTIFICATION', 'EFFECT'}]
    state, = _case_rows(flow_engine, lifecycle.state, case)
    assert all(state[name] is None for name in ('outcome', 'return_record_id', 'label_record_id', 'notification_work_id'))
    assert not rows(flow_engine, lifecycle.effects) and no_execution_grant(flow_engine)
    evidence(request.node.nodeid, boundary=boundary, shared_clock=at, before=before,
        after=snapshot(flow_engine), overlap=overlap, results={key:asdict(result) for key, result in results.items()})


def test_AP11_real_customer_input_attempt_competes_but_cannot_edit_awaiting_approval(
        flow_engine, identities, enabled, request, monkeypatch):
    case, _, body = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    input_body = dict(expected_case_version=body['expected_case_version'],
        question_set_id='unavailable_question_set', answers=[dict(question_id='unavailable_question',
            text='This input must not alter an awaiting-approval case.')], evidence_ids=[])

    def submit_input():
        try:
            result = identities.flow().clarify(case, input_body, 'input-race-key', 'input-race-correlation')
        except FlowError as error:
            return dict(status='DENIED', safe_code=error.code)
        return dict(status='ACCEPTED', response_status=result.status, body=result.body)

    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        approve=lambda:approve(flow_engine, identities).accept(case, body, 'input-race-approve', 'input-race-correlation'),
        input=submit_input))
    assert results['input']['status'] == 'DENIED'
    assert results['input']['safe_code'] in {'INVALID_STATE', 'STALE_CASE_VERSION'}
    _assert_one_approval(flow_engine, case, body, results['approve'])
    after = snapshot(flow_engine)
    head, = _case_rows(flow_engine, old.case_heads, case)
    original_head, = [row for row in before[old.case_heads.name] if row['case_id'] == case]
    assert head['input_version'] == original_head['input_version']
    for table in (old.intake_sessions, old.intake_work, old.questions):
        assert after[table.name] == before[table.name]
    for name in ('original_statement_records', 'original_statement_contents', old.evidence.name, old.evidence_contents.name):
        assert after[name] == before[name]
    original_history = {row['record_id']:row for row in before[old.history.name]}
    assert {row['record_id']:row for row in after[old.history.name]
        if row['record_id'] in original_history} == original_history
    assert not [row for row in after[old.acceptances.name]
        if row['operation'] == 'submitClarification' and row['target'] == case]
    customer_denials = [event for event in _new_audits(flow_engine, before)
        if event['actor'].get('principal_id') == identities.people['customer_a']['principal_id']]
    assert len(customer_denials) == 1
    assert customer_denials[0]['event_type'] == 'CUSTOMER_TRANSITION_DENIED'
    evidence(request.node.nodeid, before=before, after=after, overlap=overlap,
        approval=asdict(results['approve']), input_result=results['input'],
        actual_boundary='CustomerFlow requires AWAITING_INFORMATION; input never accepted in this state')


@pytest.mark.parametrize('first', ['retention', 'approve'])
def test_AP12_retention_and_approval_serialize_under_the_actual_write_fence(
        flow_engine, identities, enabled, request, monkeypatch, first):
    from returnops_domain.retention import RetentionService
    case, action, body = ready(flow_engine, identities)
    source, = [row for row in _case_rows(flow_engine, old.history, case) if row['kind'] == 'STATEMENT']
    before = snapshot(flow_engine)
    caller = approve(flow_engine, identities)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        approve=lambda:caller.accept(case, body, 'retention-race-approve', 'retention-race-correlation'),
        retention=lambda:RetentionService(flow_engine).remove('STATEMENT', source['object_id'])), first=first)
    assert results['retention'] is True
    approved = results['approve']
    after = snapshot(flow_engine)
    state, = _case_rows(flow_engine, lifecycle.state, case)
    assert state['available'] is False and state['preview_id'] is None and state['approval_record_id'] is None
    saved, = _case_rows(flow_engine, previews, case)
    assert saved['preview_id'] == action['preview_id'] and saved['body'] is None and saved['available'] is False
    assert saved['request_key'] == 'approve-preview-key'
    history = _case_rows(flow_engine, old.history, case)
    decision = [row for row in history if row['kind'] == 'DECISION']
    approval = [row for row in history if row['kind'] == 'APPROVAL']
    work = _case_rows(flow_engine, lifecycle.work, case)
    execution = [row for row in work if row['purpose'] == 'EXECUTION']
    head, = _case_rows(flow_engine, old.case_heads, case)
    facts = [row for row in rows(flow_engine, old.acceptances)
        if row['target'] == case and row['operation'] == 'recordFounderDecision']
    if first == 'retention':
        assert approved.status == 'DENIED' and approved.receipt is None and approved.audit == 'NOT_RECORDED'
        assert not decision and not approval and not execution and not facts
        assert not [row for row in work if row['purpose'] == 'APPROVAL']
        assert head['case_version'] == body['expected_case_version']+1
        assert saved['consuming_decision_record_id'] is None and saved['consumed_at'] is None
    else:
        # The returned acceptance is historical truth. Subsequent retention
        # removes derivative bytes and availability, not the accepted identity.
        assert approved.status == 'ACCEPTED' and approved.receipt['case_version'] == body['expected_case_version']+1
        assert len(decision) == len(approval) == len(execution) == len(facts) == 1
        assert head['case_version'] == body['expected_case_version']+2 and head['status'] == 'APPROVED'
        assert all(row['retention_state'] == 'DELETED' for row in decision+approval)
        assert approval[0]['object_id'] == approved.receipt['approval_id']
        assert decision[0]['object_id'] == approved.receipt['decision_id']
        assert saved['consuming_decision_record_id'] == decision[0]['record_id']
        assert execution[0]['state'] == 'PAUSED' and execution[0]['epoch'] == 1
        assert all(execution[0][field] is None for field in
            ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))
        receipt, = [row for row in rows(flow_engine, old.receipts)
            if row['acceptance_id'] == facts[0]['acceptance_id']]
        assert receipt['body'] is None and receipt['available'] is False
    derivative_ids = {row['record_id'] for row in history
        if row['kind'] in {'STATEMENT', 'PROPOSAL', 'REVIEW', 'DECISION', 'APPROVAL'}}
    assert not [row for row in rows(flow_engine, old.history_contents) if row['record_id'] in derivative_ids]
    assert not [row for row in work if row['purpose'] in {'NOTIFICATION', 'EFFECT'}]
    assert not rows(flow_engine, lifecycle.effects) and no_execution_grant(flow_engine)
    recovered = caller.recover(case, body, 'retention-race-approve')
    replay = caller.accept(case, body, 'retention-race-approve', 'retention-replay-correlation')
    assert recovered.status == 'UNKNOWN' and recovered.receipt is None
    assert replay.status == 'DENIED' and replay.receipt is None and replay.audit == 'NOT_RECORDED'
    assert snapshot(flow_engine) == after
    evidence(request.node.nodeid, first=first, before=before, after=after, overlap=overlap,
        approval=asdict(approved), retention=results['retention'], recovery=asdict(recovered), replay=asdict(replay),
        coordination='Supported retention and approval both hold the same transaction advisory write fence')
