import unittest
from unittest.mock import patch

from readiness import EvidencePlaneReadinessProbe


class FakeClient:
    def __init__(self, datasource_uid="uid", error=None):
        self.datasource_uid = datasource_uid
        self.error = error
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        if self.error is not None:
            raise self.error


class ReadinessProbeTests(unittest.TestCase):
    def probe(self, *, metric_error=None, log_error=None, activation=object(), log_activation=object()):
        return EvidencePlaneReadinessProbe(
            object(),
            activation,
            log_activation,
            FakeClient("prom-uid", metric_error),
            None if log_activation is None else FakeClient("loki-uid", log_error),
            now_unix=lambda: 123,
        )

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_ready_requires_both_fresh_pins_and_both_read_only_handshakes(self, verify_metric, verify_log):
        probe = self.probe()
        result = probe.check()
        self.assertTrue(result.ready)
        self.assertEqual(
            {
                "metric_activation": "ok",
                "loki_activation": "ok",
                "prometheus_mcp": "ok",
                "loki_mcp": "ok",
            },
            result.checks,
        )
        verify_metric.assert_called_once()
        verify_log.assert_called_once()

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record", side_effect=ValueError("expired secret endpoint"))
    def test_expired_metric_activation_fails_without_error_detail(self, _verify_metric, _verify_log):
        result = self.probe().check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["metric_activation"])
        self.assertNotIn("expired", str(result))
        self.assertNotIn("secret", str(result))

    @patch("readiness.verify_log_activation_record", side_effect=ValueError("datasource drift https://private"))
    @patch("readiness.verify_activation_record")
    def test_loki_datasource_drift_fails_closed_without_provider_detail(self, _verify_metric, _verify_log):
        result = self.probe().check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["loki_activation"])
        self.assertNotIn("private", str(result))

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_missing_mcp_binary_or_grafana_auth_failure_fails_handshake(self, _verify_metric, _verify_log):
        result = self.probe(metric_error=FileNotFoundError("/secret/mcp"), log_error=RuntimeError("401 token=bad")).check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["prometheus_mcp"])
        self.assertEqual("failed", result["checks"]["loki_mcp"])
        self.assertNotIn("token", str(result))
        self.assertNotIn("secret", str(result))

    @patch("readiness.verify_activation_record")
    def test_missing_loki_activation_is_not_ready(self, _verify_metric):
        result = self.probe(log_activation=None).check()
        self.assertFalse(result.ready)
        self.assertEqual("missing", result.checks["loki_activation"])
        self.assertEqual("missing", result.checks["loki_mcp"])


if __name__ == "__main__":
    unittest.main()
