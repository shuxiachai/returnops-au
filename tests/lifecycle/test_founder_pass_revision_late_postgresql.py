"""RVP02/04/05/06/07 final seals and actual two-backend fence races.

Fault injection occurs inside a trusted test transaction. Races use the existing
actual pg_stat_activity advisory-wait observer, never elapsed time as evidence.
"""
from dataclasses import asdict
from datetime import timedelta
import json

import pytest
from sqlalchemy import delete, select, update

from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.preview_tables import previews
from returnops_domain.revision_denial import COMPONENT, OPERATION
from manual_helpers import business, evidence, rows, snapshot
from pass_revision_helpers import (ready, service, attempt, assert_revised, case_rows,
    mutate_source, mutate_authority)
from test_founder_approve_late_postgresql import _overlap_at_actual_fence, _fence_cost_lines
from test_manual_postgresql import expire_human


def _original_revision_event(engine, case):
    """Rehydrate only the actual saved event and original accepted claim."""
    from returnops_domain.lifecycle_events import LifecycleClaim, RevisionRequested
    saved, = [row for row in case_rows(engine, t.events, case) if row['event_kind'] == 'REVISION']
    work, = [row for row in case_rows(engine, t.work, case) if row['work_id'] == saved['work_id']]
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    return RevisionRequested(saved['event_id'], claim, saved['record_id']), saved


@pytest.mark.parametrize('later_generation', [False, True])
def test_RVP05_direct_domain_original_preview_revision_replay_is_read_only(flow_engine, identities, enabled, request, later_generation):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.proposal_processor import FixedProposalProcessor
    from pass_review_helpers import build_positive, receiver
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, accepted, action=action)
    event, original = _original_revision_event(flow_engine, case)
    if later_generation:
        processor = FixedProposalProcessor(flow_engine, build=build_positive)
        assert processor.process(processor.prepare(case)).status == 'ACCEPTED'
        head, = case_rows(flow_engine, old.case_heads, case)
        assert receiver(flow_engine).accept(case, head['case_version'], 'domain-later-review', 'domain_later_review').status == 'ACCEPTED'
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        replay = LifecycleGuards(COMPONENT).apply(uow, event, at)
        assert replay == original
        uow.commit()
    assert snapshot(flow_engine) == before
    preview, = case_rows(flow_engine, previews, case)
    assert preview['preview_id'] == action['preview_id'] and preview['consuming_decision_record_id'] == event.record_id
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), event=asdict(event),
        replay=replay, later_generation=later_generation, entrypoint='LifecycleGuards.apply; no service accept/recover during replay')


@pytest.mark.parametrize('fault', ['review', 'preview', 'claim'])
def test_RVP05_direct_domain_replay_rejects_corrupt_original_proof(flow_engine, identities, enabled, request, monkeypatch, fault):
    from returnops_domain import revision_sources
    from returnops_domain.lifecycle_guards import LifecycleGuards
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, accepted, action=action)
    event, _ = _original_revision_event(flow_engine, case)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if fault == 'review':
            review, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'REVIEW']
            assert uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == review['record_id']).values(body=b'{}')).rowcount == 1
        elif fault == 'preview':
            assert uow.execute(update(previews).where(previews.c.preview_id == action['preview_id']).values(body_hash='0' * 64)).rowcount == 1
        else:
            assert uow.execute(update(t.work).where(t.work.c.work_id == event.claim.work_id).values(claim_id='corrupted_original_claim')).rowcount == 1
        uow.commit()
    original_proof = revision_sources.accepted_revision
    proof_calls = []
    def proof(*args, **kwargs):
        proof_calls.append('direct_domain_accepted_revision')
        return original_proof(*args, **kwargs)
    monkeypatch.setattr(revision_sources, 'accepted_revision', proof)
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        with pytest.raises(FlowError):
            LifecycleGuards(COMPONENT).apply(uow, event, at)
        with pytest.raises(FlowError):
            uow.commit()
    assert proof_calls == ['direct_domain_accepted_revision']
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), fault=fault,
        event=asdict(event), proof_calls=proof_calls, entrypoint='LifecycleGuards.apply')


