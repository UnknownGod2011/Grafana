#!/usr/bin/env python3
"""Deterministic tamper-evident hash chaining for StageGuard audit events.

This module is credential-free and provider-neutral. It does not persist secrets,
provider identifiers, endpoints, or response bodies. Callers can persist only the
64-character chain head alongside an authenticated checkpoint, then verify that a
replayed durable audit sequence is complete, ordered, and unmodified.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from typing import Iterable, Protocol

from incident_service import AuditEvent

GENESIS_SHA256 = "0" * 64


class AuditSink(Protocol):
    def append(self, event: AuditEvent) -> None: ...


def _valid_digest(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def canonical_audit_event(event: AuditEvent) -> bytes:
    """Return a stable UTF-8 representation suitable for integrity hashing."""
    if not isinstance(event.sequence, int) or isinstance(event.sequence, bool) or event.sequence < 1:
        raise ValueError("audit sequence must be a positive integer")
    if not isinstance(event.timestamp_unix_ms, int) or isinstance(event.timestamp_unix_ms, bool) or event.timestamp_unix_ms < 0:
        raise ValueError("audit timestamp must be a non-negative integer")
    if not isinstance(event.incident_id, str) or not event.incident_id:
        raise ValueError("audit incident_id must be a non-empty string")
    if not isinstance(event.event_type, str) or not event.event_type:
        raise ValueError("audit event_type must be a non-empty string")
    if not isinstance(event.actor, str) or not event.actor:
        raise ValueError("audit actor must be a non-empty string")
    if not isinstance(event.payload, dict):
        raise ValueError("audit payload must be a dictionary")
    try:
        return json.dumps(
            asdict(event), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("audit event is not canonically serializable") from exc


def extend_audit_chain(previous_sha256: str, event: AuditEvent) -> str:
    """Hash one event onto a prior chain head using domain-separated SHA-256."""
    if not _valid_digest(previous_sha256):
        raise ValueError("previous audit-chain digest must be lowercase SHA-256 hex")
    digest = hashlib.sha256()
    digest.update(b"stageguard.audit-chain.v1\x00")
    digest.update(bytes.fromhex(previous_sha256))
    digest.update(b"\x00")
    digest.update(canonical_audit_event(event))
    return digest.hexdigest()


@dataclass(frozen=True)
class AuditChainCheckpoint:
    """Minimal restart state safe to embed in authenticated durable checkpoint state."""

    sequence: int
    head_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValueError("audit-chain sequence must be a non-negative integer")
        if not _valid_digest(self.head_sha256):
            raise ValueError("audit-chain head must be lowercase SHA-256 hex")
        if self.sequence == 0 and self.head_sha256 != GENESIS_SHA256:
            raise ValueError("empty audit chain must use the genesis digest")


class AuditChain:
    """Thread-safe strict sequence chain supporting safe restart continuation."""

    def __init__(self, checkpoint: AuditChainCheckpoint | None = None) -> None:
        checkpoint = checkpoint or AuditChainCheckpoint(0, GENESIS_SHA256)
        self._sequence = checkpoint.sequence
        self._head = checkpoint.head_sha256
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> AuditChainCheckpoint:
        with self._lock:
            expected = self._sequence + 1
            if event.sequence != expected:
                raise ValueError("audit event sequence is not contiguous")
            self._head = extend_audit_chain(self._head, event)
            self._sequence = event.sequence
            return AuditChainCheckpoint(self._sequence, self._head)

    def checkpoint(self) -> AuditChainCheckpoint:
        with self._lock:
            return AuditChainCheckpoint(self._sequence, self._head)


def verify_audit_chain(
    events: Iterable[AuditEvent],
    expected: AuditChainCheckpoint,
    *,
    initial: AuditChainCheckpoint | None = None,
) -> AuditChainCheckpoint:
    """Verify deletion/reordering/mutation against an authenticated expected head.

    ``initial`` supports bounded restart verification from a previously trusted
    chain checkpoint instead of requiring unbounded historical replay.
    """
    chain = AuditChain(initial)
    for event in events:
        chain.append(event)
    actual = chain.checkpoint()
    if actual != expected:
        raise ValueError("audit chain integrity verification failed")
    return actual


class ChainedAuditSink:
    """Audit-sink decorator that advances integrity state only after sink success."""

    def __init__(self, inner: AuditSink, *, checkpoint: AuditChainCheckpoint | None = None) -> None:
        self._inner = inner
        self._chain = AuditChain(checkpoint)
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            # Validate and calculate before I/O, but do not publish the new head
            # until the underlying append succeeds.
            current = self._chain.checkpoint()
            if event.sequence != current.sequence + 1:
                raise ValueError("audit event sequence is not contiguous")
            next_head = extend_audit_chain(current.head_sha256, event)
            self._inner.append(event)
            self._chain = AuditChain(AuditChainCheckpoint(event.sequence, next_head))

    def checkpoint(self) -> AuditChainCheckpoint:
        with self._lock:
            return self._chain.checkpoint()
