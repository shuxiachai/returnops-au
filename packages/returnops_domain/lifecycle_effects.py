"""Read-only verification of saved effect provenance, never dispatch authority."""
import hashlib
import json
from sqlalchemy import select
from . import lifecycle_tables as t
from .lifecycle_state import reject


def fingerprint(value):
    """Frozen restricted ASCII/integer JSON fingerprint from docs/09 section6."""
    def check(item):
        if type(item) in {bool,int}:
            return
        if type(item) is str and item.isascii():
            return
        if type(item) is list:
            for value in item:
                check(value)
            return
        if type(item) is dict and all(type(key) is str and key.isascii() for key in item):
            for value in item.values():
                check(value)
            return
        raise ValueError('Invalid restricted fingerprint value')
    check(value)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')).hexdigest()


def unique_source(uow, sources, kind, object_id):
    values = [row for row in sources.proof.revisions.values() if row['kind']==kind and row['object_id']==object_id]
    if len(values) != 1:
        reject(uow)
    return sources.read(values[0]['record_id'],{kind},current_actor=False)


def saved_approval(uow, sources, approval_id):
    row, approval = unique_source(uow,sources,'APPROVAL',approval_id)
    scope = approval['scope']
    if fingerprint(scope) != approval['scope_fingerprint']:
        reject(uow)
    decision_row, decision = unique_source(uow,sources,'DECISION',approval['decision_id'])
    review_row, review_bundle = unique_source(uow,sources,'REVIEW',scope['review_id'])
    review = review_bundle['review']
    proposal_row, bundle = sources.read(review_bundle['proposal_record_id'],{'PROPOSAL'},current_actor=False)
    packet = bundle['packet']
    if (decision['decision'] != 'APPROVE' or decision.get('approval_id') != approval_id
            or decision['principal_id'] != approval['principal_id']
            or review['outcome'] not in {'PASS','PASS_WITH_WARNING'}
            or any(decision[name] != scope[name] for name in ('case_id','proposal_id','proposal_version'))
            or any(review[name] != scope[name] or packet[name] != scope[name]
                   for name in ('case_id','input_version','proposal_id','proposal_version'))
            or proposal_row['recorded_sequence'] > review_row['recorded_sequence']
            or review_row['recorded_sequence'] > decision_row['recorded_sequence']
            or decision_row['recorded_sequence'] > row['recorded_sequence']):
        reject(uow)
    create,label = scope['commands']
    if (create['command_id'] == label['command_id'] or create['parameters']['parcel_id'] != scope['parcel_id']
            or label['parameters']['parcel_id'] != scope['parcel_id']
            or label['parameters']['return_command_id'] != create['command_id']):
        reject(uow)
    lines = create['parameters']['line_items']
    ids = [line['line_item_id'] for line in lines]
    if ids != sorted(set(ids)):
        reject(uow)
    return row, approval


def original_dispatch(uow, sources, work, body, binding):
    original_id = work['target_record_id']
    if binding['dispatch_source_record_id'] != original_id:
        reject(uow)
    original_row, original = sources.read(original_id,{'OPERATION'},current_actor=False)
    original_binding = uow.execute(select(t.sources).where(t.sources.c.record_id == original_id)).mappings().one_or_none()
    if original_binding is None:
        reject(uow)
    original_work = uow.execute(select(t.work).where(t.work.c.work_id == original_binding['work_id'])).mappings().one_or_none()
    original_actor = sources.proof.origin(original_row)['actor']
    # Dispatch is an explicitly saved earlier causal fact. The observer does
    # not create or renew that authorization, even for an old generation.
    if (original_work is None or original_work['purpose'] != 'EFFECT'
            or original_actor!={'kind':'SERVICE','component_id':original_work['component_id']}
            or original_binding['case_id'] != work['case_id'] or original_work['case_id'] != work['case_id']
            or original_binding['source_hash'] != original_row['content_sha256']
            or original_binding['claim_id'] != original_work['claim_id']
            or original_binding['epoch'] != original_work['epoch']
            or original_binding['authority_revision'] != original_work['authority_revision']
            or original_binding['generation'] != original_work['generation']
            or original_binding['input_version'] != original_work['input_version']
            or original_binding['case_version'] != original_work['claimed_case_version']
            or original_row['case_version'] != original_work['claimed_case_version']
            or original_work['store_id'] != sources.head['store_id']
            or original_work['owner_id'] != sources.head['owner_principal_id']
            or original['status'] not in {'EXECUTING','UNKNOWN','RECONCILING'}):
        reject(uow)
    identity = ('operation_id','case_id','command_id','approval_id','proposal_id','proposal_version',
                'input_version','provider_id','operation_fingerprint','idempotency_key')
    if any(body[name] != original[name] for name in identity):
        reject(uow)
    approval_row,approval = saved_approval(uow,sources,body['approval_id'])
    if original_binding['target_record_id'] != approval_row['record_id']:
        reject(uow)
    if original_row['recorded_sequence'] < approval_row['recorded_sequence']:
        reject(uow)
    # Expiry is checked against the original dispatch, never the later receipt.
    from datetime import datetime
    expired = datetime.fromisoformat(approval['scope']['expires_at'].replace('Z','+00:00'))
    if original_row['recorded_at'] >= expired:
        reject(uow)
    return original_binding, approval_row, approval
