"""Explicit 0011 continuation proof; the strict 0010 verifier is unchanged."""
from datetime import datetime
from sqlalchemy import select, func
from . import customer_tables as old, founder_tables as founder, lifecycle_tables as life
from . import founder_codec as finite, preview_profile as policy
from .audit import timestamp
from .canonical import digest
from .approval_admission_sources import (authorize as approval_authorize, approval_receipt,
    restricted_bytes, session_bounds, check_session_time, check_time)
from .approve_sources import accepted_approval, execution_identity
from .execution_preparation_sources import (identities, request_fingerprint, operation, audit_payload,
    retained_proof as strict_preparation)
from .execution_preparation_tables import preparations
from .founder_integrity import CaseProof, read_revision
from .lifecycle_effects import fingerprint
from .lifecycle_schema import EXECUTION, version
from .lifecycle_sources import Sources, authority
from .lifecycle_state import current, reject
from .manual_target import one
from .pass_review_sources import accepted_review
from .return_execution_tables import controls, permissions, ledger, CONTROL_IDS, CONTROL_HASHES, CONTROL_NUMBERS

COMPONENT = 'operations-return-v1'
CONFIG = dict(config_id='core-return-sql-v1', provider_id='provider-mock-return',
              command_type='CREATE_RETURN', environment='SIMULATED', version='sql-mock-v1')


def configuration():
    return dict(CONFIG)


def config_hash():
    return digest(CONFIG, 'core-return-config/v1')


def database_now(uow):
    return uow.execute(select(func.clock_timestamp())).scalar_one()


def key_hash(actor, key):
    return digest(dict(principal_id=actor.principal_id, original_key=key), 'return-original-key/v1')


def stable(kind, preparation_id):
    return kind + '_' + digest(dict(preparation_id=preparation_id), 'return-' + kind + '/v1')


def control_payload(row):
    names = (*CONTROL_IDS, *(name for name in CONTROL_HASHES if name != 'binding_hash'),
             *CONTROL_NUMBERS, 'effect_key')
    value = {name: row[name] for name in names}
    value.update(dispatch_at=timestamp(row['dispatch_at']), dispatch_deadline=timestamp(row['dispatch_deadline']))
    return dict(profile='return-execution/v1', reservation=value)


def dispatch_payload(row):
    return {**control_payload(row), 'binding_hash': row['binding_hash']}


def ledger_payload(row):
    value = {str(name): row[name] for name in ledger.columns.keys() if name != 'fact_hash'}
    value['accepted_at'] = timestamp(value['accepted_at'])
    return value


def accepted_payload(row, fact, record_hash=None):
    if record_hash is None:
        return dict(profile='return-retained-result/v1', operation_id=row['operation_id'],
            preparation_id=row['preparation_id'], dispatch_binding_hash=row['binding_hash'],
            ledger_hash=fact['fact_hash'], provider_operation_id=fact['provider_operation_id'],
            confirmed_effect_status=fact['status'], content_available=False)
    return dict(profile='return-result/v1', dispatch_binding_hash=row['binding_hash'],
                ledger_hash=fact['fact_hash'], operation_hash=record_hash)


def provider_permission(uow, head, *, create):
    config = configuration()
    if config != CONFIG or config['provider_id'] != policy.PROFILE['return_provider']:
        reject(uow)
    row = uow.execute(select(permissions).where(permissions.c.store_id == head['store_id'],
        permissions.c.component_id == COMPONENT, permissions.c.provider_id == CONFIG['provider_id'],
        permissions.c.config_id == CONFIG['config_id'], permissions.c.command_type == 'CREATE_RETURN')
        .with_for_update()).mappings().one_or_none()
    if row is None or row['config_hash'] != config_hash() or not row['create_enabled' if create else 'query_enabled']:
        reject(uow, 'FORBIDDEN')
    return dict(row)


def authorize(uow, callback, case_id, *, create):
    if version(uow.connection) != EXECUTION:
        reject(uow)
    actor = callback(uow.connection, 'getSession')
    if actor.role != 'FOUNDER':
        reject(uow, 'FORBIDDEN')
    if callback(uow.connection, 'getFounderCase', case_id) != actor:
        reject(uow, 'UNAUTHENTICATED')
    head = one(uow, old.case_heads, case_id=case_id)
    if not head['available'] or head['store_id'] != actor.store_id:
        reject(uow, 'NOT_FOUND')
    grant = dict(authority(uow, head, COMPONENT, 'EXECUTION' if create else 'EFFECT'))
    permission = provider_permission(uow, head, create=create)
    bounds = session_bounds(uow, actor)
    check_session_time(database_now(uow), bounds)
    return actor, head, grant, permission, bounds