@pytest.mark.parametrize('fault', ['founder_disabled', 'preview_seal'])
def test_RVP05_direct_domain_replay_final_actor_and_seal_checks_reject_and_roll_back(flow_engine, identities, enabled, request, monkeypatch, fault):
    from returnops_domain import revision_sources
    from returnops_domain.lifecycle_guards import LifecycleGuards
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, accepted, action=action)
    event, original = _original_revision_event(flow_engine, case)
    original_proof = revision_sources.accepted_revision
    original_actor = revision_sources.check_actor
    original_seal = revision_sources.check_seal
    proof_calls, injections, actor_checks, actor_denials, seal_checks = [], [], [], [], []
    def proof(uow, *args, **kwargs):
        result = original_proof(uow, *args, **kwargs)
        proof_calls.append('returned')
        if len(proof_calls) == 2:
            if fault == 'founder_disabled':
                assert uow.execute(update(old.principals).where(old.principals.c.principal_id ==
                    identities.people['founder']['principal_id']).values(enabled=False)).rowcount == 1
            else:
                assert uow.execute(update(previews).where(previews.c.preview_id == action['preview_id']).values(
                    request_key='changed_after_domain_final_proof')).rowcount == 1
            injections.append('after_final_domain_accepted_revision')
        return result
    def actor(*args, **kwargs):
        actor_checks.append('direct_domain_check_actor')
        try:
            return original_actor(*args, **kwargs)
        except FlowError as error:
            actor_denials.append(error.code)
            raise
    def seal(*args, **kwargs):
        seal_checks.append('direct_domain_check_seal')
        return original_seal(*args, **kwargs)
    monkeypatch.setattr(revision_sources, 'accepted_revision', proof)
    monkeypatch.setattr(revision_sources, 'check_actor', actor)
    monkeypatch.setattr(revision_sources, 'check_seal', seal)
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        assert LifecycleGuards(COMPONENT).apply(uow, event, at) == original
        with pytest.raises(FlowError) as denied:
            uow.commit()
        assert denied.value.code == 'INVALID_STATE'
        with pytest.raises(FlowError):
            uow.commit()
    assert proof_calls == ['returned', 'returned']
    assert injections == ['after_final_domain_accepted_revision']
    assert actor_checks == ['direct_domain_check_actor']
    assert actor_denials == (['FORBIDDEN'] if fault == 'founder_disabled' else [])
    assert seal_checks == ([] if fault == 'founder_disabled' else ['direct_domain_check_seal'])
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), fault=fault, event=asdict(event),
        proof_calls=proof_calls, injections=injections, actor_checks=actor_checks,
        actor_denials=actor_denials, seal_checks=seal_checks, commit_denial=denied.value.code,
        entrypoint='LifecycleGuards.apply original event; no browser authority or service replay used')


def _after_service_history_proof(monkeypatch, mutate, *, replay=False):
    """Patch only the service alias; independent lower Domain checks remain."""
    from returnops_domain import revision_decision
    original = revision_decision.accepted_revision
    injected = []
    calls = []
    def proof(uow, *args, **kwargs):
        result = original(uow, *args, **kwargs)
        calls.append('returned')
        # New acceptance and replay each save an initial proof, then re-read
        # it in their final callback. Inject after that final re-read returns.
        if len(calls) == 2:
            mutate(uow, result)
            injected.append('after_service_accepted_revision')
        return result
    monkeypatch.setattr(revision_decision, 'accepted_revision', proof)
    return injected


@pytest.mark.parametrize('mode', ['raw_statement', 'evidence_raw', 'order_projection', 'review_binding'])
def test_RVP02_current_sources_are_reread_after_historical_proof(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body, _, at = ready(flow_engine, identities)
    injected = _after_service_history_proof(monkeypatch, lambda uow, seal:mutate_source(uow, mode))
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert injected == ['after_service_accepted_revision']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, source_fault=mode)


