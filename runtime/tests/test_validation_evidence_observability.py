"""Contracts for StageGuard's evidence/diagnosis and runtime-observability validation gates."""
from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_evidence_contract", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec); sys.modules[spec.name] = validator; spec.loader.exec_module(validator)

class EvidenceObservabilityValidationTests(unittest.TestCase):
    def _gate_files(self, name: str) -> set[str]:
        gate = next(g for g in validator.GATES if g.name == name)
        return {p.name for p in validator._files(gate)}

    def test_evidence_gate_owns_ingestion_investigation_and_briefing_contracts(self):
        names = self._gate_files("evidence and diagnosis")
        required = {
            "test_telemetry.py", "test_log_activation.py", "test_log_evidence.py",
            "test_investigator.py", "test_correlated_investigator.py",
            "test_briefing_runtime.py", "test_gemini_commander.py",
        }
        self.assertTrue(required <= names, f"missing evidence contracts: {sorted(required - names)}")

    def test_observability_gate_owns_grafana_recovery_and_watchdog_contracts(self):
        names = self._gate_files("runtime observability")
        required = {
            "test_grafana_runtime_observability.py", "test_recovery_observability.py",
            "test_watchdog_observability_acceptance.py", "test_watchdog_scrape_health.py",
            "test_watchdog_scrape_lifecycle_acceptance.py", "test_observability_image_pins.py",
        }
        self.assertTrue(required <= names, f"missing observability contracts: {sorted(required - names)}")

    def test_evidence_precedes_operator_mutation_and_observability_precedes_execution(self):
        order = [gate.name for gate in validator.GATES]
        self.assertLess(order.index("evidence and diagnosis"), order.index("operator API boundary"))
        self.assertLess(order.index("runtime observability"), order.index("execution safety"))

    def test_validation_contract_tests_are_owned_by_harness_gate(self):
        names = self._gate_files("validation harness")
        self.assertIn("test_validation_evidence_observability.py", names)
        self.assertIn("test_validation_durable_state_integrity.py", names)
        self.assertIn("test_validation_remediation_boundary.py", names)

if __name__ == "__main__": unittest.main()
