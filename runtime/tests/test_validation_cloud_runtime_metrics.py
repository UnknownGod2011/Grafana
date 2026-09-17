"""Contracts for StageGuard's cloud runtime metrics validation gate."""
from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_cloud_metrics_contract", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec); sys.modules[spec.name] = validator; spec.loader.exec_module(validator)

class CloudRuntimeMetricsValidationTests(unittest.TestCase):
    def _gate_files(self, name: str) -> set[str]:
        gate = next(g for g in validator.GATES if g.name == name)
        return {p.name for p in validator._files(gate)}

    def test_gate_owns_bridge_and_acceptance_unit_contracts(self):
        names = self._gate_files("cloud runtime metrics bridge")
        required = {"test_cloud_run_metrics_bridge.py", "test_cloud_run_metrics_acceptance.py"}
        self.assertTrue(required <= names, f"missing cloud metrics contracts: {sorted(required - names)}")

    def test_cloud_metrics_precedes_runtime_observability(self):
        order = [gate.name for gate in validator.GATES]
        self.assertLess(order.index("cloud runtime metrics bridge"), order.index("runtime observability"))

    def test_contract_is_owned_by_validation_harness(self):
        self.assertIn("test_validation_cloud_runtime_metrics.py", self._gate_files("validation harness"))

if __name__ == "__main__": unittest.main()
