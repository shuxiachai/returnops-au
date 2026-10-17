"""Fixed, server-owned synthetic two-cup profile; no provider is invoked."""
from copy import deepcopy
from datetime import timedelta
from .audit import timestamp
from .canonical import digest
from .errors import FlowError
from .lifecycle_effects import fingerprint
from .wire import validate

COMPONENT = 'action-preview-v1'
APPROVAL_COMPONENT = 'founder-approve-v1'
PROFILE = dict(version='mock-v1', scenario='synthetic-cups-pass-v1', ttl_seconds=300,
    environment='SIMULATED', currency='AUD', amount_ceiling_minor=0,
    return_provider='provider-mock-return', label_provider='provider-mock-label',
    label_format='PDF', chargeable=False)


def profile():
    """A fresh complete policy, not request-controlled or a live-provider grant."""
    return deepcopy(PROFILE)


def profile_hash(value):
    return digest(value, 'action-preview-profile/v1')


def stable_id(kind, value):
    return kind + '_' + digest(value, 'action-preview-' + kind + '/v1')


def selected_lines(packet, order):
    """Builder boundary (1..100); the runtime additionally checks the fixed family."""
    lines = deepcopy(packet['facts']['line_items'])
    if not 1 <= len(lines) <= 100:
        raise FlowError('INVALID_STATE')
    ids = [line['line_item_id'] for line in lines]
    order_lines = order['line_items']
    order_ids = [line['line_item_id'] for line in order_lines]
    if len(ids) != len(set(ids)) or len(order_ids) != len(set(order_ids)):
        raise FlowError('INVALID_STATE')
    quantities = {line['line_item_id']:line['quantity'] for line in order_lines}
    for line in lines:
        if type(line.get('quantity')) is not int:
            raise FlowError('INVALID_STATE')
        validate('LineSelection', line, internal=True)
        quantity = quantities.get(line['line_item_id'])
        if type(quantity) is not int or line['quantity'] > quantity:
            raise FlowError('INVALID_STATE')
    return sorted(lines, key=lambda line:line['line_item_id'])


def build(preview_id, proposal, review, issued_at, policy):
    """Build only from a previously verified retained proposal/review and policy."""
    if issued_at.utcoffset() is None or policy != PROFILE:
        raise FlowError('INVALID_STATE')
    packet = proposal['packet']
    lookup = proposal['order_lookup']
    if lookup['status'] != 'MATCHED':
        raise FlowError('INVALID_STATE')
    order = lookup['snapshot']
    parcel = stable_id('parcel', preview_id)
    create_id = stable_id('return_cmd', preview_id)
    commands = [dict(command_id=create_id, type='CREATE_RETURN', provider_id=policy['return_provider'],
        parameters=dict(order_id=order['order_id'], line_items=selected_lines(packet, order), parcel_id=parcel)),
        dict(command_id=stable_id('label_cmd', preview_id), type='GENERATE_LABEL', provider_id=policy['label_provider'],
        parameters=dict(parcel_id=parcel, return_command_id=create_id,
                        label_format=policy['label_format'], chargeable=policy['chargeable']))]
    scope = dict(**{name:packet[name] for name in ('case_id','input_version','proposal_id','proposal_version')},
        review_id=review['review_id'], parcel_id=parcel, commands=commands,
        currency=policy['currency'], amount_ceiling_minor=policy['amount_ceiling_minor'],
        expires_at=timestamp(issued_at + timedelta(seconds=policy['ttl_seconds'])),
        allowlist_version=policy['version'], environment=policy['environment'])
    body = dict(preview_id=preview_id, scope=scope, scope_fingerprint=fingerprint(scope))
    return validate('ActionPreview', body, internal=True)
