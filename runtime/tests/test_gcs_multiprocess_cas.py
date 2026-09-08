import hashlib
import json
import multiprocessing
import os
import unittest

from incident_checkpoint import CheckpointConflictError, GoogleCloudStorageCheckpointStore, IncidentCheckpoint
from investigator import Evidence, IncidentReport

KEY = b"k" * 32
OBJECT = "stageguard/incident-checkpoint.json"


class PreconditionFailed(Exception):
    code = 412


class SharedBlob:
    """Process-safe, generation-aware subset of the GCS Blob contract."""

    def __init__(self, state, lock):
        self._state = state
        self._lock = lock

    @property
    def generation(self):
        value = self._state.get("generation", 0)
        return None if value == 0 else int(value)

    def exists(self):
        with self._lock:
            return bool(self._state.get("data"))

    def reload(self):
        with self._lock:
            if not self._state.get("data"):
                raise FileNotFoundError

    def download_as_bytes(self, *, if_generation_match=None):
        with self._lock:
            generation = int(self._state.get("generation", 0))
            data = self._state.get("data", b"")
            if not data:
                raise FileNotFoundError
            if if_generation_match is not None and int(if_generation_match) != generation:
                raise PreconditionFailed("generation mismatch")
            return bytes(data)

    def upload_from_string(self, data, *, content_type, if_generation_match):
        if content_type != "application/json":
            raise AssertionError("unexpected content type")
        with self._lock:
            generation = int(self._state.get("generation", 0))
            expected = 0 if not self._state.get("data") else generation
            if int(if_generation_match) != expected:
                raise PreconditionFailed("generation mismatch")
            self._state["data"] = bytes(data)
            self._state["generation"] = generation + 1


class SharedBucket:
    def __init__(self, state, lock):
        self._state = state
        self._lock = lock

    def blob(self, name):
        if name != OBJECT:
            raise AssertionError("unexpected checkpoint object")
        return SharedBlob(self._state, self._lock)


def checkpoint(sequence):
    report = IncidentReport(
        "diagnosed",
        "broadcast-alpha",
        "program-feed",
        "uplink-b packet loss",
        0.97,
        "bounded diagnosis",
        (),
        (Evidence("symptom", "fixed-query", 4.0, ">1", True),),
    )
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return IncidentCheckpoint("incident-001", revision, report, None, None, sequence, "none")


def _race_writer(tag, sequence, state, lock, barrier, results, retry_event):
    """Load one generation, race a CAS, then let the loser retry while stale."""
    store = GoogleCloudStorageCheckpointStore(SharedBucket(state, lock), KEY, OBJECT)
    loaded = store.load()
    results.put((tag, "loaded", loaded.sequence))
    barrier.wait()
    try:
        store.save(checkpoint(sequence))
    except CheckpointConflictError:
        results.put((tag, "first", "conflict"))
        retry_event.wait(10)
        try:
            store.save(checkpoint(sequence + 1000))
        except CheckpointConflictError:
            results.put((tag, "retry", "conflict"))
        else:
            results.put((tag, "retry", "unexpected-success"))
    else:
        results.put((tag, "first", "winner"))


def _create_writer(tag, sequence, state, lock, barrier, results):
    """Race two brand-new stores using the GCS create-only generation precondition."""
    store = GoogleCloudStorageCheckpointStore(SharedBucket(state, lock), KEY, OBJECT)
    loaded = store.load()
    results.put((tag, "loaded", None if loaded is None else loaded.sequence))
    barrier.wait()
    try:
        store.save(checkpoint(sequence))
    except CheckpointConflictError:
        results.put((tag, "first", "conflict"))
    else:
        results.put((tag, "first", "winner"))


@unittest.skipUnless(os.name == "posix", "multiprocess CAS acceptance requires POSIX process support")
class GcsMultiprocessCasAcceptanceTests(unittest.TestCase):
    def test_one_generation_winner_and_stale_loser_cannot_overwrite_recovery(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Manager() as manager:
            state = manager.dict(data=b"", generation=0)
            lock = manager.RLock()
            bucket = SharedBucket(state, lock)

            seed = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            seed.save(checkpoint(1))
            self.assertEqual(1, int(state["generation"]))

            barrier = ctx.Barrier(2)
            results = ctx.Queue()
            retry_event = ctx.Event()
            workers = [
                ctx.Process(target=_race_writer, args=("a", 2, state, lock, barrier, results, retry_event)),
                ctx.Process(target=_race_writer, args=("b", 3, state, lock, barrier, results, retry_event)),
            ]
            for worker in workers:
                worker.start()

            loaded = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({("a", "loaded", 1), ("b", "loaded", 1)}, set(loaded))

            first = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({"winner", "conflict"}, {item[2] for item in first})
            loser_tag = next(item[0] for item in first if item[2] == "conflict")
            self.assertEqual(2, int(state["generation"]))

            # A fresh store adopts the durable winner and writes a newer recovered
            # state. This models reconciliation plus fresh-evidence recovery.
            recovery = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            durable_winner = recovery.load()
            self.assertIn(durable_winner.sequence, {2, 3})
            recovery.save(checkpoint(100))
            self.assertEqual(3, int(state["generation"]))
            self.assertEqual(100, recovery.load().sequence)

            # The original losing process still holds generation 1. Even after
            # recovery advances the object again, it must remain unable to write.
            retry_event.set()
            retry = results.get(timeout=10)
            self.assertEqual((loser_tag, "retry", "conflict"), retry)

            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(0, worker.exitcode)

            verifier = GoogleCloudStorageCheckpointStore(bucket, KEY, OBJECT)
            final = verifier.load()
            self.assertEqual(100, final.sequence)
            self.assertEqual(3, int(state["generation"]))

    def test_two_uninitialized_processes_racing_create_have_one_winner(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Manager() as manager:
            state = manager.dict(data=b"", generation=0)
            lock = manager.RLock()
            barrier = ctx.Barrier(2)
            results = ctx.Queue()
            workers = [
                ctx.Process(target=_create_writer, args=("a", 1, state, lock, barrier, results)),
                ctx.Process(target=_create_writer, args=("b", 2, state, lock, barrier, results)),
            ]
            for worker in workers:
                worker.start()

            loaded = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({("a", "loaded", None), ("b", "loaded", None)}, set(loaded))
            first = [results.get(timeout=10), results.get(timeout=10)]
            self.assertEqual({"winner", "conflict"}, {item[2] for item in first})

            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())
                self.assertEqual(0, worker.exitcode)

            self.assertEqual(1, int(state["generation"]))
            verifier = GoogleCloudStorageCheckpointStore(SharedBucket(state, lock), KEY, OBJECT)
            self.assertIn(verifier.load().sequence, {1, 2})


if __name__ == "__main__":
    unittest.main()
