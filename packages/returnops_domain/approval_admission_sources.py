"""Read-only actual-source proof for the first private CREATE_RETURN check.

Original approval replay remains in approve_sources. This separate verifier
requires current inputs and deliberately does not support any prior operation.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from sqlalchemy import select
from . import customer_tables as old, founder_tables as founder
from . import investigation_tables as inv, lifecycle_tables as life, storage
from . import idempotency, preview_profile as policy
from .audit import timestamp
from .canonical import digest
from .approve_sources import accepted_approval, execution_identity
from .errors import FlowError
from .lifecycle_effects import fingerprint
from .lifecycle_schema import APPROVAL_VERSIONS, version
from .lifecycle_sources import Sources, authority
from .lifecycle_state import current, reject
from .manual_target import one
from .pass_review_sources import accepted_review
from .preview_tables import previews
from .wire import validate


class AdmissionUncertain(Exception):
    """An original outcome is unresolved; this does not authorize retry."""


class ProofReads:
    """Reject trusted helper mutations while retaining the original write fence.

    Not a database sandbox: only audited internal Select statements reach this
    object. Raw connection access is confined to existing schema/F.03 readers.
    There is no caller-controlled SQL or general query API.
    """
    def __init__(self, uow):
        self._uow = uow
        self.connection = uow.connection

    def poison(self):
        self._uow.poison()

    def execute(self, statement, parameters=None):
        if not getattr(statement, 'is_select', False):
            reject(self)
        return self._uow.execute(statement, parameters)


def restricted_bytes(value):
    """docs09 bytes, with bounded shape checking before wire normalization."""
    def check(item, depth=0):
        if depth > 12:
            raise FlowError('VALIDATION_ERROR')
        if type(item) is str:
            if not item.isascii() or len(item) > 4096:
                raise FlowError('VALIDATION_ERROR')
        elif type(item) is int:
            if not -(2**53-1) <= item <= 2**53-1:
                raise FlowError('VALIDATION_ERROR')
        elif type(item) is bool:
            pass
        elif type(item) is list and len(item) <= 100:
            for entry in item:
                check(entry, depth+1)
        elif type(item) is dict and len(item) <= 32 and all(type(key) is str for key in item):
            for key, entry in item.items():
                check(key, depth+1); check(entry, depth+1)
        else:
            raise FlowError('VALIDATION_ERROR')
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def command_request(value):
    restricted_bytes(value)
    validate('CommandSpec', value)
    return deepcopy(value)


def authorize(uow, callback, case_id):
    actor = callback(uow.connection, 'getSession')
    if actor.role != 'FOUNDER':
        reject(uow, 'FORBIDDEN')
    if callback(uow.connection, 'getFounderCase', case_id) != actor:
        reject(uow, 'UNAUTHENTICATED')
    if version(uow.connection) not in APPROVAL_VERSIONS:
        reject(uow)
    head = uow.execute(select(old.case_heads).where(old.case_heads.c.case_id == case_id)
                       .with_for_update()).mappings().one_or_none()
    if head is None or not head['available']:
        reject(uow, 'NOT_FOUND')
    if head['store_id'] != actor.store_id:
        reject(uow, 'FORBIDDEN')
    grant = authority(uow, head, policy.APPROVAL_COMPONENT, 'EXECUTION')
    return actor, dict(head), dict(grant)


def session_bounds(uow, actor):
    """Retain current registry bounds for the already verified session identity.

    F.03 binds these exact integer dates to signed JWT claims. A final real
    getSession call re-establishes that binding; this tuple is never supplied by
    the request and is not independently an authentication credential.
    """
    row = uow.execute(select(old.sessions).where(old.sessions.c.session_id == actor.session_id,
        old.sessions.c.principal_id == actor.principal_id)).mappings().one_or_none()
    if row is None or row['revoked'] is not False:
        reject(uow, 'UNAUTHENTICATED')
    times = tuple(row[name] for name in ('issued_at', 'not_before', 'expires_at'))
    if (any(type(value) is not int or not 0 <= value <= 9007199254740991 for value in times)
            or not times[0] <= times[1] < times[2]):
        reject(uow, 'UNAUTHENTICATED')
    return (row['principal_id'], row['session_id'], *times, row['revoked'])


def check_session_time(now, bounds):
    """Additional admission freshness; deliberately stricter than F.03 leeway."""
    if type(now) is not datetime or now.utcoffset() != timedelta(0):
        raise FlowError('INVALID_STATE')
    issued, not_before, expires = bounds[2:5]
    if not issued <= not_before <= now.timestamp() < expires:
        raise FlowError('UNAUTHENTICATED')


def source_closure(uow, case_id):
    """Exact transient raw-row seal of this case's referenced source closure.

    Bodies stay in memory and are never returned/logged. Primary-key ordering
    makes insertion, removal, availability and byte changes observable. No
    unrelated case or whole-database scan is performed.
    """
    history_ids = select(old.history.c.record_id).where(old.history.c.case_id == case_id)
    evidence_ids = select(old.evidence.c.evidence_id).where(old.evidence.c.case_id == case_id)
    statement_ids = select(storage.original_statement_records.c.statement_id).where(
        storage.original_statement_records.c.case_id == case_id)
    acceptance_ids = select(old.acceptances.c.acceptance_id).where(
        old.acceptances.c.resource_kind == 'CASE', old.acceptances.c.resource_id == case_id)
    order_ids = select(inv.receipts.c.receipt_id).where(inv.receipts.c.case_id == case_id)
    projection_ids = select(inv.projections.c.projection_id).where(inv.projections.c.case_id == case_id)
    work_ids = select(inv.work.c.work_id).where(inv.work.c.case_id == case_id)
    cases = (storage.case_records, storage.original_statement_records, old.case_heads,
        old.history, old.audit, old.evidence, old.questions, old.intake_sessions, old.intake_work,
        old.processing_failures, inv.state, inv.work, inv.clarification_inputs, inv.receipts,
        inv.projections, inv.blocks, life.state, life.work, life.sources, life.events, life.effects, previews)
    queries = [(table, table.c.case_id == case_id) for table in cases]
    queries += [(old.history_contents, old.history_contents.c.record_id.in_(history_ids)),
        (founder.encodings, founder.encodings.c.record_id.in_(history_ids)),
        (old.evidence_contents, old.evidence_contents.c.evidence_id.in_(evidence_ids)),
        (storage.original_statement_contents, storage.original_statement_contents.c.statement_id.in_(statement_ids)),
        (old.acceptances, old.acceptances.c.acceptance_id.in_(acceptance_ids)),
        (old.receipts, old.receipts.c.acceptance_id.in_(acceptance_ids)),
        (old.receipt_refs, old.receipt_refs.c.acceptance_id.in_(acceptance_ids)),
        (inv.receipt_contents, inv.receipt_contents.c.receipt_id.in_(order_ids)),
        (inv.projection_contents, inv.projection_contents.c.projection_id.in_(projection_ids)),
        (inv.inputs, inv.inputs.c.work_id.in_(work_ids))]
    return {table.name: [dict(row) for row in uow.execute(select(table).where(clause)
        .order_by(*table.primary_key.columns)).mappings()] for table, clause in queries}


def prior_operation(uow, head):
    refs = list(uow.execute(select(life.effects).where(life.effects.c.case_id == head['case_id'])).mappings())
    records = list(uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
        old.history.c.kind == 'OPERATION')).mappings())
    if not records and not refs:
        if head['status'] == 'RECONCILING':
            raise AdmissionUncertain()
        return
    sources = Sources(uow, head, policy.APPROVAL_COMPONENT)
    bodies = {row['record_id']: sources.read(row['record_id'], {'OPERATION'}, current_actor=False)
              for row in records}
    for ref in refs:
        pair = bodies.get(ref['record_id'])
        if pair is None:
            reject(uow)
        row, body = pair
        if (ref['operation_id'] != body['operation_id'] or ref['object_version'] != row['object_version']
                or ref['status'] != body['status']):
            reject(uow)
    if any(body['status'] in {'UNKNOWN', 'RECONCILING'} for _, body in bodies.values()):
        raise AdmissionUncertain()
    # Includes FAILED/BLOCKED: retry/continuation is deliberately later scope.
    reject(uow)


def approval_receipt(uow, actor, head, seal, original_key):
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
    expected_refs = {('CASE', head['case_id'])} | {(row['kind'], row['object_id']) for row in
        uow.execute(select(old.history).where(old.history.c.case_id == head['case_id'],
            old.history.c.kind.in_(['STATEMENT', 'EVIDENCE']))).mappings()}
    if {(row['kind'], row['object_id']) for row in refs} != expected_refs:
        reject(uow)
    return dict(fact=dict(fact), receipt=one(uow, old.receipts, acceptance_id=fact['acceptance_id']), refs=refs)


def read_proof(uow, actor, head, expected, execution_id, original_key, candidate):
    prior_operation(uow, head)
    if head['case_version'] != expected:
        reject(uow, 'STALE_CASE_VERSION')
    state = current(uow, head, initialize=False)
    if (head['status'] != 'APPROVED' or head['current_failure_id'] is not None
            or state is None or not state['available'] or state['approval_record_id'] is None
            or any(state[name] is not None for name in ('outcome_record_id', 'outcome', 'notification_id',
                'notification_record_id', 'notification_hash', 'notification_work_id', 'return_record_id', 'label_record_id'))):
        reject(uow)
    investigation = one(uow, inv.state, case_id=head['case_id'])
    if investigation['current_block_id'] is not None:
        reject(uow)
    seal = accepted_approval(uow, head, state['approval_record_id'], policy.APPROVAL_COMPONENT)
    review = accepted_review(uow, head, state, policy.APPROVAL_COMPONENT, current=True)
    if (review != seal['preview']['review'] or state['preview_id'] != seal['body']['preview_id']
            or head['case_version'] != seal['event']['case_version']
            or head['input_version'] != seal['event']['input_version']
            or state['generation'] != seal['event']['generation']):
        reject(uow)
    receipt = approval_receipt(uow, actor, head, seal, original_key)
    execution = seal['execution']
    derived_id, target_hash = execution_identity(seal['record'], seal['body'], state['generation'])
    if (execution_id != derived_id or execution['work_id'] != derived_id
            or execution['target_hash'] != target_hash or execution['idempotency_key'] != derived_id
            or execution['state'] != 'PENDING' or execution['epoch'] != 0
            or any(execution[name] is not None for name in
                ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))):
        reject(uow)
    scope = seal['body']['scope']
    restricted_bytes(scope)
    validate('ApprovalScope', scope, internal=True)
    profile = policy.profile()
    preview = seal['preview']['row']
    if (profile != policy.PROFILE or preview['profile_hash'] != policy.profile_hash(profile)
            or preview['profile_version'] != profile['version']
            or seal['preview']['body'] != policy.build(preview['preview_id'], review['proposal']['body'],
                review['body']['review'], preview['issued_at'], profile)
            or fingerprint(scope) != seal['body']['scope_fingerprint']
            or candidate['type'] != 'CREATE_RETURN'
            or restricted_bytes(candidate) != restricted_bytes(scope['commands'][0])):
        reject(uow)
    # Original docs09 operation fingerprint, never a permission or new identity.
    operation = fingerprint(dict(approval_id=seal['body']['approval_id'],
        scope_fingerprint=seal['body']['scope_fingerprint'], command=scope['commands'][0]))
    return dict(state=dict(state), approval=seal, original_receipt=receipt,
                operation_fingerprint=operation)


def check_time(now, proof, *, initial=None):
    if type(now) is not datetime or now.utcoffset() != timedelta(0):
        raise FlowError('INVALID_STATE')
    preview = proof['approval']['preview']['row']
    approval_at = proof['approval']['record']['recorded_at']
    if (now < approval_at or now < preview['issued_at'] or now >= preview['expires_at']
            or initial is not None and now < initial):
        raise FlowError('INVALID_STATE')