def preparation_root(uow, actor, head, row, original_key):
    """Same retained first record/binding proof, without claiming no continuation.

    Used only by the explicit 0011 reader below. Old strict_preparation still
    requires its one-operation/no-effect/head-state invariants for old readers.
    """
    if version(uow.connection) != EXECUTION:
        reject(uow)
    work_id = row['approval_execution_work_id']; stable_ids = identities(work_id)
    if (row['case_id'] != head['case_id'] or any(row[name] != value for name, value in stable_ids.items())
            or row['command_type'] != 'CREATE_RETURN' or row['state'] not in {'PENDING', 'PAUSED', 'SUPERSEDED'}):
        reject(uow)
    sources = Sources(uow, head, COMPONENT)
    record, body = sources.read(row['first_operation_record_id'], {'OPERATION'}, current_actor=False)
    execution = one(uow, life.work, work_id=work_id)
    approval = accepted_approval(uow, head, execution['target_record_id'], policy.APPROVAL_COMPONENT)
    receipt = approval_receipt(uow, actor, head, approval, original_key)
    command = approval['body']['scope']['commands'][0]
    proof = dict(approval=approval, original_receipt=receipt,
        operation_fingerprint=fingerprint(dict(approval_id=approval['body']['approval_id'],
            scope_fingerprint=approval['body']['scope_fingerprint'], command=command)))
    derived, _ = execution_identity(approval['record'], approval['body'], approval['event']['generation'])
    if (derived != work_id or receipt['fact']['acceptance_id'] != row['original_approval_acceptance_id']
            or row['request_fingerprint'] != request_fingerprint(command)
            or policy.profile() != policy.PROFILE or row['profile_hash'] != policy.profile_hash(policy.PROFILE)
            or row['profile_hash'] != approval['preview']['row']['profile_hash'] or row['prepared_authority_revision'] < 1
            or row['created_at'] < approval['record']['recorded_at'] or row['created_at'] >= approval['preview']['row']['expires_at']
            or body != operation(head, proof, stable_ids, row['created_at'])
            or record['object_id'] != row['operation_id'] or record['object_version'] != 1
            or record['case_version'] != approval['event']['case_version'] or record['recorded_at'] != row['created_at']
            or record['recorded_sequence'] <= approval['record']['recorded_sequence']
            or record['content_sha256'] != finite.digest(body)
            or execution['state'] != row['state'] or execution['state'] == 'PENDING' and execution['epoch'] != 0):
        reject(uow)
    encoding = one(uow, founder.encodings, record_id=record['record_id'])
    if encoding != dict(record_id=record['record_id'], profile=finite.PROFILE,
            source_content_sha256=record['content_sha256'], projected_content_sha256=record['content_sha256'], receipt_id=None):
        reject(uow)
    origin = sources.proof.origin(record); value = audit_payload(row, body, record['content_sha256'])
    ref = {name: record[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}
    if (row['binding_hash'] != value['binding_hash'] or origin['event_id'] != row['origin_audit_event_id']
            or origin['event_type'] != 'OPERATION_REVISION_RECORDED'
            or origin['actor'] != {'kind': 'SERVICE', 'component_id': policy.APPROVAL_COMPONENT}
            or origin['case_version'] != record['case_version'] or origin['occurred_at'] != timestamp(row['created_at'])
            or origin['object_ids'] != [row['operation_id']] or origin['history_refs'] != [ref]
            or origin['payload_hash'] != digest(value, 'audit-payload/v1')):
        reject(uow)
    return dict(**proof, row=dict(row), record=dict(record), body=body, origin=origin, command=command)


def control_identity(uow, actor, head, row, original_key):
    if (row['case_id'] != head['case_id'] or row['store_id'] != actor.store_id
            or row['owner_id'] != head['owner_principal_id'] or row['principal_id'] != actor.principal_id
            or row['original_key_hash'] != key_hash(actor, original_key)
            or row['config_id'] != CONFIG['config_id'] or row['provider_id'] != CONFIG['provider_id']
            or row['config_hash'] != config_hash() or row['binding_hash'] != digest(control_payload(row), 'return-reservation/v1')):
        reject(uow, 'IDEMPOTENCY_CONFLICT')


def continued_proof(uow, actor, head, row, original_key, *, creating=False):
    """Complete exact N1 root + two/three N2 revisions, or retained identity only."""
    control_identity(uow, actor, head, row, original_key)
    existing_fact = uow.execute(select(ledger).where(ledger.c.effect_key == row['effect_key'])).mappings().one_or_none()
    if existing_fact is not None:
        verify_fact(uow, row, existing_fact)
    prep = one(uow, preparations, preparation_id=row['preparation_id'])
    if (prep['case_id'] != row['case_id'] or prep['binding_hash'] != row['preparation_hash'] or prep['operation_id'] != row['operation_id']
            or prep['first_operation_record_id'] != row['first_record_id'] or prep['effect_key'] != row['effect_key']
            or prep['approval_execution_work_id'] != row['execution_work_id']
            or prep['original_approval_acceptance_id'] != row['approval_acceptance_id']
            or prep['profile_hash'] != row['profile_hash'] or prep['request_fingerprint'] != row['request_fingerprint']
            or row['dispatch_record_id'] != stable('dispatch', prep['preparation_id'])
            or row['dispatch_claim_id'] != stable('rclaim', prep['preparation_id'])
            or row['result_record_id'] not in {None, stable('rresult', prep['preparation_id'])}):
        reject(uow)
    proof = CaseProof(uow, head)
    expected = [row['first_record_id'], row['dispatch_record_id']]
    if row['result_record_id'] is not None:
        expected.append(row['result_record_id'])
    operations = [record for record in proof.revisions.values() if record['kind'] == 'OPERATION']
    if [record['record_id'] for record in operations] != expected:
        reject(uow)
    if list(uow.execute(select(preparations.c.preparation_id).where(preparations.c.case_id == head['case_id'])).scalars()) != [row['preparation_id']]:
        reject(uow)
    if list(uow.execute(select(controls.c.preparation_id).where(controls.c.case_id == head['case_id'])).scalars()) != [row['preparation_id']]:
        reject(uow)
    if [event['event_id'] for event in proof.events if event['event_type'] == 'OPERATION_REVISION_RECORDED'] != [proof.origin(record)['event_id'] for record in operations]:
        reject(uow)
    first, dispatch = operations[:2]
    if (first['object_id'] != row['operation_id'] or first['object_version'] != 1
            or first['case_version'] != row['approval_case_version']
            or proof.origin(first)['event_id'] != prep['origin_audit_event_id']):
        reject(uow)
    if (first['content_sha256'] != row['first_body_hash'] or dispatch['content_sha256'] != row['dispatch_body_hash']
            or dispatch['object_id'] != row['operation_id'] or dispatch['object_version'] != 2
            or dispatch['recorded_sequence'] != first['recorded_sequence'] + 1
            or dispatch['case_version'] != row['dispatch_case_version'] or dispatch['recorded_at'] != row['dispatch_at']
            or row['dispatch_case_version'] != row['approval_case_version'] + 1):
        reject(uow)
    origin = proof.origin(dispatch)
    if (origin['event_id'] != row['dispatch_audit_id'] or origin['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
            or origin['payload_hash'] != digest(dispatch_payload(row), 'audit-payload/v1')):
        reject(uow)
    effects = list(uow.execute(select(life.effects).where(life.effects.c.case_id == head['case_id'])).mappings())
    if row['result_record_id'] is None:
        if effects:
            reject(uow)
    elif len(effects) != 1 or effects[0]['record_id'] != row['result_record_id'] or effects[0]['dispatch_source_record_id'] != row['dispatch_record_id'] or effects[0]['status'] != row['status']:
        reject(uow)
    root = None
    if row['source_available']:
        root = preparation_root(uow, actor, head, prep, original_key)
        if (root['approval']['record']['record_id'] != row['approval_record_id']
                or root['original_receipt']['fact']['acceptance_id'] != row['approval_acceptance_id']
                or root['operation_fingerprint'] != row['operation_fingerprint']):
            reject(uow)
        sources = Sources(uow, head, COMPONENT)
        _, dispatched = sources.read(row['dispatch_record_id'], {'OPERATION'})
        expected_body = {**root['body'], 'status': 'EXECUTING', 'case_version': row['dispatch_case_version'], 'updated_at': timestamp(row['dispatch_at'])}
        if dispatched != expected_body:
            reject(uow)
    else:
        if creating or row['result_retained'] or any(record['retention_state'] == 'AVAILABLE' for record in operations):
            reject(uow)
        for record in operations:
            if 'content' in read_revision(uow, record, proof):
                reject(uow)
    confirmed = row['confirmed_effect_status'] is not None
    if not confirmed:
        if (row['status'] != 'EXECUTING' or row['result_record_id'] is not None or row['result_audit_id'] is not None
                or row['confirmed_ledger_hash'] is not None or row['confirmed_provider_operation_id'] is not None
                or row['confirmation_audit_id'] is not None or row['result_retained']):
            reject(uow)
    else:
        fact = one(uow, ledger, effect_key=row['effect_key'])
        verify_fact(uow, row, fact)
        if (row['confirmed_ledger_hash'] != fact['fact_hash'] or row['confirmed_effect_status'] != fact['status']
                or row['confirmed_provider_operation_id'] != fact['provider_operation_id']):
            reject(uow)
        if row['result_record_id'] is None:
            if row['status'] != 'EXECUTING' or row['source_available'] or row['result_retained'] or row['result_audit_id'] is not None:
                reject(uow)
            matching = [event for event in proof.events if event['event_id'] == row['confirmation_audit_id']]
            if len(matching) != 1:
                reject(uow)
            event = matching[0]
            ref = {name: dispatch[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}
            if (event['event_type'] != 'RETURN_EFFECT_CONFIRMED_RETAINED'
                    or event['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
                    or event['object_ids'] != [row['operation_id']] or event['history_refs'] != [ref]
                    or event['payload_hash'] != digest(accepted_payload(row, fact), 'audit-payload/v1')):
                reject(uow)
        else:
            record = operations[2]; event = proof.origin(record)
            if (row['status'] != fact['status'] or row['confirmation_audit_id'] is not None
                    or record['object_version'] != 3 or record['object_id'] != row['operation_id']
                    or record['recorded_sequence'] <= dispatch['recorded_sequence']
                    or event['event_id'] != row['result_audit_id']
                    or event['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
                    or event['payload_hash'] != digest(accepted_payload(row, fact, record['content_sha256']), 'audit-payload/v1')):
                reject(uow)
            if row['source_available']:
                if not row['result_retained']:
                    reject(uow)
                _, result_body = Sources(uow, head, COMPONENT).read(record['record_id'], {'OPERATION'})
                expected_result = {**dispatched, 'status': fact['status'], 'updated_at': timestamp(record['recorded_at']),
                                   'provider_operation_id': fact['provider_operation_id']}
                projected = project_result(fact)
                if projected is not None:
                    expected_result['result'] = projected
                else:
                    expected_result['error'] = dict(error=dict(code='INTERNAL_ERROR', message='Core mock confirmed no effect.',
                        correlation_id=event['correlation_id'], retryable=False, details=[]))
                if result_body != expected_result:
                    reject(uow)
            from .return_execution_history import effect_values
            identity = {name: row[name] for name in ('operation_id', 'case_id', 'command_id', 'approval_id',
                'proposal_id', 'proposal_version', 'input_version', 'provider_id', 'operation_fingerprint', 'status')}
            identity['idempotency_key'] = row['effect_key']
            if dict(effects[0]) != effect_values(row, identity, record):
                reject(uow)
    if creating:
        state = current(uow, head, initialize=False)
        if (root is None or prep['state'] != 'PENDING' or head['status'] != 'ACTION_IN_PROGRESS'
                or head['case_version'] != row['dispatch_case_version'] or head['input_version'] != row['input_version']
                or state is None or not state['available'] or state['generation'] != row['generation']
                or state['approval_record_id'] != row['approval_record_id']
                or any(state[name] is not None for name in ('outcome', 'outcome_record_id', 'notification_id', 'return_record_id', 'label_record_id'))
                or accepted_review(uow, head, state, policy.APPROVAL_COMPONENT, current=True) != root['approval']['preview']['review']):
            reject(uow)
        check_time(database_now(uow), root)
    return root


def verify_fact(uow, row, fact):
    if (fact is None or any(fact[name] != row[name] for name in
            ('effect_key', 'store_id', 'provider_id', 'config_id', 'config_hash', 'operation_id', 'dispatch_record_id', 'operation_fingerprint', 'parcel_id'))
            or fact['dispatch_binding_hash'] != row['binding_hash']
            or fact['fact_hash'] != digest(ledger_payload(fact), 'core-return-fact/v1')
            or fact['provider_operation_id'] != stable('mock_return', row['preparation_id'])
            or not row['dispatch_at'] <= fact['accepted_at'] < row['dispatch_deadline']):
        reject(uow)
    if fact['status'] == 'SUCCEEDED':
        if fact['provider_return_id'] != stable('return', row['preparation_id']) or fact['error_code'] is not None:
            reject(uow)
    elif fact['status'] != 'FAILED' or fact['provider_return_id'] is not None or fact['error_code'] != 'INTERNAL_ERROR':
        reject(uow)


def project_result(fact):
    """Only retained-body-permitted Domain acceptance projects a full result."""
    if fact['status'] == 'FAILED':
        return None
    return finite.validate('OperationResult', dict(type='CREATE_RETURN',
        provider_return_id=fact['provider_return_id'], parcel_id=fact['parcel_id']))


def preparation_replay(uow, actor, head, expected, work_id, original_key, candidate, preparation):
    """Version0011-only historical N1 replay; never a create/retry permit."""
    saved = uow.execute(select(controls).where(controls.c.execution_work_id == work_id)).mappings().one_or_none()
    if saved is None:
        return strict_preparation(uow, actor, head, expected, work_id, original_key, candidate, preparation)
    if expected != saved['approval_case_version'] or request_fingerprint(candidate) != saved['request_fingerprint']:
        reject(uow, 'IDEMPOTENCY_CONFLICT')
    root = continued_proof(uow, actor, head, saved, original_key)
    if root is None or root['row'] != dict(preparation):
        reject(uow)
    return {**root, 'n2_control': dict(saved)}
