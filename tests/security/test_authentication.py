"""Actual JWT verification with synthetic registries, not HTTP/DB acceptance.

F.03; FR-009/012, NFR-002/003/009; docs/16 AUTH-01/02/07/12,
CS-D01 and MA G-REQUEST. Keys/tokens exist only in test memory.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime
import json
from pathlib import Path
import secrets
import traceback

import jwt
from jsonschema import Draft202012Validator
import pytest

from returnops_api.security import authentication
from returnops_api.security.authentication import AuthConfig, Authenticator
from returnops_api.security.authorization import AuthorizationService, CaseResource
from returnops_api.security.errors import Forbidden, ResourceNotFound, SecurityDependencyError, SecurityStoreUnavailable, Unauthenticated
from returnops_api.security.types import IdentitySnapshot, PrincipalRecord, Role, SessionRecord


NOW = 1800000000


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.fromtimestamp(NOW, tz=tz)


class RegistryDouble:
    """Replaceable coherent read snapshot; never an application identity store."""

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.reads = []
        self.failed = False

    def read_identity(self, principal_id, session_id):
        self.reads.append((principal_id, session_id))
        if self.failed:
            raise SecurityStoreUnavailable("private registry backend diagnostic")
        return self.snapshot


@pytest.fixture
def auth(monkeypatch):
    # Freeze the library's wall clock only, keeping real signing and validation.
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDateTime)
    monkeypatch.setattr(authentication, "datetime", FrozenDateTime)
    config = AuthConfig("returnops-demo", "returnops-api", secrets.token_bytes(32))
    snapshot = IdentitySnapshot(
        PrincipalRecord("customer_alpha", Role.CUSTOMER, "store_demo"),
        SessionRecord("session_alpha", "customer_alpha", NOW, NOW, NOW + 900),
    )
    store = RegistryDouble(snapshot)
    return Authenticator(config, store), config, store


def claims(**overrides):
    return {
        "iss": "returnops-demo", "aud": "returnops-api", "sub": "customer_alpha",
        "jti": "session_alpha", "iat": NOW, "nbf": NOW, "exp": NOW + 900,
        **overrides,
    }


def bearer(config, payload=None, **kwargs):
    # JWS signs malformed claim fixtures too; the application still validates JWTs.
    raw = json.dumps(claims() if payload is None else payload).encode("utf-8")
    return "Bearer " + jwt.PyJWS().encode(raw, config.signing_key, algorithm="HS256", **kwargs)


def bind_times(store, payload):
    store.snapshot = replace(store.snapshot, session=replace(
        store.snapshot.session,
        issued_at=payload["iat"], not_before=payload["nbf"], expires_at=payload["exp"],
    ))


def test_valid_session_projects_only_contract_principal(auth):
    service, config, store = auth
    principal = service.authenticate(bearer(config))
    assert principal.session_view() == {"principal_id": "customer_alpha", "role": "CUSTOMER"}
    schema = json.loads((Path(__file__).resolve().parents[2] / "contracts/v1/schemas.json").read_text(encoding="utf-8"))
    Draft202012Validator({"$ref": "#/$defs/Principal", "$defs": schema["$defs"]}).validate(principal.session_view())
    assert store.reads == [("customer_alpha", "session_alpha")]
    with pytest.raises(FrozenInstanceError):
        principal.role = Role.FOUNDER


@pytest.mark.parametrize("value", [None, "", "Basic abc", "Bearer", "Bearer x.y.z", "Bearer a.b.c\n", "Bearer\ta.b.c", "Bearer a.b.c extra", "Bearer " + "a" * 4097, 42, b"Bearer abc"])
def test_malformed_or_missing_bearer_rejected_before_registry(auth, value):
    service, _, store = auth
    with pytest.raises(Unauthenticated):
        service.authenticate(value)
    assert store.reads == []


def test_authentication_scheme_is_case_insensitive(auth):
    service, config, _ = auth
    assert service.authenticate(bearer(config).replace("Bearer ", "bEaReR  ")).role is Role.CUSTOMER


@pytest.mark.parametrize("name", ["iss", "aud", "sub", "jti", "iat", "nbf", "exp"])
def test_required_claim_missing_or_null_rejected(auth, name):
    service, config, store = auth
    for missing in (True, False):
        payload = claims()
        if missing:
            del payload[name]
        else:
            payload[name] = None
        with pytest.raises(Unauthenticated):
            service.authenticate(bearer(config, payload))
    assert store.reads == []


@pytest.mark.parametrize("overrides", [
    {"iss": "other-issuer"}, {"aud": "other-audience"}, {"aud": ["returnops-api"]},
    {"sub": ""}, {"sub": "customer_alpha\n"}, {"sub": 13}, {"sub": "x" * 81},
    {"jti": ""}, {"jti": 13}, {"jti": "session/alpha"},
    {"exp": NOW + 901}, {"exp": NOW}, {"exp": NOW - 6},
    {"iat": NOW + 6}, {"nbf": NOW + 6}, {"nbf": NOW + 900},
    {"iat": NOW + 1}, {"nbf": NOW - 1},
    {"iat": str(NOW)}, {"nbf": float(NOW)}, {"exp": str(NOW + 900)},
    {"iat": True}, {"nbf": False}, {"exp": float("inf")}, {"iat": -1},
    {"sub": {}}, {"jti": []}, {"iat": {}}, {"nbf": []}, {"exp": {}},
])
def test_invalid_claim_values_fail_before_registry(auth, overrides):
    service, config, store = auth
    with pytest.raises(Unauthenticated):
        service.authenticate(bearer(config, claims(**overrides)))
    assert store.reads == []


@pytest.mark.parametrize("issued_offset,nbf_offset,expiry_offset,allowed", [
    (5, 5, 900, True), (6, 6, 900, False),
    (0, 5, 900, True), (0, 6, 900, False),
    (-899, -899, -4, True), (-899, -899, -5, False),
    (0, 0, 900, True), (0, 0, 901, False),
])
def test_exact_clock_leeway_and_max_lifetime(auth, issued_offset, nbf_offset, expiry_offset, allowed):
    service, config, store = auth
    payload = claims(iat=NOW + issued_offset, nbf=NOW + nbf_offset, exp=NOW + expiry_offset)
    bind_times(store, payload)
    if allowed:
        assert service.authenticate(bearer(config, payload)).principal_id == "customer_alpha"
    else:
        with pytest.raises(Unauthenticated):
            service.authenticate(bearer(config, payload))


@pytest.mark.parametrize("algorithm", ["HS384", "HS512", "none"])
def test_other_algorithms_rejected(auth, algorithm):
    service, config, store = auth
    key = None if algorithm == "none" else secrets.token_bytes(64)
    token = jwt.encode(claims(), key, algorithm=algorithm)
    with pytest.raises(Unauthenticated):
        service.authenticate("Bearer " + token)
    assert store.reads == []


@pytest.mark.parametrize("headers", [{"typ": "at+jwt"}, {"typ": None}, {"kid": "client-chosen"}, {"jku": "https://invalid.example/keys"}, {"crit": []}, {"jwk": {}}])
def test_unsupported_header_metadata_rejected(auth, headers):
    service, config, store = auth
    with pytest.raises(Unauthenticated):
        service.authenticate(bearer(config, headers=headers))
    assert store.reads == []


def test_bad_signature_and_modified_payload_are_rejected(auth):
    service, config, store = auth
    wrong_key = replace(config, signing_key=secrets.token_bytes(32))
    with pytest.raises(Unauthenticated):
        service.authenticate(bearer(wrong_key))
    original = bearer(config).split(".")
    modified = bearer(config, claims(sub="founder_demo")).split(".")
    with pytest.raises(Unauthenticated):
        service.authenticate(".".join([original[0], modified[1], original[2]]))
    assert store.reads == []


@pytest.mark.parametrize("change", [
    "missing", "disabled", "revoked", "other_principal", "other_session", "wrong_session_owner",
    "shorter_session", "other_issued", "other_nbf", "invalid_role", "invalid_store", "untyped_enabled", "untyped_revoked",
])
def test_current_registration_binding_and_revocation(auth, change):
    service, config, store = auth
    token = bearer(config)
    assert service.authenticate(token).principal_id == "customer_alpha"
    current = store.snapshot
    updates = {
        "disabled": replace(current, principal=replace(current.principal, enabled=False)),
        "revoked": replace(current, session=replace(current.session, revoked=True)),
        "other_principal": replace(current, principal=replace(current.principal, principal_id="other_customer")),
        "other_session": replace(current, session=replace(current.session, session_id="other_session")),
        "wrong_session_owner": replace(current, session=replace(current.session, principal_id="other_customer")),
        "shorter_session": replace(current, session=replace(current.session, expires_at=NOW - 1)),
        "other_issued": replace(current, session=replace(current.session, issued_at=NOW - 1)),
        "other_nbf": replace(current, session=replace(current.session, not_before=NOW - 1)),
        "invalid_role": replace(current, principal=replace(current.principal, role="ADMIN")),
        "invalid_store": replace(current, principal=replace(current.principal, store_id="")),
        "untyped_enabled": replace(current, principal=replace(current.principal, enabled=1)),
        "untyped_revoked": replace(current, session=replace(current.session, revoked=0)),
        "missing": None,
    }
    store.snapshot = updates[change]
    with pytest.raises(Unauthenticated):
        service.authenticate(token)
    assert len(store.reads) == 2


def test_role_and_store_come_from_current_registry_never_token(auth):
    service, config, store = auth
    token = bearer(config, claims(role="FOUNDER", store_id="foreign_store", owner="other_customer"))
    actual = service.authenticate(token)
    assert (actual.role, actual.store_id) == (Role.CUSTOMER, "store_demo")
    store.snapshot = replace(store.snapshot, principal=replace(store.snapshot.principal, role=Role.FOUNDER))
    assert service.authenticate(token).role is Role.FOUNDER
    store.snapshot = replace(store.snapshot, principal=replace(store.snapshot.principal, role=Role.CUSTOMER))
    assert service.authenticate(token).role is Role.CUSTOMER


def test_empty_registry_after_restart_has_no_default_identity(auth):
    service, config, store = auth
    token = bearer(config)
    service.authenticate(token)
    restarted = Authenticator(config, RegistryDouble(None))
    with pytest.raises(Unauthenticated):
        restarted.authenticate(token)


def test_key_rotation_requires_new_valid_signature(auth):
    service, config, store = auth
    old_token = bearer(config)
    new_config = replace(config, signing_key=secrets.token_bytes(32))
    rotated = Authenticator(new_config, store)
    with pytest.raises(Unauthenticated):
        rotated.authenticate(old_token)
    assert rotated.authenticate(bearer(new_config)).role is Role.CUSTOMER


def test_dependency_failure_does_not_use_last_success_or_leak_details(auth, caplog):
    service, config, store = auth
    token = bearer(config)
    service.authenticate(token)
    store.failed = True
    with pytest.raises(SecurityDependencyError) as exc:
        service.authenticate(token)
    displayed = "".join(traceback.format_exception(exc.value))
    assert "private registry backend diagnostic" not in displayed
    assert token not in displayed + caplog.text + repr(config) + repr(service)
    assert repr(config.signing_key) not in repr(config)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("overrides", [{"signing_key": b"short"}, {"signing_key": "a" * 32}, {"signing_key": b"a" * 129}, {"issuer": ""}, {"audience": ""}, {"issuer": "bad\nissuer"}, {"audience": "a" * 201}, {"max_ttl_seconds": 901}, {"max_ttl_seconds": True}, {"max_ttl_seconds": 0}, {"leeway_seconds": 6}, {"leeway_seconds": -1}, {"leeway_seconds": False}])
def test_unsafe_configuration_fails_without_echoing_key(overrides):
    values = {"issuer": "returnops-demo", "audience": "returnops-api", "signing_key": secrets.token_bytes(32), **overrides}
    with pytest.raises(ValueError) as exc:
        AuthConfig(**values)
    assert repr(values["signing_key"]) not in str(exc.value)


class CaseOnlyResources:
    """One isolated case port, no DB or provider connection."""

    def __init__(self):
        self.case = CaseResource("case_alpha", "store_demo", "customer_alpha")
        self.reads = 0

    def get_case(self, case_id):
        self.reads += 1
        return self.case if self.case.case_id == case_id else None


def test_real_authentication_and_authorization_compose_without_token_role_authority(auth):
    authenticator, config, _ = auth
    resources = CaseOnlyResources()
    service = AuthorizationService(authenticator, resources)
    token = bearer(config, claims(role="FOUNDER", store_id="foreign_store"))
    grant = service.authorize(token, "getCustomerCase", "case_alpha")
    assert grant.principal.role is Role.CUSTOMER
    assert grant.case_id == "case_alpha"
    with pytest.raises(Forbidden):
        service.authorize(token, "recordFounderDecision", "case_alpha")
    assert resources.reads == 1


@pytest.mark.parametrize("change,denial", [
    ("revoked", Unauthenticated), ("disabled", Unauthenticated),
    ("owner", ResourceNotFound), ("store", ResourceNotFound),
])
def test_composed_recheck_rejects_changed_authority_without_new_effect(auth, change, denial):
    authenticator, config, identities = auth
    resources = CaseOnlyResources()
    service = AuthorizationService(authenticator, resources)
    token = bearer(config)
    effects = []

    def isolated_consumer():
        grant = service.authorize(token, "getCustomerCase", "case_alpha")
        # Spy records a test-only downstream callback, not a real business write.
        effects.append(grant.case_id)

    isolated_consumer()
    if change == "revoked":
        identities.snapshot = replace(identities.snapshot, session=replace(identities.snapshot.session, revoked=True))
    elif change == "disabled":
        identities.snapshot = replace(identities.snapshot, principal=replace(identities.snapshot.principal, enabled=False))
    elif change == "owner":
        resources.case = replace(resources.case, customer_id="customer_beta")
    else:
        resources.case = replace(resources.case, store_id="store_other")
    with pytest.raises(denial):
        isolated_consumer()
    assert effects == ["case_alpha"]
    assert resources.reads == (1 if change in {"revoked", "disabled"} else 2)


def test_actual_bad_token_is_rejected_before_resource_port(auth):
    authenticator, config, _ = auth
    resources = CaseOnlyResources()
    service = AuthorizationService(authenticator, resources)
    wrong = replace(config, signing_key=secrets.token_bytes(32))
    with pytest.raises(Unauthenticated):
        service.authorize(bearer(wrong), "getCustomerCase", "case_alpha")
    assert resources.reads == 0


@pytest.mark.parametrize("snapshot", [{}, IdentitySnapshot(None, None)])
def test_malformed_trusted_registry_result_is_safe_dependency_failure(auth, snapshot):
    authenticator, config, store = auth
    store.snapshot = snapshot
    with pytest.raises(SecurityDependencyError):
        authenticator.authenticate(bearer(config))


def test_session_expiring_during_registry_read_cannot_return_a_grant(auth, monkeypatch):
    authenticator, config, store = auth

    class AfterSlowRead(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(NOW + 905, tz=tz)

    monkeypatch.setattr(authentication, "datetime", AfterSlowRead)
    with pytest.raises(Unauthenticated):
        authenticator.authenticate(bearer(config))
    assert len(store.reads) == 1


@pytest.mark.parametrize("name,value", [("issued_at", float(NOW)), ("not_before", False), ("expires_at", str(NOW + 900))])
def test_registry_times_are_strict_integers(auth, name, value):
    authenticator, config, store = auth
    store.snapshot = replace(store.snapshot, session=replace(store.snapshot.session, **{name: value}))
    with pytest.raises(Unauthenticated):
        authenticator.authenticate(bearer(config))
