from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_runner", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
# dataclasses resolves annotations through sys.modules while the module executes.
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class StageGuardValidationRunnerTests(unittest.TestCase):
    def test_every_gate_resolves_to_concrete_tests(self) -> None:
        for gate in runner.GATES:
            with self.subTest(gate=gate.name):
                self.assertTrue(runner._files(gate))

    def test_timeline_gate_includes_audit_timeline_contracts(self) -> None:
        timeline = next(gate for gate in runner.GATES if gate.name == "timeline disclosure")
        names = {path.name for path in runner._files(timeline)}
        self.assertIn("test_timeline_projection.py", names)
        self.assertIn("test_audit_timeline.py", names)
        self.assertIn("test_audit_timeline_reconciliation_projection.py", names)

    def test_file_selection_is_unique_and_deterministic(self) -> None:
        for gate in runner.GATES:
            with self.subTest(gate=gate.name):
                names = [path.name for path in runner._files(gate)]
                self.assertEqual(names, sorted(set(names)))

    def test_commands_are_scoped_to_one_concrete_file(self) -> None:
        command = runner._command(runner.TESTS / "test_timeline_projection.py")
        self.assertEqual(command[-2:], ["-p", "test_timeline_projection.py"])
        self.assertNotIn("-t", command)


if __name__ == "__main__":
    unittest.main()
