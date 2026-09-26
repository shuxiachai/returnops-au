"""Explicit trusted local registry maintenance; no public identity-issuance API."""
from datetime import datetime, timezone
from sqlalchemy import or_, select, update
from . import customer_tables as t
from .audit import identifier
from .customer_uow import CustomerUnitOfWork
from .errors import FlowError
from .scope_audit import append_scope_event
from .wire import validate

_SERVICE = {"kind": "SERVICE", "component_id": "local_demo_registry"}

class TrustedRegistry:
    def __init__(self, engine, *, clock=lambda: datetime.now(timezone.utc)):
        self.engine, self.clock = engine, clock

    def provision(self, principals, sessions):
        principal_ids = {item["principal_id"] for item in principals}
        if len(principal_ids) != len(principals) or not principals or not sessions: raise FlowError("VALIDATION_ERROR")
        for item in principals:
            if set(item) != {"principal_id", "role", "store_id", "enabled"} or type(item["enabled"]) is not bool: raise FlowError("VALIDATION_ERROR")
            validate("Principal", {"principal_id": item["principal_id"], "role": item["role"]}); validate("Id", item["store_id"])
        for item in sessions:
            if set(item) != {"session_id", "principal_id", "issued_at", "not_before", "expires_at", "revoked"}: raise FlowError("VALIDATION_ERROR")
            validate("Id", item["session_id"])
            times = [item[x] for x in ("issued_at", "not_before", "expires_at")]
            if (item["principal_id"] not in principal_ids or any(type(x) is not int for x in times)
                    or not 0 <= times[0] <= times[1] < times[2] <= 9007199254740991 or times[2] - times[0] > 900
                    or type(item["revoked"]) is not bool): raise FlowError("VALIDATION_ERROR")
        with CustomerUnitOfWork(self.engine, write=True) as uow:
            if uow.execute(select(t.principals.c.principal_id).where(t.principals.c.principal_id.in_(principal_ids))).first(): raise FlowError("INVALID_STATE")
            for item in principals:
                uow.execute(t.principals.insert().values(**item))
                append_scope_event(uow,"PRINCIPAL",item["principal_id"],item["principal_id"],item["store_id"],
                    action="PRINCIPAL_PROVISIONED",actor=_SERVICE,payload={"role":item["role"],"enabled":item["enabled"]},correlation_id=identifier("corr"),now=self.clock())
            for item in sessions: uow.execute(t.sessions.insert().values(**item))
            uow.commit()

    def register_session(self, principal_id, session_id, issued_at, not_before, expires_at):
        for value in (principal_id, session_id): validate("Id", value)
        times = (issued_at, not_before, expires_at)
        if any(type(x) is not int for x in times) or not 0 <= issued_at <= not_before < expires_at <= 9007199254740991 or expires_at-issued_at > 900: raise FlowError("VALIDATION_ERROR")
        with CustomerUnitOfWork(self.engine, write=True) as uow:
            principal = uow.execute(select(t.principals).where(t.principals.c.principal_id==principal_id)).mappings().one_or_none()
            if principal is None or not principal["enabled"]: raise FlowError("INVALID_STATE")
            uow.execute(t.sessions.insert().values(session_id=session_id,principal_id=principal_id,issued_at=issued_at,not_before=not_before,expires_at=expires_at,revoked=False))
            append_scope_event(uow,"PRINCIPAL",principal_id,principal_id,principal["store_id"],action="SESSION_REGISTERED",actor=_SERVICE,payload={"session_id":session_id},correlation_id=identifier("corr"),now=self.clock())
            uow.commit()

    def change_principal(self, principal_id, *, enabled=None, store_id=None, role=None):
        validate("Id", principal_id); values = {}
        if enabled is not None:
            if type(enabled) is not bool: raise FlowError("VALIDATION_ERROR")
            values["enabled"] = enabled
        if store_id is not None: validate("Id", store_id); values["store_id"] = store_id
        if role is not None:
            validate("Principal", {"principal_id":principal_id,"role":role}); values["role"] = role
        with CustomerUnitOfWork(self.engine, write=True) as uow:
            current = uow.execute(select(t.principals).where(t.principals.c.principal_id==principal_id)).mappings().one_or_none()
            if current is None: raise FlowError("NOT_FOUND")
            if values:
                uow.execute(update(t.principals).where(t.principals.c.principal_id==principal_id).values(**values))
                uow.execute(update(t.intake_work).where(t.intake_work.c.accepted_principal_id==principal_id,t.intake_work.c.state=="PAUSED").values(state="PENDING",claim_id=None,lease_expires_at=None,next_attempt_at=self.clock()))
                append_scope_event(uow,"PRINCIPAL",principal_id,principal_id,values.get("store_id",current["store_id"]),action="PRINCIPAL_CHANGED",actor=_SERVICE,payload=values,correlation_id=identifier("corr"),now=self.clock())
            uow.commit()

    def revoke_session(self, session_id):
        validate("Id", session_id)
        with CustomerUnitOfWork(self.engine, write=True) as uow:
            session = uow.execute(select(t.sessions).where(t.sessions.c.session_id==session_id)).mappings().one_or_none()
            if session is None: raise FlowError("NOT_FOUND")
            principal = uow.execute(select(t.principals).where(t.principals.c.principal_id==session["principal_id"])).mappings().one()
            uow.execute(update(t.sessions).where(t.sessions.c.session_id==session_id).values(revoked=True))
            append_scope_event(uow,"PRINCIPAL",principal["principal_id"],principal["principal_id"],principal["store_id"],action="SESSION_REVOKED",actor=_SERVICE,payload={"session_id":session_id},correlation_id=identifier("corr"),now=self.clock())
            uow.commit()

    def change_empty_case_scope(self, case_id, owner_id, store_id):
        """Metadata-only maintenance; accepted cases cannot be transferred or purged."""
        from .storage import original_statement_records
        for value in (case_id,owner_id,store_id): validate("Id",value)
        with CustomerUnitOfWork(self.engine,write=True) as uow:
            head=uow.execute(select(t.case_heads).where(t.case_heads.c.case_id==case_id)).mappings().one_or_none()
            if head is None: raise FlowError("NOT_FOUND")
            if (head["owner_principal_id"],head["store_id"])==(owner_id,store_id): uow.commit(); return
            personal = (uow.execute(select(original_statement_records.c.statement_id).where(original_statement_records.c.case_id==case_id)).first()
                or uow.execute(select(t.history.c.record_id).where(t.history.c.case_id==case_id)).first()
                or uow.execute(select(t.evidence.c.evidence_id).where(t.evidence.c.case_id==case_id)).first()
                or uow.execute(select(t.acceptances.c.acceptance_id).where(t.acceptances.c.resource_kind=="CASE",t.acceptances.c.resource_id==case_id)).first())
            if personal: raise FlowError("INVALID_STATE")
            owner=uow.execute(select(t.principals).where(t.principals.c.principal_id==owner_id,t.principals.c.store_id==store_id,t.principals.c.role=="CUSTOMER",t.principals.c.enabled.is_(True))).first()
            if owner is None: raise FlowError("INVALID_STATE")
            uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==case_id).values(owner_principal_id=owner_id,store_id=store_id,case_version=head["case_version"]+1,updated_at=self.clock()))
            uow.commit()
