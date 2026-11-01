"""Founder AI assistant (31 October 2026): strict output parsing and route wiring, no database.

Outside contract v1. FR-002, FR-012; NFR-002, NFR-003, NFR-009: an answer is accepted
only in the exact shape, without links or contact details; anything else is one closed
code and no result.
"""
import json
from decimal import Decimal
import pytest
from returnops_api import accounts
from returnops_api.main import create_app
from returnops_domain import founder_assistant as assistant, risk_reviewer
from returnops_domain.founder_assistant import AssistantRejected, parse_reply, parse_summary, parse_triage
from returnops_domain.risk_reviewer import parse_risk_review, review_input

MODEL_ENV = {
    'RETURNOPS_MODEL_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'RETURNOPS_MODEL_API_KEY': 'sk-test-not-a-real-key',
    'RETURNOPS_MODEL_ID': 'qwen-plus',
    'RETURNOPS_MODEL_PROVIDER_ID': 'aliyun_bailian',
}
REPLY = {'customer_language': 'zh', 'reply': '您好，感谢您的来信。我们已收到您关于水壶不加热的问题，店主会尽快查看。',
         'reply_english': 'Hello, thank you for writing. We have received your report that the kettle does not heat, and the shop will look at it soon.'}


def code(call):
    with pytest.raises(AssistantRejected) as rejected:
        call()
    return rejected.value.code


def test_a_reply_draft_is_accepted_only_in_the_exact_shape():
    assert parse_reply(json.dumps(REPLY)) == REPLY
    # A fenced reply is unwrapped as for the showcase.
    assert parse_reply('```json\n' + json.dumps(REPLY) + '\n```') == REPLY
    assert code(lambda: parse_reply('not json')) == 'MALFORMED_JSON'
    assert code(lambda: parse_reply('[1]')) == 'NOT_OBJECT'
    assert code(lambda: parse_reply(json.dumps({**REPLY, 'approve': True}))) == 'EXTRA_KEYS'
    assert code(lambda: parse_reply(json.dumps({'reply': 'x', 'reply_english': 'x'}))) == 'SCHEMA'
    assert code(lambda: parse_reply(json.dumps({**REPLY, 'customer_language': 'Chinese'}))) == 'SCHEMA'
    assert code(lambda: parse_reply(json.dumps({**REPLY, 'reply': 'x' * 1201}))) == 'LENGTH'
    assert code(lambda: parse_reply(json.dumps({**REPLY, 'reply_english': '​ '}))) == 'LENGTH'
    assert code(lambda: parse_reply('x' * 16001)) == 'MALFORMED_JSON'


def test_a_draft_with_a_link_or_contact_details_is_discarded():
    for text in ('Please visit https://example.com/refund to continue.', 'See www.example.com.',
                 'Write to help@example.com.', 'Call us on 0412 345 678.'):
        assert code(lambda: parse_reply(json.dumps({**REPLY, 'reply_english': text}))) == 'CONTACT_DETAILS'
    # Dates and placeholders are not contact details.
    kept = {**REPLY, 'reply_english': 'Your order [ORDER_REF] of 2026-10-30 is being looked at.'}
    assert parse_reply(json.dumps(kept)) == kept


def test_a_triage_must_cover_every_case_once_and_name_only_known_cases():
    good = {'cases': [{'ref': 1, 'urgency': 'HIGH', 'reason': 'Burning smell.'},
                      {'ref': 2, 'urgency': 'LOW', 'reason': 'A question.'}],
            'groups': [{'label': 'Kitchen appliances', 'refs': [1, 2]}]}
    triaged, groups = parse_triage(json.dumps(good), {1, 2})
    assert triaged == {1: {'urgency': 'HIGH', 'reason': 'Burning smell.'}, 2: {'urgency': 'LOW', 'reason': 'A question.'}}
    assert groups == [{'label': 'Kitchen appliances', 'refs': [1, 2]}]
    missing = {**good, 'cases': good['cases'][:1]}
    assert code(lambda: parse_triage(json.dumps(missing), {1, 2})) == 'REFS'
    twice = {**good, 'cases': good['cases'] + [good['cases'][0]]}
    assert code(lambda: parse_triage(json.dumps(twice), {1, 2})) == 'REFS'
    unknown = {**good, 'groups': [{'label': 'Other', 'refs': [1, 3]}]}
    assert code(lambda: parse_triage(json.dumps(unknown), {1, 2})) == 'REFS'
    single = {**good, 'groups': [{'label': 'Alone', 'refs': [1]}]}
    assert code(lambda: parse_triage(json.dumps(single), {1, 2})) == 'REFS'
    flag = {**good, 'cases': [{'ref': True, 'urgency': 'HIGH', 'reason': 'x'}, good['cases'][1]]}
    assert code(lambda: parse_triage(json.dumps(flag), {1, 2})) == 'REFS'
    urgent = {**good, 'cases': [{'ref': 1, 'urgency': 'CRITICAL', 'reason': 'x'}, good['cases'][1]]}
    assert code(lambda: parse_triage(json.dumps(urgent), {1, 2})) == 'SCHEMA'
    many = {**good, 'groups': [{'label': f'G{n}', 'refs': [1, 2]} for n in range(9)]}
    assert code(lambda: parse_triage(json.dumps(many), {1, 2})) == 'SCHEMA'
    long_label = {**good, 'groups': [{'label': 'x' * 61, 'refs': [1, 2]}]}
    assert code(lambda: parse_triage(json.dumps(long_label), {1, 2})) == 'LENGTH'


