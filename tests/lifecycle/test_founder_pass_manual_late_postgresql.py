"""PMP02/04/05/06/07: full final seals and observed two-backend fences."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import timedelta

import pytest
from sqlalchemy import delete, select, update

from returnops_domain import customer_tables as old, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.preview_tables import previews
from returnops_domain.manual_denial import COMPONENT, OPERATION
from manual_helpers import evidence, rows, snapshot
from pass_manual_helpers import (ready, service, attempt, assert_manual, case_rows,
    mutate_source, mutate_authority, business_snapshot, provision_notification)
from test_founder_approve_late_postgresql import _overlap_at_actual_fence
from test_manual_postgresql import expire_human

business = business_snapshot


def _original_manual_event(engine, case):
    """Only the actual event, original claim and original notification binding."""
    from returnops_domain.lifecycle_events import LifecycleClaim, OutcomeAccepted
    saved, = [row for row in case_rows(engine, t.events, case) if row['event_kind'] == 'OUTCOME']
    work, = [row for row in case_rows(engine, t.work, case) if row['work_id'] == saved['work_id']]
    note, = [row for row in case_rows(engine, t.sources, case)
        if row['work_id'] == work['work_id'] and row['slot'] == 'NOTIFICATION']
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    return OutcomeAccepted(saved['event_id'], claim, saved['record_id'], note['record_id']), saved


@contextmanager
def _observe_manual_review_proofs(monkeypatch, case, event, original, original_work, review_id, control):
    """Transparent real-proof observation; exception objects stay in test memory."""
    from returnops_domain import notification_intent, notification_sources, pass_manual_sources
    from returnops_domain.lifecycle_sources import Sources
    from returnops_domain.notification_profile import COMPONENT as NOTIFIER
    original_control = notification_sources.validate_control
    original_inventory = notification_intent._inventory
    original_read, original_manual = Sources.read, pass_manual_sources.accepted_manual
    observed = dict(stage='apply', controls=[], inventories=[], reads=[], manual=[],
                    active_controls=[], active_inventories=[])

    def entry(group, exact, **extra):
        value = dict(stage=observed['stage'], exact=exact, returned=False, error=None, **extra)
        observed[group].append(value)
        return value

    def invoke(value, function, *args, **kwargs):
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            value['error'] = error
            raise
        value['returned'] = True
        return result

    def validate(uow, head, saved, **kwargs):
        value = entry('controls', head['case_id'] == case and saved['case_id'] == case
            and saved['notification_work_id'] == control['notification_work_id']
            and saved['outcome_record_id'] == event.record_id)
        observed['active_controls'].append(value)
        try:
            return invoke(value, original_control, uow, head, saved, **kwargs)
        finally:
            observed['active_controls'].pop()

    def inventory(uow, head, initial_record_id):
        parent = observed['active_controls'][-1] if observed['active_controls'] else None
        value = entry('inventories', head['case_id'] == case
            and initial_record_id == control['initial_notification_record_id'],
            control=parent)
        observed['active_inventories'].append(value)
        try:
            return invoke(value, original_inventory, uow, head, initial_record_id)
        finally:
            observed['active_inventories'].pop()

    def read(sources, record_id, kinds, **kwargs):
        if record_id != review_id:
            return original_read(sources, record_id, kinds, **kwargs)
        parent = observed['active_inventories'][-1] if observed['active_inventories'] else None
        value = entry('reads', sources.head['case_id'] == case and kinds == {'REVIEW'}
            and kwargs.get('current_actor', True) is False and sources.component_id == NOTIFIER,
            inventory=parent)
        result = invoke(value, original_read, sources, record_id, kinds, **kwargs)
        value['binding_valid'] = (type(result) is tuple and len(result) == 2
            and hasattr(result[0], 'get') and result[0].get('record_id') == review_id
            and result[0].get('case_id') == case and result[0].get('kind') == 'REVIEW')
        return result

    def manual(uow, head, record_id, component):
        value = entry('manual', head['case_id'] == case and record_id == event.record_id
            and component == COMPONENT,
            context='control_outcome' if observed['active_controls'] else 'direct')
        result = invoke(value, original_manual, uow, head, record_id, component)
        value['binding_valid'] = (type(result) is dict and result.get('event') == original
                                  and result.get('work') == original_work)
        return result

    with monkeypatch.context() as scoped:
        scoped.setattr(notification_sources, 'validate_control', validate)
        scoped.setattr(notification_intent, '_inventory', inventory)
        scoped.setattr(Sources, 'read', read)
        scoped.setattr(pass_manual_sources, 'accepted_manual', manual)
        yield observed


def _review_corruption_rejected_by_notification_inventory(flow_engine, identities, request, monkeypatch):
    """Modern positive replay, then the exact damaged-review rejection chain."""
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.notification_tables import controls
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_manual(flow_engine, case, body, accepted, action=action)
    event, original = _original_manual_event(flow_engine, case)
    original_work, = [row for row in case_rows(flow_engine, t.work, case)
                      if row['work_id'] == event.claim.work_id]
    review, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'REVIEW']
    control, = [row for row in rows(flow_engine, controls)
                if row['case_id'] == case and row['outcome_record_id'] == event.record_id]
    with _observe_manual_review_proofs(monkeypatch, case, event, original, original_work,
                                      review['record_id'], control) as observed:
        positive_before = snapshot(flow_engine)
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            assert LifecycleGuards(COMPONENT).apply(uow, event, at) == original
            observed['stage'] = 'commit'
            uow.commit()
        assert snapshot(flow_engine) == positive_before
        assert not observed['active_controls'] and not observed['active_inventories']
        assert observed['controls'] and all(value['exact'] and value['returned']
            and value['error'] is None for value in observed['controls'])
        assert observed['inventories'] and all(value['exact'] and value['returned']
            and value['error'] is None and any(value['control'] is parent for parent in observed['controls'])
            for value in observed['inventories'])
        inventory_reads = [value for value in observed['reads'] if value['inventory'] is not None]
        assert inventory_reads and all(value['exact'] and value['returned'] and value['binding_valid']
            and value['error'] is None and any(value['inventory'] is parent for parent in observed['inventories'])
            for value in inventory_reads)
        assert {value['stage'] for value in inventory_reads} == {'apply', 'commit'}
        assert observed['manual'] and all(value['exact'] and value['returned']
            and value['binding_valid'] and value['error'] is None for value in observed['manual'])
        assert {(value['stage'], value['context']) for value in observed['manual']} >= {
            ('apply', 'control_outcome'), ('apply', 'direct'),
            ('commit', 'control_outcome'), ('commit', 'direct')}
        positive_counts = {group:len(observed[group]) for group in ('controls', 'inventories', 'reads', 'manual')}
        for group in positive_counts:
            observed[group].clear()
        observed['stage'] = 'apply'

        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            assert uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == review['record_id']).values(body=b'{}')).rowcount == 1
            uow.commit()
        before = snapshot(flow_engine)
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            with pytest.raises(FlowError) as denied:
                LifecycleGuards(COMPONENT).apply(uow, event, at)
            observed['stage'] = 'commit'
            with pytest.raises(FlowError) as commit_denied:
                uow.commit()
        assert denied.value.code == commit_denied.value.code == 'INTERNAL_ERROR'
        assert not observed['active_controls'] and not observed['active_inventories']
        assert len(observed['controls']) == len(observed['inventories']) == len(observed['reads']) == 1
        control_error, inventory_error, read_error = (
            observed['controls'][0], observed['inventories'][0], observed['reads'][0])
        assert all(value['exact'] and value['stage'] == 'apply' and not value['returned']
            and value['error'] is denied.value for value in (control_error, inventory_error, read_error))
        assert inventory_error['control'] is control_error and read_error['inventory'] is inventory_error
        assert observed['manual'] == []
        assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), fault='review',
        event=asdict(event), positive_snapshot=positive_before, positive_proof_counts=positive_counts,
        negative_guard_chain=['validate_control', '_inventory', 'Sources.read exact REVIEW'],
        negative_code=denied.value.code, negative_manual_proof_calls=0,
        commit_denial=commit_denied.value.code, entrypoint='LifecycleGuards.apply')


@pytest.mark.parametrize('fault', ['review', 'preview', 'claim'])
def test_PMP05_direct_domain_replay_rejects_corrupt_original_proof(flow_engine, identities, enabled, request, monkeypatch, fault):
    if fault == 'review':
        return _review_corruption_rejected_by_notification_inventory(flow_engine, identities, request, monkeypatch)
    from returnops_domain import pass_manual_sources
    from returnops_domain.lifecycle_guards import LifecycleGuards
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_manual(flow_engine, case, body, accepted, action=action)
    event, _ = _original_manual_event(flow_engine, case)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        if fault == 'review':
            review, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'REVIEW']
            assert uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == review['record_id']).values(body=b'{}')).rowcount == 1
        elif fault == 'preview':
            assert uow.execute(update(previews).where(previews.c.preview_id == action['preview_id']).values(body_hash='0' * 64)).rowcount == 1
        else:
            assert uow.execute(update(t.work).where(t.work.c.work_id == event.claim.work_id).values(claim_id='corrupted_original_claim')).rowcount == 1
        uow.commit()
    original_proof = pass_manual_sources.accepted_manual
    proof_calls = []
    def proof(*args, **kwargs):
        proof_calls.append('direct_domain_accepted_manual')
        return original_proof(*args, **kwargs)
    monkeypatch.setattr(pass_manual_sources, 'accepted_manual', proof)
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        with pytest.raises(FlowError):
            LifecycleGuards(COMPONENT).apply(uow, event, at)
        with pytest.raises(FlowError):
            uow.commit()
    assert proof_calls == ['direct_domain_accepted_manual']
    assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), fault=fault,
        event=asdict(event), proof_calls=proof_calls, entrypoint='LifecycleGuards.apply')



@contextmanager
def _observe_manual_final_replay(monkeypatch, case, event, original, original_work, control, mutate):
    """Forward real calls; arm tampering only at this replay's final direct proof."""
    import sys
    from types import CodeType
    from returnops_domain import notification_sources, pass_manual_sources
    from returnops_domain.lifecycle_guards import LifecycleGuards
    apply_code = LifecycleGuards.apply.__code__
    final_codes = [value for value in apply_code.co_consts
                   if isinstance(value, CodeType) and value.co_name == 'manual_replay_check']
    assert len(final_codes) == 1
    final_code = final_codes[0]
    outcome_code = notification_sources._outcome.__code__
    original_control = notification_sources.validate_control
    original_proof = pass_manual_sources.accepted_manual
    original_actor = pass_manual_sources.check_actor
    original_seal = pass_manual_sources.check_seal
    observed = dict(phase='apply', armed=False, uow=None, active_controls=[],
        controls=[], proofs=[], actors=[], seals=[], proof_calls=[], injections=[],
        eligible=[], actor_checks=[], actor_denials=[], seal_checks=[])

    def entry(group, exact, **fields):
        value = dict(phase=observed['phase'], exact=exact, returned=False, error=None, **fields)
        observed[group].append(value)
        return value

    def invoke(value, callback, *args, **kwargs):
        try:
            result = callback(*args, **kwargs)
        except BaseException as error:
            value['error'] = error
            raise
        value['returned'] = True
        return result

    def bound(seal):
        return type(seal) is dict and seal.get('event') == original and seal.get('work') == original_work

    def validate(uow, head, row, **kwargs):
        value = entry('controls', uow is observed['uow'] and head.get('case_id') == case
                      and type(row) is dict and row == control)
        observed['active_controls'].append(value)
        try:
            return invoke(value, original_control, uow, head, row, **kwargs)
        finally:
            observed['active_controls'].pop()

    def proof(uow, head, record_id, component):
        caller = sys._getframe(1).f_code
        callsite = ('apply' if caller is apply_code else
                    'manual_replay_check' if caller is final_code else
                    'notification_outcome' if caller is outcome_code else 'other')
        parent = observed['active_controls'][-1] if observed['active_controls'] else None
        context = 'control_outcome' if parent is not None else 'direct'
        value = entry('proofs', uow is observed['uow'] and head.get('case_id') == case
            and record_id == event.record_id and component == COMPONENT,
            context=context, callsite=callsite, control=parent, binding_valid=False,
            injected=False, mutation_error=None)
        result = invoke(value, original_proof, uow, head, record_id, component)
        value['binding_valid'] = bound(result)
        if context == 'direct' and callsite in {'apply', 'manual_replay_check'}:
            observed['proof_calls'].append('returned')
        if (observed['armed'] and value['phase'] == 'commit' and context == 'direct'
                and callsite == 'manual_replay_check' and value['exact'] and value['binding_valid']):
            observed['eligible'].append(value)
            if not observed['injections']:
                try:
                    mutate(uow)
                except BaseException as error:
                    value['mutation_error'] = error
                    raise
                value['injected'] = True
                observed['injections'].append('after_final_domain_accepted_manual')
        return result

    def actor(uow, head, seal):
        observed['actor_checks'].append('direct_domain_check_actor')
        value = entry('actors', sys._getframe(1).f_code is final_code
            and uow is observed['uow'] and head.get('case_id') == case and bound(seal))
        try:
            return invoke(value, original_actor, uow, head, seal)
        except FlowError as error:
            observed['actor_denials'].append(error.code)
            raise

    def seal(uow, saved):
        observed['seal_checks'].append('direct_domain_check_seal')
        value = entry('seals', sys._getframe(1).f_code is final_code
            and uow is observed['uow'] and bound(saved))
        return invoke(value, original_seal, uow, saved)

    with monkeypatch.context() as scoped:
        scoped.setattr(notification_sources, 'validate_control', validate)
        scoped.setattr(pass_manual_sources, 'accepted_manual', proof)
        scoped.setattr(pass_manual_sources, 'check_actor', actor)
        scoped.setattr(pass_manual_sources, 'check_seal', seal)
        yield observed


