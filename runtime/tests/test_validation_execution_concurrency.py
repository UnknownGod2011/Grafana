import unittest

import scripts.run_stageguard_validation as validation


class ExecutionConcurrencyValidationTests(unittest.TestCase):
    def test_execution_concurrency_gate_owns_exact_fake_storage_contracts(self):
        gates = {gate.name: gate for gate in validation.GATES}
        gate = gates["execution concurrency simulation"]
        expected = (
            "test_execution_gcs_multiprocess_cas.py",
            "test_execution_reconciliation_gcs_multiprocess_cas.py",
        )
        self.assertEqual(expected, gate.patterns)
        self.assertEqual(set(expected), {path.name for path in validation._files(gate)})
        self.assertFalse(any("*" in pattern for pattern in gate.patterns))

    def test_fake_concurrency_contracts_execute_under_explicit_owner(self):
        selections = tuple((gate, validation._files(gate)) for gate in validation.GATES)
        plan = validation._execution_plan(selections)
        by_name = {gate.name: (runnable, covered) for gate, runnable, covered in plan}
        runnable, _ = by_name["execution concurrency simulation"]
        self.assertEqual(
            {
                "test_execution_gcs_multiprocess_cas.py",
                "test_execution_reconciliation_gcs_multiprocess_cas.py",
            },
            {path.name for path in runnable},
        )
        _, covered = by_name["execution safety"]
        covered_names = {path.name for path in covered}
        self.assertIn("test_execution_gcs_multiprocess_cas.py", covered_names)
        self.assertIn("test_execution_reconciliation_gcs_multiprocess_cas.py", covered_names)

    def test_execution_concurrency_is_after_state_integrity_and_before_general_execution(self):
        names = [gate.name for gate in validation.GATES]
        concurrency = names.index("execution concurrency simulation")
        self.assertLess(names.index("cloud durability simulation"), concurrency)
        self.assertLess(names.index("remediation adapter boundary"), concurrency)
        self.assertLess(concurrency, names.index("execution safety"))


if __name__ == "__main__":
    unittest.main()
