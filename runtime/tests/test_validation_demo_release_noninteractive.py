from __future__ import annotations

import builtins
import subprocess
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

    def test_compose_down_rejects_failed_teardown(self) -> None:
        completed = subprocess.CompletedProcess(args=["docker", "compose", "down"], returncode=17)
        with mock.patch.object(demo_release.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "exit code 17"):
                demo_release._compose_down()

    def test_recreate_does_not_claim_fresh_boundary_after_failed_teardown(self) -> None:
        with mock.patch.object(
            demo_release, "_compose_down", side_effect=demo_release.EvidenceGateError("teardown failed")
        ):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "teardown failed"):
                demo_release._recreate_compose_stack()

    def test_cleanup_stops_stack_after_success(self) -> None:
        values = iter((0.1, 0.0, 12.0, 3.0))
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_recreate_compose_stack"),
            mock.patch.object(demo_release.demo_local, "up"),
            mock.patch.object(demo_release, "_wait_for", side_effect=lambda *args, **kwargs: next(values)),
            mock.patch.object(demo_release.demo_local, "inject_fault"),
            mock.patch.object(demo_release, "_compose_down") as down_mock,
        ):
            result = demo_release.main(["--non-interactive", "--cleanup"])

        self.assertEqual(result, 0)
        down_mock.assert_called_once_with()

    def test_cleanup_failure_turns_successful_acceptance_into_failure(self) -> None:
        values = iter((0.1, 0.0, 12.0, 3.0))
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_recreate_compose_stack"),
            mock.patch.object(demo_release.demo_local, "up"),
            mock.patch.object(demo_release, "_wait_for", side_effect=lambda *args, **kwargs: next(values)),
            mock.patch.object(demo_release.demo_local, "inject_fault"),
            mock.patch.object(
                demo_release, "_compose_down", side_effect=demo_release.EvidenceGateError("cleanup failed")
            ),
        ):
            result = demo_release.main(["--non-interactive", "--cleanup"])

        self.assertEqual(result, 1)

    def test_cleanup_stops_stack_after_evidence_failure(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_recreate_compose_stack"),
            mock.patch.object(demo_release.demo_local, "up"),
            mock.patch.object(demo_release, "_wait_for", side_effect=demo_release.EvidenceGateError("missing evidence")),
            mock.patch.object(demo_release, "_compose_down") as down_mock,
        ):
            result = demo_release.main(["--non-interactive", "--cleanup"])

        self.assertEqual(result, 1)
        down_mock.assert_called_once_with()

    def test_cleanup_stops_partially_started_stack(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_recreate_compose_stack"),
            mock.patch.object(demo_release.demo_local, "up", side_effect=demo_release.demo_local.DemoError("startup failed")),
            mock.patch.object(demo_release, "_compose_down") as down_mock,
        ):
            result = demo_release.main(["--non-interactive", "--cleanup"])

        self.assertEqual(result, 1)
        down_mock.assert_called_once_with()

    def test_cleanup_does_not_touch_preexisting_stack(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=True),
            mock.patch.object(demo_release, "_compose_down") as down_mock,
        ):
            result = demo_release.main(["--non-interactive", "--cleanup"])

        self.assertEqual(result, 1)
        down_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