@pytest.mark.parametrize('fault', ['founder_disabled', 'preview_seal'])
def test_PMP05_direct_domain_replay_final_actor_and_seal_checks_reject_and_roll_back(flow_engine, identities, enabled, request, monkeypatch, fault):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.notification_tables import controls
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_manual(flow_engine, case, body, accepted, action=action)
    event, original = _original_manual_event(flow_engine, case)
    original_work, = [row for row in case_rows(flow_engine, t.work, case)
                      if row['work_id'] == event.claim.work_id]
    control, = [row for row in rows(flow_engine, controls)
                if row['case_id'] == case and row['outcome_record_id'] == event.record_id]

    def mutate(uow):
        if fault == 'founder_disabled':
            assert uow.execute(update(old.principals).where(old.principals.c.principal_id ==
                identities.people['founder']['principal_id']).values(enabled=False)).rowcount == 1
        else:
            assert uow.execute(update(previews).where(previews.c.preview_id == action['preview_id']).values(
                request_key='changed_after_domain_final_proof')).rowcount == 1

    with _observe_manual_final_replay(monkeypatch, case, event, original, original_work,
                                      control, mutate) as observed:
        proof_calls, injections = observed['proof_calls'], observed['injections']
        actor_checks, actor_denials, seal_checks = (
            observed['actor_checks'], observed['actor_denials'], observed['seal_checks'])

        def assert_proof_contexts():
            assert not observed['active_controls']
            assert observed['controls'] and all(value['exact'] and value['returned']
                and value['error'] is None for value in observed['controls'])
            assert all(value['exact'] and value['returned'] and value['binding_valid']
                and value['error'] is None and value['mutation_error'] is None for value in observed['proofs'])
            assert {(value['phase'], value['context'], value['callsite']) for value in observed['proofs']} == {
                ('apply', 'control_outcome', 'notification_outcome'), ('apply', 'direct', 'apply'),
                ('commit', 'control_outcome', 'notification_outcome'), ('commit', 'direct', 'manual_replay_check')}
            assert all(any(value['control'] is parent for parent in observed['controls'])
                for value in observed['proofs'] if value['context'] == 'control_outcome')
            assert [value['phase'] for value in observed['proofs'] if value['context'] == 'direct'] == ['apply', 'commit']

        # Real no-tamper apply+commit proves the original receipt and unchanged
        # database before arming either fault, including modern control proofs.
        before = snapshot(flow_engine)
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            observed['uow'] = uow
            assert LifecycleGuards(COMPONENT).apply(uow, event, at) == original
            observed['phase'] = 'commit'
            uow.commit()
        assert snapshot(flow_engine) == before
        assert_proof_contexts()
        assert proof_calls == ['returned', 'returned'] and not injections and not observed['eligible']
        assert actor_checks == ['direct_domain_check_actor'] and not actor_denials
        assert seal_checks == ['direct_domain_check_seal']
        assert all(value['exact'] and value['phase'] == 'commit' and value['returned']
            and value['error'] is None for value in observed['actors'] + observed['seals'])
        positive_counts = {group:len(observed[group]) for group in ('controls', 'proofs', 'actors', 'seals')}
        for group in ('controls', 'proofs', 'actors', 'seals', 'proof_calls', 'injections',
                      'eligible', 'actor_checks', 'actor_denials', 'seal_checks'):
            observed[group].clear()
        observed.update(phase='apply', armed=True, uow=None)

        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            observed['uow'] = uow
            assert LifecycleGuards(COMPONENT).apply(uow, event, at) == original
            assert not injections and not observed['eligible']
            observed['phase'] = 'commit'
            with pytest.raises(FlowError) as denied:
                uow.commit()
            assert denied.value.code == 'INVALID_STATE'
            with pytest.raises(FlowError) as poisoned:
                uow.commit()
        assert_proof_contexts()
        assert proof_calls == ['returned', 'returned']
        assert injections == ['after_final_domain_accepted_manual']
        eligible, = observed['eligible']
        assert eligible['phase'] == 'commit' and eligible['context'] == 'direct'
        assert eligible['callsite'] == 'manual_replay_check' and eligible['injected']
        assert actor_checks == ['direct_domain_check_actor']
        assert actor_denials == (['FORBIDDEN'] if fault == 'founder_disabled' else [])
        assert seal_checks == ([] if fault == 'founder_disabled' else ['direct_domain_check_seal'])
        actor, = observed['actors']
        assert actor['exact'] and actor['phase'] == 'commit'
        if fault == 'founder_disabled':
            assert not actor['returned'] and isinstance(actor['error'], FlowError)
            assert actor['error'].code == 'FORBIDDEN' and not observed['seals']
            inner_error = actor['error']
        else:
            seal, = observed['seals']
            assert actor['returned'] and actor['error'] is None
            assert seal['exact'] and seal['phase'] == 'commit' and not seal['returned']
            assert isinstance(seal['error'], FlowError) and seal['error'].code == 'INVALID_STATE'
            inner_error = seal['error']
        assert denied.value is not inner_error  # UoW converts the callback error.
        assert poisoned.value.code == 'INTERNAL_ERROR' and poisoned.value is not denied.value
        assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), fault=fault, event=asdict(event),
        proof_calls=proof_calls, injections=injections, actor_checks=actor_checks,
        actor_denials=actor_denials, seal_checks=seal_checks, commit_denial=denied.value.code,
        positive_proof_counts=positive_counts, injection_phase='commit',
        injection_callsite='manual_replay_check', inner_denial=inner_error.code,
        poisoned_commit_denial=poisoned.value.code,
        entrypoint='LifecycleGuards.apply original event; no browser authority or service replay used')



