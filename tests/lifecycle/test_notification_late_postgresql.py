"""Cloud-only modern late observations, using reachable real producers.

Actual cloud execution is required; this file is not an acceptance record.
No synthetic post-execution reject/manual transition is a modern acceptance.
"""
from contextlib import contextmanager
from dataclasses import asdict
import pytest
from sqlalchemy import update
from returnops_domain import customer_tables as old, lifecycle_tables as life
from returnops_domain.customer_uow import CustomerUnitOfWork
from returnops_domain.notification_mock import CoreMockNotification
from returnops_domain.notification_profile import COMPONENT
from returnops_domain.notification_tables import controls, facts
from returnops_domain.retention import RetentionService
from notification_helpers import ready, service, rows, snapshot, evidence, pdf_call_counts
from test_notification_delivery_postgresql import LostReply, NoEffect, NoSend


KINDS = ["return", "reject", "manual_pass", "manual_block"]
TERMINAL = {"RETURN_CREATED": "COMPLETED", "REJECTED": "REJECTED", "MANUAL_HANDLED": "MANUAL_HANDLED"}
IDENTITY = (
    "notification_work_id", "notification_id", "case_id", "store_id", "owner_id",
    "logical_key", "outcome", "producer_id", "outcome_record_id", "outcome_event_id",
    "initial_notification_record_id", "profile", "channel", "profile_hash",
    "payload_hash", "source_hash", "intent_hash", "intent_core", "input_version",
    "generation", "created_at",
)
EFFECT_TABLES = (
    "lifecycle_effect_refs", "core_mock_return_ledger", "core_mock_label_ledger",
    "generated_label_artifact_contents", "generated_label_artifacts",
)
FORBIDDEN_PDF = ("render", "text_line", "assembly", "expected_pdf",
                 "return_provider", "label_provider", "artifact_retrieval")


def control_for(engine, setup):
    found = [row for row in rows(engine, controls) if row["notification_work_id"] == setup["work_id"]]
    assert len(found) == 1
    return found[0]


def head_for(engine, setup):
    found = [row for row in rows(engine, old.case_heads) if row["case_id"] == setup["case_id"]]
    assert len(found) == 1
    return found[0]


def fact_for(engine, setup):
    found = [row for row in rows(engine, facts) if row["notification_work_id"] == setup["work_id"]]
    assert len(found) == 1
    return found[0]


def same_identity(control, original):
    assert {name: control[name] for name in IDENTITY} == {name: original[name] for name in IDENTITY}


@contextmanager
def notification_calls(monkeypatch):
    """Count real base calls; no call is replaced with a synthetic result."""
    calls = {"deliver": 0, "_insert": 0, "query": 0}
    with monkeypatch.context() as patch:
        for name in calls:
            original = getattr(CoreMockNotification, name)
            def wrapped(self, *args, _name=name, _original=original, **kwargs):
                calls[_name] += 1
                return _original(self, *args, **kwargs)
            patch.setattr(CoreMockNotification, name, wrapped)
        yield calls


class LateQuery(CoreMockNotification):
    """Query and close for real, then run a real winner before returning its fact."""
    def __init__(self, engine, action, calls):
        self.query_closed = []
        self.returned = []
        self.forbidden_sends = []
        self.after_action = None
        self.after_action_calls = None
        self.action = action
        self.calls = calls
        owner = self
        class QueryUow(CustomerUnitOfWork):
            def __exit__(self, *args):
                result = super().__exit__(*args)
                owner.query_closed.append(self.connection.closed)
                return result
        super().__init__(engine, uow_factory=QueryUow)

    def deliver(self, reservation_id):
        self.forbidden_sends.append(reservation_id)
        pytest.fail("Late observation invoked a sender")

    def query(self, reservation_id):
        assert not self.returned, "The original observation must query exactly once"
        found = super().query(reservation_id)
        assert found is not None and found["reservation_id"] == reservation_id
        assert self.query_closed == [True], "Race must start after the real query UoW closes"
        self.returned.append(dict(found))
        replacement = self.action(found)
        self.after_action = snapshot(self.engine)
        self.after_action_calls = dict(self.calls)
        # Only the explicit other-case port-fault test supplies a replacement.
        return found if replacement is None else replacement


