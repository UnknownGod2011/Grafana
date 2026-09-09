#!/usr/bin/env python3
"""Cross-process cooperative locking for local StageGuard audit JSONL files.

The lock is intentionally local-file specific. Cloud Logging has independent
provider consistency semantics and must not use this mechanism.
"""
from __future__ import annotations

import os
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
        fd = os.open(sidecar, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                os.fchmod(fd, 0o600)
            except AttributeError:
                # os.fchmod is unavailable on some Windows Python builds; the
                # file is still created with the restrictive mode above where
                # the platform honors POSIX-style permission bits.
                pass
            _lock_fd(fd)
            try:
                yield
            finally:
                _unlock_fd(fd)
        finally:
            os.close(fd)