def _after_service_history_proof(monkeypatch, mutate, *, replay=False):
    """Patch only the service alias; independent lower Domain checks remain."""
    from returnops_domain import manual_decision
    original = manual_decision.accepted_manual
    injected = []
    calls = []
    def proof(uow, *args, **kwargs):
        result = original(uow, *args, **kwargs)
        calls.append('returned')
        # New acceptance and replay each save an initial proof, then re-read
        # it in their final callback. Inject after that final re-read returns.
        if len(calls) == 2:
            mutate(uow, result)
            injected.append('after_service_accepted_manual')
        return result
    monkeypatch.setattr(manual_decision, 'accepted_manual', proof)
    return injected



@pytest.mark.parametrize('mode', ['raw_statement', 'evidence_raw', 'order_projection', 'review_binding'])
def test_PMP02_current_sources_are_reread_after_historical_proof(flow_engine, identities, enabled, request, monkeypatch, mode):
    case, body, _, at = ready(flow_engine, identities)
    injected = _after_service_history_proof(monkeypatch, lambda uow, seal:mutate_source(uow, mode))
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert injected == ['after_service_accepted_manual']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, source_fault=mode)



@pytest.mark.parametrize('mode', ['human_revoked', 'human_disabled', 'human_demoted', 'human_store', 'owner',
    'service_revoked', 'service_revision', 'claim', 'epoch', 'authority', 'lease_renewal',
    'human_expiry', 'service_clock', 'guard_clock'])