def unknown_after_real_t2(engine, identities, setup, monkeypatch):
    with notification_calls(monkeypatch) as calls:
        unknown = service(engine, identities, mock=LostReply(engine)).send(setup["work_id"])
    assert unknown.status == "UNKNOWN", asdict(unknown)
    assert calls == {"deliver": 1, "_insert": 1, "query": 0}
    original = fact_for(engine, setup)
    control = control_for(engine, setup)
    assert original["status"] == "SENT" and original["reservation_id"] == control["reservation_id"]
    assert control["accepted_fact_id"] is None and control["attempt_count"] == 1
    return original


def assert_stale_is_read_only(engine, setup, adapter, calls, pdf):
    assert len(adapter.returned) == 1 and adapter.query_closed == [True]
    assert adapter.forbidden_sends == []
    assert snapshot(engine) == adapter.after_action
    assert calls == adapter.after_action_calls
    assert all(pdf[name] == 0 for name in FORBIDDEN_PDF)
    same_identity(control_for(engine, setup), setup["control"])


@pytest.mark.parametrize("kind", KINDS)
def test_modern_lost_reply_recovers_original_fact_without_replaying_business(
        flow_engine, identities, enabled, request, monkeypatch, kind):
    setup = ready(flow_engine, identities, kind)
    original_fact = unknown_after_real_t2(flow_engine, identities, setup, monkeypatch)
    original_control = control_for(flow_engine, setup)
    before = snapshot(flow_engine)
    original_events = [row for row in rows(flow_engine, life.events)
                       if row["case_id"] == setup["case_id"] and row["event_kind"] == "NOTIFICATION"]
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, lambda fact: None, calls)
        recovered = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert recovered.status == "SENT", asdict(recovered)
    assert calls == {"deliver": 0, "_insert": 0, "query": 1}
    assert adapter.returned == [original_fact] and adapter.query_closed == [True]
    assert not adapter.forbidden_sends and all(pdf[name] == 0 for name in FORBIDDEN_PDF)
    assert fact_for(flow_engine, setup) == original_fact
    control = control_for(flow_engine, setup)
    same_identity(control, setup["control"])
    assert control["reservation_id"] == original_control["reservation_id"]
    assert control["reservation_epoch"] == original_control["reservation_epoch"]
    assert control["attempt_count"] == 1 and control["accepted_fact_id"] == original_fact["fact_id"]
    assert control["accepted_record_id"] and control["accepted_event_id"]
    assert head_for(flow_engine, setup)["status"] == TERMINAL[control["outcome"]]
    accepted = [row for row in rows(flow_engine, life.events)
                if row["case_id"] == setup["case_id"] and row["event_kind"] == "NOTIFICATION"]
    assert len(accepted) == len(original_events) + 1
    assert any(row["event_id"] == control["accepted_event_id"]
               and row["record_id"] == control["accepted_record_id"] for row in accepted)
    messages = [row for row in rows(flow_engine, old.history)
                if row["case_id"] == setup["case_id"] and row["kind"] == "OUTCOME_MESSAGE"]
    assert len(messages) == 1
    after = snapshot(flow_engine)
    assert all(after[name] == before[name] for name in EFFECT_TABLES)
    evidence(request.node.nodeid, kind=kind, result=asdict(recovered), before=before, after=after,
             fact_id=original_fact["fact_id"], fact_hash=original_fact["fact_hash"],
             notification_calls=calls, pdf_calls=pdf)


@pytest.mark.parametrize("kind", KINDS)
def test_real_t3_winner_before_late_query_return_keeps_exact_winner(
        flow_engine, identities, enabled, request, monkeypatch, kind):
    setup = ready(flow_engine, identities, kind)
    original_fact = unknown_after_real_t2(flow_engine, identities, setup, monkeypatch)
    winners = []
    def winner(found):
        assert found == original_fact
        accepted = service(flow_engine, identities).reconcile(setup["work_id"])
        assert accepted.status == "SENT", asdict(accepted)
        winners.append(asdict(accepted))
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, winner, calls)
        late = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert len(winners) == 1 and asdict(late) == winners[0]
    assert calls == {"deliver": 0, "_insert": 0, "query": 2}
    assert_stale_is_read_only(flow_engine, setup, adapter, calls, pdf)
    assert fact_for(flow_engine, setup) == original_fact
    control = control_for(flow_engine, setup)
    assert control["accepted_fact_id"] == original_fact["fact_id"] and control["attempt_count"] == 1
    assert head_for(flow_engine, setup)["status"] == TERMINAL[control["outcome"]]
    evidence(request.node.nodeid, kind=kind, winner=winners[0], late=asdict(late),
             after_winner=adapter.after_action, after_late=snapshot(flow_engine),
             notification_calls=calls, pdf_calls=pdf)


