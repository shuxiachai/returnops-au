"""Full modern proposal MANUAL_HANDLING proof, dispatched by retained review."""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, founder_tables as finite_tables, lifecycle_tables as t
from . import founder_codec as finite
from .audit import timestamp
from .canonical import digest
from .lifecycle_events import LifecycleClaim, OutcomeAccepted
from .lifecycle_schema import APPROVAL_VERSIONS, version
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one
from .manual_denial import COMPONENT
from .preview_sources import EMPTY, accepted_preview, source_target, consume_payload
from .preview_tables import previews

MESSAGE = 'Your request has been assigned for manual handling.'


def _review_kind(uow, record_id):
    if record_id is None:
        reject(uow)
    kind = one(uow, t.events, record_id=record_id)['event_kind']
    if kind not in {'REVIEW', 'REVIEW_PASS'}:
        reject(uow)
    return kind


def _review(uow, head, state, component, *, record_id=None, current=True):
    identity = record_id if record_id is not None else state['review_record_id']
    if _review_kind(uow, identity) == 'REVIEW_PASS':
        from .pass_review_sources import accepted_review
    else:
        from .review_sources import accepted_review
    return accepted_review(uow, head, state, component, record_id=identity, current=current)


def read_preview(uow, head, state, expected_version, *, consumer=None):
    if state is None:
        reject(uow)
    if _review_kind(uow, state['review_record_id']) == 'REVIEW':
        if state['preview_id'] is not None:
            reject(uow)
        return None
    _, preview = source_target(uow, head, state, expected_version=expected_version,
                               allow_consumed=consumer is not None)
    if preview is not None and preview['row']['consuming_decision_record_id'] != consumer:
        reject(uow)
    return preview


def read_target(uow, head, state, request, component, *, original_state=None, consumer=None):
    initial = state if original_state is None else original_state
    if (component != COMPONENT or version(uow.connection) not in APPROVAL_VERSIONS
            or initial is None or state is None or not initial['available'] or not state['available']
            or initial['proposal_record_id'] is None or initial['review_record_id'] is None):
        reject(uow)
    kind = _review_kind(uow, initial['review_record_id'])
    if kind == 'REVIEW_PASS':
        review, preview = source_target(uow, head, initial,
            expected_version=request['expected_case_version'], allow_consumed=consumer is not None)
        if preview is not None and preview['row']['consuming_decision_record_id'] != consumer:
            reject(uow)
    else:
        from .review_sources import manual_proposal_target
        review = manual_proposal_target(uow, head, initial, request, component,
            accepted_version=request['expected_case_version'])
        if initial['preview_id'] is not None:
            reject(uow)
    packet = review['proposal']['body']['packet']
    if (request.get('decision') != 'MANUAL_HANDLING'
            or any(request.get(name) != packet[name] for name in ('proposal_id', 'proposal_version'))
            or any(initial[name] is not None for name in EMPTY)
            or initial['input_version'] != head['input_version']
            or any(state[name] != initial[name] for name in
                ('input_version', 'generation', 'proposal_version', 'proposal_record_id', 'review_record_id'))):
        reject(uow)
    expected = request['expected_case_version']
    if original_state is None:
        status = 'AWAITING_APPROVAL' if kind == 'REVIEW_PASS' else 'ESCALATED'
        if head['status'] != status or head['case_version'] != expected:
            reject(uow)
    elif (head['status'] != 'NOTIFICATION_PENDING' or head['case_version'] != expected + 1
            or state['outcome'] != 'MANUAL_HANDLED' or state['outcome_record_id'] != consumer
            or any(state[name] is None for name in
                ('notification_id', 'notification_record_id', 'notification_hash', 'notification_work_id'))
            or any(state[name] is not None for name in ('preview_id', 'approval_record_id', 'return_record_id', 'label_record_id'))):
        reject(uow)
    return review


def check_current(uow, head, original_state, review, component):
    """An original acceptance alone cannot replace current input/order proof."""
    if _review(uow, head, original_state, component, current=True) != review:
        reject(uow)


def check_actor(uow, head, seal):
    person = uow.execute(select(old.principals).where(
        old.principals.c.principal_id == seal['body']['principal_id']).with_for_update()).mappings().one_or_none()
    if (person is None or not person['enabled'] or person['role'] != 'FOUNDER'
            or person['store_id'] != head['store_id']):
        reject(uow, 'FORBIDDEN')


