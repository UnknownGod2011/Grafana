#!/usr/bin/env python3
"""Cross-process cooperative locking for local StageGuard audit JSONL files.

The lock is intentionally local-file specific. Cloud Logging has independent
provider consistency semantics and must not use this mechanism.
"""
from __future__ import annotations

import os
import stat
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


def _process_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PROCESS_LOCKS[key] = lock
        return lock


def lock_path_for(audit_path: str | Path) -> Path:
    path = Path(audit_path)
    return path.with_name(f".{path.name}.stageguard.lock")


def _same_file_identity(fd_stat: os.stat_result, path_stat: os.stat_result) -> bool:
    """Return whether an opened descriptor still names the visible filesystem object."""
    return (fd_stat.st_dev, fd_stat.st_ino) == (path_stat.st_dev, path_stat.st_ino)


def assert_open_regular_file_identity(fd: int, path: str | Path) -> os.stat_result:
    """Fail closed unless ``fd`` is the same private regular file visible at ``path``.

    Retention keeps an audit descriptor open across inventory, backup, and rewrite.
    Rechecking immediately before pathname mutation prevents a substituted path from
    becoming the target of the final ``os.replace`` even if the original descriptor
    itself remains valid. Hard-linked audit files are rejected because a second
    pathname to the same inode would permit writes or permission changes outside the
    StageGuard-owned audit path while all inode-identity checks still pass.
    """
    audit_path = Path(path)
    try:
        fd_stat = os.fstat(fd)
    except OSError as exc:
        raise RuntimeError("audit data file descriptor could not be inspected safely") from exc
    if not stat.S_ISREG(fd_stat.st_mode):
        raise RuntimeError("audit data file must be a regular file")
    if fd_stat.st_nlink != 1:
        raise RuntimeError("audit data file must not have multiple hard links")
    try:
        path_stat = os.lstat(audit_path)
    except OSError as exc:
        raise RuntimeError("audit data file path changed while in use") from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise RuntimeError("audit data file must not be a symbolic link")
    if not stat.S_ISREG(path_stat.st_mode) or path_stat.st_nlink != 1 or not _same_file_identity(fd_stat, path_stat):
        raise RuntimeError("audit data file path changed while in use")
    return fd_stat


def open_regular_audit_file(path: str | Path, flags: int, mode: int = 0o600) -> int:
    """Open the local audit data file without accepting symlink/path substitution.

    The caller receives a validated descriptor and owns closing it. ``O_TRUNC`` is
    deliberately forbidden because on platforms without ``O_NOFOLLOW`` truncation
    could mutate a substituted target before the post-open identity check runs.
    Creation and append/read opens are safe because no audit bytes are written until
    after descriptor/path identity has been verified.
    """
    audit_path = Path(path)
    if flags & getattr(os, "O_TRUNC", 0):
        raise ValueError("secure audit file open does not permit O_TRUNC")
    try:
        if audit_path.is_symlink():
            raise RuntimeError("audit data file must not be a symbolic link")
    except OSError as exc:
        raise RuntimeError("audit data file could not be inspected safely") from exc

    effective_flags = flags
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        effective_flags |= nofollow
    try:
        fd = os.open(audit_path, effective_flags, mode)
    except OSError as exc:
        raise RuntimeError("audit data file could not be opened safely") from exc

    try:
        assert_open_regular_file_identity(fd, audit_path)
        try:
            os.fchmod(fd, 0o600)
        except AttributeError:
            pass
        return fd
    except Exception:
        os.close(fd)
        raise


def _open_lock_sidecar(sidecar: Path) -> int:
    """Open one owner-only regular lock file without accepting path substitution."""
    try:
        if sidecar.is_symlink():
            raise RuntimeError("audit lock sidecar must not be a symbolic link")
    except OSError as exc:
        raise RuntimeError("audit lock sidecar could not be inspected safely") from exc

    flags = os.O_RDWR | os.O_CREAT
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    try:
        fd = os.open(sidecar, flags, 0o600)
    except OSError as exc:
        raise RuntimeError("audit lock sidecar could not be opened safely") from exc

    try:
        fd_stat = os.fstat(fd)
        if not stat.S_ISREG(fd_stat.st_mode):
            raise RuntimeError("audit lock sidecar must be a regular file")
        try:
            path_stat = os.lstat(sidecar)
        except OSError as exc:
            raise RuntimeError("audit lock sidecar path changed while opening") from exc
        if stat.S_ISLNK(path_stat.st_mode):
            raise RuntimeError("audit lock sidecar must not be a symbolic link")
        if not stat.S_ISREG(path_stat.st_mode) or not _same_file_identity(fd_stat, path_stat):
            raise RuntimeError("audit lock sidecar path changed while opening")
        try:
            os.fchmod(fd, 0o600)
        except AttributeError:
            pass
        return fd
    except Exception:
        os.close(fd)
        raise


def _lock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        return

    import fcntl
    fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl
    fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def audit_file_lock(audit_path: str | Path) -> Iterator[None]:
    """Hold an exclusive cooperative lock for one local audit file."""
    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = lock_path_for(path)
    process_lock = _process_lock(path)

    with process_lock:
        fd = _open_lock_sidecar(sidecar)
        try:
            _lock_fd(fd)
            try:
                yield
            finally:
                _unlock_fd(fd)
        finally:
            os.close(fd)
