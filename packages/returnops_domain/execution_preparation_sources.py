"""Separate fresh and retained preparation proofs; never a dispatch permit."""
from sqlalchemy import select
from . import customer_tables as old, founder_tables as founder, lifecycle_tables as lifecycle
from . import founder_codec as finite, preview_profile as policy
from .audit import timestamp
from .canonical import digest
from .approval_admission_sources import (read_proof, source_closure as approval_closure,
    restricted_bytes, approval_receipt, AdmissionUncertain)
from .approve_sources import accepted_approval, execution_identity
from .execution_preparation_tables import preparations
from .lifecycle_effects import fingerprint
from .lifecycle_sources import Sources
from .lifecycle_state import current, reject, MAX_VERSION
from .manual_target import one
from .pass_review_sources import accepted_review


def identities(work_id):
    value = dict(approval_execution_work_id=work_id, command_type='CREATE_RETURN')
    return dict(preparation_id='preparation_' + digest(value, 'execution-preparation-id/v1'),
        operation_id='operation_' + digest(value, 'execution-operation-id/v1'),
        first_operation_record_id='operation_row_' + digest(value, 'execution-first-record-id/v1'),
        effect_key='effect_' + digest(value, 'execution-effect-key/v1'))


def request_fingerprint(command):
    # Validation and exact bytes happen before this typed digest; changed
    # parameters cannot change any stable identity above.
    restricted_bytes(command)
    return digest(command, 'execution-preparation-request/v1')


def source_closure(uow, case_id):
    result = approval_closure(uow, case_id)
    result[preparations.name] = [dict(row) for row in uow.execute(select(preparations)
        .where(preparations.c.case_id == case_id).order_by(preparations.c.preparation_id)).mappings()]
    return result


def discover(uow, work_id):
    return uow.execute(select(preparations).where(
        preparations.c.approval_execution_work_id == work_id,
        preparations.c.command_type == 'CREATE_RETURN')).mappings().one_or_none()


def fresh_proof(uow, actor, head, expected, work_id, original_key, candidate):
    # The original A2.02 checker retains its strict prior-operation denial.
    # A sidecar without its operation is corruption, never a fresh start.
    if uow.execute(select(preparations.c.preparation_id).where(
            preparations.c.case_id == head['case_id'])).first():
        reject(uow)
    proof = read_proof(uow, actor, head, expected, work_id, original_key, candidate)
    if any(event['event_type'] == 'OPERATION_REVISION_RECORDED'
           for event in Sources(uow, head, policy.APPROVAL_COMPONENT).proof.events):
        reject(uow)
    if max(head['history_sequence'], head['audit_sequence']) >= MAX_VERSION:
        reject(uow)
    return proof


def operation(head, proof, stable, now):
    approval = proof['approval']['body']
    scope = approval['scope']; command = scope['commands'][0]
    body = dict(operation_id=stable['operation_id'], case_id=head['case_id'],
        case_version=proof['approval']['event']['case_version'], command_id=command['command_id'],
        approval_id=approval['approval_id'], proposal_id=scope['proposal_id'],
        proposal_version=scope['proposal_version'], input_version=scope['input_version'],
        provider_id=command['provider_id'], operation_fingerprint=proof['operation_fingerprint'],
        status='PENDING', attempt_count=1, updated_at=timestamp(now), idempotency_key=stable['effect_key'])
    return finite.validate('OperationAttempt', body)


def payload(row, body, source_hash):
    immutable = {name:row[name] for name in ('preparation_id', 'case_id', 'approval_execution_work_id',
        'original_approval_acceptance_id', 'command_type', 'operation_id', 'first_operation_record_id',
        'effect_key', 'request_fingerprint', 'profile_hash', 'prepared_authority_revision')}
    immutable.update(created_at=timestamp(row['created_at']), first_operation_hash=source_hash,
                     first_operation=body)
    return dict(profile='execution-preparation/v1', preparation=immutable)


def audit_payload(row, body, source_hash):
    value = payload(row, body, source_hash)
    return {**value, 'binding_hash':digest(value, 'execution-preparation/v1')}


