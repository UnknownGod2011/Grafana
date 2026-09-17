"""Contracts for StageGuard's operator-readiness and UI validation gate."""
from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_stageguard_validation.py"
spec = importlib.util.spec_from_file_location("stageguard_validation_operator_contract", SCRIPT)
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec); sys.modules[spec.name] = validator; spec.loader.exec_module(validator)

class OperatorReadinessValidationTests(unittest.TestCase):
    def _gate_files(self, name: str) -> set[str]:
        gate = next(g for g in validator.GATES if g.name == name)
        return {p.name for p in validator._files(gate)}

    def test_gate_owns_bootstrap_readiness_onboarding_and_ui_contracts(self):
        names = self._gate_files("operator readiness and UI")
        required = {
            "test_bootstrap.py", "test_incident_service.py", "test_onboarding.py",
            "test_readiness.py", "test_readiness_api.py", "test_readiness_local_short_circuit.py",
            "test_operator_console.py", "test_operator_console_dom.py",
            "test_operator_console_dom_requests.py", "test_operator_browser_evidence_unavailable.py",
            "test_operator_browser_execution_uncertain.py", "test_operator_integrity_policy.py",
            "test_operator_recovery_recheck.py", "test_preflight_cli.py",
            "test_stageguard_doctor.py", "test_command_line.py", "test_command_line_bounds.py",
        }
        self.assertTrue(required <= names, f"missing operator-readiness contracts: {sorted(required - names)}")

    def test_operator_readiness_precedes_api_mutation_boundary(self):
        order = [gate.name for gate in validator.GATES]
        self.assertLess(order.index("operator readiness and UI"), order.index("operator API boundary"))

    def test_contract_is_owned_by_validation_harness(self):
        self.assertIn("test_validation_operator_readiness.py", self._gate_files("validation harness"))

if __name__ == "__main__": unittest.main()
