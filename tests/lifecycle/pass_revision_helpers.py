"""TEST ONLY real PASS, preview and Founder revision acceptance fixtures."""
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import select, update

from returnops_domain import customer_tables as old, investigation_tables as inv, lifecycle_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.preview_profile import COMPONENT as PREVIEW
from returnops_domain.preview_tables import previews
from returnops_domain.revision_denial import COMPONENT, OPERATION
from approve_helpers import preview
from manual_helpers import business as legacy_business, rows, now
from pass_review_helpers import ControlledPassReviewer, ready_pass, receiver
from revision_helpers import provision, service, mutate_authority
from reject_helpers import mutate_source as retained_fault


def case_rows(engine, table, case):
    return [row for row in rows(engine, table) if row['case_id'] == case]


def business_snapshot(value):
    """Keep every business row/field, ordering heads after audit exclusion.

    The shared snapshot sorts full rows before its business projection removes
    audit_head/audit_sequence. An allowed denial audit can therefore change two
    heads' order without changing either business row. Sort the complete
    remaining rows, preserving duplicates and every original business field.
    """
    projected = legacy_business(value)
    projected[old.case_heads.name] = sorted(projected[old.case_heads.name],
        key=lambda row:json.dumps(row, sort_keys=True))
    return projected


def provision_preview(engine, identities):
    """Only PREVIEW is needed by fixture creation; no APPROVAL/EXECUTION grant."""
    with CustomerUnitOfWork(engine, write=True) as uow:
        if not uow.execute(select(t.authorities).where(t.authorities.c.component_id == PREVIEW,
                t.authorities.c.purpose == 'PREVIEW')).first():
            uow.execute(t.authorities.insert().values(store_id=identities.people['founder']['store_id'],
                component_id=PREVIEW, purpose='PREVIEW', revision=1, enabled=True))
        uow.commit()


def ready(engine, identities, *, outcome='PASS', preview_mode='valid', replacements=0, grant=True):
    case, version = ready_pass(engine, identities)
    review = receiver(engine, ControlledPassReviewer(outcome)).accept(
        case, version, 'pass-revision-review', 'pass_revision_review')
    assert review.status == 'ACCEPTED', review
    version += 1
    if grant:
        provision(engine, identities)
    action = None
    at = now()
    if preview_mode != 'none':
        provision_preview(engine, identities)
        for index in range(replacements + 1):
            result = preview(engine, identities, clock=lambda:at).accept(
                case, version, 'pass-revision-preview-' + str(index), 'pass_revision_preview')
            assert result.status == 'ACCEPTED', result
            action = result.receipt['action_preview']
            version += 1
            expiry = datetime.fromisoformat(action['scope']['expires_at'].replace('Z', '+00:00'))
            at = expiry
        saved = next(row for row in case_rows(engine, previews, case)
            if row['preview_id'] == action['preview_id'])
        at = {'valid':saved['issued_at'] + timedelta(microseconds=1),
              'equal':saved['expires_at'], 'expired':saved['expires_at'] + timedelta(seconds=1)}[preview_mode]
    proposal, = [row for row in case_rows(engine, old.history, case) if row['kind'] == 'PROPOSAL']
    body = dict(expected_case_version=version, proposal_id=proposal['object_id'],
        proposal_version=proposal['object_version'], decision='REQUEST_REVISION',
        reason='Please reassess this exact retained passed proposal.')
    return case, body, action, at


def attempt(engine, identities, case, body, at, **options):
    return service(engine, identities, clock=lambda:at, **options).accept(
        case, body, 'pass-revision-key', 'pass_revision_correlation')


