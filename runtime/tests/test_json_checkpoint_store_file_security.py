import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from incident_checkpoint import IncidentCheckpoint, JsonCheckpointStore
from investigator import IncidentReport


def checkpoint(sequence: int = 1) -> IncidentCheckpoint:
    report = IncidentReport(
        status="diagnosed",
        production_id="demo-production",
        affected_feed="program",
        hypothesis="uplink_loss",
        confidence=0.9,
        summary="bounded test checkpoint",
        missing_evidence=(),
        evidence=(),
    )
    return IncidentCheckpoint(
        incident_id="incident-001",
        revision="a" * 16,
        report=report,
        approval=None,
        outcome=None,
        sequence=sequence,
        execution_phase="none",
    )


class JsonCheckpointStoreFileSecurityTests(unittest.TestCase):
    def test_missing_checkpoint_loads_as_empty_without_path_precheck(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            self.assertIsNone(JsonCheckpointStore(path).load())

    def test_round_trip_uses_private_single_link_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store = JsonCheckpointStore(path)
            expected = checkpoint()

            store.save(expected)
            restored = store.load()

            self.assertEqual(expected, restored)
            file_stat = os.lstat(path)
            self.assertTrue(stat.S_ISREG(file_stat.st_mode))
            self.assertEqual(1, file_stat.st_nlink)
            if os.name != "nt":
                self.assertEqual(0o600, stat.S_IMODE(file_stat.st_mode))

    def test_symlink_load_is_rejected_without_reading_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_bytes(b"do-not-trust")
            path = root / "checkpoint.json"
            try:
                path.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this platform")

            with self.assertRaises(RuntimeError):
                JsonCheckpointStore(path).load()
            self.assertEqual(b"do-not-trust", target.read_bytes())

    def test_hard_link_load_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            peer = root / "peer.json"
            peer.write_bytes(b"not-a-checkpoint")
            path = root / "checkpoint.json"
            try:
                os.link(peer, path)
            except (OSError, NotImplementedError):
                self.skipTest("hard links unavailable on this platform")

            with self.assertRaisesRegex(RuntimeError, "hard links"):
                JsonCheckpointStore(path).load()
            self.assertEqual(b"not-a-checkpoint", peer.read_bytes())

    def test_save_replaces_symlink_entry_without_mutating_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_bytes(b"preserve-me")
            path = root / "checkpoint.json"
            try:
                path.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this platform")

            store = JsonCheckpointStore(path)
            store.save(checkpoint())

            self.assertEqual(b"preserve-me", target.read_bytes())
            self.assertFalse(path.is_symlink())
            self.assertEqual(checkpoint(), store.load())

    def test_store_propagates_post_open_identity_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            with mock.patch(
                "incident_checkpoint.read_private_bytes",
                side_effect=RuntimeError("checkpoint file path changed while in use"),
            ) as secure_read:
                with self.assertRaisesRegex(RuntimeError, "path changed"):
                    JsonCheckpointStore(path).load()
            secure_read.assert_called_once()

    def test_save_delegates_to_atomic_private_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            with mock.patch("incident_checkpoint.atomic_write_private_bytes") as secure_write:
                JsonCheckpointStore(path).save(checkpoint())
            secure_write.assert_called_once()
            called_path, called_bytes = secure_write.call_args.args
            self.assertEqual(path, called_path)
            self.assertIsInstance(called_bytes, bytes)
            self.assertLessEqual(len(called_bytes), 256 * 1024)


if __name__ == "__main__":
    unittest.main()
