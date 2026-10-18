"""Full original-chain label binding, current creation and historical observation.

No caller-selected command, provider return identity, permission or result is
trusted. Full chain composition is owned by execution_chain_sources.
"""
from copy import deepcopy
from sqlalchemy import select, or_
from . import customer_tables as old, founder_tables as founder, lifecycle_tables as life, founder_codec as finite
from .audit import timestamp
from .canonical import digest
from .approval_admission_sources import session_bounds, check_session_time, check_time
from .execution_preparation_sources import source_closure
from .founder_integrity import CaseProof, read_revision
from .lifecycle_effects import fingerprint
from .lifecycle_schema import LABEL, LABEL_VERSIONS, ARTIFACT, version
from .lifecycle_sources import Sources, authority
from .lifecycle_state import current, reject
from .manual_target import one
from .pass_review_sources import accepted_review
from . import preview_profile as policy
from .return_execution_sources import database_now
from .label_execution_tables import controls, permissions, ledger, artifact_work, CONTROL_IDS, CONTROL_HASHES, CONTROL_NUMBERS

COMPONENT = 'operations-label-v1'
CONFIG = dict(config_id='core-label-sql-v1', provider_id='provider-mock-label',
              command_type='GENERATE_LABEL', environment='SIMULATED', version='sql-mock-v1')


def configuration():
    return dict(CONFIG)


def config_hash():
    return digest(CONFIG, 'core-label-config/v1')


def stable(kind, work_id):
    return kind + '_' + digest(dict(execution_work_id=work_id, command_type='GENERATE_LABEL'), 'label-' + kind + '/v1')


def identities(work_id):
    return {name:stable(kind, work_id) for name,kind in (
        ('control_id','lcontrol'), ('operation_id','loperation'), ('first_record_id','lfirst'),
        ('dispatch_record_id','ldispatch'), ('dispatch_claim_id','lclaim'), ('effect_key','leffect'))}


def key_hash(actor, original_key):
    return digest(dict(principal_id=actor.principal_id, original_key=original_key), 'label-original-key/v1')


def command_hash(command):
    return digest(command, 'label-command/v1')


def bridge_hash(receipt):
    value = {str(name):item for name,item in receipt.items()}
    value['accepted_at'] = timestamp(receipt['accepted_at'])
    return digest(value, 'label-bridge-receipt/v1')


def control_payload(row):
    names = (*CONTROL_IDS, *(name for name in CONTROL_HASHES if name != 'binding_hash'), *CONTROL_NUMBERS, 'effect_key')
    return dict(profile='label-reservation/v1', reservation={**{name:row[name] for name in names},
        'dispatch_at':timestamp(row['dispatch_at']), 'dispatch_deadline':timestamp(row['dispatch_deadline'])})


def dispatch_payload(row, revision):
    return dict(profile='label-operation/v1', revision=revision, binding_hash=row['binding_hash'],
                control_id=row['control_id'], operation_hash=row['first_body_hash' if revision == 1 else 'dispatch_body_hash'])


def ledger_payload(row):
    values = {str(name):row[name] for name in ledger.columns.keys() if name != 'fact_hash'}
    values['accepted_at'] = timestamp(values['accepted_at'])
    return values


def accepted_payload(row, fact, record_hash=None):
    value = dict(profile='label-confirmation/v1' if record_hash is not None else 'label-retained-fact/v1',
        control_id=row['control_id'], operation_id=row['operation_id'], binding_hash=row['binding_hash'],
        ledger_hash=fact['fact_hash'], provider_operation_id=fact['provider_operation_id'],
        confirmed_effect_status=fact['status'], content_available=record_hash is not None)
    if record_hash is not None:
        value['operation_hash'] = record_hash
    return value


