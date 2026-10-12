"""Dispatch revision proof by the durable review event, never by head status."""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, founder_codec as finite
from . import investigation_tables as investigation, lifecycle_tables as t
from .audit import timestamp
from .canonical import digest
from .lifecycle_events import LifecycleClaim, RevisionRequested
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one
from .review_sources import accepted_review


def _review_kind(uow, record_id):
    if record_id is None:
        reject(uow)
    event = one(uow, t.events, record_id=record_id)
    if event['event_kind'] not in {'REVIEW', 'REVIEW_PASS'}:
        reject(uow)
    return event['event_kind']


def read_target(uow, head, state, request, component, *, original_state=None, consumer=None):
    initial = state if original_state is None else original_state
    if initial is None or state is None:
        reject(uow)
    if _review_kind(uow, initial['review_record_id']) == 'REVIEW_PASS':
        from .pass_revision_sources import read_target as read_pass_target
        return read_pass_target(uow, head, state, request, component,
            original_state=original_state, consumer=consumer)
    return _read_escalate_target(uow, head, state, request, component, original_state=original_state)


def read_preview(uow, head, state, expected_version, *, consumer=None):
    if state is None:
        reject(uow)
    if _review_kind(uow, state['review_record_id']) == 'REVIEW_PASS':
        from .pass_revision_sources import read_preview as read_pass_preview
        return read_pass_preview(uow, head, state, expected_version, consumer=consumer)
    if state['preview_id'] is not None:
        reject(uow)
    return None


def check_current(uow, head, original_state, review, component):
    """A historical revision proof cannot substitute for current raw sources."""
    if _review_kind(uow, original_state['review_record_id']) == 'REVIEW_PASS':
        from .pass_review_sources import accepted_review as verifier
    else:
        verifier = accepted_review
    if verifier(uow, head, original_state, component, current=True) != review:
        reject(uow)


def check_seal(uow, seal):
    """Recheck saved rows after expensive proof reads and fresh authority."""
    for item in (seal, seal['review'], seal['review']['proposal']):
        for table, key, name in ((old.history, 'record_id', 'record'),
                (t.sources, 'record_id', 'binding'), (t.work, 'work_id', 'work'),
                (t.events, 'record_id', 'event')):
            saved = item[name]
            if one(uow, table, **{key: saved[key]}) != saved:
                reject(uow)
        content = one(uow, old.history_contents, record_id=item['record']['record_id'])
        if finite.decode_document(content['body']) != item['body']:
            reject(uow)
    if seal.get('preview') is not None:
        from .preview_tables import previews
        for item in seal['preview']['chain']:
            row = item['row']
            if one(uow, previews, preview_id=row['preview_id']) != row:
                reject(uow)


def check_actor(uow, head, seal):
    """Fresh principal check after provenance reads; no session is fabricated."""
    person = uow.execute(select(old.principals).where(
        old.principals.c.principal_id == seal['body']['principal_id']).with_for_update()).mappings().one_or_none()
    if (person is None or not person['enabled'] or person['role'] != 'FOUNDER'
            or person['store_id'] != head['store_id']):
        reject(uow, 'FORBIDDEN')


def _read_escalate_target(uow, head, state, request, component, *, original_state=None):
    # The original references are server-derived before invalidation. Using them
    # with current=True deliberately repeats live input/order verification; a
    # historical current=False read alone would not verify retained raw inputs.
    initial = state if original_state is None else original_state
    if initial is None or state is None:
        reject(uow)
    seal = accepted_review(uow, head, initial, component)
    packet = seal['proposal']['body']['packet']
    block = uow.execute(select(investigation.state.c.current_block_id).where(
        investigation.state.c.case_id == head['case_id'])).scalar_one_or_none()
    expected = request['expected_case_version']
    if (request.get('decision') != 'REQUEST_REVISION'
            or any(request.get(k) != packet[k] for k in ('proposal_id', 'proposal_version'))
            or seal['event']['case_version'] != expected or head['current_failure_id'] is not None
            or block is not None or not state['available'] or not initial['available']
            or state['input_version'] != head['input_version']
            or initial['input_version'] != head['input_version']
            or any(initial[n] is not None or state[n] is not None for n in
                ('preview_id', 'approval_record_id', 'outcome_record_id', 'outcome'))):
        reject(uow)
    if original_state is None:
        if head['status'] != 'ESCALATED' or head['case_version'] != expected:
            reject(uow)
    elif (head['status'] != 'POLICY_ASSESSMENT' or head['case_version'] != expected + 1
            or state['generation'] != initial['generation'] + 1
            or state['proposal_version'] != initial['proposal_version']
            or state['proposal_record_id'] is not None or state['review_record_id'] is not None):
        reject(uow)
    return seal


