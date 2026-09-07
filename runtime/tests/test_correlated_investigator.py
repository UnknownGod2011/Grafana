import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from investigator import QUERIES, investigate_with_log_corroboration
from log_evidence import LogQueryResult, LogRecord


class Metrics:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def instant(self, promql):
        self.calls.append(promql)
        for name, (query, _) in QUERIES.items():
            if query == promql:
                return self.values[name]
        raise AssertionError(promql)


class Logs:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def range(self, logql, *, start, end, limit):
        self.calls.append((logql, start, end, limit))
        return self.result


def metric_fault():
    return {
        "symptom": 8.0,
        "causal": 18.0,
        "contradiction_cpu": 41.0,
        "contradiction_gpu": 37.0,
        "healthy_peer_loss": 0.2,
        "healthy_peer_drop": 0.0,
    }


def alarm_result(*, truncated=False):
    return LogQueryResult((LogRecord(
        timestamp="1760000000000000000",
        line='{"event":"packet_loss_alarm"}',
        labels={"production_id": "broadcast-alpha", "uplink": "uplink-b"},
        structured_metadata={},
        parsed={"event": "packet_loss_alarm"},
    ),), truncated, "now-5m", "now")


class CorrelatedInvestigatorTests(unittest.TestCase):
    def test_metric_diagnosis_requires_log_corroboration(self):
        metrics = Metrics(metric_fault())
        logs = Logs(alarm_result())
        report = investigate_with_log_corroboration(metrics, logs)
        self.assertEqual("diagnosed", report.status)
        self.assertEqual("corroborated", report.log_corroboration.status)
        self.assertEqual(6, len(metrics.calls))
        self.assertEqual(1, len(logs.calls))

    def test_missing_log_converts_diagnosis_to_abstention(self):
        logs = Logs(LogQueryResult((), False, "now-5m", "now"))
        report = investigate_with_log_corroboration(Metrics(metric_fault()), logs)
        self.assertEqual("abstain", report.status)
        self.assertIn("causal_log", report.missing_evidence)
        self.assertEqual("missing", report.log_corroboration.status)

    def test_truncated_log_converts_diagnosis_to_abstention(self):
        report = investigate_with_log_corroboration(Metrics(metric_fault()), Logs(alarm_result(truncated=True)))
        self.assertEqual("abstain", report.status)
        self.assertEqual("ambiguous", report.log_corroboration.status)

    def test_loki_not_queried_when_metrics_do_not_diagnose(self):
        values = metric_fault()
        values["causal"] = 0.1
        logs = Logs(alarm_result())
        report = investigate_with_log_corroboration(Metrics(values), logs)
        self.assertEqual("abstain", report.status)
        self.assertEqual([], logs.calls)


if __name__ == "__main__":
    unittest.main()
