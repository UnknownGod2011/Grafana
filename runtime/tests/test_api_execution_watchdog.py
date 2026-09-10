from __future__ import annotations

import unittest

from api import _remediation_execution_observability


class WatchdogService:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def remediation_execution_observability(self):
        if self.error is not None:
            raise self.error
        return self.value


class NoWatchdogService:
    pass


class ApiExecutionWatchdogTests(unittest.TestCase):
    def test_runtime_without_watchdog_is_backward_compatible(self):
        self.assertEqual(
            {
                "active": False,
                "age_seconds": 0.0,
                "max_seconds": 0.0,
                "deadline_exceeded": False,
            },
            _remediation_execution_observability(NoWatchdogService()),
        )

    def test_valid_watchdog_state_is_normalized(self):
        service = WatchdogService(
            {
                "active": True,
                "age_seconds": 2,
                "max_seconds": 10,
                "deadline_exceeded": False,
                "provider_detail": "must-not-pass-through",
            }
        )
        self.assertEqual(
            {
                "active": True,
                "age_seconds": 2.0,
                "max_seconds": 10.0,
                "deadline_exceeded": False,
            },
            _remediation_execution_observability(service),
        )

    def test_invalid_or_exceptional_watchdog_state_fails_closed_without_details(self):
        bad_values = (
            None,
            {},
            {"active": "yes", "age_seconds": 1, "max_seconds": 2, "deadline_exceeded": False},
            {"active": True, "age_seconds": -1, "max_seconds": 2, "deadline_exceeded": False},
            {"active": True, "age_seconds": float("nan"), "max_seconds": 2, "deadline_exceeded": False},
            {"active": True, "age_seconds": 1, "max_seconds": 0, "deadline_exceeded": False},
            {"active": True, "age_seconds": 1, "max_seconds": float("inf"), "deadline_exceeded": False},
            {"active": True, "age_seconds": 1, "max_seconds": 2, "deadline_exceeded": "no"},
        )
        expected = {
            "active": False,
            "age_seconds": 0.0,
            "max_seconds": 0.0,
            "deadline_exceeded": True,
        }
        for value in bad_values:
            with self.subTest(value=value):
                self.assertEqual(expected, _remediation_execution_observability(WatchdogService(value)))

        secret = "https://provider.example/private?token=secret"
        observed = _remediation_execution_observability(WatchdogService(error=RuntimeError(secret)))
        self.assertEqual(expected, observed)
        self.assertNotIn(secret, repr(observed))


if __name__ == "__main__":
    unittest.main()
