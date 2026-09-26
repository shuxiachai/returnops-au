"""F.01 / KAN-32 fixture semantics, not notification delivery or state guards.

FR-010/011/012; docs/09 sections 8.2/10.4 and MA recovery sequence.
Regression for C-F01-20260920-01: customer content is independent of transport.
"""
from copy import deepcopy
import re
import unittest

from test_contract_v1 import POSITIVE, validator


def assert_customer_content(record):
    """Reject the reported operator-only wording in synthetic customer fields."""
    text = " ".join([record["message"], *record["next_steps"]])
    assert not re.search(
        r"\b(?:resend|re-send|retry)\b|notification delivery failed|"
        r"do not recreate the return or label",
        text,
        re.IGNORECASE,
    ), "Internal delivery/retry instruction in customer content"


class NotificationFixtureTests(unittest.TestCase):
    def test_customer_content_stays_stable_across_delivery_and_history(self):
        sent = POSITIVE["notification-sent"]["value"]
        history = POSITIVE["history-notification"]["value"]["content"]
        customer = POSITIVE["customer-history-outcome"]["value"]["content"]
        failed = POSITIVE["notification-failed"]["value"]
        pending = POSITIVE["notification-retry-accepted"]["value"]
        for record in (failed, pending, sent, history, customer):
            with self.subTest(status=record.get("status", "customer history")):
                self.assertEqual(record["outcome"], "RETURN_CREATED")
                for field in ("notification_id", "outcome", "message", "next_steps"):
                    self.assertEqual(record[field], sent[field], field)
                self.assertTrue(record["next_steps"])
                assert_customer_content(record)
        self.assertEqual([failed["status"], pending["status"], sent["status"]],
                         ["FAILED", "PENDING", "SENT"])
        self.assertEqual(failed["error"]["error"]["code"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(customer["sent_at"], sent["sent_at"])

    def test_schema_valid_operator_wording_is_detected_in_customer_fields(self):
        for schema, original in (
            ("NotificationRecord", POSITIVE["notification-sent"]["value"]),
            ("CustomerOutcomeMessage", POSITIVE["customer-history-outcome"]["value"]["content"]),
        ):
            for field, bad_content in (
                ("message", "The simulated return and free label were recorded. Notification delivery failed."),
                ("next_steps", ["Resend this message only; do not recreate the return or label."]),
            ):
                with self.subTest(schema=schema, field=field):
                    record = deepcopy(original)
                    record[field] = bad_content
                    validator(schema).validate(record)
                    with self.assertRaisesRegex(AssertionError, "Internal delivery/retry"):
                        assert_customer_content(record)


if __name__ == "__main__":
    unittest.main()
