#!/usr/bin/env python3
"""Filesystem integrity primitives for StageGuard local checkpoint state.

This module is intentionally separate from checkpoint serialization. It provides
small descriptor-bound operations that reject symbolic links, hard-link aliases,
and post-open pathname substitution before local state is trusted.
"""
from __future__ import annotations

import os
import secrets
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


def _assert_directory_identity(fd: int, path: Path) -> os.stat_result:
    """Require ``fd`` to be the exact directory still visible at ``path``."""
    try:
        fd_stat = os.fstat(fd)
    except OSError as exc:
        raise RuntimeError("checkpoint directory descriptor could not be inspected safely") from exc
    if not stat.S_ISDIR(fd_stat.st_mode):
        raise RuntimeError("checkpoint parent must be a directory")
    try:
        path_stat = os.lstat(path)
    except OSError as exc:
        raise RuntimeError("checkpoint parent directory changed while in use") from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise RuntimeError("checkpoint parent directory must not be a symbolic link")
    if not stat.S_ISDIR(path_stat.st_mode) or not _same_identity(fd_stat, path_stat):
        raise RuntimeError("checkpoint parent directory changed while in use")
    return fd_stat


def _open_parent_directory(path: Path) -> int:
    """Open and validate the parent directory without following its final symlink."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError("checkpoint parent directory could not be opened safely") from exc
    try:
        _assert_directory_identity(fd, path)
        return fd
    except Exception:
        os.close(fd)
        raise


def _supports_directory_relative_atomic_write() -> bool:
    supports_dir_fd = getattr(os, "supports_dir_fd", set())
    # CPython does not list os.replace separately even where it exposes the same
    # dir-fd-capable renameat implementation as os.rename. POSIX + dir-fd open/
    # rename therefore describes the production capability more accurately.
    return os.name == "posix" and os.open in supports_dir_fd and os.rename in supports_dir_fd


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


def _write_all_and_sync(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise OSError("checkpoint write made no progress")
        offset += written
    os.fsync(fd)


def _atomic_write_via_parent_fd(state_path: Path, data: bytes, parent_fd: int) -> None:
    """Create and replace checkpoint state relative to one validated directory fd."""
    tmp_name = f".checkpoint-{secrets.token_hex(12)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    created = False
    try:
        fd = os.open(tmp_name, flags, 0o600, dir_fd=parent_fd)
        created = True
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        _write_all_and_sync(fd, data)
        fd_stat = os.fstat(fd)
        if not stat.S_ISREG(fd_stat.st_mode) or fd_stat.st_nlink != 1:
            raise RuntimeError("checkpoint temporary file is not a private regular file")
        _assert_directory_identity(parent_fd, state_path.parent)
        os.close(fd)
        fd = -1
        os.replace(tmp_name, state_path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        created = False
        _assert_directory_identity(parent_fd, state_path.parent)
        final_fd = os.open(
            state_path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            final_stat = os.fstat(final_fd)
            if not stat.S_ISREG(final_stat.st_mode) or final_stat.st_nlink != 1:
                raise RuntimeError("checkpoint file is not a private regular file")
            if stat.S_IMODE(final_stat.st_mode) != 0o600:
                raise RuntimeError("checkpoint file permissions changed unexpectedly")
        finally:
            os.close(final_fd)
        os.fsync(parent_fd)
        _assert_directory_identity(parent_fd, state_path.parent)
    finally:
        if fd >= 0:
            os.close(fd)
        if created:
            try:
                os.unlink(tmp_name, dir_fd=parent_fd)
            except OSError:
                pass


def _atomic_write_portable_fallback(state_path: Path, data: bytes, parent_fd: int) -> None:
    """Fallback for platforms lacking dir-fd replace support, with identity checks."""
    _assert_directory_identity(parent_fd, state_path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=".checkpoint-", dir=state_path.parent)
    tmp_path = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        _write_all_and_sync(fd, data)
        if not hasattr(os, "fchmod"):
            os.chmod(tmp_path, 0o600)
        assert_private_regular_file_identity(fd, tmp_path)
        _assert_directory_identity(parent_fd, state_path.parent)
        os.close(fd)
        fd = -1
        os.replace(tmp_path, state_path)
        _assert_directory_identity(parent_fd, state_path.parent)
        final_fd = open_private_regular_file(state_path, os.O_RDONLY)
        try:
            assert_private_regular_file_identity(final_fd, state_path)
        finally:
            os.close(final_fd)
        _assert_directory_identity(parent_fd, state_path.parent)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            if tmp_path.exists() or tmp_path.is_symlink():
                tmp_path.unlink()
        except OSError:
            pass


def atomic_write_private_bytes(path: str | Path, data: bytes) -> None:
    """Atomically replace local state with an owner-only regular file.

    On platforms with directory-relative file operations (including StageGuard's
    Linux/Cloud Run production target), temporary creation and final replacement
    are anchored to one validated parent-directory descriptor. This prevents a
    parent pathname swap from redirecting either operation. Other platforms keep
    the portable path implementation but validate the parent identity before and
    after each pathname-sensitive phase.
    """
    if not isinstance(data, bytes):
        raise TypeError("checkpoint data must be bytes")
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    parent_fd = _open_parent_directory(state_path.parent)
    try:
        if _supports_directory_relative_atomic_write():
            _atomic_write_via_parent_fd(state_path, data, parent_fd)
        else:
            _atomic_write_portable_fallback(state_path, data, parent_fd)
    finally:
        os.close(parent_fd)
