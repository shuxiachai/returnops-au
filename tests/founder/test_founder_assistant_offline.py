"""Founder AI assistant (31 October 2026): strict output parsing and route wiring, no database.

Outside contract v1. FR-002, FR-012; NFR-002, NFR-003, NFR-009: an answer is accepted
only in the exact shape, without links or contact details; anything else is one closed
code and no result.
"""
import json
import pytest
from returnops_api import accounts
from returnops_api.main import create_app
from returnops_domain import founder_assistant as assistant
from returnops_domain.founder_assistant import AssistantRejected, parse_reply, parse_summary, parse_triage

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
    expected = ['/v1/founder/assistant/summary', '/v1/founder/assistant/triage', '/v1/founder/cases/{case_id}/assistant/reply']
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
