import unittest

import scripts.run_stageguard_validation as validation


class CloudDurabilityValidationTests(unittest.TestCase):
    def test_cloud_durability_gate_owns_only_fake_storage_contracts(self):
        gates = {gate.name: gate for gate in validation.GATES}
        gate = gates["cloud durability simulation"]
        self.assertEqual(
            (
                "test_gcs_checkpoint.py",
                "test_gcs_multiprocess_cas.py",
                "test_fake_cloud_restart_acceptance.py",
            ),
            gate.patterns,
        )
        selected = {path.name for path in validation._files(gate)}
        self.assertEqual(set(gate.patterns), selected)
        self.assertFalse(any("*" in pattern for pattern in gate.patterns))

    def test_cloud_durability_precedes_mutation_and_cloud_deployment_boundaries(self):
        names = [gate.name for gate in validation.GATES]
        cloud_durability = names.index("cloud durability simulation")
        self.assertLess(names.index("durable state integrity"), cloud_durability)
        self.assertLess(cloud_durability, names.index("operator API boundary"))
        self.assertLess(cloud_durability, names.index("remediation adapter boundary"))
        self.assertLess(cloud_durability, names.index("cloud deployment contract"))


if __name__ == "__main__":
    unittest.main()