@pytest.mark.parametrize("winner_state", ["READY", "RESERVED", "SENT"])
def test_old_no_effect_fact_after_real_founder_retry_cannot_downgrade_winner(
        flow_engine, identities, enabled, request, monkeypatch, winner_state):
    setup = ready(flow_engine, identities, "reject")
    failed = service(flow_engine, identities, mock=NoEffect(flow_engine)).send(setup["work_id"])
    assert failed.status == "NO_EFFECT_FAILED", asdict(failed)
    original_fact = fact_for(flow_engine, setup)
    assert original_fact["status"] == "NO_EFFECT_FAILED"
    original_control = control_for(flow_engine, setup)
    assert original_control["accepted_fact_id"] == original_fact["fact_id"]
    winners = []
    def retry_and_advance(found):
        assert found == original_fact
        version = head_for(flow_engine, setup)["case_version"]
        retried = service(flow_engine, identities).retry(setup["work_id"], version)
        assert retried.status == "READY", asdict(retried)
        if winner_state != "READY":
            mock = NoSend(flow_engine) if winner_state == "RESERVED" else CoreMockNotification(flow_engine)
            advanced = service(flow_engine, identities, mock=mock).send(setup["work_id"])
            assert advanced.status == ("UNKNOWN" if winner_state == "RESERVED" else "SENT")
        control = control_for(flow_engine, setup)
        assert control["state"] == winner_state
        winners.append(control)
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, retry_and_advance, calls)
        late = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert late.status == ("READY" if winner_state == "READY" else "UNKNOWN"), asdict(late)
    assert len(winners) == 1
    assert_stale_is_read_only(flow_engine, setup, adapter, calls, pdf)
    control = control_for(flow_engine, setup)
    assert control == winners[0]
    assert control["attempt_count"] == (1 if winner_state == "READY" else 2)
    assert (control["reservation_id"] == original_control["reservation_id"]) == (winner_state == "READY")
    all_facts = sorted([row for row in rows(flow_engine, facts)
                        if row["notification_work_id"] == setup["work_id"]], key=lambda row: row["attempt_count"])
    assert all_facts[0] == original_fact
    assert [row["status"] for row in all_facts] == (["NO_EFFECT_FAILED", "SENT"]
                                                   if winner_state == "SENT" else ["NO_EFFECT_FAILED"])
    if winner_state == "SENT":
        assert control["accepted_fact_id"] == all_facts[1]["fact_id"]
        assert head_for(flow_engine, setup)["status"] == "REJECTED"
    evidence(request.node.nodeid, winner_state=winner_state, late=asdict(late),
             after_winner=adapter.after_action, after_late=snapshot(flow_engine),
             notification_calls=calls, pdf_calls=pdf)


def test_actual_other_case_fact_port_fault_cannot_accept_either_scope(
        flow_engine, identities, enabled, request, monkeypatch):
    setup = ready(flow_engine, identities, "manual_block")
    original_fact = unknown_after_real_t2(flow_engine, identities, setup, monkeypatch)
    other = ready(flow_engine, identities, "reject")
    other_fact = unknown_after_real_t2(flow_engine, identities, other, monkeypatch)
    assert other["case_id"] != setup["case_id"]
    assert other_fact["notification_work_id"] != original_fact["notification_work_id"]
    before = snapshot(flow_engine)
    def wrong_port_fact(found):
        assert found == original_fact
        assert fact_for(flow_engine, other) == other_fact
        return dict(other_fact)
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, wrong_port_fact, calls)
        late = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert late.status == "UNKNOWN", asdict(late)
    assert_stale_is_read_only(flow_engine, setup, adapter, calls, pdf)
    assert snapshot(flow_engine) == before
    assert fact_for(flow_engine, setup) == original_fact and fact_for(flow_engine, other) == other_fact
    assert control_for(flow_engine, setup)["accepted_fact_id"] is None
    assert control_for(flow_engine, other)["accepted_fact_id"] is None
    evidence(request.node.nodeid, actual_other_case_port_fault=True, late=asdict(late),
             before=before, after=snapshot(flow_engine), notification_calls=calls, pdf_calls=pdf)