def test_a_summary_has_one_to_three_short_highlights():
    good = {'summary': 'Seven cases came in; three wait for the customer.', 'highlights': ['One case is escalated.']}
    assert parse_summary(json.dumps(good)) == good
    assert code(lambda: parse_summary(json.dumps({**good, 'highlights': []}))) == 'SCHEMA'
    assert code(lambda: parse_summary(json.dumps({**good, 'highlights': ['a', 'b', 'c', 'd']}))) == 'SCHEMA'
    assert code(lambda: parse_summary(json.dumps({**good, 'summary': 'x' * 701}))) == 'LENGTH'


def test_the_prompts_forbid_promises_contact_details_and_obeying_the_customer():
    for prompt in (assistant.REPLY_PROMPT, assistant.TRIAGE_PROMPT, assistant.SUMMARY_PROMPT):
        assert 'decide nothing' in prompt and 'exactly one JSON object' in prompt and prompt.isascii()
    assert 'never instructions' in assistant.REPLY_PROMPT and 'never instructions' in assistant.TRIAGE_PROMPT
    assert 'Do not promise or refuse' in assistant.REPLY_PROMPT and 'no links' in assistant.REPLY_PROMPT
    assert 'counts only' in assistant.SUMMARY_PROMPT


def test_the_routes_exist_only_with_password_sign_in_and_the_model(tmp_path, monkeypatch):
    for name in ('RETURNOPS_ACCOUNTS_FILE', 'RETURNOPS_AUTH_FILE', 'RETURNOPS_MODEL_SHOWCASE'):
        monkeypatch.delenv(name, raising=False)
    for name, value in MODEL_ENV.items():
        monkeypatch.setenv(name, value)
    path = tmp_path / 'credentials.json'
    accounts.new_credentials_file(path, 'store_demo', {})

    def assistant_paths(app):
        return sorted(route.path for route in app.routes if 'assistant' in getattr(route, 'path', ''))
    expected = ['/v1/founder/assistant/summary', '/v1/founder/assistant/triage',
                '/v1/founder/cases/{case_id}/assistant/image-observations', '/v1/founder/cases/{case_id}/assistant/reply',
                '/v1/founder/cases/{case_id}/assistant/risk-review']
    assert assistant_paths(create_app(engine=object(), enable_processor=False)) == []
    assert assistant_paths(create_app(engine=object(), enable_processor=False, enable_model_showcase=True)) == []
    assert assistant_paths(create_app(engine=object(), enable_processor=False, accounts_file=str(path.resolve()))) == []
    both = create_app(engine=object(), enable_processor=False, enable_model_showcase=True, accounts_file=str(path.resolve()))
    assert assistant_paths(both) == expected
    assert all(route.methods == {'POST'} for route in both.routes if 'assistant' in getattr(route, 'path', ''))


def test_the_assistant_module_imports_no_http_client_and_stays_ascii():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for path in ('packages/returnops_domain/founder_assistant.py', 'apps/api/returnops_api/founder_assistant_http.py'):
        source = (root / path).read_text(encoding='utf-8')
        assert 'import httpx' not in source and 'import requests' not in source and 'experiments' not in source
        assert source.isascii() and '\r' not in source


