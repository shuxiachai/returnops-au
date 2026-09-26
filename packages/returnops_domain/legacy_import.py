"""0002 facts imported with actual migration-time SERVICE provenance, not acceptance."""
from datetime import datetime, timezone
from hashlib import sha256
from sqlalchemy import select
from . import customer_tables as tables
from .storage import case_records, original_statement_records, original_statement_contents
from .canonical import digest, encode_document
from .audit import timestamp

def import_legacy(connection) -> None:
    now = datetime.now(timezone.utc)
    for case in connection.execute(select(case_records)).mappings():
        statement = connection.execute(select(original_statement_records).where(original_statement_records.c.case_id == case["case_id"])).mappings().one_or_none()
        content = None if statement is None else connection.execute(select(original_statement_contents).where(original_statement_contents.c.statement_id == statement["statement_id"])).mappings().one_or_none()
        complete = statement is not None and content is not None
        connection.execute(tables.case_heads.insert().values(**case, history_sequence=1 if complete else 0,
                           audit_sequence=0, audit_head=None, current_question_set_id=None, available=complete))
        if not complete:
            continue
        body = {"statement_id": statement["statement_id"], "kind": "ORIGINAL",
                "raw_text": bytes(content["raw_text"]).decode("utf-8", "surrogatepass"),
                "requested_outcome": content["requested_outcome"], "submitted_at": timestamp(statement["submitted_at"])}
        record_id = "hist_import_" + sha256((case["case_id"] + ":" + statement["statement_id"]).encode()).hexdigest()[:32]
        connection.execute(tables.history.insert().values(record_id=record_id, case_id=case["case_id"],
            kind="STATEMENT", object_id=statement["statement_id"], object_version=1, case_version=1,
            recorded_sequence=1, recorded_at=now, content_sha256=digest(body, "history/v1"),
            retention_state="AVAILABLE", removal_reason=None))
        connection.execute(tables.history_contents.insert().values(record_id=record_id, body=encode_document(body)))
        event = {"event_id": "evt_import_" + sha256(case["case_id"].encode()).hexdigest()[:32],
                 "case_id": case["case_id"], "case_version": 1, "correlation_id": "migration_0003",
                 "event_type": "INITIAL_RECORD_IMPORTED", "occurred_at": timestamp(now),
                 "object_ids": [statement["statement_id"]], "component_version": "customer-flow/v1",
                 "payload_hash": digest({"source_revision": "0002_initial_records", "case_id": case["case_id"]}, "audit-payload/v1"),
                 "actor": {"kind": "SERVICE", "component_id": "a1_storage_import"},
                 "history_refs": [{"record_id": record_id, "kind": "STATEMENT", "object_id": statement["statement_id"], "object_version": 1}]}
        event["event_hash"] = digest({"sequence": 1, "event": event}, "audit/v1")
        connection.execute(tables.audit.insert().values(event_id=event["event_id"], case_id=case["case_id"], sequence=1, event_hash=event["event_hash"], body=encode_document(event)))
        connection.execute(tables.case_heads.update().where(tables.case_heads.c.case_id == case["case_id"]).values(audit_sequence=1, audit_head=event["event_hash"]))
