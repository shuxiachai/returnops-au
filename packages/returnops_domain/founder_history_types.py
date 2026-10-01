"""Neutral frozen-history decoding, not proposal/approval/execution production.

These event names define the internal storage contract for future producers.
Reading a valid retained record grants no current decision or effect authority.
"""
from .errors import FlowError
from .founder_codec import validate

ORIGINS = {
    'PROPOSAL': {'PROPOSAL_ACCEPTED'},
    'REVIEW': {'RISK_REVIEW_ACCEPTED'},
    'DECISION': {'FOUNDER_DECISION_ACCEPTED'},
    'APPROVAL': {'FOUNDER_APPROVAL_ISSUED'},
    'OPERATION': {'OPERATION_REVISION_RECORDED'},
    'NOTIFICATION': {'NOTIFICATION_REVISION_RECORDED'},
}
SCHEMAS = {'PROPOSAL': 'HistoricalProposalBundle', 'REVIEW': 'HistoricalRiskReview',
           'DECISION': 'FounderDecisionRecord', 'APPROVAL': 'ApprovalRecord',
           'OPERATION': 'OperationAttempt', 'NOTIFICATION': 'NotificationRecord'}
IDENTITIES = {'PROPOSAL': 'proposal_id', 'REVIEW': 'review_id', 'DECISION': 'decision_id',
              'APPROVAL': 'approval_id', 'OPERATION': 'operation_id', 'NOTIFICATION': 'notification_id'}


def _same(left, right, names):
    if any(left[name] != right[name] for name in names):
        raise FlowError()


def _unique(values):
    if len(values) != len(set(values)):
        raise FlowError()
    return set(values)


def proposal_bindings(bundle):
    """Compare saved input identities; do not retrieve or rerun assessment/Risk."""
    packet = bundle['packet']
    for name in ('order_lookup', 'retrieval_result', 'citation_verification', 'image_observations'):
        if name in bundle:
            _same(packet, bundle[name], ('case_id', 'input_version'))
    for name in ('retrieval_result', 'citation_verification'):
        _same(packet, bundle[name], ('corpus_version',))
    _same(packet, bundle['citation_verification'], ('proposal_id', 'proposal_version'))
    statements = _unique([item['statement_id'] for item in bundle['statements']])
    attachments = _unique([item['evidence_id'] for item in bundle['attachments']])
    original = [item['statement_id'] for item in bundle['statements'] if item['kind'] == 'ORIGINAL']
    if original != [packet['original_statement_id']] or bundle['evidence_matrix'] != packet['evidence_matrix']:
        raise FlowError()
    for attachment in bundle['attachments']:
        if attachment['status'] != 'BOUND' or attachment.get('case_id') != packet['case_id']:
            raise FlowError()
    for criterion in bundle['evidence_matrix']:
        if not set(criterion['statement_ids']) <= statements or not set(criterion['evidence_ids']) <= attachments:
            raise FlowError()
    citations = _unique([item['citation_id'] for item in packet['citations']])
    checks = _unique([item['citation_id'] for item in bundle['citation_verification']['checks']])
    if citations != checks:
        raise FlowError()
    for item in packet['citations'] + bundle['retrieval_result']['passages']:
        if item['corpus_version'] != packet['corpus_version']:
            raise FlowError()
    if 'image_observations' in bundle and any(item['evidence_id'] not in attachments
            for item in bundle['image_observations']['observations']):
        raise FlowError()


def verify_content(row, content, origin, proof, read_source):
    kind = row['kind']
    # Strict DTO validation precedes every nested field access.
    validate(SCHEMAS[kind], content)
    body = content['packet'] if kind == 'PROPOSAL' else content['review'] if kind == 'REVIEW' else content
    case = body['scope']['case_id'] if kind == 'APPROVAL' else body['case_id']
    if body[IDENTITIES[kind]] != row['object_id'] or case != row['case_id']:
        raise FlowError()
    if 'case_version' in body and body['case_version'] > row['case_version']:
        raise FlowError()
    inputs = body['scope'] if kind == 'APPROVAL' else body
    if inputs.get('input_version', 1) > proof.head['input_version']:
        raise FlowError()
    actor = origin['actor']
    if kind in {'DECISION', 'APPROVAL'}:
        if actor != {'kind': 'HUMAN', 'role': 'FOUNDER', 'principal_id': body['principal_id']}:
            raise FlowError()
    elif actor['kind'] == 'MODEL':
        if actor['model_run'] != body.get('model_run'):
            raise FlowError()
    if kind == 'PROPOSAL':
        if row['object_version'] != body['proposal_version']:
            raise FlowError()
        proposal_bindings(content)
    elif kind == 'REVIEW':
        source = proof.revisions.get(content['proposal_record_id'])
        if (source is None or source['kind'] != 'PROPOSAL' or source['case_id'] != row['case_id']
                or source['object_id'] != body['proposal_id'] or source['object_version'] != body['proposal_version']
                or source['recorded_sequence'] > row['recorded_sequence'] or source['case_version'] > row['case_version']):
            raise FlowError()
        saved = read_source(source)
        if 'content' in saved:
            _same(body, saved['content']['packet'], ('case_id', 'proposal_id', 'proposal_version', 'input_version', 'corpus_version'))
        # A source tombstone still proves retained identity; never reconstruct it.
