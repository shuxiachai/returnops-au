"""A3 sandbox carrier adapter without a database (OF-004; FR-010, UC-04, NFR-004, NFR-007).

docs/49-a3-carrier-sandbox.md. The adapter's ``_outcome`` and HTTP client run
against the local contract-test sandbox over real HTTP on 127.0.0.1; every
value is synthetic and no carrier is contacted. The PostgreSQL label-execution
path is covered by tests/lifecycle/label_carrier_sandbox_postgresql.py.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from returnops_domain.carrier_adapter import (  # noqa: E402
    DEADLINE_MARGIN_SECONDS, DISPATCH_WINDOW_SECONDS, TOTAL_BUDGET_SECONDS, CarrierLabelClient, CarrierOutcomeUnknown, SandboxCarrierLabel,
    SandboxLabelFactory, dispatch_budget, label_request,
)
from returnops_domain.carrier_sandbox import TEST_KEY, CarrierSandbox  # noqa: E402
from returnops_domain.core_label_mock import CoreLabelMock, MockReply, Ticket  # noqa: E402
from returnops_domain.customer_uow import CustomerUnitOfWork  # noqa: E402
from returnops_domain.label_execution import LabelExecutionService  # noqa: E402

KEY = "leffect_" + "c0ffee" * 10 + "abcd"
OTHER_KEY = "leffect_" + "beef" * 16
COMMAND = dict(command_id="label_cmd_adapter_a", type="GENERATE_LABEL", provider_id="provider-mock-label",
               parameters=dict(parcel_id="parcel_adapter_a", return_command_id="return_cmd_adapter_a",
                               label_format="PDF", chargeable=False))


def control(key=KEY, *, seconds=30.0, parcel="parcel_adapter_a"):
    return dict(effect_key=key, parcel_id=parcel, provider_return_id="return_adapter_a",
                dispatch_deadline=datetime.now(timezone.utc) + timedelta(seconds=seconds))


def command(**parameters):
    return {**COMMAND, "parameters": {**COMMAND["parameters"], **parameters}}


class CarrierAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = CarrierSandbox().start()
        self.addCleanup(self.sandbox.close)
        self.factory = SandboxLabelFactory(self.sandbox.base_url, request_timeout=0.4)

    def run_outcome(self, row=None, cmd=COMMAND):
        adapter = self.factory(None)
        return adapter, adapter._outcome(control() if row is None else row, cmd)

    def statuses(self, adapter):
        return [(attempt["phase"], attempt["method"], attempt["status"], attempt["error"]) for attempt in adapter.attempts]

    def assert_no_key(self, *values):
        rendered = repr(values) + json.dumps([value.carrier_result.receipt() for value in values
                                              if isinstance(value, SandboxCarrierLabel) and value.carrier_result])
        rendered += repr(self.sandbox.requests()) + repr(self.sandbox) + repr(self.factory) + repr(self.factory.client)
        for secret in (KEY, OTHER_KEY, TEST_KEY):
            self.assertNotIn(secret, rendered)

    def test_factory_fits_mock_factory_and_overrides_only_outcome(self):
        engine, unit = object(), type("Unit", (CustomerUnitOfWork,), {})
        adapter = self.factory(engine)
        self.assertIsInstance(adapter, CoreLabelMock)
        self.assertIs(adapter.engine, engine)
        self.assertIs(adapter.uow_factory, CustomerUnitOfWork)
        self.assertIs(self.factory(engine, uow_factory=unit).uow_factory, unit)
        self.assertEqual(self.factory.adapters[0], adapter)
        core = {name for name in vars(CoreLabelMock) if not name.startswith("__")}
        self.assertEqual(core & set(vars(SandboxCarrierLabel)), {"_outcome"})
        self.assertIs(SandboxCarrierLabel.perform, CoreLabelMock.perform)
        self.assertIs(SandboxCarrierLabel._insert, CoreLabelMock._insert)
        calls = []

        def recording(*args, **kwargs):
            calls.append((args, kwargs))
            return self.factory(*args, **kwargs)

        # The service builds the adapter as mock_factory(engine); without a database the
        # fenced transaction fails first, so the carrier is never called.
        service = LabelExecutionService(None, lambda *a: None, mock_factory=recording)
        ticket = Ticket("lcontrol_a", "case_a", "key_a", "0" * 64, "DISPATCH", "lclaim_a", 0)
        result = service._perform(ticket, "a3-offline-correlation")
        self.assertEqual((result.status, calls), ("UNKNOWN", [((None,), {})]))
        self.assertEqual(self.sandbox.requests(), [])
        self.assertEqual(SandboxCarrierLabel(None).perform(ticket, lambda *a: None), MockReply("UNKNOWN"))

    def test_normal_label_is_one_post_with_a_recorded_request_id(self):
        adapter, outcome = self.run_outcome()
        self.assertEqual(outcome, "SUCCEEDED")
        self.assertEqual(self.statuses(adapter), [("create", "POST", 201, None)])
        attempt, = adapter.attempts
        self.assertEqual((attempt["route"], set(attempt)), ("/v1/labels", {"phase", "method", "route", "status",
                                                                           "error", "request_id", "elapsed_ms"}))
        self.assertRegex(attempt["request_id"], r"^SBXR[0-9A-F]{12}$")
        result = adapter.carrier_result
        self.assertRegex(result.label["label_id"], r"^SBXL[0-9A-F]{10}$")
        self.assertFalse(result.recovered)
        server, = self.sandbox.requests(result.correlation_id)
        self.assertEqual((server["request_id"], server["status"]), (attempt["request_id"], 201))
        self.assertEqual(self.sandbox.labels_for_key(KEY), 1)
        again, outcome = self.run_outcome()
        self.assertEqual((outcome, self.statuses(again)), ("SUCCEEDED", [("create", "POST", 200, None)]))
        self.assertEqual(again.carrier_result.label, result.label)
        self.assertEqual(self.sandbox.labels_for_key(KEY), 1)
        self.assert_no_key(adapter, again)

    def test_error_before_commit_recovers_by_lookup_and_one_retry_with_the_same_key(self):
        self.sandbox.inject("error_before_commit")
        adapter, outcome = self.run_outcome()
        self.assertEqual(outcome, "SUCCEEDED")
        self.assertEqual(self.statuses(adapter), [("create", "POST", 503, None), ("verify", "GET", 404, None),
                                                  ("retry", "POST", 201, None)])
        self.assertEqual(adapter.attempts[1]["route"], "/v1/labels/by-key/{idempotency_key}")
        self.assertTrue(adapter.carrier_result.recovered)
        self.assertEqual((self.sandbox.labels_for_key(KEY), self.sandbox.label_count()), (1, 1))
        ids = [attempt["request_id"] for attempt in adapter.attempts]
        self.assertEqual(ids, [entry["request_id"] for entry in self.sandbox.requests(adapter.carrier_result.correlation_id)])
        self.assertEqual(len(set(ids)), 3)
        self.assert_no_key(adapter)

    def test_timeout_after_commit_recovers_by_lookup_without_a_second_post(self):
        self.sandbox.inject("timeout_after_commit", delay=1.2)
        adapter, outcome = self.run_outcome()
        self.assertEqual(outcome, "SUCCEEDED")
        self.assertEqual(self.statuses(adapter), [("create", "POST", None, "TIMEOUT"), ("verify", "GET", 200, None)])
        self.assertIsNone(adapter.attempts[0]["request_id"])
        self.assertTrue(adapter.carrier_result.recovered)
        self.assertTrue(self.sandbox.wait_idle(5))
        server = self.sandbox.requests(adapter.carrier_result.correlation_id)
        self.assertEqual(sorted((entry["method"], entry["status"], entry["fault"]) for entry in server),
                         [("GET", 200, None), ("POST", 201, "timeout_after_commit")])
        self.assertEqual((self.sandbox.labels_for_key(KEY), self.sandbox.label_count()), (1, 1))
        self.assert_no_key(adapter)

    def test_late_original_after_a_retry_is_replayed_not_duplicated(self):
        self.sandbox.inject("delay_before_commit", delay=1.0)
        adapter, outcome = self.run_outcome()
        self.assertEqual(outcome, "SUCCEEDED")
        self.assertEqual(self.statuses(adapter), [("create", "POST", None, "TIMEOUT"), ("verify", "GET", 404, None),
                                                  ("retry", "POST", 201, None)])
        self.assertTrue(self.sandbox.wait_idle(5))
        posts = [entry["status"] for entry in self.sandbox.requests(adapter.carrier_result.correlation_id)
                 if entry["method"] == "POST"]
        self.assertEqual(posts, [201, 200])
        self.assertEqual((self.sandbox.labels_for_key(KEY), self.sandbox.label_count()), (1, 1))

    def test_reject_auth_and_invalid_are_failed_without_recovery(self):
        for fault, status, error in (("reject_auth", 401, "CARRIER_AUTH_REJECTED"),
                                     ("invalid", 422, "CARRIER_INVALID_REQUEST")):
            with self.subTest(fault=fault):
                self.sandbox.inject(fault)
                adapter, outcome = self.run_outcome()
                self.assertEqual((outcome, adapter.carrier_result.error), ("FAILED", error))
                self.assertEqual(self.statuses(adapter), [("create", "POST", status, None)])
                self.assertEqual(self.sandbox.labels_for_key(KEY), 0)
                self.assert_no_key(adapter)

    def test_wrong_test_key_is_failed(self):
        factory = SandboxLabelFactory(self.sandbox.base_url, api_key="not-the-sandbox-key")
        adapter = factory(None)
        self.assertEqual(adapter._outcome(control(), COMMAND), "FAILED")
        self.assertEqual(self.statuses(adapter), [("create", "POST", 401, None)])
        self.assertEqual(self.sandbox.label_count(), 0)

    def test_same_key_with_a_different_command_is_a_failed_conflict(self):
        self.assertEqual(self.run_outcome()[1], "SUCCEEDED")
        adapter, outcome = self.run_outcome(control(parcel="parcel_adapter_b"), command(parcel_id="parcel_adapter_b"))
        self.assertEqual((outcome, adapter.carrier_result.error), ("FAILED", "CARRIER_IDEMPOTENCY_CONFLICT"))
        self.assertEqual(self.statuses(adapter), [("create", "POST", 409, None)])
        self.assertEqual((self.sandbox.labels_for_key(KEY), self.sandbox.label_count()), (1, 1))

    def test_outcome_still_unknown_raises_and_stores_nothing(self):
        self.sandbox.inject("error_before_commit", times=None)
        adapter = self.factory(None)
        with self.assertRaises(CarrierOutcomeUnknown):
            adapter._outcome(control(), COMMAND)
        self.assertEqual(adapter.carrier_result.outcome, "UNKNOWN")
        self.assertEqual(self.statuses(adapter), [("create", "POST", 503, None), ("verify", "GET", 404, None),
                                                  ("retry", "POST", 503, None), ("confirm", "GET", 404, None)])
        self.assertEqual(self.sandbox.label_count(), 0)
        self.assert_no_key(adapter)

    def test_unreachable_sandbox_is_a_bounded_unknown(self):
        factory = SandboxLabelFactory(self.sandbox.base_url, request_timeout=0.3, budget_seconds=3.0)
        self.sandbox.close()
        adapter = factory(None)
        started = time.monotonic()
        with self.assertRaises(CarrierOutcomeUnknown):
            adapter._outcome(control(), COMMAND)
        self.assertLess(time.monotonic() - started, 4.0)
        self.assertTrue(adapter.attempts)
        self.assertLessEqual(len(adapter.attempts), 6)
        self.assertEqual({attempt["error"] for attempt in adapter.attempts}, {"CONNECTION"})

    def test_timeouts_are_sized_from_the_dispatch_deadline(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(dispatch_budget(now + timedelta(seconds=30), now=now), TOTAL_BUDGET_SECONDS)
        self.assertEqual(dispatch_budget(now + timedelta(seconds=8), now=now), 8 - DEADLINE_MARGIN_SECONDS)
        self.assertEqual(dispatch_budget(now + timedelta(seconds=2), now=now), 0.0)
        self.assertEqual(dispatch_budget(None), 0.0)
        self.assertEqual(dispatch_budget(datetime.now() + timedelta(seconds=30)), 0.0)
        self.assertLess(TOTAL_BUDGET_SECONDS + DEADLINE_MARGIN_SECONDS, DISPATCH_WINDOW_SECONDS)
        # Drift guard: the constants above were sized from this line of label_execution.py.
        source = (Path(__file__).resolve().parents[2] / "packages/returnops_domain/label_execution.py").read_text(encoding="utf-8")
        self.assertIn("dispatch_deadline=min(now+timedelta(seconds=30),", source)
        # Too close to the deadline: nothing is sent and the explicit no-effect FAILED is used.
        adapter, outcome = self.run_outcome(control(seconds=DEADLINE_MARGIN_SECONDS + 0.1))
        self.assertEqual((outcome, adapter.carrier_result.error, adapter.attempts), ("FAILED", "CARRIER_NOT_SENT_DEADLINE", ()))
        self.assertEqual(self.sandbox.requests(), [])
        # A slow carrier near the deadline: the whole call stays inside the remaining budget.
        self.sandbox.inject("timeout_after_commit", times=None, delay=3.0)
        slow = SandboxLabelFactory(self.sandbox.base_url, request_timeout=2.0)(None)
        started = time.monotonic()
        with self.assertRaises(CarrierOutcomeUnknown):
            slow._outcome(control(seconds=DEADLINE_MARGIN_SECONDS + 1.5), COMMAND)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertLessEqual(max(attempt["elapsed_ms"] for attempt in slow.attempts), 1600)

    def test_mapping_rejections_fail_without_sending(self):
        cases = [(control(), {**COMMAND, "type": "CREATE_RETURN"}), (control(), command(chargeable=True)),
                 (control(), command(label_format="ZPL")), (control(parcel="parcel_adapter_other"), COMMAND),
                 (control(), {name: value for name, value in COMMAND.items() if name != "parameters"}),
                 (control(key="has space"), COMMAND), ({**control(), "provider_return_id": None}, COMMAND)]
        for row, cmd in cases:
            with self.subTest(cmd=cmd.get("type"), row=row["parcel_id"]):
                adapter, outcome = self.run_outcome(row, cmd)
                self.assertEqual((outcome, adapter.carrier_result.error), ("FAILED", "CARRIER_MAPPING_REJECTED"))
        self.assertEqual(self.sandbox.requests(), [])
        self.assertEqual(label_request(control(), COMMAND), dict(
            client_reference="label_cmd_adapter_a", parcel_reference="parcel_adapter_a",
            return_reference="return_adapter_a", label_format="PDF", service="RETURN", chargeable=False))

    def test_without_a_client_the_outcome_is_unknown_never_a_label(self):
        with self.assertRaises(CarrierOutcomeUnknown):
            SandboxCarrierLabel(None)._outcome(control(), COMMAND)
        self.assertEqual(self.sandbox.requests(), [])

    def test_client_reaches_only_the_local_sandbox(self):
        for url in ("https://carrier.example.com", "http://10.0.0.1:8080", "http://localhost:8080",
                    "http://127.0.0.1", "http://127.0.0.1:8080/v1", "http://user@127.0.0.1:8080",
                    "http://127.0.0.1:8080?x=1", "ftp://127.0.0.1:21", None, 7):
            with self.subTest(url=url), self.assertRaises(ValueError):
                CarrierLabelClient(url)
        for options in ({"request_timeout": 0}, {"lookup_attempts": 0}, {"backoff": ()}, {"backoff": (5,)},
                        {"budget_seconds": 26}, {"api_key": ""}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CarrierLabelClient(self.sandbox.base_url, **options)
        self.assertRegex(repr(self.factory.client), r"^CarrierLabelClient\(sandbox=http://127\.0\.0\.1:\d+, ")
        self.assertIsNone(re.search(TEST_KEY, repr(self.factory)))


if __name__ == "__main__":
    unittest.main()