@pytest.mark.parametrize('mode', ['human_revoked', 'human_disabled', 'human_demoted', 'human_store', 'owner',
    'service_revoked', 'service_revision', 'claim', 'epoch', 'authority', 'lease_renewal',
    'human_expiry', 'service_clock', 'guard_clock'])
def test_RVP04_expensive_history_read_is_followed_by_fresh_authority_and_lease(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body, _, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    def change(uow, seal):
        if mode == 'human_expiry':
            expire_human(monkeypatch)
        elif mode == 'service_clock':
            caller.clock = lambda:at + timedelta(seconds=1000)
        elif mode == 'guard_clock':
            caller.guard.clock = lambda:at + timedelta(seconds=1000)
        elif mode == 'lease_renewal':
            assert uow.execute(update(t.work).where(t.work.c.work_id == seal['work']['work_id']).values(
                lease_expires_at=at + timedelta(hours=1))).rowcount == 1
        else:
            mutate_authority(uow, identities, case, mode)
    injected = _after_service_history_proof(monkeypatch, change)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'late-revision-key', 'late_revision')
    assert injected == ['after_service_accepted_revision']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, fault=mode)


@pytest.mark.parametrize('entry', ['accept', 'recover'])
@pytest.mark.parametrize('mode', ['fact_key', 'fact_fingerprint', 'fact_time', 'receipt_body', 'receipt_unavailable', 'receipt_delete'])
def test_RVP05_replay_final_fact_and_receipt_seals(flow_engine, identities, enabled, request, monkeypatch, entry, mode):
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'pass-revision-key', 'first_revision')
    assert_revised(flow_engine, case, body, accepted, action=action)
    def change(uow, seal):
        fact = uow.execute(select(old.acceptances).where(old.acceptances.c.target == case,
            old.acceptances.c.operation == OPERATION)).mappings().one()
        if mode.startswith('fact_'):
            changes = {'fact_key':dict(request_key='replaced_original_key'),
                'fact_fingerprint':dict(fingerprint='0' * 64),
                'fact_time':dict(accepted_at=fact['accepted_at'] + timedelta(seconds=1))}[mode]
            assert uow.execute(update(old.acceptances).where(old.acceptances.c.acceptance_id == fact['acceptance_id']).values(**changes)).rowcount == 1
        elif mode == 'receipt_delete':
            assert uow.execute(delete(old.receipts).where(old.receipts.c.acceptance_id == fact['acceptance_id'])).rowcount == 1
        else:
            changes = dict(body=b'{}') if mode == 'receipt_body' else dict(body=None, available=False)
            assert uow.execute(update(old.receipts).where(old.receipts.c.acceptance_id == fact['acceptance_id']).values(**changes)).rowcount == 1
    injected = _after_service_history_proof(monkeypatch, change, replay=True)
    before = snapshot(flow_engine)
    result = (caller.accept(case, body, 'pass-revision-key', 'late_replay') if entry == 'accept'
        else caller.recover(case, body, 'pass-revision-key'))
    assert injected == ['after_service_accepted_revision']
    assert result.status == ('DENIED' if entry == 'accept' else 'UNKNOWN') and result.receipt is None
    assert business(snapshot(flow_engine)) == business(before)
    if entry == 'recover':
        assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, fault=mode)


@pytest.mark.parametrize('same_key', [True, False])
def test_RVP06_two_actual_backends_have_one_revision_intent(flow_engine, identities, enabled, request, monkeypatch, same_key):
    case, body, action, at = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    keys = {'first':'shared_revision', 'second':'shared_revision' if same_key else 'second_revision'}
    calls = {name:(lambda name=name:service(flow_engine, identities, clock=lambda:at).accept(
        case, body, keys[name], 'concurrent_revision')) for name in keys}
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, calls)
    assert sorted(result.status for result in results.values()) == (['ACCEPTED', 'ACCEPTED'] if same_key else ['ACCEPTED', 'DENIED'])
    accepted = next(result for result in results.values() if result.status == 'ACCEPTED')
    assert_revised(flow_engine, case, body, accepted, before=before, action=action)
    if same_key:
        assert results['first'].receipt == results['second'].receipt
    else:
        denied, = [result for result in results.values() if result.status == 'DENIED']
        assert denied.safe_code == 'STALE_CASE_VERSION' and denied.audit == 'RECORDED'
    assert len([row for row in rows(flow_engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]) == 1
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap,
        results={name:asdict(result) for name,result in results.items()})


