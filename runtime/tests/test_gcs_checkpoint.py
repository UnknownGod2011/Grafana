import unittest

from incident_checkpoint import CheckpointConflictError, GoogleCloudStorageCheckpointStore, IncidentCheckpoint
from investigator import Evidence, IncidentReport

KEY = b"k" * 32


class PreconditionFailed(Exception):
    code = 412


class FakeBlob:
    def __init__(self):
        self.data = None
        self.generation = None
        self.uploads = []
        self.downloads = []
        self.force_conflict = False

    def exists(self):
        return self.data is not None

    def reload(self):
        if self.data is None:
            raise AssertionError("reload called for missing blob")

    def download_as_bytes(self, *, if_generation_match=None):
        if self.data is None:
            raise FileNotFoundError
        if if_generation_match is not None and if_generation_match != self.generation:
            raise PreconditionFailed("generation mismatch")
        self.downloads.append(if_generation_match)
        return self.data

    def upload_from_string(self, data, *, content_type, if_generation_match):
        if self.force_conflict:
            raise PreconditionFailed("provider object path must remain private")
        expected = 0 if self.data is None else self.generation
        if if_generation_match != expected:
            raise PreconditionFailed("generation mismatch")
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
        store = GoogleCloudStorageCheckpointStore(bucket, KEY)
        store.save(checkpoint())
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        self.assertEqual(("application/json", 0), blob.uploads[0])
        self.assertEqual(1, store.load().sequence)

    def test_update_uses_generation_pinned_by_previous_success(self):
        bucket = FakeBucket()
        store = GoogleCloudStorageCheckpointStore(bucket, KEY)
        store.save(checkpoint(1))
        store.save(checkpoint(2))
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        self.assertEqual(("application/json", 1), blob.uploads[1])
        self.assertEqual(2, store.load().sequence)
        self.assertEqual(2, blob.downloads[-1])

    def test_two_stale_writers_cannot_silently_overwrite_winner(self):
        bucket = FakeBucket()
        seed = GoogleCloudStorageCheckpointStore(bucket, KEY)
        seed.save(checkpoint(1))

        writer_a = GoogleCloudStorageCheckpointStore(bucket, KEY)
        writer_b = GoogleCloudStorageCheckpointStore(bucket, KEY)
        self.assertEqual(1, writer_a.load().sequence)
        self.assertEqual(1, writer_b.load().sequence)

        writer_a.save(checkpoint(2))
        with self.assertRaisesRegex(CheckpointConflictError, "concurrent update conflict"):
            writer_b.save(checkpoint(3))

        verifier = GoogleCloudStorageCheckpointStore(bucket, KEY)
        self.assertEqual(2, verifier.load().sequence)
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        self.assertEqual(2, blob.generation)

    def test_fresh_store_cannot_overwrite_existing_object_without_loading(self):
        bucket = FakeBucket()
        writer = GoogleCloudStorageCheckpointStore(bucket, KEY)
        writer.save(checkpoint(1))
        stale_uninitialized = GoogleCloudStorageCheckpointStore(bucket, KEY)
        with self.assertRaises(CheckpointConflictError):
            stale_uninitialized.save(checkpoint(2))
        self.assertEqual(1, writer.load().sequence)

    def test_generation_precondition_failure_has_bounded_conflict_type(self):
        bucket = FakeBucket()
        store = GoogleCloudStorageCheckpointStore(bucket, KEY)
        store.save(checkpoint(1))
        bucket.blob("stageguard/incident-checkpoint.json").force_conflict = True
        with self.assertRaisesRegex(CheckpointConflictError, "concurrent update conflict") as caught:
            store.save(checkpoint(2))
        self.assertNotIn("provider object path", str(caught.exception))

    def test_wrong_signing_key_fails_closed(self):
        bucket = FakeBucket()
        GoogleCloudStorageCheckpointStore(bucket, KEY).save(checkpoint())
        with self.assertRaises(ValueError):
            GoogleCloudStorageCheckpointStore(bucket, b"x" * 32).load()

    def test_bucket_writer_cannot_forge_state_without_hmac(self):
        bucket = FakeBucket()
        store = GoogleCloudStorageCheckpointStore(bucket, KEY)
        store.save(checkpoint())
        blob = bucket.blob("stageguard/incident-checkpoint.json")
        tampered = bytearray(blob.data)
        index = tampered.find(b"broadcast-alpha")
        self.assertGreaterEqual(index, 0)
        tampered[index:index + len(b"broadcast-alpha")] = b"broadcast-omega"
        blob.data = bytes(tampered)
        with self.assertRaises(ValueError):
            store.load()

    def test_object_name_is_fixed_and_traversal_is_rejected(self):
        bucket = FakeBucket()
        with self.assertRaises(ValueError):
            GoogleCloudStorageCheckpointStore(bucket, KEY, "../other.json")
        store = GoogleCloudStorageCheckpointStore(bucket, KEY, "/prod/current.json")
        store.save(checkpoint())
        self.assertIn("prod/current.json", bucket.blobs)

    def test_short_signing_key_is_rejected(self):
        with self.assertRaises(ValueError):
            GoogleCloudStorageCheckpointStore(FakeBucket(), b"short")


if __name__ == "__main__":
    unittest.main()
