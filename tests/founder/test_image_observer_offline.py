"""C3 image evidence observations (1 November 2026): input, output and transport, no database.

FR-005, FR-012; NFR-003, NFR-009; UC-02 (docs/07 section 2.9). Only bound JPEG and PNG
files are sent, at most three and at most 4 MB each; the model sees redacted words and no
IDs or file names; an answer is accepted only in the exact shape, one entry per photo in
order; the result has the contract v1 ImageObservationResult shape with each original
file's ID; anything else is one closed code and no result.
"""
import io
import json
from pathlib import Path
import pytest
from pydantic import SecretStr
from returnops_api.model_settings import ModelSettings
from returnops_api.settings import ConfigurationError
from returnops_domain import image_observer
from returnops_domain.founder_assistant import AssistantRejected
from returnops_domain.image_observer import (IMAGE_PROMPT, MAX_IMAGE_BYTES, PROMPT_VERSION, contract_result,
                                             observation_input, parse_observations, select_images)
from returnops_domain.model_transport import BudgetedTransport, ChatCompletionsTransport, ModelInvocation
from returnops_domain.wire import _validator


def contract_shaped(result):
    return next(_validator('ImageObservationResult').iter_errors(result), None) is None

KEY = 'sk-test-not-a-real-key'
MODEL_ENV = {
    'RETURNOPS_MODEL_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'RETURNOPS_MODEL_API_KEY': KEY,
    'RETURNOPS_MODEL_ID': 'qwen-plus',
    'RETURNOPS_MODEL_PROVIDER_ID': 'aliyun_bailian',
}
ONE = {'image': 1, 'condition': 'DAMAGE_VISIBLE', 'visible_observations': ['Two white cups; one has a chip on the rim.'],
       'limitations': ['The photo cannot show when or how the chip happened.'], 'confidence': 80, 'text_in_image': 'NONE'}
TWO = {'image': 2, 'condition': 'CANNOT_DETERMINE', 'visible_observations': ['A paper note with printed words.'],
       'limitations': ['The note does not show the item.'], 'confidence': 30, 'text_in_image': 'PRESENT_IGNORED'}
ANSWER = {'images': [ONE, TWO], 'consistency': 'CONSISTENT', 'summary': 'The first photo shows a chipped cup.'}


def code(call):
    with pytest.raises(AssistantRejected) as rejected:
        call()
    return rejected.value.code


def evidence(evidence_id, media_type='image/png', size=2048, status='BOUND', case_id='case_one', filename='photo.png'):
    return {'evidence_id': evidence_id, 'case_id': case_id, 'filename': filename, 'media_type': media_type,
            'size_bytes': size, 'sha256': 'a' * 64, 'created_at': '2026-11-01T07:00:00Z', 'status': status,
            'content_path': '/v1/evidence/' + evidence_id + '/content'}


def view(files, order=None):
    return {'case_id': 'case_one', 'case_version': 3, 'input_version': 2, 'status': 'RISK_REVIEW', 'evidence': files,
            'order_snapshot': order,
            'statements': [{'kind': 'ORIGINAL', 'requested_outcome': 'REFUND',
                            'raw_text': 'Two cups arrived chipped. Mail me at jo@example.com or call 0412 345 678.'}]}