def test_PMP04_expensive_history_read_is_followed_by_fresh_authority_and_lease(flow_engine, identities, enabled, request, monkeypatch, mode):
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
    assert injected == ['after_service_accepted_manual']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, fault=mode)



@pytest.mark.parametrize('entry', ['accept', 'recover'])
@pytest.mark.parametrize('mode', ['fact_key', 'fact_fingerprint', 'fact_time', 'receipt_body', 'receipt_unavailable', 'receipt_delete'])
def test_PMP05_replay_final_fact_and_receipt_seals(flow_engine, identities, enabled, request, monkeypatch, entry, mode):
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    accepted = caller.accept(case, body, 'pass-manual-key', 'first_revision')
    assert_manual(flow_engine, case, body, accepted, action=action)
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
    result = (caller.accept(case, body, 'pass-manual-key', 'late_replay') if entry == 'accept'
        else caller.recover(case, body, 'pass-manual-key'))
    assert injected == ['after_service_accepted_manual']
    assert result.status == ('DENIED' if entry == 'accept' else 'UNKNOWN') and result.receipt is None
    assert business(snapshot(flow_engine)) == business(before)
    if entry == 'recover':
        assert snapshot(flow_engine) == before
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, fault=mode)



def _pmp06_result(value):
    """Closed result projection; never retain the receipt or arbitrary strings."""
    status = getattr(value, 'status', None)
    code = getattr(value, 'safe_code', None)
    audit = getattr(value, 'audit', None)
    return dict(
        status=status if type(status) is str and status in {'ACCEPTED', 'DENIED', 'UNKNOWN'} else 'OTHER_STATUS',
        safe_code=code if type(code) is str and code in {
            'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'VALIDATION_ERROR',
            'STALE_CASE_VERSION', 'IDEMPOTENCY_CONFLICT', 'INVALID_STATE',
            'REQUEST_TOO_LARGE', 'UNSUPPORTED_MEDIA_TYPE', 'INTERNAL_ERROR'} else None,
        audit=audit if type(audit) is str and audit in {
            'NOT_ATTEMPTED', 'RECORDED', 'NOT_RECORDED', 'UNKNOWN'} else 'OTHER_AUDIT',
        receipt_present=getattr(value, 'receipt', None) is not None)


def _pmp06_lines(diagnostic):
    """Project bounded ASCII records again at the output boundary."""
    import json
    maximum = (1 << 63) - 1
    stages = {'create_control', 'validate_control', 'inventory', 'case_proof',
              'notification_descriptor', 'notification_ownership'}
    event_names = {'fence_call', 'fence_return', 'fence_error', 'commit_call',
                   'native_commit_begin', 'uow_commit_return', 'uow_commit_error'}
    error_types = {'OperationalError', 'InterfaceError', 'DBAPIError', 'FlowError',
                   'AssertionError', 'AcceptanceOutcomeUnknown', 'OTHER_EXCEPTION'}

    def number(value, upper=maximum, lower=0):
        return value if type(value) is int and lower <= value <= upper else None

    def enum(value, choices):
        return value if type(value) is str and value in choices else None

    def entries(value, limit):
        return value[:limit] if type(value) is list else []

    def error(value):
        state = value.get('sqlstate')
        if (type(state) is not str or len(state) != 5
                or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for c in state)):
            state = None
        return dict(error_type=enum(value.get('error_type'), error_types), sqlstate=state)

    if type(diagnostic) is not dict:
        diagnostic = {}
    transactions = diagnostic.get('transactions')
    events = diagnostic.get('events')
    results = diagnostic.get('results')
    costs = diagnostic.get('costs')
    if type(costs) is not dict:
        costs = {}
    cost_rows = costs.get('rows')
    records = [('FENCE_DIAGNOSTIC', dict(kind='summary',
        overflow_count=number(diagnostic.get('overflow_count')),
        observer_error_count=number(diagnostic.get('observer_error_count')),
        cleanup_incomplete=diagnostic.get('cleanup_incomplete') if type(diagnostic.get('cleanup_incomplete')) is bool else None,
        output_truncated=any(type(value) is list and len(value) > limit
            for value, limit in ((transactions, 8), (events, 64), (cost_rows, 54)))))]
    for row in entries(transactions, 8):
        if type(row) is not dict:
            continue
        records.append(('FENCE_DIAGNOSTIC', dict(kind='transaction',
            token=number(row.get('token'), 8, 1),
            label=enum(row.get('label'), {'holder', 'first', 'second', 'unknown'}),
            phase=enum(row.get('phase'), {'holder', 'accept', 'denial', 'unknown'}),
            backend_pid=number(row.get('backend_pid'), 2147483647, 1),
            hold_lower_bound_ns=number(row.get('hold_lower_bound_ns')),
            hold_upper_bound_ns=number(row.get('hold_upper_bound_ns')),
            commit_checks_inclusive_ns=number(row.get('commit_checks_inclusive_ns')))))
    for row in entries(events, 64):
        if type(row) is not dict or enum(row.get('event'), event_names) is None:
            continue
        records.append(('FENCE_DIAGNOSTIC', dict(kind='event',
            token=number(row.get('token'), 8, 1), event=row['event'],
            monotonic_ns=number(row.get('monotonic_ns')), **error(row))))
    if type(results) is dict:
        for label in ('first', 'second'):
            row = results.get(label)
            if type(row) is not dict:
                continue
            records.append(('FENCE_DIAGNOSTIC', dict(kind='result', label=label,
                status=enum(row.get('status'), {'ACCEPTED', 'DENIED', 'UNKNOWN', 'OTHER_STATUS'}),
                safe_code=enum(row.get('safe_code'), {
                    'UNAUTHENTICATED', 'FORBIDDEN', 'NOT_FOUND', 'VALIDATION_ERROR',
                    'STALE_CASE_VERSION', 'IDEMPOTENCY_CONFLICT', 'INVALID_STATE',
                    'REQUEST_TOO_LARGE', 'UNSUPPORTED_MEDIA_TYPE', 'INTERNAL_ERROR'}),
                audit=enum(row.get('audit'), {
                    'NOT_ATTEMPTED', 'RECORDED', 'NOT_RECORDED', 'UNKNOWN', 'OTHER_AUDIT'}),
                receipt_present=row.get('receipt_present') if type(row.get('receipt_present')) is bool else None,
                **error(row))))
    records.append(('FENCE_COST', dict(kind='summary', inclusive_totals_overlap=True,
        overflow_count=number(costs.get('overflow_count')),
        observer_error_count=number(costs.get('observer_error_count')))))
    for row in entries(cost_rows, 54):
        if type(row) is not dict or enum(row.get('stage'), stages) is None:
            continue
        token = number(row.get('token'), 8, 1)
        pid = number(row.get('backend_pid'), 2147483647, 1) if token is not None else None
        records.append(('FENCE_COST', dict(kind='stage', stage=row['stage'], token=token,
            backend_pid=pid, binding_unavailable=token is None or pid is None,
            count=number(row.get('count')), inclusive_ns=number(row.get('inclusive_ns')),
            unmeasured_count=number(row.get('unmeasured_count')))))
    records[0][1]['output_truncated'] |= len(records) > 128
    output = []
    for prefix, value in records[:128]:
        line = 'RETURNOPS_PMP06_' + prefix + ' ' + json.dumps(value, sort_keys=True, ensure_ascii=True)
        if not line.isascii() or len(line) > 1024:
            raise ValueError('PMP06 diagnostic bound')
        output.append(line)
    return output