def accepted_revision(uow, head, record_id, component):
    binding = one(uow, t.sources, record_id=record_id)
    if _review_kind(uow, binding['target_record_id']) == 'REVIEW_PASS':
        from .pass_revision_sources import accepted_revision as accepted_pass_revision
        return accepted_pass_revision(uow, head, record_id, component)
    return _accepted_escalate_revision(uow, head, record_id, component)


def _accepted_escalate_revision(uow, head, record_id, component):
    """Verify the original durable revision fact without requiring current refs."""
    sources = Sources(uow, head, component)
    row, body = sources.read(record_id, {'DECISION'}, current_actor=False)
    binding = one(uow, t.sources, record_id=record_id)
    work = one(uow, t.work, work_id=binding['work_id'])
    event = one(uow, t.events, record_id=record_id)
    origin = sources.proof.origin(row)
    review = accepted_review(uow, head, None, component,
        record_id=binding['target_record_id'], current=False)
    packet = review['proposal']['body']['packet']
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    identity = dict(case_id=head['case_id'], **asdict(claim))
    from .lifecycle_guards import target
    original_head = {**head, 'input_version':claim.input_version}
    original_state = dict(generation=claim.generation, proposal_record_id=review['proposal']['record']['record_id'],
        review_record_id=review['record']['record_id'], approval_record_id=None)
    if (any(binding[k] != v for k, v in identity.items()) or work['component_id'] != component
            or work['purpose'] != 'REVISION' or work['state'] != 'DONE' or work['epoch'] < 1
            or work['claim_id'] is None or work['store_id'] != head['store_id']
            or work['owner_id'] != head['owner_principal_id'] or binding['slot'] != 'PRIMARY'
            or work['target_record_id'] is not None or work['target_hash'] != target(original_head, original_state, 'REVISION')
            or event['accepted_at'] != row['recorded_at']
            or binding['source_hash'] != row['content_sha256'] or row['case_version'] != claim.case_version
            or body['decision'] != 'REQUEST_REVISION'
            or any(body[k] != packet[k] for k in ('case_id', 'proposal_id', 'proposal_version'))
            or origin['actor'] != {'kind':'HUMAN', 'role':'FOUNDER', 'principal_id':body['principal_id']}
            or origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
            or body['decided_at'] != timestamp(event['accepted_at'])
            or origin['occurred_at'] != body['decided_at']
            or event['event_kind'] != 'REVISION' or event['status'] != 'POLICY_ASSESSMENT'
            or event['fingerprint'] != digest({'kind':'REVISION', **asdict(
                RevisionRequested(event['event_id'], claim, record_id))}, 'lifecycle-event/v1')
            or event['case_id'] != head['case_id'] or event['work_id'] != work['work_id']
            or event['source_id'] != record_id or event['source_hash'] != row['content_sha256']
            or event['source_audit_event_id'] != origin['event_id']
            or event['pre_case_version'] != claim.case_version or event['case_version'] != claim.case_version + 1
            or event['pre_generation'] != claim.generation or event['generation'] != claim.generation + 1
            or event['pre_input_version'] != claim.input_version or event['input_version'] != claim.input_version
            or review['event']['case_version'] != claim.case_version
            or review['event']['generation'] != claim.generation
            or review['event']['input_version'] != claim.input_version):
        reject(uow)
    audits = [a for a in sources.proof.events if a['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
        and a['correlation_id'] == event['event_id']]
    payload = dict(event='REVISION', work_id=work['work_id'], source_record_id=record_id,
        generation=event['generation'])
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind':'SERVICE', 'component_id':component}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])):
        reject(uow)
    return dict(record=dict(row), body=body, binding=binding, work=work, event=event, review=review)
