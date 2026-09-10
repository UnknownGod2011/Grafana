from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "runtime" / "grafana" / "dashboards" / "stageguard-runtime.json"
DASHBOARD_PROVIDER = ROOT / "runtime" / "grafana" / "provisioning" / "dashboards" / "stageguard.yml"
ALERTING = ROOT / "runtime" / "grafana" / "provisioning" / "alerting" / "stageguard-watchdog.yml"
COMPOSE = ROOT / "docker-compose.yml"


class GrafanaRuntimeObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        cls.provider = DASHBOARD_PROVIDER.read_text(encoding="utf-8")
        cls.alerting = ALERTING.read_text(encoding="utf-8")
        cls.compose = COMPOSE.read_text(encoding="utf-8")

    def test_dashboard_is_stable_and_queries_all_watchdog_metrics(self) -> None:
        self.assertEqual(self.dashboard["uid"], "stageguard-runtime-safety")
        self.assertEqual(self.dashboard["title"], "StageGuard Runtime Safety")
        expressions = {
            target["expr"]
            for panel in self.dashboard["panels"]
            for target in panel.get("targets", [])
        }
        self.assertIn("stageguard_remediation_execution_active", expressions)
        self.assertIn("stageguard_remediation_execution_deadline_exceeded", expressions)
        self.assertIn("stageguard_remediation_execution_age_seconds", expressions)
        self.assertIn("stageguard_remediation_execution_max_seconds", expressions)
        self.assertIn(
            "stageguard_remediation_execution_max_seconds - stageguard_remediation_execution_age_seconds",
            expressions,
        )

    def test_dashboard_uses_the_provisioned_read_only_prometheus_source(self) -> None:
        for panel in self.dashboard["panels"]:
            datasource = panel.get("datasource", {})
            self.assertEqual(datasource.get("uid"), "stageguard-prometheus")
        self.assertIn("allowUiUpdates: false", self.provider)
        self.assertIn("disableDeletion: true", self.provider)
        self.assertIn("updateIntervalSeconds: 30", self.provider)
        self.assertIn("path: /var/lib/grafana/dashboards", self.provider)

    def test_compose_mounts_dashboard_and_provisioning_trees_read_only(self) -> None:
        self.assertIn(
            "./runtime/grafana/provisioning:/etc/grafana/provisioning:ro",
            self.compose,
        )
        self.assertIn(
            "./runtime/grafana/dashboards:/var/lib/grafana/dashboards:ro",
            self.compose,
        )

    def test_deadline_alert_is_bound_to_dashboard_panel_and_metric(self) -> None:
        self.assertIn("uid: stageguard-remediation-deadline", self.alerting)
        self.assertIn(
            "expr: max(stageguard_remediation_execution_deadline_exceeded)",
            self.alerting,
        )
        self.assertIn("datasourceUid: stageguard-prometheus", self.alerting)
        self.assertIn("dashboardUid: stageguard-runtime-safety", self.alerting)
        self.assertIn("panelId: 2", self.alerting)
        self.assertIn("for: 10s", self.alerting)
        self.assertIn("severity: critical", self.alerting)

    def test_alert_does_not_conflate_missing_data_with_deadline_exceeded(self) -> None:
        self.assertIn("noDataState: NoData", self.alerting)
        self.assertIn("execErrState: Error", self.alerting)
        self.assertNotIn("noDataState: Alerting", self.alerting)

    def test_provisioning_does_not_embed_notification_destinations_or_secrets(self) -> None:
        lowered = self.alerting.lower()
        for forbidden in (
            "contactpoints:",
            "policies:",
            "authorization:",
            "bearer ",
            "webhook",
            "password",
            "token:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
