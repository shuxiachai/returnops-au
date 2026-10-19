from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pytest
from sqlalchemy import func,select,text,update
from returnops_domain import customer_tables as t
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry
from returnops_domain.audit import verify_chain

pytestmark=pytest.mark.database

def count(engine,table):
    with engine.connect() as c:return c.execute(select(func.count()).select_from(table)).scalar_one()

def test_create_is_submitted_original_receipt_plus_one_durable_work(flow_engine,identities):
    flow=identities.flow();request={"original_message":"  exact\n\x00\ud800 e\u0301 ","order_reference":"ref_001"}
    first=flow.create(request,"create-key-0001","corr_create")
    assert first.status==201 and not first.replayed
    assert first.body["status"]=="SUBMITTED" and first.body["case_version"]==first.body["input_version"]==1
    assert first.body["statements"][0]["raw_text"]==request["original_message"]
    assert first.body["collection_windows"]["statements"]["snapshot_id"]==first.body["collection_windows"]["evidence"]["snapshot_id"]
    with flow_engine.connect() as c:
        work=c.execute(select(t.intake_work)).mappings().one();session=c.execute(select(t.intake_sessions)).mappings().one()
        assert work["state"]=="PENDING" and work["input_version"]==1
        assert session["status"]=="SUBMITTED" and session["clarification_round"]==0 and session["current_work_id"]==work["work_id"]
    replay=flow.create(request,"create-key-0001","corr_replay")
    assert replay.replayed and replay.body==first.body
    assert count(flow_engine,t.acceptances)==count(flow_engine,t.intake_work)==1
    with CustomerUnitOfWork(flow_engine,write=False) as u:assert verify_chain(u,first.body["case_id"])

def test_get_registration_does_not_advance_case_input_audit_or_work(flow_engine,identities):
    flow=identities.flow();created=flow.create({"original_message":"Help"},"create-key-0002","corr_create").body
    before=[count(flow_engine,table) for table in (t.history,t.audit,t.intake_work,t.acceptances)]
    first=flow.get_case(created["case_id"]).body;second=flow.get_case(created["case_id"]).body
    assert first["case_version"]==second["case_version"]==created["case_version"]
    assert first["input_version"]==second["input_version"]==1
    assert first["collection_windows"]["statements"]["snapshot_id"]!=second["collection_windows"]["statements"]["snapshot_id"]
    assert before==[count(flow_engine,table) for table in (t.history,t.audit,t.intake_work,t.acceptances)]

def test_same_key_different_body_conflicts_and_scope_is_per_principal(flow_engine,identities):
    a,b=identities.flow(),identities.flow("customer_b")
    one=a.create({"original_message":"first"},"shared-key-0001","corr_one")
    with pytest.raises(FlowError) as error:a.create({"original_message":"different"},"shared-key-0001","corr_two")
    assert error.value.code=="IDEMPOTENCY_CONFLICT"
    other=b.create({"original_message":"different"},"shared-key-0001","corr_three")
    assert other.body["case_id"]!=one.body["case_id"] and count(flow_engine,t.acceptances)==2

def test_current_role_owner_store_and_session_guard_receipt_access(flow_engine,identities):
    a,b,f=identities.flow(),identities.flow("customer_b"),identities.flow("founder")
    created=a.create({"original_message":"private"},"create-key-0003","corr_one").body
    with pytest.raises(FlowError) as error:b.get_case(created["case_id"])
    assert error.value.code=="NOT_FOUND"
    with pytest.raises(FlowError) as error:f.create({"original_message":"attempt"},"founder-key-1","corr_two")
    assert error.value.code=="FORBIDDEN"
    registry=TrustedRegistry(flow_engine)
    registry.change_principal(identities.people["customer_a"]["principal_id"],store_id="store_other")
    with pytest.raises(FlowError) as error:a.create({"original_message":"DIFFERENT"},"create-key-0003","corr_three")
    assert error.value.code=="NOT_FOUND", "Current accepted-resource scope must be checked before fingerprint disclosure"
    registry.change_principal(identities.people["customer_a"]["principal_id"],store_id=identities.people["customer_a"]["store_id"])
    registry.revoke_session(identities.sessions["customer_a"]["session_id"])
    with pytest.raises(FlowError) as error:a.get_case(created["case_id"])
    assert error.value.code=="UNAUTHENTICATED"

def test_receipt_removal_keeps_acceptance_and_conflict_precedes_availability(flow_engine,identities):
    flow=identities.flow();request={"original_message":"kept acceptance"};flow.create(request,"retained-key-01","corr_one")
    with CustomerUnitOfWork(flow_engine,write=True) as u:
        u.execute(update(t.receipts).values(available=False,body=None));u.commit()
    with pytest.raises(FlowError) as unavailable:flow.create(request,"retained-key-01","corr_two")
    assert unavailable.value.code=="INVALID_STATE" and not unavailable.value.retryable and "previously accepted" in str(unavailable.value)
    with pytest.raises(FlowError) as conflict:flow.create({"original_message":"different"},"retained-key-01","corr_three")
    assert conflict.value.code=="IDEMPOTENCY_CONFLICT"
    assert count(flow_engine,t.acceptances)==count(flow_engine,t.intake_work)==1

def test_same_key_concurrent_transactions_accept_exactly_once(flow_engine,identities):
    def send(_):return identities.flow().create({"original_message":"concurrent"},"concurrent-key-1","corr_request")
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(send,range(8)))
    assert len({r.body["case_id"] for r in results})==1
    assert sum(not r.replayed for r in results)==1
    assert all(r.body==results[0].body for r in results)
    assert count(flow_engine,t.acceptances)==count(flow_engine,t.intake_work)==1

def test_history_cursor_starts_full_snapshot_and_enforces_scope_query(flow_engine,identities):
    flow=identities.flow();created=flow.create({"original_message":"original"},"history-key-01","corr_request").body
    start=created["collection_windows"]["statements"]["start_cursor"]
    page=flow.history(created["case_id"],{"kind":"STATEMENT","cursor":start}).body
    assert len(page["items"])==1 and page["items"][0]["content"]["raw_text"]=="original" and "next_cursor" not in page
    for query in ({"kind":"EVIDENCE","cursor":start},{"kind":"STATEMENT","cursor":start,"limit":21},{"kind":"STATEMENT","cursor":start+"x"}):
        with pytest.raises(FlowError) as error:flow.history(created["case_id"],query)
        assert error.value.code=="INVALID_STATE"
    empty=flow.history(created["case_id"],{"kind":"STATEMENT","object_id":"unknown_object"}).body
    assert empty["items"]==[]

def test_lookup_requires_resource_authorization_callback():
    from returnops_domain.idempotency import lookup
    with pytest.raises(TypeError):lookup(None,None,"createCase",None,"valid-key-1","fingerprint")