def _pmp06_emit(capsys, diagnostic):
    """Even a broken formatter/capture/output cannot replace the real failure."""
    def failed():
        try:
            count = diagnostic.get('observer_error_count')
            diagnostic['observer_error_count'] = min((1 << 63) - 1,
                (count if type(count) is int and count >= 0 else 0) + 1)
        except BaseException:
            pass
    try:
        lines = _pmp06_lines(diagnostic)
    except BaseException:
        failed()
        lines = ['RETURNOPS_PMP06_FENCE_DIAGNOSTIC {"kind":"formatter_error","observer_error_count":1}']
    try:
        with capsys.disabled():
            for line in lines:
                print(line, flush=True)
    except BaseException:
        failed()


def _pmp06_observed_overlap(engine, monkeypatch, calls, diagnostic):
    """Observe only this existing race; forward every operation exactly once.

    No SQL, UoW, barrier, polling, timeout or retry is added. Connection and
    actual transaction identity distinguish lifetimes, including pooled PIDs.
    Cost totals are inclusive and overlap. All observations are best effort.
    """
    from threading import Lock, local
    from time import monotonic_ns
    from sqlalchemy import event as sqlalchemy_event
    from returnops_domain import customer_uow, manual_decision
    from test_founder_approve_late_postgresql import _install_fence_cost_observer, _safe_fence_error
    maximum = (1 << 63) - 1
    mutex, context = Lock(), local()
    transactions, transaction_rows, events, results = {}, [], [], {}
    counters = dict(overflow_count=0, observer_error_count=0)
    original_fence = customer_uow.acquire_fence
    original_commit = CustomerUnitOfWork.commit
    original_denial = manual_decision.record_denial
    overlap = None
    snapshot_costs = None
    manager = None
    listener_attempted = False

    def bump(name):
        try:
            with mutex:
                counters[name] = min(maximum, counters[name] + 1)
        except BaseException:
            # A failed recorder must not interrupt or mask the actual call.
            try:
                counters['observer_error_count'] = min(maximum, counters['observer_error_count'] + 1)
            except BaseException:
                pass

    def observe(callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except BaseException:
            bump('observer_error_count')
            return None

    def transaction(connection):
        if connection is None or connection.engine is not engine:
            return None
        current = connection.get_transaction()  # Local SQLAlchemy state; no SQL.
        if current is None:
            return None
        with mutex:
            previous = transactions.get(connection)
            if previous is not None and previous['_transaction'] is current:
                return previous
            if len(transaction_rows) >= 8:
                counters['overflow_count'] = min(maximum, counters['overflow_count'] + 1)
                transactions.pop(connection, None)
                return None
            label = getattr(context, 'label', 'holder')
            phase = getattr(context, 'phase', 'holder')
            row = dict(token=len(transaction_rows) + 1,
                label=label if label in {'holder', 'first', 'second'} else 'unknown',
                phase=phase if phase in {'holder', 'accept', 'denial'} else 'unknown',
                backend_pid=None, _transaction=current)
            transactions[connection] = row
            transaction_rows.append(row)
            return row

    def record(row, name, **fields):
        stamp = monotonic_ns()
        if type(stamp) is not int or not 0 <= stamp <= maximum:
            raise ValueError('PMP06 clock bound')
        with mutex:
            if len(events) == 64:
                counters['overflow_count'] = min(maximum, counters['overflow_count'] + 1)
                return
            events.append(dict(token=row['token'] if row is not None else None,
                               event=name, monotonic_ns=stamp, **fields))

    def fence(connection, *, write):
        if not observe(lambda: connection.engine is engine):
            return original_fence(connection, write=write)
        row = observe(transaction, connection)
        observe(record, row, 'fence_call')
        try:
            result = original_fence(connection, write=write)
        except BaseException as error:
            fields = observe(_safe_fence_error, error) or {}
            observe(record, row, 'fence_error', **fields)
            raise
        observe(record, row, 'fence_return')
        return result

    def commit(uow):
        connection = observe(lambda: uow.connection)
        if not observe(lambda: connection.engine is engine):
            return original_commit(uow)
        row = observe(transaction, connection)
        observe(record, row, 'commit_call')
        try:
            result = original_commit(uow)
        except BaseException as error:
            fields = observe(_safe_fence_error, error) or {}
            observe(record, row, 'uow_commit_error', **fields)
            raise
        # Keep the original token after native commit ends the transaction.
        observe(record, row, 'uow_commit_return')
        return result

    def commit_begin(connection):
        if not observe(lambda: connection.engine is engine):
            return
        row = observe(transaction, connection)
        observe(record, row, 'native_commit_begin')

    def denial(*args, **kwargs):
        target = args[0] if args else kwargs.get('engine')
        if target is not engine:
            return original_denial(*args, **kwargs)
        previous = observe(lambda: getattr(context, 'phase', 'unknown'))
        observe(setattr, context, 'phase', 'denial')
        try:
            return original_denial(*args, **kwargs)
        finally:
            observe(setattr, context, 'phase', previous)

    def save_result(label, value):
        if label in {'first', 'second'}:
            with mutex:
                results[label] = value

    def invoke(label, call):
        observe(setattr, context, 'label', label)
        observe(setattr, context, 'phase', 'accept')
        try:
            value = call()
        except BaseException as error:
            observe(save_result, label, observe(_safe_fence_error, error) or {})
            raise
        else:
            observe(save_result, label, observe(_pmp06_result, value) or {})
            return value
        finally:
            observe(delattr, context, 'label')
            observe(delattr, context, 'phase')

    class Patches:
        """Also restore attempted patches if pytest installation/undo raises."""
        def __init__(self, scoped):
            self.scoped, self.saved = scoped, []

        def setattr(self, owner, name, value):
            if len(self.saved) >= 16:
                bump('overflow_count')
                raise RuntimeError('PMP06 patch bound')
            self.saved.append((owner, name, getattr(owner, name)))
            if self.scoped is None:
                setattr(owner, name, value)
            else:
                self.scoped.setattr(owner, name, value)

        def restore(self):
            for owner, name, value in reversed(self.saved):
                observe(setattr, owner, name, value)
            self.saved.clear()

    patches = Patches(None)

    def cleanup():
        nonlocal listener_attempted, manager
        if listener_attempted:
            observe(sqlalchemy_event.remove, engine, 'commit', commit_begin)
            # A partial registration or a failed removal is local observer
            # cleanup, never a second business attempt.
            present = observe(sqlalchemy_event.contains, engine, 'commit', commit_begin)
            if present:
                observe(sqlalchemy_event.remove, engine, 'commit', commit_begin)
            listener_attempted = observe(sqlalchemy_event.contains, engine, 'commit', commit_begin) is not False
        if manager is not None:
            observe(manager.__exit__, None, None, None)
            manager = None
        patches.restore()

    def freeze():
        # The unchanged overlap helper joins workers before return or raise.
        if type(overlap) is dict:
            participants = overlap.get('participants')
            holder = overlap.get('holder_backend_pid')
            if (type(participants) is list and len(participants) == 2
                    and all(type(item) in {tuple, list} and len(item) == 2
                        and type(item[0]) is str and item[0] in {'first', 'second'}
                        and type(item[1]) is int and 1 <= item[1] <= 2147483647 for item in participants)
                    and {item[0] for item in participants} == {'first', 'second'}
                    and type(holder) is int and 1 <= holder <= 2147483647
                    and len({holder, *(item[1] for item in participants)}) == 3):
                for label, pid in [('holder', holder), *participants]:
                    phase = 'holder' if label == 'holder' else 'accept'
                    row = next((row for row in transaction_rows
                                if row['label'] == label and row['phase'] == phase), None)
                    if row is not None:
                        row['backend_pid'] = pid
            else:
                bump('observer_error_count')
        projected = []
        for row in transaction_rows:
            value = {key: row[key] for key in ('token', 'label', 'phase', 'backend_pid')}
            times = {}
            for item in events:
                if item['token'] == row['token']:
                    times.setdefault(item['event'], []).append(item['monotonic_ns'])
            names = ('fence_call', 'fence_return', 'commit_call', 'native_commit_begin', 'uow_commit_return')
            if (all(len(times.get(name, [])) == 1 for name in names)
                    and not {'fence_error', 'uow_commit_error'} & times.keys()):
                start, acquired, checking, releasing, returned = (times[name][0] for name in names)
                if start <= acquired <= checking <= releasing <= returned:
                    value.update(hold_lower_bound_ns=releasing-acquired,
                        hold_upper_bound_ns=returned-start, commit_checks_inclusive_ns=releasing-checking)
            projected.append(value)
        costs = observe(snapshot_costs) if snapshot_costs is not None else None
        if type(costs) is dict and type(costs.get('rows')) is list:
            # Retained transaction tokens also cover a reused Connection object.
            known = {row['token']: row['backend_pid'] for row in transaction_rows}
            for row in costs['rows'][:54]:
                if type(row) is dict:
                    row['backend_pid'] = known.get(row.get('token'))
        diagnostic.update(format=1, transactions=projected, events=list(events),
                          results=dict(results), costs=costs, **counters)

    try:
        try:
            manager = monkeypatch.context()
            scoped = manager.__enter__()
            patches = Patches(scoped)
            patches.setattr(customer_uow, 'acquire_fence', fence)
            patches.setattr(CustomerUnitOfWork, 'commit', commit)
            patches.setattr(manual_decision, 'record_denial', denial)
            snapshot_costs = _install_fence_cost_observer(patches, transactions, mutex)
            listener_attempted = True
            sqlalchemy_event.listen(engine, 'commit', commit_begin)
        except BaseException:
            bump('observer_error_count')
            observe(cleanup)
            # Failed observation installation never causes a second business
            # attempt. Run the original helper once with a fresh local scope.
            patches = Patches(None)
            snapshot_costs = None
        result, overlap = _overlap_at_actual_fence(engine, patches,
            {label: (lambda label=label, call=call: invoke(label, call))
             for label, call in calls.items()})
        return result, overlap
    finally:
        observe(cleanup)
        observe(freeze)
        # Even an unavailable freeze exposes a bounded observation error count.
        observe(diagnostic.update, cleanup_incomplete=listener_attempted, **counters)


@pytest.mark.parametrize('same_key', [True, False])
def test_PMP06_two_actual_backends_have_one_manual_intent(flow_engine, identities, enabled, request, monkeypatch, same_key, capsys):
    case, body, action, at = ready(flow_engine, identities)
    before = snapshot(flow_engine)
    keys = {'first':'shared_revision', 'second':'shared_revision' if same_key else 'second_revision'}
    calls = {name:(lambda name=name:service(flow_engine, identities, clock=lambda:at).accept(
        case, body, keys[name], 'concurrent_revision')) for name in keys}
    diagnostic = {}
    try:
        results, overlap = _pmp06_observed_overlap(flow_engine, monkeypatch, calls, diagnostic)
        assert sorted(result.status for result in results.values()) == (['ACCEPTED', 'ACCEPTED'] if same_key else ['ACCEPTED', 'DENIED'])
    except BaseException:
        _pmp06_emit(capsys, diagnostic)
        raise
    accepted = next(result for result in results.values() if result.status == 'ACCEPTED')
    assert_manual(flow_engine, case, body, accepted, before=before, action=action)
    if same_key:
        assert results['first'].receipt == results['second'].receipt
    else:
        denied, = [result for result in results.values() if result.status == 'DENIED']
        assert denied.safe_code == 'STALE_CASE_VERSION' and denied.audit == 'RECORDED'
    assert len([row for row in rows(flow_engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]) == 1
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap,
        results={name:asdict(result) for name,result in results.items()})



@pytest.mark.parametrize('first', ['manual', 'preview'])
def test_PMP06_expired_preview_replacement_and_manual_serialize(flow_engine, identities, enabled, request, monkeypatch, first):
    from approve_helpers import preview
    case, body, action, at = ready(flow_engine, identities, preview_mode='equal')
    caller = service(flow_engine, identities, clock=lambda:at)
    producer = preview(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        manual=lambda:caller.accept(case, body, 'expiry_revision', 'expiry_race'),
        preview=lambda:producer.accept(case, body['expected_case_version'], 'replacement_preview', 'expiry_race')), first=first)
    assert results[first].status == 'ACCEPTED'
    second = 'preview' if first == 'manual' else 'manual'
    assert results[second].status == 'DENIED' and results[second].receipt is None
    if first == 'manual':
        assert_manual(flow_engine, case, body, results['manual'], before=before, action=action)
    else:
        assert results['manual'].safe_code == 'STALE_CASE_VERSION'
        chain = sorted(case_rows(flow_engine, previews, case), key=lambda row:row['post_case_version'])
        assert len(chain) == 2 and chain[1]['previous_preview_id'] == action['preview_id']
        assert all(row['consuming_decision_record_id'] is None for row in chain)
        assert not [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
        assert not [row for row in case_rows(flow_engine, t.work, case) if row['purpose'] == 'OUTCOME']
    assert not rows(flow_engine, t.effects)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap, clock=at,
        results={name:asdict(result) for name,result in results.items()})


