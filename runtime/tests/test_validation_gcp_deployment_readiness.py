from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("stageguard_validation_gcp_readiness", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load validation runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GcpDeploymentReadinessValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = _load_runner()

    def test_gate_owns_only_explicit_deterministic_doctor_contracts(self) -> None:
        gate = next(g for g in self.runner.GATES if g.name == "GCP deployment readiness")
        self.assertEqual(
            gate.patterns,
            (
                "test_gcp_deploy_doctor.py",
                "test_gcp_deploy_doctor_fake_gcloud.py",
                "test_gcp_deploy_doctor_process_failures.py",
                "test_gcp_deploy_doctor_serialization.py",
                "test_gcp_identifiers.py",
            ),
        )
        selected = {path.name for path in self.runner._files(gate)}
        self.assertEqual(selected, set(gate.patterns))
        self.assertFalse(any("*" in pattern for pattern in gate.patterns))

    def test_readiness_follows_static_deploy_contract_and_precedes_runtime_bridge(self) -> None:
        names = [gate.name for gate in self.runner.GATES]
        self.assertLess(names.index("cloud deployment contract"), names.index("GCP deployment readiness"))
        self.assertLess(names.index("GCP deployment readiness"), names.index("cloud runtime metrics bridge"))


if __name__ == "__main__":
    unittest.main()
