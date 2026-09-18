import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("stageguard_validation_execution_ownership", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ExecutionSafetyOwnershipTests(unittest.TestCase):
    def test_general_execution_gate_is_exact_and_future_safe(self):
        runner = _load_runner()
        gate = next(g for g in runner.GATES if g.name == "execution safety")
        self.assertNotIn("test_*execution*.py", gate.patterns)
        self.assertTrue(gate.patterns)
        self.assertTrue(all("*" not in pattern and "?" not in pattern for pattern in gate.patterns))

    def test_every_current_execution_named_test_has_an_explicit_execution_owner(self):
        runner = _load_runner()
        explicit_names = set()
        for gate_name in ("execution concurrency simulation", "execution safety"):
            gate = next(g for g in runner.GATES if g.name == gate_name)
            explicit_names.update(gate.patterns)

        current = {
            path.name
            for path in runner.TESTS.glob("test_*execution*.py")
            if runner._safe_test_file(path)
        }
        # Operator watchdog execution is intentionally owned by operator concurrency.
        current.discard("test_api_execution_watchdog.py")
        # Validation contracts are intentionally owned by the validation harness.
        current = {name for name in current if not name.startswith("test_validation_")}
        self.assertEqual(current, explicit_names - {"test_local_execution_uncertainty_barrier.py"})

    def test_concurrency_pair_remains_earliest_owned_by_simulation_gate(self):
        runner = _load_runner()
        selections = tuple((gate, runner._files(gate)) for gate in runner.GATES)
        plan = runner._execution_plan(selections)
        by_name = {gate.name: (runnable, covered) for gate, runnable, covered in plan}
        concurrency = {p.name for p in by_name["execution concurrency simulation"][0]}
        self.assertEqual(concurrency, {
            "test_execution_gcs_multiprocess_cas.py",
            "test_execution_reconciliation_gcs_multiprocess_cas.py",
        })
        general = {p.name for p in by_name["execution safety"][0]}
        self.assertTrue(concurrency.isdisjoint(general))


if __name__ == "__main__":
    unittest.main()
