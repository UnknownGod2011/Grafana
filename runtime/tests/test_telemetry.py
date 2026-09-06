import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from investigator import investigate
from telemetry import TelemetryProfile, investigation_queries, recovery_queries


class RecordingClient:
    def __init__(self, values_by_query):
        self.values_by_query = values_by_query
        self.calls = []

    def instant(self, promql):
        self.calls.append(promql)
        return self.values_by_query.get(promql)


class TelemetryProfileTests(unittest.TestCase):
    def custom_profile(self):
        return TelemetryProfile(
            production_id='tenant-a/prod"42',
            affected_feed="camera.hero",
            affected_uplink="wan-primary",
            healthy_uplink="wan-backup",
            healthy_peer_feeds=("camera-a", "camera-b"),
            dropped_frames_metric="media_frames_dropped_total",
            packet_loss_metric="edge_packet_loss_pct",
            cpu_metric="media_encoder_cpu_pct",
            gpu_metric="media_encoder_gpu_pct",
            production_label="tenant",
            feed_label="source",
            uplink_label="path",
        )

    def test_custom_mapping_preserves_exact_six_query_budget(self):
        profile = self.custom_profile()
        queries = investigation_queries(profile)
        values = {
            queries["symptom"][0]: 8.0,
            queries["causal"][0]: 18.0,
            queries["contradiction_cpu"][0]: 41.0,
            queries["contradiction_gpu"][0]: 37.0,
            queries["healthy_peer_loss"][0]: 0.2,
            queries["healthy_peer_drop"][0]: 0.0,
        }
        client = RecordingClient(values)
        report = investigate(client, profile)
        self.assertEqual("diagnosed", report.status)
        self.assertEqual(profile.production_id, report.production_id)
        self.assertEqual("wan-primary packet loss", report.hypothesis)
        self.assertEqual(6, len(client.calls))
        self.assertEqual(set(q for q, _ in queries.values()), set(client.calls))

    def test_production_value_is_escaped_not_interpreted_as_matcher(self):
        query = investigation_queries(self.custom_profile())["causal"][0]
        self.assertIn('tenant="tenant-a/prod\\"42"', query)
        self.assertNotIn('tenant=~', query)

    def test_peer_values_are_regex_escaped(self):
        profile = TelemetryProfile(healthy_peer_feeds=("cam.1", "cam+2"))
        query = investigation_queries(profile)["healthy_peer_drop"][0]
        self.assertIn('cam\\.1|cam\\+2', query)

    def test_unsafe_metric_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            TelemetryProfile(packet_loss_metric='loss_metric} or vector(1)')

    def test_unsafe_label_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            TelemetryProfile(production_label='production_id="other"')

    def test_recovery_contract_remains_exactly_two_queries(self):
        queries = recovery_queries(self.custom_profile())
        self.assertEqual({"packet_loss", "dropped_frames"}, set(queries))
        self.assertEqual(2, len(queries))

    def test_missing_mapped_evidence_still_abstains(self):
        profile = self.custom_profile()
        queries = investigation_queries(profile)
        values = {q: 0.0 for q, _ in queries.values()}
        values[queries["causal"][0]] = None
        report = investigate(RecordingClient(values), profile)
        self.assertEqual("abstain", report.status)
        self.assertIn("causal", report.missing_evidence)


if __name__ == "__main__":
    unittest.main()
