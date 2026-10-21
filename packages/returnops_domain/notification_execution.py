"""Read the accepted modern return/label/PDF chain without dispatch authority.

The retained acceptance is selected by its persisted ID. It is not a fabricated
Founder actor, a supplied original key, or an alternative execution entry point.
"""
from sqlalchemy import select, or_
from . import customer_tables as old
from .canonical import digest
from .lifecycle_schema import NOTIFICATION, version
from .lifecycle_state import current, reject
from .manual_target import one
from .execution_artifact_chain_sources import _continuation_material, _approval_receipt_fact
from .return_execution_tables import controls as returns, ledger as return_facts
from .label_execution_tables import controls as labels, artifact_work
from .label_artifact_tables import artifacts
from .generated_evidence import verify_certificate
from .wire import validate


class _AcceptedExecution:
    def __init__(self, acceptance):
        self.acceptance = acceptance

    def receipt(self, uow, head, seal, acceptance_id):
        fact = self.acceptance
        decision, approval, event = seal['decision'], seal['body'], seal['event']
        request = dict(expected_case_version=event['pre_case_version'], decision='APPROVE',
            proposal_id=decision['proposal_id'], proposal_version=decision['proposal_version'],
            reason=decision['reason'], preview_id=approval['preview_id'],
            scope_fingerprint=approval['scope_fingerprint'])
        validate('FounderDecisionRequest', request, internal=True)
        if (fact['acceptance_id'] != acceptance_id or fact['principal_id'] != decision['principal_id']
                or fact['principal_id'] != approval['principal_id'] or fact['store_id'] != head['store_id']
                or fact['method'] != 'POST' or fact['operation'] != 'recordFounderDecision'
                or fact['target'] != head['case_id'] or fact['resource_kind'] != 'CASE'
                or fact['resource_id'] != head['case_id']
                or fact['fingerprint'] != digest(request, 'founder-approve-request/v1')):
            reject(uow)
        return _approval_receipt_fact(uow, head, seal, fact)

    def _identity(self, uow, head, row, module, domain):
        fact = self.acceptance
        if (row['case_id'] != head['case_id'] or row['store_id'] != head['store_id']
                or row['owner_id'] != head['owner_principal_id']
                or row['principal_id'] != fact['principal_id']
                or row['approval_acceptance_id'] != fact['acceptance_id']
                or row['original_key_hash'] != digest(
                    dict(principal_id=fact['principal_id'], original_key=fact['request_key']),
                    domain + '-original-key/v1')
                or row['config_id'] != module.CONFIG['config_id']
                or row['provider_id'] != module.CONFIG['provider_id']
                or row['config_hash'] != module.config_hash()
                or row['binding_hash'] != digest(module.control_payload(row), domain + '-reservation/v1')):
            reject(uow)

    def return_identity(self, uow, head, row):
        from . import return_execution_sources as module
        self._identity(uow, head, row, module, 'return')

    def label_identity(self, uow, head, row):
        from . import label_execution_sources as module
        self._identity(uow, head, row, module, 'label')
        if any(row[name] != value for name, value in module.identities(row['execution_work_id']).items()):
            reject(uow)

    def bridge(self, uow, head, row, root):
        from .execution_chain_sources import retained_bridge
        return retained_bridge(uow, self.acceptance['principal_id'], head, row, root)


def completed_pair(uow, head):
    """Complete exact union, including real certificate bytes and every effect."""
    if version(uow.connection) != NOTIFICATION:
        reject(uow)
    rows = list(uow.execute(select(returns).where(returns.c.case_id == head['case_id'])).mappings())
    if len(rows) != 1:
        reject(uow)
    returned = dict(rows[0])
    facts = list(uow.execute(select(return_facts).where(or_(
        return_facts.c.effect_key == returned['effect_key'],
        return_facts.c.operation_id == returned['operation_id'],
        return_facts.c.dispatch_record_id == returned['dispatch_record_id'],
        return_facts.c.dispatch_binding_hash == returned['binding_hash']))).mappings())
    if len(facts) != 1 or facts[0]['effect_key'] != returned['effect_key']:
        reject(uow)
    acceptance = one(uow, old.acceptances, acceptance_id=returned['approval_acceptance_id'])
    root = _continuation_material(uow, head, returned, _AcceptedExecution(acceptance))
    matches = list(uow.execute(select(labels).where(labels.c.case_id == head['case_id'])).mappings())
    if (root is None or len(matches) != 1 or returned['status'] != 'SUCCEEDED'
            or not returned['source_available'] or not returned['result_retained']):
        reject(uow)
    label = dict(matches[0])
    work = one(uow, artifact_work, control_id=label['control_id'])
    artifact = one(uow, artifacts, work_id=work['work_id'])
    seal = verify_certificate(uow, artifact['evidence_id'])
    state = current(uow, head, initialize=False)
    approval = root['approval']
    if (state is None or not state['available'] or head['current_failure_id'] is not None
            or state['input_version'] != head['input_version']
            or state['generation'] != returned['generation']
            or state['generation'] != label['generation']
            or state['approval_record_id'] != returned['approval_record_id']
            or state['approval_record_id'] != approval['record']['record_id']
            or state['proposal_record_id'] != approval['preview']['row']['proposal_record_id']
            or state['review_record_id'] != approval['preview']['row']['review_record_id']
            or state['preview_id'] != approval['preview']['row']['preview_id']):
        reject(uow)
    if state['outcome'] is None:
        if (head['status'] not in {'ACTION_IN_PROGRESS', 'RECONCILING'}
                or any(state[name] is not None for name in
                       ('outcome_record_id','notification_id','notification_record_id',
                        'notification_work_id','return_record_id','label_record_id'))):
            reject(uow)
    elif (state['outcome'] != 'RETURN_CREATED'
            or head['status'] not in {'NOTIFICATION_PENDING','NOTIFICATION_FAILED','COMPLETED'}
            or state['return_record_id'] != returned['result_record_id']
            or state['label_record_id'] != seal['result_record']['record_id']
            or any(state[name] is None for name in
                   ('outcome_record_id','notification_id','notification_record_id','notification_work_id'))):
        reject(uow)
    if (label['confirmed_effect_status'] != 'SUCCEEDED' or not label['source_available']
            or not label['confirmation_retained'] or not artifact['available']
            or seal['content'] is None
            or returned['input_version'] != head['input_version']
            or label['input_version'] != head['input_version']):
        reject(uow)
    return dict(root=root, returned=returned, label=label, artifact=seal,
                acceptance=acceptance, return_record_id=returned['result_record_id'],
                label_record_id=seal['result_record']['record_id'],
                evidence_id=artifact['evidence_id'])
