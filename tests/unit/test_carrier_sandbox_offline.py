"""A3 carrier sandbox contract without a database (OF-004; FR-010, NFR-004, NFR-007).

docs/49-a3-carrier-sandbox.md. Real HTTP on 127.0.0.1 against the in-memory
contract-test sandbox; every value is synthetic and no carrier is contacted.
"""
from http.client import HTTPConnection
import json
from pathlib import Path
import re
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from returnops_domain.carrier_sandbox import (  # noqa: E402
    FAULTS, TEST_KEY, CarrierSandbox, identifier, parse_label_request,
)

BODY = dict(client_reference="label_cmd_sandbox_a", parcel_reference="parcel_sandbox_a",
            return_reference="return_sandbox_a", label_format="PDF", service="RETURN", chargeable=False)
NINE_DIGITS = re.compile(r"(?<![0-9])[0-9]{9}(?![0-9])")


class CarrierSandboxTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = CarrierSandbox(fault_delay=1.0).start()
        self.addCleanup(self.sandbox.close)
        self.port = int(self.sandbox.base_url.rsplit(":", 1)[1])

    def call(self, method, path, body=None, *, key="sbx-key-a", auth=TEST_KEY, headers=None, timeout=5.0, raw=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        sent = {} if auth is None else {"Authorization": "Bearer " + auth}
        if key is not None and method == "POST":
            sent["Idempotency-Key"] = key
        sent.update(headers or {})
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        if data is not None:
            sent["Content-Type"] = "application/json"
        try:
            connection.request(method, path, body=data, headers=sent)
            response = connection.getresponse()
            payload = response.read()
            return response.status, dict(response.getheaders()), json.loads(payload) if payload else None
        finally:
            connection.close()

    def create(self, body=BODY, **options):
        return self.call("POST", "/v1/labels", body, **options)

    def test_first_use_creates_and_same_key_same_body_returns_the_same_record(self):
        status, headers, first = self.create()
        self.assertEqual(status, 201)
        self.assertEqual(set(first), {"label_id", "tracking_number", "status", "created_at",
                                      "client_reference", "parcel_reference", "return_reference"})
        self.assertEqual(first["status"], "CREATED")
        self.assertRegex(first["label_id"], r"^SBXL[0-9A-F]{10}$")
        self.assertRegex(first["tracking_number"], r"^SBXT[0-9A-F]{10}$")
        self.assertRegex(first["created_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertRegex(headers["X-Request-Id"], r"^SBXR[0-9A-F]{12}$")
        status, again_headers, again = self.create()
        self.assertEqual((status, again), (200, first))
        self.assertNotEqual(again_headers["X-Request-Id"], headers["X-Request-Id"])
        self.assertEqual((self.sandbox.labels_for_key("sbx-key-a"), self.sandbox.label_count()), (1, 1))
        status, _, other = self.create(key="sbx-key-b")
        self.assertEqual(status, 201)
        self.assertNotEqual(other["label_id"], first["label_id"])
        self.assertEqual(self.sandbox.label_count(), 2)

    def test_same_key_with_a_different_body_is_409_and_stores_nothing_new(self):
        self.assertEqual(self.create()[0], 201)
        status, headers, payload = self.create({**BODY, "parcel_reference": "parcel_sandbox_other"})
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "idempotency_key_reused")
        self.assertEqual(payload["request_id"], headers["X-Request-Id"])
        self.assertEqual((self.sandbox.labels_for_key("sbx-key-a"), self.sandbox.label_count()), (1, 1))

    def test_missing_or_wrong_test_key_is_401_on_every_route(self):
        for auth in (None, "wrong-sandbox-key", TEST_KEY + "x"):
            with self.subTest(auth=auth):
                for method, path in (("POST", "/v1/labels"), ("GET", "/v1/labels/by-key/sbx-key-a"),
                                     ("GET", "/v1/labels/SBXLAAAAAAAAAA")):
                    status, headers, payload = self.call(method, path, BODY if method == "POST" else None, auth=auth)
                    self.assertEqual(status, 401)
                    self.assertEqual(payload["error"]["code"], "unauthorized")
                    self.assertIn("X-Request-Id", headers)
        self.assertEqual(self.sandbox.label_count(), 0)

    def test_invalid_body_or_missing_idempotency_key_is_422(self):
        cases = {
            "missing field": {name: value for name, value in BODY.items() if name != "service"},
            "extra field": {**BODY, "price_minor": 0},
            "chargeable": {**BODY, "chargeable": True},
            "format": {**BODY, "label_format": "ZPL"},
            "service": {**BODY, "service": "OUTBOUND"},
            "reference type": {**BODY, "parcel_reference": 7},
            "reference text": {**BODY, "parcel_reference": "parcel with spaces"},
            "array": [BODY],
        }
        for name, body in cases.items():
            with self.subTest(case=name):
                status, _, payload = self.create(body)
                self.assertEqual((status, payload["error"]["code"]), (422, "invalid_request"))
        for raw in (b"{not json", b'{"client_reference":"a","client_reference":"b"}', bytes([0xE9])):
            with self.subTest(raw=raw):
                self.assertEqual(self.create(raw=raw)[0], 422)
        for key in (None, "", "has space", "x" * 300):
            with self.subTest(key=key):
                status, _, payload = self.create(key=key)
                self.assertEqual((status, payload["error"]["code"]), (422, "idempotency_key_required"))
        self.assertEqual(self.sandbox.label_count(), 0)

    def test_lookup_by_key_and_by_id(self):
        self.assertEqual(self.call("GET", "/v1/labels/by-key/sbx-key-a")[0], 404)
        _, _, created = self.create()
        status, headers, found = self.call("GET", "/v1/labels/by-key/sbx-key-a")
        self.assertEqual((status, found), (200, created))
        self.assertIn("X-Request-Id", headers)
        self.assertEqual(self.call("GET", "/v1/labels/" + created["label_id"])[2], created)
        self.assertEqual(self.call("GET", "/v1/labels/SBXLFFFFFFFFFF")[0], 404)
        self.assertEqual(self.call("GET", "/v1/labels/by-key/sbx-key-zzz")[0], 404)
        self.assertEqual(self.call("GET", "/v1/other")[0], 404)
        self.assertEqual(self.call("DELETE", "/v1/labels/" + created["label_id"])[0], 405)
        self.assertEqual(self.sandbox.label_count(), 1)

    def test_correlation_header_is_echoed_and_logged_without_the_key(self):
        status, headers, _ = self.create(headers={"X-Correlation-Id": "A3CTESTCORRELATION"})
        self.assertEqual((status, headers["X-Correlation-Id"]), (201, "A3CTESTCORRELATION"))
        _, headers, _ = self.call("GET", "/v1/labels/by-key/sbx-key-a", headers={"X-Correlation-Id": "bad value!"})
        self.assertNotIn("X-Correlation-Id", headers)
        log = self.sandbox.requests()
        self.assertEqual([(entry["method"], entry["route"], entry["status"]) for entry in log],
                         [("POST", "/v1/labels", 201), ("GET", "/v1/labels/by-key/{idempotency_key}", 200)])
        self.assertEqual(self.sandbox.requests("A3CTESTCORRELATION")[0]["status"], 201)
        self.assertNotIn("sbx-key-a", repr(log) + repr(self.sandbox))

    def test_fault_error_before_commit_is_503_with_nothing_stored_then_clears(self):
        self.sandbox.inject("error_before_commit")
        status, headers, payload = self.create()
        self.assertEqual((status, payload["error"]["code"]), (503, "temporarily_unavailable"))
        self.assertIn("X-Request-Id", headers)
        self.assertEqual(self.sandbox.labels_for_key("sbx-key-a"), 0)
        self.assertEqual(self.call("GET", "/v1/labels/by-key/sbx-key-a")[0], 404)
        self.assertEqual(self.create()[0], 201)
        self.assertEqual(self.sandbox.labels_for_key("sbx-key-a"), 1)

    def test_persistent_fault_lasts_until_cleared(self):
        self.sandbox.inject("error_before_commit", times=None)
        self.assertEqual([self.create()[0] for _ in range(3)], [503, 503, 503])
        self.sandbox.clear()
        self.assertEqual(self.create()[0], 201)
        self.sandbox.inject("error_before_commit", times=2)
        self.assertEqual([self.create(key="sbx-key-n")[0] for _ in range(3)], [503, 503, 201])

    def test_fault_timeout_after_commit_stores_then_answers_too_late(self):
        self.sandbox.inject("timeout_after_commit", delay=1.0)
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.create(timeout=0.3)
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertEqual(self.sandbox.labels_for_key("sbx-key-a"), 1)
        status, _, found = self.call("GET", "/v1/labels/by-key/sbx-key-a")
        self.assertEqual((status, found["status"]), (200, "CREATED"))
        self.assertTrue(self.sandbox.wait_idle(5))
        late = [entry for entry in self.sandbox.requests() if entry["method"] == "POST"]
        self.assertEqual([(entry["status"], entry["fault"]) for entry in late], [(201, "timeout_after_commit")])

    def test_fault_delay_before_commit_lets_a_late_original_replay_without_a_second_label(self):
        self.sandbox.inject("delay_before_commit", delay=0.8)
        with self.assertRaises(TimeoutError):
            self.create(timeout=0.2)
        self.assertEqual(self.sandbox.labels_for_key("sbx-key-a"), 0)
        self.assertEqual(self.create()[0], 201)
        self.assertTrue(self.sandbox.wait_idle(5))
        self.assertEqual(sorted(entry["status"] for entry in self.sandbox.requests()), [200, 201])
        self.assertEqual(self.sandbox.labels_for_key("sbx-key-a"), 1)

    def test_fault_reject_auth_is_401_even_with_the_right_key(self):
        self.sandbox.inject("reject_auth")
        status, _, payload = self.create()
        self.assertEqual((status, payload["error"]["code"]), (401, "unauthorized"))
        self.assertEqual(self.sandbox.label_count(), 0)
        self.assertEqual(self.create()[0], 201)

    def test_fault_invalid_is_422_even_with_a_valid_body(self):
        self.sandbox.inject("invalid")
        status, _, payload = self.create()
        self.assertEqual((status, payload["error"]["code"]), (422, "invalid_request"))
        self.assertEqual(self.sandbox.label_count(), 0)

    def test_faults_come_only_from_the_owner_not_from_request_content(self):
        for name in FAULTS:
            status, _, _ = self.create(key="sbx-key-" + name, headers={"X-Sandbox-Fault": name, "X-Fault": name})
            self.assertEqual(status, 201)
        self.assertEqual(self.sandbox.label_count(), len(FAULTS))
        with self.assertRaises(ValueError):
            self.sandbox.inject("drop_database")
        with self.assertRaises(ValueError):
            self.sandbox.inject("invalid", times=0)

    def test_identifiers_never_carry_long_digit_runs(self):
        values = [identifier("SBXL") for _ in range(5000)] + [identifier("SBXR", 6) for _ in range(5000)]
        self.assertFalse([value for value in values if re.search(r"[0-9]{6}", value)])
        for index in range(20):
            self.create(key=f"sbx-key-{index}")
        rendered = json.dumps(self.sandbox.requests())
        self.assertIsNone(NINE_DIGITS.search(rendered))

    def test_parse_and_construction_guards(self):
        self.assertEqual(parse_label_request(json.dumps(BODY).encode()), BODY)
        self.assertIsNone(parse_label_request(b"null"))
        for options in ({"port": -1}, {"port": 70000}, {"api_key": ""}, {"api_key": chr(0xE9)}, {"fault_delay": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                CarrierSandbox(**options)
        with self.assertRaises(RuntimeError):
            self.sandbox.start()
        self.assertTrue(self.sandbox.base_url.startswith("http://127.0.0.1:"))
        self.assertRegex(repr(self.sandbox), r"^CarrierSandbox\(running=True, labels=0\)$")


if __name__ == "__main__":
    unittest.main()
