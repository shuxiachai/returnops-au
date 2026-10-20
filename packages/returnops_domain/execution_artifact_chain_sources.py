"""0013 explicit exact union: original N1/N2/bridge/N3 plus one certified v4.

The frozen0012 wrapper and its whole-case effect rule remain unmodified.
This version has private object proofs and independently checks the full union.
"""
from sqlalchemy import select,or_
from . import customer_tables as old,lifecycle_tables as life,founder_tables as founder,founder_codec as finite
from .return_execution_sources import (control_identity,verify_fact,stable,
    dispatch_payload,accepted_payload,project_result,COMPONENT,database_now)
from .return_execution_tables import controls,ledger
from .execution_preparation_tables import preparations
from .founder_integrity import CaseProof,read_revision
from .lifecycle_sources import Sources
from .lifecycle_state import current,reject
from .manual_target import one
from .audit import timestamp
from .canonical import digest,decode_document
from .pass_review_sources import accepted_review
from . import preview_profile as policy
from .approval_admission_sources import check_time
from .execution_chain_sources import historical_bridge
from . import idempotency
from .approval_admission_sources import AdmissionUncertain
from .approve_sources import accepted_approval,execution_identity
from .execution_preparation_sources import (identities as preparation_ids, request_fingerprint as preparation_request_fingerprint,
    operation as preparation_operation, audit_payload as preparation_audit_payload)
from .lifecycle_effects import fingerprint
from .lifecycle_schema import ARTIFACT, ARTIFACT_VERSIONS,version
from .wire import validate

def approval_receipt_0013(uow, actor, head, seal, original_key):
    decision, approval, event = seal['decision'], seal['body'], seal['event']
    if actor.principal_id != approval['principal_id'] or actor.principal_id != decision['principal_id']:
        reject(uow, 'FORBIDDEN')
    request = dict(expected_case_version=event['pre_case_version'], decision='APPROVE',
        proposal_id=decision['proposal_id'], proposal_version=decision['proposal_version'],
        reason=decision['reason'], preview_id=approval['preview_id'],
        scope_fingerprint=approval['scope_fingerprint'])
    validate('FounderDecisionRequest', request, internal=True)
    def resource(fact):
        if (fact['resource_kind'] != 'CASE' or fact['resource_id'] != head['case_id']
                or fact['store_id'] != actor.store_id):
            reject(uow, 'FORBIDDEN')
    fact = idempotency.lookup(uow, actor, 'recordFounderDecision', head['case_id'], original_key,
        digest(request, 'founder-approve-request/v1'), check_resource=resource)
    if fact is None:
        raise AdmissionUncertain()
    return _approval_receipt_fact(uow, head, seal, fact)


def _approval_receipt_fact(uow, head, seal, fact):
    decision, approval, event = seal['decision'], seal['body'], seal['event']
    status, receipt = idempotency.original_receipt(uow, fact)
    validate('DecisionReceipt', receipt, internal=True)
    expected = dict(case_id=head['case_id'], case_version=event['case_version'],
        decision_id=decision['decision_id'], approval_id=approval['approval_id'], decision='APPROVE',
        accepted_at=timestamp(event['accepted_at']), processing_status='ACCEPTED')
    if status != 200 or receipt != expected or fact['accepted_at'] != event['accepted_at']:
        reject(uow)
    refs = list(uow.execute(select(old.receipt_refs).where(
        old.receipt_refs.c.acceptance_id == fact['acceptance_id'])
        .order_by(old.receipt_refs.c.kind, old.receipt_refs.c.object_id)).mappings())
    # Reconstruct exactly the immutable input inventory present when this
    # APPROVE receipt was accepted. Neither a later output nor a genuinely
    # later customer acceptance is inserted into the original receipt.
    proof=CaseProof(uow,head)
    cutoff=seal['record']['recorded_sequence']
    originals=[r for r in proof.revisions.values() if r['kind'] in {'STATEMENT','EVIDENCE'}
               and r['recorded_sequence']<cutoff]
    for record in originals:
        _customer_acceptance(uow,head,proof,record)
        if record['case_version']>seal['record']['case_version'] or record['recorded_at']>event['accepted_at']:
            reject(uow)
    expected_refs={('CASE',head['case_id'])}|{(r['kind'],r['object_id']) for r in originals}
    if {(row['kind'], row['object_id']) for row in refs} != expected_refs:
        reject(uow)
    return dict(fact=dict(fact), receipt=one(uow, old.receipts, acceptance_id=fact['acceptance_id']), refs=refs)


