from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_runner", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class StageGuardValidationRunnerTests(unittest.TestCase):
    def test_every_gate_resolves_to_concrete_tests(self) -> None:
        for gate in runner.GATES:
            with self.subTest(gate=gate.name):
                self.assertTrue(runner._files(gate))

    def test_validation_harness_gate_owns_runner_regressions(self) -> None:
        harness = next(gate for gate in runner.GATES if gate.name == "validation harness")
        names = {path.name for path in runner._files(harness)}
        self.assertEqual(names, {"test_stageguard_validation_runner.py"})

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

    def test_command_rejects_paths_outside_test_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "test_timeline_projection.py"
            outside.write_text("pass\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner._command(outside)

    def test_safe_test_file_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests = root / "tests"
            tests.mkdir()
            target = root / "outside.py"
            target.write_text("pass\n", encoding="utf-8")
            link = tests / "test_link.py"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with mock.patch.object(runner, "TESTS", tests):
                self.assertFalse(runner._safe_test_file(link))

    def test_safe_test_file_accepts_direct_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tests = Path(directory) / "tests"
            tests.mkdir()
            test_file = tests / "test_ok.py"
            test_file.write_text("pass\n", encoding="utf-8")
            with mock.patch.object(runner, "TESTS", tests):
                self.assertTrue(runner._safe_test_file(test_file))

    def test_default_file_timeout_is_bounded(self) -> None:
        self.assertGreater(runner.DEFAULT_FILE_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(runner.DEFAULT_FILE_TIMEOUT_SECONDS, 300)
        self.assertLessEqual(
            runner.DEFAULT_FILE_TIMEOUT_SECONDS, runner.MAX_FILE_TIMEOUT_SECONDS
        )

    def test_timeout_parser_rejects_unbounded_non_positive_or_excessive_values(self) -> None:
        excessive = str(runner.MAX_FILE_TIMEOUT_SECONDS + 1)
        for value in ("0", "-1", "nan", "inf", "-inf", excessive, "1e308"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    runner._positive_timeout(value)

    def test_timeout_parser_accepts_fractional_seconds_and_maximum(self) -> None:
        self.assertEqual(runner._positive_timeout("2.5"), 2.5)
        maximum = str(runner.MAX_FILE_TIMEOUT_SECONDS)
        self.assertEqual(runner._positive_timeout(maximum), runner.MAX_FILE_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
