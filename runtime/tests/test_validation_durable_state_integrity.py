from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_durable_contract", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class DurableStateValidationContractTests(unittest.TestCase):
    def test_gate_owns_checkpoint_security_and_persistence_integrity(self):
        gate = next(g for g in runner.GATES if g.name == "durable state integrity")
        names = {path.name for path in runner._files(gate)}
        self.assertIn("test_checkpoint_file_security.py", names)
        self.assertTrue(
            any("integrity" in name and name != Path(__file__).name for name in names),
            f"durable state gate has no independent integrity contract: {sorted(names)}",
        )

    def test_durable_state_precedes_operator_mutation_gates(self):
        names = [gate.name for gate in runner.GATES]
        durable = names.index("durable state integrity")
        self.assertLess(durable, names.index("operator API boundary"))
        self.assertLess(durable, names.index("operator concurrency"))
        self.assertLess(durable, names.index("incident lifecycle"))


if __name__ == "__main__":
    unittest.main()
