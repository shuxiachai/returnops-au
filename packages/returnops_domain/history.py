"""Immutable case revisions and registered, currently authorized history snapshots."""
from __future__ import annotations
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from sqlalchemy import and_, case, func, or_, select, update
from . import customer_tables as t
from .audit import identifier, timestamp
from .canonical import decode_document, digest, encode_document
from .errors import FlowError
from .wire import validate

_CONTENT_TYPES = {"STATEMENT": "CustomerStatement", "EVIDENCE": "EvidenceAttachment", "PROCESSING_FAILURE": "ProcessingFailure"}

def append_revision(uow, case_id, kind, object_id, object_version, content, now):
    if kind not in _CONTENT_TYPES: raise FlowError("INTERNAL_ERROR")
    validate(_CONTENT_TYPES[kind], content, internal=True)
    identity_key = {"STATEMENT": "statement_id", "EVIDENCE": "evidence_id", "PROCESSING_FAILURE": "failure_id"}[kind]
    if content[identity_key] != object_id or (kind != "STATEMENT" and content["case_id"] != case_id):
        raise FlowError("INTERNAL_ERROR")
    head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
    record_id = identifier("hist"); sequence = head["history_sequence"] + 1
    uow.execute(t.history.insert().values(record_id=record_id, case_id=case_id, kind=kind,
        object_id=object_id, object_version=object_version, case_version=head["case_version"],
        recorded_sequence=sequence, recorded_at=now, content_sha256=digest(content, "history/v1"),
        retention_state="AVAILABLE", removal_reason=None))
    uow.execute(t.history_contents.insert().values(record_id=record_id, body=encode_document(content)))
    uow.execute(update(t.case_heads).where(t.case_heads.c.case_id == case_id).values(history_sequence=sequence))
    return {"record_id": record_id, "kind": kind, "object_id": object_id, "object_version": object_version}

def read_revision(uow, row):
    result = {name: row[name] for name in ("record_id", "case_id", "kind", "object_id", "object_version", "case_version", "recorded_sequence", "content_sha256", "retention_state")}
    result["recorded_at"] = timestamp(row["recorded_at"])
    if row["retention_state"] == "AVAILABLE":
        raw = uow.execute(select(t.history_contents.c.body).where(t.history_contents.c.record_id == row["record_id"])).scalar_one_or_none()
        if raw is None: raise FlowError("INTERNAL_ERROR")
        content = decode_document(raw)
        if digest(content, "history/v1") != row["content_sha256"]: raise FlowError("INTERNAL_ERROR")
        result["content"] = content
    else:
        result["removal_reason"] = row["removal_reason"]
    oracle = "CustomerHistoryRecord" if row["kind"] in {"STATEMENT", "EVIDENCE", "OUTCOME_MESSAGE"} else "FounderHistoryRecord"
    validate(oracle, result, internal=True)
    identity_key = {"STATEMENT": "statement_id", "EVIDENCE": "evidence_id", "PROCESSING_FAILURE": "failure_id"}.get(row["kind"])
    if "content" in result and identity_key and result["content"][identity_key] != row["object_id"]:
        raise FlowError("INTERNAL_ERROR")
    if "content" in result and row["kind"] in {"EVIDENCE", "PROCESSING_FAILURE"} and result["content"]["case_id"] != row["case_id"]:
        raise FlowError("INTERNAL_ERROR")
    return result

def _snapshot(uow, actor, head, now, ttl):
    snapshot = {"snapshot_id": identifier("snap"), "principal_id": actor.principal_id, "role": actor.role,
                "store_id": actor.store_id, "case_id": head["case_id"], "case_version": head["case_version"],
                "highwater": head["history_sequence"], "as_of": now, "expires_at": now + timedelta(seconds=ttl)}
    uow.execute(t.snapshots.insert().values(**snapshot))
    return snapshot

def _cursor(uow, snapshot, kind, limit, object_id=None, object_version=None, last_sequence=0, last_record_id=None):
    value = token_urlsafe(32)
    uow.execute(t.cursors.insert().values(cursor_hash=sha256(value.encode("ascii")).hexdigest(),
        snapshot_id=snapshot["snapshot_id"], kind=kind, page_limit=limit, object_id=object_id,
        object_version=object_version, last_sequence=last_sequence, last_record_id=last_record_id))
    return value