def assert_revised(engine, case, body, result, *, before=None, action=None):
    assert result.status == 'ACCEPTED', (result.status, result.safe_code, result.audit)
    head, = case_rows(engine, old.case_heads, case)
    state, = case_rows(engine, t.state, case)
    assert head['status'] == 'POLICY_ASSESSMENT'
    assert head['case_version'] == body['expected_case_version'] + 1
    assert all(state[name] is None for name in ('proposal_record_id', 'review_record_id', 'preview_id',
        'approval_record_id', 'outcome_record_id', 'outcome', 'return_record_id', 'label_record_id',
        'notification_id', 'notification_hash', 'notification_record_id', 'notification_work_id'))
    work, = [row for row in case_rows(engine, t.work, case) if row['component_id'] == COMPONENT]
    assert work['purpose'] == 'REVISION' and work['state'] == 'DONE' and work['epoch'] == 1
    assert work['claim_id'] and work['authority_revision'] == 1 and work['lease_expires_at'] is None
    assert state['generation'] == work['generation'] + 1 and head['input_version'] == work['input_version']
    decision, = [row for row in case_rows(engine, old.history, case) if row['kind'] == 'DECISION']
    assert result.receipt['decision_id'] == decision['object_id']
    event, = [row for row in case_rows(engine, t.events, case) if row['event_kind'] == 'REVISION']
    assert event['record_id'] == decision['record_id'] and event['pre_case_version'] == body['expected_case_version']
    assert event['case_version'] == head['case_version'] and event['generation'] == state['generation']
    fact, = [row for row in rows(engine, old.acceptances) if row['target'] == case and row['operation'] == OPERATION]
    receipt, = [row for row in rows(engine, old.receipts) if row['acceptance_id'] == fact['acceptance_id']]
    assert receipt['available'] and receipt['body'] is not None
    assert not rows(engine, t.effects)
    assert not [row for row in case_rows(engine, t.work, case) if row['purpose'] in {'EXECUTION', 'NOTIFICATION', 'EFFECT'}]
    assert not [row for row in case_rows(engine, old.history, case) if row['kind'] in {'APPROVAL', 'OPERATION', 'NOTIFICATION'}]
    saved_previews = case_rows(engine, previews, case)
    consumed = [row for row in saved_previews if row['consuming_decision_record_id'] is not None]
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
        assert state['generation'] == old_state['generation'] + 1
        assert state['proposal_version'] == old_state['proposal_version']
        from manual_helpers import snapshot
        after = snapshot(engine)
        assert after[t.authorities.name] == before[t.authorities.name]
        for name in ('original_statement_records', 'original_statement_contents', old.evidence.name,
                old.evidence_contents.name, inv.projections.name, inv.projection_contents.name, inv.receipts.name, inv.receipt_contents.name):
            assert after[name] == before[name]
        old_history = {row['record_id']:row for row in before[old.history.name]}
        assert {row['record_id']:row for row in after[old.history.name]
            if row['record_id'] in old_history} == old_history
        original_previews = {row['preview_id']:row for row in before[previews.name]}
        for row in after[previews.name]:
            if row['preview_id'] in original_previews:
                prior = original_previews[row['preview_id']]
                assert {k:v for k,v in row.items() if k not in {'consuming_decision_record_id', 'consumed_at'}} == {
                    k:v for k,v in prior.items() if k not in {'consuming_decision_record_id', 'consumed_at'}}
        for prior in before[t.work.name]:
            if prior['case_id'] == case:
                current = next(row for row in rows(engine, t.work) if row['work_id'] == prior['work_id'])
                if prior['state'] in {'PENDING', 'RUNNING', 'PAUSED'}:
                    assert current['state'] == 'SUPERSEDED' and current['epoch'] == prior['epoch'] + 1
                    assert current['claim_id'] is None and current['lease_expires_at'] is None
                    assert current['claimed_case_version'] == prior['claimed_case_version']
                    assert current['authority_revision'] == prior['authority_revision']
                else:
                    safe_current = next(row for row in after[t.work.name] if row['work_id'] == prior['work_id'])
                    assert safe_current == prior


def mutate_source(uow, mode):
    if mode in {'review_fingerprint', 'review_ESC', 'review_version'}:
        # The current review pointer is cleared by a successful staged revision.
        # Locate the actual retained review so both entry and final injections
        # change one real event; a zero-row mutation must never count as proof.
        record = uow.execute(select(old.history.c.record_id).where(old.history.c.kind == 'REVIEW')).scalar_one()
        values = {'review_fingerprint':dict(fingerprint='0' * 64),
            'review_ESC':dict(event_kind='REVIEW_ESCALATE'),
            'review_version':dict(pre_case_version=999)}[mode]
        assert uow.execute(update(t.events).where(t.events.c.record_id == record).values(**values)).rowcount == 1
    elif mode == 'missing_review':
        # Removing retained bytes works before and after current refs clear;
        # the preview/history foreign keys remain valid and the proof must deny.
        from sqlalchemy import delete
        record = uow.execute(select(old.history.c.record_id).where(old.history.c.kind == 'REVIEW')).scalar_one()
        assert uow.execute(delete(old.history_contents).where(old.history_contents.c.record_id == record)).rowcount == 1
    elif mode == 'evidence_raw':
        assert uow.execute(update(old.evidence_contents).values(body=b'changed evidence bytes')).rowcount == 1
    elif mode == 'order_projection':
        assert uow.execute(update(inv.projection_contents).values(body=b'{}')).rowcount == 1
    else:
        retained_fault(uow, mode)


def mutate_preview(uow, case, mode):
    state = uow.execute(select(t.state).where(t.state.c.case_id == case)).mappings().one()
    row = uow.execute(select(previews).where(previews.c.preview_id == state['preview_id'])).mappings().one()
    values = {'body':dict(body=b'{}'), 'hash':dict(body_hash='0' * 64),
        'audit':dict(audit_hash='0' * 64), 'version':dict(pre_case_version=row['pre_case_version'] + 5,
            post_case_version=row['post_case_version'] + 5), 'generation':dict(generation=row['generation'] + 1),
        'input':dict(input_version=row['input_version'] + 1),
        'chain':dict(previous_preview_id=row['preview_id']),
        'proposal':dict(proposal_record_id=row['review_record_id']),
        'review':dict(review_record_id=row['proposal_record_id']),
        'consumed':dict(consuming_decision_record_id=row['proposal_record_id'], consumed_at=row['issued_at'])}[mode]
    assert uow.execute(update(previews).where(previews.c.preview_id == row['preview_id']).values(**values)).rowcount == 1
