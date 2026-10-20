"""Fresh v2 origin, fixed recipient and immutable original notification intent."""
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as life
from .audit import timestamp
from .canonical import digest, encode_document, decode_document
from .lifecycle_schema import NOTIFICATION, version
from .lifecycle_state import reject
from .lifecycle_sources import Sources
from .manual_target import one
from .notification_profile import COMPONENT, CHANNEL, PROFILES, profile_hash, render
from .notification_tables import controls
from .label_artifact_sources import canonical_rows

RETURN_PRODUCER = 'notification-outcome-v2'


def initial_payload(producer, outcome, source_record_id, source_hash):
    return dict(profile='notification-initial/v2', producer_id=producer, outcome=outcome,
                profile_hash=profile_hash(outcome), source_record_id=source_record_id,
                source_hash=source_hash)


def initial_format(uow, outcome, legacy_message):
    return (render(outcome) if version(uow.connection) == NOTIFICATION
            else dict(message=legacy_message, next_steps=[]))


def accepted_initial_format(uow, head, note_work, note_row, source_row, producer, outcome,
                            legacy_message, legacy_payload):
    """Explicit original work ownership selects v2; missing controls cannot fall back."""
    if note_work['component_id'] == COMPONENT:
        if version(uow.connection) != NOTIFICATION:
            reject(uow)
        control = one(uow, controls, notification_work_id=note_work['work_id'])
        if (control['initial_notification_record_id'] != note_row['record_id']
                or control['outcome_record_id'] != source_row['record_id']
                or control['producer_id'] != producer or control['outcome'] != outcome):
            reject(uow)
        return (render(outcome), initial_payload(producer, outcome, source_row['record_id'],
                                                 source_row['content_sha256']), COMPONENT)
    if note_work['component_id'] != producer:
        reject(uow)
    return dict(message=legacy_message, next_steps=[]), legacy_payload, producer


def _inventory(uow, head, initial_record_id):
    sources = Sources(uow, head, COMPONENT)
    cutoff = one(uow, old.history, record_id=initial_record_id)['recorded_sequence']
    records = []
    for row in sources.proof.revisions.values():
        if row['recorded_sequence'] > cutoff:
            continue
        _, body = sources.read(row['record_id'], {row['kind']}, current_actor=False)
        records.append(dict(record=canonical_rows(dict(row)), content_hash=digest(body, 'notification-source-body/v2'),
                            origin_hash=sources.proof.origin(row)['event_hash']))
    return records


def create_control(uow, head, before, after, work, receipt, producer):
    """Only the outcome guard calls this in the actual original transaction."""
    if version(uow.connection) != NOTIFICATION or work['component_id'] != COMPONENT:
        reject(uow)
    initial = one(uow, old.history, record_id=after['notification_record_id'])
    sources = Sources(uow, head, producer)
    _, note = sources.read(initial['record_id'], {'NOTIFICATION'})
    source = one(uow, old.history, record_id=after['outcome_record_id'])
    evidence_id = None
    if after['outcome'] == 'RETURN_CREATED':
        from .notification_execution import completed_pair
        pair = completed_pair(uow, head)
        evidence_id = pair['evidence_id']
        source_id, source_hash = pair['label_record_id'], pair['artifact']['result_record']['content_sha256']
    else:
        source_id, source_hash = source['record_id'], source['content_sha256']
    payload = initial_payload(producer, after['outcome'], source_id, source_hash)
    expected = render(after['outcome'], label_evidence_id=evidence_id)
    if (note['message'] != expected['message'] or note['next_steps'] != expected['next_steps']
            or note['attempt_count'] != 0 or note['status'] != 'PENDING'
            or sources.proof.origin(initial)['payload_hash'] != digest(payload, 'audit-payload/v1')):
        reject(uow)
    manifest = dict(profile='notification-source/v2', original_state=canonical_rows(dict(before)),
                    records=_inventory(uow, head, initial['record_id']), evidence_id=evidence_id)
    recipient = dict(case_id=head['case_id'], store_id=head['store_id'], owner_id=head['owner_principal_id'])
    delivery = dict(recipient=recipient, channel=CHANNEL, outcome=after['outcome'], **expected)
    core = dict(profile='notification-intent/v2', notification_work_id=work['work_id'],
        notification_id=note['notification_id'], outcome_record_id=source['record_id'],
        initial_notification_record_id=initial['record_id'], outcome_event_id=receipt['event_id'],
        producer_id=producer, logical_key=work['idempotency_key'], input_version=head['input_version'],
        generation=after['generation'], message_profile=PROFILES[after['outcome']],
        profile_hash=profile_hash(after['outcome']), payload_hash=digest(delivery, 'notification-payload/v2'),
        source_hash=digest(manifest, 'notification-source/v2'), created_at=timestamp(receipt['accepted_at']),
        recipient=recipient, channel=CHANNEL, outcome=after['outcome'])
    uow.execute(controls.insert().values(notification_work_id=work['work_id'], **recipient,
        notification_id=note['notification_id'], outcome_record_id=source['record_id'],
        initial_notification_record_id=initial['record_id'], outcome_event_id=receipt['event_id'],
        producer_id=producer, outcome=after['outcome'], profile=core['message_profile'], channel=CHANNEL,
        profile_hash=core['profile_hash'], payload_hash=core['payload_hash'], source_hash=core['source_hash'],
        intent_hash=digest(core, 'notification-intent/v2'), intent_core=encode_document(core),
        source_manifest=encode_document(manifest), logical_key=work['idempotency_key'],
        input_version=head['input_version'], generation=after['generation'],
        created_at=receipt['accepted_at'], available=True, state='READY', attempt_count=0))


