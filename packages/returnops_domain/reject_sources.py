"""Actual retained REVIEW_PASS and original REJECT/notification acceptance proofs."""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, investigation_tables as investigation, lifecycle_tables as t
from .audit import timestamp
from .canonical import digest
from .lifecycle_events import LifecycleClaim, OutcomeAccepted
from .lifecycle_schema import version, CURRENT
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one
from .pass_review_sources import accepted_review
from .reject_denial import COMPONENT

EMPTY_TARGETS = ('preview_id', 'approval_record_id', 'outcome_record_id', 'outcome',
                 'notification_id', 'notification_record_id', 'notification_hash',
                 'notification_work_id', 'return_record_id', 'label_record_id')
MESSAGE = 'Your return request has been rejected.'


def check_seal(uow, seal):
    """Final small row reads after expensive proof and current authorization."""
    for table, key, saved in (
        (old.history, 'record_id', seal['record']),
        (old.history, 'record_id', seal['notification_record']),
        (t.sources, 'record_id', seal['binding']),
        (t.sources, 'record_id', seal['notification_binding']),
        (t.work, 'work_id', seal['work']),
        (t.work, 'work_id', seal['notification_work']),
        (t.events, 'record_id', seal['event']),
    ):
        if one(uow, table, **{key:saved[key]}) != saved:
            reject(uow)
    if seal.get('preview') is not None:
        from .preview_tables import previews
        for item in seal['preview']['chain']:
            row = item['row']
            if one(uow, previews, preview_id=row['preview_id']) != row:
                reject(uow)


def read_target(uow, head, state, request, component, *, original_state=None, consumer=None):
    initial = state if original_state is None else original_state
    if (component != COMPONENT or version(uow.connection) != CURRENT or initial is None or state is None
            or not initial['available'] or not state['available']
            or initial['review_record_id'] is None or initial['proposal_record_id'] is None):
        reject(uow)
    # current=True repeats full retained input and current order verification,
    # including during the final check against the server-derived original refs.
    seal = accepted_review(uow, head, initial, component, current=True)
    packet = seal['proposal']['body']['packet']
    block = uow.execute(select(investigation.state.c.current_block_id).where(
        investigation.state.c.case_id == head['case_id'])).scalar_one_or_none()
    expected = request['expected_case_version']
    from .preview_sources import source_target
    _, preview = source_target(uow, head, initial, expected_version=expected, allow_consumed=consumer is not None)
    if preview is not None and preview['row']['consuming_decision_record_id'] != consumer:
        reject(uow)
    if (request.get('decision') != 'REJECT'
            or any(request.get(k) != packet[k] for k in ('proposal_id', 'proposal_version'))
            or head['current_failure_id'] is not None
            or block is not None or any(initial[name] is not None for name in EMPTY_TARGETS if name != 'preview_id')
            or initial['input_version'] != head['input_version']
            or any(state[name] != initial[name] for name in
                ('input_version', 'generation', 'proposal_version', 'proposal_record_id', 'review_record_id'))):
        reject(uow)
    if original_state is None:
        if head['status'] != 'AWAITING_APPROVAL' or head['case_version'] != expected:
            reject(uow)
    elif (head['status'] != 'NOTIFICATION_PENDING' or head['case_version'] != expected + 1
            or state['outcome'] != 'REJECTED' or state['outcome_record_id'] is None
            or any(state[name] is None for name in
                ('notification_id', 'notification_record_id', 'notification_hash', 'notification_work_id'))
            or any(state[name] is not None for name in ('preview_id', 'approval_record_id', 'return_record_id', 'label_record_id'))):
        reject(uow)
    return seal


