"""Real PostgreSQL acceptance/authentication races; no timing-only lock claims.

Each test uses flow_engine's fresh owned schema. Events expose precise transaction
boundaries; pg_locks must show the particular contender PID waiting before the
holder is released. The short polling wait yields CPU only: elapsed time never
stands in for a lock observation. Thread joins and all barriers are bounded.

Transaction wrappers inject transport acknowledgement failure or hold a commit;
they do not replace CustomerFlow, F.03, SQL reads, the fence or persistence. No
case ownership/store SQL corruption is used or represented as a supported
transfer. Registry changes use only the supported TrustedRegistry methods.
"""
from concurrent.futures import Future
from datetime import datetime, timezone
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from uuid import uuid4

import jwt.api_jwt as jwt_clock_module
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from returnops_api.customer_authority import CurrentRequestAuthority
from returnops_api.security import authentication as authentication_module
from returnops_domain import customer_tables as t
from returnops_domain import customer_uow as uow_module
from returnops_domain import registry as registry_module
from returnops_domain.customer_service import CustomerFlow
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.errors import FlowError
from returnops_domain.registry import TrustedRegistry
from returnops_domain.storage import (
    case_records, original_statement_records, original_statement_contents,
)

pytestmark = pytest.mark.database
_EVENT_TIMEOUT = 4
_JOIN_TIMEOUT = 12
_CORE_TABLES = (
    case_records, original_statement_records, original_statement_contents,
    t.case_heads, t.acceptances, t.receipts, t.history, t.history_contents,
    t.audit, t.intake_sessions, t.intake_work,
)
_FACT_TABLES = _CORE_TABLES + (t.receipt_refs, t.snapshots, t.cursors)


class _Call:
    """Capture exceptions in the controlling thread, with a bounded cleanup join."""
    def __init__(self, name, operation):
        self.future = Future()

        def run():
            try:
                self.future.set_result(operation())
            except BaseException as error:
                self.future.set_exception(error)

        self.thread = Thread(name=name, target=run, daemon=True)
        self.thread.start()

    def result(self):
        assert not self.thread.is_alive(), "Result requested before bounded join"
        return self.future.result(timeout=0)


def _join(calls):
    for call in calls:
        call.thread.join(timeout=_JOIN_TIMEOUT)
    assert all(not call.thread.is_alive() for call in calls), "Race worker exceeded bounded join"


def _counts(engine):
    with engine.connect() as connection:
        return {table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
                for table in _FACT_TABLES}


def _assert_empty_admission(engine):
    assert set(_counts(engine).values()) == {0}


def _assert_single_admission(engine, expected_text, identities):
    counts = _counts(engine)
    assert all(counts[table.name] == 1 for table in _CORE_TABLES)
    with engine.connect() as connection:
        head = connection.execute(select(t.case_heads)).mappings().one()
        fact = connection.execute(select(t.acceptances)).mappings().one()
        work = connection.execute(select(t.intake_work)).mappings().one()
        stored = connection.execute(select(original_statement_contents.c.raw_text)).scalar_one()
        legacy = connection.execute(select(case_records)).mappings().one()
    assert bytes(stored).decode("utf-8", "surrogatepass") == expected_text
    assert (head["case_version"], head["input_version"], head["status"]) == (1, 1, "SUBMITTED")
    assert head["owner_principal_id"] == legacy["owner_principal_id"] == identities.people["customer_a"]["principal_id"]
    assert head["store_id"] == legacy["store_id"] == identities.people["customer_a"]["store_id"]
    assert fact["resource_id"] == work["case_id"] == head["case_id"]
    assert fact["acceptance_id"] == work["acceptance_id"]
    assert work["state"] == "PENDING", "Recovery/replay must not execute the accepted processor work"