def preparation_root_0013(uow, actor, head, row, original_key):
    return _preparation_material(uow, head, row, _ExecutionCaller(actor, original_key))


def _preparation_material(uow, head, row, context):
    """Same retained first record/binding proof, without claiming no continuation.

    This 0013 copy changes only the receipt inventory to its original acceptance
    point. All frozen0011/0012 readers and their stronger old inventory remain.
    """
    if version(uow.connection) not in ARTIFACT_VERSIONS:
        reject(uow)
    work_id = row['approval_execution_work_id']; stable_ids = preparation_ids(work_id)
    if (row['case_id'] != head['case_id'] or any(row[name] != value for name, value in stable_ids.items())
            or row['command_type'] != 'CREATE_RETURN' or row['state'] not in {'PENDING', 'PAUSED', 'SUPERSEDED'}):
        reject(uow)
    sources = Sources(uow, head, COMPONENT)
    record, body = sources.read(row['first_operation_record_id'], {'OPERATION'}, current_actor=False)
    execution = one(uow, life.work, work_id=work_id)
    approval = accepted_approval(uow, head, execution['target_record_id'], policy.APPROVAL_COMPONENT)
    receipt = context.receipt(uow, head, approval, row['original_approval_acceptance_id'])
    command = approval['body']['scope']['commands'][0]
    proof = dict(approval=approval, original_receipt=receipt,
        operation_fingerprint=fingerprint(dict(approval_id=approval['body']['approval_id'],
            scope_fingerprint=approval['body']['scope_fingerprint'], command=command)))
    derived, _ = execution_identity(approval['record'], approval['body'], approval['event']['generation'])
    if (derived != work_id or receipt['fact']['acceptance_id'] != row['original_approval_acceptance_id']
            or row['request_fingerprint'] != preparation_request_fingerprint(command)
            or policy.profile() != policy.PROFILE or row['profile_hash'] != policy.profile_hash(policy.PROFILE)
            or row['profile_hash'] != approval['preview']['row']['profile_hash'] or row['prepared_authority_revision'] < 1
            or row['created_at'] < approval['record']['recorded_at'] or row['created_at'] >= approval['preview']['row']['expires_at']
            or body != preparation_operation(head, proof, stable_ids, row['created_at'])
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
    origin = sources.proof.origin(record); value = preparation_audit_payload(row, body, record['content_sha256'])
    ref = {name: record[name] for name in ('record_id', 'kind', 'object_id', 'object_version')}
    if (row['binding_hash'] != value['binding_hash'] or origin['event_id'] != row['origin_audit_event_id']
            or origin['event_type'] != 'OPERATION_REVISION_RECORDED'
            or origin['actor'] != {'kind': 'SERVICE', 'component_id': policy.APPROVAL_COMPONENT}
            or origin['case_version'] != record['case_version'] or origin['occurred_at'] != timestamp(row['created_at'])
            or origin['object_ids'] != [row['operation_id']] or origin['history_refs'] != [ref]
            or origin['payload_hash'] != digest(value, 'audit-payload/v1')):
        reject(uow)
    return dict(**proof, row=dict(row), record=dict(record), body=body, origin=origin, command=command)


def _return_chain_proof(uow, actor, head, row, original_key, *, creating=False):
    return _return_material(uow, head, row, _ExecutionCaller(actor, original_key), creating=creating)


def _return_material(uow, head, row, context, *, creating=False):
    """Complete exact N1 root + two/three N2 revisions, or retained identity only."""
    context.return_identity(uow, head, row)
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
    effects = list(uow.execute(select(life.effects).where(life.effects.c.case_id == head['case_id'], life.effects.c.operation_id == row['operation_id'])).mappings())
    if row['result_record_id'] is None:
        if effects:
            reject(uow)
    elif len(effects) != 1 or effects[0]['record_id'] != row['result_record_id'] or effects[0]['dispatch_source_record_id'] != row['dispatch_record_id'] or effects[0]['status'] != row['status']:
        reject(uow)
    root = None
    if row['source_available']:
        root = _preparation_material(uow, head, prep, context)
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



from .label_execution_sources import (control_identity as label_identity, verify_fact as label_fact, stable as label_stable,
    bridge_hash,operation,identities,command_hash,dispatch_payload as label_dispatch,
    accepted_payload as label_accepted,artifact_values,confirmation_body,COMPONENT as LABEL_COMPONENT)
from .label_execution_tables import ledger as label_ledger,artifact_work
def _validate_label_chain(uow, actor, head, row, original_key, returned, root, bridge):
    return _label_material(uow, head, row, returned, root, bridge, _ExecutionCaller(actor, original_key))


def _label_material(uow, head, row, returned, root, bridge, context):
    """Private lower proof invoked only inside the exact 0012 aggregate."""
    context.label_identity(uow, head, row)
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
                or event['actor'] != {'kind':'SERVICE','component_id':LABEL_COMPONENT}
                or event['payload_hash'] != digest(label_dispatch(row, i), 'audit-payload/v1')):
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
        _, first_body = Sources(uow, head, LABEL_COMPONENT).read(first['record_id'], {'OPERATION'})
        _, dispatched = Sources(uow, head, LABEL_COMPONENT).read(dispatch['record_id'], {'OPERATION'})
        if first_body != expected or dispatched != {**expected, 'status':'EXECUTING', 'case_version':row['dispatch_case_version']}:
            reject(uow)
    else:
        if root is not None or row['confirmation_retained'] or any(record['retention_state'] == 'AVAILABLE' for record in records):
            reject(uow)
        if any('content' in read_revision(uow, record, proof) for record in records):
            reject(uow)
    facts = list(uow.execute(select(label_ledger).where(or_(label_ledger.c.case_id == head['case_id'],
        label_ledger.c.effect_key == row['effect_key'], label_ledger.c.operation_id == row['operation_id']))).mappings())
    if len(facts) > 1:
        reject(uow)
    fact = dict(facts[0]) if facts else None
    if fact is not None:
        label_fact(uow, row, fact)
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
                or event['actor'] != {'kind':'SERVICE','component_id':LABEL_COMPONENT}
                or event['object_ids'] != [row['operation_id']] or event['history_refs'] != [ref]
                or event['payload_hash'] != digest(label_accepted(row, fact), 'audit-payload/v1')):
            reject(uow)
        return ids
    record = records[2]; event = proof.origin(record)
    if (record['record_id'] != label_stable('lconfirm', row['execution_work_id'])
            or record['case_version'] != row['confirmation_case_version']
            or record['recorded_sequence'] <= dispatch['recorded_sequence']
            or record['recorded_at'] < fact['accepted_at']
            or event['event_id'] != row['confirmation_audit_id']
            or event['actor'] != {'kind':'SERVICE','component_id':LABEL_COMPONENT}
            or event['payload_hash'] != digest(label_accepted(row, fact, record['content_sha256']), 'audit-payload/v1')
            or row['status'] != ('EXECUTING' if fact['status'] == 'SUCCEEDED' else 'FAILED')):
        reject(uow)
    if row['source_available']:
        if not row['confirmation_retained']:
            reject(uow)
        _, body = Sources(uow, head, LABEL_COMPONENT).read(record['record_id'], {'OPERATION'})
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
    return ids


