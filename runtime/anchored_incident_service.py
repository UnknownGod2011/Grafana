#!/usr/bin/env python3
"""Anchor-aware StageGuard incident service and local audit reader.

This module is intentionally layered on the stable IncidentService API so audit
anchor rollout can be exercised independently before it becomes the default
bootstrap composition.
"""
from __future__ import annotations

import json

from audit_anchor import AuditAnchor, DEFAULT_ANCHOR_INTERVAL, roll_audit_anchor, select_anchored_committed_lineage
from audit_file_lock import audit_file_lock
from audit_integrity import AuditChain, AuditChainCheckpoint
from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
from incident_service import (
    _MAX_AUDIT_LINEAGE_READ_EVENTS,
    AuditEvent,
    IncidentService,
    IncidentSnapshot,
    JsonlAuditLog,
)


class AnchoredJsonlAuditLog(JsonlAuditLog):
    """Lock-coordinated JSONL sink/reader with anchored candidate bounds."""

    def append(self, event: AuditEvent) -> None:
        with audit_file_lock(self.path):
            super().append(event)

    def read(self, *, incident_id: str, after_sequence: int = 0, limit: int = 50) -> list[AuditEvent]:
        with audit_file_lock(self.path):
            return super().read(incident_id=incident_id, after_sequence=after_sequence, limit=limit)

    def read_candidates(
        self,
        *,
        incident_id: str,
        through_sequence: int,
        after_sequence: int = 0,
        limit: int = JsonlAuditLog.MAX_LINEAGE_READ_RESULTS,
    ) -> list[AuditEvent]:
        if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
            raise ValueError("after_sequence must be a non-negative integer")
        if not isinstance(through_sequence, int) or isinstance(through_sequence, bool) or through_sequence < 0:
            raise ValueError("through_sequence must be a non-negative integer")
        if after_sequence > through_sequence:
            raise ValueError("after_sequence cannot exceed through_sequence")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= self.MAX_LINEAGE_READ_RESULTS:
            raise ValueError(f"limit must be between 1 and {self.MAX_LINEAGE_READ_RESULTS}")
        if after_sequence == through_sequence:
            return []

        candidates: list[AuditEvent] = []
        try:
            with audit_file_lock(self.path):
                with self.path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        event = AuditEvent(**json.loads(line))
                        if event.incident_id != incident_id:
                            continue
                        if event.sequence < 1:
                            raise ValueError("audit candidate sequence must be positive")
                        if event.sequence <= after_sequence or event.sequence > through_sequence:
                            continue
                        candidates.append(event)
                        if len(candidates) > limit:
                            raise ValueError("audit candidate read exceeded the safe result bound")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("local audit candidates could not be read safely") from exc
        return candidates


