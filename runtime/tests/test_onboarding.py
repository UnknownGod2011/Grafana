import json
import math
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from evidence_errors import EvidenceUnavailable
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

    def profile_and_queries(self):
        path = write_config(self.valid_document())
        self.addCleanup(path.unlink)
        profile = load_telemetry_profile(path)
        all_queries = [q for q, _ in investigation_queries(profile).values()]
        all_queries += [q for q, _ in recovery_queries(profile).values()]
        return profile, all_queries

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
        profile, all_queries = self.profile_and_queries()
        client = RecordingClient(values={query: 1.0 for query in all_queries})
        result = preflight_telemetry(client, profile)
        self.assertTrue(result.ready)
        self.assertEqual(8, len(result.slots))
        self.assertEqual(8, len(client.calls))
        self.assertTrue(all(slot.status == "ok" for slot in result.slots))

    def test_missing_slot_refuses_activation_but_checks_remaining_slots(self):
        profile, all_queries = self.profile_and_queries()
        values = {query: 1.0 for query in all_queries}
        values[all_queries[2]] = None
        client = RecordingClient(values=values)
        result = preflight_telemetry(client, profile)
        self.assertFalse(result.ready)
        self.assertEqual(8, len(client.calls))
        self.assertEqual("missing", result.slots[2].status)
        self.assertEqual(1, len(result.failures))

    def test_non_finite_samples_refuse_activation_and_never_serialize_non_finite_json(self):
        for sample in (math.nan, math.inf, -math.inf):
            with self.subTest(sample=sample):
                profile, all_queries = self.profile_and_queries()
                values = {query: 1.0 for query in all_queries}
                values[all_queries[3]] = sample
                client = RecordingClient(values=values)

                result = preflight_telemetry(client, profile)

                self.assertFalse(result.ready)
                self.assertEqual(8, len(client.calls))
                self.assertEqual("invalid", result.slots[3].status)
                self.assertIsNone(result.slots[3].value)
                self.assertEqual("query returned a non-finite sample", result.slots[3].detail)
                serialized = json.dumps(result.to_dict(), allow_nan=False)
                self.assertNotIn("NaN", serialized)
                self.assertNotIn("Infinity", serialized)

    def test_adapter_type_violation_fails_loudly(self):
        for sample in (True, "1.0", object()):
            with self.subTest(sample=type(sample).__name__):
                profile, all_queries = self.profile_and_queries()
                values = {query: 1.0 for query in all_queries}
                values[all_queries[0]] = sample
                client = RecordingClient(values=values)

                with self.assertRaisesRegex(TypeError, "numeric sample or None"):
                    preflight_telemetry(client, profile)
                self.assertEqual(1, len(client.calls))

    def test_expected_evidence_error_is_redacted_and_remaining_slots_are_checked(self):
        profile, all_queries = self.profile_and_queries()
        secret = "https://user:super-secret@example.invalid/api"
        client = RecordingClient(
            values={query: 1.0 for query in all_queries},
            errors={all_queries[4]: EvidenceUnavailable(f"provider failed at {secret}")},
        )
        result = preflight_telemetry(client, profile)
        self.assertFalse(result.ready)
        self.assertEqual(8, len(client.calls))
        self.assertEqual("error", result.slots[4].status)
        self.assertEqual("evidence source unavailable", result.slots[4].detail)
        self.assertNotIn("super-secret", json.dumps(result.to_dict()))

    def test_unexpected_programming_error_is_not_downgraded_to_telemetry_unavailability(self):
        profile, all_queries = self.profile_and_queries()
        client = RecordingClient(
            values={query: 1.0 for query in all_queries},
            errors={all_queries[1]: AssertionError("broken adapter invariant")},
        )
        with self.assertRaisesRegex(AssertionError, "broken adapter invariant"):
            preflight_telemetry(client, profile)
        self.assertEqual(2, len(client.calls))


if __name__ == "__main__":
    unittest.main()
