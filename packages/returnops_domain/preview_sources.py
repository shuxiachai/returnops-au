"""Full retained proof of exact, server-issued preview version transitions."""
from datetime import timedelta
from sqlalchemy import select, update
from . import customer_tables as old, investigation_tables as investigation
from .preview_tables import previews
from . import preview_profile as policy
from .audit import timestamp
from .canonical import digest, decode_document
from . import founder_codec as finite
from .errors import ReceiptUnavailable
from .founder_integrity import CaseProof
from .lifecycle_schema import CURRENT, version
from .lifecycle_sources import authority
from .lifecycle_state import reject
from .manual_target import one
from .pass_review_sources import accepted_review

EMPTY = ('approval_record_id','outcome_record_id','outcome','notification_id',
         'notification_record_id','notification_hash','notification_work_id','return_record_id','label_record_id')
IMMUTABLE = ('preview_id','case_id','component_id','store_id','owner_id','input_version','generation',
    'proposal_record_id','proposal_hash','review_record_id','review_hash','review_event_id','review_event_hash',
    'order_projection_id','order_hash','profile_version','profile_hash','authority_revision',
    'pre_case_version','post_case_version','previous_preview_id','issued_at','expires_at','body_hash',
    'request_key','request_fingerprint')


def request_fingerprint(version_number):
    return digest({'expected_case_version':version_number}, 'action-preview-request/v1')


def payload(row):
    value = {name:row[name] for name in IMMUTABLE}
    for name in ('issued_at','expires_at'):
        value[name] = timestamp(value[name])
    return dict(profile='action-preview-proof/v1', transition=value)


def authorize(uow, case_id):
    if version(uow.connection) != CURRENT:
        reject(uow)
    head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case_id)
        .with_for_update()).mappings().one_or_none()
    if head is None or not head['available']:
        reject(uow, 'NOT_FOUND')
    return head, authority(uow, head, policy.COMPONENT, 'PREVIEW')


def source_target(uow, head, state, *, expected_version, allow_consumed=False):
    if (state is None or not state['available'] or head['current_failure_id'] is not None
            or state['proposal_record_id'] is None or state['review_record_id'] is None):
        reject(uow)
    block = uow.execute(select(investigation.state.c.current_block_id).where(
        investigation.state.c.case_id == head['case_id'])).scalar_one_or_none()
    if block is not None:
        reject(uow)
    review = accepted_review(uow, head, state, policy.COMPONENT)
    if state['preview_id'] is None:
        if review['event']['case_version'] != expected_version:
            reject(uow)
        return review, None
    preview = accepted_preview(uow, head, state['preview_id'], review=review)
    if (preview['row']['post_case_version'] != expected_version
            or preview['row']['input_version'] != head['input_version']
            or preview['row']['generation'] != state['generation']
            or not allow_consumed and preview['row']['consuming_decision_record_id'] is not None):
        reject(uow)
    return review, preview


def accepted_preview(uow, head, preview_id, *, review=None):
    """Prove every predecessor back to the exact original REVIEW_PASS version.

    No <= version admission. Each edge is exactly +1, with the same retained
    input/proposal/review and an explicit expired predecessor replacement.
    Reading an old acceptance never grants new approval or execution authority.
    """
    if version(uow.connection) != CURRENT:
        reject(uow)
    row = one(uow, previews, preview_id=preview_id)
    if not row['available'] or row['body'] is None:
        raise ReceiptUnavailable()
    review = review or accepted_review(uow, head, None, policy.COMPONENT,
        record_id=row['review_record_id'], current=False)
    proof = CaseProof(uow, head)
    audits = {event['event_id']:event for event in proof.events}
    chain = []
    seen = set()
    candidate = row
    while True:
        if candidate['preview_id'] in seen:
            reject(uow)
        seen.add(candidate['preview_id'])
        body = _verify_row(uow, head, candidate, review, audits)
        chain.append(dict(row=candidate, body=body))
        previous_id = candidate['previous_preview_id']
        if previous_id is None:
            if candidate['pre_case_version'] != review['event']['case_version']:
                reject(uow)
            break
        previous = one(uow, previews, preview_id=previous_id)
        if (previous['post_case_version'] != candidate['pre_case_version']
                or previous['consuming_decision_record_id'] is not None
                or candidate['issued_at'] < previous['expires_at']):
            # This v1 profile cannot change version at runtime; replacement is
            # exclusively an explicit new intent after the predecessor expires.
            reject(uow)
        candidate = previous
    return dict(row=row, body=chain[0]['body'], chain=chain, review=review)


