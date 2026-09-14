#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import checkpoint_file_security
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

    @unittest.skipUnless(
        checkpoint_file_security._supports_directory_relative_open(),
        "requires directory-relative checkpoint reads",
    )
    def test_read_rejects_symlink_parent_without_reading_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_parent = root / "real-parent"
            real_parent.mkdir()
            (real_parent / "checkpoint.json").write_bytes(b"attacker-state")
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)

            with self.assertRaises(RuntimeError):
                read_private_bytes(linked_parent / "checkpoint.json", max_bytes=64)

            self.assertEqual((real_parent / "checkpoint.json").read_bytes(), b"attacker-state")

    @unittest.skipUnless(
        checkpoint_file_security._supports_directory_relative_open(),
        "requires directory-relative checkpoint reads",
    )
    def test_directory_relative_read_cannot_be_redirected_by_parent_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "state"
            parent.mkdir()
            checkpoint = parent / "checkpoint.json"
            checkpoint.write_bytes(b"trusted-state")
            displaced = root / "state-original"
            real_open = os.open
            real_replace = os.replace
            swapped = False

            def swap_then_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if not swapped and dir_fd is not None and path == checkpoint.name:
                    real_replace(parent, displaced)
                    parent.mkdir()
                    (parent / checkpoint.name).write_bytes(b"attacker-state")
                    swapped = True
                return real_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(checkpoint_file_security.os, "open", side_effect=swap_then_open):
                with self.assertRaisesRegex(RuntimeError, "parent directory changed"):
                    read_private_bytes(checkpoint, max_bytes=64)

            self.assertTrue(swapped)
            self.assertEqual((displaced / checkpoint.name).read_bytes(), b"trusted-state")
            self.assertEqual(checkpoint.read_bytes(), b"attacker-state")

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

    def test_atomic_write_rejects_symlink_parent_without_mutating_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_parent = root / "real-parent"
            real_parent.mkdir()
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)

            with self.assertRaises(RuntimeError):
                atomic_write_private_bytes(linked_parent / "checkpoint.json", b"blocked")

            self.assertFalse((real_parent / "checkpoint.json").exists())

    @unittest.skipUnless(
        checkpoint_file_security._supports_directory_relative_atomic_write(),
        "requires directory-relative atomic replacement",
    )
    def test_atomic_write_detects_parent_path_substitution_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "state"
            parent.mkdir()
            checkpoint = parent / "checkpoint.json"
            displaced = root / "state-original"
            real_write = checkpoint_file_security._write_all_and_sync
            swapped = False

            def write_then_swap(fd: int, data: bytes) -> None:
                nonlocal swapped
                real_write(fd, data)
                parent.replace(displaced)
                parent.mkdir()
                swapped = True

            with mock.patch.object(
                checkpoint_file_security,
                "_write_all_and_sync",
                side_effect=write_then_swap,
            ):
                with self.assertRaisesRegex(RuntimeError, "parent directory changed"):
                    atomic_write_private_bytes(checkpoint, b"new-state")

            self.assertTrue(swapped)
            self.assertFalse(checkpoint.exists())
            self.assertFalse((displaced / "checkpoint.json").exists())
            self.assertEqual(list(displaced.glob(".checkpoint-*")), [])

    @unittest.skipUnless(
        checkpoint_file_security._supports_directory_relative_atomic_write(),
        "requires directory-relative atomic replacement",
    )
    def test_directory_relative_replace_never_targets_substituted_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "state"
            parent.mkdir()
            checkpoint = parent / "checkpoint.json"
            displaced = root / "state-original"
            real_replace = os.replace
            swapped = False

            def swap_then_replace(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                nonlocal swapped
                if not swapped and src_dir_fd is not None and dst_dir_fd is not None:
                    real_replace(parent, displaced)
                    parent.mkdir()
                    swapped = True
                return real_replace(
                    src,
                    dst,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                )

            with mock.patch.object(checkpoint_file_security.os, "replace", side_effect=swap_then_replace):
                with self.assertRaisesRegex(RuntimeError, "parent directory changed"):
                    atomic_write_private_bytes(checkpoint, b"new-state")

            self.assertTrue(swapped)
            self.assertFalse(checkpoint.exists())
            self.assertEqual((displaced / "checkpoint.json").read_bytes(), b"new-state")


if __name__ == "__main__":
    unittest.main()
