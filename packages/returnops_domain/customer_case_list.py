"""The signed-in customer's own cases, newest first (31 October 2026; outside contract v1).

Read only. CustomerFlow.list_cases authorises every listed case again exactly as a
single-case read; a summary carries the case head and the start of the customer's own
original statement, never shop data, facts or another customer's case.
"""
from __future__ import annotations
from sqlalchemy import select
from . import customer_tables as t
from .audit import timestamp
from .history import read_revision
from .wire import validate

LIST_LIMIT = 20
EXCERPT_CHARACTERS = 120


def own_case_ids(uow, actor, limit=LIST_LIMIT):
    heads = t.case_heads.c
    return list(uow.execute(select(heads.case_id).where(heads.owner_principal_id == actor.principal_id,
        heads.store_id == actor.store_id, heads.available.is_(True))
        .order_by(heads.created_at.desc(), heads.case_id.desc()).limit(limit)).scalars())


def case_summary(uow, case_id, *, prove=False):
    head = uow.execute(select(t.case_heads).where(t.case_heads.c.case_id == case_id)).mappings().one()
    if prove:
        # The same stored-chain check as a single-case read on an artifact schema.
        from .founder_integrity import CaseProof
        CaseProof(uow, head)
    result = {"case_id": head["case_id"], "status": head["status"], "created_at": timestamp(head["created_at"]),
              "updated_at": timestamp(head["updated_at"]), "awaiting_answer": head["current_question_set_id"] is not None}
    from .storage import original_statement_records
    original_id = uow.execute(select(original_statement_records.c.statement_id)
        .where(original_statement_records.c.case_id == case_id)).scalar_one_or_none()
    if original_id is not None:
        # The newest revision of the original statement, read only while it is still available.
        row = uow.execute(select(t.history).where(t.history.c.case_id == case_id, t.history.c.kind == "STATEMENT",
            t.history.c.object_id == original_id).order_by(t.history.c.object_version.desc(),
            t.history.c.recorded_sequence.desc()).limit(1)).mappings().one_or_none()
        if row is not None and row["retention_state"] == "AVAILABLE":
            content = read_revision(uow, row)["content"]
            text = " ".join(content["raw_text"].split())
            if text:
                result["excerpt"] = text if len(text) <= EXCERPT_CHARACTERS else text[:EXCERPT_CHARACTERS].rstrip() + "..."
            if content.get("requested_outcome") is not None:
                validate("RequestedOutcome", content["requested_outcome"], internal=True)
                result["requested_outcome"] = content["requested_outcome"]
    validate("Id", result["case_id"], internal=True)
    validate("CaseStatus", result["status"], internal=True)
    validate("Timestamp", result["created_at"], internal=True)
    validate("Timestamp", result["updated_at"], internal=True)
    return result
