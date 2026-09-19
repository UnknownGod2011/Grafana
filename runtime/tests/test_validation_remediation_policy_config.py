import math
import unittest

from production_remediation import AllowlistedProductionRemediationClient


class NoCallTransport:
    def execute(self, request, *, timeout_seconds):
        raise AssertionError("configuration validation must happen before transport")


class ProductionRemediationPolicyConfigTests(unittest.TestCase):
    def test_allowlist_identity_requires_canonical_bounded_strings(self):
        for production_id, uplink in (
            (None, "uplink-b"),
            (123, "uplink-b"),
            (b"broadcast-alpha", "uplink-b"),
            ("broadcast-alpha", None),
            ("broadcast-alpha", 123),
            ("broadcast-alpha", b"uplink-b"),
            ("", "uplink-b"),
            (" broadcast-alpha", "uplink-b"),
            ("broadcast-alpha ", "uplink-b"),
            ("broadcast\nalpha", "uplink-b"),
            ("broadcast\x7falpha", "uplink-b"),
            ("x" * 129, "uplink-b"),
            ("broadcast-alpha", " uplink-b"),
            ("broadcast-alpha", "uplink-b\t"),
            ("broadcast-alpha", "uplink\rb"),
            ("broadcast-alpha", "x" * 129),
        ):
            with self.subTest(production_id=repr(production_id), uplink=repr(uplink)):
                with self.assertRaises(ValueError):
                    AllowlistedProductionRemediationClient(
                        NoCallTransport(),
                        allowed_production_id=production_id,
                        allowed_uplink=uplink,
                    )

    def test_allowlist_identity_accepts_boundary_length(self):
        AllowlistedProductionRemediationClient(
            NoCallTransport(),
            allowed_production_id="p" * 128,
            allowed_uplink="u" * 128,
        )

    def test_numeric_policy_rejects_bool_nonfinite_and_wrong_types(self):
        cases = (
            {"timeout_seconds": True},
            {"timeout_seconds": math.nan},
            {"timeout_seconds": math.inf},
            {"timeout_seconds": "3"},
            {"max_attempts": True},
            {"max_attempts": 2.0},
            {"retry_delay_seconds": False},
            {"retry_delay_seconds": math.nan},
            {"retry_delay_seconds": -math.inf},
            {"retry_delay_seconds": "0.25"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    AllowlistedProductionRemediationClient(
                        NoCallTransport(),
                        allowed_production_id="broadcast-alpha",
                        allowed_uplink="uplink-b",
                        **kwargs,
                    )

    def test_policy_boundaries_accept_finite_ints_and_floats(self):
        for timeout, attempts, delay in ((0.1, 1, 0), (10, 3, 2.0), (3, 2, 0.25)):
            with self.subTest(timeout=timeout, attempts=attempts, delay=delay):
                AllowlistedProductionRemediationClient(
                    NoCallTransport(),
                    allowed_production_id="broadcast-alpha",
                    allowed_uplink="uplink-b",
                    timeout_seconds=timeout,
                    max_attempts=attempts,
                    retry_delay_seconds=delay,
                )

    def test_sleep_hook_must_be_callable(self):
        with self.assertRaises(ValueError):
            AllowlistedProductionRemediationClient(
                NoCallTransport(),
                allowed_production_id="broadcast-alpha",
                allowed_uplink="uplink-b",
                sleep=None,
            )


if __name__ == "__main__":
    unittest.main()
