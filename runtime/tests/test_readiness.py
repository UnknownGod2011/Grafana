import math
import threading
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


class Clock:
    def __init__(self, value=0.0):
        self.value = float(value)

    def __call__(self):
        return self.value


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
        clock=None,
    ):
        metric = FakeClient("prom-uid", metric_connect_error, metric_lookup_error)
        logs = None if log_activation is None else FakeClient("loki-uid", log_connect_error, log_lookup_error)
        clock = clock or Clock()
        probe = EvidencePlaneReadinessProbe(
            object(),
            activation,
            log_activation,
            metric,
            logs,
            now_unix=lambda: 123,
            monotonic=clock,
            external_probe_ttl_seconds=15,
            failure_backoff_seconds=5,
            stale_grace_seconds=30,
        )
        return probe, metric, logs, clock

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_ready_requires_fresh_pins_and_bounded_datasource_access(self, verify_metric, verify_log):
        probe, metric, logs, _ = self.probe()
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
    @patch("readiness.verify_activation_record")
    def test_cache_reuses_external_success_but_rechecks_activation_every_request(self, verify_metric, verify_log):
        probe, metric, logs, clock = self.probe()
        self.assertTrue(probe.check().ready)
        clock.value = 10
        self.assertTrue(probe.check().ready)
        self.assertEqual(1, metric.connect_calls)
        self.assertEqual(1, logs.connect_calls)
        self.assertEqual(2, verify_metric.call_count)
        self.assertEqual(2, verify_log.call_count)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_transient_refresh_failure_uses_only_bounded_stale_grace(self, _verify_metric, _verify_log):
        probe, metric, logs, clock = self.probe()
        self.assertTrue(probe.check().ready)
        metric.transport.error = RuntimeError("401 token=secret")
        logs.transport.error = RuntimeError("https://private")

        clock.value = 16
        stale = probe.check()
        self.assertTrue(stale.ready)
        self.assertEqual("stale", stale.checks["prometheus_mcp"])
        self.assertEqual("stale", stale.checks["loki_mcp"])
        self.assertNotIn("secret", str(stale.to_dict()))
        self.assertNotIn("private", str(stale.to_dict()))

        clock.value = 31
        expired = probe.check()
        self.assertFalse(expired.ready)
        self.assertEqual("failed", expired.checks["prometheus_mcp"])
        self.assertEqual("failed", expired.checks["loki_mcp"])

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_local_activation_failure_short_circuits_cached_external_success(self, verify_metric, _verify_log):
        probe, metric, logs, clock = self.probe()
        self.assertTrue(probe.check().ready)
        self.assertEqual(1, metric.connect_calls)
        self.assertEqual(1, logs.connect_calls)

        verify_metric.side_effect = ValueError("expired")
        clock.value = 5
        result = probe.check()

        self.assertFalse(result.ready)
        self.assertEqual("failed", result.checks["metric_activation"])
        self.assertEqual("blocked", result.checks["prometheus_mcp"])
        self.assertEqual("blocked", result.checks["loki_mcp"])
        self.assertEqual(1, metric.connect_calls)
        self.assertEqual(1, logs.connect_calls)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_concurrent_health_polling_single_flights_external_probes(self, _verify_metric, _verify_log):
        probe, metric, logs, _ = self.probe()
        results = []

        def run():
            results.append(probe.check().ready)

        threads = [threading.Thread(target=run) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(results))
        self.assertEqual(1, metric.connect_calls)
        self.assertEqual(1, logs.connect_calls)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record", side_effect=ValueError("expired secret endpoint"))
    def test_expired_metric_activation_fails_without_error_detail(self, _verify_metric, _verify_log):
        probe, _, _, _ = self.probe()
        result = probe.check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["metric_activation"])
        self.assertEqual("blocked", result["checks"]["prometheus_mcp"])
        self.assertNotIn("expired", str(result))
        self.assertNotIn("secret", str(result))

    @patch("readiness.verify_log_activation_record", side_effect=ValueError("datasource drift https://private"))
    @patch("readiness.verify_activation_record")
    def test_loki_datasource_drift_fails_closed_without_provider_detail(self, _verify_metric, _verify_log):
        probe, _, _, _ = self.probe()
        result = probe.check().to_dict()
        self.assertFalse(result["ready"])
        self.assertEqual("failed", result["checks"]["loki_activation"])
        self.assertEqual("blocked", result["checks"]["loki_mcp"])
        self.assertNotIn("private", str(result))

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_missing_mcp_binary_or_grafana_auth_failure_fails_handshake(self, _verify_metric, _verify_log):
        probe, _, _, _ = self.probe(
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
        probe, metric, _, _ = self.probe(log_activation=None)
        result = probe.check()
        self.assertFalse(result.ready)
        self.assertEqual("missing", result.checks["loki_activation"])
        self.assertEqual("blocked", result.checks["prometheus_mcp"])
        self.assertEqual("missing", result.checks["loki_mcp"])
        self.assertEqual(0, metric.connect_calls)

    @patch("readiness.verify_log_activation_record")
    @patch("readiness.verify_activation_record")
    def test_metrics_are_bounded_and_contain_no_provider_details(self, _verify_metric, _verify_log):
        probe, metric, _, clock = self.probe()
        probe.check()
        metric.transport.error = RuntimeError("token=SECRET https://private")
        clock.value = 16
        probe.check()
        text = probe.prometheus_metrics()
        self.assertIn("stageguard_readiness_ready 1", text)
        self.assertIn('stageguard_readiness_external_probe_attempts_total{plane="prometheus"} 2', text)
        self.assertIn('class="lookup"', text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("private", text)
        self.assertNotIn("prom-uid", text)

    def test_invalid_cache_policy_is_rejected(self):
        metric = FakeClient()
        with self.assertRaises(ValueError):
            EvidencePlaneReadinessProbe(object(), object(), object(), metric, metric, external_probe_ttl_seconds=0)
        with self.assertRaises(ValueError):
            EvidencePlaneReadinessProbe(
                object(), object(), object(), metric, metric,
                external_probe_ttl_seconds=15, stale_grace_seconds=10,
            )

    def test_non_finite_boolean_and_unbounded_cache_policy_is_rejected(self):
        metric = FakeClient()
        invalid = (True, False, math.nan, math.inf, -math.inf, "15", None)
        for value in invalid:
            with self.subTest(field="external_probe_ttl_seconds", value=value):
                with self.assertRaises(ValueError):
                    EvidencePlaneReadinessProbe(
                        object(), object(), object(), metric, metric,
                        external_probe_ttl_seconds=value,
                    )
            with self.subTest(field="failure_backoff_seconds", value=value):
                with self.assertRaises(ValueError):
                    EvidencePlaneReadinessProbe(
                        object(), object(), object(), metric, metric,
                        failure_backoff_seconds=value,
                    )
            with self.subTest(field="stale_grace_seconds", value=value):
                with self.assertRaises(ValueError):
                    EvidencePlaneReadinessProbe(
                        object(), object(), object(), metric, metric,
                        stale_grace_seconds=value,
                    )

        with self.assertRaises(ValueError):
            EvidencePlaneReadinessProbe(
                object(), object(), object(), metric, metric,
                external_probe_ttl_seconds=300.01,
            )
        with self.assertRaises(ValueError):
            EvidencePlaneReadinessProbe(
                object(), object(), object(), metric, metric,
                failure_backoff_seconds=300.01,
            )
        with self.assertRaises(ValueError):
            EvidencePlaneReadinessProbe(
                object(), object(), object(), metric, metric,
                stale_grace_seconds=900.01,
            )

    def test_cache_policy_accepts_safety_envelope_boundaries(self):
        metric = FakeClient()
        probe = EvidencePlaneReadinessProbe(
            object(), object(), object(), metric, metric,
            external_probe_ttl_seconds=300,
            failure_backoff_seconds=300,
            stale_grace_seconds=900,
        )
        self.assertEqual(300.0, probe._ttl)
        self.assertEqual(300.0, probe._failure_backoff)
        self.assertEqual(900.0, probe._stale_grace)


if __name__ == "__main__":
    unittest.main()
