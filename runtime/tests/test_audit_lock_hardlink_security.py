#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from audit_file_lock import audit_file_lock, lock_path_for


class AuditLockHardlinkSecurityTests(unittest.TestCase):
    def _hardlink_or_skip(self, source: Path, alias: Path) -> None:
        try:
            os.link(source, alias)
        except (AttributeError, NotImplementedError, OSError) as exc:
            self.skipTest(f"hard links are unavailable on this filesystem: {exc}")

    def test_hardlinked_sidecar_is_rejected_without_mutating_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            sidecar = lock_path_for(audit_path)
            peer = Path(tmp) / "unrelated.txt"
            peer.write_text("do-not-touch", encoding="utf-8")
            try:
                os.chmod(peer, 0o644)
            except OSError:
                pass
            before_mode = stat.S_IMODE(peer.stat().st_mode)
            self._hardlink_or_skip(peer, sidecar)

            with self.assertRaisesRegex(RuntimeError, "multiple hard links"):
                with audit_file_lock(audit_path):
                    self.fail("hard-linked lock sidecar must never be acquired")

            self.assertEqual(peer.read_text(encoding="utf-8"), "do-not-touch")
            self.assertEqual(stat.S_IMODE(peer.stat().st_mode), before_mode)
            self.assertEqual(peer.stat().st_nlink, 2)

    def test_normal_sidecar_remains_private_single_link_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            sidecar = lock_path_for(audit_path)

            with audit_file_lock(audit_path):
                sidecar_stat = os.lstat(sidecar)
                self.assertTrue(stat.S_ISREG(sidecar_stat.st_mode))
                self.assertEqual(sidecar_stat.st_nlink, 1)
                if os.name != "nt":
                    self.assertEqual(stat.S_IMODE(sidecar_stat.st_mode), 0o600)

            self.assertTrue(sidecar.exists())


if __name__ == "__main__":
    unittest.main()