def original_intent(uow, head, control):
    if version(uow.connection) != NOTIFICATION or not head['available'] or not control['available']:
        reject(uow)
    core = decode_document(control['intent_core'])
    manifest = decode_document(control['source_manifest'])
    sources = Sources(uow, head, COMPONENT)
    initial, note = sources.read(control['initial_notification_record_id'], {'NOTIFICATION'}, current_actor=False)
    receipt = one(uow, life.events, event_id=control['outcome_event_id'])
    work = one(uow, life.work, work_id=control['notification_work_id'])
    evidence_id = manifest['evidence_id']
    expected = render(control['outcome'], label_evidence_id=evidence_id)
    recipient = dict(case_id=head['case_id'], store_id=head['store_id'], owner_id=head['owner_principal_id'])
    delivery = dict(recipient=recipient, channel=CHANNEL, outcome=control['outcome'], **expected)
    expected_core = dict(profile='notification-intent/v2', **{
        name:control[name] for name in ('notification_work_id','notification_id','outcome_record_id',
        'initial_notification_record_id','outcome_event_id','producer_id','logical_key','input_version','generation')},
        message_profile=PROFILES[control['outcome']], profile_hash=profile_hash(control['outcome']),
        payload_hash=digest(delivery, 'notification-payload/v2'),
        source_hash=digest(manifest, 'notification-source/v2'), created_at=timestamp(control['created_at']),
        recipient=recipient, channel=CHANNEL, outcome=control['outcome'])
    if (core != expected_core or encode_document(core) != bytes(control['intent_core'])
            or digest(core, 'notification-intent/v2') != control['intent_hash']
            or any(core[name] != control[name] for name in ('profile_hash','payload_hash','source_hash'))
            or control['profile'] != core['message_profile'] or control['channel'] != CHANNEL
            or any(control[name] != value for name,value in recipient.items())
            or manifest['records'] != _inventory(uow, head, initial['record_id'])
            or work['component_id'] != COMPONENT or work['purpose'] != 'NOTIFICATION'
            or work['idempotency_key'] != control['logical_key']
            or work['created_at'] != control['created_at']
            or receipt['record_id'] != control['outcome_record_id'] or receipt['event_kind'] != 'OUTCOME'
            or receipt['accepted_at'] != control['created_at'] or receipt['status'] != 'NOTIFICATION_PENDING'
            or note['notification_id'] != control['notification_id'] or note['outcome'] != control['outcome']
            or note['message'] != expected['message'] or note['next_steps'] != expected['next_steps']
            or note['status'] != 'PENDING' or note['attempt_count'] != 0):
        reject(uow)
    return dict(core=core, manifest=manifest, initial=initial, note=note, receipt=receipt, work=work)
