"""The Founder decision POST is registered only by explicit choice (A2.07 step 1).

Offline: a placeholder engine and an in-memory auth configuration; no lifespan,
no database, no private configuration. FR-009; NFR-002; docs/40.
"""
import secrets

import pytest

from returnops_api.founder_decision_http import PATH, OPERATION
from returnops_api.main import create_app
from returnops_api.security.authentication import AuthConfig


def _config():
    return AuthConfig('registration-tests', 'registration-api', secrets.token_bytes(48), leeway_seconds=0)


def _decision_routes(app):
    return [route for route in app.routes if getattr(route, 'path', '') == PATH]


def test_default_composition_keeps_the_decision_route_off(monkeypatch):
    monkeypatch.delenv('RETURNOPS_FOUNDER_DECISIONS', raising=False)
    app = create_app(engine=object(), auth_config=_config(), enable_processor=False, enable_fixed_proposal=False)
    assert _decision_routes(app) == []


def test_keyword_registers_exactly_one_decision_post(monkeypatch):
    monkeypatch.delenv('RETURNOPS_FOUNDER_DECISIONS', raising=False)
    app = create_app(engine=object(), auth_config=_config(), enable_processor=False, enable_fixed_proposal=False,
                     enable_founder_decisions=True)
    route, = _decision_routes(app)
    assert route.methods == {'POST'} and route.operation_id == OPERATION
    # The four Founder reads, the F.06 analytics GET and the health routes are untouched.
    # F.06: the default-registered analytics GET adds the sixth /v1/founder/ route.
    assert sum(1 for r in app.routes if getattr(r, 'path', '').startswith('/v1/founder/')) == 6


@pytest.mark.parametrize('value, expected', [('0', 0), ('1', 1)])
def test_environment_flag_selects_registration(monkeypatch, value, expected):
    monkeypatch.setenv('RETURNOPS_FOUNDER_DECISIONS', value)
    app = create_app(engine=object(), auth_config=_config(), enable_processor=False, enable_fixed_proposal=False)
    assert len(_decision_routes(app)) == expected


@pytest.mark.parametrize('value', ['', 'true', '2', ' 1', 'yes'])
def test_malformed_environment_flag_is_rejected_before_any_route(monkeypatch, value):
    monkeypatch.setenv('RETURNOPS_FOUNDER_DECISIONS', value)
    with pytest.raises(ValueError):
        create_app(engine=object(), auth_config=_config(), enable_processor=False, enable_fixed_proposal=False)


def test_keyword_must_be_boolean(monkeypatch):
    with pytest.raises(ValueError):
        create_app(engine=object(), auth_config=_config(), enable_processor=False, enable_fixed_proposal=False,
                   enable_founder_decisions='1')
