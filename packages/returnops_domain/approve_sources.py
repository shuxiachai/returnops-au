"""Full proof of a retained HUMAN approval and its unclaimed execution intent."""
from dataclasses import asdict
from sqlalchemy import select
from . import customer_tables as old, lifecycle_tables as t
from .audit import timestamp
from .canonical import digest
from .lifecycle_events import ApprovalAccepted, LifecycleClaim
from .lifecycle_schema import APPROVAL_VERSIONS, version
from .lifecycle_sources import Sources
from .lifecycle_state import reject
from .manual_target import one
from .preview_tables import previews
from .preview_profile import APPROVAL_COMPONENT as COMPONENT
from .preview_sources import (accepted_preview, source_target, consume_payload, current_policy, EMPTY)


def execution_identity(approval_record, approval, generation):
    values = dict(approval_record_id=approval_record['record_id'], approval_hash=approval_record['content_sha256'],
        scope_fingerprint=approval['scope_fingerprint'], case_id=approval['scope']['case_id'],
        input_version=approval['scope']['input_version'], generation=generation)
    target_hash = digest(values, 'approved-execution-intent/v1')
    return 'execution_' + target_hash, target_hash


def read_target(uow, head, state, request, component, *, original_state=None, consumer=None):
    initial = state if original_state is None else original_state
    if (component != COMPONENT or version(uow.connection) not in APPROVAL_VERSIONS or initial is None
            or state is None or not initial['available'] or not state['available']
            or initial['preview_id'] is None or any(initial[name] is not None for name in EMPTY)):
        reject(uow)
    expected = request['expected_case_version']
    review, preview = source_target(uow, head, initial, expected_version=expected, allow_consumed=consumer is not None)
    row, body = preview['row'], preview['body']
    packet = review['proposal']['body']['packet']
    if (request.get('decision') != 'APPROVE' or request.get('preview_id') != row['preview_id']
            or request.get('scope_fingerprint') != body['scope_fingerprint']
            or any(request.get(name) != packet[name] for name in ('proposal_id','proposal_version'))
            or row['consuming_decision_record_id'] != consumer
            or any(state[name] != initial[name] for name in
                ('input_version','generation','proposal_version','proposal_record_id','review_record_id','preview_id'))):
        reject(uow)
    if original_state is None:
        if head['status'] != 'AWAITING_APPROVAL' or head['case_version'] != expected:
            reject(uow)
    elif (head['status'] != 'APPROVED' or head['case_version'] != expected+1
            or state['approval_record_id'] is None or state['outcome'] is not None):
        reject(uow)
    return preview


def approval_relations(uow, head, sources, row, body, binding, work, decision_id, preview):
    decision_row, decision = sources.read(decision_id, {'DECISION'}, current_actor=False)
    origin = sources.proof.origin(row)
    decision_origin = sources.proof.origin(decision_row)
    p = preview['row']; saved = preview['body']; review = preview['review']
    actor = {'kind':'HUMAN','role':'FOUNDER','principal_id':body['principal_id']}
    if (row['kind'] != 'APPROVAL' or row['object_id'] != body['approval_id'] or row['object_version'] != 1
            or row['case_version'] != work['claimed_case_version']
            or work['claimed_case_version'] != p['post_case_version']
            or body['preview_id'] != p['preview_id'] or body['scope'] != saved['scope']
            or body['scope_fingerprint'] != saved['scope_fingerprint']
            or decision['decision'] != 'APPROVE' or decision['decision_id'] != body['decision_id']
            or decision['decision_id'] != decision_row['object_id'] or decision_row['object_version'] != 1
            or decision['principal_id'] != body['principal_id'] or decision.get('approval_id') != body['approval_id']
            or any(decision[name] != saved['scope'][name] for name in ('case_id','proposal_id','proposal_version'))
            or decision_row['case_version'] != row['case_version']
            or decision_row['recorded_sequence'] + 1 != row['recorded_sequence']
            or review['record']['recorded_sequence'] >= decision_row['recorded_sequence']
            or decision_row['recorded_at'] != row['recorded_at'] or p['consumed_at'] != row['recorded_at']
            or row['recorded_at'] < p['issued_at'] or row['recorded_at'] >= p['expires_at']
            or decision['decided_at'] != body['issued_at'] or body['issued_at'] != timestamp(row['recorded_at'])
            or p['consuming_decision_record_id'] != decision_id
            or origin['actor'] != actor or decision_origin['actor'] != actor
            or origin['event_type'] != 'FOUNDER_APPROVAL_ISSUED'
            or decision_origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
            or origin['correlation_id'] != decision_origin['correlation_id']
            or origin['payload_hash'] != digest(consume_payload(p), 'audit-payload/v1')
            or decision_origin['payload_hash'] != origin['payload_hash']
            or binding['target_record_id'] != review['record']['record_id']
            or binding['order_projection_id'] != p['order_projection_id']):
        reject(uow)
    return dict(decision_record=dict(decision_row), decision=decision, origin=origin, decision_origin=decision_origin)


