from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("stageguard_validation_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validation runner: {RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidationFullCoverageTests(unittest.TestCase):
    """Keep dependency-light runtime-test ownership fail-visible as the suite grows."""

    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_every_safe_runtime_test_has_an_intentional_gate_owner(self):
        selections = tuple(
            (gate, self.runner._files(gate)) for gate in self.runner.GATES
        )
        unowned = self.runner._unowned_tests(selections)
        self.assertEqual(
            (),
            tuple(path.name for path in unowned),
            "safe runtime tests must be classified into a validation gate or "
            "explicitly moved outside the dependency-light runtime-test boundary",
        )

    def test_every_gate_resolves_at_least_one_safe_test(self):
        empty = tuple(
            gate.name for gate in self.runner.GATES if not self.runner._files(gate)
        )
        self.assertEqual((), empty, "production validation gates must not silently go empty")

    def test_execution_plan_runs_each_owned_test_at_most_once(self):
        selections = tuple(
            (gate, self.runner._files(gate)) for gate in self.runner.GATES
        )
        plan = self.runner._execution_plan(selections)
        runnable = [path.name for _, files, _ in plan for path in files]
        self.assertEqual(len(runnable), len(set(runnable)))


if __name__ == "__main__":
    unittest.main()