@pytest.mark.parametrize('competitor', ['approve', 'reject'])
@pytest.mark.parametrize('first', ['revision', 'competitor'])
def test_RVP06_founder_decisions_compete_in_both_real_fence_orders(flow_engine, identities, enabled, request, monkeypatch, competitor, first, capsys):
    from approve_helpers import approve, provision as provision_approval, assert_approved_without_effects
    from reject_helpers import service as reject, provision as provision_reject, assert_rejected
    case, body, action, at = ready(flow_engine, identities)
    if competitor == 'approve':
        provision_approval(flow_engine, identities)
        other = approve(flow_engine, identities, clock=lambda:at)
        other_body = {**body, 'decision':'APPROVE', 'preview_id':action['preview_id'],
            'scope_fingerprint':action['scope_fingerprint']}
    else:
        provision_reject(flow_engine, identities)
        other = reject(flow_engine, identities, clock=lambda:at)
        other_body = {**body, 'decision':'REJECT'}
    caller = service(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    diagnostic = {}
    cost_diagnostic = {}
    try:
        results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
            revision=lambda:caller.accept(case, body, 'race_revision', 'decision_race'),
            competitor=lambda:other.accept(case, other_body, 'race_other', 'decision_race')),
            first=first, diagnostic=diagnostic, cost=True, cost_diagnostic=cost_diagnostic)
    finally:
        # Emit safe timing evidence even if the original assertion fails. The
        # existing evidence file still carries the complete successful result.
        diagnostic['competitor_kind'] = competitor
        with capsys.disabled():
            for line in _fence_cost_lines(cost_diagnostic):
                print(line, flush=True)
            print('RETURNOPS_REVISION_FENCE_OBSERVATION ' + json.dumps(diagnostic, sort_keys=True), flush=True)
    assert results[first].status == 'ACCEPTED'
    loser = 'competitor' if first == 'revision' else 'revision'
    assert results[loser].status == 'DENIED' and results[loser].receipt is None
    assert results[loser].safe_code == 'STALE_CASE_VERSION'
    if first == 'revision':
        assert_revised(flow_engine, case, body, results['revision'], before=before, action=action)
    elif competitor == 'approve':
        assert_approved_without_effects(flow_engine, case, other_body, results['competitor'])
    else:
        assert_rejected(flow_engine, case, other_body, results['competitor'])
    decision, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
    saved, = case_rows(flow_engine, previews, case)
    assert saved['consuming_decision_record_id'] == decision['record_id']
    assert not rows(flow_engine, t.effects)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap,
        results={name:asdict(result) for name,result in results.items()})


@pytest.mark.parametrize('first', ['revision', 'preview'])
def test_RVP06_expired_preview_replacement_and_revision_serialize(flow_engine, identities, enabled, request, monkeypatch, first):
    from approve_helpers import preview
    case, body, action, at = ready(flow_engine, identities, preview_mode='equal')
    caller = service(flow_engine, identities, clock=lambda:at)
    producer = preview(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        revision=lambda:caller.accept(case, body, 'expiry_revision', 'expiry_race'),
        preview=lambda:producer.accept(case, body['expected_case_version'], 'replacement_preview', 'expiry_race')), first=first)
    assert results[first].status == 'ACCEPTED'
    second = 'preview' if first == 'revision' else 'revision'
    assert results[second].status == 'DENIED' and results[second].receipt is None
    if first == 'revision':
        assert_revised(flow_engine, case, body, results['revision'], before=before, action=action)
    else:
        assert results['revision'].safe_code == 'STALE_CASE_VERSION'
        chain = sorted(case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])
        assert len(chain) == 2 and chain[1]['previous_preview_id'] == action['preview_id']
        assert all(row['consuming_decision_record_id'] is None for row in chain)
        assert not [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
        assert not [row for row in case_rows(flow_engine, t.work, case) if row['purpose'] == 'REVISION']
    assert not rows(flow_engine, t.effects)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap, clock=at,
        results={name:asdict(result) for name,result in results.items()})


