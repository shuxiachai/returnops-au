"""Full PASS/preview proof for a HUMAN revision, without approval authority."""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .audit import timestamp
from .canonical import digest
from .lifecycle_events import LifecycleClaim, RevisionRequested
from .lifecycle_schema import APPROVAL_VERSIONS, version
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one
from .pass_review_sources import accepted_review
from .preview_sources import EMPTY, source_target, accepted_preview, consume_payload
from .preview_tables import previews
from .revision_denial import COMPONENT


def read_preview(uow, head, state, expected_version, *, consumer=None):
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
    expected = request['expected_case_version']
    # source_target performs accepted_review(current=True), including after
    # invalidation: original refs locate the source, current head checks input.
    review, preview = source_target(uow, head, initial, expected_version=expected,
                                    allow_consumed=consumer is not None)
    packet = review['proposal']['body']['packet']
    if (request.get('decision') != 'REQUEST_REVISION'
            or any(request.get(name) != packet[name] for name in ('proposal_id', 'proposal_version'))
            or initial['input_version'] != head['input_version'] or state['input_version'] != head['input_version']
            or any(initial[name] is not None or state[name] is not None for name in EMPTY)
            or preview is not None and preview['row']['consuming_decision_record_id'] != consumer):
        reject(uow)
    if original_state is None:
        if head['status'] != 'AWAITING_APPROVAL' or head['case_version'] != expected:
            reject(uow)
    elif (head['status'] != 'POLICY_ASSESSMENT' or head['case_version'] != expected + 1
            or state['generation'] != initial['generation'] + 1
            or state['proposal_version'] != initial['proposal_version']
            or any(state[name] is not None for name in ('proposal_record_id', 'review_record_id', 'preview_id'))):
        reject(uow)
    return review


def accepted_revision(uow, head, record_id, component):
    """Prove the exact old fact, including its unique consumed preview tail.

    The frozen REVISION target does not contain a preview ID. The exact claim
    version, complete preview chain, HUMAN audit and consumer bind that identity.
    Historical proof neither consults producer grants nor grants new authority.
    """
    if component != COMPONENT or version(uow.connection) not in APPROVAL_VERSIONS:
        reject(uow)
    sources = Sources(uow, head, component)
    row, body = sources.read(record_id, {'DECISION'}, current_actor=False)
    binding = one(uow, t.sources, record_id=record_id)
    work = one(uow, t.work, work_id=binding['work_id'])
    event = one(uow, t.events, record_id=record_id)
    origin = sources.proof.origin(row)
    review = accepted_review(uow, head, None, component,
        record_id=binding['target_record_id'], current=False)
    consumed = uow.execute(select(previews.c.preview_id).where(
        previews.c.consuming_decision_record_id == record_id)).scalar_one_or_none()
    preview = None if consumed is None else accepted_preview(uow, head, consumed, review=review)
    payload = {'private_revision': True} if preview is None else consume_payload(preview['row'])
    packet = review['proposal']['body']['packet']
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    identity = dict(case_id=head['case_id'], **asdict(claim))
    from .lifecycle_guards import target
    original_head = {**head, 'input_version': claim.input_version}
    original_state = dict(generation=claim.generation,
        proposal_record_id=review['proposal']['record']['record_id'],
        review_record_id=review['record']['record_id'], approval_record_id=None)
    original_version = review['event']['case_version'] if preview is None else preview['row']['post_case_version']
    if (any(binding[key] != value for key, value in identity.items())
            or work['case_id'] != head['case_id'] or work['component_id'] != component
            or work['purpose'] != 'REVISION' or work['state'] != 'DONE' or work['epoch'] < 1
            or work['claim_id'] is None or work['authority_revision'] is None or work['lease_expires_at'] is not None
            or work['store_id'] != head['store_id'] or work['owner_id'] != head['owner_principal_id']
            or binding['slot'] != 'PRIMARY' or work['target_record_id'] is not None
            or work['target_hash'] != target(original_head, original_state, 'REVISION')
            or binding['source_hash'] != row['content_sha256'] or row['case_version'] != claim.case_version
            or row['object_version'] != 1 or body['decision_id'] != row['object_id']
            or body['decision'] != 'REQUEST_REVISION'
            or any(body[name] != packet[name] for name in ('case_id', 'proposal_id', 'proposal_version'))
            or origin['actor'] != {'kind': 'HUMAN', 'role': 'FOUNDER', 'principal_id': body['principal_id']}
            or origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
            or origin['payload_hash'] != digest(payload, 'audit-payload/v1')
            or origin['case_version'] != claim.case_version or origin['occurred_at'] != body['decided_at']
            or body['decided_at'] != timestamp(event['accepted_at']) or event['accepted_at'] != row['recorded_at']
            or event['accepted_at'] < review['event']['accepted_at']
            or event['event_kind'] != 'REVISION' or event['status'] != 'POLICY_ASSESSMENT'
            or event['fingerprint'] != digest({'kind': 'REVISION', **asdict(
                RevisionRequested(event['event_id'], claim, record_id))}, 'lifecycle-event/v1')
            or event['case_id'] != head['case_id'] or event['work_id'] != work['work_id']
            or event['source_id'] != record_id or event['source_hash'] != row['content_sha256']
            or event['source_audit_event_id'] != origin['event_id']
            or event['pre_case_version'] != claim.case_version or event['case_version'] != claim.case_version + 1
            or event['pre_generation'] != claim.generation or event['generation'] != claim.generation + 1
            or event['pre_input_version'] != claim.input_version or event['input_version'] != claim.input_version
            or original_version != claim.case_version or review['event']['generation'] != claim.generation
            or review['event']['input_version'] != claim.input_version):
        reject(uow)
    if preview is not None and (preview['row']['consuming_decision_record_id'] != record_id
            or preview['row']['consumed_at'] != event['accepted_at']):
        reject(uow)
    audits = [audit for audit in sources.proof.events if audit['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
        and audit['correlation_id'] == event['event_id']]
    event_payload = dict(event='REVISION', work_id=work['work_id'], source_record_id=record_id,
                         generation=event['generation'])
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(event_payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind': 'SERVICE', 'component_id': component}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])):
        reject(uow)
    return dict(record=dict(row), body=body, binding=binding, work=work, event=event,
                review=review, preview=preview)
