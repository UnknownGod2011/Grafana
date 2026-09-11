import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from evidence_errors import EvidenceUnavailable
from investigator import QUERIES, investigate


class FakeClient:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def instant(self, promql):
        self.calls.append(promql)
        for name, (query, _) in QUERIES.items():
            if query == promql:
                return self.values.get(name)
        raise AssertionError(f"unexpected query: {promql}")


class FailingClient(FakeClient):
    def __init__(self, values, failed_slot, exc):
        super().__init__(values)
        self.failed_query = QUERIES[failed_slot][0]
        self.exc = exc

    def instant(self, promql):
        self.calls.append(promql)
        if promql == self.failed_query:
            raise self.exc
        for name, (query, _) in QUERIES.items():
            if query == promql:
                return self.values.get(name)
        raise AssertionError(f"unexpected query: {promql}")


def fault_values():
    return {
        "symptom": 8.0,
        "causal": 18.0,
        "contradiction_cpu": 41.0,
        "contradiction_gpu": 37.0,
        "healthy_peer_loss": 0.2,
        "healthy_peer_drop": 0.0,
    }


class InvestigatorTests(unittest.TestCase):
    def test_diagnoses_only_when_all_four_evidence_classes_support_hypothesis(self):
        report = investigate(FakeClient(fault_values()))
        self.assertEqual("diagnosed", report.status)
        self.assertEqual("uplink-b packet loss", report.hypothesis)
        self.assertGreaterEqual(report.confidence, 0.95)
        self.assertEqual((), report.missing_evidence)
        self.assertEqual((), report.unavailable_evidence)
        self.assertEqual(6, len(report.evidence))

    def test_missing_causal_evidence_forces_abstention(self):
        values = fault_values()
        values["causal"] = None
        report = investigate(FakeClient(values))
        self.assertEqual("abstain", report.status)
        self.assertIsNone(report.hypothesis)
        self.assertIn("causal", report.missing_evidence)
        self.assertEqual(0.0, report.confidence)

    def test_missing_one_contradiction_metric_marks_group_missing(self):
        values = fault_values()
        values["contradiction_gpu"] = None
        report = investigate(FakeClient(values))
        self.assertEqual("abstain", report.status)
        self.assertEqual(("contradiction",), report.missing_evidence)

    def test_symptom_without_supporting_cause_abstains(self):
        values = fault_values()
        values["causal"] = 0.3
        report = investigate(FakeClient(values))
        self.assertEqual("abstain", report.status)
        self.assertIsNone(report.hypothesis)
        self.assertEqual((), report.missing_evidence)

    def test_healthy_camera_returns_no_incident(self):
        values = fault_values()
        values["symptom"] = 0.0
        values["causal"] = 0.3
        report = investigate(FakeClient(values))
        self.assertEqual("no_incident", report.status)
        self.assertIsNone(report.hypothesis)
        self.assertGreater(report.confidence, 0.9)

    def test_fixed_query_budget_is_six_reads(self):
        client = FakeClient(fault_values())
        investigate(client)
        self.assertEqual(6, len(client.calls))
        self.assertEqual(set(query for query, _ in QUERIES.values()), set(client.calls))

    def test_evidence_source_failure_returns_sanitized_abstention_and_stops_collection(self):
        secret = "Bearer super-secret-provider-token"
        client = FailingClient(fault_values(), "causal", EvidenceUnavailable(secret))
        report = investigate(client)
        self.assertEqual("abstain", report.status)
        self.assertIsNone(report.hypothesis)
        self.assertEqual(0.0, report.confidence)
        self.assertEqual(("causal",), report.unavailable_evidence)
        self.assertEqual((), report.missing_evidence)
        self.assertNotIn(secret, report.summary)
        self.assertNotIn(secret, str(report.to_dict()))
        self.assertEqual(2, len(client.calls))

    def test_programming_error_is_not_swallowed_as_evidence_unavailability(self):
        client = FailingClient(fault_values(), "causal", TypeError("adapter bug"))
        with self.assertRaisesRegex(TypeError, "adapter bug"):
            investigate(client)


if __name__ == "__main__":
    unittest.main()