def _customer_acceptance(uow,head,proof,record):
    """Actual same-case customer origin and immutable acceptance, not a name."""
    origin=proof.origin(record)
    if (record['case_id']!=head['case_id']
            or origin['event_type'] not in {'CUSTOMER_CASE_ACCEPTED','CUSTOMER_CLARIFICATION_ACCEPTED'}
            or origin['actor']!={'kind':'HUMAN','role':'CUSTOMER','principal_id':head['owner_principal_id']}):reject(uow)
    accepted=[dict(r) for r in uow.execute(select(old.acceptances).join(old.receipt_refs,
        old.acceptances.c.acceptance_id==old.receipt_refs.c.acceptance_id).where(
        old.receipt_refs.c.kind==record['kind'],old.receipt_refs.c.object_id==record['object_id'],
        old.acceptances.c.principal_id==head['owner_principal_id'],old.acceptances.c.store_id==head['store_id'],
        old.acceptances.c.method=='POST',old.acceptances.c.resource_kind=='CASE',old.acceptances.c.resource_id==head['case_id'],
        old.acceptances.c.operation==('createCase' if origin['event_type']=='CUSTOMER_CASE_ACCEPTED' else 'submitClarification'),
        old.acceptances.c.accepted_at==record['recorded_at'])).mappings()]
    if len(accepted)!=1:reject(uow)
    return accepted[0]