def _denied(operation, code):
    with pytest.raises(FlowError) as caught:
        operation()
    assert caught.value.code == code
    assert caught.value.status == {"NOT_FOUND": 404, "UNAUTHENTICATED": 401,
                                   "IDEMPOTENCY_CONFLICT": 409}[code]
    assert not caught.value.retryable
    assert caught.value.envelope("corr_race")["error"]["details"] == []


def _fence_probe(monkeypatch, contender_name):
    attempted, acquired = Event(), Event()
    state = {}
    actual = uow_module.acquire_fence

    def observe(connection, *, write):
        is_contender = current_thread().name == contender_name
        if is_contender:
            state["pid"] = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            attempted.set()
        actual(connection, write=write)
        if is_contender:
            acquired.set()

    monkeypatch.setattr(uow_module, "acquire_fence", observe)
    return attempted, acquired, state


def _assert_waiting_on_fence(engine, probe):
    attempted, acquired, state = probe
    assert attempted.wait(_EVENT_TIMEOUT), "Contender did not reach its real fence request"
    deadline = monotonic() + 3
    poll_yield = Event()
    with engine.connect() as observer:
        while monotonic() < deadline:
            waiting = observer.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE pid=:pid "
                "AND locktype='advisory' AND NOT granted)"
            ), {"pid": state["pid"]}).scalar_one()
            if waiting:
                assert not acquired.is_set()
                return
            poll_yield.wait(0.01)
    pytest.fail("The exact contender PID never entered an advisory-lock wait", pytrace=False)


def _commit_barrier(ready, release):
    class HeldCommit(CustomerUnitOfWork):
        def commit(self):
            if self.write:
                ready.set()
                assert release.wait(8), "Controller did not release the held real transaction"
            super().commit()
    return HeldCommit


def _fault_once(mode):
    state = {"armed": True, "faults": 0, "transactions": []}

    class CommitBoundary:
        def __init__(self, transaction):
            self.transaction = transaction

        def commit(self):
            if mode == "committed-ack-loss":
                self.transaction.commit()
            else:
                self.transaction.rollback()
            state["faults"] += 1
            raise SQLAlchemyError("Synthetic commit acknowledgement failure")

    class FaultingUnitOfWork(CustomerUnitOfWork):
        def __enter__(self):
            result = super().__enter__()
            transaction_id = self.connection.execute(text("SELECT txid_current()")).scalar_one()
            state["transactions"].append((self.write, transaction_id))
            if self.write and state["armed"]:
                state["armed"] = False
                self.transaction = CommitBoundary(self.transaction)
            return result

    return FaultingUnitOfWork, state


def test_committed_ack_loss_recovers_original_key_in_fresh_transaction(flow_engine, identities):
    factory, fault = _fault_once("committed-ack-loss")
    flow = identities.flow(uow_factory=factory)
    request = {"original_message": "  committed original\x00\ud800  "}
    recovered = flow.create(request, "ack-loss-original-key", "corr_ack_loss")
    assert recovered.status == 201 and recovered.replayed
    assert recovered.body["statements"][0]["raw_text"] == request["original_message"]
    assert fault["faults"] == 1
    assert [write for write, _ in fault["transactions"][:2]] == [True, False]
    assert fault["transactions"][0][1] != fault["transactions"][1][1]
    before = _counts(flow_engine)
    replay = flow.create(request, "ack-loss-original-key", "corr_ack_replay")
    assert replay.replayed and replay.body == recovered.body
    assert _counts(flow_engine) == before
    _assert_single_admission(flow_engine, request["original_message"], identities)


def test_rollback_before_commit_never_invents_acceptance_then_same_key_can_retry(flow_engine, identities):
    factory, fault = _fault_once("rollback-before-commit")
    flow = identities.flow(uow_factory=factory)
    request = {"original_message": "original after uncertain rollback"}
    with pytest.raises(FlowError) as uncertain:
        flow.create(request, "rollback-original-key", "corr_rollback")
    assert (uncertain.value.code, uncertain.value.status, uncertain.value.retryable) == ("INTERNAL_ERROR", 503, True)
    assert fault["faults"] == 1
    assert [write for write, _ in fault["transactions"]] == [True, False]
    assert fault["transactions"][0][1] != fault["transactions"][1][1]
    _assert_empty_admission(flow_engine)
    accepted = flow.create(request, "rollback-original-key", "corr_retry")
    assert accepted.status == 201 and not accepted.replayed
    replay = flow.create(request, "rollback-original-key", "corr_replay")
    assert replay.replayed and replay.body == accepted.body
    _assert_single_admission(flow_engine, request["original_message"], identities)


