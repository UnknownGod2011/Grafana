from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_gate_selection", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationGateSelectionTests(unittest.TestCase):
    def test_no_selection_preserves_complete_gate_order(self):
        self.assertEqual(runner._select_gates(None), runner.GATES)
        self.assertEqual(runner._select_gates([]), runner.GATES)

    def test_exact_gate_selection_preserves_canonical_order_and_deduplicates(self):
        selected = runner._select_gates(["Grafana MCP", "runtime activation", "Grafana MCP"])
        self.assertEqual([gate.name for gate in selected], ["runtime activation", "Grafana MCP"])

    def test_unknown_gate_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown validation gate"):
            runner._select_gates(["grafana mcp"])

    def test_main_rejects_unknown_gate_before_launching_tests(self):
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["run_stageguard_validation.py", "--gate", "not-a-gate"]), \
             mock.patch.object(runner, "_run_test_file") as run, redirect_stderr(err):
            self.assertEqual(runner.main(), 2)
        run.assert_not_called()
        self.assertIn("unknown validation gate", err.getvalue())

    def test_main_runs_only_selected_gate(self):
        target = next(gate for gate in runner.GATES if gate.name == "Grafana MCP")
        expected = list(runner._files(target))
        self.assertTrue(expected)
        with mock.patch.object(sys, "argv", ["run_stageguard_validation.py", "--gate", "Grafana MCP"]), \
             mock.patch.object(runner, "_run_test_file", return_value=0) as run:
            self.assertEqual(runner.main(), 0)
        self.assertEqual([call.args[0] for call in run.call_args_list], expected)

    def test_full_coverage_check_remains_global_when_gate_is_focused(self):
        target = next(gate for gate in runner.GATES if gate.name == "Grafana MCP")
        unowned = runner.TESTS / "test_unowned.py"
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["run_stageguard_validation.py", "--gate", target.name, "--require-full-coverage"]), \
             mock.patch.object(runner, "_unowned_tests", return_value=(unowned,)), \
             mock.patch.object(runner, "_run_test_file") as run, redirect_stderr(err):
            self.assertEqual(runner.main(), 2)
        run.assert_not_called()
        self.assertIn("test_unowned.py", err.getvalue())


if __name__ == "__main__":
    unittest.main()
