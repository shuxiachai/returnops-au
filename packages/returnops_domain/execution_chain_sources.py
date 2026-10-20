"""0012 explicit full return/bridge/label composition; never caller-allowed IDs.

The private lower return reader validates its own exact object revisions. Only
the outer reader owns whole-case inventory; no lower reader calls the outer.
"""
from sqlalchemy import select, or_
from .return_execution_sources import (control_identity, verify_fact, preparation_root,
    stable, dispatch_payload, accepted_payload, project_result, COMPONENT)
from .return_execution_tables import controls, ledger
from .execution_preparation_tables import preparations
from . import lifecycle_tables as life, founder_codec as finite
from .founder_integrity import CaseProof, read_revision
from .lifecycle_sources import Sources
from .lifecycle_state import current, reject
from .manual_target import one
from .audit import timestamp
from .canonical import digest
from .pass_review_sources import accepted_review
from . import preview_profile as policy
from .return_execution_sources import database_now
from .approval_admission_sources import check_time

def _return_chain_proof(uow, actor, head, row, original_key, *, creating=False):
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
    operations = [record for record in proof.revisions.values() if record['kind'] == 'OPERATION' and record['object_id'] == row['operation_id']]
    if [record['record_id'] for record in operations] != expected:
        reject(uow)
    if list(uow.execute(select(preparations.c.preparation_id).where(preparations.c.case_id == head['case_id'])).scalars()) != [row['preparation_id']]:
        reject(uow)
    if list(uow.execute(select(controls.c.preparation_id).where(controls.c.case_id == head['case_id'])).scalars()) != [row['preparation_id']]:
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


def historical_bridge(uow, actor, head, row, root):
    """Original immutable bridge metadata, plus retained bodies when available.

    Metadata-only proof after retention does not rebuild commands or operations.
    The original input/generation are used for the unchanged bridge identity.
    """
    from . import customer_tables as old
    from .return_label_sources import identity, retained_acceptance, KIND
    receipts = list(uow.execute(select(life.events).where(life.events.c.case_id == head['case_id'],
        life.events.c.event_kind == KIND)).mappings())
    if row['status'] != 'SUCCEEDED' or row['result_record_id'] is None:
        if receipts:
            reject(uow)
        return None
    fact = one(uow, ledger, effect_key=row['effect_key'])
    record = one(uow, old.history, record_id=row['result_record_id'])
    approval_record = one(uow, old.history, record_id=row['approval_record_id'])
    source = dict(control=dict(row), record=dict(record), fact=dict(fact),
        origin=CaseProof(uow, head).origin(record),
        state={'generation':row['generation']},
        root={'approval':{'record':dict(approval_record)}} if root is None else root)
    historical_head = {**head, 'input_version':row['input_version']}
    ids = identity(actor, historical_head, source)
    accepted = retained_acceptance(uow, historical_head, source, ids)
    if (accepted is None and receipts) or (accepted is not None and
            [entry['event_id'] for entry in receipts] != [ids['event_id']]):
        reject(uow)
    if accepted is None:
        return None
    if root is not None:
        _, body = Sources(uow, head, COMPONENT).read(record['record_id'], {'OPERATION'})
        create, label = root['approval']['body']['scope']['commands']
        scope = root['approval']['body']['scope']
        if (create['type'] != 'CREATE_RETURN' or label['type'] != 'GENERATE_LABEL'
                or create['provider_id'] != policy.PROFILE['return_provider']
                or label['provider_id'] != policy.PROFILE['label_provider']
                or label['parameters']['return_command_id'] != create['command_id']
                or label['parameters']['parcel_id'] != create['parameters']['parcel_id']
                or label['parameters']['parcel_id'] != scope['parcel_id']
                or label['parameters']['label_format'] != 'PDF' or label['parameters']['chargeable'] is not False
                or 'provider_return_id' in label['parameters']
                or body['status'] != 'SUCCEEDED'
                or body['result'] != dict(type='CREATE_RETURN', provider_return_id=fact['provider_return_id'], parcel_id=row['parcel_id'])):
            reject(uow)
        source.update(body=body, label_command=label)
    return dict(source=source, accepted=accepted, ids=ids)


def return_continuation(uow, actor, head, row, original_key, *, creating=False):
    """Only 0012's aggregate may accept its exact internally proven union."""
    from .label_execution_tables import controls as labels, artifact_work, ledger as label_ledger
    from .label_execution_sources import _validate_label_chain, identities
    root = _return_chain_proof(uow, actor, head, row, original_key, creating=creating)
    bridge = historical_bridge(uow, actor, head, row, root)
    found = list(uow.execute(select(labels).where(labels.c.case_id == head['case_id'])).mappings())
    if len(found) > 1:
        reject(uow)
    proof = CaseProof(uow, head)
    expected = [row['first_record_id'], row['dispatch_record_id']]
    if row['result_record_id'] is not None:
        expected.append(row['result_record_id'])
    if found:
        if bridge is None or creating:
            reject(uow)
        expected += _validate_label_chain(uow, actor, head, dict(found[0]), original_key, row, root, bridge)
    elif (uow.execute(select(artifact_work.c.work_id).where(artifact_work.c.case_id == head['case_id'])).first()
          or uow.execute(select(label_ledger.c.effect_key).where(or_(label_ledger.c.case_id == head['case_id'],
              label_ledger.c.operation_id == identities(row['execution_work_id'])['operation_id'],
              label_ledger.c.effect_key == identities(row['execution_work_id'])['effect_key']))).first()):
        reject(uow)
    operations = [record for record in proof.revisions.values() if record['kind'] == 'OPERATION']
    if ([record['record_id'] for record in operations] != expected
            or [event['event_id'] for event in proof.events if event['event_type'] == 'OPERATION_REVISION_RECORDED']
            != [proof.origin(record)['event_id'] for record in operations]):
        reject(uow)
    return root

