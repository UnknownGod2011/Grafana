import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from onboarding import load_telemetry_profile, preflight_telemetry
from telemetry import investigation_queries, recovery_queries


class RecordingClient:
    def __init__(self, values=None, errors=None):
        self.values = values or {}
        self.errors = errors or {}
        self.calls = []

    def instant(self, promql):
        self.calls.append(promql)
        if promql in self.errors:
            raise self.errors[promql]
        return self.values.get(promql)


def write_config(document):
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    try:
        json.dump(document, handle)
        return pathlib.Path(handle.name)
    finally:
        handle.close()


class OnboardingTests(unittest.TestCase):
    def valid_document(self):
        return {
            "version": 1,
            "profile": {
                "production_id": "prod-42",
                "affected_feed": "hero-cam",
                "affected_uplink": "primary-wan",
                "healthy_uplink": "backup-wan",
                "healthy_peer_feeds": ["cam-a", "cam-b"],
                "dropped_frames_metric": "media_frames_dropped_total",
                "packet_loss_metric": "media_packet_loss_percent",
                "cpu_metric": "media_encoder_cpu_percent",
                "gpu_metric": "media_encoder_gpu_percent",
                "production_label": "production",
                "feed_label": "feed",
                "uplink_label": "uplink",
            },
        }

    def test_loads_versioned_profile(self):
        path = write_config(self.valid_document())
        self.addCleanup(path.unlink)
        profile = load_telemetry_profile(path)
        self.assertEqual("prod-42", profile.production_id)
        self.assertEqual(("cam-a", "cam-b"), profile.healthy_peer_feeds)

    def test_rejects_unknown_top_level_field(self):
        document = self.valid_document()
        document["promql"] = "vector(1)"
        path = write_config(document)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "unknown telemetry config"):
            load_telemetry_profile(path)

    def test_rejects_unknown_profile_field(self):
        document = self.valid_document()
        document["profile"]["datasource_uid"] = "arbitrary"
        path = write_config(document)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "unknown profile field"):
            load_telemetry_profile(path)

    def test_rejects_unsupported_version(self):
        document = self.valid_document()
        document["version"] = 2
        path = write_config(document)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "unsupported telemetry config version"):
            load_telemetry_profile(path)

    def test_ready_requires_all_eight_bounded_slots(self):
        path = write_config(self.valid_document())
        self.addCleanup(path.unlink)
        profile = load_telemetry_profile(path)
        all_queries = [q for q, _ in investigation_queries(profile).values()]
        all_queries += [q for q, _ in recovery_queries(profile).values()]
        client = RecordingClient(values={query: 1.0 for query in all_queries})
        result = preflight_telemetry(client, profile)
        self.assertTrue(result.ready)
        self.assertEqual(8, len(result.slots))
        self.assertEqual(8, len(client.calls))
        self.assertTrue(all(slot.status == "ok" for slot in result.slots))

    def test_missing_slot_refuses_activation_but_checks_remaining_slots(self):
        path = write_config(self.valid_document())
        self.addCleanup(path.unlink)
        profile = load_telemetry_profile(path)
        all_queries = [q for q, _ in investigation_queries(profile).values()]
        all_queries += [q for q, _ in recovery_queries(profile).values()]
        values = {query: 1.0 for query in all_queries}
        values[all_queries[2]] = None
        client = RecordingClient(values=values)
        result = preflight_telemetry(client, profile)
        self.assertFalse(result.ready)
        self.assertEqual(8, len(client.calls))
        self.assertEqual("missing", result.slots[2].status)
        self.assertEqual(1, len(result.failures))

    def test_ambiguous_or_transport_error_is_reported_per_slot(self):
        path = write_config(self.valid_document())
        self.addCleanup(path.unlink)
        profile = load_telemetry_profile(path)
        all_queries = [q for q, _ in investigation_queries(profile).values()]
        all_queries += [q for q, _ in recovery_queries(profile).values()]
        client = RecordingClient(
            values={query: 1.0 for query in all_queries},
            errors={all_queries[4]: RuntimeError("returned 2 series; expected exactly one")},
        )
        result = preflight_telemetry(client, profile)
        self.assertFalse(result.ready)
        self.assertEqual("error", result.slots[4].status)
        self.assertIn("2 series", result.slots[4].detail)
        self.assertEqual(8, len(client.calls))


if __name__ == "__main__":
    unittest.main()
