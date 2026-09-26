"""Internal pre-case/registry audit chain; never a fabricated public AuditEvent.

Scope identity and indexed identity fields are included in the versioned hash.
All callers already hold the global exclusive transaction fence. Binding a file
also emits the ordinary case AuditEvent; this internal chain exposes no route.
"""
from sqlalchemy import BigInteger, Column, ForeignKeyConstraint, LargeBinary, MetaData, String, Table, UniqueConstraint, select, update
from .audit import identifier, timestamp
from .canonical import decode_document, digest, encode_document
from .errors import FlowError
from .wire import validate

metadata = MetaData()
heads = Table("customer_scope_audit_heads", metadata,
    Column("scope_kind", String(16), primary_key=True), Column("scope_id", String(80), primary_key=True),
    Column("sequence", BigInteger, nullable=False), Column("head_hash", String(64)))
events = Table("customer_scope_audit_events", metadata,
    Column("event_id", String(80), primary_key=True), Column("scope_kind", String(16), nullable=False),
    Column("scope_id", String(80), nullable=False), Column("principal_id", String(80), nullable=False),
    Column("store_id", String(80), nullable=False), Column("sequence", BigInteger, nullable=False),
    Column("event_hash", String(64), nullable=False), Column("body", LargeBinary, nullable=False),
    ForeignKeyConstraint(["scope_kind", "scope_id"], [heads.c.scope_kind, heads.c.scope_id]),
    UniqueConstraint("scope_kind", "scope_id", "sequence", name="uq_customer_scope_audit_sequence"))

def append_scope_event(uow, scope_kind, scope_id, principal_id, store_id, *, action, actor, payload, correlation_id, now):
    if scope_kind not in {"PRINCIPAL", "EVIDENCE"}: raise FlowError("INTERNAL_ERROR")
    for value in (scope_id, principal_id, store_id, correlation_id): validate("Id", value, internal=True)
    validate("ActorProvenance", actor, internal=True)
    condition = (heads.c.scope_kind == scope_kind, heads.c.scope_id == scope_id)
    head = uow.execute(select(heads).where(*condition)).mappings().one_or_none()
    if head is None:
        uow.execute(heads.insert().values(scope_kind=scope_kind, scope_id=scope_id, sequence=0, head_hash=None))
        sequence, previous = 1, None
    else: sequence, previous = head["sequence"] + 1, head["head_hash"]
    body = {"version": 1, "event_id": identifier("scope_evt"), "scope_kind": scope_kind, "scope_id": scope_id,
            "principal_id": principal_id, "store_id": store_id, "sequence": sequence, "action": action,
            "actor": actor, "correlation_id": correlation_id, "occurred_at": timestamp(now),
            "payload_hash": digest(payload, "scope-audit-payload/v1")}
    if previous is not None: body["previous_event_hash"] = previous
    event_hash = digest(body, "scope-audit/v1"); body["event_hash"] = event_hash
    uow.execute(events.insert().values(event_id=body["event_id"], scope_kind=scope_kind, scope_id=scope_id,
        principal_id=principal_id, store_id=store_id, sequence=sequence, event_hash=event_hash, body=encode_document(body)))
    uow.execute(update(heads).where(*condition).values(sequence=sequence, head_hash=event_hash))
    return body

def verify_scope_chain(uow, scope_kind, scope_id):
    rows = uow.execute(select(events).where(events.c.scope_kind == scope_kind, events.c.scope_id == scope_id).order_by(events.c.sequence)).mappings().all()
    previous = None
    for sequence, row in enumerate(rows, 1):
        body = decode_document(row["body"]); actual = body.pop("event_hash", None)
        if (any(body.get(k) != row[k] for k in ("event_id", "scope_kind", "scope_id", "principal_id", "store_id", "sequence"))
                or body.get("scope_kind") != scope_kind or body.get("scope_id") != scope_id
                or body.get("version") != 1 or row["sequence"] != sequence
                or body.get("previous_event_hash") != previous or actual != row["event_hash"]
                or digest(body, "scope-audit/v1") != actual): return False
        previous = actual
    head = uow.execute(select(heads).where(heads.c.scope_kind == scope_kind, heads.c.scope_id == scope_id)).mappings().one_or_none()
    return head is not None and head["sequence"] == len(rows) and head["head_hash"] == previous
