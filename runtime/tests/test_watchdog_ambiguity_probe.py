from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "runtime" / "watchdog_observability_acceptance.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("watchdog_observability_acceptance_probe", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load watchdog acceptance module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WatchdogAmbiguityProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_probe_manufactures_two_query_local_label_distinct_series(self) -> None:
        query = self.module.AMBIGUITY_PROBE_QUERY
        self.assertEqual(query.count(self.module.METRIC), 2)
        self.assertEqual(query.count("label_replace("), 2)
        self.assertIn('"stageguard_acceptance_probe", "left"', query)
        self.assertIn('"stageguard_acceptance_probe", "right"', query)
        self.assertIn(" or ", query)

    def test_probe_accepts_only_explicit_multi_series_rejection(self) -> None:
        expected = ValueError("Prometheus safety query must return exactly one series")
        with mock.patch.object(self.module, "prometheus_query_value", side_effect=expected) as query:
            self.assertTrue(self.module.prometheus_ambiguity_probe_rejected("http://127.0.0.1:9090"))
        query.assert_called_once_with("http://127.0.0.1:9090", self.module.AMBIGUITY_PROBE_QUERY)

    def test_probe_fails_if_ambiguous_query_is_accidentally_accepted(self) -> None:
        with mock.patch.object(self.module, "prometheus_query_value", return_value=0.0):
            self.assertFalse(self.module.prometheus_ambiguity_probe_rejected("http://127.0.0.1:9090"))

    def test_probe_does_not_misclassify_unrelated_parser_failure_as_success(self) -> None:
        with mock.patch.object(
            self.module,
            "prometheus_query_value",
            side_effect=ValueError("Prometheus query sample must be finite"),
        ):
            self.assertFalse(self.module.prometheus_ambiguity_probe_rejected("http://127.0.0.1:9090"))


if __name__ == "__main__":
    unittest.main()