def retained_proof(uow, actor, head, expected, work_id, original_key, candidate, row):
    """Validate original preparation independently, including original receipt.

    Natural expiry does not erase history. Current session/case/EXECUTION
    authority is checked by the service, without interpreting replay as a permit.
    Retained-away bodies fail closed and are never reconstructed.
    """
    stable = identities(work_id)
    if (row['case_id'] != head['case_id'] or row['approval_execution_work_id'] != work_id
            or any(row[name] != value for name, value in stable.items())
            or row['command_type'] != 'CREATE_RETURN'
            or row['state'] not in {'PENDING', 'PAUSED', 'SUPERSEDED'}):
        reject(uow)
    if row['request_fingerprint'] != request_fingerprint(candidate):
        reject(uow, 'IDEMPOTENCY_CONFLICT')
    sources = Sources(uow, head, policy.APPROVAL_COMPONENT)
    record, body = sources.read(row['first_operation_record_id'], {'OPERATION'}, current_actor=False)
    execution = one(uow, lifecycle.work, work_id=work_id)
    approval = accepted_approval(uow, head, execution['target_record_id'], policy.APPROVAL_COMPONENT)
    receipt = approval_receipt(uow, actor, head, approval, original_key)
    scope = approval['body']['scope']; profile = policy.profile()
    proof = dict(approval=approval, original_receipt=receipt,
        operation_fingerprint=fingerprint(dict(approval_id=approval['body']['approval_id'],
            scope_fingerprint=approval['body']['scope_fingerprint'], command=scope['commands'][0])))
    execution_id, _ = execution_identity(approval['record'], approval['body'], approval['event']['generation'])
    if (expected != approval['event']['case_version'] or execution_id != work_id
            or receipt['fact']['acceptance_id'] != row['original_approval_acceptance_id']
            or profile != policy.PROFILE or row['profile_hash'] != policy.profile_hash(profile)
            or row['profile_hash'] != approval['preview']['row']['profile_hash']
            or candidate['type'] != 'CREATE_RETURN'
            or restricted_bytes(candidate) != restricted_bytes(scope['commands'][0])
            or row['prepared_authority_revision'] < 1
            or row['created_at'] < approval['record']['recorded_at']
            or row['created_at'] >= approval['preview']['row']['expires_at']
            or body != operation(head, proof, stable, row['created_at'])
            or record['object_id'] != row['operation_id'] or record['object_version'] != 1
            or record['case_version'] != expected or record['recorded_at'] != row['created_at']
            or record['recorded_sequence'] <= approval['record']['recorded_sequence']
            or record['content_sha256'] != finite.digest(body)):
        reject(uow)
    encoding = one(uow, founder.encodings, record_id=record['record_id'])
    if encoding != dict(record_id=record['record_id'], profile=finite.PROFILE,
            source_content_sha256=record['content_sha256'], projected_content_sha256=record['content_sha256'],
            receipt_id=None):
        reject(uow)
    # No second first attempt, orphan OP, sidecar, effect provenance or later
    # revision is accepted by this deliberately bounded first-preparation slice.
    if ([r['record_id'] for r in sources.proof.revisions.values() if r['kind'] == 'OPERATION'] != [record['record_id']]
            or list(uow.execute(select(preparations.c.preparation_id).where(
                preparations.c.case_id == head['case_id'])).scalars()) != [row['preparation_id']]
            or uow.execute(select(lifecycle.effects.c.operation_id).where(
                lifecycle.effects.c.case_id == head['case_id'])).first()):
        reject(uow)
    origin = sources.proof.origin(record)
    if [event['event_id'] for event in sources.proof.events
            if event['event_type'] == 'OPERATION_REVISION_RECORDED'] != [origin['event_id']]:
        reject(uow)
    ref = {name:record[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}
    value = audit_payload(row, body, record['content_sha256'])
    if (row['binding_hash'] != value['binding_hash']
            or origin['event_id'] != row['origin_audit_event_id']
            or origin['event_type'] != 'OPERATION_REVISION_RECORDED'
            or origin['actor'] != {'kind':'SERVICE', 'component_id':policy.APPROVAL_COMPONENT}
            or origin['case_version'] != expected or origin['occurred_at'] != timestamp(row['created_at'])
            or origin['object_ids'] != [row['operation_id']] or origin['history_refs'] != [ref]
            or origin['payload_hash'] != digest(value, 'audit-payload/v1')):
        reject(uow)
    if row['state'] == 'PENDING':
        state = current(uow, head, initialize=False)
        if (execution['state'] != 'PENDING' or execution['epoch'] != 0
                or state is None or not state['available']
                or state['approval_record_id'] != approval['record']['record_id']
                or state['generation'] != approval['event']['generation']
                or head['case_version'] != expected or head['status'] != 'APPROVED'):
            reject(uow)
    elif row['state'] != execution['state']:
        reject(uow)
    return dict(**proof, row=dict(row), record=dict(record), body=body, origin=origin)


def current_staged(uow, head, initial, retained):
    """Fresh source proof after our single OP is staged, on the post-write head."""
    state = current(uow, head, initialize=False)
    if (state is None or dict(state) != initial['state']
            or retained['approval'] != initial['approval']
            or retained['original_receipt'] != initial['original_receipt']
            or retained['operation_fingerprint'] != initial['operation_fingerprint']
            or accepted_review(uow, head, state, policy.APPROVAL_COMPONENT, current=True)
               != initial['approval']['preview']['review']):
        reject(uow)


def expected_closure(before, rows, head):
    """An explicit row/column delta, never an excluded history/audit/head table."""
    result = {name:[dict(row) for row in values] for name,values in before.items()}
    for table, row in rows:
        keys = [column.name for column in table.primary_key.columns]
        if any(all(saved[key] == row[key] for key in keys) for saved in result[table.name]):
            raise ValueError('Existing preparation identity cannot be overwritten')
        result[table.name] = sorted(result[table.name] + [dict(row)], key=lambda saved:tuple(saved[k] for k in keys))
    original, = result[old.case_heads.name]
    if any(head[name] != original[name] for name in original if name not in
           {'history_sequence', 'audit_sequence', 'audit_head'}):
        raise ValueError('Preparation changed the case')
    if (head['history_sequence'] != original['history_sequence'] + 1
            or head['audit_sequence'] != original['audit_sequence'] + 1
            or head['audit_head'] == original['audit_head']):
        raise ValueError('Preparation sequence delta is not exact')
    result[old.case_heads.name] = [dict(head)]
    return result
