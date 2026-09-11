from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "runtime" / "watchdog_observability_acceptance.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("watchdog_observability_acceptance_scrape", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load watchdog acceptance module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchdogScrapeLifecycleAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_scrape_query_matches_provisioned_job_contract(self) -> None:
        self.assertEqual(self.module.SCRAPE_JOB, "stageguard-runtime-watchdog")
        self.assertEqual(
            self.module.SCRAPE_QUERY,
            'max(up{job="stageguard-runtime-watchdog"})',
        )

    def test_prometheus_scrape_up_uses_exact_target_health_query(self) -> None:
        with mock.patch.object(self.module, "prometheus_query_value", return_value=1.0) as query:
            self.assertEqual(self.module.prometheus_scrape_up("http://127.0.0.1:9090"), 1.0)
        query.assert_called_once_with(
            "http://127.0.0.1:9090",
            self.module.SCRAPE_QUERY,
        )

    def test_scrape_alert_matches_its_title(self) -> None:
        payload = [
            {
                "labels": {"alertname": self.module.SCRAPE_ALERT_TITLE},
                "annotations": {},
            }
        ]
        with mock.patch.object(self.module, "grafana_active_alerts", return_value=payload):
            self.assertTrue(
                self.module.scrape_alert_active(
                    "http://127.0.0.1:3000",
                    ("admin", "local"),
                )
            )

    def test_scrape_alert_matches_its_summary(self) -> None:
        payload = [
            {
                "labels": {},
                "annotations": {"summary": self.module.SCRAPE_ALERT_SUMMARY},
            }
        ]
        with mock.patch.object(self.module, "grafana_active_alerts", return_value=payload):
            self.assertTrue(
                self.module.scrape_alert_active(
                    "http://127.0.0.1:3000",
                    ("admin", "local"),
                )
            )

    def test_stale_or_deadline_alert_does_not_match_scrape_identity(self) -> None:
        for title in (self.module.STALE_ALERT_TITLE, self.module.DEADLINE_ALERT_TITLE):
            with self.subTest(title=title):
                payload = [{"labels": {"alertname": title}, "annotations": {}}]
                with mock.patch.object(self.module, "grafana_active_alerts", return_value=payload):
                    self.assertFalse(
                        self.module.scrape_alert_active(
                            "http://127.0.0.1:3000",
                            ("admin", "local"),
                        )
                    )

    def test_stale_guard_fails_when_stale_warning_is_active(self) -> None:
        with mock.patch.object(self.module, "stale_alert_active", return_value=True):
            self.assertFalse(
                self.module._fail_if_stale_alert_active(
                    "http://127.0.0.1:3000",
                    ("admin", "local"),
                    "during ordering check",
                )
            )

    def test_stale_guard_passes_when_stale_warning_is_inactive(self) -> None:
        with mock.patch.object(self.module, "stale_alert_active", return_value=False):
            self.assertTrue(
                self.module._fail_if_stale_alert_active(
                    "http://127.0.0.1:3000",
                    ("admin", "local"),
                    "during ordering check",
                )
            )


if __name__ == "__main__":
    unittest.main()
