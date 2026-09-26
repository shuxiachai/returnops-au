"""F.03 authorization component evidence, not HTTP/business/DB acceptance.

Trace: FR-001/009/011/012, NFR-002/003/009; docs/16 AUTH-02/03/04/05/12,
CS-D01 / MA G-REQUEST. Stub tokens are not real credentials. Synthetic IDs
follow contracts/v1/schemas.json Id: ASCII alphanumeric, underscore/hyphen,
3-80 characters. The expected matrix below comes from docs/16, not the code.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from returnops_api.security.authorization import (
    AuthorizationService,
    CaseLinkedResource,
    CaseResource,
    EvidenceKind,
    EvidenceResource,
)
from returnops_api.security.errors import (
    Forbidden,
    ResourceNotFound,
    SecurityDependencyError,
    SecurityStoreUnavailable,
    Unauthenticated,
)
from returnops_api.security.types import Role, VerifiedPrincipal


NOW = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
ALPHA = VerifiedPrincipal("customer-alpha", Role.CUSTOMER, "store-demo", "session-alpha")
BETA = VerifiedPrincipal("customer-beta", Role.CUSTOMER, "store-demo", "session-beta")
FOUNDER = VerifiedPrincipal("founder-demo", Role.FOUNDER, "store-demo", "session-founder")


class StubAuthenticator:
    def __init__(self):
        self.principals = {"Bearer alpha": ALPHA, "Bearer beta": BETA, "Bearer founder": FOUNDER}
        self.calls = []
        self.unavailable = False

    def authenticate(self, authorization):
        self.calls.append(authorization)
        if self.unavailable:
            raise SecurityStoreUnavailable("private identity-store detail")
        if authorization not in self.principals:
            raise Unauthenticated()
        return self.principals[authorization]


class SyntheticResources:
    """Only synthetic read methods; dictionaries change solely in test setup."""

    def __init__(self):
        self.cases = {
            "case-alpha": CaseResource("case-alpha", "store-demo", "customer-alpha"),
            "case-beta": CaseResource("case-beta", "store-demo", "customer-beta"),
            "case-other-store": CaseResource("case-other-store", "store-other", "customer-alpha"),
        }
        self.evidence = {
            "evidence-bound": EvidenceResource(
                "evidence-bound", "store-demo", EvidenceKind.BOUND,
                "customer-alpha", "case-alpha", expires_at=NOW + timedelta(minutes=1),
            ),
            "evidence-staged": EvidenceResource(
                "evidence-staged", "store-demo", EvidenceKind.STAGED, "customer-alpha",
            ),
            "evidence-generated": EvidenceResource(
                "evidence-generated", "store-demo", EvidenceKind.GENERATED, case_id="case-alpha",
            ),
        }
        self.operations = {"operation-alpha": CaseLinkedResource("operation-alpha", "case-alpha")}
        self.notifications = {"notification-alpha": CaseLinkedResource("notification-alpha", "case-alpha")}
        self.calls = []
        self.unavailable = set()

    def _read(self, kind, key, collection):
        self.calls.append((kind, key))
        if kind in self.unavailable:
            raise SecurityStoreUnavailable("private resource-store detail")
        return collection.get(key)

    def get_case(self, case_id):
        return self._read("case", case_id, self.cases)

    def get_evidence(self, evidence_id):
        return self._read("evidence", evidence_id, self.evidence)

    def get_operation(self, operation_id):
        return self._read("operation", operation_id, self.operations)

    def get_notification(self, notification_id):
        return self._read("notification", notification_id, self.notifications)


@pytest.fixture
def security():
    auth = StubAuthenticator()
    resources = SyntheticResources()
    return AuthorizationService(auth, resources, clock=lambda: NOW), auth, resources


# Columns: operation, addressed resource, alpha result, beta result, Founder result.
# "allow" is an authorization observation; it is not an HTTP success or approval.
MATRIX = [
    ("getSession", None, "allow", "allow", "allow"),
    ("stageEvidence", None, "allow", "allow", Forbidden),
    ("getEvidenceContent", "evidence-bound", "allow", ResourceNotFound, "allow"),
    ("createCase", None, "allow", "allow", Forbidden),
    ("getCustomerCase", "case-alpha", "allow", ResourceNotFound, Forbidden),
    ("listCustomerCaseHistory", "case-alpha", "allow", ResourceNotFound, Forbidden),
    ("submitClarification", "case-alpha", "allow", ResourceNotFound, Forbidden),
    ("listFounderCases", None, Forbidden, Forbidden, "allow"),
    ("getFounderCase", "case-alpha", Forbidden, Forbidden, "allow"),
    ("listFounderCaseHistory", "case-alpha", Forbidden, Forbidden, "allow"),
    ("recordFounderDecision", "case-alpha", Forbidden, Forbidden, "allow"),
    ("reconcileOperation", "operation-alpha", Forbidden, Forbidden, "allow"),
    ("retryNotification", "notification-alpha", Forbidden, Forbidden, "allow"),
    ("listCaseAudit", "case-alpha", Forbidden, Forbidden, "allow"),
    ("getFounderAnalytics", None, Forbidden, Forbidden, "allow"),
]


def test_matrix_covers_exactly_the_existing_openapi_operations():
    api = json.loads((Path(__file__).resolve().parents[2] / "contracts/v1/openapi.json").read_text(encoding="utf-8"))
    operations = {
        spec["operationId"] for path in api["paths"].values()
        for spec in path.values() if isinstance(spec, dict) and "operationId" in spec
    }
    assert len(MATRIX) == 15
    assert {row[0] for row in MATRIX} == operations


@pytest.mark.parametrize("value", ["case-alpha\n", "case/alpha", "ca", "x" * 81])
def test_invalid_address_does_not_reach_resource_port(security, value):
    service, _, resources = security
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer alpha", "getCustomerCase", value)
    assert resources.calls == []


@pytest.mark.parametrize("value", ["false", 1, None])
def test_untyped_resource_availability_never_grants_access(security, value):
    service, _, resources = security
    resources.cases["case-alpha"] = replace(resources.cases["case-alpha"], available=value)
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")


@pytest.mark.parametrize("operation,resource_id,alpha,beta,founder", MATRIX)
@pytest.mark.parametrize("actor,column", [("alpha", 0), ("beta", 1), ("founder", 2)])
def test_fifteen_operation_role_and_ownership_matrix(
    security, operation, resource_id, alpha, beta, founder, actor, column,
):
    service, auth, resources = security
    expected = (alpha, beta, founder)[column]
    token = f"Bearer {actor}"
    if expected == "allow":
        grant = service.authorize(token, operation, resource_id)
        assert grant.principal == auth.principals[token]
        assert grant.store_id == "store-demo"
        assert grant.operation == operation
        assert grant.resource_id == resource_id
        assert grant.case_id == ("case-alpha" if resource_id is not None else None)
        assert token not in repr(grant)
    else:
        with pytest.raises(expected):
            service.authorize(token, operation, resource_id)
        if expected is Forbidden:
            assert resources.calls == []
    assert auth.calls == [token]


@pytest.mark.parametrize("operation,resource_id,alpha,beta,founder", MATRIX)
def test_every_operation_authenticates_before_resource_lookup(
    security, operation, resource_id, alpha, beta, founder,
):
    service, auth, resources = security
    with pytest.raises(Unauthenticated):
        service.authorize(None, operation, resource_id)
    assert auth.calls == [None]
    assert resources.calls == []


@pytest.mark.parametrize("token,operation", [
    ("Bearer alpha", "getCustomerCase"),
    ("Bearer founder", "getFounderCase"),
])
@pytest.mark.parametrize("case_id", ["case-missing", "case-other-store"])
def test_absent_and_cross_store_cases_have_the_same_safe_error(security, token, operation, case_id):
    service, _, _ = security
    with pytest.raises(ResourceNotFound) as caught:
        service.authorize(token, operation, case_id)
    assert str(caught.value) == str(ResourceNotFound())
    assert case_id not in str(caught.value)


def test_founder_can_read_both_customers_in_the_authorized_store(security):
    service, _, _ = security
    for case_id in ("case-alpha", "case-beta"):
        assert service.authorize("Bearer founder", "getFounderCase", case_id).case_id == case_id


@pytest.mark.parametrize("operation,resource_id,collection,kind", [
    ("reconcileOperation", "operation-alpha", "operations", "operation"),
    ("retryNotification", "notification-alpha", "notifications", "notification"),
])
@pytest.mark.parametrize("target", ["case-missing", "case-other-store"])
def test_linked_resources_resolve_their_authoritative_case(security, operation, resource_id, collection, kind, target):
    service, _, resources = security
    getattr(resources, collection)[resource_id] = CaseLinkedResource(resource_id, target)
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer founder", operation, resource_id)
    assert resources.calls == [(kind, resource_id), ("case", target)]


@pytest.mark.parametrize("operation,resource_id,collection", [
    ("reconcileOperation", "operation-alpha", "operations"),
    ("retryNotification", "notification-alpha", "notifications"),
])
@pytest.mark.parametrize("mode", ["missing", "unavailable", "wrong-record"])
def test_unusable_linked_records_cannot_grant_access(security, operation, resource_id, collection, mode):
    service, _, resources = security
    records = getattr(resources, collection)
    if mode == "missing":
        records.pop(resource_id)
    elif mode == "unavailable":
        records[resource_id] = replace(records[resource_id], available=False)
    else:
        records[resource_id] = replace(records[resource_id], resource_id="resource-other")
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer founder", operation, resource_id)
    assert len(resources.calls) == 1


@pytest.mark.parametrize("token,allowed", [("Bearer alpha", True), ("Bearer beta", False), ("Bearer founder", False)])
def test_staged_evidence_is_only_readable_by_its_uploader(security, token, allowed):
    service, _, resources = security
    if allowed:
        assert service.authorize(token, "getEvidenceContent", "evidence-staged").case_id is None
    else:
        with pytest.raises(ResourceNotFound):
            service.authorize(token, "getEvidenceContent", "evidence-staged")
    assert resources.calls == [("evidence", "evidence-staged")]


@pytest.mark.parametrize("token,allowed", [("Bearer alpha", True), ("Bearer beta", False), ("Bearer founder", True)])
def test_generated_evidence_uses_case_relationship_without_a_customer_uploader(security, token, allowed):
    service, _, _ = security
    if allowed:
        assert service.authorize(token, "getEvidenceContent", "evidence-generated").case_id == "case-alpha"
    else:
        with pytest.raises(ResourceNotFound):
            service.authorize(token, "getEvidenceContent", "evidence-generated")


@pytest.mark.parametrize("change", [
    {"available": False},
    {"expires_at": NOW},
    {"expires_at": NOW - timedelta(seconds=1)},
    {"expires_at": NOW.replace(tzinfo=None)},
    {"store_id": "store-other"},
    {"case_id": "case-other-store"},
    {"case_id": "case-missing"},
    {"case_id": None},
    {"uploader_id": "customer-beta"},
    {"evidence_id": "evidence-other"},
    {"kind": "UNKNOWN"},
])
@pytest.mark.parametrize("token", ["Bearer alpha", "Bearer founder"])
def test_unavailable_expired_or_inconsistent_evidence_is_not_found(security, change, token):
    service, _, resources = security
    resources.evidence["evidence-bound"] = replace(resources.evidence["evidence-bound"], **change)
    with pytest.raises(ResourceNotFound):
        service.authorize(token, "getEvidenceContent", "evidence-bound")


@pytest.mark.parametrize("evidence_id,change", [
    ("evidence-staged", {"case_id": "case-alpha"}),
    ("evidence-generated", {"uploader_id": "customer-alpha"}),
])
def test_inconsistent_evidence_lifecycle_records_do_not_grant_access(security, evidence_id, change):
    service, _, resources = security
    resources.evidence[evidence_id] = replace(resources.evidence[evidence_id], **change)
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer alpha", "getEvidenceContent", evidence_id)


@pytest.mark.parametrize("change", [{"available": False}, {"case_id": "case-other"}])
def test_unavailable_or_wrong_case_record_cannot_authorize_indirect_access(security, change):
    service, _, resources = security
    resources.cases["case-alpha"] = replace(resources.cases["case-alpha"], **change)
    for operation, resource_id in [
        ("getFounderCase", "case-alpha"),
        ("getEvidenceContent", "evidence-bound"),
        ("reconcileOperation", "operation-alpha"),
        ("retryNotification", "notification-alpha"),
    ]:
        with pytest.raises(ResourceNotFound):
            service.authorize("Bearer founder", operation, resource_id)


@pytest.mark.parametrize("operation,resource_id,kind", [
    ("getFounderCase", "case-alpha", "case"),
    ("getEvidenceContent", "evidence-bound", "evidence"),
    ("getEvidenceContent", "evidence-bound", "case"),
    ("reconcileOperation", "operation-alpha", "operation"),
    ("reconcileOperation", "operation-alpha", "case"),
    ("retryNotification", "notification-alpha", "notification"),
    ("retryNotification", "notification-alpha", "case"),
])
def test_resource_dependency_failure_is_safe_and_never_grants_access(security, operation, resource_id, kind):
    service, _, resources = security
    resources.unavailable.add(kind)
    with pytest.raises(SecurityDependencyError) as caught:
        service.authorize("Bearer founder", operation, resource_id)
    assert "private" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_identity_dependency_failure_is_safe_and_precedes_resources(security):
    service, auth, resources = security
    auth.unavailable = True
    with pytest.raises(SecurityDependencyError) as caught:
        service.authorize("Bearer founder", "getFounderCase", "case-alpha")
    assert "private" not in str(caught.value)
    assert resources.calls == []


def test_wrong_role_precedes_even_an_unavailable_resource_store(security):
    service, _, resources = security
    resources.unavailable.add("case")
    with pytest.raises(Forbidden):
        service.authorize("Bearer founder", "getCustomerCase", "case-alpha")
    assert resources.calls == []


def test_a_second_call_reauthenticates_and_rejects_a_revoked_session(security):
    service, auth, resources = security
    service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")
    auth.principals.pop("Bearer alpha")
    with pytest.raises(Unauthenticated):
        service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")
    assert auth.calls == ["Bearer alpha", "Bearer alpha"]
    assert resources.calls == [("case", "case-alpha")]


def test_a_second_call_uses_the_current_role(security):
    service, auth, resources = security
    service.authorize("Bearer founder", "recordFounderDecision", "case-alpha")
    auth.principals["Bearer founder"] = replace(FOUNDER, role=Role.CUSTOMER)
    with pytest.raises(Forbidden):
        service.authorize("Bearer founder", "recordFounderDecision", "case-alpha")
    assert resources.calls == [("case", "case-alpha")]
    assert len(auth.calls) == 2


def test_a_second_call_rereads_case_ownership(security):
    service, auth, resources = security
    service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")
    resources.cases["case-alpha"] = replace(resources.cases["case-alpha"], customer_id="customer-beta")
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")
    assert len(auth.calls) == 2
    assert resources.calls == [("case", "case-alpha"), ("case", "case-alpha")]


@pytest.mark.parametrize("operation", ["executeAnything", "", "GET /v1/session"])
def test_unknown_operation_fails_closed_after_authentication(security, operation):
    service, auth, resources = security
    with pytest.raises(Forbidden):
        service.authorize("Bearer founder", operation, "case-alpha")
    assert auth.calls == ["Bearer founder"]
    assert resources.calls == []


@pytest.mark.parametrize("operation,resource_id", [("getCustomerCase", None), ("getCustomerCase", ""), ("getSession", "case-alpha")])
def test_mismatched_component_call_scope_is_not_authorized(security, operation, resource_id):
    service, _, resources = security
    with pytest.raises(ResourceNotFound):
        service.authorize("Bearer alpha", operation, resource_id)
    assert resources.calls == []


def test_access_grant_and_resource_records_are_immutable(security):
    service, _, resources = security
    grant = service.authorize("Bearer alpha", "getCustomerCase", "case-alpha")
    with pytest.raises(FrozenInstanceError):
        grant.case_id = "case-beta"
    with pytest.raises(FrozenInstanceError):
        resources.cases["case-alpha"].customer_id = "customer-beta"
    assert not hasattr(grant, "authorization")
    assert not hasattr(grant, "token")
