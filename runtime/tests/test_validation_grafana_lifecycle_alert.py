from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ALERT = ROOT / "runtime" / "grafana" / "provisioning" / "alerting" / "stageguard-lifecycle-safety.yml"


class GrafanaLifecycleSafetyAlertTests(unittest.TestCase):
    def test_alert_tracks_composite_fail_closed_metric(self):
        text = ALERT.read_text(encoding="utf-8")
        self.assertIn("uid: stageguard-lifecycle-unsafe", text)
        self.assertIn('expr: max(stageguard_lifecycle_safety_state{state!="ok"})', text)
        self.assertIn("noDataState: Alerting", text)
        self.assertIn("execErrState: Error", text)
        self.assertIn("severity: critical", text)
        self.assertIn("safety_boundary: lifecycle", text)

    def test_alert_does_not_encode_mutation_or_provider_actions(self):
        text = ALERT.read_text(encoding="utf-8").lower()
        for forbidden in ("/v1/execute", "/v1/approve", "recover_uplink", "authorization:", "bearer "):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