@pytest.mark.parametrize('later_notification', [False, True])
# Historical v1 synthetic delivery compatibility; actual v2 delivery has separate oracles.
@pytest.mark.parametrize('flow_engine',['0013_label_artifact_result'],indirect=True)
def test_PMP05_direct_domain_original_event_replay_is_read_only(flow_engine, identities, enabled, request, later_notification):
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from synthetic_sources import notify
    case, body, action, at = ready(flow_engine, identities)
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_manual(flow_engine, case, body, accepted, action=action)
    event, original = _original_manual_event(flow_engine, case)
    if later_notification:
        provision_notification(flow_engine, identities)
        notify(flow_engine, identities, case, 'SENT', component=COMPONENT)
    before = snapshot(flow_engine)
    with CustomerUnitOfWork(flow_engine, write=True) as uow:
        replay = LifecycleGuards(COMPONENT).apply(uow, event, at)
        assert replay == original
        uow.commit()
    assert snapshot(flow_engine) == before
    saved, = case_rows(flow_engine, previews, case)
    assert saved['preview_id'] == action['preview_id'] and saved['consuming_decision_record_id'] == event.record_id
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), event=asdict(event),
        replay=replay, later_notification=later_notification,
        entrypoint='LifecycleGuards.apply; no service accept/recover during replay')