@pytest.mark.parametrize('removed', ['STATEMENT', 'EVIDENCE'])
@pytest.mark.parametrize('first', ['retention', 'revision'])
def test_RVP07_retention_and_revision_both_actual_fence_orders(flow_engine, identities, enabled, request, monkeypatch, removed, first):
    from returnops_domain.retention import RetentionService
    case, body, action, at = ready(flow_engine, identities)
    source, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == removed]
    caller = service(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        revision=lambda:caller.accept(case, body, 'retained_revision', 'retention_race'),
        retention=lambda:RetentionService(flow_engine).remove(removed, source['object_id'])), first=first)
    assert results['retention'] is True
    result = results['revision']
    after = snapshot(flow_engine)
    saved, = case_rows(flow_engine, previews, case)
    prior = next(row for row in before[previews.name] if row['preview_id'] == saved['preview_id'])
    assert saved['preview_id'] == action['preview_id'] and saved['body'] is None and saved['available'] is False
    assert saved['body_hash'] == prior['body_hash'] and saved['audit_hash'] == prior['audit_hash']
    assert saved['request_key'] == prior['request_key']
    state, = case_rows(flow_engine, t.state, case)
    assert state['available'] is False and state['preview_id'] is None
    decisions = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
    if first == 'retention':
        assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and not decisions
        assert saved['consuming_decision_record_id'] is None and saved['consumed_at'] is None
        assert not [row for row in case_rows(flow_engine, t.work, case) if row['purpose'] == 'REVISION']
    else:
        assert result.status == 'ACCEPTED'
        decision, = decisions
        assert decision['retention_state'] == 'DELETED' and decision['object_id'] == result.receipt['decision_id']
        assert saved['consuming_decision_record_id'] == decision['record_id']
        assert saved['consumed_at'] == decision['recorded_at']
        fact, = [row for row in rows(flow_engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]
        receipt, = [row for row in rows(flow_engine, old.receipts) if row['acceptance_id'] == fact['acceptance_id']]
        assert receipt['body'] is None and receipt['available'] is False
    derivative_ids = {row['record_id'] for row in case_rows(flow_engine, old.history, case)
        if row['kind'] in {'PROPOSAL', 'REVIEW', 'DECISION'}}
    assert not [row for row in rows(flow_engine, old.history_contents) if row['record_id'] in derivative_ids]
    assert not rows(flow_engine, t.effects)
    assert not [row for row in case_rows(flow_engine, t.work, case) if row['purpose'] in {'EXECUTION', 'NOTIFICATION', 'EFFECT'}]
    recovery = caller.recover(case, body, 'retained_revision')
    replay = caller.accept(case, body, 'retained_revision', 'retained_replay')
    assert recovery.status == 'UNKNOWN' and replay.status == 'DENIED'
    assert recovery.receipt is None and replay.receipt is None and snapshot(flow_engine) == after
    evidence(request.node.nodeid, before=before, after=after, overlap=overlap, revision=asdict(result),
        retention=results['retention'], recovery=asdict(recovery), replay=asdict(replay))


def test_RVP07_founder_reads_current_and_retained_history_without_business_writes(flow_engine, identities, enabled, request):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_revised(flow_engine, case, body, accepted, action=action)
    reader = FounderQueries(flow_engine, CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens['founder']))
    before = snapshot(flow_engine)
    detail = reader.read('getFounderCase', case).body
    assert 'current_review' not in detail and 'current_proposal' not in detail
    for kind in ('PROPOSAL', 'REVIEW', 'DECISION'):
        reader.read('listFounderCaseHistory', case, {'kind':kind})
    reader.read('listCaseAudit', case)
    after = snapshot(flow_engine)
    assert {k:v for k,v in before.items() if not k.startswith('founder_')} == {k:v for k,v in after.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid, before=before, after=after, detail=detail, acceptance=asdict(accepted))
