from pathlib import Path
import tempfile
import unittest

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
    def test_runtime_composes_execution_safe_service_by_default(self):
        example = Path(__file__).parents[1] / "telemetry.example.json"
        with tempfile.TemporaryDirectory() as tmp:
            bundle = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=Path(tmp) / "audit.jsonl",
                host="127.0.0.1",
                port=0,
                checkpoint_backend="none",
                metrics_factory=FakeMetrics,
            )
            try:
                self.assertIsInstance(bundle.service, ExecutionSafeIncidentService)
                self.assertEqual("synchronized", bundle.service.checkpoint_state())
                self.assertEqual("clear", bundle.service.execution_reconciliation_state())
            finally:
                bundle.close()


if __name__ == "__main__":
    unittest.main()
