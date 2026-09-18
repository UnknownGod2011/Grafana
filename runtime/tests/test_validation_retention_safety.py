import unittest

import scripts.run_stageguard_validation as validation


class RetentionValidationOwnershipTests(unittest.TestCase):
    def test_retention_gate_owns_exact_deterministic_contracts_before_evidence(self):
        gates = {gate.name: gate for gate in validation.GATES}
        self.assertIn("retention safety", gates)
        self.assertEqual(
            (
                "test_retention_planner.py",
                "test_retention_executor.py",
                "test_retention_path_security.py",
                "test_retention_coordinator_cli.py",
            ),
            gates["retention safety"].patterns,
        )
        names = [gate.name for gate in validation.GATES]
        self.assertLess(names.index("durable state integrity"), names.index("retention safety"))
        self.assertLess(names.index("retention safety"), names.index("evidence and diagnosis"))

    def test_retention_gate_does_not_use_broad_pattern_that_could_admit_cloud_deletion(self):
        gate = next(g for g in validation.GATES if g.name == "retention safety")
        self.assertTrue(all("*" not in pattern for pattern in gate.patterns))
        self.assertTrue(all("cloud" not in pattern and "gcs" not in pattern for pattern in gate.patterns))


if __name__ == "__main__":
    unittest.main()
