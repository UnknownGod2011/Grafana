import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from incident_checkpoint import IncidentCheckpoint
from investigator import IncidentReport
from signed_json_checkpoint import SignedJsonCheckpointStore


_SIGNING_KEY = b"stageguard-test-signing-key-32-bytes!!"
_OTHER_KEY = b"stageguard-other-signing-key-32-bytes!"


def checkpoint(sequence: int = 1) -> IncidentCheckpoint:
    report = IncidentReport(
        status="diagnosed",
        production_id="demo-production",
        affected_feed="program",
        hypothesis="uplink_loss",
        confidence=0.9,
        summary="bounded signed checkpoint",
        missing_evidence=(),
        evidence=(),
    )
    return IncidentCheckpoint(
        incident_id="incident-signed-001",
        revision="b" * 16,
        report=report,
        approval=None,
        outcome=None,
        sequence=sequence,
        execution_phase="none",
    )


class SignedJsonCheckpointStoreFileSecurityTests(unittest.TestCase):
    def test_missing_checkpoint_loads_as_empty_without_path_precheck(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            self.assertIsNone(SignedJsonCheckpointStore(path, _SIGNING_KEY).load())

    def test_round_trip_uses_private_single_link_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store = SignedJsonCheckpointStore(path, _SIGNING_KEY)
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
                SignedJsonCheckpointStore(path, _SIGNING_KEY).load()
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
                SignedJsonCheckpointStore(path, _SIGNING_KEY).load()
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

            store = SignedJsonCheckpointStore(path, _SIGNING_KEY)
            store.save(checkpoint())

            self.assertEqual(b"preserve-me", target.read_bytes())
            self.assertFalse(path.is_symlink())
            self.assertEqual(checkpoint(), store.load())

    def test_wrong_signing_key_still_rejects_securely_read_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            SignedJsonCheckpointStore(path, _SIGNING_KEY).save(checkpoint())

            with self.assertRaisesRegex(ValueError, "authenticity check failed"):
                SignedJsonCheckpointStore(path, _OTHER_KEY).load()

    def test_load_propagates_post_open_identity_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            with mock.patch(
                "signed_json_checkpoint.read_private_bytes",
                side_effect=RuntimeError("checkpoint file path changed while in use"),
            ) as secure_read:
                with self.assertRaisesRegex(RuntimeError, "path changed"):
                    SignedJsonCheckpointStore(path, _SIGNING_KEY).load()
            secure_read.assert_called_once_with(path, max_bytes=256 * 1024)

    def test_save_delegates_to_atomic_private_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            with mock.patch("signed_json_checkpoint.atomic_write_private_bytes") as secure_write:
                SignedJsonCheckpointStore(path, _SIGNING_KEY).save(checkpoint())
            secure_write.assert_called_once()
            called_path, called_bytes = secure_write.call_args.args
            self.assertEqual(path, called_path)
            self.assertIsInstance(called_bytes, bytes)
            self.assertLessEqual(len(called_bytes), 256 * 1024)
            self.assertIn(b'"hmac_sha256"', called_bytes)


if __name__ == "__main__":
    unittest.main()
