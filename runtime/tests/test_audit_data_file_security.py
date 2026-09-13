from __future__ import annotations

import os
import stat
from types import SimpleNamespace

import pytest

import audit_file_lock as audit_lock_module
from anchored_incident_service import AnchoredJsonlAuditLog
from audit_file_lock import open_regular_audit_file
from incident_service import AuditEvent


def _event(sequence: int = 1) -> AuditEvent:
    return AuditEvent(
        sequence=sequence,
        timestamp_unix_ms=sequence,
        incident_id="incident-data-file",
        event_type="test",
        actor="test",
        payload={"sequence": sequence},
    )


def _symlink_or_skip(link, target) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable on this platform: {exc}")


def test_secure_audit_open_rejects_symlink_without_mutating_target(tmp_path):
    target = tmp_path / "unrelated.txt"
    target.write_text("sentinel", encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"
    _symlink_or_skip(audit_path, target)

    with pytest.raises(RuntimeError, match="must not be a symbolic link"):
        open_regular_audit_file(audit_path, os.O_WRONLY | os.O_APPEND)

    assert target.read_text(encoding="utf-8") == "sentinel"


def test_secure_audit_open_rejects_post_open_identity_change(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_bytes(b"")
    actual = os.lstat(audit_path)
    forged = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600,
        st_dev=actual.st_dev,
        st_ino=actual.st_ino + 1,
    )
    monkeypatch.setattr(audit_lock_module.os, "lstat", lambda path: forged)

    with pytest.raises(RuntimeError, match="path changed while opening"):
        open_regular_audit_file(audit_path, os.O_RDONLY)


def test_secure_audit_open_forbids_truncation_before_validation(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="does not permit O_TRUNC"):
        open_regular_audit_file(audit_path, os.O_WRONLY | os.O_TRUNC)

    assert audit_path.read_text(encoding="utf-8") == "preserve"


def test_anchored_audit_constructor_rejects_symlink_without_touching_target(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_text("sentinel\n", encoding="utf-8")
    audit_path = tmp_path / "audit.jsonl"
    _symlink_or_skip(audit_path, target)

    with pytest.raises(RuntimeError, match="must not be a symbolic link"):
        AnchoredJsonlAuditLog(audit_path)

    assert target.read_text(encoding="utf-8") == "sentinel\n"


def test_anchored_audit_append_rejects_path_replaced_by_symlink(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(audit_path)
    audit.append(_event())
    original = audit_path.read_bytes()
    audit_path.unlink()

    target = tmp_path / "unrelated.jsonl"
    target.write_text("sentinel\n", encoding="utf-8")
    _symlink_or_skip(audit_path, target)

    with pytest.raises(RuntimeError, match="must not be a symbolic link"):
        audit.append(_event(2))

    assert target.read_text(encoding="utf-8") == "sentinel\n"
    assert original


def test_anchored_audit_read_rejects_path_replaced_by_symlink(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(audit_path)
    audit.append(_event())
    audit_path.unlink()

    target = tmp_path / "unrelated.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    _symlink_or_skip(audit_path, target)

    with pytest.raises(RuntimeError, match="local audit log could not be read safely"):
        audit.read(incident_id="incident-data-file")


def test_anchored_audit_normal_round_trip_uses_regular_owner_only_file(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = AnchoredJsonlAuditLog(audit_path)
    event = _event()
    audit.append(event)

    assert audit.read(incident_id=event.incident_id) == [event]
    assert audit.read_candidates(
        incident_id=event.incident_id,
        after_sequence=0,
        through_sequence=1,
    ) == [event]
    visible = os.lstat(audit_path)
    assert stat.S_ISREG(visible.st_mode)
    if os.name != "nt":
        assert stat.S_IMODE(visible.st_mode) == 0o600