def accepted_reject(uow, head, record_id, component):
    """Read the original notification binding, never the current note pointer.

    Notification work may legitimately advance later. Its original identity is
    located by the original immutable outcome target; the original notification
    body, binding and audit remain required even after a failed/retried send.
    """
    if component != COMPONENT or version(uow.connection) != CURRENT:
        reject(uow)
    sources = Sources(uow, head, component)
    row, body = sources.read(record_id, {'DECISION'}, current_actor=False)
    binding = one(uow, t.sources, record_id=record_id)
    work = one(uow, t.work, work_id=binding['work_id'])
    event = one(uow, t.events, record_id=record_id)
    origin = sources.proof.origin(row)
    from .preview_tables import previews
    from .preview_sources import accepted_preview, consume_payload
    consumed = uow.execute(select(previews.c.preview_id).where(
        previews.c.consuming_decision_record_id == record_id)).scalar_one_or_none()
    preview = None if consumed is None else accepted_preview(uow, head, consumed)
    expected_payload = {'private_reject':True} if preview is None else consume_payload(preview['row'])
    review = accepted_review(uow, head, None, component,
        record_id=binding['target_record_id'], current=False)
    packet = review['proposal']['body']['packet']
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    identity = dict(case_id=head['case_id'], **asdict(claim))
    note_binding = uow.execute(select(t.sources).where(t.sources.c.work_id == work['work_id'],
        t.sources.c.epoch == claim.epoch, t.sources.c.slot == 'NOTIFICATION')).mappings().one_or_none()
    if note_binding is None:
        reject(uow)
    note_row, note = sources.read(note_binding['record_id'], {'NOTIFICATION'}, current_actor=False)
    note_origin = sources.proof.origin(note_row)
    from .lifecycle_guards import target, notification_hash
    original_head = {**head, 'input_version':claim.input_version}
    original_state = dict(generation=claim.generation, proposal_record_id=review['proposal']['record']['record_id'],
        review_record_id=review['record']['record_id'], approval_record_id=None)
    note_state = dict(generation=claim.generation, outcome_record_id=record_id, outcome='REJECTED',
        notification_id=note['notification_id'], notification_hash=notification_hash(note))
    note_work = uow.execute(select(t.work).where(t.work.c.case_id == head['case_id'],
        t.work.c.purpose == 'NOTIFICATION', t.work.c.generation == claim.generation,
        t.work.c.target_hash == target(original_head, note_state, 'NOTIFICATION'))).mappings().one_or_none()
    if (any(binding[k] != v or note_binding[k] != v for k, v in identity.items())
            or work['component_id'] != component or work['purpose'] != 'OUTCOME'
            or work['case_id'] != head['case_id'] or work['state'] != 'DONE' or work['epoch'] < 1
            or work['claim_id'] is None or work['authority_revision'] is None or work['lease_expires_at'] is not None
            or work['store_id'] != head['store_id'] or work['owner_id'] != head['owner_principal_id']
            or work['target_record_id'] is not None or work['target_hash'] != target(original_head, original_state, 'OUTCOME')
            or binding['slot'] != 'PRIMARY' or binding['source_hash'] != row['content_sha256']
            or row['case_version'] != claim.case_version or row['object_version'] != 1
            or body['decision'] != 'REJECT' or body['decision_id'] != row['object_id']
            or any(body[k] != packet[k] for k in ('case_id', 'proposal_id', 'proposal_version'))
            or origin['actor'] != {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':body['principal_id']}
            or origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
            or origin['payload_hash'] != digest(expected_payload, 'audit-payload/v1')
            or body['decided_at'] != timestamp(event['accepted_at']) or origin['occurred_at'] != body['decided_at']
            or event['accepted_at'] != row['recorded_at'] or origin['case_version'] != claim.case_version
            or note_binding['target_record_id'] != record_id or note_binding['source_hash'] != note_row['content_sha256']
            or note_row['case_version'] != claim.case_version or note_row['object_version'] != 1
            or note_row['recorded_at'] != event['accepted_at'] or note['notification_id'] != note_row['object_id']
            or note['case_id'] != head['case_id'] or note['case_version'] != claim.case_version
            or note['status'] != 'PENDING' or note['outcome'] != 'REJECTED' or note['attempt_count'] != 0
            or note['message'] != MESSAGE or note['next_steps'] != []
            or note['updated_at'] != timestamp(event['accepted_at'])
            or note_origin['actor'] != {'kind':'SERVICE', 'component_id':component}
            or note_origin['event_type'] != 'NOTIFICATION_REVISION_RECORDED'
            or note_origin['payload_hash'] != digest(expected_payload, 'audit-payload/v1')
            or note_origin['correlation_id'] != origin['correlation_id']
            or note_origin['occurred_at'] != note['updated_at'] or note_origin['case_version'] != claim.case_version
            or event['event_kind'] != 'OUTCOME' or event['status'] != 'NOTIFICATION_PENDING'
            or event['fingerprint'] != digest({'kind':'OUTCOME', **asdict(
                OutcomeAccepted(event['event_id'], claim, record_id, note_row['record_id']))}, 'lifecycle-event/v1')
            or event['case_id'] != head['case_id'] or event['work_id'] != work['work_id']
            or event['source_id'] != record_id or event['source_hash'] != row['content_sha256']
            or event['source_audit_event_id'] != origin['event_id']
            or event['pre_case_version'] != claim.case_version or event['case_version'] != claim.case_version + 1
            or event['pre_generation'] != claim.generation or event['generation'] != claim.generation
            or event['pre_input_version'] != claim.input_version or event['input_version'] != claim.input_version
            or (review['event']['case_version'] if preview is None else preview['row']['post_case_version']) != claim.case_version
            or review['event']['generation'] != claim.generation or review['event']['input_version'] != claim.input_version
            or note_work is None or note_work['component_id'] != component
            or note_work['store_id'] != head['store_id'] or note_work['owner_id'] != head['owner_principal_id']
            or note_work['input_version'] != claim.input_version or note_work['target_record_id'] is not None
            or not note_work['idempotency_key'] or note_work['created_at'] != event['accepted_at']):
        reject(uow)
    if preview is not None and (preview['review'] != review or preview['row']['consuming_decision_record_id'] != record_id
            or preview['row']['consumed_at'] != event['accepted_at']):
        reject(uow)
    audits = [a for a in sources.proof.events if a['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
        and a['correlation_id'] == event['event_id']]
    payload = dict(event='OUTCOME', work_id=work['work_id'], source_record_id=record_id, generation=event['generation'])
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind':'SERVICE', 'component_id':component}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])):
        reject(uow)
    return dict(record=dict(row), body=body, binding=binding, work=work, event=event, review=review,
        notification_record=dict(note_row), notification=note, notification_binding=dict(note_binding),
        notification_work=dict(note_work), preview=preview)