def historical_material(uow,head,root):
    """Prove the original customer set, and independently accepted later inputs."""
    from hashlib import sha256
    from .customer_service import CustomerFlow
    from .generated_evidence import partition_evidence
    from . import investigation_tables as inv
    from .founder_queries import _order
    proposal=root['approval']['preview']['review']['proposal']
    bundle=proposal['body'];record=proposal['record']
    proof=CaseProof(uow,head);customer,_=partition_evidence(uow,proof)
    rows=[r for r in proof.revisions.values() if r['kind']=='STATEMENT']+customer
    originals={'STATEMENT':{},'EVIDENCE':{}}
    for r in rows:
        _customer_acceptance(uow,head,proof,r)
        result=read_revision(uow,r,proof)
        if 'content' not in result:reject(uow)
        body=result['content']
        if r['kind']=='EVIDENCE':
            e=one(uow,old.evidence,evidence_id=r['object_id'])
            raw=uow.execute(select(old.evidence_contents.c.body).where(old.evidence_contents.c.evidence_id==r['object_id'])).scalar_one_or_none()
            if (not e['available'] or e['status']!='BOUND' or e['case_id']!=head['case_id']
                    or e['store_id']!=head['store_id'] or e['uploader_id']!=head['owner_principal_id']
                    or raw is None or len(raw)!=e['size_bytes'] or sha256(bytes(raw)).hexdigest()!=e['sha256']
                    or CustomerFlow._evidence_view(e)!=body):reject(uow)
        if r['recorded_sequence']<record['recorded_sequence']:
            originals[r['kind']][r['object_id']]=body
    expected_statements={b['statement_id']:b for b in bundle['statements']}
    expected_evidence={b['evidence_id']:b for b in bundle['attachments']}
    if originals!={'STATEMENT':expected_statements,'EVIDENCE':expected_evidence}:reject(uow)
    from .label_artifact_sources import verify_original_statement_physical
    original=verify_original_statement_physical(uow,head['case_id'])
    if original['statement_id']!=bundle['packet']['original_statement_id']:reject(uow)
    customer_ids={r['object_id'] for r in customer}
    actual_ids=set(uow.execute(select(old.evidence.c.evidence_id).where(old.evidence.c.case_id==head['case_id'])).scalars())
    if customer_ids!=actual_ids:reject(uow)
    projection_id=proposal['binding']['order_projection_id']
    snapshot=_order(uow,proof,{**head,'input_version':proposal['work']['input_version']},projection_id)
    projection=one(uow,inv.projections,projection_id=projection_id)
    raw=uow.execute(select(inv.receipt_contents.c.body).where(inv.receipt_contents.c.receipt_id==projection['receipt_id'])).scalar_one_or_none()
    if raw is None:reject(uow)
    lookup=dict(decode_document(raw)['result']);lookup['input_version']=proposal['work']['input_version']
    if bundle['order_lookup']!=lookup or lookup.get('snapshot')!=snapshot:reject(uow)


def return_continuation(uow,actor,head,row,original_key,*,creating=False):
    return _continuation_material(uow, head, row, _ExecutionCaller(actor, original_key), creating=creating)


