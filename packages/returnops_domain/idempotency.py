"""Durable acceptance facts and separately erasable exact original receipts."""
from sqlalchemy import and_, select
from . import customer_tables as t
from .audit import identifier
from .canonical import decode_document, encode_document
from .errors import FlowError, ReceiptUnavailable
from .wire import validate

def lookup(uow, actor, operation, target, key, fingerprint, *, check_resource):
    validate("IdempotencyKey", key)
    fact = uow.execute(select(t.acceptances).where(t.acceptances.c.principal_id == actor.principal_id,
        t.acceptances.c.method == "POST", t.acceptances.c.operation == operation,
        t.acceptances.c.target == (target or ""), t.acceptances.c.request_key == key)).mappings().one_or_none()
    if fact is None: return None
    # Mandatory fresh resource authorization precedes the retained conflict guard.
    check_resource(fact)
    if fact["fingerprint"] != fingerprint: raise FlowError("IDEMPOTENCY_CONFLICT")
    return fact

def original_receipt(uow, fact):
    receipt = uow.execute(select(t.receipts).where(t.receipts.c.acceptance_id == fact["acceptance_id"])).mappings().one_or_none()
    if receipt is None or not receipt["available"] or receipt["body"] is None:
        raise ReceiptUnavailable()
    return fact["response_status"], decode_document(receipt["body"])

def record_acceptance(uow, actor, operation, target, key, fingerprint, resource_kind, resource_id, status, now):
    acceptance_id = identifier("accept")
    uow.execute(t.acceptances.insert().values(acceptance_id=acceptance_id, principal_id=actor.principal_id,
        store_id=actor.store_id, method="POST", operation=operation, target=target or "", request_key=key,
        fingerprint=fingerprint, resource_kind=resource_kind, resource_id=resource_id, accepted_at=now,
        response_status=status))
    return acceptance_id

def record_receipt(uow, acceptance_id, body, refs):
    uow.execute(t.receipts.insert().values(acceptance_id=acceptance_id, body=encode_document(body), available=True))
    for kind, object_id in sorted(set(refs)):
        uow.execute(t.receipt_refs.insert().values(acceptance_id=acceptance_id, kind=kind, object_id=object_id))

def view_refs(view):
    return [("CASE", view["case_id"])] + [("STATEMENT", item["statement_id"]) for item in view["statements"]] + [("EVIDENCE", item["evidence_id"]) for item in view["evidence"]]
