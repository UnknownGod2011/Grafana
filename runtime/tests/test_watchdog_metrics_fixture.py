from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from watchdog_metrics_fixture import WatchdogFixtureState, make_server  # noqa: E402


class WatchdogMetricsFixtureTests(unittest.TestCase):
    def test_states_emit_exact_watchdog_series(self) -> None:
        state = WatchdogFixtureState()
        idle = state.prometheus_metrics()
        self.assertIn("stageguard_remediation_execution_active 0", idle)
        self.assertIn("stageguard_remediation_execution_deadline_exceeded 0", idle)
        self.assertIn("stageguard_remediation_execution_max_seconds 60.0", idle)

        state.set("active")
        active = state.prometheus_metrics()
        self.assertIn("stageguard_remediation_execution_active 1", active)
        self.assertIn("stageguard_remediation_execution_age_seconds 12.0", active)
        self.assertIn("stageguard_remediation_execution_deadline_exceeded 0", active)

        state.set("overdue")
        overdue = state.prometheus_metrics()
        self.assertIn("stageguard_remediation_execution_active 1", overdue)
        self.assertIn("stageguard_remediation_execution_age_seconds 75.0", overdue)
        self.assertIn("stageguard_remediation_execution_max_seconds 60.0", overdue)
        self.assertIn("stageguard_remediation_execution_deadline_exceeded 1", overdue)

    def test_telemetry_availability_is_independent_of_remediation_state(self) -> None:
        state = WatchdogFixtureState()
        state.set("active")
        name, snapshot, available = state.snapshot()
        self.assertEqual(name, "active")
        self.assertEqual(snapshot["active"], 1)
        self.assertTrue(available)

        state.set_telemetry_available(False)
        name, snapshot, available = state.snapshot()
        self.assertEqual(name, "active")
        self.assertEqual(snapshot["active"], 1)
        self.assertFalse(available)
        with self.assertRaises(RuntimeError):
            state.prometheus_metrics()

        state.set_telemetry_available(True)
        self.assertIn("stageguard_remediation_execution_active 1", state.prometheus_metrics())

    def test_fixture_rejects_unknown_state(self) -> None:
        state = WatchdogFixtureState()
        with self.assertRaises(ValueError):
            state.set("provider-success")

    def test_fixture_rejects_non_boolean_telemetry_availability(self) -> None:
        state = WatchdogFixtureState()
        for value in (0, 1, "offline", None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    state.set_telemetry_available(value)  # type: ignore[arg-type]

    def test_http_control_surface_is_bounded_to_named_scenarios(self) -> None:
        server = make_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            request = urllib.request.Request(f"{base}/scenario/overdue", data=b"", method="POST")
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
            with urllib.request.urlopen(f"{base}/state", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["state"], "overdue")
            self.assertEqual(payload["exceeded"], 1)
            self.assertTrue(payload["telemetry_available"])

            bad = urllib.request.Request(f"{base}/scenario/arbitrary-provider-action", data=b"", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(bad, timeout=2)
            self.assertEqual(caught.exception.code, 404)

            with urllib.request.urlopen(f"{base}/metrics", timeout=2) as response:
                metrics = response.read().decode("utf-8")
            self.assertIn("stageguard_remediation_execution_deadline_exceeded 1", metrics)
            self.assertNotIn("provider", metrics.lower())
            self.assertNotIn("token", metrics.lower())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_telemetry_outage_returns_503_without_mutating_state(self) -> None:
        server = make_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            active = urllib.request.Request(f"{base}/scenario/active", data=b"", method="POST")
            urllib.request.urlopen(active, timeout=2).close()

            offline = urllib.request.Request(f"{base}/telemetry/offline", data=b"", method="POST")
            urllib.request.urlopen(offline, timeout=2).close()
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f"{base}/metrics", timeout=2)
            self.assertEqual(caught.exception.code, 503)

            with urllib.request.urlopen(f"{base}/state", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["state"], "active")
            self.assertEqual(payload["active"], 1)
            self.assertFalse(payload["telemetry_available"])

            online = urllib.request.Request(f"{base}/telemetry/online", data=b"", method="POST")
            urllib.request.urlopen(online, timeout=2).close()
            with urllib.request.urlopen(f"{base}/metrics", timeout=2) as response:
                metrics = response.read().decode("utf-8")
            self.assertIn("stageguard_remediation_execution_active 1", metrics)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
