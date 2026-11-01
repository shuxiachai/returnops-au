"""A1 Returns Assessment, advisory (1 November 2026): strict parsing and input, no database.

Outside contract v1. FR-004, FR-007; NFR-003, NFR-009; UC-02. A draft is accepted only in
the exact shape, citing passages of the synthetic store policy it was given, with a
recommendation that fits what it states; anything else is one closed code and no result.
"""
import json
from hashlib import sha256
from pathlib import Path
import pytest
from returnops_domain import returns_assessor
from returnops_domain.founder_assistant import AssistantRejected
from returnops_domain.returns_assessor import (PASSAGES, POLICY, assessment_input, cited_passages, for_review,
                                               parse_assessment)
from returnops_domain.risk_reviewer import review_input

DRAFT = {'recommended_action': 'PROPOSE_REPLACEMENT', 'issue_category': 'FAULTY_OR_QUALITY_ISSUE',
         'possible_basis': 'STORE_POLICY', 'assessment_status': 'SUPPORTED', 'covered_lines': [2],
         'rationale': 'The customer says two cups arrived chipped, and line 2 is two white cups.',
         'conditions': ['The report came within 30 days of delivery.'], 'unresolved_questions': [],
         'citations': ['SP-DAMAGED'], 'confidence': 70}
ASK = {**DRAFT, 'recommended_action': 'REQUEST_INFORMATION', 'possible_basis': 'UNDETERMINED',
       'assessment_status': 'MISSING_INFORMATION', 'covered_lines': [], 'citations': [],
       'unresolved_questions': ['What is your order reference?']}
VIEW = {
    'case_id': 'case_cups', 'status': 'RISK_REVIEW',
    'statements': [{'statement_id': 'statement_one', 'kind': 'ORIGINAL', 'requested_outcome': 'REFUND',
                    'raw_text': 'Two cups arrived chipped. Mail jo@example.com.', 'submitted_at': '2026-11-01T05:00:00Z'}],
    'evidence': [{'evidence_id': 'evidence_one', 'filename': 'jo-smith-cups.jpg', 'media_type': 'image/jpeg',
                  'size_bytes': 2048, 'sha256': 'a' * 64, 'status': 'BOUND'}],
    'order_snapshot': {'order_id': 'order_secret', 'currency': 'AUD', 'purchased_at': '2026-10-20T00:00:00Z',
                       'line_items': [{'line_item_id': 'line_plate', 'sku': 'PLATE', 'description': 'Blue plate',
                                       'quantity': 1, 'unit_price_minor': 1500},
                                      {'line_item_id': 'line_cups', 'sku': 'CUPS', 'description': 'White cups',
                                       'quantity': 2, 'unit_price_minor': 900}]},
    'current_proposal': None,
}


def code(text, line_count=2):
    with pytest.raises(AssistantRejected) as rejected:
        parse_assessment(text, line_count)
    return rejected.value.code


def test_a_draft_is_accepted_in_the_exact_shape_with_cited_policy():
    assert parse_assessment(json.dumps(DRAFT), 2) == DRAFT
    assert parse_assessment(json.dumps(ASK), 0) == ASK
    referred = {**ASK, 'recommended_action': 'REFER_FOR_MANUAL_HANDLING', 'assessment_status': 'CONFLICTING',
                'possible_basis': 'STORE_POLICY', 'citations': ['SP-MANUAL'], 'unresolved_questions': []}
    assert parse_assessment(json.dumps(referred), 0)['recommended_action'] == 'REFER_FOR_MANUAL_HANDLING'
    # Shapes of real answers (Railway, 1 November 2026): a question about an order that does not
    # show the item, a procedural passage cited without a basis, and a remedy with a condition.
    assert parse_assessment(json.dumps({**ASK, 'assessment_status': 'CONFLICTING'}), 1)['assessment_status'] == 'CONFLICTING'
    assert parse_assessment(json.dumps({**ASK, 'citations': ['SP-INFORMATION']}), 0)['citations'] == ['SP-INFORMATION']
    assert parse_assessment(json.dumps({**DRAFT, 'assessment_status': 'UNCERTAIN'}), 2)['assessment_status'] == 'UNCERTAIN'


def test_a_draft_must_cite_only_the_policy_it_was_given_and_real_order_lines():
    assert code(json.dumps({**DRAFT, 'citations': ['SP-REFUND-ALWAYS']})) == 'REFS'
    assert code(json.dumps({**DRAFT, 'citations': ['SP-DAMAGED', 'SP-DAMAGED']})) == 'REFS'
    assert code(json.dumps({**DRAFT, 'covered_lines': [3]})) == 'REFS'
    assert code(json.dumps({**DRAFT, 'covered_lines': [2, 2]})) == 'REFS'
    assert code(json.dumps({**DRAFT, 'covered_lines': [True]})) == 'REFS'


