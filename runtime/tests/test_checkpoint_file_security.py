#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from checkpoint_file_security import (
    assert_private_regular_file_identity,
    atomic_write_private_bytes,
    open_private_regular_file,
    read_private_bytes,
)


@unittest.skipIf(os.name == "nt", "hard-link and mode assertions are POSIX-focused")
class CheckpointFileSecurityTests(unittest.TestCase):
    def test_read_rejects_symlink_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_bytes(b"secret")
            checkpoint = root / "checkpoint.json"
            checkpoint.symlink_to(target)

            with self.assertRaises(RuntimeError):
                read_private_bytes(checkpoint, max_bytes=64)

            self.assertEqual(target.read_bytes(), b"secret")

    def test_read_rejects_hard_link_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_bytes(b"state")
            checkpoint = root / "checkpoint.json"
            os.link(target, checkpoint)

            with self.assertRaises(RuntimeError):
                read_private_bytes(checkpoint, max_bytes=64)

            self.assertEqual(target.read_bytes(), b"state")

    def test_identity_check_rejects_post_open_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_bytes(b"old")
            fd = open_private_regular_file(checkpoint, os.O_RDONLY)
            try:
                displaced = root / "displaced.json"
                checkpoint.replace(displaced)
                checkpoint.write_bytes(b"replacement")
                with self.assertRaises(RuntimeError):
                    assert_private_regular_file_identity(fd, checkpoint)
            finally:
                os.close(fd)

    def test_read_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint.json"
            checkpoint.write_bytes(b"12345")
            with self.assertRaises(ValueError):
                read_private_bytes(checkpoint, max_bytes=4)

    def test_atomic_write_round_trip_is_private_single_link_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp) / "checkpoint.json"
            atomic_write_private_bytes(checkpoint, b'{"ok":true}\n')

            self.assertEqual(read_private_bytes(checkpoint, max_bytes=64), b'{"ok":true}\n')
            st = os.lstat(checkpoint)
            self.assertTrue(stat.S_ISREG(st.st_mode))
            self.assertEqual(st.st_nlink, 1)
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o600)

    def test_atomic_write_replaces_symlink_entry_without_mutating_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_bytes(b"do-not-touch")
            checkpoint = root / "checkpoint.json"
            checkpoint.symlink_to(target)

            atomic_write_private_bytes(checkpoint, b"new-state")

            self.assertEqual(target.read_bytes(), b"do-not-touch")
            self.assertFalse(checkpoint.is_symlink())
            self.assertEqual(checkpoint.read_bytes(), b"new-state")


if __name__ == "__main__":
    unittest.main()
