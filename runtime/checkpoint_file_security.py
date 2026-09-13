#!/usr/bin/env python3
"""Filesystem integrity primitives for StageGuard local checkpoint state.

This module is intentionally separate from checkpoint serialization. It provides
small descriptor-bound operations that reject symbolic links, hard-link aliases,
and post-open pathname substitution before local state is trusted.
"""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def assert_private_regular_file_identity(fd: int, path: str | Path) -> os.stat_result:
    """Require ``fd`` to be the exact single-link regular file visible at ``path``."""
    state_path = Path(path)
    try:
        fd_stat = os.fstat(fd)
    except OSError as exc:
        raise RuntimeError("checkpoint file descriptor could not be inspected safely") from exc
    if not stat.S_ISREG(fd_stat.st_mode):
        raise RuntimeError("checkpoint file must be a regular file")
    if fd_stat.st_nlink != 1:
        raise RuntimeError("checkpoint file must not have multiple hard links")
    try:
        path_stat = os.lstat(state_path)
    except OSError as exc:
        raise RuntimeError("checkpoint file path changed while in use") from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise RuntimeError("checkpoint file must not be a symbolic link")
    if (
        not stat.S_ISREG(path_stat.st_mode)
        or path_stat.st_nlink != 1
        or not _same_identity(fd_stat, path_stat)
    ):
        raise RuntimeError("checkpoint file path changed while in use")
    return fd_stat


def open_private_regular_file(path: str | Path, flags: int, mode: int = 0o600) -> int:
    """Open an existing/created checkpoint file without following symlinks.

    ``O_TRUNC`` is prohibited because truncation could mutate an attacker-selected
    target before post-open validation on platforms that lack ``O_NOFOLLOW``.
    A genuinely absent path preserves ``FileNotFoundError`` so callers can retain
    normal empty-store semantics without a check/open race.
    """
    state_path = Path(path)
    if flags & getattr(os, "O_TRUNC", 0):
        raise ValueError("secure checkpoint open does not permit O_TRUNC")
    try:
        if state_path.is_symlink():
            raise RuntimeError("checkpoint file must not be a symbolic link")
    except OSError as exc:
        raise RuntimeError("checkpoint file could not be inspected safely") from exc

    effective_flags = flags | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(state_path, effective_flags, mode)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise RuntimeError("checkpoint file could not be opened safely") from exc
    try:
        assert_private_regular_file_identity(fd, state_path)
        try:
            os.fchmod(fd, 0o600)
        except AttributeError:
            pass
        return fd
    except Exception:
        os.close(fd)
        raise


def read_private_bytes(path: str | Path, *, max_bytes: int) -> bytes:
    """Read bounded local state while detecting path replacement during the read."""
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    fd = open_private_regular_file(path, os.O_RDONLY)
    try:
        assert_private_regular_file_identity(fd, path)
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise ValueError("checkpoint file exceeds size limit")
        assert_private_regular_file_identity(fd, path)
        return raw
    finally:
        os.close(fd)


def atomic_write_private_bytes(path: str | Path, data: bytes) -> None:
    """Atomically replace local state with an owner-only regular file.

    The temporary file is created in the destination directory, written and fsynced
    through its descriptor, validated as single-link regular state, and then renamed.
    No pathname chmod is performed after replacement, avoiding a chmod race against
    a substituted destination path.
    """
    if not isinstance(data, bytes):
        raise TypeError("checkpoint data must be bytes")
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".checkpoint-", dir=state_path.parent)
    tmp_path = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise OSError("checkpoint write made no progress")
            offset += written
        os.fsync(fd)
        if not hasattr(os, "fchmod"):
            os.chmod(tmp_path, 0o600)
        assert_private_regular_file_identity(fd, tmp_path)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, state_path)
        final_fd = open_private_regular_file(state_path, os.O_RDONLY)
        try:
            assert_private_regular_file_identity(final_fd, state_path)
        finally:
            os.close(final_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            if tmp_path.exists() or tmp_path.is_symlink():
                tmp_path.unlink()
        except OSError:
            pass
