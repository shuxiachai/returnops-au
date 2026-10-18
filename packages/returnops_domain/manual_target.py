"""Retained authoritative sources for the private no-proposal manual slice."""
from sqlalchemy import select
from . import customer_tables as old, investigation_tables as investigation, lifecycle_tables as t
from .canonical import decode_document, digest
from .audit import timestamp
from .founder_integrity import lookup_receipt
from .lifecycle_guards import LifecycleGuards
from .lifecycle_sources import Sources
from .lifecycle_state import reject


def one(uow, table, **keys):
    row = uow.execute(select(table).where(*(getattr(table.c, k) == v for k, v in keys.items()))).mappings().one_or_none()
    if row is None:
        reject(uow)
    return dict(row)


def accepted_input(uow, head, intake_id, proof):
    """Reuse actual intake validation and bind its refs to the acceptance audit.

    Both createCase and submitClarification retain a CustomerCaseView receipt;
    neither can be replaced by an available but unrelated or malformed body.
    """
    from .intake_processor import IntakeProcessor
    work = one(uow, old.intake_work, work_id=intake_id)
    valid, _ = IntakeProcessor(None)._context(uow, work)
    if valid != 'CURRENT':
        reject(uow)
    fact = one(uow, old.acceptances, acceptance_id=work['acceptance_id'])
    receipt = one(uow, old.receipts, acceptance_id=work['acceptance_id'])
    expected_event = {'createCase':'CUSTOMER_CASE_ACCEPTED', 'submitClarification':'CUSTOMER_CLARIFICATION_ACCEPTED'}.get(fact['operation'])
    payload_hash = digest({'acceptance_id':fact['acceptance_id'], 'request_fingerprint':fact['fingerprint'],
                           'work_id':work['work_id']}, 'audit-payload/v1')
    origins = [event for event in proof.events if event['event_type'] == expected_event
               and event['payload_hash'] == payload_hash]
    if len(origins) != 1:
        reject(uow)
    origin = origins[0]
    refs = decode_document(work['source_refs'])
    if (origin['actor'] != {'kind':'HUMAN', 'role':'CUSTOMER', 'principal_id':work['accepted_principal_id']}
            or origin['history_refs'] != refs or origin['case_version'] != work['accepted_case_version']
            or origin['occurred_at'] != timestamp(fact['accepted_at'])
            or fact['method'] != 'POST' or fact['target'] != ('' if fact['operation'] == 'createCase' else head['case_id'])
            or fact['response_status'] != (201 if fact['operation'] == 'createCase' else 202)):
        reject(uow)
    return dict(work=work, fact=fact, receipt=receipt, origin=origin)


