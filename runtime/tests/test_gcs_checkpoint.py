import unittest

from incident_checkpoint import GoogleCloudStorageCheckpointStore, IncidentCheckpoint
from investigator import Evidence, IncidentReport


class FakeBlob:
    def __init__(self):
        self.data = None
        self.generation = None
        self.uploads = []

    def exists(self):
        return self.data is not None

    def reload(self):
        if self.data is None:
            raise AssertionError("reload called for missing blob")

    def download_as_bytes(self):
        if self.data is None:
            raise FileNotFoundError
        return self.data

    def upload_from_string(self, data, *, content_type, if_generation_match):
        expected = 0 if self.data is None else self.generation
        if if_generation_match != expected:
            raise RuntimeError("generation mismatch")
        self.data = bytes(data)
        self.generation = 1 if self.generation is None else self.generation + 1
        self.uploads.append((content_type, if_generation_match))


class FakeBucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, name):
        return self.blobs.setdefault(name, FakeBlob())


def checkpoint(sequence=1):
    report = IncidentReport(
        "diagnosed", "broadcast-alpha", "program-feed", "uplink-b packet loss", 0.97, "bounded diagnosis", (),
        (Evidence("symptom", "fixed-query", 4.0, ">1", True),),
    )
    import hashlib, json
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return IncidentCheckpoint("incident-001", revision, report, None, None, sequence)


class GcsCheckpointTests(unittest.TestCase):
    def test_first_write_uses_create_only_generation_precondition(self):
        bucket = FakeBucket()
        store = GoogleCloudStorageCheckpointStore(bucket)
        store.save(checkpoint())
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        self.assertEqual(("application/json", 0), blob.uploads[0])
        self.assertEqual(1, store.load().sequence)

    def test_update_uses_current_generation_precondition(self):
        bucket = FakeBucket()
        store = GoogleCloudStorageCheckpointStore(bucket)
        store.save(checkpoint(1))
        store.save(checkpoint(2))
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        self.assertEqual(("application/json", 1), blob.uploads[1])
        self.assertEqual(2, store.load().sequence)

    def test_object_name_is_fixed_and_traversal_is_rejected(self):
        bucket = FakeBucket()
        with self.assertRaises(ValueError):
            GoogleCloudStorageCheckpointStore(bucket, "../other.json")
        store = GoogleCloudStorageCheckpointStore(bucket, "/prod/current.json")
        store.save(checkpoint())
        self.assertIn("prod/current.json", bucket.blobs)


if __name__ == "__main__":
    unittest.main()
