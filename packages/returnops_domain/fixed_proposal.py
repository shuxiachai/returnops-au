"""Fixed synthetic guidance only: no model, C1 retrieval, Risk or effects.

The complete source DTOs are kept separate from deliberately uncertain facts.
The synthetic text explicitly carries no legal or executable recommendation.
"""
from copy import deepcopy
from hashlib import sha256
from .audit import timestamp
from .errors import FlowError
from .founder_codec import validate
from .founder_history_types import proposal_bindings
from .proposal_policy import stable_id
from .wire import _validator

CORPUS = 'fixed-synthetic-guidance-v1'
CAPACITY_MESSAGE = 'Complete retained proposal input exceeds the supported capacity; manual handling is required.'
CONTENT = ('Synthetic integration guidance only. Preserve all customer material '
           'for independent review; this text establishes no entitlement, '
           'legal conclusion, approval or permission to execute an action.')


class ProposalCapacityError(Exception):
    def __init__(self):
        super().__init__('Complete retained proposal input exceeds the frozen DTO capacity.')


def build_fixed_proposal(material, work, proposal_version, now):
    at = timestamp(now)
    proposal_id = stable_id('proposal', work['work_id'])
    binding = dict(case_id=work['case_id'], input_version=work['input_version'], corpus_version=CORPUS)
    passage = dict(passage_id='fixed-synthetic-guidance', document_id='fixed-synthetic-document',
        source_type='STORE_POLICY', title='Synthetic integration guidance; no real policy assessment',
        source_uri='urn:returnops:synthetic:fixed-guidance:v1', accessed_on=at[:10],
        source_version='fixed-synthetic-v1', corpus_version=CORPUS, location='notice',
        content=CONTENT, content_sha256=sha256(CONTENT.encode('utf-8')).hexdigest(),
        retrieved_at=at, is_synthetic=True)
    citation = {name: passage[name] for name in (
        'passage_id', 'document_id', 'source_version', 'corpus_version', 'content_sha256', 'location')}
    citation['citation_id'] = 'fixed-synthetic-citation'
    matrix = [dict(criterion_id='fixed-independent-assessment', status='MISSING',
        statement_ids=[item['statement_id'] for item in material.statements],
        evidence_ids=[item['evidence_id'] for item in material.attachments],
        rationale='All retained material is preserved; its business meaning requires independent review.')]
    original = next(item for item in material.statements if item['statement_id'] == material.original_id)
    packet = dict(**binding, proposal_id=proposal_id, proposal_version=proposal_version,
        original_statement_id=material.original_id, created_at=at,
        facts=dict(issue_category='UNCLEAR', customer_requested_outcome=original['requested_outcome'],
            possible_basis='UNDETERMINED', assessment_status='UNCERTAIN', line_items=[],
            summary='Fixed synthetic integration output. No model assessed the retained customer material.'),
        evidence_matrix=matrix, recommended_action='REFER_FOR_MANUAL_HANDLING',
        rationale='Non-executable fixed guidance for independent review, not a customer remedy decision.',
        alternatives=[], conditions=['Independent review is required before any subsequent decision.'],
        cost_responsibility_note='No allocation of costs or legal responsibility is made.',
        citations=[citation], confidence=0,
        unresolved_questions=['The retained facts and applicable policy have not been independently assessed.'],
        model_run=dict(run_id=stable_id('run', work['work_id']), role='ASSESSMENT',
            provider_id='provider-fixture', model_id='fixture-no-live-model',
            prompt_version='fixed-synthetic-no-model-v1', started_at=at, finished_at=at,
            input_tokens=0, output_tokens=0))
    bundle = dict(packet=packet, statements=deepcopy(material.statements),
        attachments=deepcopy(material.attachments), evidence_matrix=deepcopy(matrix),
        order_lookup=deepcopy(material.order_lookup),
        retrieval_result=dict(**binding, status='MATCHED', passages=[passage], conflicts=[], retrieved_at=at),
        citation_verification=dict(**binding, proposal_id=proposal_id, proposal_version=proposal_version,
            checks=[dict(citation_id=citation['citation_id'], result='VALID',
                message='Exact synthetic text, identity, version, location and hash match; no policy assessment.')],
            checked_at=at))
    # Use the unchanged installed schema as the capacity oracle. Never retain a
    # jsonschema error (which contains customer instances) in exception context.
    errors = list(_validator('HistoricalProposalBundle').iter_errors(bundle))
    too_large = any(error.validator in {'maxItems', 'maxLength'} for error in errors)
    invalid = bool(errors)
    del errors
    if too_large:
        raise ProposalCapacityError()
    if invalid:
        raise FlowError('INVALID_STATE')
    result = validate('HistoricalProposalBundle', bundle)
    proposal_bindings(result)
    return result
