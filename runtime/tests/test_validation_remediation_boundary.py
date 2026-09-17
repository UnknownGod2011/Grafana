"""Contract for the consolidated validator's mutation-capable remediation boundary."""
from __future__ import annotations

import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = runpy.run_path(str(ROOT / "scripts" / "run_stageguard_validation.py"), run_name="stageguard_validation_contract")
GATES = NS["GATES"]
_files = NS["_files"]


class RemediationValidationBoundaryTests(unittest.TestCase):
    def test_remediation_gate_owns_transport_provider_receiver_and_result_contracts(self):
        gates = {gate.name: gate for gate in GATES}
        self.assertIn("remediation adapter boundary", gates)
        names = {p.name for p in _files(gates["remediation adapter boundary"])}
        required = {
            "test_remediation_receiver.py",
            "test_remediation_result_boundary.py",
            "test_production_remediation.py",
            "test_http_remediation_transport.py",
            "test_http_remediation_tls_integration.py",
        }
        self.assertTrue(required <= names, f"missing remediation safety contracts: {sorted(required - names)}")

    def test_remediation_boundary_precedes_execution_and_mcp(self):
        order = [gate.name for gate in GATES]
        remediation = order.index("remediation adapter boundary")
        self.assertLess(remediation, order.index("execution safety"))
        self.assertLess(remediation, order.index("Grafana MCP"))

    def test_local_uncertainty_barrier_is_not_omitted(self):
        execution = next(g for g in GATES if g.name == "execution safety")
        names = {p.name for p in _files(execution)}
        self.assertIn("test_local_execution_uncertainty_barrier.py", names)


if __name__ == "__main__":
    unittest.main()