def check_seal(uow, seal):
    """Small retained rows are checked after costly proof and fresh authority."""
    for item in (seal, seal['review'], seal['review']['proposal']):
        for table, key, name in ((old.history, 'record_id', 'record'),
                (t.sources, 'record_id', 'binding'), (t.work, 'work_id', 'work'),
                (t.events, 'record_id', 'event')):
            saved = item[name]
            if one(uow, table, **{key: saved[key]}) != saved:
                reject(uow)
        raw = one(uow, old.history_contents, record_id=item['record']['record_id'])
        if finite.decode_document(raw['body']) != item['body']:
            reject(uow)
    for table, key, name in ((old.history, 'record_id', 'notification_record'),
            (t.sources, 'record_id', 'notification_binding'), (t.work, 'work_id', 'notification_work')):
        saved = seal[name]
        if one(uow, table, **{key: saved[key]}) != saved:
            reject(uow)
    raw = one(uow, old.history_contents, record_id=seal['notification_record']['record_id'])
    if finite.decode_document(raw['body']) != seal['notification']:
        reject(uow)
    for row in seal['encodings']:
        if one(uow, finite_tables.encodings, record_id=row['record_id']) != row:
            reject(uow)
    for row in seal['audits']:
        if one(uow, old.audit, event_id=row['event_id']) != row:
            reject(uow)
    if seal['preview'] is not None:
        for item in seal['preview']['chain']:
            row = item['row']
            if one(uow, previews, preview_id=row['preview_id']) != row:
                reject(uow)


