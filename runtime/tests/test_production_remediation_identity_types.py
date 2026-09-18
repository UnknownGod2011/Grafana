import unittest

from production_remediation import AllowlistedProductionRemediationClient


class NoCallTransport:
    def __init__(self):
        self.execute_calls = []
        self.reconcile_calls = []

    def execute(self, request, *, timeout_seconds):
        self.execute_calls.append((request, timeout_seconds))
        raise AssertionError("invalid operation identity reached mutation transport")

    def reconcile(self, operation_id, *, timeout_seconds):
        self.reconcile_calls.append((operation_id, timeout_seconds))
        raise AssertionError("invalid operation identity reached reconciliation transport")


class ProductionRemediationIdentityTypeTests(unittest.TestCase):
    def setUp(self):
        self.transport = NoCallTransport()
        self.client = AllowlistedProductionRemediationClient(
            self.transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
        )

    def test_non_string_operation_id_fails_closed_without_transport_or_reflection(self):
        invalid_values = (None, 123, True, b"sg-" + b"a" * 40, ["sg-" + "a" * 40], {"id": "sg-" + "a" * 40})
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                result = self.client.recover_uplink_idempotent("broadcast-alpha", "uplink-b", value)
                self.assertFalse(result.accepted)
                self.assertEqual("invalid remediation operation identity", result.detail)
                self.assertEqual("", result.metadata["operation_id"])
                self.assertEqual(0, result.metadata["attempt_count"])
        self.assertEqual([], self.transport.execute_calls)

    def test_non_string_operation_id_cannot_reach_reconciliation_transport(self):
        for value in (None, 123, True, b"sg-" + b"a" * 40, ["sg-" + "a" * 40]):
            with self.subTest(value=repr(value)):
                self.assertEqual("unknown", self.client.reconcile_operation(value))
        self.assertEqual([], self.transport.reconcile_calls)

    def test_invalid_identity_is_not_reflected_for_wrong_target_either(self):
        value = {"not": "json-safe enough to trust"}
        result = self.client.recover_uplink_idempotent("other-production", "other-uplink", value)
        self.assertFalse(result.accepted)
        self.assertEqual("", result.metadata["operation_id"])
        self.assertEqual([], self.transport.execute_calls)


if __name__ == "__main__":
    unittest.main()
