import unittest
from unittest.mock import patch

from readiness import EvidencePlaneReadinessProbe


class FakeTransport:
    def __init__(self):
        self.requests = []

    def request(self, method, params):
        self.requests.append((method, params))
        return {"isError": False, "content": []}


class FakeClient:
    def __init__(self, datasource_uid):
        self.datasource_uid = datasource_uid
        self.connect_calls = 0
        self.transport = FakeTransport()
        self._client = None

    def connect(self):
        self.connect_calls += 1
        self._client = self.transport


class ReadinessLocalShortCircuitTests(unittest.TestCase):
    def _probe(self, activation=object(), log_activation=object(), logs=True):
        metric = FakeClient("prom-uid")
        log_client = FakeClient("loki-uid") if logs else None
        probe = EvidencePlaneReadinessProbe(
            object(),
            activation,
            log_activation,
            metric,
            log_client,
            now_unix=lambda: 123,
            monotonic=lambda: 10.0,
            external_probe_ttl_seconds=15,
            failure_backoff_seconds=5,
            stale_grace_seconds=30,
        )
        return probe, metric, log_client

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record", side_effect=ValueError("expired"))
    def test_invalid_metric_activation_blocks_all_external_mcp(self, _verify_metric, _verify_log):
        probe, metric, logs = self._probe()

        result = probe.check()

        self.assertFalse(result.ready)
        self.assertEqual("failed", result.checks["metric_activation"])
        self.assertEqual("blocked", result.checks["prometheus_mcp"])
        self.assertEqual("blocked", result.checks["loki_mcp"])
        self.assertEqual(0, metric.connect_calls)
        self.assertEqual(0, logs.connect_calls)
        self.assertEqual([], metric.transport.requests)
        self.assertEqual([], logs.transport.requests)

    @patch("readiness.verify_log_activation_record", side_effect=ValueError("drift"))
    @patch("readiness.verify_activation_record")
    def test_invalid_log_activation_blocks_all_external_mcp(self, _verify_metric, _verify_log):
        probe, metric, logs = self._probe()

        result = probe.check()

        self.assertFalse(result.ready)
        self.assertEqual("ok", result.checks["metric_activation"])
        self.assertEqual("failed", result.checks["loki_activation"])
        self.assertEqual("blocked", result.checks["prometheus_mcp"])
        self.assertEqual("blocked", result.checks["loki_mcp"])
        self.assertEqual(0, metric.connect_calls)
        self.assertEqual(0, logs.connect_calls)

    @patch("readiness.verify_activation_record")
    def test_missing_loki_dependency_does_not_probe_prometheus(self, _verify_metric):
        probe, metric, _ = self._probe(log_activation=None, logs=False)

        result = probe.check()

        self.assertFalse(result.ready)
        self.assertEqual("ok", result.checks["metric_activation"])
        self.assertEqual("missing", result.checks["loki_activation"])
        self.assertEqual("blocked", result.checks["prometheus_mcp"])
        self.assertEqual("missing", result.checks["loki_mcp"])
        self.assertEqual(0, metric.connect_calls)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_valid_local_trust_still_probes_both_planes(self, _verify_metric, _verify_log):
        probe, metric, logs = self._probe()

        result = probe.check()

        self.assertTrue(result.ready)
        self.assertEqual("ok", result.checks["prometheus_mcp"])
        self.assertEqual("ok", result.checks["loki_mcp"])
        self.assertEqual(1, metric.connect_calls)
        self.assertEqual(1, logs.connect_calls)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record", side_effect=ValueError("expired"))
    def test_blocked_checks_do_not_increment_external_attempt_metrics(self, _verify_metric, _verify_log):
        probe, _, _ = self._probe()
        probe.check()

        metrics = probe.prometheus_metrics()

        self.assertIn('stageguard_readiness_external_probe_attempts_total{plane="prometheus"} 0', metrics)
        self.assertIn('stageguard_readiness_external_probe_attempts_total{plane="loki"} 0', metrics)
        self.assertIn("stageguard_readiness_ready 0", metrics)


if __name__ == "__main__":
    unittest.main()