def provider_permission(uow, head, *, create):
    if configuration() != CONFIG or CONFIG['provider_id'] != policy.PROFILE['label_provider']:
        reject(uow)
    row = uow.execute(select(permissions).where(permissions.c.store_id == head['store_id'],
        permissions.c.component_id == COMPONENT, permissions.c.provider_id == CONFIG['provider_id'],
        permissions.c.config_id == CONFIG['config_id'], permissions.c.command_type == 'GENERATE_LABEL').with_for_update()).mappings().one_or_none()
    if row is None or row['config_hash'] != config_hash() or not row['create_enabled' if create else 'query_enabled']:
        reject(uow, 'FORBIDDEN')
    return dict(row)


def authorize(uow, callback, case_id, *, create):
    if version(uow.connection) not in LABEL_VERSIONS:
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


def creation_authority(uow, callback, authorization):
    from .return_execution_sources import authorize as return_authorize
    actor, head, grant, permission, bounds = authorization
    effect = dict(authority(uow, head, COMPONENT, 'EFFECT'))
    query = provider_permission(uow, head, create=False)
    ra, rh, rg, rp, rb = return_authorize(uow, callback, head['case_id'], create=False)
    if ra != actor or rh != head or rb != bounds or query != permission:
        reject(uow)
    return effect, rg, rp


def closure(uow, case_id):
    from .return_execution_tables import controls as returns, ledger as return_ledger
    saved = source_closure(uow, case_id)
    for table in (returns, controls, artifact_work):
        saved[table.name] = [dict(row) for row in uow.execute(select(table).where(table.c.case_id == case_id)
            .order_by(*table.primary_key.columns)).mappings()]
    keys = select(returns.c.effect_key).where(returns.c.case_id == case_id)
    saved[return_ledger.name] = [dict(row) for row in uow.execute(select(return_ledger).where(
        return_ledger.c.effect_key.in_(keys)).order_by(return_ledger.c.effect_key)).mappings()]
    saved[ledger.name] = [dict(row) for row in uow.execute(select(ledger).where(ledger.c.case_id == case_id)
        .order_by(ledger.c.effect_key)).mappings()]
    return saved


def full_chain(uow, actor, head, work_id, original_key):
    from .return_execution_tables import controls as returns
    from .execution_chain_sources import return_continuation, historical_bridge
    if version(uow.connection) == ARTIFACT:
        from .execution_artifact_chain_sources import return_continuation
    returned = one(uow, returns, execution_work_id=work_id)
    root = return_continuation(uow, actor, head, returned, original_key)
    bridge = historical_bridge(uow, actor, head, returned, root)
    if bridge is None:
        reject(uow)
    return returned, root, bridge


def eligible(uow, head, root, returned):
    if root is None or not returned['source_available'] or not returned['result_retained']:
        return False
    state = current(uow, head, initialize=False)
    approval = root['approval']; preview = approval['preview']; scope = approval['body']['scope']
    expected = dict(input_version=returned['input_version'], generation=returned['generation'],
        proposal_version=scope['proposal_version'], proposal_record_id=preview['row']['proposal_record_id'],
        review_record_id=preview['row']['review_record_id'], preview_id=approval['body']['preview_id'],
        approval_record_id=approval['record']['record_id'])
    if (state is None or not state['available'] or head['status'] != 'ACTION_IN_PROGRESS'
            or head['current_failure_id'] is not None or head['input_version'] != returned['input_version']
            or any(state[name] != value for name,value in expected.items())
            or any(state[name] is not None for name in ('outcome', 'outcome_record_id', 'notification_id',
                'notification_record_id', 'notification_hash', 'notification_work_id', 'return_record_id', 'label_record_id'))):
        return False
    return accepted_review(uow, head, state, policy.APPROVAL_COMPONENT, current=True) == preview['review']


def create_source(uow, actor, head, work_id, original_key):
    returned, root, bridge = full_chain(uow, actor, head, work_id, original_key)
    if not eligible(uow, head, root, returned):
        reject(uow)
    execution = root['approval']['execution']
    if (execution['work_id'] != work_id or execution['state'] != 'PENDING' or execution['epoch'] != 0
            or any(execution[name] is not None for name in ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))):
        reject(uow)
    check_time(database_now(uow), root)
    return returned, root, bridge


