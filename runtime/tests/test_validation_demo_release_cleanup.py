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
    def test_owned_runtime_cleanup_stops_host_api_before_compose_and_verifies_removal(self) -> None:
        order: list[str] = []
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api", side_effect=lambda: order.append("api")) as stop_api,
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=False),
            mock.patch.object(demo_release, "_compose_down", side_effect=lambda: order.append("compose")) as compose_down,
            mock.patch.object(
                demo_release, "_compose_has_resources", side_effect=lambda: order.append("verify") or False
            ) as compose_has_resources,
        ):
            demo_release._cleanup_owned_runtime()

        stop_api.assert_called_once_with()
        compose_down.assert_called_once_with()
        compose_has_resources.assert_called_once_with()
        self.assertEqual(order, ["api", "compose", "verify"])

    def test_owned_runtime_cleanup_fails_closed_if_api_survives_stop(self) -> None:
        with (
            mock.patch.object(demo_release.demo_local, "_stop_api") as stop_api,
            mock.patch.object(demo_release.demo_local, "_api_running", return_value=True),
            mock.patch.object(demo_release, "_compose_down") as compose_down,
            mock.patch.object(demo_release, "_compose_has_resources") as compose_has_resources,
        ):
            with self.assertRaisesRegex(demo_release.EvidenceGateError, "remained reachable"):
                demo_release._cleanup_owned_runtime()

        stop_api.assert_called_once_with()
        compose_down.assert_not_called()
        compose_has_resources.assert_not_called()

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
