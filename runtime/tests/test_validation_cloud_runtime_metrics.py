"""Contracts for StageGuard's cloud runtime metrics validation gate."""
from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_cloud_metrics_contract", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec); sys.modules[spec.name] = validator; spec.loader.exec_module(validator)

EXPECTED = {
    "test_cloud_run_metrics_bridge.py",
    "test_cloud_run_metrics_acceptance.py",
    "test_cloud_run_metrics_bridge_audience_boundary.py",
    "test_cloud_run_metrics_bridge_bounds.py",
    "test_cloud_run_metrics_bridge_inbound_auth.py",
    "test_cloud_run_metrics_bridge_redirects.py",
    "test_cloud_run_metrics_bridge_sentinel_family.py",
}

class CloudRuntimeMetricsValidationTests(unittest.TestCase):
    def _gate(self, name: str):
        return next(g for g in validator.GATES if g.name == name)

    def _gate_files(self, name: str) -> set[str]:
        return {p.name for p in validator._files(self._gate(name))}

    def test_gate_owns_all_audited_dependency_light_bridge_contracts(self):
        self.assertEqual(self._gate_files("cloud runtime metrics bridge"), EXPECTED)

    def test_gate_uses_exact_filenames_only(self):
        patterns = self._gate("cloud runtime metrics bridge").patterns
        self.assertEqual(set(patterns), EXPECTED)
        self.assertFalse(any(any(char in pattern for char in "*?[") for pattern in patterns))

    def test_live_or_future_metrics_tests_do_not_enter_by_filename_family(self):
        # The credentialed/Docker acceptance boundary must remain deliberately
        # classified rather than being swept in by a broad metrics wildcard.
        self.assertNotIn("test_cloud_run_metrics_live_acceptance.py", self._gate_files("cloud runtime metrics bridge"))

    def test_cloud_metrics_precedes_runtime_observability(self):
        order = [gate.name for gate in validator.GATES]
        self.assertLess(order.index("cloud runtime metrics bridge"), order.index("runtime observability"))

    def test_contract_is_owned_by_validation_harness(self):
        self.assertIn("test_validation_cloud_runtime_metrics.py", self._gate_files("validation harness"))

if __name__ == "__main__": unittest.main()
