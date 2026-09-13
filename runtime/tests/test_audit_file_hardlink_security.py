#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from audit_file_lock import assert_open_regular_file_identity, open_regular_audit_file


class AuditFileHardLinkSecurityTests(unittest.TestCase):
    def _make_hard_link(self, source: Path, alias: Path) -> None:
        try:
            os.link(source, alias)
        except (AttributeError, NotImplementedError, OSError) as exc:
            self.skipTest(f"hard links are unavailable in this test environment: {exc}")

    def test_secure_open_rejects_existing_hard_link_without_mutating_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            peer = root / "unrelated.txt"
            audit = root / "audit.jsonl"
            original = b"do-not-touch\n"
            peer.write_bytes(original)
            self._make_hard_link(peer, audit)

            with self.assertRaisesRegex(RuntimeError, "multiple hard links"):
                open_regular_audit_file(audit, os.O_WRONLY | os.O_APPEND)

            self.assertEqual(peer.read_bytes(), original)
            self.assertEqual(audit.read_bytes(), original)

    def test_identity_recheck_rejects_descriptor_after_second_hard_link_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.jsonl"
            alias = root / "audit-alias.jsonl"
            audit.write_text("{}\n", encoding="utf-8")

            fd = open_regular_audit_file(audit, os.O_RDONLY)
            try:
                self._make_hard_link(audit, alias)
                with self.assertRaisesRegex(RuntimeError, "multiple hard links"):
                    assert_open_regular_file_identity(fd, audit)
            finally:
                os.close(fd)

    def test_single_link_regular_file_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            fd = open_regular_audit_file(
                audit,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            )
            try:
                stat_result = assert_open_regular_file_identity(fd, audit)
                self.assertEqual(stat_result.st_nlink, 1)
                os.write(fd, b"{}\n")
                os.fsync(fd)
            finally:
                os.close(fd)

            self.assertEqual(audit.read_text(encoding="utf-8"), "{}\n")


if __name__ == "__main__":
    unittest.main()
