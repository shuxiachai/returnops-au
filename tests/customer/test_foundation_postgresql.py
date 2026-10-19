from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
import time
from uuid import uuid4
import pytest
from sqlalchemy import select, text, update
from returnops_domain.storage import InitialRecordUnitOfWork, InitialRecordRepository, case_records, original_statement_records, original_statement_contents
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain import customer_tables as tables
from returnops_domain.audit import append_event, verify_chain

pytestmark = pytest.mark.database

def test_two_legacy_read_then_write_transactions_do_not_upgrade_shared_locks(customer_engine, initial_bundle):
    first_read = Event(); release_first = Event(); second_read = Event()
    suffix = uuid4().hex; second_id = "case_" + suffix; statement_id = "stmt_" + suffix
    second = replace(initial_bundle, case=replace(initial_bundle.case, case_id=second_id),
                     statement=replace(initial_bundle.statement, case_id=second_id, statement_id=statement_id),
                     content=replace(initial_bundle.content, statement_id=statement_id))
    def run_first():
        with InitialRecordUnitOfWork(customer_engine) as uow:
            assert uow.repository.load_initial_record(initial_bundle.case.case_id) is None
            first_read.set(); assert release_first.wait(5)
            uow.repository.insert_initial_record(initial_bundle); uow.commit()
    def run_second():
        assert first_read.wait(5)
        with InitialRecordUnitOfWork(customer_engine) as uow:
            assert uow.repository.load_initial_record(second.case.case_id) is None
            second_read.set(); uow.repository.insert_initial_record(second); uow.commit()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(run_first); two = pool.submit(run_second)
            try:
                assert first_read.wait(5)
                deadline = time.monotonic() + 4; blocked = False
                while time.monotonic() < deadline:
                    with customer_engine.connect() as observer:
                        blocked = bool(observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted AND database=(SELECT oid FROM pg_database WHERE datname=current_database()))")).scalar_one())
                    if blocked: break
                    time.sleep(0.01)
                assert blocked and not second_read.is_set(), "Write-capable transactions must serialize before their first read"
            finally: release_first.set()
            one.result(timeout=5); two.result(timeout=5)
        with InitialRecordUnitOfWork(customer_engine) as uow:
            assert uow.repository.load_initial_record(initial_bundle.case.case_id) == initial_bundle
            assert uow.repository.load_initial_record(second.case.case_id) == second
    finally:
        # Remove only this test's explicitly generated records under the same fence.
        with CustomerUnitOfWork(customer_engine, write=True) as uow:
            for bundle in (initial_bundle, second):
                uow.execute(original_statement_contents.delete().where(original_statement_contents.c.statement_id==bundle.statement.statement_id))
                uow.execute(original_statement_records.delete().where(original_statement_records.c.statement_id==bundle.statement.statement_id))
                uow.execute(case_records.delete().where(case_records.c.case_id==bundle.case.case_id))
            uow.commit()

@pytest.mark.parametrize("tamper", ["row-event-id", "body-event-id", "body-case-id"], ids=["row-event-id","body-event-id","body-case-id"])
def test_audit_chain_binds_row_and_body_identity(customer_engine, initial_bundle, tamper):
    from returnops_domain.canonical import decode_document, encode_document
    with CustomerUnitOfWork(customer_engine, write=True) as uow:
        InitialRecordRepository(uow.connection,uow.poison).insert_initial_record(initial_bundle)
        c=initial_bundle.case
        uow.execute(tables.case_heads.insert().values(case_id=c.case_id,owner_principal_id=c.owner_principal_id,store_id=c.store_id,
                    case_version=1,input_version=1,status="SUBMITTED",created_at=c.created_at,updated_at=c.updated_at,
                    history_sequence=0,audit_sequence=0,audit_head=None,current_question_set_id=None,available=True))
        event=append_event(uow,c.case_id,actor={"kind":"SERVICE","component_id":"test_harness"},event_type="CASE_TEST_CREATED",
                           correlation_id="corr_test",payload={"test":True},object_ids=[],history_refs=[],now=c.created_at)
        assert verify_chain(uow,c.case_id)
        if tamper=="row-event-id":
            uow.execute(update(tables.audit).where(tables.audit.c.event_id==event["event_id"]).values(event_id="evt_tampered"))
        else:
            event["event_id" if tamper=="body-event-id" else "case_id"]="other_identity"
            uow.execute(update(tables.audit).where(tables.audit.c.event_id==uow.execute(select(tables.audit.c.event_id).where(tables.audit.c.case_id==c.case_id)).scalar_one()).values(body=encode_document(event)))
        assert not verify_chain(uow,c.case_id)
        # No commit: this test's simulated tampering and generated rows roll back.
