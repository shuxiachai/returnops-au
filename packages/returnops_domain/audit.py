"""Versioned case audit chain in the same business transaction; no DBA resistance claim."""
from __future__ import annotations
from datetime import datetime, timezone
from secrets import token_hex
from sqlalchemy import select, update
from . import customer_tables as tables
from .canonical import digest, encode_document, decode_document
from .errors import FlowError
from .wire import validate

def identifier(prefix: str) -> str: return prefix + "_" + token_hex(16)
def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def append_event(uow, case_id: str, *, actor: dict, event_type: str, correlation_id: str,
                 payload: dict, object_ids: list[str], history_refs: list[dict], now: datetime):
    head = uow.execute(select(tables.case_heads).where(tables.case_heads.c.case_id == case_id)).mappings().one()
    sequence = head["audit_sequence"] + 1
    event = {"event_id": identifier("evt"), "case_id": case_id, "case_version": head["case_version"],
             "correlation_id": correlation_id, "event_type": event_type, "occurred_at": timestamp(now),
             "object_ids": object_ids, "component_version": "customer-flow/v1",
             "payload_hash": digest(payload, "audit-payload/v1"), "actor": actor, "history_refs": history_refs}
    if head["audit_head"] is not None: event["previous_event_hash"] = head["audit_head"]
    event["event_hash"] = digest({"sequence": sequence, "event": event}, "audit/v1")
    validate("AuditEvent", event, internal=True)
    uow.execute(tables.audit.insert().values(event_id=event["event_id"], case_id=case_id,
                sequence=sequence, event_hash=event["event_hash"], body=encode_document(event)))
    uow.execute(update(tables.case_heads).where(tables.case_heads.c.case_id == case_id).values(
                audit_sequence=sequence, audit_head=event["event_hash"]))
    return event

def verify_chain(uow, case_id: str) -> bool:
    records = uow.execute(select(tables.audit).where(tables.audit.c.case_id == case_id).order_by(tables.audit.c.sequence)).mappings().all()
    previous = None
    for sequence, record in enumerate(records, 1):
        event = decode_document(record["body"])
        validate("AuditEvent", event, internal=True)
        actual = event.pop("event_hash")
        if (event["event_id"] != record["event_id"] or event["case_id"] != record["case_id"]
                or event["case_id"] != case_id or record["sequence"] != sequence
                or event.get("previous_event_hash") != previous
                or actual != record["event_hash"] or digest({"sequence": sequence, "event": event}, "audit/v1") != actual):
            return False
        previous = actual
    head = uow.execute(select(tables.case_heads).where(tables.case_heads.c.case_id == case_id)).mappings().one_or_none()
    return head is not None and head["audit_sequence"] == len(records) and head["audit_head"] == previous
