"""tools/railway/start.py turns the advisory model showcase on only when it is configured (31 October 2026).

A missing or invalid model variable must not stop the demonstration: the service starts
without the showcase and says which variable is wrong, never its value. NFR-009; docs/44.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('railway_start', ROOT / 'tools' / 'railway' / 'start.py')
start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(start)

SECRET = 'sk-test-not-a-real-key-0123456789'
CONFIGURED = {
    'RETURNOPS_MODEL_SHOWCASE': '1',
    'RETURNOPS_MODEL_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'RETURNOPS_MODEL_API_KEY': SECRET,
    'RETURNOPS_MODEL_ID': 'qwen-plus',
    'RETURNOPS_MODEL_PROVIDER_ID': 'aliyun_bailian',
    'RETURNOPS_MODEL_DEADLINE_SECONDS': '30',
    'RETURNOPS_MODEL_MAX_CALLS': '50',
}


def test_the_showcase_is_on_only_when_switched_on_and_configured(capsys):
    assert '--model-showcase' in start.serve_arguments(CONFIGURED)
    assert '--model-showcase' not in start.serve_arguments({**CONFIGURED, 'RETURNOPS_MODEL_SHOWCASE': '0'})
    assert '--model-showcase' not in start.serve_arguments({})
    assert SECRET not in capsys.readouterr().out


@pytest.mark.parametrize('change', [
    {'RETURNOPS_MODEL_API_KEY': ''},
    {'RETURNOPS_MODEL_BASE_URL': 'http://dashscope.aliyuncs.com/compatible-mode/v1'},
    {'RETURNOPS_MODEL_MAX_CALLS': 'many'},
])
def test_an_incomplete_model_configuration_starts_without_the_showcase(change, capsys):
    arguments = start.serve_arguments({**CONFIGURED, **change})
    assert '--model-showcase' not in arguments and '--accounts' in arguments
    out = capsys.readouterr().out
    assert 'starting without it' in out and SECRET not in out
