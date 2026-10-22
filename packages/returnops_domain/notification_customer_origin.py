"""Private customer provenance without widening frozen Founder history refs.

FR-011/012, NFR-003/004; recovery-notification-sequence and exact-scope-sequence.
Opaque audit marker discovery is global and bounded, never a successful cache.
An overflow fails closed instead of accepting an incomplete alias search.
"""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import decode_document, digest
from .lifecycle_events import LifecycleClaim, NotificationObserved
from .lifecycle_schema import NOTIFICATION, version
from .lifecycle_state import reject
from .manual_target import one
from .notification_profile import COMPONENT
from .notification_tables import controls, facts
from .wire import validate

EVENT = 'NOTIFICATION_CUSTOMER_MESSAGE_RECORDED'
PROFILE = 'notification-customer-message/v3'
ROW_LIMIT = 4096
AUDIT_LIMIT = 16384
AUDIT_BODY_LIMIT = 65536
AUDIT_BYTES_LIMIT = 16 * 1024 * 1024
METADATA = ('record_id', 'case_id', 'kind', 'object_id', 'object_version',
            'case_version', 'recorded_sequence', 'recorded_at', 'content_sha256')


def customer_id(notification_id):
    return 'nmessage_' + digest({'notification_id': notification_id}, 'notification-customer-id/v2')