def test_concurrent_different_body_same_key_commits_only_first_intent(flow_engine, identities, monkeypatch):
    ready, release = Event(), Event()
    contender_name = "different-body-" + uuid4().hex
    probe = _fence_probe(monkeypatch, contender_name)
    first_flow = identities.flow(uow_factory=_commit_barrier(ready, release))
    calls = []
    try:
        first = _Call("first-intent", lambda: first_flow.create(
            {"original_message": "first immutable intent"}, "race-same-key", "corr_first"))
        calls.append(first)
        assert ready.wait(_EVENT_TIMEOUT)
        second = _Call(contender_name, lambda: identities.flow().create(
            {"original_message": "different losing intent"}, "race-same-key", "corr_second"))
        calls.append(second)
        _assert_waiting_on_fence(flow_engine, probe)
        assert not second.future.done()
        _assert_empty_admission(flow_engine)
    finally:
        release.set()
        _join(calls)
    accepted = first.result()
    assert accepted.status == 201 and not accepted.replayed
    _denied(second.result, "IDEMPOTENCY_CONFLICT")
    assert probe[1].is_set()
    _assert_single_admission(flow_engine, "first immutable intent", identities)
    replay = identities.flow().create({"original_message": "first immutable intent"}, "race-same-key", "corr_replay")
    assert replay.replayed and replay.body == accepted.body


def _change_registry(registry, identities, change):
    principal = identities.people["customer_a"]["principal_id"]
    if change == "store":
        registry.change_principal(principal, store_id="store_changed")
    elif change == "disable":
        registry.change_principal(principal, enabled=False)
    else:
        registry.revoke_session(identities.sessions["customer_a"]["session_id"])


def _assert_registry_changed(engine, identities, change):
    with engine.connect() as connection:
        principal = connection.execute(select(t.principals).where(
            t.principals.c.principal_id == identities.people["customer_a"]["principal_id"])).mappings().one()
        session = connection.execute(select(t.sessions).where(
            t.sessions.c.session_id == identities.sessions["customer_a"]["session_id"])).mappings().one()
    if change == "store":
        assert principal["store_id"] == "store_changed"
    elif change == "disable":
        assert principal["enabled"] is False
    else:
        assert session["revoked"] is True


@pytest.mark.parametrize("change,denial", [("store", "NOT_FOUND"), ("disable", "UNAUTHENTICATED"),
                                          ("revoke", "UNAUTHENTICATED")])
def test_registry_change_waits_for_acceptance_fence_then_replay_uses_current_authority(
        flow_engine, identities, monkeypatch, change, denial):
    ready, release = Event(), Event()
    contender_name = "registry-contender-" + uuid4().hex
    probe = _fence_probe(monkeypatch, contender_name)
    flow = identities.flow(uow_factory=_commit_barrier(ready, release))
    request = {"original_message": "accepted before registry change"}
    calls = []
    try:
        admission = _Call("accepted-holder", lambda: flow.create(request, "authority-race-key", "corr_admit"))
        calls.append(admission)
        assert ready.wait(_EVENT_TIMEOUT)
        change_call = _Call(contender_name, lambda: _change_registry(TrustedRegistry(flow_engine), identities, change))
        calls.append(change_call)
        _assert_waiting_on_fence(flow_engine, probe)
        assert not change_call.future.done()
        _assert_empty_admission(flow_engine)
    finally:
        release.set()
        _join(calls)
    assert admission.result().status == 201
    change_call.result()
    _assert_registry_changed(flow_engine, identities, change)
    before = _counts(flow_engine)
    # Authority/resource denial precedes different-body fingerprint disclosure.
    _denied(lambda: identities.flow().create({"original_message": "different"},
            "authority-race-key", "corr_denied"), denial)
    assert _counts(flow_engine) == before
    _assert_single_admission(flow_engine, request["original_message"], identities)


