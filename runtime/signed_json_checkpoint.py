#!/usr/bin/env python3
"""Authenticated atomic local checkpoint storage for StageGuard."""
from __future__ import annotations

from pathlib import Path

from checkpoint_file_security import atomic_write_private_bytes, read_private_bytes
from incident_checkpoint import IncidentCheckpoint, _MAX_BYTES, _decode, _encode


class SignedJsonCheckpointStore:
    """HMAC-authenticated local checkpoint store with hardened filesystem access.

    This is the local counterpart to the authenticated GCS store. It deliberately
    requires a signing key and rejects unsigned, wrongly signed, or tampered
    checkpoint documents on load. Filesystem access is delegated to the same
    descriptor-bound primitive used by ``JsonCheckpointStore`` so symlinks,
    hard-link aliases, and post-open path substitution fail closed.
    """

    supports_execution_phase = True

    def __init__(self, path: str | Path, signing_key: bytes) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("checkpoint signing key must be at least 32 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._signing_key = signing_key

    def load(self) -> IncidentCheckpoint | None:
        try:
            raw = read_private_bytes(self.path, max_bytes=_MAX_BYTES)
        except FileNotFoundError:
            return None
        return _decode(
            raw,
            signing_key=self._signing_key,
            require_signature=True,
        )

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        atomic_write_private_bytes(
            self.path,
            _encode(checkpoint, signing_key=self._signing_key),
        )
