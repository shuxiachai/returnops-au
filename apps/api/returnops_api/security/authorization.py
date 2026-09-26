"""F.03 candidate: read-only authorization, not fifteen implemented HTTP routes.

Trace: FR-001/009/011/012, NFR-002/003/009; docs/16 AUTH-02/03/04/05/12,
CS-D01 and MA G-REQUEST. Resource records below are trusted internal port
results, never request DTOs or evidence of ownership supplied by a caller.

A grant is one authorization observation, not a durable execution capability.
Domain must recheck current authority and relationships in its transaction.
Approval, lifecycle, idempotency, cursor and business-write guards are separate.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from .errors import (
    Forbidden,
    ResourceNotFound,
    SecurityDependencyError,
    SecurityStoreUnavailable,
)
from .types import Role, VerifiedPrincipal, valid_id


class AuthenticatorPort(Protocol):
    def authenticate(self, authorization: str | None) -> VerifiedPrincipal: ...


@dataclass(frozen=True, slots=True)
class CaseResource:
    case_id: str
    store_id: str
    customer_id: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class CaseLinkedResource:
    """An operation or notification with its authoritative case relationship."""

    resource_id: str
    case_id: str
    available: bool = True


class EvidenceKind(StrEnum):
    STAGED = "STAGED"
    BOUND = "BOUND"
    GENERATED = "GENERATED"


@dataclass(frozen=True, slots=True)
class EvidenceResource:
    evidence_id: str
    store_id: str
    kind: EvidenceKind
    uploader_id: str | None = None
    case_id: str | None = None
    available: bool = True
    expires_at: datetime | None = None


class ReadOnlyResources(Protocol):
    """Fresh trusted reads; unavailable storage raises SecurityStoreUnavailable.

    None represents absence. Adapters must not return cached ownership after
    revocation/deletion; transactional revalidation remains Domain's obligation.
    """

    def get_case(self, case_id: str) -> CaseResource | None: ...

    def get_evidence(self, evidence_id: str) -> EvidenceResource | None: ...

    def get_operation(self, operation_id: str) -> CaseLinkedResource | None: ...

    def get_notification(self, notification_id: str) -> CaseLinkedResource | None: ...


@dataclass(frozen=True, slots=True)
class AccessGrant:
    principal: VerifiedPrincipal
    operation: str
    store_id: str
    case_id: str | None = None
    resource_id: str | None = None


class _ResourceKind(StrEnum):
    NONE = "none"
    CASE = "case"
    EVIDENCE = "evidence"
    OPERATION = "operation"
    NOTIFICATION = "notification"


@dataclass(frozen=True, slots=True)
class _Policy:
    roles: frozenset[Role]
    resource: _ResourceKind = _ResourceKind.NONE


_CUSTOMER = frozenset({Role.CUSTOMER})
_FOUNDER = frozenset({Role.FOUNDER})
_BOTH = frozenset({Role.CUSTOMER, Role.FOUNDER})
_POLICIES = MappingProxyType({
    "getSession": _Policy(_BOTH),
    "stageEvidence": _Policy(_CUSTOMER),
    "getEvidenceContent": _Policy(_BOTH, _ResourceKind.EVIDENCE),
    "createCase": _Policy(_CUSTOMER),
    "getCustomerCase": _Policy(_CUSTOMER, _ResourceKind.CASE),
    "listCustomerCaseHistory": _Policy(_CUSTOMER, _ResourceKind.CASE),
    "submitClarification": _Policy(_CUSTOMER, _ResourceKind.CASE),
    "listFounderCases": _Policy(_FOUNDER),
    "getFounderCase": _Policy(_FOUNDER, _ResourceKind.CASE),
    "listFounderCaseHistory": _Policy(_FOUNDER, _ResourceKind.CASE),
    "recordFounderDecision": _Policy(_FOUNDER, _ResourceKind.CASE),
    "reconcileOperation": _Policy(_FOUNDER, _ResourceKind.OPERATION),
    "retryNotification": _Policy(_FOUNDER, _ResourceKind.NOTIFICATION),
    "listCaseAudit": _Policy(_FOUNDER, _ResourceKind.CASE),
    "getFounderAnalytics": _Policy(_FOUNDER),
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthorizationService:
    def __init__(
        self,
        authenticator: AuthenticatorPort,
        resources: ReadOnlyResources,
        *,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._authenticator = authenticator
        self._resources = resources
        self._clock = clock

    def authorize(
        self,
        authorization: str | None,
        operation: str,
        resource_id: str | None = None,
    ) -> AccessGrant:
        """Authenticate on every call, then role-check before any resource read.

        Unknown operations fail closed using the existing FORBIDDEN category.
        resource_id addresses a resource; it never proves a case relationship.
        Wire syntax validation remains the future API adapter's responsibility.
        """
        try:
            principal = self._authenticator.authenticate(authorization)
            policy = _POLICIES.get(operation) if isinstance(operation, str) else None
            if policy is None or principal.role not in policy.roles:
                raise Forbidden()

            if policy.resource == _ResourceKind.NONE:
                if resource_id is not None:
                    raise ResourceNotFound()
                return AccessGrant(principal, operation, principal.store_id)

            if not valid_id(resource_id):
                raise ResourceNotFound()
            if policy.resource == _ResourceKind.EVIDENCE:
                case_id = self._authorize_evidence(principal, resource_id)
            elif policy.resource == _ResourceKind.CASE:
                case_id = self._authorize_case(principal, resource_id).case_id
            else:
                if policy.resource == _ResourceKind.OPERATION:
                    linked = self._resources.get_operation(resource_id)
                else:
                    linked = self._resources.get_notification(resource_id)
                if (
                    linked is None
                    or linked.resource_id != resource_id
                    or linked.available is not True
                    or not valid_id(linked.case_id)
                ):
                    raise ResourceNotFound()
                case_id = self._authorize_case(principal, linked.case_id).case_id

            return AccessGrant(principal, operation, principal.store_id, case_id, resource_id)
        except SecurityStoreUnavailable:
            # Port diagnostics may contain private resource/connection details.
            raise SecurityDependencyError() from None

    def _authorize_case(self, principal: VerifiedPrincipal, case_id: str) -> CaseResource:
        case = self._resources.get_case(case_id)
        if (
            case is None
            or case.case_id != case_id
            or case.available is not True
            or case.store_id != principal.store_id
            or (principal.role == Role.CUSTOMER and case.customer_id != principal.principal_id)
        ):
            raise ResourceNotFound()
        return case

    def _authorize_evidence(self, principal: VerifiedPrincipal, evidence_id: str) -> str | None:
        evidence = self._resources.get_evidence(evidence_id)
        if (
            evidence is None
            or evidence.evidence_id != evidence_id
            or evidence.available is not True
            or evidence.store_id != principal.store_id
        ):
            raise ResourceNotFound()
        if evidence.expires_at is not None:
            if evidence.expires_at.utcoffset() is None:
                raise ResourceNotFound()
            now = self._clock()
            if now.utcoffset() is None:
                raise SecurityDependencyError()
            if evidence.expires_at <= now:
                raise ResourceNotFound()

        if evidence.kind == EvidenceKind.STAGED:
            if (
                principal.role != Role.CUSTOMER
                or evidence.uploader_id != principal.principal_id
                or evidence.case_id is not None
            ):
                raise ResourceNotFound()
            return None

        if evidence.kind not in {EvidenceKind.BOUND, EvidenceKind.GENERATED} or not valid_id(evidence.case_id):
            raise ResourceNotFound()
        case = self._authorize_case(principal, evidence.case_id)
        if evidence.kind == EvidenceKind.BOUND and evidence.uploader_id != case.customer_id:
            raise ResourceNotFound()
        if evidence.kind == EvidenceKind.GENERATED and evidence.uploader_id is not None:
            raise ResourceNotFound()
        return case.case_id
