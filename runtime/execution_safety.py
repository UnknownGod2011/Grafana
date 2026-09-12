#!/usr/bin/env python3
"""Fail-closed remediation execution uncertainty handling.

This layer closes the race where a remediation provider may have accepted an
operation immediately before the lifecycle checkpoint loses compare-and-swap.
It never retries the remote action. Recovery requires adopting the durable
checkpoint winner and then collecting a fresh Grafana investigation; production
adapters that declare reconciliation as required must additionally prove the
idempotent provider operation is no longer ambiguous.

Checkpoint schema v2+ persists a provider-detail-free execution phase. Schema v3
additionally binds the audit-chain head when the base lifecycle has a verifiable
chain. A durable ``approved`` phase proves the side effect was not dispatched and
can safely survive restart. ``dispatching`` means the provider may have been
contacted and therefore requires reconciliation. Legacy v1 pending approvals
remain ambiguous because they contain no pre-side-effect phase marker.
"""
from __future__ import annotations

from typing import Literal

from incident_checkpoint import CheckpointConflictError
from incident_service import (
    AuditEvent,
    IncidentService,
    IncidentSnapshot,
    _MAX_AUDIT_LINEAGE_READ_EVENTS,
    _MAX_TIMELINE_EVENTS,
)
from remediation import remediation_operation_id

ReconciliationState = Literal["accepted", "not_found", "unknown"]
ExecutionPhase = Literal["none", "approved", "dispatching", "resolved", "legacy_unknown", "unknown"]
ReconciliationReason = Literal[
    "clear",
    "durable_dispatching",
    "legacy_unknown",
    "post_dispatch_checkpoint_regression",
    "phase_unavailable",
]
_EXECUTION_PHASES = {"none", "approved", "dispatching", "resolved", "legacy_unknown", "unknown"}
_RECONCILIATION_REASONS = {
    "clear",
    "durable_dispatching",
    "legacy_unknown",
    "post_dispatch_checkpoint_regression",
    "phase_unavailable",
}
_RECONCILIATION_RESULTS = {"accepted", "not_found", "unknown"}
_RECONCILIATION_AUDIT_STAGES = {"attempt", "recovered"}