def accepted_manual(uow, head, record_id, component):
    """Prove the original outcome and notice independently of current pointers.

    Notification work can advance lawfully after acceptance. Its immutable
    original target locates it; replay never requires it to still be unclaimed.
    """
    if component != COMPONENT or version(uow.connection) not in APPROVAL_VERSIONS:
        reject(uow)
    sources = Sources(uow, head, component)
    row, body = sources.read(record_id, {'DECISION'}, current_actor=False)
    binding = one(uow, t.sources, record_id=record_id)
    work = one(uow, t.work, work_id=binding['work_id'])
    event = one(uow, t.events, record_id=record_id)
    origin = sources.proof.origin(row)
    # Original PRIMARY identity, never the current head, chooses the family.
    review = _review(uow, head, None, component, record_id=binding['target_record_id'], current=False)
    consumed = uow.execute(select(previews.c.preview_id).where(
        previews.c.consuming_decision_record_id == record_id)).scalar_one_or_none()
    preview = None if consumed is None else accepted_preview(uow, head, consumed, review=review)
    if preview is not None and review['event']['event_kind'] != 'REVIEW_PASS':
        reject(uow)
    expected_payload = {'private_manual': True} if preview is None else consume_payload(preview['row'])
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
    original_head = {**head, 'input_version': claim.input_version}
    original_state = dict(generation=claim.generation, proposal_record_id=review['proposal']['record']['record_id'],
        review_record_id=review['record']['record_id'], approval_record_id=None)
    note_state = dict(generation=claim.generation, outcome_record_id=record_id, outcome='MANUAL_HANDLED',
        notification_id=note['notification_id'], notification_hash=notification_hash(note))
    note_work = uow.execute(select(t.work).where(t.work.c.case_id == head['case_id'],
        t.work.c.purpose == 'NOTIFICATION', t.work.c.generation == claim.generation,
        t.work.c.target_hash == target(original_head, note_state, 'NOTIFICATION'))).mappings().one_or_none()
    if note_work is None:
        reject(uow)
    from .notification_intent import accepted_initial_format
    note_format, note_payload, note_component = accepted_initial_format(
        uow, head, note_work, note_row, row, component, 'MANUAL_HANDLED', MESSAGE, expected_payload)
    if (any(binding[name] != value or note_binding[name] != value for name, value in identity.items())
            or work['component_id'] != component or work['purpose'] != 'OUTCOME'
            or work['case_id'] != head['case_id'] or work['state'] != 'DONE' or work['epoch'] < 1
            or work['claim_id'] is None or work['authority_revision'] is None or work['lease_expires_at'] is not None
            or work['store_id'] != head['store_id'] or work['owner_id'] != head['owner_principal_id']
            or work['target_record_id'] is not None or work['target_hash'] != target(original_head, original_state, 'OUTCOME')
            or binding['slot'] != 'PRIMARY' or binding['source_hash'] != row['content_sha256']
            or row['case_version'] != claim.case_version or row['object_version'] != 1
            or body['decision'] != 'MANUAL_HANDLING' or body['decision_id'] != row['object_id']
            or any(body[name] != packet[name] for name in ('case_id', 'proposal_id', 'proposal_version'))
            or origin['actor'] != {'kind': 'HUMAN', 'role': 'FOUNDER', 'principal_id': body['principal_id']}
            or origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
            or origin['payload_hash'] != digest(expected_payload, 'audit-payload/v1')
            or body['decided_at'] != timestamp(event['accepted_at']) or origin['occurred_at'] != body['decided_at']
            or event['accepted_at'] != row['recorded_at'] or origin['case_version'] != claim.case_version
            or event['accepted_at'] < review['event']['accepted_at']
            or note_binding['target_record_id'] != record_id or note_binding['source_hash'] != note_row['content_sha256']
            or note_row['case_version'] != claim.case_version or note_row['object_version'] != 1
            or note_row['recorded_at'] != event['accepted_at'] or note['notification_id'] != note_row['object_id']
            or note['case_id'] != head['case_id'] or note['case_version'] != claim.case_version
            or note['status'] != 'PENDING' or note['outcome'] != 'MANUAL_HANDLED' or note['attempt_count'] != 0
            or note['message'] != note_format['message'] or note['next_steps'] != note_format['next_steps']
            or note['updated_at'] != timestamp(event['accepted_at'])
            or note_origin['actor'] != {'kind': 'SERVICE', 'component_id': component}
            or note_origin['event_type'] != 'NOTIFICATION_REVISION_RECORDED'
            or note_origin['payload_hash'] != digest(note_payload, 'audit-payload/v1')
            or note_origin['correlation_id'] != origin['correlation_id']
            or note_origin['occurred_at'] != note['updated_at'] or note_origin['case_version'] != claim.case_version
            or event['event_kind'] != 'OUTCOME' or event['status'] != 'NOTIFICATION_PENDING'
            or event['fingerprint'] != digest({'kind': 'OUTCOME', **asdict(
                OutcomeAccepted(event['event_id'], claim, record_id, note_row['record_id']))}, 'lifecycle-event/v1')
            or event['case_id'] != head['case_id'] or event['work_id'] != work['work_id']
            or event['source_id'] != record_id or event['source_hash'] != row['content_sha256']
            or event['source_audit_event_id'] != origin['event_id']
            or event['pre_case_version'] != claim.case_version or event['case_version'] != claim.case_version + 1
            or event['pre_generation'] != claim.generation or event['generation'] != claim.generation
            or event['pre_input_version'] != claim.input_version or event['input_version'] != claim.input_version
            or (review['event']['case_version'] if preview is None else preview['row']['post_case_version']) != claim.case_version
            or review['event']['generation'] != claim.generation or review['event']['input_version'] != claim.input_version
            or note_work is None or note_work['component_id'] != note_component
            or note_work['store_id'] != head['store_id'] or note_work['owner_id'] != head['owner_principal_id']
            or note_work['input_version'] != claim.input_version or note_work['target_record_id'] is not None
            or not note_work['idempotency_key'] or note_work['created_at'] != event['accepted_at']):
        reject(uow)
    if preview is not None and (preview['row']['consuming_decision_record_id'] != record_id
            or preview['row']['consumed_at'] != event['accepted_at']):
        reject(uow)
    audits = [audit for audit in sources.proof.events if audit['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
        and audit['correlation_id'] == event['event_id']]
    payload = dict(event='OUTCOME', work_id=work['work_id'], source_record_id=record_id, generation=event['generation'])
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind': 'SERVICE', 'component_id': component}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])):
        reject(uow)
    records = [row, note_row, review['record'], review['proposal']['record']]
    # Preserve the full existing audit row bytes, including source-chain rows.
    audit_rows = [dict(item) for item in uow.execute(select(old.audit).where(
        old.audit.c.case_id == head['case_id']).order_by(old.audit.c.sequence)).mappings()]
    return dict(record=dict(row), body=body, binding=binding, work=work, event=event, review=review,
        notification_record=dict(note_row), notification=note, notification_binding=dict(note_binding),
        notification_work=dict(note_work), preview=preview, audits=audit_rows,
        encodings=[one(uow, finite_tables.encodings, record_id=item['record_id']) for item in records])