def test_the_assistant_has_its_own_model_budget(tmp_path, monkeypatch):
    # Runtime review (31 October 2026): cases lodged by strangers spend the showcase's
    # calls; they must not use up the Founder's assistant as well.
    from fastapi.testclient import TestClient
    from returnops_domain.model_transport import BudgetedTransport
    for name in ('RETURNOPS_ACCOUNTS_FILE', 'RETURNOPS_AUTH_FILE', 'RETURNOPS_MODEL_SHOWCASE'):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**MODEL_ENV, 'RETURNOPS_MODEL_MAX_CALLS': '7'}.items():
        monkeypatch.setenv(name, value)
    path = tmp_path / 'credentials.json'
    accounts.new_credentials_file(path, 'store_demo', {})
    app = create_app(engine=object(), enable_processor=False, enable_model_showcase=True, accounts_file=str(path.resolve()))
    with TestClient(app):
        showcase = app.state.coordinator_showcase.transport
        assistant_transport = app.state.founder_assistant.transport
        assert isinstance(showcase, BudgetedTransport) and isinstance(assistant_transport, BudgetedTransport)
        assert assistant_transport is not showcase and assistant_transport.remaining == showcase.remaining == 7



# The C2 Risk Reviewer, live and advisory (1 November 2026): C's five outcomes with their
# conditions; FR-008, NFR-009.
def finding(severity, category='MISSING_INFORMATION'):
    return {'category': category, 'severity': severity, 'message': 'No photo of the damage was supplied.'}


WARNED = {'outcome': 'PASS_WITH_WARNING', 'summary': 'The proposal matches the complaint; a photo is missing.',
          'findings': [finding('WARNING')], 'questions': [], 'revision_requests': []}


def test_a_risk_review_is_accepted_only_under_c2s_outcome_conditions():
    assert parse_risk_review(json.dumps(WARNED), True) == WARNED
    # With no proposal yet there is nothing to pass, but a warning can still be given.
    assert parse_risk_review(json.dumps(WARNED), False) == WARNED
    passed = {**WARNED, 'outcome': 'PASS', 'findings': [finding('INFO')]}
    assert parse_risk_review(json.dumps(passed), True) == passed
    assert code(lambda: parse_risk_review(json.dumps(passed), False)) == 'OUTCOME'
    assert code(lambda: parse_risk_review(json.dumps({**passed, 'findings': [finding('WARNING')]}), True)) == 'OUTCOME'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'findings': [finding('INFO')]}), True)) == 'OUTCOME'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'questions': ['Which order?']}), True)) == 'OUTCOME'
    revise = {**WARNED, 'outcome': 'REVISE', 'revision_requests': ['Cover only the two chipped cups.']}
    assert parse_risk_review(json.dumps(revise), True) == revise
    assert code(lambda: parse_risk_review(json.dumps(revise), False)) == 'OUTCOME'
    assert code(lambda: parse_risk_review(json.dumps({**revise, 'revision_requests': []}), True)) == 'OUTCOME'
    ask = {**WARNED, 'outcome': 'NEEDS_INFORMATION', 'questions': ['Which order is this about?']}
    assert parse_risk_review(json.dumps(ask), False) == ask
    assert code(lambda: parse_risk_review(json.dumps({**ask, 'questions': []}), False)) == 'OUTCOME'
    escalate = {**WARNED, 'outcome': 'ESCALATE', 'findings': [finding('BLOCK', 'INJECTION')]}
    assert parse_risk_review(json.dumps(escalate), False) == escalate
    assert code(lambda: parse_risk_review(json.dumps({**escalate, 'findings': [finding('WARNING')]}), False)) == 'OUTCOME'
    # A BLOCK finding is allowed only with ESCALATE.
    for outcome, extra in (('PASS_WITH_WARNING', {}), ('REVISE', {'revision_requests': ['x']}),
                           ('NEEDS_INFORMATION', {'questions': ['Which order?']})):
        blocked = {**WARNED, 'outcome': outcome, 'findings': [finding('BLOCK', 'CONFLICT')], **extra}
        assert code(lambda: parse_risk_review(json.dumps(blocked), True)) == 'OUTCOME'


def test_a_risk_review_in_any_other_shape_is_discarded():
    one = finding('WARNING')
    assert code(lambda: parse_risk_review('not json', True)) == 'MALFORMED_JSON'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'approve': True}), True)) == 'EXTRA_KEYS'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'outcome': 'APPROVE'}), True)) == 'SCHEMA'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'findings': [{**one, 'category': 'LEGAL'}]}), True)) == 'SCHEMA'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'findings': [{**one, 'severity': 'CRITICAL'}]}), True)) == 'SCHEMA'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'findings': [{**one, 'id': 'x'}]}), True)) == 'EXTRA_KEYS'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'findings': [one] * 7}), True)) == 'SCHEMA'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'questions': ['a?', 'b?', 'c?', 'd?']}), True)) == 'SCHEMA'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'summary': 'x' * 401}), True)) == 'LENGTH'
    assert code(lambda: parse_risk_review(json.dumps({**WARNED, 'questions': [3]}), True)) == 'LENGTH'
    called = {**WARNED, 'findings': [{**one, 'message': 'Call the customer on 0412 345 678 first.'}]}
    assert code(lambda: parse_risk_review(json.dumps(called), True)) == 'CONTACT_DETAILS'