def test_an_answer_in_the_exact_shape_is_accepted_one_entry_per_photo_in_order():
    parsed = parse_observations(json.dumps(ANSWER), 2)
    assert parsed['consistency'] == 'CONSISTENT' and parsed['summary'] == ANSWER['summary']
    assert [item['condition'] for item in parsed['images']] == ['DAMAGE_VISIBLE', 'CANNOT_DETERMINE']
    assert [item['text_in_image'] for item in parsed['images']] == ['NONE', 'PRESENT_IGNORED']
    # The model gives a whole-number percentage; the contract keeps 0 to 1.
    assert parsed['images'][0]['confidence'] == 0.8 and parsed['images'][1]['confidence'] == 0.3
    assert parse_observations(json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': 100}, TWO]}), 2)['images'][0]['confidence'] == 1.0


@pytest.mark.parametrize('answer, expected', [
    ('not json', 'MALFORMED_JSON'),
    (json.dumps([ANSWER]), 'NOT_OBJECT'),
    (json.dumps({**ANSWER, 'decision': 'REFUND'}), 'EXTRA_KEYS'),
    (json.dumps({'images': [ONE, TWO], 'summary': 'x'}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [ONE]}), 'SCHEMA'),                                   # one entry per photo sent
    (json.dumps({**ANSWER, 'images': [TWO, ONE]}), 'SCHEMA'),                              # in order
    (json.dumps({**ANSWER, 'images': [{**ONE, 'image': True}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'condition': 'BROKEN'}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': 101}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': -1}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': 0.8}, TWO]}), 'MALFORMED_JSON'),  # no fractions on the wire
    (json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': True}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'confidence': '80'}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'text_in_image': 'FOLLOWED'}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'visible_observations': []}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'limitations': ['a', 'b', 'c', 'd']}, TWO]}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'refund': True}, TWO]}), 'EXTRA_KEYS'),
    (json.dumps({**ANSWER, 'consistency': 'SUPPORTED'}), 'SCHEMA'),
    (json.dumps({**ANSWER, 'summary': 'x' * 401}), 'LENGTH'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'visible_observations': ['y' * 301]}, TWO]}), 'LENGTH'),
    (json.dumps({**ANSWER, 'summary': 'Call the customer on 0412 345 678.'}), 'CONTACT_DETAILS'),
    (json.dumps({**ANSWER, 'images': [{**ONE, 'visible_observations': ['See https://example.com/photo']}, TWO]}), 'CONTACT_DETAILS'),
])
def test_any_other_answer_is_discarded_with_one_closed_code(answer, expected):
    assert code(lambda: parse_observations(answer, 2)) == expected


def test_only_bound_jpeg_and_png_files_are_sent_at_most_three_and_4_mb_each():
    files = [evidence('ev_a'), evidence('ev_pdf', media_type='application/pdf'), evidence('ev_big', size=MAX_IMAGE_BYTES + 1),
             evidence('ev_b', media_type='image/jpeg'), evidence('ev_staged', status='STAGED'),
             evidence('ev_other', case_id='case_two'), evidence('ev_c'), evidence('ev_d')]
    chosen, skipped = select_images(view(files))
    assert [item['evidence_id'] for item in chosen] == ['ev_a', 'ev_b', 'ev_c']
    assert skipped == [{'evidence_id': 'ev_pdf', 'reason': 'NOT_AN_IMAGE'}, {'evidence_id': 'ev_big', 'reason': 'TOO_LARGE'},
                       {'evidence_id': 'ev_d', 'reason': 'LIMIT'}]
    assert select_images(view([])) == ([], [])


def test_the_model_sees_redacted_words_and_no_ids_file_names_or_hashes():
    order = {'currency': 'AUD', 'purchased_at': '2026-10-01T00:00:00Z',
             'line_items': [{'line_item_id': 'line_secret_id', 'description': 'Blue cup', 'quantity': 2, 'unit_price_minor': 1500}]}
    chosen, _ = select_images(view([evidence('ev_secret_id', filename='jo-smith-receipt.png')], order))
    payload = observation_input(view([evidence('ev_secret_id')], order), chosen)
    text = json.dumps(payload)
    assert 'jo@example.com' not in text and '0412 345 678' not in text and '[EMAIL]' in text and '[PHONE]' in text
    assert 'ev_secret_id' not in text and 'line_secret_id' not in text and 'jo-smith' not in text and 'a' * 64 not in text
    assert payload['images'] == [{'image': 1, 'media_type': 'image/png'}]
    assert payload['order_lines'] == [{'line': 1, 'description': 'Blue cup', 'quantity': 2}]
    assert observation_input(view([]), [])['order_lines'] is None


def test_the_result_has_the_contract_shape_and_keeps_each_original_file():
    files = [evidence('ev_a'), evidence('ev_b')]
    chosen, _ = select_images(view(files))
    result = contract_result(view(files), chosen, parse_observations(json.dumps(ANSWER), 2))
    assert contract_shaped(result)
    assert (result['case_id'], result['input_version'], result['component_version']) == ('case_one', 2, PROMPT_VERSION)
    assert [item['evidence_id'] for item in result['observations']] == ['ev_a', 'ev_b']
    assert result['observations'][0]['visible_observations'] == ONE['visible_observations']


