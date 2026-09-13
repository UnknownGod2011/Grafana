from __future__ import annotations

import os
from pathlib import Path

import pytest

from audit_file_lock import audit_file_lock, lock_path_for


def test_audit_file_lock_rejects_directory_sidecar(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    sidecar = lock_path_for(audit_path)
    sidecar.mkdir()

    with pytest.raises(RuntimeError, match="regular file|opened safely"):
        with audit_file_lock(audit_path):
            raise AssertionError("unsafe sidecar unexpectedly acquired")


def test_audit_file_lock_rejects_symlink_sidecar_without_touching_target(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are unavailable on this platform")

    audit_path = tmp_path / "audit.jsonl"
    sidecar = lock_path_for(audit_path)
    target = tmp_path / "unrelated.txt"
    target.write_text("do-not-touch", encoding="utf-8")

    try:
        sidecar.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not permitted in this environment")

    with pytest.raises(RuntimeError, match="symbolic link|opened safely"):
        with audit_file_lock(audit_path):
            raise AssertionError("symlink sidecar unexpectedly acquired")

    assert target.read_text(encoding="utf-8") == "do-not-touch"


def test_audit_file_lock_still_creates_owner_only_regular_sidecar(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    sidecar = lock_path_for(audit_path)

    with audit_file_lock(audit_path):
        assert sidecar.is_file()
        assert not sidecar.is_symlink()
        if os.name != "nt":
            assert sidecar.stat().st_mode & 0o777 == 0o600