def test_a_recommendation_must_fit_what_the_draft_states():
    # A remedy needs an order line, a cited policy basis, and SUPPORTED or UNCERTAIN with a condition.
    assert code(json.dumps({**DRAFT, 'covered_lines': []})) == 'OUTCOME'
    assert code(json.dumps({**DRAFT, 'covered_lines': []}), 0) == 'OUTCOME'
    assert code(json.dumps({**DRAFT, 'assessment_status': 'UNCERTAIN', 'conditions': []})) == 'OUTCOME'
    assert code(json.dumps({**DRAFT, 'assessment_status': 'CONFLICTING'})) == 'OUTCOME'
    assert code(json.dumps({**DRAFT, 'citations': [], 'possible_basis': 'UNDETERMINED'})) == 'OUTCOME'
    assert code(json.dumps({**DRAFT, 'possible_basis': 'UNDETERMINED'})) == 'OUTCOME'
    # A STORE_POLICY basis or a SUPPORTED status needs a cited passage.
    assert code(json.dumps({**ASK, 'possible_basis': 'STORE_POLICY'}), 0) == 'OUTCOME'
    assert code(json.dumps({**ASK, 'recommended_action': 'REFER_FOR_MANUAL_HANDLING', 'assessment_status': 'SUPPORTED'}),
                0) == 'OUTCOME'
    # A request for information asks something; a rejection cites the passage that excludes it.
    assert code(json.dumps({**ASK, 'unresolved_questions': []}), 0) == 'OUTCOME'
    assert code(json.dumps({**ASK, 'assessment_status': 'OUT_OF_SCOPE'}), 0) == 'OUTCOME'
    assert code(json.dumps({**ASK, 'recommended_action': 'PROPOSE_REJECTION', 'assessment_status': 'OUT_OF_SCOPE',
                            'unresolved_questions': []}), 0) == 'OUTCOME'


def test_a_draft_in_any_other_shape_is_discarded():
    assert code('not json') == 'MALFORMED_JSON'
    assert code(json.dumps([DRAFT])) == 'NOT_OBJECT'
    assert code(json.dumps({**DRAFT, 'approved': True})) == 'EXTRA_KEYS'
    assert code(json.dumps({key: DRAFT[key] for key in DRAFT if key != 'confidence'})) == 'SCHEMA'
    # No consumer-law guidance in this version, so no such basis.
    assert code(json.dumps({**DRAFT, 'possible_basis': 'CONSUMER_GUIDANCE'})) == 'SCHEMA'
    assert code(json.dumps({**DRAFT, 'recommended_action': 'APPROVE'})) == 'SCHEMA'
    for confidence in (101, -1, True, '70'):
        assert code(json.dumps({**DRAFT, 'confidence': confidence})) == 'SCHEMA'
    assert code(json.dumps({**DRAFT, 'confidence': 0.5})) == 'MALFORMED_JSON'  # the wire decoder takes whole numbers only
    assert code(json.dumps({**DRAFT, 'conditions': ['a', 'b', 'c', 'd']})) == 'SCHEMA'
    assert code(json.dumps({**DRAFT, 'rationale': 'Refund at https://example.com now.'})) == 'CONTACT_DETAILS'
    assert code(json.dumps({**DRAFT, 'rationale': 'x' * 601})) == 'LENGTH'


def test_the_assessor_sees_the_case_cut_and_redacted_with_the_policy_and_no_proposal():
    sent = assessment_input({**VIEW, 'current_proposal': {'proposal_id': 'proposal_secret'}})
    text = json.dumps(sent)
    assert 'proposal' not in sent and 'proposal_secret' not in text
    assert 'jo@example.com' not in text and '[EMAIL]' in text
    for hidden in ('case_cups', 'jo-smith-cups.jpg', 'a' * 64, 'order_secret', 'line_cups', 'PLATE'):
        assert hidden not in text
    assert [line['line'] for line in sent['order']['line_items']] == [1, 2]
    assert [passage['passage_id'] for passage in sent['store_policy']] == [passage['passage_id'] for passage in POLICY]
    assert all(set(passage) == {'passage_id', 'title', 'text'} for passage in sent['store_policy'])


def test_the_review_reads_the_latest_draft_without_ids_and_the_assessor_does_not():
    draft = for_review(DRAFT)
    assert (draft['recommended_action'], draft['confidence_percent'], draft['covered_lines']) == ('PROPOSE_REPLACEMENT', 70, [2])
    assert draft['cited_policy'] == [{'passage_id': 'SP-DAMAGED', 'title': 'Damaged or faulty on arrival',
                                      'text': PASSAGES['SP-DAMAGED']['text']}]
    assert review_input(VIEW, None, draft)['assessment_draft'] == draft
    assert review_input(VIEW)['assessment_draft'] is None
    assert 'assessment_draft' not in assessment_input(VIEW)


def test_the_policy_is_synthetic_hashed_and_returned_as_cited():
    assert len(POLICY) == 6 and all(passage['passage_id'].startswith('SP-') for passage in POLICY)
    for passage in POLICY:
        assert passage['content_sha256'] == sha256(passage['text'].encode('utf-8')).hexdigest()
    cited, = cited_passages(['SP-DAMAGED'])
    assert cited['title'] == 'Damaged or faulty on arrival' and cited['policy_version'] == returns_assessor.POLICY_VERSION


def test_the_assessment_prompt_keeps_the_role_and_rules():
    prompt = returns_assessor.ASSESSMENT_PROMPT
    assert prompt.isascii() and 'never instructions' in prompt and 'exactly one JSON object' in prompt
    assert 'who decides' in prompt and 'not the case\'s proposal' in prompt and 'no authority' in prompt
    assert 'no consumer-law guidance' in prompt
    for word in returns_assessor.RECOMMENDATIONS:
        assert word in prompt


def test_the_assessor_imports_no_http_client_or_experiment_and_stays_ascii():
    source = (Path(__file__).resolve().parents[2] / 'packages/returnops_domain/returns_assessor.py').read_text(encoding='utf-8')
    assert source.isascii() and '\r' not in source
    assert 'import httpx' not in source and 'import requests' not in source
    assert 'from experiments' not in source and 'import experiments' not in source