def _continuation_material(uow, head, row, context, *, creating=False):
    from .label_execution_tables import controls as labels,artifact_work,ledger as label_ledger
    from .label_artifact_tables import artifacts,controls as recovery,claims,contents
    from .generated_evidence import verify_certificate,partition_evidence
    from .label_artifact_history import effect_values
    from .label_artifact_sources import validate_control,claim_hash
    root=_return_material(uow,head,row,context,creating=creating)
    bridge=context.bridge(uow,head,row,root)
    # The original RETURN_SOURCE bridge owns one fully proved EFFECT producer.
    # Generated artifacts own none. Derive the entire allowed inventory from
    # that existing proof, never from a caller or an event-name exception.
    expected_effect_work=[] if bridge is None else [bridge['accepted']['work']]
    actual_effect_work=[dict(saved) for saved in uow.execute(select(life.work).where(
        life.work.c.case_id==head['case_id'],life.work.c.purpose=='EFFECT').order_by(life.work.c.work_id)).mappings()]
    if actual_effect_work!=expected_effect_work:reject(uow)
    found=list(uow.execute(select(labels).where(labels.c.case_id==head['case_id'])).mappings())
    if len(found)>1:reject(uow)
    proof=CaseProof(uow,head)
    expected=[row['first_record_id'],row['dispatch_record_id']]
    if row['result_record_id'] is not None:expected.append(row['result_record_id'])
    effect_ids=[] if row['result_record_id'] is None else [row['operation_id']]
    generated_ids=[]
    if found:
        label=dict(found[0])
        if bridge is None or creating:reject(uow)
        expected+=_label_material(uow,head,label,row,root,bridge,context)
        works=list(uow.execute(select(artifact_work).where(artifact_work.c.case_id==head['case_id'])).mappings())
        for work in works:
            control=uow.execute(select(recovery).where(recovery.c.work_id==work['work_id'])).mappings().one_or_none()
            completed=list(uow.execute(select(artifacts).where(artifacts.c.work_id==work['work_id'])).mappings())
            if len(completed)>1:reject(uow)
            if control is None:
                if completed or uow.execute(select(claims.c.claim_id).where(claims.c.work_id==work['work_id'])).first():reject(uow)
            else:
                validate_control(uow,control)
                prior=list(uow.execute(select(claims).where(claims.c.work_id==work['work_id']).order_by(claims.c.epoch)).mappings())
                if any(c['claim_hash']!=claim_hash(c) or c['epoch']>control['epoch'] for c in prior):reject(uow)
                if control['state']=='RUNNING':
                    active=[c for c in prior if c['claim_id']==control['active_claim_id']]
                    if len(active)!=1 or active[0]['epoch']!=control['epoch']:reject(uow)
                elif control['active_claim_id'] is not None:reject(uow)
                if not completed and control['state']=='DONE':reject(uow)
                if control['source_withdrawal_receipt'] is not None:
                    from .label_artifact_retention import verify_control_retention
                    verify_control_retention(uow,dict(control),proof)
            if completed:
                seal=verify_certificate(uow,completed[0]['evidence_id'],proof=proof)
                generated_records=[seal['evidence_record']['record_id'],seal['result_record']['record_id']]
                if (uow.execute(select(life.sources.c.record_id).where(life.sources.c.record_id.in_(generated_records))).first()
                        or uow.execute(select(life.events.c.event_id).where(life.events.c.record_id.in_(generated_records))).first()):reject(uow)
                expected.append(seal['result_record']['record_id']);generated_ids.append(seal['evidence_record']['record_id'])
                effect_ids.append(label['operation_id'])
                identity={n:label[n] for n in ('operation_id','case_id','command_id','approval_id','proposal_id',
                    'proposal_version','input_version','provider_id','operation_fingerprint')}
                identity.update(idempotency_key=label['effect_key'],status='SUCCEEDED',result={'label_evidence_id':seal['row']['evidence_id']})
                actual=one(uow,life.effects,operation_id=label['operation_id'])
                if actual!=effect_values(label,identity,seal['result_record'],seal['row']['sha256']):reject(uow)
    elif (uow.execute(select(artifact_work.c.work_id).where(artifact_work.c.case_id==head['case_id'])).first()
          or uow.execute(select(label_ledger.c.effect_key).where(label_ledger.c.case_id==head['case_id'])).first()):reject(uow)
    operations=[r for r in proof.revisions.values() if r['kind']=='OPERATION']
    if ([r['record_id'] for r in operations]!=expected
            or [e['event_id'] for e in proof.events if e['event_type']=='OPERATION_REVISION_RECORDED']
            !=[proof.origin(r)['event_id'] for r in operations]):reject(uow)
    actual_effect_ids=set(uow.execute(select(life.effects.c.operation_id).where(life.effects.c.case_id==head['case_id'])).scalars())
    if actual_effect_ids!=set(effect_ids):reject(uow)
    _,generated=partition_evidence(uow,proof)
    if [r['record_id'] for r in generated]!=generated_ids:reject(uow)
    if root is not None:historical_material(uow,head,root)
    return root



class _ExecutionCaller:
    """Existing execution entry points keep their actual actor and original key."""
    def __init__(self, actor, key):
        self.actor, self.key = actor, key

    def receipt(self, uow, head, approval, acceptance_id):
        result = approval_receipt_0013(uow, self.actor, head, approval, self.key)
        if result['fact']['acceptance_id'] != acceptance_id:
            reject(uow)
        return result

    def return_identity(self, uow, head, row):
        control_identity(uow, self.actor, head, row, self.key)

    def label_identity(self, uow, head, row):
        label_identity(uow, self.actor, head, row, self.key)

    def bridge(self, uow, head, row, root):
        return historical_bridge(uow, self.actor, head, row, root)