def operation(head, root, command, ids, now):
    approval = root['approval']['body']; scope = approval['scope']
    return finite.validate('OperationAttempt', dict(operation_id=ids['operation_id'], case_id=head['case_id'],
        case_version=head['case_version'], command_id=command['command_id'], approval_id=approval['approval_id'],
        proposal_id=scope['proposal_id'], proposal_version=scope['proposal_version'], input_version=scope['input_version'],
        provider_id=command['provider_id'], operation_fingerprint=fingerprint(dict(approval_id=approval['approval_id'],
            scope_fingerprint=approval['scope_fingerprint'], command=command)), status='PENDING', attempt_count=1,
        updated_at=timestamp(now), idempotency_key=ids['effect_key']))


def control_identity(uow, actor, head, row, original_key):
    if (row['case_id'] != head['case_id'] or row['store_id'] != actor.store_id
            or row['owner_id'] != head['owner_principal_id'] or row['principal_id'] != actor.principal_id
            or row['original_key_hash'] != key_hash(actor, original_key)
            or any(row[name] != value for name,value in identities(row['execution_work_id']).items())
            or row['config_id'] != CONFIG['config_id'] or row['provider_id'] != CONFIG['provider_id']
            or row['config_hash'] != config_hash()
            or row['binding_hash'] != digest(control_payload(row), 'label-reservation/v1')):
        reject(uow, 'IDEMPOTENCY_CONFLICT')


def verify_fact(uow, row, fact):
    names = ('effect_key', 'case_id', 'store_id', 'provider_id', 'config_id', 'config_hash', 'operation_id',
        'dispatch_record_id', 'operation_fingerprint', 'command_hash', 'return_ledger_hash', 'provider_return_id', 'parcel_id')
    if (fact is None or any(fact[name] != row[name] for name in names)
            or fact['dispatch_binding_hash'] != row['binding_hash']
            or fact['provider_operation_id'] != stable('mock_label', row['execution_work_id'])
            or fact['fact_hash'] != digest(ledger_payload(fact), 'core-label-fact/v1')
            or not row['dispatch_at'] <= fact['accepted_at'] < row['dispatch_deadline']):
        reject(uow)
    if fact['status'] == 'SUCCEEDED':
        if fact['provider_label_id'] != stable('label', row['execution_work_id']) or fact['error_code'] is not None:
            reject(uow)
    elif fact['status'] != 'FAILED' or fact['provider_label_id'] is not None or fact['error_code'] != 'INTERNAL_ERROR':
        reject(uow)


def artifact_values(row, fact, record, state):
    return dict(work_id=stable('artifact', row['execution_work_id']), control_id=row['control_id'],
        case_id=row['case_id'], operation_id=row['operation_id'], provider_label_id=fact['provider_label_id'],
        parcel_id=row['parcel_id'], confirmation_record_id=record['record_id'],
        confirmation_case_version=record['case_version'], confirmed_ledger_hash=fact['fact_hash'],
        binding_hash=row['binding_hash'], state=state, epoch=0, claim_id=None, lease_expires_at=None,
        claimed_case_version=None, authority_revision=None, created_at=record['recorded_at'])


