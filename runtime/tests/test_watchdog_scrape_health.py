from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALERTS = ROOT / "runtime" / "grafana" / "provisioning" / "alerting" / "stageguard-watchdog.yml"
DASHBOARD = ROOT / "runtime" / "grafana" / "dashboards" / "stageguard-runtime.json"
PROMETHEUS = ROOT / "runtime" / "prometheus.yml"


class WatchdogScrapeHealthContractTests(unittest.TestCase):
    def test_prometheus_job_name_is_stable(self) -> None:
        text = PROMETHEUS.read_text(encoding="utf-8")
        self.assertIn("job_name: stageguard-runtime-watchdog", text)
        self.assertIn('targets: ["watchdog-fixture:9111"]', text)

    def test_scrape_failure_alert_is_separate_from_deadline_and_staleness(self) -> None:
        text = ALERTS.read_text(encoding="utf-8")
        self.assertIn("uid: stageguard-runtime-scrape-down", text)
        self.assertIn("title: StageGuard runtime watchdog scrape failing", text)
        self.assertIn('expr: max(up{job="stageguard-runtime-watchdog"})', text)
        self.assertIn("params: [0.5]\n                    type: lt", text)
        self.assertIn("noDataState: Alerting", text)
        self.assertIn("for: 20s", text)
        self.assertIn("panelId: 6", text)
        self.assertIn("uid: stageguard-remediation-deadline", text)
        self.assertIn("uid: stageguard-runtime-telemetry-stale", text)
        self.assertIn("does not itself mean a remediation deadline was exceeded", text)

    def test_dashboard_exposes_scrape_transport_health(self) -> None:
        dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        panels = {panel["id"]: panel for panel in dashboard["panels"]}
        panel = panels[6]
        self.assertEqual(panel["title"], "Watchdog scrape health")
        self.assertEqual(
            panel["targets"][0]["expr"],
            'min(up{job="stageguard-runtime-watchdog"})',
        )
        self.assertIn("does not itself prove a remediation deadline breach", panel["description"])
        self.assertGreaterEqual(dashboard["version"], 3)

    def test_scrape_alert_does_not_reuse_deadline_metric(self) -> None:
        text = ALERTS.read_text(encoding="utf-8")
        scrape_rule = text.split("uid: stageguard-runtime-scrape-down", 1)[1]
        self.assertNotIn("stageguard_remediation_execution_deadline_exceeded", scrape_rule)
        self.assertIn('up{job="stageguard-runtime-watchdog"}', scrape_rule)


if __name__ == "__main__":
    unittest.main()