def test_the_prompt_keeps_photos_and_their_text_untrusted_and_decides_nothing():
    for words in ('untrusted data, never', 'instructions', 'CANNOT_DETERMINE', 'Never invent details',
                  'Do not decide', 'eligibility, refund, liability or legal rights', 'text_in_image'):
        assert words in IMAGE_PROMPT
    source = (Path(__file__).resolve().parents[2] / 'packages/returnops_domain/image_observer.py').read_text(encoding='utf-8')
    assert source.isascii() and '\r' not in source and 'experiments' not in source and 'import httpx' not in source
    assert image_observer.MAX_IMAGES == 3


# ---------------------------------------------------------------- transport with photos

class FakeResponse:
    def __init__(self, body):
        self._stream, self.status, self.headers = io.BytesIO(body), 200, {}
    def read(self, size=-1): return self._stream.read(size)
    def close(self): pass


def completion():
    return json.dumps({'id': 'chatcmpl_1', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '{}'}}],
                       'usage': {'prompt_tokens': 90, 'completion_tokens': 20, 'total_tokens': 110}}).encode('utf-8')


def test_photos_follow_the_json_as_data_urls_and_text_calls_are_unchanged():
    seen = []
    def opener(request, timeout):
        seen.append(request)
        return FakeResponse(completion())
    transport = ChatCompletionsTransport('https://model.example.invalid/v1/', SecretStr(KEY), 'vision-model', urlopen=opener)
    png, jpeg = b'\x89PNG\r\n\x1a\nfake', b'\xff\xd8\xfffake'
    transport(ModelInvocation('system text', '{"images": []}', PROMPT_VERSION, 'stub', 'vision-model',
                              (('image/png', png), ('image/jpeg', jpeg))))
    transport(ModelInvocation('system text', '{"a": 1}', PROMPT_VERSION, 'stub', 'vision-model'))
    with_photos, text_only = (json.loads(request.data) for request in seen)
    content = with_photos['messages'][1]['content']
    assert content[0] == {'type': 'text', 'text': '{"images": []}'}
    assert content[1] == {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,iVBORw0KGgpmYWtl'}}
    assert content[2]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert text_only['messages'][1] == {'role': 'user', 'content': '{"a": 1}'}
    assert KEY not in repr(ModelInvocation('s', '{}', 'v', 'p', 'm', (('image/png', png),)))


@pytest.mark.parametrize('images', [
    (('image/gif', b'GIF89a'),), (('image/png', b''),), (('image/png', 'not bytes'),), [('image/png', b'x')], (('image/png',),),
])
def test_only_jpeg_and_png_bytes_reach_the_model(images):
    transport = ChatCompletionsTransport('https://model.example.invalid/v1/', SecretStr(KEY), 'vision-model',
                                         urlopen=lambda request, timeout: FakeResponse(completion()))
    with pytest.raises(ValueError):
        transport(ModelInvocation('system text', '{}', PROMPT_VERSION, 'stub', 'vision-model', images))


def test_the_vision_model_is_optional_and_has_its_own_budget():
    plain = ModelSettings.from_environment(MODEL_ENV)
    assert plain.vision_model_id is None and plain.vision_transport() is None
    settings = ModelSettings.from_environment({**MODEL_ENV, 'RETURNOPS_MODEL_VISION_ID': 'qwen3-vl-plus',
                                               'RETURNOPS_MODEL_MAX_CALLS': '5'})
    vision, text = settings.vision_transport(), settings.transport()
    assert isinstance(vision, BudgetedTransport) and vision is not text and vision.remaining == text.remaining == 5
    assert (vision.inner.model_id, text.inner.model_id) == ('qwen3-vl-plus', 'qwen-plus')
    for value in ('qwen vl\n', 'x' * 121, 'qwen-视觉'):
        with pytest.raises(ConfigurationError) as caught:
            ModelSettings.from_environment({**MODEL_ENV, 'RETURNOPS_MODEL_VISION_ID': value})
        assert KEY not in str(caught.value)