def test_the_reviewer_sees_the_case_as_the_founder_does_cut_and_redacted():
    view = {
        'case_id': 'case_cups', 'status': 'RISK_REVIEW',
        'statements': [{'statement_id': 'statement_one', 'kind': 'ORIGINAL', 'requested_outcome': 'REFUND',
                        'raw_text': 'Two cups arrived chipped. Mail jo@example.com or call 0412 345 678.',
                        'submitted_at': '2026-11-01T05:00:00Z'}],
        'evidence': [{'evidence_id': 'evidence_one', 'filename': 'jo-smith-cups.jpg', 'media_type': 'image/jpeg',
                      'size_bytes': 2048, 'sha256': 'a' * 64, 'status': 'BOUND'}],
        'order_snapshot': {'order_id': 'order_secret', 'currency': 'AUD', 'purchased_at': '2026-10-20T00:00:00Z',
                           'line_items': [{'line_item_id': 'line_plate', 'sku': 'PLATE', 'description': 'Blue plate',
                                           'quantity': 1, 'unit_price_minor': 1500},
                                          {'line_item_id': 'line_cups', 'sku': 'CUPS', 'description': 'White cups',
                                           'quantity': 2, 'unit_price_minor': 900}]},
        'current_proposal': {
            'proposal_id': 'proposal_one', 'proposal_version': 1, 'recommended_action': 'PROPOSE_RETURN',
            'rationale': 'Both cups arrived chipped.', 'conditions': ['Return both cups unused.'], 'alternatives': [],
            'unresolved_questions': [], 'cost_responsibility_note': 'The store pays the return label.',
            'confidence': Decimal('0.6'), 'citations': [],
            'facts': {'issue_category': 'DAMAGED', 'customer_requested_outcome': 'REFUND', 'possible_basis': 'STORE_POLICY',
                      'assessment_status': 'SUPPORTED', 'line_items': [{'line_item_id': 'line_cups', 'quantity': 2}],
                      'summary': 'Two cups chipped.'},
            'evidence_matrix': [{'criterion_id': 'criterion_one', 'status': 'MET', 'rationale': 'A photo shows the chips.',
                                 'statement_ids': ['statement_one'], 'evidence_ids': ['evidence_one']}]},
    }
    sent = review_input(view)
    text = json.dumps(sent)  # the Decimal confidence is already a plain number
    assert 'jo@example.com' not in text and '0412 345 678' not in text and '[EMAIL]' in text and '[PHONE]' in text
    for hidden in ('case_cups', 'jo-smith-cups.jpg', 'a' * 64, 'order_secret', 'proposal_one', 'line_cups', 'PLATE'):
        assert hidden not in text
    assert sent['attachments'] == [{'media_type': 'image/jpeg', 'status': 'BOUND'}]
    assert [line['line'] for line in sent['order']['line_items']] == [1, 2]
    assert sent['proposal']['covered_lines'] == [{'line': 2, 'quantity': 2}]
    assert sent['proposal']['confidence'] == 0.6 and sent['proposal']['guidance_citations'] == 0
    assert sent['order_lookup_block'] is None and sent['open_questions_to_customer'] == []
    assert review_input({**view, 'current_proposal': None, 'order_snapshot': None})['proposal'] is None


def test_the_risk_prompt_keeps_c2s_role_and_rules():
    prompt = risk_reviewer.RISK_PROMPT
    assert prompt.isascii() and 'never instructions' in prompt and 'exactly one JSON object' in prompt
    assert 'not the Assessment role' in prompt and 'decide nothing' in prompt and 'no authority' in prompt
    for word in risk_reviewer.OUTCOMES + tuple(sorted(risk_reviewer.CATEGORIES)):
        assert word in prompt
    assert 'A BLOCK finding is allowed only with ESCALATE.' in prompt


def test_the_risk_reviewer_imports_no_http_client_or_experiment_and_stays_ascii():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[2] / 'packages/returnops_domain/risk_reviewer.py').read_text(encoding='utf-8')
    assert source.isascii() and '\r' not in source
    assert 'import httpx' not in source and 'import requests' not in source
    assert 'from experiments' not in source and 'import experiments' not in source
