"""The per-process cap on model calls (31 October 2026): over budget, fail closed, send nothing."""
import pytest

from returnops_api.model_settings import ModelSettings
from returnops_api.settings import ConfigurationError
from returnops_domain.model_transport import BudgetedTransport, ModelTransportError, TRANSIENT_CODES

BASE = {
    'RETURNOPS_MODEL_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'RETURNOPS_MODEL_API_KEY': 'sk-test-not-a-real-key',
    'RETURNOPS_MODEL_ID': 'qwen-plus',
    'RETURNOPS_MODEL_PROVIDER_ID': 'aliyun_bailian',
}


def test_the_budget_lets_through_the_allowed_calls_and_then_fails_closed():
    sent = []
    transport = BudgetedTransport(lambda invocation: sent.append(invocation) or 'reply', 2)
    assert transport('a') == 'reply' and transport('b') == 'reply'
    with pytest.raises(ModelTransportError) as refused:
        transport('c')
    assert refused.value.code == 'BUDGET' and 'BUDGET' not in TRANSIENT_CODES
    assert sent == ['a', 'b']


def test_settings_wrap_the_transport_only_when_a_cap_is_set():
    assert not isinstance(ModelSettings.from_environment(BASE).transport(), BudgetedTransport)
    capped = ModelSettings.from_environment({**BASE, 'RETURNOPS_MODEL_MAX_CALLS': '50'}).transport()
    assert isinstance(capped, BudgetedTransport) and capped.remaining == 50
    for value in ('0', '-1', 'ten', '100001'):
        with pytest.raises(ConfigurationError) as error:
            ModelSettings.from_environment({**BASE, 'RETURNOPS_MODEL_MAX_CALLS': value})
        assert 'RETURNOPS_MODEL_MAX_CALLS' in str(error.value) and 'sk-test' not in str(error.value)