def _validate_label_chain(uow, actor, head, row, original_key, returned, root, bridge):
    """Private lower proof invoked only inside the exact 0012 aggregate."""
    control_identity(uow, actor, head, row, original_key)
    source = bridge['source']; receipt = bridge['accepted']['receipt']
    expected_binding = dict(execution_work_id=returned['execution_work_id'],
        approval_record_id=returned['approval_record_id'], approval_acceptance_id=returned['approval_acceptance_id'],
        bridge_event_id=bridge['ids']['event_id'], bridge_work_id=bridge['ids']['work_id'],
        bridge_target_hash=bridge['ids']['target_hash'], bridge_receipt_hash=bridge_hash(receipt),
        return_preparation_id=returned['preparation_id'], return_operation_id=returned['operation_id'],
        return_record_id=returned['result_record_id'], return_result_hash=source['record']['content_sha256'],
        return_ledger_hash=source['fact']['fact_hash'], provider_return_id=source['fact']['provider_return_id'],
        parcel_id=returned['parcel_id'], input_version=returned['input_version'], generation=returned['generation'],
        proposal_version=returned['proposal_version'], approval_id=returned['approval_id'], proposal_id=returned['proposal_id'],
        return_command_id=returned['command_id'], profile_hash=returned['profile_hash'])
    if (any(row[name] != value for name,value in expected_binding.items())
            or not receipt['case_version'] <= row['pre_dispatch_case_version'] < row['dispatch_case_version'] <= head['case_version']
            or row['dispatch_case_version'] != row['pre_dispatch_case_version'] + 1
            or row['dispatch_at'] < receipt['accepted_at']):
        reject(uow)
    proof = CaseProof(uow, head)
    ids = [row['first_record_id'], row['dispatch_record_id']]
    if row['confirmation_record_id'] is not None:
        ids.append(row['confirmation_record_id'])
    records = [one(uow, old.history, record_id=record_id) for record_id in ids]
    first, dispatch = records[:2]
    for i, record in enumerate(records, 1):
        if record['case_id'] != head['case_id'] or record['kind'] != 'OPERATION' or record['object_id'] != row['operation_id'] or record['object_version'] != i:
            reject(uow)
        encoding = one(uow, founder.encodings, record_id=record['record_id'])
        if encoding != dict(record_id=record['record_id'], profile=finite.PROFILE,
                source_content_sha256=record['content_sha256'], projected_content_sha256=record['content_sha256'], receipt_id=None):
            reject(uow)
    if (first['case_version'] != row['pre_dispatch_case_version'] or dispatch['case_version'] != row['dispatch_case_version']
            or first['recorded_at'] != row['dispatch_at'] or dispatch['recorded_at'] != row['dispatch_at']
            or first['content_sha256'] != row['first_body_hash'] or dispatch['content_sha256'] != row['dispatch_body_hash']
            or first['recorded_sequence'] <= source['record']['recorded_sequence']
            or dispatch['recorded_sequence'] != first['recorded_sequence'] + 1):
        reject(uow)
    for i, record in enumerate(records[:2], 1):
        event = proof.origin(record)
        if (event['event_id'] != row['first_audit_id' if i == 1 else 'dispatch_audit_id']
                or event['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
                or event['payload_hash'] != digest(dispatch_payload(row, i), 'audit-payload/v1')):
            reject(uow)
    if row['source_available']:
        if root is None or not returned['source_available']:
            reject(uow)
        command = source['label_command']
        if row['command_id'] != command['command_id'] or row['command_hash'] != command_hash(command):
            reject(uow)
        expected = operation({**head, 'case_version':row['pre_dispatch_case_version']}, root, command,
                             identities(row['execution_work_id']), row['dispatch_at'])
        if row['operation_fingerprint'] != expected['operation_fingerprint']:
            reject(uow)
        _, first_body = Sources(uow, head, COMPONENT).read(first['record_id'], {'OPERATION'})
        _, dispatched = Sources(uow, head, COMPONENT).read(dispatch['record_id'], {'OPERATION'})
        if first_body != expected or dispatched != {**expected, 'status':'EXECUTING', 'case_version':row['dispatch_case_version']}:
            reject(uow)
    else:
        if root is not None or row['confirmation_retained'] or any(record['retention_state'] == 'AVAILABLE' for record in records):
            reject(uow)
        if any('content' in read_revision(uow, record, proof) for record in records):
            reject(uow)
    facts = list(uow.execute(select(ledger).where(or_(ledger.c.case_id == head['case_id'],
        ledger.c.effect_key == row['effect_key'], ledger.c.operation_id == row['operation_id']))).mappings())
    if len(facts) > 1:
        reject(uow)
    fact = dict(facts[0]) if facts else None
    if fact is not None:
        verify_fact(uow, row, fact)
    works = list(uow.execute(select(artifact_work).where(artifact_work.c.case_id == head['case_id'])).mappings())
    if row['confirmed_effect_status'] is None:
        if (row['status'] != 'EXECUTING' or works or any(row[name] is not None for name in
                ('confirmation_record_id', 'confirmation_audit_id', 'confirmation_case_version', 'confirmed_ledger_hash',
                 'confirmed_provider_operation_id', 'confirmed_provider_label_id')) or row['confirmation_retained']):
            reject(uow)
        return ids
    if (fact is None or row['confirmed_ledger_hash'] != fact['fact_hash']
            or row['confirmed_effect_status'] != fact['status']
            or row['confirmed_provider_operation_id'] != fact['provider_operation_id']
            or row['confirmed_provider_label_id'] != fact['provider_label_id']
            or row['query_claim_id'] is not None or row['query_lease_until'] is not None
            or row['confirmation_case_version'] is None
            or not row['dispatch_case_version'] <= row['confirmation_case_version'] <= head['case_version']):
        reject(uow)
    if row['confirmation_record_id'] is None:
        if row['source_available'] or row['confirmation_retained'] or row['status'] != 'EXECUTING' or works:
            reject(uow)
        events = [entry for entry in proof.events if entry['event_id'] == row['confirmation_audit_id']]
        if len(events) != 1:
            reject(uow)
        event = events[0]
        ref = {name:dispatch[name] for name in ('record_id','kind','object_id','object_version')}
        if (event['event_type'] != 'LABEL_EFFECT_CONFIRMED_RETAINED'
                or event['case_version'] != row['confirmation_case_version']
                or event['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
                or event['object_ids'] != [row['operation_id']] or event['history_refs'] != [ref]
                or event['payload_hash'] != digest(accepted_payload(row, fact), 'audit-payload/v1')):
            reject(uow)
        return ids
    record = records[2]; event = proof.origin(record)
    if (record['record_id'] != stable('lconfirm', row['execution_work_id'])
            or record['case_version'] != row['confirmation_case_version']
            or record['recorded_sequence'] <= dispatch['recorded_sequence']
            or record['recorded_at'] < fact['accepted_at']
            or event['event_id'] != row['confirmation_audit_id']
            or event['actor'] != {'kind':'SERVICE','component_id':COMPONENT}
            or event['payload_hash'] != digest(accepted_payload(row, fact, record['content_sha256']), 'audit-payload/v1')
            or row['status'] != ('EXECUTING' if fact['status'] == 'SUCCEEDED' else 'FAILED')):
        reject(uow)
    if row['source_available']:
        if not row['confirmation_retained']:
            reject(uow)
        _, body = Sources(uow, head, COMPONENT).read(record['record_id'], {'OPERATION'})
        expected_body = confirmation_body(dispatched, fact, record['recorded_at'], event['correlation_id'])
        if body != expected_body:
            reject(uow)
    if fact['status'] == 'FAILED':
        if works:
            reject(uow)
    else:
        if len(works) != 1 or works[0]['state'] not in {'PENDING','PAUSED'}:
            reject(uow)
        expected_work = artifact_values(row, fact, record, works[0]['state'])
        if dict(works[0]) != expected_work or (not row['source_available'] and works[0]['state'] != 'PAUSED'):
            reject(uow)
        if works[0]['state'] == 'PENDING' and not eligible(uow, head, root, returned):
            reject(uow)
    return ids


def confirmation_body(dispatched, fact, now, correlation):
    body = {**deepcopy(dispatched), 'updated_at':timestamp(now), 'provider_operation_id':fact['provider_operation_id']}
    if fact['status'] == 'FAILED':
        body.update(status='FAILED', error=dict(error=dict(code='INTERNAL_ERROR',
            message='Core label mock confirmed no effect.', correlation_id=correlation, retryable=False, details=[])))
    # A known label without a stored artifact stays EXECUTING, never SUCCEEDED.
    return finite.validate('OperationAttempt', body)