def history_ref(row):
    return {name: row[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}


def customer_payload(control, fact, row):
    metadata = {name: row[name] for name in METADATA}
    metadata['recorded_at'] = timestamp(row['recorded_at'])
    return dict(profile=PROFILE, **{name: control[name] for name in (
        'notification_work_id', 'notification_id', 'case_id', 'store_id', 'owner_id', 'intent_hash')},
        accepted_fact_id=fact['fact_id'], fact_hash=fact['fact_hash'],
        notification_record_id=control['accepted_record_id'], customer_record=metadata)


def _bounded(uow, table, limit):
    rows = uow.execute(select(table).limit(limit + 1)).mappings().all()
    if len(rows) > limit:
        reject(uow)
    return [dict(row) for row in rows]


def audit_markers(uow):
    """Read all opaque events within explicit caps, including foreign cases."""
    result, total = [], 0
    for row in _bounded(uow, old.audit, AUDIT_LIMIT):
        raw = row['body']
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            reject(uow)
        total += len(raw)
        if len(raw) > AUDIT_BODY_LIMIT or total > AUDIT_BYTES_LIMIT:
            reject(uow)
        event = decode_document(raw)
        validate('AuditEvent', event, internal=True)
        if event['event_id'] != row['event_id'] or event['case_id'] != row['case_id']:
            reject(uow)
        result.append(event)
    return result


def related_markers(row, all_controls, all_facts, events):
    """Identity OR case membership; a conflicting case cannot hide an alias."""
    notifications = {row['object_id']}
    customer_ids = {row['record_id'], customer_id(row['object_id'])}
    work_ids, fact_ids, record_ids, event_ids = set(), set(), set(), set()
    linked_controls, linked_facts = [], []
    changed = True
    while changed:
        changed = False
        for collection, linked in ((all_controls, linked_controls), (all_facts, linked_facts)):
            for value in collection:
                if value in linked:
                    continue
                matches = (value['case_id'] == row['case_id']
                    or value['notification_id'] in notifications
                    or customer_id(value['notification_id']) in customer_ids
                    or value['notification_work_id'] in work_ids
                    or value.get('fact_id') in fact_ids
                    or value.get('accepted_fact_id') in fact_ids
                    or value.get('accepted_record_id') in record_ids
                    or value.get('accepted_event_id') in event_ids)
                if not matches:
                    continue
                linked.append(value)
                notifications.add(value['notification_id'])
                customer_ids.add(customer_id(value['notification_id']))
                work_ids.add(value['notification_work_id'])
                for key, target in (('fact_id', fact_ids), ('accepted_fact_id', fact_ids),
                                    ('accepted_record_id', record_ids), ('accepted_event_id', event_ids)):
                    if value.get(key) is not None:
                        target.add(value[key])
                changed = True
    linked_events = []
    for event in events:
        ids = set(event['object_ids'])
        refs = {ref['record_id'] for ref in event['history_refs']}
        # A wrong-type event still cannot hide when it names the customer row.
        if (event['event_type'] == EVENT or ids & customer_ids) and (
                event['case_id'] == row['case_id'] or ids & (notifications | customer_ids)
                or refs & record_ids or event['correlation_id'] in event_ids):
            linked_events.append(event)
    return dict(controls=linked_controls, facts=linked_facts, events=linked_events)


def message_markers(uow, row):
    revision = version(uow.connection)
    if revision is None:
        reject(uow)
    modern = revision == NOTIFICATION
    found = related_markers(row, _bounded(uow, controls, ROW_LIMIT) if modern else [],
                            _bounded(uow, facts, ROW_LIMIT) if modern else [], audit_markers(uow))
    required = row['record_id'].startswith('nmessage_') or any(found.values())
    if required and not modern:
        reject(uow)
    return required, found


def current_case_markers(uow, head):
    """Discover orphan facts/origins even when no customer row was selected."""
    revision = version(uow.connection)
    if revision != NOTIFICATION:
        return dict(controls=[], facts=[], events=[])
    all_controls = _bounded(uow, controls, ROW_LIMIT)
    all_facts = _bounded(uow, facts, ROW_LIMIT)
    events = audit_markers(uow)
    found = dict(controls=[], facts=[], events=[
        event for event in events if event['case_id'] == head['case_id'] and event['event_type'] == EVENT])
    seeds = [value for value in all_controls + all_facts if value['case_id'] == head['case_id']]
    for value in seeds:
        probe = dict(case_id=head['case_id'], object_id=value['notification_id'],
                     record_id=customer_id(value['notification_id']))
        related = related_markers(probe, all_controls, all_facts, events)
        for family, matches in related.items():
            for match in matches:
                if match not in found[family]:
                    found[family].append(match)
    return found


def forbid_existing_messages(uow, case_id):
    """Fresh admission only; staged outcome writes must roll back on failure."""
    if uow.execute(select(old.history.c.record_id).where(
            old.history.c.case_id == case_id, old.history.c.kind == 'OUTCOME_MESSAGE')).first():
        reject(uow)


def verify_customer_origin(uow, head, row, control, fact, proof, markers):
    accepted = proof.revisions.get(control['accepted_record_id'])
    messages = [value for value in proof.revisions.values() if value['kind'] == 'OUTCOME_MESSAGE']
    origins = markers['events']
    if (accepted is None or len(messages) != 1 or messages[0]['record_id'] != row['record_id']
            or any(messages[0][name] != row[name] for name in METADATA)
            or row['kind'] != 'OUTCOME_MESSAGE' or row['object_version'] != 1
            or row['record_id'] != customer_id(control['notification_id'])
            or row['object_id'] != control['notification_id']
            or row['case_id'] != head['case_id'] or control['case_id'] != head['case_id']
            or control['store_id'] != head['store_id'] or control['owner_id'] != head['owner_principal_id']
            or fact['fact_id'] != control['accepted_fact_id'] or fact['status'] != 'SENT'
            or accepted['kind'] != 'NOTIFICATION' or accepted['case_id'] != head['case_id']
            or accepted['object_id'] != row['object_id']
            or row['case_version'] != accepted['case_version'] + 1
            or row['recorded_sequence'] != accepted['recorded_sequence'] + 1
            or row['recorded_at'] != accepted['recorded_at'] or row['recorded_at'] < fact['accepted_at']
            or len(markers['controls']) != 1 or markers['controls'][0] != control
            or len(origins) != 1):
        reject(uow)
    origin = origins[0]
    if (origin not in proof.events or origin['event_type'] != EVENT
            or origin['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
            or origin['case_id'] != row['case_id'] or origin['case_version'] != row['case_version']
            or origin['occurred_at'] != timestamp(row['recorded_at'])
            or origin['correlation_id'] != control['accepted_event_id']
            or origin['object_ids'] != [row['object_id'], row['record_id']]
            or origin['history_refs'] != [history_ref(accepted)]
            or origin['payload_hash'] != digest(customer_payload(control, fact, row), 'audit-payload/v1')):
        reject(uow)
    return accepted


def verify_accepted_metadata(uow, head, control, fact, accepted, proof):
    """Exact retained T3 identity; does not read or regenerate deleted bodies."""
    from .notification_mock import verify_fact
    from .notification_sources import phase_payload
    for found in _bounded(uow, facts, ROW_LIMIT):
        if (found['notification_id'] == control['notification_id']
                or found['notification_work_id'] == control['notification_work_id']
                or found['logical_key'] == control['logical_key']
                or found['intent_hash'] == control['intent_hash']
                or found['reservation_id'] == control['reservation_id']):
            verify_fact(uow, control, found)
    verify_fact(uow, control, fact)
    work = one(uow, life.work, work_id=control['notification_work_id'])
    binding = one(uow, life.sources, record_id=accepted['record_id'])
    claim = LifecycleClaim(**{name: binding[name] for name in LifecycleClaim.__dataclass_fields__})
    expected_binding = dict(record_id=accepted['record_id'], case_id=head['case_id'], **asdict(claim),
        source_hash=accepted['content_sha256'], target_record_id=control['outcome_record_id'], slot='PRIMARY',
        dispatch_source_record_id=None, provider_operation_id=None, artifact_evidence_id=None,
        artifact_sha256=None, order_projection_id=None)
    origin = proof.origin(accepted)
    if (binding != expected_binding or claim.work_id != control['notification_work_id']
            or claim.case_version != accepted['case_version']
            or claim.input_version != control['input_version'] or claim.generation != control['generation']
            or work['case_id'] != head['case_id'] or work['store_id'] != head['store_id']
            or work['owner_id'] != head['owner_principal_id'] or work['purpose'] != 'NOTIFICATION'
            or work['component_id'] != COMPONENT or work['state'] != 'DONE'
            or work['claim_id'] != claim.claim_id or work['epoch'] != claim.epoch
            or work['claimed_case_version'] != claim.case_version
            or work['input_version'] != claim.input_version or work['generation'] != claim.generation
            or work['authority_revision'] != claim.authority_revision
            or origin['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
            or origin['event_type'] != 'NOTIFICATION_REVISION_RECORDED'
            or origin['correlation_id'] != control['accepted_event_id']
            or origin['payload_hash'] != digest(phase_payload(control, 'FACT', fact['fact_hash']), 'audit-payload/v1')):
        reject(uow)
    receipt = one(uow, life.events, event_id=control['accepted_event_id'])
    event = NotificationObserved(control['accepted_event_id'], claim, accepted['record_id'])
    terminal = {'RETURN_CREATED': 'COMPLETED', 'REJECTED': 'REJECTED', 'MANUAL_HANDLED': 'MANUAL_HANDLED'}
    expected = dict(event_id=event.event_id, case_id=head['case_id'], work_id=claim.work_id,
        record_id=accepted['record_id'], fingerprint=digest({'kind': 'NOTIFICATION', **asdict(event)}, 'lifecycle-event/v1'),
        event_kind='NOTIFICATION', source_id=accepted['record_id'], source_hash=accepted['content_sha256'],
        source_audit_event_id=origin['event_id'], pre_case_version=accepted['case_version'],
        pre_input_version=claim.input_version, pre_generation=claim.generation,
        case_version=accepted['case_version'] + 1, input_version=claim.input_version, generation=claim.generation,
        status=terminal[control['outcome']], accepted_at=accepted['recorded_at'])
    audits = [item for item in proof.events if item['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
              and item['correlation_id'] == event.event_id]
    payload = dict(event='NOTIFICATION', work_id=claim.work_id,
                   source_record_id=accepted['record_id'], generation=claim.generation)
    if (receipt != expected or len(audits) != 1
            or audits[0]['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
            or audits[0]['case_version'] != receipt['case_version']
            or audits[0]['occurred_at'] != timestamp(receipt['accepted_at'])
            or audits[0]['object_ids'] != [accepted['object_id'], claim.work_id]
            or audits[0]['history_refs'] != []
            or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')):
        reject(uow)
