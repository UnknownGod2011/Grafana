import unittest

from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint, ObservableCheckpointStore
from investigator import Evidence, IncidentReport


class FakeStore:
    def __init__(self):
        self.value = None
        self.load_error = None
        self.save_error = None

    def load(self):
        if self.load_error is not None:
            raise self.load_error
        return self.value

    def save(self, checkpoint):
        if self.save_error is not None:
            raise self.save_error
        self.value = checkpoint


def checkpoint():
    import hashlib
    import json

    report = IncidentReport(
        "diagnosed", "broadcast-alpha", "program-feed", "uplink-b packet loss", 0.97,
        "bounded diagnosis", (), (Evidence("symptom", "fixed-query", 4.0, ">1", True),),
    )
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return IncidentCheckpoint("incident-001", revision, report, None, None, 1)


class CheckpointObservabilityTests(unittest.TestCase):
    def test_empty_load_and_successful_save_use_bounded_labels(self):
        inner = FakeStore()
        clock = iter((10.0, 10.2, 20.0, 20.3))
        store = ObservableCheckpointStore(inner, monotonic=lambda: next(clock))

        self.assertIsNone(store.load())
        store.save(checkpoint())
        metrics = store.prometheus_metrics()

        self.assertIn('stageguard_checkpoint_loads_total{result="empty"} 1', metrics)
        self.assertIn('stageguard_checkpoint_saves_total{result="ok"} 1', metrics)
        self.assertIn('stageguard_checkpoint_last_operation_latency_seconds{operation="load"} 0.200000', metrics)
        self.assertIn('stageguard_checkpoint_last_operation_latency_seconds{operation="save"} 0.300000', metrics)
        self.assertIn("stageguard_checkpoint_last_operation_ok 1", metrics)
        self.assertNotIn("broadcast-alpha", metrics)
        self.assertNotIn("incident-001", metrics)

    def test_conflict_is_distinct_from_generic_failure(self):
        inner = FakeStore()
        inner.save_error = CheckpointConflictError("provider detail must not escape")
        store = ObservableCheckpointStore(inner)

        with self.assertRaises(CheckpointConflictError):
            store.save(checkpoint())

        metrics = store.prometheus_metrics()
        self.assertIn('stageguard_checkpoint_saves_total{result="conflict"} 1', metrics)
        self.assertIn('stageguard_checkpoint_saves_total{result="failed"} 0', metrics)
        self.assertIn("stageguard_checkpoint_last_operation_ok 0", metrics)
        self.assertNotIn("provider detail", metrics)

    def test_generic_load_and_save_failures_are_counted_without_exception_text(self):
        inner = FakeStore()
        inner.load_error = RuntimeError("secret bucket/path")
        store = ObservableCheckpointStore(inner)
        with self.assertRaises(RuntimeError):
            store.load()
        inner.load_error = None
        inner.save_error = RuntimeError("credential detail")
        with self.assertRaises(RuntimeError):
            store.save(checkpoint())

        metrics = store.prometheus_metrics()
        self.assertIn('stageguard_checkpoint_loads_total{result="failed"} 1', metrics)
        self.assertIn('stageguard_checkpoint_saves_total{result="failed"} 1', metrics)
        self.assertNotIn("secret bucket", metrics)
        self.assertNotIn("credential detail", metrics)


if __name__ == "__main__":
    unittest.main()
