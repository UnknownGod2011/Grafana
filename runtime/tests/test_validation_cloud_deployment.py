from __future__ import annotations

import unittest

import test_stageguard_validation_runner as validation


class CloudDeploymentValidationOwnershipTests(unittest.TestCase):
    def test_cloud_deployment_gate_owns_deterministic_deployment_contracts(self) -> None:
        gate = next(gate for gate in validation.RUNNER.GATES if gate.name == "cloud deployment contract")
        owned = {path.name for path in validation.RUNNER._files(gate)}
        self.assertEqual(
            owned,
            {
                "test_cloud_run_deploy_contract.py",
                "test_cloud_run_deploy_shell.py",
                "test_deploy_cloud_run_script.py",
                "test_cloudrun_entrypoint.py",
            },
        )

    def test_deployment_contract_precedes_metrics_and_observability(self) -> None:
        names = [gate.name for gate in validation.RUNNER.GATES]
        deployment = names.index("cloud deployment contract")
        self.assertLess(deployment, names.index("cloud runtime metrics bridge"))
        self.assertLess(deployment, names.index("runtime observability"))

    def test_live_or_credentialed_acceptance_is_not_selected_by_deployment_gate(self) -> None:
        gate = next(gate for gate in validation.RUNNER.GATES if gate.name == "cloud deployment contract")
        patterns = set(gate.patterns)
        self.assertNotIn("test_gemini_acceptance_smoke.py", patterns)
        self.assertNotIn("test_gcs_*.py", patterns)
        self.assertNotIn("test_fake_cloud_restart_acceptance.py", patterns)


if __name__ == "__main__":
    unittest.main()