@pytest.mark.parametrize("revoked", ["service_grant", "owner_principal"])
def test_real_current_authority_revocation_after_query_blocks_late_acceptance(
        flow_engine, identities, enabled, request, monkeypatch, revoked):
    setup = ready(flow_engine, identities, "manual_pass")
    original_fact = unknown_after_real_t2(flow_engine, identities, setup, monkeypatch)
    status = head_for(flow_engine, setup)["status"]
    def revoke(found):
        assert found == original_fact
        with CustomerUnitOfWork(flow_engine, write=True) as uow:
            if revoked == "service_grant":
                changed = uow.execute(update(life.authorities).where(
                    life.authorities.c.component_id == COMPONENT,
                    life.authorities.c.purpose == "NOTIFICATION",
                    life.authorities.c.store_id == setup["control"]["store_id"]
                ).values(enabled=False, revision=life.authorities.c.revision + 1))
            else:
                changed = uow.execute(update(old.principals).where(
                    old.principals.c.principal_id == setup["control"]["owner_id"]).values(enabled=False))
            assert changed.rowcount == 1
            uow.commit()
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, revoke, calls)
        late = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert late.status == "UNKNOWN", asdict(late)
    assert_stale_is_read_only(flow_engine, setup, adapter, calls, pdf)
    assert fact_for(flow_engine, setup) == original_fact
    assert control_for(flow_engine, setup)["accepted_fact_id"] is None
    assert head_for(flow_engine, setup)["status"] == status
    evidence(request.node.nodeid, revoked=revoked, late=asdict(late),
             after_revocation=adapter.after_action, after_late=snapshot(flow_engine),
             notification_calls=calls, pdf_calls=pdf)


@pytest.mark.parametrize("removed", ["pdf", "statement"])
def test_real_retention_after_query_cannot_resurrect_content_or_accept_late_fact(
        flow_engine, identities, enabled, request, monkeypatch, removed):
    setup = ready(flow_engine, identities, "return")
    original_fact = unknown_after_real_t2(flow_engine, identities, setup, monkeypatch)
    status = head_for(flow_engine, setup)["status"]
    if removed == "pdf":
        object_id, kind = setup["artifact"].label_evidence_id, "EVIDENCE"
    else:
        original = [row for row in rows(flow_engine, old.history)
                    if row["case_id"] == setup["case_id"] and row["kind"] == "STATEMENT"]
        assert original
        object_id, kind = original[0]["object_id"], "STATEMENT"
    def retain(found):
        assert found == original_fact
        assert RetentionService(flow_engine).remove(kind, object_id)
    with notification_calls(monkeypatch) as calls, pdf_call_counts() as pdf:
        adapter = LateQuery(flow_engine, retain, calls)
        late = service(flow_engine, identities, mock=adapter).reconcile(setup["work_id"])
    assert late.status == "UNKNOWN", asdict(late)
    assert_stale_is_read_only(flow_engine, setup, adapter, calls, pdf)
    assert fact_for(flow_engine, setup) == original_fact
    control = control_for(flow_engine, setup)
    assert control["state"] == "RETAINED" and not control["available"]
    assert control["source_manifest"] is None and control["accepted_fact_id"] is None
    assert head_for(flow_engine, setup)["status"] == status
    derivatives = [row for row in rows(flow_engine, old.history)
                   if row["case_id"] == setup["case_id"] and row["kind"] in {"NOTIFICATION", "OUTCOME_MESSAGE"}]
    assert derivatives and all(row["retention_state"] != "AVAILABLE" for row in derivatives)
    removed_ids = {row["record_id"] for row in derivatives}
    assert not any(row["record_id"] in removed_ids for row in rows(flow_engine, old.history_contents))
    evidence(request.node.nodeid, removed=removed, late=asdict(late),
             after_retention=adapter.after_action, after_late=snapshot(flow_engine),
             notification_calls=calls, pdf_calls=pdf)