class ExecutionSafeIncidentService(IncidentService):
    """IncidentService with fail-closed remediation execution uncertainty."""

    def __init__(self, *args, **kwargs) -> None:
        self._execution_uncertain = False
        self._execution_uncertain_operation_id: str | None = None
        self._execution_reloaded = False
        self._allow_uncertainty_investigation = False
        self._uncertain_execution_phase: ExecutionPhase = "unknown"
        self._execution_reconciliation_reason: ReconciliationReason = "clear"
        super().__init__(*args, **kwargs)
        self._guard_restored_production_approval()

    @staticmethod
    def _snapshot_execution_phase(snapshot: IncidentSnapshot | None) -> ExecutionPhase:
        if snapshot is None:
            return "none"
        if snapshot.outcome is not None:
            return "resolved"
        if snapshot.approval is not None:
            return "approved"
        return "none"

    def execution_checkpoint_phase(self) -> ExecutionPhase:
        with self._lock:
            if not self._execution_uncertain:
                return self._snapshot_execution_phase(self._snapshot)
            phase = self._uncertain_execution_phase
            return phase if phase in _EXECUTION_PHASES else "unknown"

    def execution_reconciliation_reason(self) -> ReconciliationReason:
        with self._lock:
            if not self._execution_uncertain:
                return "clear"
            reason = self._execution_reconciliation_reason
            return reason if reason in _RECONCILIATION_REASONS else "phase_unavailable"

    def execution_reconciliation_reference(self) -> str | None:
        """Return the stable StageGuard idempotency reference for operator reconciliation.

        The value is a deterministic ``sg-`` hash, not provider response detail or
        credentials. It is exposed only while execution remains ambiguous so an
        authenticated operator can correlate StageGuard state with the provider's
        idempotency/reconciliation record without reconstructing the approved action.
        """
        with self._lock:
            if not self._execution_uncertain:
                return None
            return self._execution_uncertain_operation_id

    def _phase_capable_store(self):
        store = self._checkpoint_store
        if store is None or not bool(getattr(store, "supports_execution_phase", False)):
            return None
        return store

    def _restored_execution_phase(self) -> str | None:
        store = self._phase_capable_store()
        snapshot = self._snapshot
        if store is None or snapshot is None:
            return None
        checkpoint = store.load()
        if checkpoint is None:
            raise RuntimeError("restored incident checkpoint became unavailable")
        if checkpoint.incident_id != snapshot.incident_id or checkpoint.revision != snapshot.revision:
            raise RuntimeError("restored incident checkpoint changed during safety validation")
        return checkpoint.execution_phase

    @staticmethod
    def _reason_for_restored_phase(phase: str | None) -> ReconciliationReason:
        if phase == "dispatching":
            return "durable_dispatching"
        if phase == "legacy_unknown":
            return "legacy_unknown"
        return "phase_unavailable"

    @staticmethod
    def _reconciliation_audit_event_type(
        stage: str, result: ReconciliationState, reason: ReconciliationReason
    ) -> str:
        safe_stage = stage if stage in _RECONCILIATION_AUDIT_STAGES else "attempt"
        safe_result = result if result in _RECONCILIATION_RESULTS else "unknown"
        safe_reason = reason if reason in _RECONCILIATION_REASONS - {"clear"} else "phase_unavailable"
        return f"remediation_reconciliation_{safe_stage}.{safe_result}.{safe_reason}"

    def _record_reconciliation_attempt(
        self,
        *,
        actor: str,
        result: ReconciliationState,
        reason: ReconciliationReason,
    ) -> None:
        """Append an attempt while preserving both dispatch and audit barriers."""
        snapshot = self._snapshot
        if snapshot is None:
            raise RuntimeError("reconciliation audit requires an incident snapshot")
        normalized_actor = actor.strip() or "stageguard"
        event_type = self._reconciliation_audit_event_type("attempt", result, reason)
        payload = {"result": result, "reason": reason}

        store = self._phase_capable_store()
        if store is None:
            self._record(snapshot.incident_id, event_type, normalized_actor, payload)
            return

        self._sequence += 1
        event = AuditEvent(self._sequence, self._clock_ms(), snapshot.incident_id, event_type, normalized_actor, payload)
        self._audit.append(event)
        if self._audit_chain is not None:
            try:
                self._audit_chain.append(event)
            except Exception:
                self._audit_integrity_state = "failed"
                raise RuntimeError("audit integrity chain could not advance safely")
        checkpoint = self._checkpoint_for_snapshot(snapshot, "dispatching")
        bound = checkpoint.audit_chain_sequence is not None
        try:
            store.save(checkpoint)
        except CheckpointConflictError:
            self._checkpoint_conflicted = True
            self._execution_reloaded = False
            raise
        # Only the checkpoint winner is operator-visible committed history. The
        # append-before-CAS record remains durable forensic residue for lineage
        # verification if this writer loses the checkpoint race.
        self._timeline.append(event)
        self._committed_audit_history.append(event)
        if len(self._timeline) > _MAX_TIMELINE_EVENTS:
            del self._timeline[: len(self._timeline) - _MAX_TIMELINE_EVENTS]
        if len(self._committed_audit_history) > _MAX_AUDIT_LINEAGE_READ_EVENTS:
            del self._committed_audit_history[: len(self._committed_audit_history) - _MAX_AUDIT_LINEAGE_READ_EVENTS]
        if bound:
            self._audit_integrity_state = "verified"

    def _clear_execution_uncertainty(self) -> None:
        self._execution_uncertain = False
        self._execution_uncertain_operation_id = None
        self._execution_reloaded = False
        self._uncertain_execution_phase = "unknown"
        self._execution_reconciliation_reason = "clear"

    def _guard_restored_production_approval(self) -> None:
        snapshot = self._snapshot
        requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
        if snapshot is None or snapshot.approval is None or snapshot.outcome is not None or not requires:
            return
        phase = self._restored_execution_phase()
        if phase == "approved":
            return
        if phase not in {"dispatching", "legacy_unknown", None}:
            raise RuntimeError("invalid pending remediation execution phase")
        self._execution_uncertain = True
        self._execution_uncertain_operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
        self._uncertain_execution_phase = "unknown" if phase is None else phase
        self._execution_reconciliation_reason = self._reason_for_restored_phase(phase)
        self._execution_reloaded = True

    def checkpoint_state(self) -> str:
        with self._lock:
            # Once provider dispatch may have happened, the no-replay barrier is
            # the most safety-critical checkpoint state. Audit integrity remains
            # separately visible and the API combines both into one safety state.
            if self._execution_uncertain:
                return "execution_uncertain"
            if self.audit_integrity_state() == "failed":
                return "conflicted"
            return super().checkpoint_state()

    def _require_checkpoint_consistency(self) -> None:
        if self._execution_uncertain and not self._allow_uncertainty_investigation:
            raise RuntimeError(
                "remediation execution is uncertain; reload durable state and reconcile before lifecycle changes"
            )
        super()._require_checkpoint_consistency()

    def _persist_dispatching_barrier(self, snapshot: IncidentSnapshot) -> bool:
        """Persist ``dispatching`` and the current audit head before provider contact."""
        requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
        store = self._phase_capable_store()
        if not requires or store is None:
            return False
        checkpoint = self._checkpoint_for_snapshot(snapshot, "dispatching")
        try:
            store.save(checkpoint)
        except CheckpointConflictError:
            self._checkpoint_conflicted = True
            raise
        return True

    def execute_approved(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                return super().execute_approved(actor=actor)
            self._require_checkpoint_consistency()
            operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
            dispatch_barrier = self._persist_dispatching_barrier(snapshot)
            try:
                return super().execute_approved(actor=actor)
            except CheckpointConflictError:
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = operation_id
                self._uncertain_execution_phase = "dispatching" if dispatch_barrier else "unknown"
                self._execution_reconciliation_reason = (
                    "durable_dispatching" if dispatch_barrier else "phase_unavailable"
                )
                self._execution_reloaded = False
                raise
            except Exception:
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = operation_id
                self._uncertain_execution_phase = "dispatching" if dispatch_barrier else "unknown"
                self._execution_reconciliation_reason = (
                    "durable_dispatching" if dispatch_barrier else "phase_unavailable"
                )
                self._execution_reloaded = True
                raise

    def reload_checkpoint_after_conflict(self) -> IncidentSnapshot:
        with self._lock:
            was_uncertain = self._execution_uncertain
            prior_phase = self._uncertain_execution_phase
            snapshot = super().reload_checkpoint_after_conflict()
            if not was_uncertain:
                return snapshot

            self._clear_execution_uncertainty()
            phase = self._restored_execution_phase()
            if snapshot.outcome is not None or snapshot.approval is None:
                return snapshot

            requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
            if not requires:
                return snapshot

            if phase == "approved":
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
                self._uncertain_execution_phase = "unknown"
                self._execution_reconciliation_reason = "post_dispatch_checkpoint_regression"
                self._execution_reloaded = True
                return snapshot

            self._guard_restored_production_approval()
            if self._execution_uncertain and phase is None and prior_phase == "dispatching":
                self._uncertain_execution_phase = "unknown"
                self._execution_reconciliation_reason = "phase_unavailable"
            return snapshot

    def execution_reconciliation_state(self) -> str:
        with self._lock:
            if not self._execution_uncertain:
                return "clear"
            return "reloaded" if self._execution_reloaded else "reload_required"

    def _provider_reconciliation(self) -> ReconciliationState:
        operation_id = self._execution_uncertain_operation_id
        if operation_id is None:
            return "unknown"
        requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
        reconcile = getattr(self._remediation, "reconcile_operation", None)
        if not requires:
            return "not_found"
        if not callable(reconcile):
            return "unknown"
        try:
            result = reconcile(operation_id)
        except Exception:
            return "unknown"
        return result if result in {"accepted", "not_found"} else "unknown"

    def reconcile_execution_uncertainty(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        """Resolve uncertain execution without replaying the approved action."""
        with self._lock:
            if not self._execution_uncertain:
                raise RuntimeError("no uncertain remediation execution requires reconciliation")
            if not self._execution_reloaded:
                raise RuntimeError("durable checkpoint winner must be reloaded before reconciliation")
            self._require_checkpoint_consistency()

            reason = self.execution_reconciliation_reason()
            provider_state = self._provider_reconciliation()
            self._record_reconciliation_attempt(actor=actor, result=provider_state, reason=reason)
            if provider_state == "unknown":
                raise RuntimeError("remediation provider idempotency state is unresolved")

            self._allow_uncertainty_investigation = True
            try:
                snapshot = super().investigate(actor=actor)
                self._record(
                    snapshot.incident_id,
                    self._reconciliation_audit_event_type("recovered", provider_state, reason),
                    actor.strip() or "stageguard",
                    {"result": provider_state, "reason": reason},
                )
            except Exception:
                raise
            else:
                self._clear_execution_uncertainty()
                return snapshot
            finally:
                self._allow_uncertainty_investigation = False
