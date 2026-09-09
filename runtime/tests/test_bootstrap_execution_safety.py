from pathlib import Path
import tempfile
import unittest

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from audit_anchor import DEFAULT_ANCHOR_INTERVAL, MAX_VERIFICATION_SUFFIX_EVENTS
from bootstrap import build_runtime
from execution_safety import ExecutionSafeIncidentService


class FakeMetrics:
    datasource_uid = "prom-main"

    def __init__(self):
        self.closed = False

    def instant(self, _promql):
        return 1.0

    def close(self):
        self.closed = True


class BootstrapExecutionSafetyTests(unittest.TestCase):
    def _bundle(self, root: Path, **kwargs):
        example = Path(__file__).parents[1] / "telemetry.example.json"
        return build_runtime(
            telemetry_config=example,
            activation_path=None,
            audit_path=root / "audit.jsonl",
            host="127.0.0.1",
            port=0,
            checkpoint_backend="none",
            metrics_factory=FakeMetrics,
            **kwargs,
        )

    def test_runtime_composes_anchor_and_execution_safety_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle(Path(tmp))
            try:
                self.assertIsInstance(bundle.service, AnchoredExecutionSafeIncidentService)
                self.assertIsInstance(bundle.service, ExecutionSafeIncidentService)
                self.assertIsInstance(bundle.service._audit, AnchoredJsonlAuditLog)
                self.assertEqual("synchronized", bundle.service.checkpoint_state())
                self.assertEqual("clear", bundle.service.execution_reconciliation_state())
                self.assertEqual(DEFAULT_ANCHOR_INTERVAL, bundle.service.audit_anchor_state()["interval"])
            finally:
                bundle.close()

    def test_runtime_accepts_bounded_anchor_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle(Path(tmp), audit_anchor_interval=17)
            try:
                self.assertEqual(17, bundle.service.audit_anchor_state()["interval"])
            finally:
                bundle.close()

    def test_runtime_rejects_anchor_interval_outside_verification_bound(self):
        for value in (0, MAX_VERIFICATION_SUFFIX_EVENTS + 1, True):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, "audit anchor interval"):
                    self._bundle(Path(tmp), audit_anchor_interval=value)


if __name__ == "__main__":
    unittest.main()
