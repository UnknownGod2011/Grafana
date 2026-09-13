from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from anchored_execution_safety import (
    AnchoredExecutionSafeIncidentService,
    MAX_REMEDIATION_EXECUTION_SECONDS,
    MIN_REMEDIATION_EXECUTION_SECONDS,
)
from anchored_incident_service import AnchoredIncidentService


class CoreExecutionWatchdogBoundsTests(unittest.TestCase):
    def build(self, value):
        # The watchdog configuration is validated before the rest of the service
        # composition is initialized. Patch the parent constructor so these tests
        # stay focused and do not require checkpoint/audit/telemetry fixtures.
        with patch.object(AnchoredIncidentService, "__init__", return_value=None):
            return AnchoredExecutionSafeIncidentService(execution_max_seconds=value)

    def test_policy_constants_match_production_runtime_contract(self):
        self.assertEqual(1.0, MIN_REMEDIATION_EXECUTION_SECONDS)
        self.assertEqual(600.0, MAX_REMEDIATION_EXECUTION_SECONDS)

    def test_exact_policy_boundaries_are_accepted(self):
        lower = self.build(MIN_REMEDIATION_EXECUTION_SECONDS)
        upper = self.build(MAX_REMEDIATION_EXECUTION_SECONDS)
        self.assertEqual(1.0, lower._execution_max_seconds)
        self.assertEqual(600.0, upper._execution_max_seconds)

    def test_values_outside_policy_window_are_rejected(self):
        for invalid in (0.999, 600.001, 601, -1, 0):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite positive number"):
                    self.build(invalid)

    def test_non_finite_boolean_and_non_numeric_values_are_rejected(self):
        for invalid in (True, False, math.nan, math.inf, -math.inf, "not-a-number", None):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "finite positive number"):
                    self.build(invalid)


if __name__ == "__main__":
    unittest.main()