def case_view(uow, actor, case_id, now, *, snapshot_ttl=900):
    head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
    snapshot = _snapshot(uow, actor, head, now, snapshot_ttl)
    result = {name: head[name] for name in ("case_id", "case_version", "input_version", "status")}
    result.update(created_at=timestamp(head["created_at"]), updated_at=timestamp(head["updated_at"]), collection_windows={})
    for kind, field in (("STATEMENT", "statements"), ("EVIDENCE", "evidence")):
        scope = and_(t.history.c.case_id == case_id, t.history.c.kind == kind,
                     t.history.c.recorded_sequence <= snapshot["highwater"], t.history.c.case_version <= snapshot["case_version"])
        total, unavailable = uow.execute(select(func.count(), func.coalesce(func.sum(case((t.history.c.retention_state != "AVAILABLE", 1), else_=0)), 0)).where(scope)).one()
        ranked = select(t.history, func.row_number().over(partition_by=t.history.c.object_id,
                         order_by=(t.history.c.object_version.desc(), t.history.c.recorded_sequence.desc())).label("position")).where(scope).subquery()
        chosen = list(uow.execute(select(ranked).where(ranked.c.position == 1, ranked.c.retention_state == "AVAILABLE").order_by(ranked.c.recorded_sequence.desc(), ranked.c.record_id.desc()).limit(100)).mappings())
        if kind == "STATEMENT":
            from .storage import original_statement_records
            original_id = uow.execute(select(original_statement_records.c.statement_id).where(original_statement_records.c.case_id == case_id)).scalar_one_or_none()
            if original_id is not None and not any(row["object_id"] == original_id for row in chosen):
                original = uow.execute(select(ranked).where(ranked.c.position == 1, ranked.c.object_id == original_id, ranked.c.retention_state == "AVAILABLE")).mappings().one_or_none()
                if original is not None: chosen = chosen[:99] + [original]
        chosen.sort(key=lambda row: (row["recorded_sequence"], row["record_id"]))
        result[field] = [read_revision(uow, row)["content"] for row in chosen]
        result["collection_windows"][field] = {"kind": kind, "snapshot_id": snapshot["snapshot_id"],
            "snapshot_case_version": snapshot["case_version"], "total_records": total, "preview_count": len(chosen),
            "unavailable_count": unavailable, "truncated": total > len(chosen), "start_cursor": _cursor(uow, snapshot, kind, 20)}
    if head["current_question_set_id"] is not None:
        questions = uow.execute(select(t.questions).where(t.questions.c.question_set_id == head["current_question_set_id"], t.questions.c.case_id == case_id)).mappings().one_or_none()
        if questions is None or questions["input_version"] != head["input_version"]: raise FlowError("INTERNAL_ERROR")
        result["clarification"] = {"question_set_id": questions["question_set_id"], "input_version": questions["input_version"], "questions": decode_document(questions["questions"])}
    validate("CustomerCaseView", result, internal=True)
    return result

def history_page(uow, actor, case_id, query, now, *, snapshot_ttl=900):
    query = validate("CustomerHistoryQuery", query); kind = query["kind"]; limit = query.get("limit", 20)
    object_id, object_version = query.get("object_id"), query.get("object_version")
    last_sequence, last_record_id = 0, None
    if "cursor" in query:
        cursor = uow.execute(select(t.cursors).where(t.cursors.c.cursor_hash == sha256(query["cursor"].encode("ascii")).hexdigest())).mappings().one_or_none()
        if cursor is None: raise FlowError("INVALID_STATE")
        snapshot = uow.execute(select(t.snapshots).where(t.snapshots.c.snapshot_id == cursor["snapshot_id"])).mappings().one_or_none()
        if (snapshot is None or snapshot["principal_id"] != actor.principal_id or snapshot["role"] != actor.role
                or snapshot["store_id"] != actor.store_id or snapshot["case_id"] != case_id or snapshot["expires_at"] <= now
                or cursor["kind"] != kind or cursor["page_limit"] != limit
                or cursor["object_id"] != object_id or cursor["object_version"] != object_version):
            raise FlowError("INVALID_STATE")
        last_sequence, last_record_id = cursor["last_sequence"], cursor["last_record_id"]
    else:
        head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
        snapshot = _snapshot(uow, actor, head, now, snapshot_ttl)
    conditions = [t.history.c.case_id == case_id, t.history.c.kind == kind,
                  t.history.c.recorded_sequence <= snapshot["highwater"], t.history.c.case_version <= snapshot["case_version"],
                  or_(t.history.c.recorded_sequence > last_sequence, and_(t.history.c.recorded_sequence == last_sequence, t.history.c.record_id > (last_record_id or "")))]
    if object_id is not None: conditions.append(t.history.c.object_id == object_id)
    if object_version is not None: conditions.append(t.history.c.object_version == object_version)
    rows = uow.execute(select(t.history).where(*conditions).order_by(t.history.c.recorded_sequence, t.history.c.record_id).limit(limit + 1)).mappings().all()
    chosen = rows[:limit]
    page = {"case_id": case_id, "kind": kind, "snapshot_id": snapshot["snapshot_id"],
            "snapshot_case_version": snapshot["case_version"], "as_of": timestamp(snapshot["as_of"]),
            "items": [read_revision(uow, row) for row in chosen]}
    if object_id is not None: page["object_id"] = object_id
    if object_version is not None: page["object_version"] = object_version
    if len(rows) > limit:
        last = chosen[-1]
        page["next_cursor"] = _cursor(uow, snapshot, kind, limit, object_id, object_version, last["recorded_sequence"], last["record_id"])
    validate("CustomerHistoryPage", page, internal=True)
    return page
