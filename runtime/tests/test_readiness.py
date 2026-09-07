import unittest
from unittest.mock import patch

from readiness import EvidencePlaneReadinessProbe


class FakeTransport:
    def __init__(self, error=None, is_error=False):
        self.error = error
        self.is_error = is_error
        self.requests = []

    def request(self, method, params):
        self.requests.append((method, params))
        if self.error is not None:
            raise self.error
        return {"isError": self.is_error, "content": []}


class FakeClient:
    def __init__(self, datasource_uid="uid", connect_error=None, lookup_error=None, lookup_is_error=False):
        self.datasource_uid = datasource_uid
        self.connect_error = connect_error
        self.connect_calls = 0
        self._client = None
        self.transport = FakeTransport(lookup_error, lookup_is_error)

    def connect(self):
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error
        self._client = self.transport


class ReadinessProbeTests(unittest.TestCase):
    def probe(
        self,
        *,
        metric_connect_error=None,
        log_connect_error=None,
        metric_lookup_error=None,
        log_lookup_error=None,
        activation=object(),
        log_activation=object(),
    ):
        metric = FakeClient("prom-uid", metric_connect_error, metric_lookup_error)
        logs = None if log_activation is None else FakeClient("loki-uid", log_connect_error, log_lookup_error)
        probe = EvidencePlaneReadinessProbe(
            object(), activation, log_activation, metric, logs, now_unix=lambda: 123
        )
        return probe, metric, logs

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_ready_requires_fresh_pins_and_bounded_datasource_access(self, verify_metric, verify_log):
        probe, metric, logs = self.probe()
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
        self.assertEqual(
            [("tools/call", {"name": "get_datasource", "arguments": {"uid": "prom-uid"}})],
            metric.transport.requests,
        )
        self.assertEqual(
            [("tools/call", {"name": "get_datasource", "arguments": {"uid": "loki-uid"}})],
            logs.transport.requests,
        )

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record", side_effect=ValueError("expired secret endpoint"))
    def test_expired_metric_activation_fails_without_error_detail(self, _verify_metric, _verify_log):
        probe, _, _ = self.probe()
        result = probe.check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["metric_activation"])
        self.assertNotIn("expired", str(result))
        self.assertNotIn("secret", str(result))

    @patch("readiness.verify_log_activation_record", side_effect=ValueError("datasource drift https://private"))
    @patch("readiness.verify_activation_record")
    def test_loki_datasource_drift_fails_closed_without_provider_detail(self, _verify_metric, _verify_log):
        probe, _, _ = self.probe()
        result = probe.check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["loki_activation"])
        self.assertNotIn("private", str(result))

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_missing_mcp_binary_or_grafana_auth_failure_fails_handshake(self, _verify_metric, _verify_log):
        probe, _, _ = self.probe(
            metric_connect_error=FileNotFoundError("/secret/mcp"),
            log_lookup_error=RuntimeError("401 token=bad"),
        )
        result = probe.check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["prometheus_mcp"])
        self.assertEqual("failed", result["checks"]["loki_mcp"])
        self.assertNotIn("token", str(result))
        self.assertNotIn("secret", str(result))

    @patch("readiness.verify_activation_record")
    def test_missing_loki_activation_is_not_ready(self, _verify_metric):
        probe, _, _ = self.probe(log_activation=None)
        result = probe.check()
        self.assertFalse(result.ready)
        self.assertEqual("missing", result.checks["loki_activation"])
        self.assertEqual("missing", result.checks["loki_mcp"])


if __name__ == "__main__":
    unittest.main()