def read_target(uow, head, state, request, component, *, original_state=None, consumer=None):
    """Return a seal of accepted facts, not an assertion supplied by the caller.

    The optional original state is internal precommit context. The original
    target must remain available and byte-identical after the outcome is staged.
    """
    initial = state if original_state is None else original_state
    if 'proposal_id' in request:
        from .pass_manual_sources import read_target as proposal_target
        return proposal_target(uow, head, state, request, component,
            original_state=original_state, consumer=consumer)
    lookup = uow.execute(select(investigation.state).where(
        investigation.state.c.case_id == head['case_id'])).mappings().one_or_none()
    block_id = None if lookup is None else lookup['current_block_id']
    failure_id = head['current_failure_id']
    if (not state['available'] or state['input_version'] != head['input_version']
            or state['generation'] != initial['generation'] or state['proposal_record_id'] is not None
            or bool(failure_id) + bool(block_id) != 1):
        reject(uow)
    kind, object_id, field = (('PROCESSING_FAILURE', failure_id, 'processing_failure_id') if failure_id
                             else ('ORDER_LOOKUP_BLOCK', block_id, 'order_lookup_block_id'))
    if request.get(field) != object_id:
        reject(uow)
    sources = Sources(uow, head, component)
    matches = [r for r in sources.proof.revisions.values() if r['kind'] == kind and r['object_id'] == object_id]
    if len(matches) != 1:
        reject(uow)
    row, body = sources.read(matches[0]['record_id'], {kind}, current_actor=False)
    origin = sources.proof.origin(row)
    value = body['block'] if kind == 'ORDER_LOOKUP_BLOCK' else body
    if value['input_version'] != head['input_version'] or value['case_id'] != head['case_id']:
        reject(uow)
    accepted_version = head['case_version'] - (original_state is not None)
    if origin['event_type'] != 'FIXED_PROPOSAL_FAILED' and (
            row['case_version'] != accepted_version or state['generation'] != head['input_version']):
        # Prior to a proposal, every generation came from one accepted input.
        # A same-input revision is a proposal lifecycle path, not an order or
        # intake source that can be retroactively relabelled as current.
        reject(uow)
    seal = dict(record=dict(row), body=body, origin=origin, lookup=None if lookup is None else dict(lookup))
    if kind == 'ORDER_LOOKUP_BLOCK':
        block = one(uow, investigation.blocks, block_id=object_id)
        receipt = one(uow, investigation.receipts, receipt_id=block['receipt_id'])
        work = one(uow, investigation.work, work_id=receipt['work_id'])
        if (lookup['current_work_id'] != work['work_id'] or lookup['current_projection_id'] is not None
                or not receipt['available'] or lookup_receipt(uow, receipt['receipt_id'], head['case_id'],
                    head['input_version'], value['status'], origin) is None):
            reject(uow)
        seal.update(block=block, receipt=receipt, work=work,
                    raw=one(uow, investigation.receipt_contents, receipt_id=receipt['receipt_id']))
        seal['accepted_input'] = accepted_input(uow, head, work['intake_work_id'], sources.proof)
    else:
        failure = one(uow, old.processing_failures, failure_id=object_id)
        if (failure['case_id'] != head['case_id'] or failure['input_version'] != head['input_version']
                or decode_document(failure['body']) != body or timestamp(failure['occurred_at']) != body['occurred_at']):
            reject(uow)
        seal['failure'] = failure
        if origin['event_type'] == 'FIXED_PROPOSAL_FAILED':
            binding = one(uow, t.sources, record_id=row['record_id'])
            event = one(uow, t.events, record_id=row['record_id'])
            work = one(uow, t.work, work_id=binding['work_id'])
            expected = dict(case_id=head['case_id'], input_version=head['input_version'], generation=state['generation'])
            if (any(binding[k] != v or event[k] != v or work[k] != v for k, v in expected.items())
                    or event['event_kind'] != 'PROPOSAL_FAILED' or event['status'] != 'ESCALATED'
                    or event['source_hash'] != row['content_sha256'] or binding['source_hash'] != row['content_sha256']
                    or event['source_audit_event_id'] != origin['event_id'] or event['work_id'] != work['work_id']
                    or event['source_id'] != row['record_id'] or work['state'] != 'DONE' or binding['slot'] != 'PRIMARY'
                    or binding['claim_id'] != work['claim_id'] or binding['epoch'] != work['epoch']
                    or binding['case_version'] != work['claimed_case_version']
                    or binding['authority_revision'] != work['authority_revision']
                    or event['pre_case_version'] != binding['case_version']
                    or event['case_version'] != binding['case_version'] + 1
                    or event['case_version'] != accepted_version):
                reject(uow)
            LifecycleGuards._failure_content(uow, head, initial, work, row, body)
            seal.update(binding=binding, event=event, work=work)
        elif origin['event_type'] == 'ORDER_INVESTIGATION_ACCEPTED':
            if lookup is None:
                reject(uow)
            work = one(uow, investigation.work, work_id=lookup['current_work_id'])
            receipt = one(uow, investigation.receipts, receipt_id=work['invocation_id'])
            raw = one(uow, investigation.receipt_contents, receipt_id=receipt['receipt_id'])
            from .investigation_policy import ACTOR
            observation = decode_document(raw['body'])
            if (lookup is None or lookup['current_work_id'] != work['work_id'] or not receipt['available']
                    or receipt['status'] != 'PROVIDER_FAILURE' or work['state'] != 'FAILED'
                    or work['case_id'] != head['case_id'] or work['input_version'] != head['input_version']
                    or work['owner_id'] != head['owner_principal_id'] or work['store_id'] != head['store_id']
                    or work['invocation_id'] != receipt['receipt_id'] or work['claim_id'] != receipt['claim_id']
                    or work['epoch'] != receipt['epoch'] or receipt['case_id'] != head['case_id']
                    or receipt['input_version'] != head['input_version']
                    or digest(observation, 'order-receipt/v1') != receipt['body_hash']
                    or observation['result']['status'] != 'PROVIDER_FAILURE'
                    or observation['result']['case_id'] != head['case_id']
                    or observation['result']['input_version'] != head['input_version']
                    or observation['service_signature'] != work['service_signature']
                    or observation['grant_signature'] != work['grant_signature']
                    or work['claimed_case_version'] + 1 != row['case_version']
                    or work['completed_at'] != receipt['recorded_at']
                    or origin['occurred_at'] != timestamp(receipt['recorded_at'])
                    or origin['actor'] != ACTOR or origin['payload_hash'] != digest(dict(
                        work_id=work['work_id'], receipt_id=receipt['receipt_id'],
                        source_input_version=work['input_version'], status='PROVIDER_FAILURE'), 'audit-payload/v1')):
                reject(uow)
            seal.update(receipt=receipt, work=work, raw=raw)
            seal['accepted_input'] = accepted_input(uow, head, work['intake_work_id'], sources.proof)
        elif origin['event_type'] == 'CUSTOMER_INTAKE_FAILED':
            session = one(uow, old.intake_sessions, case_id=head['case_id'])
            work = one(uow, old.intake_work, work_id=session['current_work_id'])
            fact = one(uow, old.acceptances, acceptance_id=work['acceptance_id'])
            original = one(uow, old.receipts, acceptance_id=work['acceptance_id'])
            from .intake_processor import SERVICE
            if (work['state'] != 'FAILED' or work['case_id'] != head['case_id']
                    or work['input_version'] != head['input_version'] or work['claim_id'] is None
                    or work['claim_epoch'] < 1 or work['accepted_owner_id'] != head['owner_principal_id']
                    or work['accepted_store_id'] != head['store_id'] or not original['available']
                    or original['body'] is None or session['current_work_id'] != work['work_id']
                    or session['status'] != 'ESCALATED_FAILURE'
                    or fact['resource_id'] != head['case_id'] or fact['store_id'] != head['store_id']
                    or origin['occurred_at'] != timestamp(work['completed_at']) or origin['actor'] != SERVICE
                    or origin['payload_hash'] != digest({'work_id':work['work_id'], 'failure_id':object_id}, 'audit-payload/v1')):
                reject(uow)
            seal.update(work=work, session=session, fact=fact, original=original)
            seal['accepted_input'] = accepted_input(uow, head, work['work_id'], sources.proof)
        else:
            reject(uow)
    return seal