@pytest.mark.parametrize('mode', ['notification_binding', 'notification_body', 'notification_work',
    'decision_binding', 'decision_body', 'review_encoding', 'proposal_encoding', 'outcome_event'])
def test_PMP04_after_expensive_proof_small_original_rows_remain_sealed(flow_engine, identities, enabled, request, monkeypatch, mode):
    from returnops_domain import founder_tables
    case, body, _, at = ready(flow_engine, identities)
    def change(uow, seal):
        if mode == 'notification_binding':
            changed = uow.execute(update(t.sources).where(t.sources.c.record_id == seal['notification_record']['record_id']).values(
                target_record_id=seal['review']['record']['record_id']))
        elif mode in {'notification_body', 'decision_body'}:
            row = seal['notification_record'] if mode == 'notification_body' else seal['record']
            changed = uow.execute(update(old.history_contents).where(old.history_contents.c.record_id == row['record_id']).values(body=b'{}'))
        elif mode == 'notification_work':
            changed = uow.execute(update(t.work).where(t.work.c.work_id == seal['notification_work']['work_id']).values(target_hash='0' * 64))
        elif mode == 'decision_binding':
            changed = uow.execute(update(t.sources).where(t.sources.c.record_id == seal['record']['record_id']).values(
                target_record_id=seal['review']['proposal']['record']['record_id']))
        elif mode.endswith('_encoding'):
            row = seal['review']['record'] if mode == 'review_encoding' else seal['review']['proposal']['record']
            changed = uow.execute(update(founder_tables.encodings).where(founder_tables.encodings.c.record_id == row['record_id']).values(
                projected_content_sha256='0' * 64))
        else:
            changed = uow.execute(update(t.events).where(t.events.c.event_id == seal['event']['event_id']).values(fingerprint='0' * 64))
        assert changed.rowcount == 1
    injected = _after_service_history_proof(monkeypatch, change)
    before = snapshot(flow_engine)
    result = attempt(flow_engine, identities, case, body, at)
    assert injected == ['after_service_accepted_manual']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result), injected=injected, fault=mode)


@pytest.mark.parametrize('mode', ['human_revoked', 'human_disabled', 'service_revoked', 'service_revision',
    'claim', 'epoch', 'authority', 'lease_renewal', 'service_clock', 'guard_clock', 'preview_seal', 'head_version'])
def test_PMP04_last_current_proof_is_followed_by_fresh_authority_lease_and_seals(flow_engine, identities, enabled, request, monkeypatch, mode):
    from returnops_domain import manual_decision
    case, body, action, at = ready(flow_engine, identities)
    caller = service(flow_engine, identities, clock=lambda:at)
    original = manual_decision.check_current
    injections = []
    def current(uow, *args, **kwargs):
        result = original(uow, *args, **kwargs)
        if mode in {'service_clock', 'guard_clock'}:
            owner = caller if mode == 'service_clock' else caller.guard
            owner.clock = lambda:at + timedelta(seconds=1000)
        elif mode == 'preview_seal':
            assert uow.execute(update(previews).where(previews.c.preview_id == action['preview_id']).values(
                request_key='changed_after_final_current_proof')).rowcount == 1
        elif mode == 'head_version':
            assert uow.execute(update(old.case_heads).where(old.case_heads.c.case_id == case).values(
                case_version=body['expected_case_version'] + 7)).rowcount == 1
        else:
            mutate_authority(uow, identities, case, mode)
        injections.append('after_service_check_current')
        return result
    monkeypatch.setattr(manual_decision, 'check_current', current)
    before = snapshot(flow_engine)
    result = caller.accept(case, body, 'late_current_manual', 'late_current_manual')
    assert injections == ['after_service_check_current']
    assert result.status == 'DENIED' and business(snapshot(flow_engine)) == business(before)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), result=asdict(result),
        injections=injections, fault=mode)


