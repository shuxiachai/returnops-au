"""Closed customer-safe CORE_MOCK v2 messages; never caller-selected promises."""
import hashlib
import json
from pathlib import Path
import re

COMPONENT = 'notification-delivery-v2'
CHANNEL = 'CORE_MOCK'
PROFILES = {
    'RETURN_CREATED': 'return-created-mock/v2',
    'REJECTED': 'rejected-mock/v2',
    'MANUAL_HANDLED': 'manual-handled-mock/v2',
}
MESSAGES = {
    'RETURN_CREATED': (
        'A simulated return and parcel label have been recorded. The prototype PDF is not valid for postage. '
        'This prototype has not arranged a real shipment or made a charge.'),
    'REJECTED': (
        'The store operator recorded a rejection for this request. This prototype message does not determine '
        'your legal rights. It does not authorise a shipment or a payment.'),
    'MANUAL_HANDLED': (
        'The store operator recorded a manual-handling outcome. Any unresolved earlier operation remains '
        'uncertain; this message does not assert that it never happened. No shipment or payment is authorised here.'),
}
COMMON_STEPS = (
    'Next step: ask the store operator to confirm the contact channel and any further arrangements.',
    'Packaging: no physical packing is arranged by this prototype; packing instructions are not applicable to this mock flow.',
    'Drop-off: no physical drop-off is arranged. Never post a parcel using a prototype label.',
    'Responsibility: not yet determined here; any applicable real-world responsibility requires human confirmation.',
    'Cost: not yet determined here; the prototype neither charges nor settles real-world return costs.',
)
CATEGORIES = {
    'packaging': {'disposition': 'NOT_APPLICABLE', 'source': 'FIXED_CORE_MOCK_BOUNDARY'},
    'drop_off': {'disposition': 'NOT_APPLICABLE', 'source': 'FIXED_CORE_MOCK_BOUNDARY'},
    'responsibility': {'disposition': 'UNKNOWN', 'source': 'NO_REVIEWED_REAL_WORLD_DETERMINATION'},
    'cost': {'disposition': 'UNKNOWN', 'source': 'NO_REVIEWED_REAL_WORLD_DETERMINATION'},
    'next_step': {'disposition': 'UNKNOWN', 'source': 'HUMAN_CONFIRMATION_REQUIRED'},
}


def implementation_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def profile_hash(outcome):
    if outcome not in PROFILES:
        raise ValueError('Unsupported notification outcome')
    material = {'profile': PROFILES[outcome], 'channel': CHANNEL,
                'implementation_sha256': implementation_hash(), 'message': MESSAGES[outcome],
                'steps': list(COMMON_STEPS), 'categories': CATEGORIES}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':')).encode('ascii')).hexdigest()


def render(outcome, *, label_evidence_id=None):
    """Pure formatting after a real producer proof; this grants no authority."""
    if outcome not in PROFILES:
        raise ValueError('Unsupported notification outcome')
    steps = list(COMMON_STEPS)
    if outcome == 'RETURN_CREATED':
        if not isinstance(label_evidence_id, str) or re.fullmatch(r'glabel_[0-9a-f]{64}', label_evidence_id) is None:
            raise ValueError('Certified generated label reference required')
        steps.insert(0, 'View the simulated label using authorised attachment access at '
                     f'/v1/evidence/{label_evidence_id}/content. This PDF must not be used for postage.')
    elif label_evidence_id is not None:
        raise ValueError('Reject/manual notification cannot assert a generated return result')
    return {'message': MESSAGES[outcome], 'next_steps': steps}