def _verify_row(uow, head, row, review, audits):
    if not row['available'] or row['body'] is None:
        raise ReceiptUnavailable()
    body = decode_document(row['body'])
    body_hash = digest(body, 'action-preview-body/v1')
    original = policy.PROFILE
    expected = dict(case_id=head['case_id'], component_id=policy.COMPONENT,
        store_id=head['store_id'], owner_id=head['owner_principal_id'],
        input_version=review['event']['input_version'], generation=review['event']['generation'],
        proposal_record_id=review['proposal']['record']['record_id'],
        proposal_hash=review['proposal']['record']['content_sha256'],
        review_record_id=review['record']['record_id'], review_hash=review['record']['content_sha256'],
        review_event_id=review['event']['event_id'], review_event_hash=review['event']['fingerprint'],
        order_projection_id=review['proposal']['binding']['order_projection_id'],
        order_hash=finite.digest(review['proposal']['body']['order_lookup']),
        profile_version=original['version'], profile_hash=policy.profile_hash(original))
    if (any(row[name] != value for name,value in expected.items())
            or row['post_case_version'] != row['pre_case_version'] + 1
            or row['authority_revision'] < 1 or row['removal_reason'] is not None
            or row['issued_at'] < review['event']['accepted_at']
            or row['request_fingerprint'] != request_fingerprint(row['pre_case_version'])
            or row['body_hash'] != body_hash
            or row['expires_at'] != row['issued_at'] + timedelta(seconds=original['ttl_seconds'])
            or body != policy.build(row['preview_id'], review['proposal']['body'],
                                    review['body']['review'], row['issued_at'], original)):
        reject(uow)
    audit = audits.get(row['audit_event_id'])
    if (audit is None or audit['event_hash'] != row['audit_hash']
            or audit['event_type'] != 'ACTION_PREVIEW_ACCEPTED'
            or audit['actor'] != {'kind':'SERVICE','component_id':policy.COMPONENT}
            or audit['case_version'] != row['post_case_version']
            or audit['occurred_at'] != timestamp(row['issued_at'])
            or audit['payload_hash'] != digest(payload(row), 'audit-payload/v1')
            or audit['object_ids'] != [row['preview_id']] or audit['history_refs']):
        reject(uow)
    if row['consuming_decision_record_id'] is not None:
        decision = one(uow, old.history, record_id=row['consuming_decision_record_id'])
        origin = CaseProof(uow, head).origin(decision)
        if (decision['case_id'] != head['case_id'] or decision['kind'] != 'DECISION'
                or decision['case_version'] != row['post_case_version']
                or decision['recorded_at'] != row['consumed_at']
                or row['consumed_at'] < row['issued_at']
                or origin['event_type'] != 'FOUNDER_DECISION_ACCEPTED'
                or origin['actor'].get('role') != 'FOUNDER' or origin['actor']['kind'] != 'HUMAN'
                or origin['payload_hash'] != digest(consume_payload(row), 'audit-payload/v1')):
            reject(uow)
    elif row['consumed_at'] is not None:
        reject(uow)
    return body


def consume_payload(row):
    return dict(private_preview_decision='v1', preview_id=row['preview_id'],
                preview_hash=row['body_hash'], preview_audit_hash=row['audit_hash'])


def consume(uow, seal, decision_record_id, now):
    row = seal['row']
    changed = uow.execute(update(previews).where(previews.c.preview_id == row['preview_id'],
        previews.c.available.is_(True), previews.c.consuming_decision_record_id.is_(None)).values(
        consuming_decision_record_id=decision_record_id, consumed_at=now))
    if changed.rowcount != 1:
        reject(uow)


def current_policy(uow, head, row):
    value = policy.profile()
    grant = authority(uow, head, policy.COMPONENT, 'PREVIEW')
    if (value != policy.PROFILE or row['profile_hash'] != policy.profile_hash(value)
            or row['profile_version'] != value['version'] or grant['revision'] != row['authority_revision']):
        reject(uow)
    return dict(grant)
