#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from checkpoint_file_security import atomic_write_private_bytes, read_private_bytes


@unittest.skipIf(os.name == "nt", "POSIX permission policy regression")
class CheckpointParentDirectoryPolicyTests(unittest.TestCase):
    def _assert_unsafe_parent_rejected(self, mode: int) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "state"
            parent.mkdir(mode=0o700)
            checkpoint = parent / "checkpoint.json"
            checkpoint.write_bytes(b"existing-state")
            os.chmod(checkpoint, 0o600)
            os.chmod(parent, mode)
            try:
                with self.assertRaisesRegex(RuntimeError, "group/world-writable"):
                    read_private_bytes(checkpoint, max_bytes=128)
                with self.assertRaisesRegex(RuntimeError, "group/world-writable"):
                    atomic_write_private_bytes(checkpoint, b"replacement")
                self.assertEqual(checkpoint.read_bytes(), b"existing-state")
            finally:
                os.chmod(parent, 0o700)

    def test_group_writable_parent_is_rejected(self) -> None:
        self._assert_unsafe_parent_rejected(0o770)

    def test_world_writable_parent_is_rejected(self) -> None:
        self._assert_unsafe_parent_rejected(0o707)

    def test_sticky_world_writable_parent_is_still_rejected(self) -> None:
        self._assert_unsafe_parent_rejected(0o1777)

    def test_private_parent_allows_checkpoint_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "state"
            parent.mkdir(mode=0o700)
            checkpoint = parent / "checkpoint.json"

            atomic_write_private_bytes(checkpoint, b'{"ok":true}\n')

            self.assertEqual(
                read_private_bytes(checkpoint, max_bytes=128),
                b'{"ok":true}\n',
            )


if __name__ == "__main__":
    unittest.main()