@pytest.mark.parametrize("change,denial", [("store", "NOT_FOUND"), ("disable", "UNAUTHENTICATED"),
                                          ("revoke", "UNAUTHENTICATED")])
def test_waiting_replay_reads_committed_registry_change_before_receipt_or_fingerprint(
        flow_engine, identities, monkeypatch, change, denial):
    request = {"original_message": "existing private acceptance"}
    identities.flow().create(request, "waiting-replay-key", "corr_original")
    before = _counts(flow_engine)
    ready, release = Event(), Event()
    contender_name = "replay-contender-" + uuid4().hex
    probe = _fence_probe(monkeypatch, contender_name)
    # Only the trusted registry adapter uses this held UoW; CustomerFlow stays real.
    monkeypatch.setattr(registry_module, "CustomerUnitOfWork", _commit_barrier(ready, release))
    calls = []
    try:
        mutation = _Call("registry-holder", lambda: _change_registry(TrustedRegistry(flow_engine), identities, change))
        calls.append(mutation)
        assert ready.wait(_EVENT_TIMEOUT)
        replay = _Call(contender_name, lambda: identities.flow().create(
            {"original_message": "different body"}, "waiting-replay-key", "corr_waiting"))
        calls.append(replay)
        _assert_waiting_on_fence(flow_engine, probe)
        assert not replay.future.done()
        assert _counts(flow_engine) == before
    finally:
        release.set()
        _join(calls)
    mutation.result()
    _denied(replay.result, denial)
    _assert_registry_changed(flow_engine, identities, change)
    assert _counts(flow_engine) == before
    _assert_single_admission(flow_engine, request["original_message"], identities)


def test_token_expiring_during_observed_fence_wait_is_rechecked_before_any_admission(
        flow_engine, identities, monkeypatch):
    expires = identities.sessions["customer_a"]["expires_at"]
    clock_lock = Lock()
    clock = [datetime.fromtimestamp(expires - 10, timezone.utc)]

    def now():
        with clock_lock:
            return clock[0]

    class ControlledDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = now()
            return value.replace(tzinfo=None) if tz is None else value.astimezone(tz)

    # Advance both genuine PyJWT claim-time validation and F.03's post-registry
    # freshness check. Signature, issuer, audience, session and role stay real.
    monkeypatch.setattr(jwt_clock_module, "datetime", ControlledDatetime)
    monkeypatch.setattr(authentication_module, "datetime", ControlledDatetime)
    authority = CurrentRequestAuthority(identities.auth_config,
        "Bearer " + identities.tokens["customer_a"], clock=now)
    flow = CustomerFlow(flow_engine, authority, clock=now)
    assert flow.preflight("createCase").principal_id == identities.people["customer_a"]["principal_id"]
    contender_name = "expiry-contender-" + uuid4().hex
    probe = _fence_probe(monkeypatch, contender_name)
    calls = []
    try:
        with CustomerUnitOfWork(flow_engine, write=True) as holder:
            contender = _Call(contender_name, lambda: flow.create(
                {"original_message": "must not be accepted"}, "expired-wait-key", "corr_expired"))
            calls.append(contender)
            _assert_waiting_on_fence(flow_engine, probe)
            assert not contender.future.done()
            with clock_lock:
                clock[0] = datetime.fromtimestamp(expires + 1, timezone.utc)
            holder.commit()
    finally:
        _join(calls)
    _denied(contender.result, "UNAUTHENTICATED")
    assert probe[1].is_set()
    _assert_empty_admission(flow_engine)