class AnchoredIncidentService(IncidentService):
    """IncidentService variant that persists and consumes authenticated audit anchors."""

    def __init__(self, *args, audit_anchor_interval: int = DEFAULT_ANCHOR_INTERVAL, **kwargs) -> None:
        if (
            not isinstance(audit_anchor_interval, int)
            or isinstance(audit_anchor_interval, bool)
            or audit_anchor_interval < 1
        ):
            raise ValueError("audit_anchor_interval must be a positive integer")
        self._audit_anchor_interval = audit_anchor_interval
        self._audit_anchor = AuditAnchor.genesis()
        self._audit_anchor_authenticated = False
        super().__init__(*args, **kwargs)

    def _read_anchored_candidates(
        self,
        incident_id: str,
        *,
        anchor_sequence: int,
        through_sequence: int,
    ) -> list[AuditEvent]:
        if self._audit_reader is None:
            raise RuntimeError("durable audit reader is required for anchored integrity verification")
        reader = getattr(self._audit_reader, "read_candidates", None)
        if not callable(reader):
            raise RuntimeError("durable audit reader does not support anchored candidate enumeration")
        try:
            candidates = reader(
                incident_id=incident_id,
                after_sequence=anchor_sequence,
                through_sequence=through_sequence,
                limit=_MAX_AUDIT_LINEAGE_READ_EVENTS,
            )
        except TypeError as exc:
            raise RuntimeError("durable audit reader does not support an anchored lower bound") from exc
        if not isinstance(candidates, list):
            raise RuntimeError("durable audit candidate reader returned an invalid result")
        return candidates

    def _restore_audit_integrity(self, checkpoint: IncidentCheckpoint) -> None:
        anchor_bound = (
            checkpoint.audit_anchor_sequence is not None
            and checkpoint.audit_anchor_head_sha256 is not None
        )
        if not anchor_bound:
            self._audit_anchor = AuditAnchor.genesis()
            self._audit_anchor_authenticated = False
            super()._restore_audit_integrity(checkpoint)
            return

        self._committed_audit_history = []
        if checkpoint.audit_chain_sequence is None or checkpoint.audit_chain_head_sha256 is None:
            self._audit_integrity_state = "failed"
            self._audit_chain = None
            return
        if self._audit_reader is None:
            self._audit_integrity_state = "failed"
            self._audit_chain = None
            return

        anchor = AuditAnchor(checkpoint.audit_anchor_sequence, checkpoint.audit_anchor_head_sha256)
        expected = AuditChainCheckpoint(checkpoint.audit_chain_sequence, checkpoint.audit_chain_head_sha256)
        try:
            candidates = self._read_anchored_candidates(
                checkpoint.incident_id,
                anchor_sequence=anchor.sequence,
                through_sequence=expected.sequence,
            )
            committed = select_anchored_committed_lineage(
                candidates,
                anchor=anchor,
                expected=expected,
            )
        except Exception:
            self._audit_integrity_state = "failed"
            self._audit_chain = None
            self._committed_audit_history = []
            return

        self._audit_anchor = anchor
        self._audit_anchor_authenticated = True
        self._audit_chain = AuditChain(expected)
        self._committed_audit_history = committed
        self._audit_integrity_state = "verified"

    def _proposed_anchor(self) -> AuditAnchor | None:
        if self._audit_chain is None or self._audit_integrity_state == "failed":
            return self._audit_anchor if self._audit_anchor_authenticated else None
        proposed = roll_audit_anchor(
            self._audit_anchor,
            self._audit_chain.checkpoint(),
            interval=self._audit_anchor_interval,
        )
        if self._audit_anchor_authenticated or proposed != self._audit_anchor:
            return proposed
        return None

    def _checkpoint_for_snapshot(
        self,
        snapshot: IncidentSnapshot,
        execution_phase: str | None = None,
    ) -> IncidentCheckpoint:
        audit_sequence, audit_head = self._audit_chain_binding()
        anchor = self._proposed_anchor() if audit_sequence is not None else None
        return IncidentCheckpoint(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            report=snapshot.report,
            approval=snapshot.approval,
            outcome=snapshot.outcome,
            sequence=self._sequence,
            execution_phase=execution_phase,
            audit_chain_sequence=audit_sequence,
            audit_chain_head_sha256=audit_head,
            audit_anchor_sequence=None if anchor is None else anchor.sequence,
            audit_anchor_head_sha256=None if anchor is None else anchor.head_sha256,
        )

    def _save_checkpoint(self) -> None:
        if self._checkpoint_store is None or self._snapshot is None:
            return
        checkpoint = self._checkpoint_for_snapshot(self._snapshot)
        bound = checkpoint.audit_chain_sequence is not None
        try:
            self._checkpoint_store.save(checkpoint)
        except CheckpointConflictError:
            self._checkpoint_conflicted = True
            raise
        if bound:
            self._audit_integrity_state = "verified"
        if (
            checkpoint.audit_anchor_sequence is not None
            and checkpoint.audit_anchor_head_sha256 is not None
        ):
            self._audit_anchor = AuditAnchor(
                checkpoint.audit_anchor_sequence,
                checkpoint.audit_anchor_head_sha256,
            )
            self._audit_anchor_authenticated = True

    def _record_snapshot_transition(
        self,
        candidate: IncidentSnapshot,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> IncidentSnapshot:
        """Keep failed anchored transitions non-authoritative for operator reads.

        A non-CAS audit/checkpoint failure can happen after the candidate snapshot
        has been installed and after the audit sequence has advanced. In that case
        the prior committed snapshot remains the only safe read authority. Unlike a
        CAS conflict there is no authenticated winner that can be adopted through
        the conflict-reload path, so anchored lifecycle mutation is blocked by
        marking audit integrity failed until process/operator recovery reconstructs
        durable state.
        """
        previous = self._snapshot
        try:
            return super()._record_snapshot_transition(candidate, event_type, actor, payload)
        except CheckpointConflictError:
            raise
        except Exception:
            self._snapshot = previous
            self._audit_integrity_state = "failed"
            raise

    def audit_anchor_state(self) -> dict[str, object]:
        """Return bounded operator-safe anchor metadata; never returns event payloads."""
        with self._lock:
            return {
                "sequence": self._audit_anchor.sequence,
                "head_sha256": self._audit_anchor.head_sha256,
                "interval": self._audit_anchor_interval,
            }
