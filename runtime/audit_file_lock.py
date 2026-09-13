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


def _open_lock_sidecar(sidecar: Path) -> int:
    """Open one owner-only regular lock file without following symlinks.

    The lock filename is derived from an operator-provided local audit path. A
    pre-created symlink must therefore never redirect StageGuard's chmod/write or
    locking operations onto an unrelated file. POSIX ``O_NOFOLLOW`` closes the
    open-time race where available; the explicit symlink and regular-file checks
    keep the contract fail-closed on platforms that do not expose that flag.
    """
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
        mode = os.fstat(fd).st_mode
        if not stat.S_ISREG(mode):
            raise RuntimeError("audit lock sidecar must be a regular file")
        try:
            os.fchmod(fd, 0o600)
        except AttributeError:
            # os.fchmod is unavailable on some Windows Python builds; the file is
            # still created with the restrictive mode above where supported.
            pass
        return fd
    except Exception:
        os.close(fd)
        raise


def _lock_fd(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        # msvcrt.locking locks bytes from the current file position. Ensure the
        # lock file always contains one byte and lock that byte exclusively.
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
    """Hold an exclusive cooperative lock for one local audit file.

    All StageGuard local writers/readers that participate in retention use this
    same sidecar lock. The in-process RLock also serializes threads because POSIX
    flock semantics alone are not a substitute for thread coordination.
    """
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