def verify_staged(uow, head, state, row, body, binding, work, event, now):
    if work['component_id'] != COMPONENT or work['purpose'] != 'APPROVAL':
        reject(uow)
    request = dict(expected_case_version=head['case_version'], decision='APPROVE',
        preview_id=event.preview_id, scope_fingerprint=body['scope_fingerprint'],
        **{name:body['scope'][name] for name in ('proposal_id','proposal_version')})
    preview = read_target(uow, head, state, request, COMPONENT, consumer=event.decision_record_id)
    if now < preview['row']['issued_at'] or now >= preview['row']['expires_at']:
        reject(uow)
    current_policy(uow, head, preview['row'])
    approval_relations(uow, head, Sources(uow, head, COMPONENT), row, body, binding, work,
                       event.decision_record_id, preview)
    return dict(state=dict(state), request=request, preview=preview, decision_record_id=event.decision_record_id)


def accepted_approval(uow, head, record_id, component):
    if component != COMPONENT or version(uow.connection) not in APPROVAL_VERSIONS:
        reject(uow)
    sources = Sources(uow, head, component)
    row, body = sources.read(record_id, {'APPROVAL'}, current_actor=False)
    binding = one(uow, t.sources, record_id=record_id)
    work = one(uow, t.work, work_id=binding['work_id'])
    event = one(uow, t.events, record_id=record_id)
    preview = accepted_preview(uow, head, body['preview_id'])
    decision_id = preview['row']['consuming_decision_record_id']
    if decision_id is None:
        reject(uow)
    related = approval_relations(uow, head, sources, row, body, binding, work, decision_id, preview)
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    expected_binding = dict(case_id=head['case_id'], **asdict(claim), source_hash=row['content_sha256'], slot='PRIMARY')
    from .lifecycle_guards import target
    original_head = {**head, 'input_version':claim.input_version}
    original_state = dict(generation=claim.generation, proposal_record_id=preview['row']['proposal_record_id'],
        review_record_id=preview['row']['review_record_id'], preview_id=preview['row']['preview_id'], approval_record_id=None)
    expected_event = ApprovalAccepted(event['event_id'], claim, record_id, decision_id, body['preview_id'])
    if (any(binding[name] != value for name,value in expected_binding.items())
            or work['purpose'] != 'APPROVAL' or work['component_id'] != COMPONENT or work['state'] != 'DONE'
            or work['case_id'] != head['case_id'] or work['store_id'] != head['store_id']
            or work['owner_id'] != head['owner_principal_id'] or work['epoch'] < 1
            or work['claim_id'] is None or work['authority_revision'] is None or work['lease_expires_at'] is not None
            or work['target_record_id'] is not None or work['target_hash'] != target(original_head, original_state, 'APPROVAL')
            or claim.input_version != preview['row']['input_version'] or claim.generation != preview['row']['generation']
            or event['fingerprint'] != digest({'kind':'APPROVAL', **asdict(expected_event)}, 'lifecycle-event/v1')
            or event['event_kind'] != 'APPROVAL' or event['status'] != 'APPROVED'
            or event['case_id'] != head['case_id'] or event['work_id'] != work['work_id']
            or event['source_id'] != record_id or event['source_hash'] != row['content_sha256']
            or event['source_audit_event_id'] != related['origin']['event_id']
            or event['pre_case_version'] != claim.case_version or event['case_version'] != claim.case_version + 1
            or event['pre_input_version'] != claim.input_version or event['input_version'] != claim.input_version
            or event['pre_generation'] != claim.generation or event['generation'] != claim.generation
            or event['accepted_at'] != row['recorded_at']):
        reject(uow)
    audits = [a for a in sources.proof.events if a['event_type'] == 'LIFECYCLE_EVENT_ACCEPTED'
        and a['correlation_id'] == event['event_id']]
    payload = dict(event='APPROVAL', work_id=work['work_id'], source_record_id=record_id, generation=claim.generation)
    if (len(audits) != 1 or audits[0]['payload_hash'] != digest(payload, 'audit-payload/v1')
            or audits[0]['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
            or audits[0]['case_version'] != event['case_version']
            or audits[0]['occurred_at'] != timestamp(event['accepted_at'])):
        reject(uow)
    execution_id, target_hash = execution_identity(row, body, claim.generation)
    execution = one(uow, t.work, work_id=execution_id)
    if (execution['case_id'] != head['case_id'] or execution['component_id'] != COMPONENT
            or execution['store_id'] != head['store_id'] or execution['owner_id'] != head['owner_principal_id']
            or execution['purpose'] != 'EXECUTION' or execution['target_record_id'] != record_id
            or execution['target_hash'] != target_hash or execution['idempotency_key'] != execution_id
            or execution['input_version'] != claim.input_version or execution['generation'] != claim.generation
            or execution['created_at'] != event['accepted_at']
            or execution['state'] not in {'PENDING','SUPERSEDED','PAUSED'}
            or any(execution[name] is not None for name in
                ('claim_id','claimed_case_version','lease_expires_at','authority_revision'))
            or execution['state'] == 'PENDING' and execution['epoch'] != 0):
        reject(uow)
    return dict(record=dict(row), body=body, binding=binding, work=work, event=event,
                preview=preview, execution=execution, **related)


def check_seal(uow, seal):
    for table, key, saved in (
        (old.history,'record_id',seal['record']), (old.history,'record_id',seal['decision_record']),
        (t.sources,'record_id',seal['binding']), (t.work,'work_id',seal['work']),
        (t.work,'work_id',seal['execution']), (t.events,'record_id',seal['event']),
        (previews,'preview_id',seal['preview']['row']),
    ):
        if one(uow, table, **{key:saved[key]}) != saved:
            reject(uow)
