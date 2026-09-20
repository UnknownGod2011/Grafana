from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import demo_release


class DemoReleaseCleanupTests(unittest.TestCase):
    def test_owned_runtime_cleanup_stops_and_verifies_both_runtime_components(self) -> None:
        order: list[str] = []
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api", side_effect=lambda: order.append("api-stop")) as stop_api,
            mock.patch.object(demo_release.demo_local, "_api_running", side_effect=lambda: order.append("api-verify") or False),
            mock.patch.object(demo_release, "_compose_down", side_effect=lambda: order.append("compose-down")) as compose_down,
            mock.patch.object(
                demo_release, "_compose_has_resources", side_effect=lambda: order.append("compose-verify") or False
            ) as compose_has_resources,
        ):
            demo_release._cleanup_owned_runtime()

        stop_api.assert_called_once_with()
        compose_down.assert_called_once_with()
        compose_has_resources.assert_called_once_with()
        self.assertEqual(order, ["api-stop", "api-verify", "compose-down", "compose-verify"])

    def test_api_survival_does_not_prevent_owned_compose_cleanup(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api") as stop_api,
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=True),
            mock.patch.object(demo_release, "_compose_down") as compose_down,
            mock.patch.object(demo_release, "_compose_has_resources", return_value=False) as compose_has_resources,
        ):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "API remained reachable"):
                demo_release._cleanup_owned_runtime()

        stop_api.assert_called_once_with()
        compose_down.assert_called_once_with()
        compose_has_resources.assert_called_once_with()

    def test_api_stop_exception_does_not_prevent_owned_compose_cleanup(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api", side_effect=RuntimeError("stop broke")),
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_compose_down") as compose_down,
            mock.patch.object(demo_release, "_compose_has_resources", return_value=False) as compose_has_resources,
        ):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "API stop failed"):
                demo_release._cleanup_owned_runtime()

        compose_down.assert_called_once_with()
        compose_has_resources.assert_called_once_with()

    def test_compose_down_failure_still_verifies_compose_postcondition(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api"),
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(
                demo_release, "_compose_down", side_effect=demo_release.EvidenceGateError("docker failed")
            ),
            mock.patch.object(demo_release, "_compose_has_resources", return_value=True) as compose_has_resources,
        ):
            with self.assertRaises(demo_release.EvidenceGateError) as raised:
                demo_release._cleanup_owned_runtime()

        compose_has_resources.assert_called_once_with()
        message = str(raised.exception)
        self.assertIn("compose teardown failed", message)
        self.assertIn("compose resources remained", message)

    def test_owned_runtime_cleanup_fails_closed_if_compose_resources_survive_down(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api") as stop_api,
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_compose_down") as compose_down,
            mock.patch.object(demo_release, "_compose_has_resources", return_value=True) as compose_has_resources,
        ):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "compose resources remained"):
                demo_release._cleanup_owned_runtime()

        stop_api.assert_called_once_with()
        compose_down.assert_called_once_with()
        compose_has_resources.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
