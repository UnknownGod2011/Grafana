from __future__ import annotations

import builtins
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import demo_release


class DemoReleaseNonInteractiveTests(unittest.TestCase):
    def test_non_interactive_confirmation_never_reads_stdin(self) -> None:
        with mock.patch.object(builtins, "input", side_effect=AssertionError("stdin must not be read")):
            demo_release._confirm_fault_injection(non_interactive=True)

    def test_interactive_confirmation_retains_operator_pause(self) -> None:
        with mock.patch.object(builtins, "input", return_value="") as input_mock:
            demo_release._confirm_fault_injection(non_interactive=False)
        input_mock.assert_called_once()

    def test_non_interactive_main_runs_baseline_then_fault_without_prompt(self) -> None:
        values = iter((0.1, 0.0, 12.0, 3.0))
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_recreate_compose_stack"),
            mock.patch.object(demo_release.demo_local, "up") as up_mock,
            mock.patch.object(demo_release, "_wait_for", side_effect=lambda *args, **kwargs: next(values)) as wait_mock,
            mock.patch.object(demo_release.demo_local, "inject_fault") as inject_mock,
            mock.patch.object(builtins, "input", side_effect=AssertionError("stdin must not be read")),
        ):
            result = demo_release.main(["--non-interactive"])

        self.assertEqual(result, 0)
        up_mock.assert_called_once_with(fresh=True, enable_gemini=False, open_browser=False)
        self.assertEqual(wait_mock.call_count, 4)
        inject_mock.assert_called_once_with(settle_seconds=0)


if __name__ == "__main__":
    unittest.main()
