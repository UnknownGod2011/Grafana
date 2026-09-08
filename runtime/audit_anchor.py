#!/usr/bin/env python3
"""Authenticated rolling anchors for bounded StageGuard audit verification.

An anchor is not a new source of truth. It is a previously verified audit-chain
checkpoint that must itself be persisted inside StageGuard's authenticated durable
checkpoint envelope before it can be trusted on restart. Once authenticated, old
audit records at or before the anchor can be compacted or age out while the suffix
remains tamper-evident and multi-writer branch selection remains fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from audit_integrity import AuditChainCheckpoint, select_committed_audit_lineage
from incident_service import AuditEvent

DEFAULT_ANCHOR_INTERVAL = 1024
MAX_VERIFICATION_SUFFIX_EVENTS = 2048


@dataclass(frozen=True)
class AuditAnchor:
    """A chain checkpoint eligible to be embedded in authenticated lifecycle state."""

    sequence: int
    head_sha256: str

    def __post_init__(self) -> None:
        AuditChainCheckpoint(self.sequence, self.head_sha256)

    def as_chain_checkpoint(self) -> AuditChainCheckpoint:
        return AuditChainCheckpoint(self.sequence, self.head_sha256)

    @classmethod
    def genesis(cls) -> "AuditAnchor":
        checkpoint = AuditChainCheckpoint(0, "0" * 64)
        return cls(checkpoint.sequence, checkpoint.head_sha256)

    @classmethod
    def from_chain_checkpoint(cls, checkpoint: AuditChainCheckpoint) -> "AuditAnchor":
        if not isinstance(checkpoint, AuditChainCheckpoint):
            raise TypeError("anchor source must be an AuditChainCheckpoint")
        return cls(checkpoint.sequence, checkpoint.head_sha256)


def roll_audit_anchor(
    previous: AuditAnchor,
    current: AuditChainCheckpoint,
    *,
    interval: int = DEFAULT_ANCHOR_INTERVAL,
) -> AuditAnchor:
    """Promote a trusted anchor only after a bounded amount of verified progress.

    Callers MUST authenticate the returned anchor in durable checkpoint state before
    treating it as a restart trust root. This helper never writes or signs state.
    """
    if not isinstance(previous, AuditAnchor):
        raise TypeError("previous anchor must be an AuditAnchor")
    if not isinstance(current, AuditChainCheckpoint):
        raise TypeError("current chain state must be an AuditChainCheckpoint")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise ValueError("anchor interval must be a positive integer")
    if current.sequence < previous.sequence:
        raise ValueError("audit chain cannot roll behind the authenticated anchor")
    if current.sequence == previous.sequence and current.head_sha256 != previous.head_sha256:
        raise ValueError("current chain conflicts with the authenticated anchor")
    if current.sequence - previous.sequence < interval:
        return previous
    return AuditAnchor.from_chain_checkpoint(current)


def select_anchored_committed_lineage(
    events: Iterable[AuditEvent],
    *,
    anchor: AuditAnchor,
    expected: AuditChainCheckpoint,
    max_suffix_events: int = MAX_VERIFICATION_SUFFIX_EVENTS,
    max_candidates_per_sequence: int = 32,
    max_states: int = 128,
) -> list[AuditEvent]:
    """Select the authenticated winner using only the post-anchor audit suffix.

    Records at or before ``anchor.sequence`` are intentionally unnecessary. This is
    the compaction boundary. Records after ``expected.sequence`` are unauthenticated
    append-before-CAS residue and are ignored by the underlying lineage selector.
    """
    if not isinstance(anchor, AuditAnchor):
        raise TypeError("anchor must be an AuditAnchor")
    if not isinstance(expected, AuditChainCheckpoint):
        raise TypeError("expected must be an AuditChainCheckpoint")
    if not isinstance(max_suffix_events, int) or isinstance(max_suffix_events, bool) or max_suffix_events < 0:
        raise ValueError("max_suffix_events must be a non-negative integer")
    initial = anchor.as_chain_checkpoint()
    if expected.sequence < initial.sequence:
        raise ValueError("expected audit checkpoint precedes authenticated anchor")
    suffix_span = expected.sequence - initial.sequence
    if suffix_span > max_suffix_events:
        raise ValueError("audit suffix exceeds authenticated verification bound")
    return select_committed_audit_lineage(
        events,
        expected,
        initial=initial,
        max_candidates_per_sequence=max_candidates_per_sequence,
        max_states=max_states,
    )
