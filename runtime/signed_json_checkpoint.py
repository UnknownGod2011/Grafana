#!/usr/bin/env python3
"""Authenticated atomic local checkpoint storage for StageGuard."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from incident_checkpoint import IncidentCheckpoint, _decode, _encode


class SignedJsonCheckpointStore:
    """HMAC-authenticated local checkpoint store with owner-only atomic writes.

    This is the local counterpart to the authenticated GCS store. It deliberately
    requires a signing key and rejects unsigned, wrongly signed, or tampered
    checkpoint documents on load so retention tooling can consume runtime-created
    local checkpoints without an out-of-band signing step.
    """

    supports_execution_phase = True

    def __init__(self, path: str | Path, signing_key: bytes) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("checkpoint signing key must be at least 32 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._signing_key = signing_key

    def load(self) -> IncidentCheckpoint | None:
        if not self.path.exists():
            return None
        if self.path.is_symlink():
            raise ValueError("incident checkpoint path must not be a symlink")
        return _decode(
            self.path.read_bytes(),
            signing_key=self._signing_key,
            require_signature=True,
        )

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        encoded = _encode(checkpoint, signing_key=self._signing_key)
        fd, tmp_name = tempfile.mkstemp(prefix=".checkpoint-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
