"""Seven-operation customer domain boundary: current authority and atomic admission.

Actual file parsing is completed before calling stage. Processing is durable,
separate from acceptance, and never invoked by GET or idempotent replay.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from . import customer_tables as t
from . import idempotency
from .audit import append_event, identifier, timestamp
from .canonical import decode_document, digest, encode_document
from .customer_uow import CustomerUnitOfWork
from .errors import AcceptanceOutcomeUnknown, FlowError
from .history import append_revision, case_view, history_page
from .records import InitialCaseRecord, InitialRecordBundle, OriginalStatementRecord, StatementContent
from .scope_audit import append_scope_event
from .storage import InitialRecordRepository, StorageError, DomainValidationError
from .wire import clarification_request, create_request, validate

@dataclass(frozen=True)
class ResponseResult:
    status: int
    body: object = field(repr=False)
    replayed: bool = False

@dataclass(frozen=True)
class _Admission:
    body: dict = field(repr=False)
    acceptance_id: str
    status: int
    resource_kind: str
    resource_id: str
    bound_expiries: tuple = field(default=(), repr=False)

class CustomerFlow:
    def __init__(self, engine, authority, *, clock=lambda: datetime.now(timezone.utc),
                 snapshot_ttl=900, staged_ttl=3600, uow_factory=CustomerUnitOfWork):
        self.engine, self.authority, self.clock = engine, authority, clock
        self.snapshot_ttl, self.staged_ttl, self.uow_factory = snapshot_ttl, staged_ttl, uow_factory

    def _authorize(self, uow, operation, resource_id=None):
        actor = self.authority(uow.connection, "getSession")
        if operation not in {"getSession", "getEvidenceContent"} and actor.role != "CUSTOMER":
            raise FlowError("FORBIDDEN")
        if resource_id is not None: validate("Id", resource_id)
        return self.authority(uow.connection, operation, resource_id)

    def _same_authority(self, uow, actor, operation, resource_id=None):
        if self._authorize(uow, operation, resource_id) != actor: raise FlowError("UNAUTHENTICATED")

    def _fact_access(self, uow, actor, fact):
        operation = "getCustomerCase" if fact["resource_kind"] == "CASE" else "getEvidenceContent"
        current = self._authorize(uow, operation, fact["resource_id"])
        if current != actor or fact["store_id"] != actor.store_id: raise FlowError("NOT_FOUND")

    def _lookup(self, uow, actor, operation, target, key, fingerprint):
        return idempotency.lookup(uow, actor, operation, target, key, fingerprint,
            check_resource=lambda fact: self._fact_access(uow, actor, fact))

    def preflight(self, operation, resource_id=None):
        """Current authentication before reading/parsing potentially large uploads."""
        try:
            with self.uow_factory(self.engine, write=False) as uow:
                actor = self._authorize(uow, operation, resource_id)
                self._same_authority(uow, actor, operation, resource_id); uow.commit()
                return actor
        except (AcceptanceOutcomeUnknown, StorageError, SQLAlchemyError):
            failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None

    def _post(self, operation, target, key, value, normalize, admit, correlation_id):
        fingerprint = None
        try:
            with self.uow_factory(self.engine, write=True) as uow:
                actor = self._authorize(uow, operation, target)
                normalized = normalize(value)
                validate("IdempotencyKey", key)
                fingerprint = digest(normalized, "request/v1")
                previous = self._lookup(uow, actor, operation, target, key, fingerprint)
                if previous is not None:
                    status, body = idempotency.original_receipt(uow, previous)
                    self._same_authority(uow, actor, operation, target); uow.commit()
                    return ResponseResult(status, body, True)
                result = admit(uow, actor, normalized, key, fingerprint, correlation_id, self.clock())
                # Repeat current authority and resource relationships after all work,
                # with a fresh clock; parsing/provider/LLM calls never occur here.
                self._same_authority(uow, actor, operation, target)
                self._fact_access(uow, actor, {"resource_kind":result.resource_kind,"resource_id":result.resource_id,"store_id":actor.store_id})
                if any(expiry <= self.clock() for expiry in result.bound_expiries): raise FlowError("NOT_FOUND")
                uow.commit()
                return ResponseResult(result.status, result.body, False)
        except AcceptanceOutcomeUnknown:
            uncertain = True
        except (StorageError, DomainValidationError, SQLAlchemyError):
            uncertain = False
        if uncertain and fingerprint is not None:
            return self._recover(operation, target, key, fingerprint)
        raise FlowError("INTERNAL_ERROR") from None

    def _recover(self, operation, target, key, fingerprint):
        # A fresh READ COMMITTED transaction waits for the old writer's fence.
        # Missing facts or any uncertainty returns503; it never creates new work.
        try:
            with self.uow_factory(self.engine, write=False) as uow:
                actor = self._authorize(uow, operation, target)
                fact = self._lookup(uow, actor, operation, target, key, fingerprint)
                if fact is None: raise FlowError("INTERNAL_ERROR")
                status, body = idempotency.original_receipt(uow, fact)
                self._same_authority(uow, actor, operation, target); uow.commit()
                return ResponseResult(status, body, True)
        except (AcceptanceOutcomeUnknown, StorageError, SQLAlchemyError):
            failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None

    def session(self):
        actor = self.preflight("getSession")
        body = {"principal_id":actor.principal_id,"role":actor.role}
        validate("Principal",body,internal=True)
        return ResponseResult(200,body)

    def get_case(self, case_id):
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                actor = self._authorize(uow,"getCustomerCase",case_id)
                body = case_view(uow,actor,case_id,self.clock(),snapshot_ttl=self.snapshot_ttl)
                self._same_authority(uow,actor,"getCustomerCase",case_id); uow.commit()
                return ResponseResult(200,body)
        except (AcceptanceOutcomeUnknown, StorageError, SQLAlchemyError):
            failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None

    def history(self, case_id, query):
        try:
            with self.uow_factory(self.engine,write=True) as uow:
                actor = self._authorize(uow,"listCustomerCaseHistory",case_id)
                body = history_page(uow,actor,case_id,query,self.clock(),snapshot_ttl=self.snapshot_ttl)
                self._same_authority(uow,actor,"listCustomerCaseHistory",case_id); uow.commit()
                return ResponseResult(200,body)
        except (AcceptanceOutcomeUnknown, StorageError, SQLAlchemyError):
            failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None

    def download(self, evidence_id):
        try:
            with self.uow_factory(self.engine,write=False) as uow:
                actor = self._authorize(uow,"getEvidenceContent",evidence_id)
                meta = uow.execute(select(t.evidence).where(t.evidence.c.evidence_id==evidence_id)).mappings().one()
                raw = uow.execute(select(t.evidence_contents.c.body).where(t.evidence_contents.c.evidence_id==evidence_id)).scalar_one_or_none()
                if raw is None or len(raw)!=meta["size_bytes"] or sha256(bytes(raw)).hexdigest()!=meta["sha256"]:
                    raise FlowError("INTERNAL_ERROR")
                self._same_authority(uow,actor,"getEvidenceContent",evidence_id); uow.commit()
                return ResponseResult(200,(bytes(raw),meta["media_type"]))
        except (AcceptanceOutcomeUnknown, StorageError, SQLAlchemyError):
            failed = True
        if failed: raise FlowError("INTERNAL_ERROR") from None

    @staticmethod
    def _evidence_view(row):
        result = {name:row[name] for name in ("evidence_id","media_type","size_bytes","sha256","status")}
        result.update(filename=bytes(row["filename"]).decode("utf-8","surrogatepass"), created_at=timestamp(row["created_at"]),
                      content_path="/v1/evidence/"+row["evidence_id"]+"/content")
        if row["description"] is not None: result["description"]=bytes(row["description"]).decode("utf-8","surrogatepass")
        if row["case_id"] is not None: result["case_id"]=row["case_id"]
        validate("EvidenceAttachment",result,internal=True)
        return result

    def _eligible_evidence(self,uow,actor,evidence_ids,now):
        rows = uow.execute(select(t.evidence).where(t.evidence.c.evidence_id.in_(evidence_ids))).mappings().all() if evidence_ids else []
        by_id = {r["evidence_id"]:r for r in rows}; eligible=[]
        for evidence_id in evidence_ids:
            row=by_id.get(evidence_id)
            if row is None or not row["available"] or row["uploader_id"]!=actor.principal_id or row["store_id"]!=actor.store_id:
                raise FlowError("NOT_FOUND")
            if row["status"]!="STAGED": raise FlowError("INVALID_STATE")
            if row["expires_at"] is None or row["expires_at"]<=now: raise FlowError("NOT_FOUND")
            if uow.execute(select(t.evidence_contents.c.evidence_id).where(t.evidence_contents.c.evidence_id==evidence_id)).first() is None: raise FlowError("NOT_FOUND")
            eligible.append(dict(row))
        return eligible

    def _bind(self,uow,actor,case_id,eligible,now,correlation_id):
        references=[]
        for row in eligible:
            changed=uow.execute(update(t.evidence).where(t.evidence.c.evidence_id==row["evidence_id"],t.evidence.c.status=="STAGED",t.evidence.c.available.is_(True)).values(case_id=case_id,status="BOUND",expires_at=None))
            if changed.rowcount!=1: raise FlowError("INVALID_STATE")
            row=dict(row);row.update(case_id=case_id,status="BOUND",expires_at=None)
            references.append(append_revision(uow,case_id,"EVIDENCE",row["evidence_id"],1,self._evidence_view(row),now))
            append_scope_event(uow,"EVIDENCE",row["evidence_id"],actor.principal_id,actor.store_id,action="EVIDENCE_BOUND",
                actor={"kind":"HUMAN","role":"CUSTOMER","principal_id":actor.principal_id},payload={"case_id":case_id},correlation_id=correlation_id,now=now)
        return references

    def _enqueue(self,uow,actor,head,acceptance_id,refs,now,*,session_status,rounds):
        work_id=identifier("work")
        uow.execute(t.intake_work.insert().values(work_id=work_id,case_id=head["case_id"],acceptance_id=acceptance_id,
            input_version=head["input_version"],phase="INTAKE",state="PENDING",claim_id=None,created_at=now,claimed_at=None,
            lease_expires_at=None,completed_at=None,accepted_case_version=head["case_version"],
            accepted_principal_id=actor.principal_id,accepted_owner_id=actor.principal_id,accepted_store_id=actor.store_id,
            processor_version="deterministic-intake-v1",source_refs=encode_document(refs),claim_epoch=0,failure_count=0,next_attempt_at=now,safe_error=None))
        session=uow.execute(select(t.intake_sessions).where(t.intake_sessions.c.case_id==head["case_id"])).mappings().one_or_none()
        values={"input_version":head["input_version"],"status":session_status,"current_work_id":work_id,"updated_at":now,
                "clarification_round":rounds,"internal_revision":1 if session is None else session["internal_revision"]+1}
        if session is None:
            uow.execute(t.intake_sessions.insert().values(intake_session_id=identifier("intake"),case_id=head["case_id"],**values))
        else:
            old=session["current_work_id"]
            if old is not None:
                uow.execute(update(t.intake_work).where(t.intake_work.c.work_id==old,t.intake_work.c.state.in_(["PENDING","RUNNING","PAUSED"])).values(state="SUPERSEDED",completed_at=now))
            uow.execute(update(t.intake_sessions).where(t.intake_sessions.c.case_id==head["case_id"]).values(**values))
        return work_id

    def create(self, request, key, correlation_id):
        return self._post("createCase",None,key,request,create_request,self._create,correlation_id)

    def _create(self,uow,actor,request,key,fingerprint,correlation_id,now):
        eligible=self._eligible_evidence(uow,actor,request["evidence_ids"],now)
        case_id,statement_id=identifier("case"),identifier("statement")
        bundle=InitialRecordBundle(InitialCaseRecord(case_id,actor.principal_id,actor.store_id,1,1,"SUBMITTED",now,now),
            OriginalStatementRecord(statement_id,case_id,"ORIGINAL",1,1,1,now),
            StatementContent(statement_id,request["original_message"],request["requested_outcome"],request.get("order_reference")))
        InitialRecordRepository(uow.connection,uow.poison).insert_initial_record(bundle)
        head={"case_id":case_id,"owner_principal_id":actor.principal_id,"store_id":actor.store_id,
              "case_version":1,"input_version":1,"status":"SUBMITTED","created_at":now,"updated_at":now,
              "history_sequence":0,"audit_sequence":0,"audit_head":None,"current_question_set_id":None,"available":True}
        uow.execute(t.case_heads.insert().values(**head))
        statement={"statement_id":statement_id,"kind":"ORIGINAL","raw_text":request["original_message"],
                   "requested_outcome":request["requested_outcome"],"submitted_at":timestamp(now)}
        refs=[append_revision(uow,case_id,"STATEMENT",statement_id,1,statement,now)]
        refs+=self._bind(uow,actor,case_id,eligible,now,correlation_id)
        acceptance_id=idempotency.record_acceptance(uow,actor,"createCase",None,key,fingerprint,"CASE",case_id,201,now)
        work_id=self._enqueue(uow,actor,head,acceptance_id,refs,now,session_status="SUBMITTED",rounds=0)
        append_event(uow,case_id,actor={"kind":"HUMAN","role":"CUSTOMER","principal_id":actor.principal_id},
            event_type="CUSTOMER_CASE_ACCEPTED",correlation_id=correlation_id,
            payload={"acceptance_id":acceptance_id,"request_fingerprint":fingerprint,"work_id":work_id},
            object_ids=[ref["object_id"] for ref in refs],history_refs=refs,now=now)
        # The original201 is frozen before a processor can claim committed work.
        body=case_view(uow,actor,case_id,now,snapshot_ttl=self.snapshot_ttl)
        if body["status"]!="SUBMITTED" or body["case_version"]!=1 or body["input_version"]!=1: raise FlowError("INTERNAL_ERROR")
        idempotency.record_receipt(uow,acceptance_id,body,idempotency.view_refs(body))
        return _Admission(body,acceptance_id,201,"CASE",case_id,tuple(r["expires_at"] for r in eligible))

    def clarify(self,case_id,request,key,correlation_id):
        return self._post("submitClarification",case_id,key,request,clarification_request,
            lambda u,a,r,k,f,c,n:self._clarify(u,a,case_id,r,k,f,c,n),correlation_id)

    def _clarify(self,uow,actor,case_id,request,key,fingerprint,correlation_id,now):
        head=dict(uow.execute(select(t.case_heads).where(t.case_heads.c.case_id==case_id)).mappings().one())
        if request["expected_case_version"]!=head["case_version"]:
            self._deny_transition(uow,actor,case_id,"STALE_CASE_VERSION",correlation_id,now)
        if head["status"]!="AWAITING_INFORMATION" or head["current_question_set_id"]!=request["question_set_id"]:
            self._deny_transition(uow,actor,case_id,"INVALID_STATE",correlation_id,now)
        current=uow.execute(select(t.questions).where(t.questions.c.question_set_id==head["current_question_set_id"],t.questions.c.case_id==case_id)).mappings().one_or_none()
        if current is None or current["input_version"]!=head["input_version"]:
            self._deny_transition(uow,actor,case_id,"INVALID_STATE",correlation_id,now)
        questions=decode_document(current["questions"]); kinds=decode_document(current["question_kinds"])
        known={q["question_id"] for q in questions}; answered={a["question_id"] for a in request["answers"]}
        if not answered<=known: raise FlowError("VALIDATION_ERROR")
        eligible=self._eligible_evidence(uow,actor,request["evidence_ids"],now)
        remaining=[q for q in questions if q["question_id"] not in answered
                   and not (eligible and kinds.get(q["question_id"])=="PURCHASE_CONTEXT")]
        session=uow.execute(select(t.intake_sessions).where(t.intake_sessions.c.case_id==case_id)).mappings().one_or_none()
        if session is None: raise FlowError("INVALID_STATE")
        new_case_version,new_input_version=head["case_version"]+1,head["input_version"]+1
        question_set_id=None;rounds=session["clarification_round"]
        if remaining:
            question_set_id=identifier("questions");rounds+=1
            uow.execute(t.questions.insert().values(question_set_id=question_set_id,case_id=case_id,input_version=new_input_version,
                questions=encode_document(remaining),question_kinds=encode_document({q["question_id"]:kinds.get(q["question_id"],"TEXT_RESPONSE") for q in remaining})))
        values={"case_version":new_case_version,"input_version":new_input_version,
                "status":"AWAITING_INFORMATION" if remaining else "UNDER_INVESTIGATION","updated_at":now,
                "current_question_set_id":question_set_id,"current_failure_id":None}
        uow.execute(update(t.case_heads).where(t.case_heads.c.case_id==case_id,t.case_heads.c.case_version==head["case_version"]).values(**values));head.update(values)
        refs=[]
        for answer in request["answers"]:
            statement_id=identifier("statement")
            statement={"statement_id":statement_id,"kind":"CLARIFICATION","raw_text":answer["text"],
                       "submitted_at":timestamp(now),"question_id":answer["question_id"]}
            refs.append(append_revision(uow,case_id,"STATEMENT",statement_id,1,statement,now))
        refs+=self._bind(uow,actor,case_id,eligible,now,correlation_id)
        acceptance_id=idempotency.record_acceptance(uow,actor,"submitClarification",case_id,key,fingerprint,"CASE",case_id,202,now)
        work_id=self._enqueue(uow,actor,head,acceptance_id,refs,now,session_status="CLARIFICATION_RECEIVED",rounds=rounds)
        append_event(uow,case_id,actor={"kind":"HUMAN","role":"CUSTOMER","principal_id":actor.principal_id},
            event_type="CUSTOMER_CLARIFICATION_ACCEPTED",correlation_id=correlation_id,
            payload={"acceptance_id":acceptance_id,"request_fingerprint":fingerprint,"work_id":work_id},
            object_ids=[r["object_id"] for r in refs],history_refs=refs,now=now)
        body=case_view(uow,actor,case_id,now,snapshot_ttl=self.snapshot_ttl)
        idempotency.record_receipt(uow,acceptance_id,body,idempotency.view_refs(body))
        return _Admission(body,acceptance_id,202,"CASE",case_id,tuple(r["expires_at"] for r in eligible))

    def stage(self,material,key,correlation_id):
        # Parsing and the first auth check are performed by the HTTP composition
        # before this fenced write; an immutable result crosses this boundary.
        from .evidence_validation import ValidatedEvidence
        if type(material) is not ValidatedEvidence: raise FlowError("VALIDATION_ERROR")
        normalized={"filename":material.filename,"media_type":material.media_type,"size_bytes":material.size_bytes,
                    "file_sha256":material.sha256}
        if material.description is not None: normalized["description"]=material.description
        if len(material.content)!=material.size_bytes or sha256(material.content).hexdigest()!=material.sha256: raise FlowError("VALIDATION_ERROR")
        return self._post("stageEvidence",None,key,normalized,lambda x:x,
            lambda u,a,r,k,f,c,n:self._stage(u,a,material,k,f,c,n),correlation_id)

    def _stage(self,uow,actor,material,key,fingerprint,correlation_id,now):
        evidence_id=identifier("evidence")
        row={"evidence_id":evidence_id,"uploader_id":actor.principal_id,"store_id":actor.store_id,"case_id":None,
             "filename":material.filename.encode("utf-8","surrogatepass"),
             "description":None if material.description is None else material.description.encode("utf-8","surrogatepass"),
             "media_type":material.media_type,"size_bytes":material.size_bytes,"sha256":material.sha256,
             "status":"STAGED","created_at":now,"expires_at":now+timedelta(seconds=self.staged_ttl),"available":True}
        body=self._evidence_view(row)
        uow.execute(t.evidence.insert().values(**row))
        uow.execute(t.evidence_contents.insert().values(evidence_id=evidence_id,body=material.content))
        acceptance_id=idempotency.record_acceptance(uow,actor,"stageEvidence",None,key,fingerprint,"EVIDENCE",evidence_id,201,now)
        append_scope_event(uow,"EVIDENCE",evidence_id,actor.principal_id,actor.store_id,action="EVIDENCE_STAGED",
            actor={"kind":"HUMAN","role":"CUSTOMER","principal_id":actor.principal_id},
            payload={"acceptance_id":acceptance_id,"request_fingerprint":fingerprint},correlation_id=correlation_id,now=now)
        idempotency.record_receipt(uow,acceptance_id,body,[("EVIDENCE",evidence_id)])
        return _Admission(body,acceptance_id,201,"EVIDENCE",evidence_id)

    def _deny_transition(self,uow,actor,case_id,code,correlation_id,now):
        # Called only by pre-mutation state/version guards, after authorized
        # idempotency lookup. Persist denial alone: no acceptance/work/revision.
        self._same_authority(uow,actor,"submitClarification",case_id)
        append_event(uow,case_id,actor={"kind":"HUMAN","role":"CUSTOMER","principal_id":actor.principal_id},
            event_type="CUSTOMER_TRANSITION_DENIED",correlation_id=correlation_id,
            payload={"operation":"submitClarification","reason":code},object_ids=[],history_refs=[],now=now)
        self._same_authority(uow,actor,"submitClarification",case_id)
        uow.commit()
        raise FlowError(code)
