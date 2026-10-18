"""TEST ONLY accepted PASS prerequisites for separate HUMAN manual handling."""
from datetime import timedelta

from sqlalchemy import delete, select, update

from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.manual_denial import COMPONENT, OPERATION
from returnops_domain.preview_tables import previews
from manual_helpers import assert_pending, provision_outcome, rows, service, snapshot, now
from pass_revision_helpers import (ready as revision_ready, business_snapshot, case_rows,
    mutate_source as retained_source_fault, mutate_preview)


def ready(engine, identities, *, outcome='PASS', preview_mode='valid', replacements=0, grant=True):
    case, body, action, at = revision_ready(engine, identities, outcome=outcome,
        preview_mode=preview_mode, replacements=replacements, grant=False)
    body = {**body, 'decision':'MANUAL_HANDLING',
        'reason':'The Founder will handle this exact retained passed proposal manually.'}
    if grant:
        provision_outcome(engine, identities)
    assert not [row for row in rows(engine, t.authorities) if row['purpose'] == 'REVISION']
    return case, body, action, at


def attempt(engine, identities, case, body, at, **options):
    return service(engine, identities, clock=lambda:at, **options).accept(
        case, body, 'pass-manual-key', 'pass_manual_correlation')


def provision_notification(engine, identities):
    """Only later explicit synthetic notification tests use this authority."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
            component_id=COMPONENT, purpose='NOTIFICATION', revision=1, enabled=True))
        uow.commit()


def assert_manual(engine, case, body, result, *, before=None, action=None):
    assert_pending(engine, case, body, result)
    head, = case_rows(engine, old.case_heads, case)
    state, = case_rows(engine, t.state, case)
    assert state['outcome'] == 'MANUAL_HANDLED'
    assert state['proposal_record_id'] and state['review_record_id']
    assert all(state[name] is None for name in
        ('preview_id', 'approval_record_id', 'return_record_id', 'label_record_id'))
    work, = [row for row in case_rows(engine, t.work, case)
        if row['component_id'] == COMPONENT and row['purpose'] == 'OUTCOME']
    notification, = [row for row in case_rows(engine, t.work, case)
        if row['component_id'] == COMPONENT and row['purpose'] == 'NOTIFICATION']
    assert work['state'] == 'DONE' and work['epoch'] == 1 and work['authority_revision'] == 1
    assert work['claim_id'] and work['lease_expires_at'] is None
    assert work['generation'] == state['generation'] and work['input_version'] == head['input_version']
    assert notification['state'] == 'PENDING' and notification['epoch'] == 0
    assert all(notification[name] is None for name in
        ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))
    assert notification['work_id'] == state['notification_work_id'] and notification['idempotency_key']
    decision, = [row for row in case_rows(engine, old.history, case) if row['kind'] == 'DECISION']
    note, = [row for row in case_rows(engine, old.history, case) if row['kind'] == 'NOTIFICATION']
    assert state['outcome_record_id'] == decision['record_id'] and state['notification_record_id'] == note['record_id']
    assert result.receipt['decision_id'] == decision['object_id'] and result.receipt['decision'] == 'MANUAL_HANDLING'
    event, = [row for row in case_rows(engine, t.events, case) if row['event_kind'] == 'OUTCOME']
    assert event['record_id'] == decision['record_id'] and event['work_id'] == work['work_id']
    assert event['pre_case_version'] == body['expected_case_version'] and event['case_version'] == head['case_version']
    binding, = [row for row in case_rows(engine, t.sources, case) if row['record_id'] == decision['record_id']]
    note_binding, = [row for row in case_rows(engine, t.sources, case) if row['record_id'] == note['record_id']]
    assert binding['target_record_id'] == state['review_record_id'] and binding['slot'] == 'PRIMARY'
    assert note_binding['target_record_id'] == decision['record_id'] and note_binding['slot'] == 'NOTIFICATION'
    assert binding['work_id'] == note_binding['work_id'] == work['work_id']
    fact, = [row for row in rows(engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]
    receipt, = [row for row in rows(engine, old.receipts) if row['acceptance_id'] == fact['acceptance_id']]
    assert receipt['available'] and receipt['body'] is not None
    assert not rows(engine, t.effects)
    assert not [row for row in case_rows(engine, t.work, case) if row['purpose'] in {'EXECUTION', 'EFFECT'}]
    saved = case_rows(engine, previews, case)
    consumed = [row for row in saved if row['consuming_decision_record_id'] is not None]
    assert len(consumed) == int(action is not None)
    if action is not None:
        tail, = consumed
        assert tail['preview_id'] == action['preview_id'] and tail['post_case_version'] == body['expected_case_version']
        assert tail['consuming_decision_record_id'] == decision['record_id']
        assert tail['consumed_at'] == decision['recorded_at'] == event['accepted_at'] == fact['accepted_at']
    if before is not None:
        old_head, = [row for row in before[old.case_heads.name] if row['case_id'] == case]
        old_state, = [row for row in before[t.state.name] if row['case_id'] == case]
        assert head['input_version'] == old_head['input_version']
        assert all(state[name] == old_state[name] for name in
            ('generation', 'input_version', 'proposal_version', 'proposal_record_id', 'review_record_id'))
        after = snapshot(engine)
        assert after[t.authorities.name] == before[t.authorities.name]
        for name in ('original_statement_records', 'original_statement_contents', old.evidence.name,
                old.evidence_contents.name, inv.projections.name, inv.projection_contents.name,
                inv.receipts.name, inv.receipt_contents.name):
            assert after[name] == before[name]
        old_history = {row['record_id']:row for row in before[old.history.name]}
        assert {row['record_id']:row for row in after[old.history.name]
            if row['record_id'] in old_history} == old_history
        original_previews = {row['preview_id']:row for row in before[previews.name]}
        for row in after[previews.name]:
            if row['preview_id'] in original_previews:
                prior = original_previews[row['preview_id']]
                excluded = {'consuming_decision_record_id', 'consumed_at'}
                assert {k:v for k,v in row.items() if k not in excluded} == {
                    k:v for k,v in prior.items() if k not in excluded}


def mutate_authority(uow, identities, case, mode):
    if mode.startswith('human_') or mode == 'owner':
        from test_manual_postgresql import mutate_authority as human
        return human(uow, identities, case, mode)
    if mode == 'service_missing':
        changed = uow.execute(delete(t.authorities).where(t.authorities.c.component_id == COMPONENT,
            t.authorities.c.purpose == 'OUTCOME'))
    elif mode in {'service_revoked', 'service_revision'}:
        changed = uow.execute(update(t.authorities).where(t.authorities.c.component_id == COMPONENT,
            t.authorities.c.purpose == 'OUTCOME').values(**(
                {'enabled':False} if mode == 'service_revoked' else {'revision':2})))
    else:
        values = {'claim':{'claim_id':'replaced_claim'}, 'epoch':{'epoch':9},
            'lease':{'lease_expires_at':now()}, 'authority':{'authority_revision':2},
            'generation':{'generation':9}, 'lease_renewal':{'lease_expires_at':now() + timedelta(hours=1)}}[mode]
        changed = uow.execute(update(t.work).where(t.work.c.component_id == COMPONENT,
            t.work.c.purpose == 'OUTCOME').values(**values))
    assert changed.rowcount == 1


def mutate_source(uow, mode):
    if mode == 'review_alternate_family':
        review = uow.execute(select(old.history.c.record_id).where(old.history.c.kind == 'REVIEW')).scalar_one()
        assert uow.execute(update(t.events).where(t.events.c.record_id == review).values(event_kind='REVIEW')).rowcount == 1
    else:
        retained_source_fault(uow, mode)


def accepted_pass_manual(engine, identities, *, notification_grant=True):
    """Real accepted no-preview prerequisites for existing notification tests.

    Rehydrate the actual original Domain event and receipt after private HUMAN
    acceptance. This never converts a legacy raw fixture into a modern source.
    """
    from returnops_domain.lifecycle_events import LifecycleClaim, OutcomeAccepted
    case, body, action, at = ready(engine, identities, preview_mode='none')
    assert not [row for row in rows(engine, t.authorities) if row['purpose'] == 'NOTIFICATION']
    before = snapshot(engine)
    result = attempt(engine, identities, case, body, at)
    assert_manual(engine, case, body, result, before=before, action=action)
    saved, = [row for row in case_rows(engine, t.events, case) if row['event_kind'] == 'OUTCOME']
    work, = [row for row in case_rows(engine, t.work, case) if row['work_id'] == saved['work_id']]
    note, = [row for row in case_rows(engine, t.sources, case)
        if row['work_id'] == work['work_id'] and row['slot'] == 'NOTIFICATION']
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    event = OutcomeAccepted(saved['event_id'], claim, saved['record_id'], note['record_id'])
    if notification_grant:
        provision_notification(engine, identities)
    return case, event, dict(saved), COMPONENT


def prove_pass_manual_target(uow, case, request):
    """Prove the actual current source independently of the causal Founder."""
    from returnops_domain.lifecycle_state import current
    from returnops_domain.manual_target import read_target, one
    from returnops_domain.pass_manual_sources import read_preview
    head = one(uow, old.case_heads, case_id=case)
    state = current(uow, head)
    source = read_target(uow, head, state, request, COMPONENT)
    assert source['event']['event_kind'] == 'REVIEW_PASS'
    assert read_preview(uow, head, state, request['expected_case_version']) is None
    return head, source


def stage_pass_manual_event(uow, identities, case, request, at):
    """TEST ONLY legal internal staging for the direct causal-actor guard.

    A real retained PASS is mandatory. The production append routine supplies
    the original HUMAN/SERVICE audits; one aware timestamp and the actual
    OUTCOME claim bind both records. No state, review or target is fabricated.
    The caller invokes LifecycleGuards.apply and must control the transaction.
    """
    from dataclasses import asdict
    from returnops_domain.audit import identifier, timestamp
    from returnops_domain.lifecycle_events import OutcomeAccepted
    from returnops_domain.lifecycle_guards import LifecycleGuards
    from returnops_domain.manual_decision import FounderDecisionService
    from returnops_domain.pass_manual_sources import MESSAGE
    head, source = prove_pass_manual_target(uow, case, request)
    assert at.utcoffset() is not None and at >= source['event']['accepted_at']
    guard = LifecycleGuards(COMPONENT, clock=lambda:at)
    work = guard.prepare(uow, case, request['expected_case_version'], OutcomeAccepted, at)
    claim = guard.claim(uow, work, at)
    assert claim is not None
    principal = identities.people['founder']['principal_id']
    correlation = identifier('causal_manual')
    decision = dict(decision_id=identifier('manual_decision'), case_id=case,
        decision='MANUAL_HANDLING', principal_id=principal, reason=request['reason'],
        decided_at=timestamp(at), proposal_id=request['proposal_id'], proposal_version=request['proposal_version'])
    decision_id, decision_hash = FounderDecisionService._append(uow, case, 'DECISION', decision,
        {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':principal}, correlation, at)
    uow.execute(t.sources.insert().values(record_id=decision_id, case_id=case, **asdict(claim),
        source_hash=decision_hash, target_record_id=source['record']['record_id'], slot='PRIMARY'))
    note = dict(notification_id=identifier('manual_notification'), case_id=case,
        case_version=head['case_version'], status='PENDING', outcome='MANUAL_HANDLED',
        message=MESSAGE, next_steps=[], attempt_count=0, updated_at=timestamp(at))
    note_id, note_hash = FounderDecisionService._append(uow, case, 'NOTIFICATION', note,
        {'kind':'SERVICE', 'component_id':COMPONENT}, correlation, at)
    uow.execute(t.sources.insert().values(record_id=note_id, case_id=case, **asdict(claim),
        source_hash=note_hash, target_record_id=decision_id, slot='NOTIFICATION'))
    return guard, OutcomeAccepted(identifier('causal_manual_event'), claim, decision_id, note_id)
