import unittest

from api import _execution_checkpoint_phase, _service_metrics, _service_readiness


class ReadinessResult:
    def __init__(self, ready=True):
        self.ready = ready

    def to_dict(self):
        return {
            "ready": self.ready,
            "checks": {
                "metric_activation": "ok",
                "loki_activation": "ok",
                "prometheus_mcp": "ok",
                "loki_mcp": "ok",
            },
        }


class ReadinessProbe:
    def check(self):
        return ReadinessResult(True)

    def prometheus_metrics(self):
        return "stageguard_evidence_plane_ready 1\n"


class FakeService:
    def __init__(self, *, phase="none", checkpoint="synchronized"):
        self.phase = phase
        self.checkpoint = checkpoint
        self._readiness_probe = ReadinessProbe()
        self._checkpoint_store = None

    def execution_checkpoint_phase(self):
        return self.phase

    def checkpoint_state(self):
        return self.checkpoint


class ExecutionPhaseObservabilityTests(unittest.TestCase):
    def test_metrics_emit_exactly_one_active_fixed_phase_label(self):
        service = FakeService(phase="dispatching", checkpoint="execution_uncertain")

        metrics = _service_metrics(service)

        phases = ("none", "approved", "dispatching", "resolved", "legacy_unknown", "unknown")
        for phase in phases:
            expected = 1 if phase == "dispatching" else 0
            self.assertIn(
                f'stageguard_remediation_execution_phase{{phase="{phase}"}} {expected}\n',
                metrics,
            )
        self.assertIn("stageguard_remediation_execution_uncertain 1\n", metrics)
        self.assertNotIn("incident_id", metrics)
        self.assertNotIn("operation_id", metrics)
        self.assertNotIn("production_id", metrics)
        self.assertNotIn("endpoint=", metrics)
        self.assertNotIn("credential", metrics.lower())

    def test_readiness_contains_only_bounded_execution_phase(self):
        readiness = _service_readiness(FakeService(phase="approved"))

        self.assertTrue(readiness["ready"])
        self.assertEqual("approved", readiness["checks"]["remediation_execution_phase"])

    def test_execution_uncertainty_forces_not_ready_and_reports_dispatching(self):
        readiness = _service_readiness(
            FakeService(phase="dispatching", checkpoint="execution_uncertain")
        )

        self.assertFalse(readiness["ready"])
        self.assertEqual("execution_uncertain", readiness["checks"]["checkpoint"])
        self.assertEqual("dispatching", readiness["checks"]["remediation_execution_phase"])

    def test_unknown_or_broken_phase_fails_closed_to_unknown(self):
        bad = FakeService(phase="surprise")
        self.assertEqual("unknown", _execution_checkpoint_phase(bad))

        class Broken(FakeService):
            def execution_checkpoint_phase(self):
                raise RuntimeError("boom")

        self.assertEqual("unknown", _execution_checkpoint_phase(Broken()))


if __name__ == "__main__":
    unittest.main()
