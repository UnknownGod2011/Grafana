import math
import unittest

from production_remediation import AllowlistedProductionRemediationClient, TransportResult


class NoCallTransport:
    def execute(self, request, *, timeout_seconds):
        raise AssertionError("configuration validation must happen before transport")


class ReconcileTransport(NoCallTransport):
    def __init__(self, state):
        self.state = state

    def reconcile(self, operation_id, *, timeout_seconds):
        return self.state


class RetryableTransport:
    def __init__(self):
        self.calls = 0

    def execute(self, request, *, timeout_seconds):
        self.calls += 1
        return TransportResult(False, 503, retryable=True)


class ProductionRemediationPolicyConfigTests(unittest.TestCase):
    def test_transport_must_expose_callable_execute(self):
        for transport in (None, object(), type("BadTransport", (), {"execute": None})()):
            with self.subTest(transport=repr(transport)):
                with self.assertRaises(ValueError):
                    AllowlistedProductionRemediationClient(transport, allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b")

    def test_allowlist_identity_requires_canonical_bounded_strings(self):
        for production_id, uplink in (
            (None, "uplink-b"), (123, "uplink-b"), (b"broadcast-alpha", "uplink-b"),
            ("broadcast-alpha", None), ("broadcast-alpha", 123), ("broadcast-alpha", b"uplink-b"),
            ("", "uplink-b"), (" broadcast-alpha", "uplink-b"), ("broadcast-alpha ", "uplink-b"),
            ("broadcast\nalpha", "uplink-b"), ("broadcast\x7falpha", "uplink-b"), ("x" * 129, "uplink-b"),
            ("broadcast-alpha", " uplink-b"), ("broadcast-alpha", "uplink-b\t"),
            ("broadcast-alpha", "uplink\rb"), ("broadcast-alpha", "x" * 129),
        ):
            with self.subTest(production_id=repr(production_id), uplink=repr(uplink)):
                with self.assertRaises(ValueError):
                    AllowlistedProductionRemediationClient(NoCallTransport(), allowed_production_id=production_id, allowed_uplink=uplink)

    def test_allowlist_identity_accepts_boundary_length(self):
        AllowlistedProductionRemediationClient(NoCallTransport(), allowed_production_id="p" * 128, allowed_uplink="u" * 128)

    def test_numeric_policy_rejects_bool_nonfinite_and_wrong_types(self):
        cases = (
            {"timeout_seconds": True}, {"timeout_seconds": math.nan}, {"timeout_seconds": math.inf}, {"timeout_seconds": "3"},
            {"max_attempts": True}, {"max_attempts": 2.0}, {"retry_delay_seconds": False},
            {"retry_delay_seconds": math.nan}, {"retry_delay_seconds": -math.inf}, {"retry_delay_seconds": "0.25"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    AllowlistedProductionRemediationClient(NoCallTransport(), allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b", **kwargs)

    def test_policy_boundaries_accept_finite_ints_and_floats(self):
        for timeout, attempts, delay in ((0.1, 1, 0), (10, 3, 2.0), (3, 2, 0.25)):
            with self.subTest(timeout=timeout, attempts=attempts, delay=delay):
                AllowlistedProductionRemediationClient(NoCallTransport(), allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b", timeout_seconds=timeout, max_attempts=attempts, retry_delay_seconds=delay)

    def test_sleep_hook_must_be_callable(self):
        with self.assertRaises(ValueError):
            AllowlistedProductionRemediationClient(NoCallTransport(), allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b", sleep=None)

    def test_retry_scheduling_fault_fails_closed_without_second_provider_call(self):
        transport = RetryableTransport()

        def broken_sleep(_seconds):
            raise RuntimeError("scheduler unavailable")

        client = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
            max_attempts=3,
            sleep=broken_sleep,
        )
        result = client.recover_uplink_idempotent("broadcast-alpha", "uplink-b", "sg-" + "a" * 40)

        self.assertFalse(result.accepted)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(result.detail, "production remediation retry scheduling fault")
        self.assertEqual(result.metadata["attempt_count"], 1)
        self.assertEqual(result.metadata["transport_status"], 503)

    def test_reconciliation_state_must_be_exact_bounded_contract_string(self):
        operation_id = "sg-" + "a" * 40
        malformed_states = (None, True, 1, [], {}, b"accepted", "ACCEPTED", "accepted\n")
        for state in malformed_states:
            with self.subTest(state=repr(state)):
                client = AllowlistedProductionRemediationClient(ReconcileTransport(state), allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b")
                self.assertEqual(client.reconcile_operation(operation_id), "unknown")

        for state in ("accepted", "not_found"):
            with self.subTest(state=state):
                client = AllowlistedProductionRemediationClient(ReconcileTransport(state), allowed_production_id="broadcast-alpha", allowed_uplink="uplink-b")
                self.assertEqual(client.reconcile_operation(operation_id), state)


if __name__ == "__main__":
    unittest.main()
