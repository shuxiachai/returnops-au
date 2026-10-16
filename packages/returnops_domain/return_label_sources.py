"""Actual modern N2 retained-source proof and distinct bridge receipt checks.

No snapshot/precheck result, provider value or claim is accepted from a caller.
These readers use the original production N1/N2/approval/review invariants.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from sqlalchemy import and_, or_, select
from . import customer_tables as old, lifecycle_tables as life
from .approval_admission_sources import ProofReads
from .audit import timestamp
from .canonical import digest, encode_document
from .execution_preparation_sources import source_closure
from .founder_integrity import CaseProof
from .lifecycle_events import LifecycleClaim
from .lifecycle_sources import Sources
from .lifecycle_state import current, reject
from .manual_target import one
from .pass_review_sources import accepted_review
from .preview_profile import APPROVAL_COMPONENT, PROFILE
from .return_execution_sources import COMPONENT, continued_proof
from .return_execution_tables import controls, ledger

KIND = 'RETURN_SOURCE'


@dataclass(frozen=True, slots=True, repr=False)
class CoreReturnSourceAccepted:
    event_id: str
    claim: LifecycleClaim
    record_id: str
    approval_record_id: str
    dispatch_record_id: str
    ledger_hash: str
    target_hash: str


def closure(uow, case_id):
    """Transient exact real rows, never persisted, returned or used as authority."""
    reads = ProofReads(uow)
    saved = source_closure(reads, case_id)
    saved[controls.name] = [dict(row) for row in reads.execute(select(controls).where(
        controls.c.case_id == case_id).order_by(controls.c.preparation_id)).mappings()]
    keys = select(controls.c.effect_key).where(controls.c.case_id == case_id)
    saved[ledger.name] = [dict(row) for row in reads.execute(select(ledger).where(
        ledger.c.effect_key.in_(keys)).order_by(ledger.c.effect_key)).mappings()]
    return saved


def read_source(uow, authorization, execution_work_id, original_key):
    """Full real retained proof plus current state, never label dispatch permission."""
    actor, head, grant, permission, bounds = authorization
    reads = ProofReads(uow)
    found = reads.execute(select(controls).where(
        controls.c.execution_work_id == execution_work_id)).mappings().one_or_none()
    if found is None:
        return None
    control = dict(found)
    root = continued_proof(reads, actor, head, control, original_key)
    state = current(reads, head, initialize=False)
    if (root is None or state is None or not state['available']
            or head['status'] != 'ACTION_IN_PROGRESS' or head['current_failure_id'] is not None
            or not control['source_available'] or not control['result_retained']
            or control['status'] != 'SUCCEEDED'
            or any(state[name] is not None for name in ('outcome_record_id', 'outcome', 'notification_id',
                'notification_record_id', 'notification_hash', 'notification_work_id', 'return_record_id', 'label_record_id'))):
        reject(uow)
    approval = root['approval']; scope = approval['body']['scope']
    preview = approval['preview']
    expected = dict(input_version=head['input_version'], generation=control['generation'],
        proposal_version=scope['proposal_version'], proposal_record_id=preview['row']['proposal_record_id'],
        review_record_id=preview['row']['review_record_id'], preview_id=approval['body']['preview_id'],
        approval_record_id=approval['record']['record_id'])
    if (any(state[name] != value for name, value in expected.items())
            or scope['input_version'] != head['input_version']
            or control['input_version'] != head['input_version']
            or approval['event']['generation'] != state['generation']
            or accepted_review(reads, head, state, APPROVAL_COMPONENT, current=True) != preview['review']):
        reject(uow)
    execution = approval['execution']
    if (execution['work_id'] != execution_work_id or execution['state'] != 'PENDING' or execution['epoch'] != 0
            or any(execution[name] is not None for name in
                ('claim_id', 'claimed_case_version', 'lease_expires_at', 'authority_revision'))):
        reject(uow)
    facts = reads.execute(select(ledger).where(ledger.c.effect_key == control['effect_key'])).mappings().one_or_none()
    if facts is None or facts['status'] != 'SUCCEEDED':
        reject(uow)
    fact = dict(facts)
    sources = Sources(reads, head, COMPONENT)
    record, body = sources.read(control['result_record_id'], {'OPERATION'})
    origin = sources.proof.origin(record)
    create, label = scope['commands']
    result = body.get('result')
    if (create['type'] != 'CREATE_RETURN' or label['type'] != 'GENERATE_LABEL'
            or create['provider_id'] != PROFILE['return_provider'] or label['provider_id'] != PROFILE['label_provider']
            or label['parameters']['return_command_id'] != create['command_id']
            or create['parameters']['parcel_id'] != label['parameters']['parcel_id']
            or label['parameters']['parcel_id'] != scope['parcel_id']
            or 'provider_return_id' in label['parameters']
            or body['status'] != 'SUCCEEDED' or body['approval_id'] != approval['body']['approval_id']
            or body['command_id'] != create['command_id'] or body['provider_id'] != create['provider_id']
            or result != dict(type='CREATE_RETURN', provider_return_id=fact['provider_return_id'], parcel_id=scope['parcel_id'])
            or control['parcel_id'] != scope['parcel_id'] or body['provider_operation_id'] != fact['provider_operation_id']):
        reject(uow)
    return dict(state=dict(state), root=root, control=control, fact=fact, record=dict(record),
        body=deepcopy(body), origin=deepcopy(origin), label_command=deepcopy(label))


def identity(actor, head, source):
    control, root, record, fact = (source[name] for name in ('control', 'root', 'record', 'fact'))
    values = dict(case_id=head['case_id'], store_id=head['store_id'], owner_id=head['owner_principal_id'],
        principal_id=actor.principal_id, execution_work_id=control['execution_work_id'],
        preparation_id=control['preparation_id'], approval_acceptance_id=control['approval_acceptance_id'],
        approval_record_id=root['approval']['record']['record_id'],
        approval_hash=root['approval']['record']['content_sha256'],
        dispatch_record_id=control['dispatch_record_id'], dispatch_binding_hash=control['binding_hash'],
        result_record_id=record['record_id'], result_hash=record['content_sha256'], ledger_hash=fact['fact_hash'],
        input_version=head['input_version'], generation=source['state']['generation'],
        original_key_hash=control['original_key_hash'])
    target_hash = digest(values, 'core-return-source-target/v1')
    return dict(work_id='rswork_' + target_hash, event_id='rsevt_' + target_hash,
        idempotency_key='rskey_' + target_hash, target_hash=target_hash)


def event_for(ids, claim, source):
    return CoreReturnSourceAccepted(ids['event_id'], claim, source['record']['record_id'],
        source['root']['approval']['record']['record_id'], source['control']['dispatch_record_id'],
        source['fact']['fact_hash'], ids['target_hash'])


def event_fingerprint(event):
    return digest({'kind': KIND, **asdict(event)}, 'lifecycle-event/v1')


def audit_payload(event):
    return dict(event=KIND, work_id=event.claim.work_id, source_record_id=event.record_id,
                generation=event.claim.generation, target_hash=event.target_hash)


def binding_values(head, event, source):
    return dict(record_id=event.record_id, case_id=head['case_id'], **asdict(event.claim),
        source_hash=source['record']['content_sha256'], target_record_id=event.approval_record_id,
        slot='PRIMARY', dispatch_source_record_id=event.dispatch_record_id,
        provider_operation_id=source['fact']['provider_operation_id'], artifact_evidence_id=None,
        artifact_sha256=None, order_projection_id=None)


def receipt_values(head, event, source, accepted_at):
    claim = event.claim
    return dict(event_id=event.event_id, case_id=head['case_id'], work_id=claim.work_id,
        record_id=event.record_id, fingerprint=event_fingerprint(event), event_kind=KIND,
        source_id=event.record_id, source_hash=source['record']['content_sha256'],
        source_audit_event_id=source['origin']['event_id'], pre_case_version=claim.case_version,
        case_version=claim.case_version + 1, pre_input_version=claim.input_version,
        input_version=claim.input_version, pre_generation=claim.generation, generation=claim.generation,
        status='ACTION_IN_PROGRESS', accepted_at=accepted_at)


def retained_acceptance(uow, head, source, ids):
    """Read exact prior claim/receipt; never reclaim or repair partial rows."""
    record_id = source['record']['record_id']
    works = list(uow.execute(select(life.work).where(or_(life.work.c.work_id == ids['work_id'],
        and_(life.work.c.case_id == head['case_id'], life.work.c.purpose == 'EFFECT',
             life.work.c.target_record_id == record_id)))).mappings())
    bindings = list(uow.execute(select(life.sources).where(or_(
        life.sources.c.record_id == record_id, life.sources.c.work_id == ids['work_id']))).mappings())
    receipts = list(uow.execute(select(life.events).where(or_(life.events.c.event_id == ids['event_id'],
        life.events.c.record_id == record_id, life.events.c.work_id == ids['work_id']))).mappings())
    if not works and not bindings and not receipts:
        return None
    if len(works) != 1 or len(bindings) != 1 or len(receipts) != 1:
        reject(uow)
    work, binding, receipt = dict(works[0]), dict(bindings[0]), dict(receipts[0])
    if (work['work_id'] != ids['work_id'] or work['case_id'] != head['case_id']
            or work['store_id'] != head['store_id'] or work['owner_id'] != head['owner_principal_id']
            or work['component_id'] != COMPONENT or work['purpose'] != 'EFFECT'
            or work['target_hash'] != ids['target_hash'] or work['target_record_id'] != record_id
            or work['idempotency_key'] != ids['idempotency_key'] or work['state'] != 'DONE'
            or work['epoch'] != 1 or work['claim_id'] is None or work['authority_revision'] is None
            or work['authority_revision'] < 1 or work['lease_expires_at'] is not None
            or work['input_version'] != head['input_version'] or work['generation'] != source['state']['generation']
            or work['claimed_case_version'] is None
            or not source['record']['case_version'] <= work['claimed_case_version'] < head['case_version']):
        reject(uow)
    claim = LifecycleClaim(work['work_id'], work['claim_id'], work['epoch'], work['claimed_case_version'],
        work['input_version'], work['generation'], work['authority_revision'])
    event = event_for(ids, claim, source)
    if (binding != binding_values(head, event, source)
            or receipt != receipt_values(head, event, source, receipt['accepted_at'])
            or receipt['case_version'] > head['case_version']
            or receipt['accepted_at'] < source['record']['recorded_at']
            or receipt['accepted_at'] < work['created_at']):
        reject(uow)
    proof = CaseProof(ProofReads(uow), head)
    audits = [entry for entry in proof.events if entry['correlation_id'] == event.event_id]
    if len(audits) != 1:
        reject(uow)
    audit = audits[0]
    if (audit['event_type'] != 'LIFECYCLE_EVENT_ACCEPTED'
            or audit['actor'] != {'kind': 'SERVICE', 'component_id': COMPONENT}
            or audit['object_ids'] != [source['control']['operation_id'], work['work_id']]
            or audit['history_refs'] != [] or audit['case_version'] != receipt['case_version']
            or audit['occurred_at'] != timestamp(receipt['accepted_at'])
            or audit['payload_hash'] != digest(audit_payload(event), 'audit-payload/v1')):
        reject(uow)
    return dict(work=work, binding=binding, receipt=receipt, audit=audit, event=event)


def expected_delta(uow, before, head, work, binding, receipt, audit):
    """Construct the permitted write set; never trust a newly captured baseline."""
    expected = deepcopy(before)
    for table, row in ((life.work, work), (life.sources, binding), (life.events, receipt),
                       (old.audit, dict(event_id=audit['event_id'], case_id=head['case_id'],
                         sequence=head['audit_sequence'] + 1, event_hash=audit['event_hash'],
                         body=encode_document(audit)))):
        if set(row) != {column.name for column in table.columns}:
            reject(uow)
        keys = [column.name for column in table.primary_key.columns]
        if any(all(saved[key] == row[key] for key in keys) for saved in expected[table.name]):
            reject(uow)
        expected[table.name] = sorted(expected[table.name] + [deepcopy(row)], key=lambda item:tuple(item[key] for key in keys))
    original, = expected[old.case_heads.name]
    if original != head:
        reject(uow)
    expected[old.case_heads.name] = [{**head, 'case_version':head['case_version'] + 1,
        'updated_at':receipt['accepted_at'], 'audit_sequence':head['audit_sequence'] + 1, 'audit_head':audit['event_hash']}]
    return expected


def context(source):
    """Private derived result; frozen GenerateLabelCommand parameters stay exact."""
    return dict(label_command=deepcopy(source['label_command']),
        provider_return_id=source['body']['result']['provider_return_id'],
        parcel_id=source['body']['result']['parcel_id'], return_operation_id=source['control']['operation_id'],
        source_record_id=source['record']['record_id'], source_hash=source['record']['content_sha256'],
        approval_record_id=source['root']['approval']['record']['record_id'],
        dispatch_record_id=source['control']['dispatch_record_id'], ledger_hash=source['fact']['fact_hash'])

