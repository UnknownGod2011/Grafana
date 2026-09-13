import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import incident_service
from incident_service import AuditEvent, JsonlAuditLog


class JsonlAuditFileSecurityTests(unittest.TestCase):
    def _event(self, sequence: int = 1) -> AuditEvent:
        return AuditEvent(
            sequence=sequence,
            timestamp_unix_ms=1_700_000_000_000 + sequence,
            incident_id="incident-1",
            event_type="investigation_completed",
            actor="stageguard",
            payload={"revision": "abc123"},
        )

    def test_constructor_rejects_symlink_without_mutating_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "outside.jsonl"
            target.write_bytes(b"outside\n")
            audit = root / "audit.jsonl"
            try:
                audit.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable on this platform")

            with self.assertRaises(RuntimeError):
                JsonlAuditLog(audit)

            self.assertEqual(target.read_bytes(), b"outside\n")

    def test_constructor_rejects_hard_link_without_mutating_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            peer = root / "peer.jsonl"
            peer.write_bytes(b"peer\n")
            audit = root / "audit.jsonl"
            try:
                os.link(peer, audit)
            except (OSError, NotImplementedError):
                self.skipTest("hard links are unavailable on this platform")

            with self.assertRaises(RuntimeError):
                JsonlAuditLog(audit)

            self.assertEqual(peer.read_bytes(), b"peer\n")

    def test_append_rejects_path_swap_after_secure_open_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.jsonl"
            log = JsonlAuditLog(audit)
            original_bytes = audit.read_bytes()
            displaced = root / "audit.original.jsonl"
            substitute = b"substitute\n"
            real_open = incident_service.open_regular_audit_file
            swapped = False

            def swap_after_open(path, flags, mode=0o600):
                nonlocal swapped
                fd = real_open(path, flags, mode)
                if not swapped and flags & os.O_WRONLY and not flags & os.O_CREAT:
                    os.replace(audit, displaced)
                    audit.write_bytes(substitute)
                    swapped = True
                return fd

            with patch.object(incident_service, "open_regular_audit_file", side_effect=swap_after_open):
                with self.assertRaises(RuntimeError):
                    log.append(self._event())

            self.assertTrue(swapped)
            self.assertEqual(displaced.read_bytes(), original_bytes)
            self.assertEqual(audit.read_bytes(), substitute)

    def test_read_rejects_path_swap_after_secure_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = root / "audit.jsonl"
            log = JsonlAuditLog(audit)
            log.append(self._event())
            displaced = root / "audit.original.jsonl"
            substitute = b'{"incident_id":"attacker"}\n'
            real_open = incident_service.open_regular_audit_file
            swapped = False

            def swap_after_open(path, flags, mode=0o600):
                nonlocal swapped
                fd = real_open(path, flags, mode)
                if not swapped and flags & os.O_RDONLY == os.O_RDONLY and not flags & os.O_WRONLY:
                    os.replace(audit, displaced)
                    audit.write_bytes(substitute)
                    swapped = True
                return fd

            with patch.object(incident_service, "open_regular_audit_file", side_effect=swap_after_open):
                with self.assertRaises(RuntimeError):
                    log.read(incident_id="incident-1")

            self.assertTrue(swapped)
            self.assertEqual(audit.read_bytes(), substitute)
            self.assertIn(b'"incident_id":"incident-1"', displaced.read_bytes())

    def test_normal_round_trip_and_candidate_read_remain_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            log = JsonlAuditLog(audit)
            first = self._event(1)
            second = self._event(2)
            log.append(first)
            log.append(second)

            self.assertEqual(log.read(incident_id="incident-1", after_sequence=0, limit=2), [first, second])
            self.assertEqual(
                log.read_candidates(incident_id="incident-1", through_sequence=2),
                [first, second],
            )
            if os.name != "nt":
                self.assertEqual(audit.stat().st_mode & 0o777, 0o600)
            self.assertEqual(audit.stat().st_nlink, 1)


if __name__ == "__main__":
    unittest.main()
