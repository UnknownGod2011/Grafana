import threading
import unittest
from unittest.mock import patch

from api import (
    _EXECUTION_RECONCILIATION_REASONS,
    _LIFECYCLE_SAFETY_STATES,
    _execution_reconciliation_reason,
    _execution_reconciliation_reference,
    _lifecycle_safety_state,
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

    def __init__(
        self,
        reason,
        *,
        checkpoint_state="execution_uncertain",
        phase="unknown",
        integrity="disabled",
        reconciliation_state=None,
        reference=None,
    ):
        self.reason = reason
        self.state = checkpoint_state
        self.phase = phase
        self.integrity = integrity
        self.reconciliation_state = reconciliation_state
        self.reference = reference

    def checkpoint_state(self):
        return self.state

    def execution_checkpoint_phase(self):
        return self.phase

    def execution_reconciliation_state(self):
        if self.reconciliation_state is not None:
            return self.reconciliation_state
        return "reloaded" if self.state == "execution_uncertain" else "clear"

    def execution_reconciliation_reason(self):
        return self.reason

    def execution_reconciliation_reference(self):
        return self.reference

    def audit_integrity_state(self):
        return self.integrity

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
                    self.assertEqual("execution_uncertain", readiness["checks"]["lifecycle_safety"])
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
        self.assertEqual(1, sum(line.endswith(" 1") for line in lines))
        self.assertIn(
            'stageguard_remediation_reconciliation_reason{reason="post_dispatch_checkpoint_regression"} 1',
            lines,
        )
        for value in secret_values:
            self.assertNotIn(value, metrics)

    def test_execution_uncertainty_metric_tracks_reconciliation_barrier(self):
        """Prometheus must agree with the composite no-replay safety contract.

        A service can retain a checkpoint conflict while execution reconciliation is
        still non-clear. In that state the operator/readiness contract correctly
        treats remediation as uncertain, so the dedicated uncertainty gauge must
        also remain asserted instead of reporting a misleading zero.
        """
        uncertain = ObservableService(
            "durable_dispatching",
            checkpoint_state="conflicted",
            integrity="failed",
            reconciliation_state="reloaded",
        )
        clear_conflict = ObservableService(
            "clear",
            checkpoint_state="conflicted",
            reconciliation_state="clear",
        )
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            uncertain_metrics = _service_metrics(uncertain)
            clear_metrics = _service_metrics(clear_conflict)

        self.assertIn("stageguard_remediation_execution_uncertain 1", uncertain_metrics)
        self.assertIn("stageguard_remediation_execution_uncertain 0", clear_metrics)
        self.assertEqual("execution_uncertain_audit_failed", _lifecycle_safety_state(uncertain))
        self.assertEqual("checkpoint_conflicted", _lifecycle_safety_state(clear_conflict))

    def test_dual_execution_and_audit_failure_has_one_explicit_operator_state(self):
        reference = "sg-" + "a" * 40
        service = ObservableService(
            "durable_dispatching",
            checkpoint_state="conflicted",
            integrity="failed",
            reconciliation_state="reloaded",
            phase="dispatching",
            reference=reference,
        )

        view = _lifecycle_view(service)
        self.assertEqual("execution_uncertain_audit_failed", view["safety_state"])
        self.assertEqual("conflicted", view["checkpoint_state"])
        self.assertEqual("failed", view["audit_integrity"])
        self.assertEqual("reloaded", view["execution_reconciliation_state"])
        self.assertEqual("durable_dispatching", view["execution_reconciliation_reason"])
        self.assertEqual(reference, view["execution_reconciliation_reference"])

        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            readiness = _service_readiness(service)
            metrics = _service_metrics(service)
        self.assertFalse(readiness["ready"])
        self.assertEqual("execution_uncertain_audit_failed", readiness["checks"]["lifecycle_safety"])
        self.assertIn("stageguard_remediation_execution_uncertain 1", metrics)
        safety_lines = [
            line for line in metrics.splitlines()
            if line.startswith("stageguard_lifecycle_safety_state{")
        ]
        self.assertEqual(len(_LIFECYCLE_SAFETY_STATES), len(safety_lines))
        self.assertEqual(1, sum(line.endswith(" 1") for line in safety_lines))
        self.assertIn(
            'stageguard_lifecycle_safety_state{state="execution_uncertain_audit_failed"} 1',
            safety_lines,
        )
        self.assertNotIn(reference, metrics, "operation references must not become metric labels or samples")

    def test_invalid_reference_and_state_data_fail_closed_without_detail_leak(self):
        secret = "https://provider.example/remediate?token=secret"
        service = ObservableService(
            "durable_dispatching",
            checkpoint_state="conflicted",
            integrity="failed",
            reconciliation_state="reloaded",
            reference=secret,
        )
        self.assertIsNone(_execution_reconciliation_reference(service))
        view = _lifecycle_view(service)
        self.assertEqual("execution_uncertain_audit_failed", view["safety_state"])
        self.assertIsNone(view["execution_reconciliation_reference"])
        self.assertNotIn(secret, str(view))

    def test_invalid_or_failing_reason_collapses_to_phase_unavailable(self):
        invalid = ObservableService("provider-operation-id-should-not-be-a-label")
        self.assertEqual("phase_unavailable", _execution_reconciliation_reason(invalid))

        class FailingService(ObservableService):
            def execution_reconciliation_reason(self):
                raise RuntimeError("secret provider detail")

        self.assertEqual("phase_unavailable", _execution_reconciliation_reason(FailingService("clear")))

    def test_operator_lifecycle_view_contains_only_bounded_reason(self):
        view = _lifecycle_view(ObservableService("durable_dispatching", phase="dispatching"))
        self.assertEqual("execution_uncertain", view["safety_state"])
        self.assertEqual("execution_uncertain", view["checkpoint_state"])
        self.assertEqual("reloaded", view["execution_reconciliation_state"])
        self.assertEqual("durable_dispatching", view["execution_reconciliation_reason"])
        self.assertIsNone(view["execution_reconciliation_reference"])
        self.assertIsNone(view["incident"])

    def test_lifecycle_safety_state_distinguishes_each_fail_closed_barrier(self):
        cases = (
            (ObservableService("clear", checkpoint_state="ok", reconciliation_state="clear"), "ok"),
            (ObservableService("clear", checkpoint_state="conflicted", reconciliation_state="clear"), "checkpoint_conflicted"),
            (ObservableService("clear", checkpoint_state="conflicted", integrity="failed", reconciliation_state="clear"), "audit_integrity_failed"),
            (ObservableService("durable_dispatching"), "execution_uncertain"),
            (
                ObservableService(
                    "durable_dispatching",
                    checkpoint_state="conflicted",
                    integrity="failed",
                    reconciliation_state="reloaded",
                ),
                "execution_uncertain_audit_failed",
            ),
        )
        for service, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, _lifecycle_safety_state(service))

    def test_execution_service_reason_and_reference_getters_fail_closed(self):
        service = object.__new__(ExecutionSafeIncidentService)
        service._lock = threading.RLock()
        service._execution_uncertain = True
        service._execution_reconciliation_reason = "provider-secret"
        service._execution_uncertain_operation_id = "sg-" + "b" * 40
        self.assertEqual("phase_unavailable", service.execution_reconciliation_reason())
        self.assertEqual("sg-" + "b" * 40, service.execution_reconciliation_reference())

        service._execution_uncertain = False
        self.assertEqual("clear", service.execution_reconciliation_reason())
        self.assertIsNone(service.execution_reconciliation_reference())


if __name__ == "__main__":
    unittest.main()
