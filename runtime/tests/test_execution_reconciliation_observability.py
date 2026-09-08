import threading
import unittest
from unittest.mock import patch

from api import (
    _EXECUTION_RECONCILIATION_REASONS,
    _execution_reconciliation_reason,
    _lifecycle_view,
    _service_metrics,
    _service_readiness,
)
from execution_safety import ExecutionSafeIncidentService


class ReadyResult:
    def to_dict(self):
        return {"ready": True, "checks": {"prometheus_mcp": "ok", "loki_mcp": "ok"}}


class ReadyProbe:
    def check(self):
        return ReadyResult()

    def prometheus_metrics(self):
        return ""


class ObservableService:
    _checkpoint_store = None

    def __init__(self, reason, *, checkpoint_state="execution_uncertain", phase="unknown"):
        self.reason = reason
        self.state = checkpoint_state
        self.phase = phase

    def checkpoint_state(self):
        return self.state

    def execution_checkpoint_phase(self):
        return self.phase

    def execution_reconciliation_state(self):
        return "reloaded" if self.state == "execution_uncertain" else "clear"

    def execution_reconciliation_reason(self):
        return self.reason

    def status(self):
        return None


class ExecutionReconciliationObservabilityTests(unittest.TestCase):
    def test_every_bounded_uncertainty_reason_blocks_readiness(self):
        uncertain_reasons = [reason for reason in _EXECUTION_RECONCILIATION_REASONS if reason != "clear"]
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            for reason in uncertain_reasons:
                with self.subTest(reason=reason):
                    readiness = _service_readiness(ObservableService(reason))
                    self.assertFalse(readiness["ready"])
                    self.assertEqual("execution_uncertain", readiness["checks"]["checkpoint"])
                    self.assertEqual(reason, readiness["checks"]["remediation_reconciliation_reason"])

    def test_reason_metric_is_one_hot_and_has_fixed_cardinality(self):
        secret_values = (
            "incident-001",
            "operation-2b3402",
            "https://provider.example/remediate",
            "broadcast-alpha",
        )
        service = ObservableService("post_dispatch_checkpoint_regression")
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            metrics = _service_metrics(service)

        lines = [
            line for line in metrics.splitlines()
            if line.startswith("stageguard_remediation_reconciliation_reason{")
        ]
        self.assertEqual(len(_EXECUTION_RECONCILIATION_REASONS), len(lines))
        self.assertEqual(
            1,
            sum(line.endswith(" 1") for line in lines),
        )
        self.assertIn(
            'stageguard_remediation_reconciliation_reason{reason="post_dispatch_checkpoint_regression"} 1',
            lines,
        )
        for value in secret_values:
            self.assertNotIn(value, metrics)

    def test_invalid_or_failing_reason_collapses_to_phase_unavailable(self):
        invalid = ObservableService("provider-operation-id-should-not-be-a-label")
        self.assertEqual("phase_unavailable", _execution_reconciliation_reason(invalid))

        class FailingService(ObservableService):
            def execution_reconciliation_reason(self):
                raise RuntimeError("secret provider detail")

        self.assertEqual("phase_unavailable", _execution_reconciliation_reason(FailingService("clear")))

    def test_operator_lifecycle_view_contains_only_bounded_reason(self):
        view = _lifecycle_view(ObservableService("durable_dispatching", phase="dispatching"))
        self.assertEqual("execution_uncertain", view["checkpoint_state"])
        self.assertEqual("reloaded", view["execution_reconciliation_state"])
        self.assertEqual("durable_dispatching", view["execution_reconciliation_reason"])
        self.assertIsNone(view["incident"])

    def test_execution_service_reason_getter_fails_closed_to_fixed_enum(self):
        service = object.__new__(ExecutionSafeIncidentService)
        service._lock = threading.RLock()
        service._execution_uncertain = True
        service._execution_reconciliation_reason = "provider-secret"
        self.assertEqual("phase_unavailable", service.execution_reconciliation_reason())

        service._execution_uncertain = False
        self.assertEqual("clear", service.execution_reconciliation_reason())


if __name__ == "__main__":
    unittest.main()
