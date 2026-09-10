from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "runtime" / "watchdog_observability_acceptance.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("watchdog_observability_acceptance", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load watchdog acceptance module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchdogObservabilityAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_alert_title_match_is_active(self) -> None:
        payload = [
            {
                "labels": {"alertname": self.module.ALERT_TITLE},
                "annotations": {},
            }
        ]
        self.assertTrue(self.module.grafana_alert_active_from_payload(payload))

    def test_summary_match_is_active(self) -> None:
        payload = [
            {
                "labels": {},
                "annotations": {"summary": self.module.ALERT_SUMMARY},
            }
        ]
        self.assertTrue(self.module.grafana_alert_active_from_payload(payload))

    def test_unrelated_active_alert_does_not_block_resolution(self) -> None:
        payload = [
            {
                "labels": {"alertname": "Different alert"},
                "annotations": {"summary": "Different summary"},
            }
        ]
        self.assertFalse(self.module.grafana_alert_active_from_payload(payload))

    def test_empty_active_alert_list_is_resolved(self) -> None:
        self.assertFalse(self.module.grafana_alert_active_from_payload([]))

    def test_unexpected_root_shape_fails_closed(self) -> None:
        for payload in ({}, None, "[]", 1):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.module.grafana_alert_active_from_payload(payload)

    def test_malformed_alert_entry_fails_closed(self) -> None:
        for payload in ([None], [{"labels": [], "annotations": {}}], [{"labels": {}, "annotations": []}]):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.module.grafana_alert_active_from_payload(payload)

    def test_loopback_guard_rejects_remote_or_credentialed_origins(self) -> None:
        rejected = (
            "https://127.0.0.1:3000",
            "http://example.com:3000",
            "http://admin:secret@127.0.0.1:3000",
            "http://127.0.0.1:3000/path",
            "http://127.0.0.1:3000?query=1",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.module._require_loopback_http(value, "grafana")

    def test_loopback_guard_accepts_local_origins(self) -> None:
        self.assertEqual(
            self.module._require_loopback_http("http://127.0.0.1:3000/", "grafana"),
            "http://127.0.0.1:3000",
        )
        self.assertEqual(
            self.module._require_loopback_http("http://localhost:3000", "grafana"),
            "http://localhost:3000",
        )


if __name__ == "__main__":
    unittest.main()
