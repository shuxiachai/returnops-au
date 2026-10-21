"""Composition adapters reuse F.03 over the exact fenced domain connection."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from returnops_domain import customer_tables as t
from returnops_domain.errors import FlowError
from returnops_domain.ports import Actor
from .security.authentication import AuthConfig, Authenticator
from .security.authorization import AuthorizationService, CaseResource, EvidenceResource, EvidenceKind
from .security.errors import SecurityError, SecurityStoreUnavailable
from .security.types import IdentitySnapshot, PrincipalRecord, Role, SessionRecord

class _Reader:
    def __init__(self, connection): self.connection = connection
    def one(self, statement):
        failed = False
        try: result = self.connection.execute(statement).mappings().one_or_none()
        except SQLAlchemyError: failed = True
        if failed: raise SecurityStoreUnavailable() from None
        return result

class SameConnectionIdentities(_Reader):
    def read_identity(self, principal_id, session_id):
        row = self.one(select(t.principals, t.sessions.c.session_id, t.sessions.c.issued_at,
            t.sessions.c.not_before, t.sessions.c.expires_at, t.sessions.c.revoked).join(t.sessions,
            and_(t.sessions.c.principal_id == t.principals.c.principal_id, t.sessions.c.session_id == session_id))
            .where(t.principals.c.principal_id == principal_id))
        if row is None: return None
        failed = False
        try:
            result = IdentitySnapshot(PrincipalRecord(row["principal_id"], Role(row["role"]), row["store_id"], row["enabled"]),
                SessionRecord(row["session_id"], row["principal_id"], row["issued_at"], row["not_before"], row["expires_at"], row["revoked"]))
        except (ValueError, TypeError, KeyError): failed = True
        if failed: raise SecurityStoreUnavailable() from None
        return result

class _DomainReads:
    """Same-connection read context; a scope hint never admits a write."""
    def __init__(self,connection):self.connection,self.failed=connection,False
    def poison(self):self.failed=True
    def execute(self,statement,parameters=None):
        if self.failed or not getattr(statement,'is_select',False):
            self.poison();raise FlowError('INTERNAL_ERROR')
        return self.connection.execute(statement,parameters or {})

class SameConnectionResources(_Reader):
    def get_case(self, case_id):
        row = self.one(select(t.case_heads).where(t.case_heads.c.case_id == case_id))
        return None if row is None else CaseResource(row["case_id"], row["store_id"], row["owner_principal_id"], row["available"])
    def get_evidence(self, evidence_id):
        from returnops_domain.generated_evidence import is_generated_resource,scope_hint
        context=_DomainReads(self.connection)
        if is_generated_resource(context,evidence_id):
            snapshot=scope_hint(context,evidence_id)
            if snapshot is None:return None
            return EvidenceResource(snapshot.evidence_id,snapshot.store_id,EvidenceKind.GENERATED,
                None,snapshot.case_id,snapshot.available,None)
        row = self.one(select(t.evidence).where(t.evidence.c.evidence_id == evidence_id))
        if row is None: return None
        if row["status"] not in {"STAGED", "BOUND"}: raise SecurityStoreUnavailable()
        return EvidenceResource(row["evidence_id"], row["store_id"], EvidenceKind(row["status"]),
            row["uploader_id"], row["case_id"], row["available"], row["expires_at"])
    def get_operation(self, operation_id): return None
    def get_notification(self, notification_id): return None

@dataclass(repr=False)
class CurrentRequestAuthority:
    config: AuthConfig
    authorization: str | None = field(repr=False)
    clock: object = lambda: datetime.now(timezone.utc)

    def __call__(self, connection, operation, resource_id=None):
        authenticator = Authenticator(self.config, SameConnectionIdentities(connection))
        service = AuthorizationService(authenticator, SameConnectionResources(connection), clock=self.clock)
        failure = None
        try:
            grant = service.authorize(self.authorization, operation, resource_id)
            if operation=='getEvidenceContent':
                from returnops_domain.generated_evidence import is_generated_resource,resolve
                context=_DomainReads(connection)
                if is_generated_resource(context,resource_id):
                    # F.03 has already accepted the minimal scope. Only this
                    # authorized path reads/verifies the certificate and bytes.
                    snapshot=resolve(context,resource_id)
                    if (not snapshot.available or snapshot.case_id!=grant.case_id
                            or snapshot.store_id!=grant.store_id):raise FlowError('INVALID_STATE')
                    if service.authorize(self.authorization,operation,resource_id)!=grant:
                        raise FlowError('UNAUTHENTICATED')
        except SecurityError as error: failure = (error.code, error.status_code)
        if failure is not None: raise FlowError(failure[0], status=failure[1]) from None
        principal = grant.principal
        return Actor(principal.principal_id, principal.role.value, principal.store_id, principal.session_id)