@pytest.mark.parametrize('competitor', ['approve', 'reject', 'revision'])
@pytest.mark.parametrize('first', ['manual', 'competitor'])
def test_PMP06_other_founder_decisions_compete_in_both_real_fence_orders(flow_engine, identities, enabled, request, monkeypatch, competitor, first):
    from approve_helpers import approve, provision as provision_approval, assert_approved_without_effects
    from reject_helpers import service as reject, provision as provision_reject, assert_rejected
    from pass_revision_helpers import service as revise, provision as provision_revision, assert_revised
    case, body, action, at = ready(flow_engine, identities)
    if competitor == 'approve':
        provision_approval(flow_engine, identities)
        other = approve(flow_engine, identities, clock=lambda:at)
        other_body = {**body, 'decision':'APPROVE', 'preview_id':action['preview_id'],
            'scope_fingerprint':action['scope_fingerprint']}
    elif competitor == 'reject':
        provision_reject(flow_engine, identities)
        other = reject(flow_engine, identities, clock=lambda:at)
        other_body = {**body, 'decision':'REJECT'}
    else:
        provision_revision(flow_engine, identities)
        other = revise(flow_engine, identities, clock=lambda:at)
        other_body = {**body, 'decision':'REQUEST_REVISION'}
    caller = service(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        manual=lambda:caller.accept(case, body, 'race_manual', 'decision_race'),
        competitor=lambda:other.accept(case, other_body, 'race_other', 'decision_race')), first=first)
    assert results[first].status == 'ACCEPTED'
    loser = 'competitor' if first == 'manual' else 'manual'
    assert results[loser].status == 'DENIED' and results[loser].receipt is None
    assert results[loser].safe_code == 'STALE_CASE_VERSION'
    if first == 'manual':
        assert_manual(flow_engine, case, body, results['manual'], before=before, action=action)
    elif competitor == 'approve':
        assert_approved_without_effects(flow_engine, case, other_body, results['competitor'])
    elif competitor == 'reject':
        assert_rejected(flow_engine, case, other_body, results['competitor'])
    else:
        assert_revised(flow_engine, case, other_body, results['competitor'], before=before, action=action)
    decision, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
    saved, = case_rows(flow_engine, previews, case)
    assert saved['consuming_decision_record_id'] == decision['record_id']
    assert not rows(flow_engine, t.effects)
    evidence(request.node.nodeid, before=before, after=snapshot(flow_engine), overlap=overlap,
        results={name:asdict(result) for name,result in results.items()})


@pytest.mark.parametrize('removed', ['STATEMENT', 'EVIDENCE'])
@pytest.mark.parametrize('first', ['retention', 'manual'])
def test_PMP07_retention_and_manual_both_actual_fence_orders(flow_engine, identities, enabled, request, monkeypatch, removed, first):
    from returnops_domain.retention import RetentionService
    case, body, action, at = ready(flow_engine, identities)
    source, = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == removed]
    caller = service(flow_engine, identities, clock=lambda:at)
    before = snapshot(flow_engine)
    results, overlap = _overlap_at_actual_fence(flow_engine, monkeypatch, dict(
        manual=lambda:caller.accept(case, body, 'retained_manual', 'retention_race'),
        retention=lambda:RetentionService(flow_engine).remove(removed, source['object_id'])), first=first)
    assert results['retention'] is True
    result = results['manual']
    after = snapshot(flow_engine)
    saved, = case_rows(flow_engine, previews, case)
    prior = next(row for row in before[previews.name] if row['preview_id'] == saved['preview_id'])
    assert saved['preview_id'] == action['preview_id'] and saved['body'] is None and saved['available'] is False
    assert saved['body_hash'] == prior['body_hash'] and saved['audit_hash'] == prior['audit_hash']
    assert saved['request_key'] == prior['request_key']
    state, = case_rows(flow_engine, t.state, case)
    assert state['available'] is False and state['preview_id'] is None
    decisions = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'DECISION']
    notes = [row for row in case_rows(flow_engine, old.history, case) if row['kind'] == 'NOTIFICATION']
    works = [row for row in case_rows(flow_engine, t.work, case) if row['component_id'] == COMPONENT]
    if first == 'retention':
        assert result.status == 'DENIED' and result.audit == 'NOT_RECORDED' and not decisions and not notes and not works
        assert saved['consuming_decision_record_id'] is None and saved['consumed_at'] is None
    else:
        assert result.status == 'ACCEPTED'
        decision, = decisions
        note, = notes
        assert decision['retention_state'] == note['retention_state'] == 'DELETED'
        assert decision['object_id'] == result.receipt['decision_id']
        assert saved['consuming_decision_record_id'] == decision['record_id']
        assert saved['consumed_at'] == decision['recorded_at']
        notification, = [row for row in works if row['purpose'] == 'NOTIFICATION']
        assert notification['state'] == 'PAUSED' and notification['epoch'] == 1
        assert all(notification[field] is None for field in
            ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))
        fact, = [row for row in rows(flow_engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]
        receipt, = [row for row in rows(flow_engine, old.receipts) if row['acceptance_id'] == fact['acceptance_id']]
        assert receipt['body'] is None and receipt['available'] is False
    derivative_ids = {row['record_id'] for row in case_rows(flow_engine, old.history, case)
        if row['kind'] in {'PROPOSAL', 'REVIEW', 'DECISION', 'NOTIFICATION'}}
    assert not [row for row in rows(flow_engine, old.history_contents) if row['record_id'] in derivative_ids]
    assert not rows(flow_engine, t.effects)
    assert not [row for row in case_rows(flow_engine, t.work, case) if row['purpose'] in {'EXECUTION', 'EFFECT'}]
    recovery = caller.recover(case, body, 'retained_manual')
    replay = caller.accept(case, body, 'retained_manual', 'retained_replay')
    assert recovery.status == 'UNKNOWN' and replay.status == 'DENIED'
    assert recovery.receipt is None and replay.receipt is None and snapshot(flow_engine) == after
    evidence(request.node.nodeid, before=before, after=after, overlap=overlap, manual=asdict(result),
        retention=results['retention'], recovery=asdict(recovery), replay=asdict(replay))


def test_PMP07_founder_current_and_historical_reads_preserve_business(flow_engine, identities, enabled, request):
    from returnops_api.customer_authority import CurrentRequestAuthority
    from returnops_domain.founder_service import FounderQueries
    case, body, action, at = ready(flow_engine, identities, outcome='PASS_WITH_WARNING')
    accepted = attempt(flow_engine, identities, case, body, at)
    assert_manual(flow_engine, case, body, accepted, action=action)
    reader = FounderQueries(flow_engine, CurrentRequestAuthority(identities.auth_config, 'Bearer ' + identities.tokens['founder']))
    before = snapshot(flow_engine)
    detail = reader.read('getFounderCase', case).body
    assert detail['current_review']['outcome'] == 'PASS_WITH_WARNING' and detail['current_review']['findings']
    for kind in ('PROPOSAL', 'REVIEW', 'DECISION', 'NOTIFICATION'):
        reader.read('listFounderCaseHistory', case, {'kind':kind})
    reader.read('listCaseAudit', case)
    after = snapshot(flow_engine)
    assert {k:v for k,v in before.items() if not k.startswith('founder_')} == {
        k:v for k,v in after.items() if not k.startswith('founder_')}
    evidence(request.node.nodeid, before=before, after=after, detail=detail, acceptance=asdict(accepted))
