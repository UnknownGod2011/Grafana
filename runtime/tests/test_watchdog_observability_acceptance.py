from __future__ import annotations

import importlib.util
import math
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

    def _active(self, payload, *, title=None, summary=None) -> bool:
        return self.module.grafana_alert_active_from_payload(
            payload,
            title=title or self.module.DEADLINE_ALERT_TITLE,
            summary=summary or self.module.DEADLINE_ALERT_SUMMARY,
        )

    def _query_payload(self, results):
        return {
            "status": "success",
            "data": {"resultType": "vector", "result": results},
        }

    def test_expected_runtime_versions_match_compose_contract(self) -> None:
        self.assertEqual(self.module.EXPECTED_PROMETHEUS_VERSION, "3.13.3")
        self.assertEqual(self.module.EXPECTED_GRAFANA_VERSION, "13.2.1")

    def test_prometheus_buildinfo_version_parser_is_strict(self) -> None:
        self.assertEqual(
            self.module.prometheus_runtime_version_from_payload(
                {"status": "success", "data": {"version": "3.13.3"}}
            ),
            "3.13.3",
        )
        invalid = (
            None,
            [],
            {},
            {"status": "error", "data": {"version": "3.13.3"}},
            {"status": "success", "data": None},
            {"status": "success", "data": {}},
            {"status": "success", "data": {"version": ""}},
            {"status": "success", "data": {"version": 3133}},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.module.prometheus_runtime_version_from_payload(payload)

    def test_grafana_health_version_parser_is_strict(self) -> None:
        self.assertEqual(
            self.module.grafana_runtime_version_from_payload(
                {"database": "ok", "version": "13.2.1"}
            ),
            "13.2.1",
        )
        invalid = (
            None,
            [],
            {},
            {"version": ""},
            {"version": 1321},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.module.grafana_runtime_version_from_payload(payload)

    def test_prometheus_query_parser_accepts_exactly_one_finite_sample(self) -> None:
        payload = self._query_payload(
            [{"metric": {"job": "watchdog-fixture"}, "value": [1720000000.0, "1"]}]
        )
        self.assertEqual(self.module.prometheus_query_value_from_payload(payload), 1.0)

    def test_prometheus_query_parser_returns_none_for_empty_vector(self) -> None:
        self.assertIsNone(self.module.prometheus_query_value_from_payload(self._query_payload([])))

    def test_prometheus_query_parser_rejects_ambiguous_multiple_series(self) -> None:
        payload = self._query_payload(
            [
                {"metric": {"instance": "a"}, "value": [1720000000.0, "0"]},
                {"metric": {"instance": "b"}, "value": [1720000000.0, "1"]},
            ]
        )
        with self.assertRaisesRegex(ValueError, "exactly one series"):
            self.module.prometheus_query_value_from_payload(payload)

    def test_prometheus_query_parser_rejects_non_finite_samples(self) -> None:
        for value in ("NaN", "Inf", "+Inf", "-Inf"):
            with self.subTest(value=value):
                payload = self._query_payload([{"metric": {}, "value": [1720000000.0, value]}])
                with self.assertRaisesRegex(ValueError, "finite"):
                    self.module.prometheus_query_value_from_payload(payload)

    def test_prometheus_query_parser_rejects_malformed_shapes(self) -> None:
        invalid = (
            None,
            {},
            {"status": "error", "data": {"resultType": "vector", "result": []}},
            {"status": "success", "data": None},
            {"status": "success", "data": {"resultType": "scalar", "result": [1, "0"]}},
            {"status": "success", "data": {"resultType": "vector", "result": {}}},
            self._query_payload([None]),
            self._query_payload([{"metric": {}, "value": [1720000000.0]}]),
            self._query_payload([{"metric": {}, "value": [1720000000.0, "not-a-number"]}]),
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.module.prometheus_query_value_from_payload(payload)

    def test_deadline_alert_title_match_is_active(self) -> None:
        payload = [{"labels": {"alertname": self.module.DEADLINE_ALERT_TITLE}, "annotations": {}}]
        self.assertTrue(self._active(payload))

    def test_deadline_summary_match_is_active(self) -> None:
        payload = [{"labels": {}, "annotations": {"summary": self.module.DEADLINE_ALERT_SUMMARY}}]
        self.assertTrue(self._active(payload))

    def test_stale_alert_matches_only_stale_identity(self) -> None:
        payload = [{"labels": {"alertname": self.module.STALE_ALERT_TITLE}, "annotations": {}}]
        self.assertTrue(
            self._active(
                payload,
                title=self.module.STALE_ALERT_TITLE,
                summary=self.module.STALE_ALERT_SUMMARY,
            )
        )
        self.assertFalse(self._active(payload))

    def test_unrelated_active_alert_does_not_block_resolution(self) -> None:
        payload = [{"labels": {"alertname": "Different alert"}, "annotations": {"summary": "Different summary"}}]
        self.assertFalse(self._active(payload))

    def test_empty_active_alert_list_is_resolved(self) -> None:
        self.assertFalse(self._active([]))

    def test_unexpected_root_shape_fails_closed(self) -> None:
        for payload in ({}, None, "[]", 1):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self._active(payload)

    def test_malformed_alert_entry_fails_closed(self) -> None:
        for payload in ([None], [{"labels": [], "annotations": {}}], [{"labels": {}, "annotations": []}]):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self._active(payload)

    def test_freshness_query_matches_provisioned_contract(self) -> None:
        self.assertIn(
            "timestamp(stageguard_remediation_execution_deadline_exceeded)",
            self.module.FRESHNESS_QUERY,
        )
        self.assertIn(
            "absent(stageguard_remediation_execution_deadline_exceeded)",
            self.module.FRESHNESS_QUERY,
        )
        self.assertEqual(self.module.FRESHNESS_THRESHOLD_SECONDS, 45.0)

    def test_set_telemetry_rejects_non_boolean_mode_before_http(self) -> None:
        for value in (0, 1, "offline", None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.module.set_telemetry("http://127.0.0.1:1", value)

    def test_timeout_validation_requires_positive_finite_values(self) -> None:
        self.assertEqual(self.module._require_positive_finite(1, "timeout"), 1.0)
        self.assertEqual(self.module._require_positive_finite(0.25, "timeout"), 0.25)
        for value in (0, -1, True, math.inf, -math.inf, math.nan, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.module._require_positive_finite(value, "timeout")

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
