#!/usr/bin/env python3
"""Fail-closed remediation execution uncertainty handling.

This layer closes the race where a remediation provider may have accepted an
operation immediately before the lifecycle checkpoint loses compare-and-swap.
It never retries the remote action. Recovery requires adopting the durable
checkpoint winner and then collecting a fresh Grafana investigation; production
adapters that declare reconciliation as required must additionally prove the
idempotent provider operation is no longer ambiguous.

Checkpoint schema v2 persists a provider-detail-free execution phase. A durable
``approved`` phase proves the side effect was not dispatched and can safely
survive restart. ``dispatching`` means the provider may have been contacted and
therefore requires reconciliation. Legacy v1 pending approvals remain ambiguous
because they contain no pre-side-effect phase marker.
"""
from __future__ import annotations

from typing import Literal

from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
from incident_service import IncidentService, IncidentSnapshot
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
        """Derive the bounded phase for ordinary synchronized lifecycle state."""
        if snapshot is None:
            return "none"
        if snapshot.outcome is not None:
            return "resolved"
        if snapshot.approval is not None:
            return "approved"
        return "none"

    def execution_checkpoint_phase(self) -> ExecutionPhase:
        """Return provider-detail-free execution phase for metrics/readiness.

        The method intentionally exposes only a fixed enum. During execution
        uncertainty it reports the authenticated/restored barrier phase rather
        than deriving ``approved`` from the still-pending lifecycle snapshot.
        """
        with self._lock:
            if not self._execution_uncertain:
                return self._snapshot_execution_phase(self._snapshot)
            phase = self._uncertain_execution_phase
            return phase if phase in _EXECUTION_PHASES else "unknown"

    def execution_reconciliation_reason(self) -> ReconciliationReason:
        """Return a fixed-cardinality reason for execution uncertainty.

        The value is deliberately provider-detail-free: it never contains an
        incident id, operation id, target, endpoint, actor, generation, or raw
        exception text. Operators can distinguish durable ambiguity from legacy
        state and contradictory multi-instance handoff without cardinality risk.
        """
        with self._lock:
            if not self._execution_uncertain:
                return "clear"
            reason = self._execution_reconciliation_reason
            return reason if reason in _RECONCILIATION_REASONS else "phase_unavailable"

    def _phase_capable_store(self):
        store = self._checkpoint_store
        if store is None or not bool(getattr(store, "supports_execution_phase", False)):
            return None
        return store

    def _restored_execution_phase(self) -> str | None:
        """Read the authenticated phase from a phase-capable durable store.

        The base constructor has already loaded and validated the checkpoint. A
        second load is deliberate: production stores pin the same current
        generation while exposing the schema-v2 phase to this safety layer.
        """
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

    def _clear_execution_uncertainty(self) -> None:
        """Reset process-local ambiguity after an authoritative durable transition."""
        self._execution_uncertain = False
        self._execution_uncertain_operation_id = None
        self._execution_reloaded = False
        self._uncertain_execution_phase = "unknown"
        self._execution_reconciliation_reason = "clear"

    def _guard_restored_production_approval(self) -> None:
        """Apply restart semantics from the durable execution phase.

        A v2 ``approved`` checkpoint is safe to execute after restart because
        StageGuard persisted it before the dispatch barrier. ``dispatching`` and
        v1 ``legacy_unknown`` are fail-closed and require reconciliation plus
        fresh Grafana evidence. Custom stores without phase support retain the
        older conservative behavior.
        """
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
        # Construction has already adopted and validated this durable state.
        self._execution_reloaded = True

    def checkpoint_state(self) -> str:
        with self._lock:
            if self._execution_uncertain:
                return "execution_uncertain"
            return super().checkpoint_state()

    def _require_checkpoint_consistency(self) -> None:
        if self._execution_uncertain and not self._allow_uncertainty_investigation:
            raise RuntimeError(
                "remediation execution is uncertain; reload durable state and reconcile before lifecycle changes"
            )
        super()._require_checkpoint_consistency()

    def _persist_dispatching_barrier(self, snapshot: IncidentSnapshot) -> bool:
        """Persist ``dispatching`` before any reconciliation-required side effect.

        Returns True when the durable barrier was written. A CAS conflict here
        occurs before provider contact and therefore remains an ordinary
        checkpoint conflict rather than execution uncertainty.
        """
        requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
        store = self._phase_capable_store()
        if not requires or store is None:
            return False
        checkpoint = IncidentCheckpoint(
            snapshot.incident_id,
            snapshot.revision,
            snapshot.report,
            snapshot.approval,
            snapshot.outcome,
            self._sequence,
            "dispatching",
        )
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
            operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
            # A phase-capable production store persists the dispatch barrier here.
            # If this save itself conflicts, the exception is raised before the
            # try block below and therefore before any provider contact.
            dispatch_barrier = self._persist_dispatching_barrier(snapshot)
            try:
                return super().execute_approved(actor=actor)
            except CheckpointConflictError:
                # We entered super().execute_approved(), so provider execution or
                # verification may already have occurred. This is ambiguous even
                # for legacy/custom stores that cannot persist schema-v2 phases.
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = operation_id
                self._uncertain_execution_phase = "dispatching" if dispatch_barrier else "unknown"
                self._execution_reconciliation_reason = (
                    "durable_dispatching" if dispatch_barrier else "phase_unavailable"
                )
                self._execution_reloaded = False
                raise
            except Exception:
                # Any exception after crossing into the provider execution path is
                # conservatively ambiguous. A v2 barrier can report dispatching;
                # phase-unaware stores report only the bounded unknown state.
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = operation_id
                self._uncertain_execution_phase = "dispatching" if dispatch_barrier else "unknown"
                self._execution_reconciliation_reason = (
                    "durable_dispatching" if dispatch_barrier else "phase_unavailable"
                )
                self._execution_reloaded = True
                raise

    def reload_checkpoint_after_conflict(self) -> IncidentSnapshot:
        """Adopt the durable winner and recompute ambiguity from that winner.

        Durable ``none``/``resolved`` winners prove that another instance has
        already cleared or consumed the stale approval, so obsolete process-local
        ambiguity can be discarded. ``dispatching`` and legacy-unknown winners
        remain reconciliation-gated.

        A durable ``approved`` checkpoint is safe on a *clean process restart*,
        but it is not sufficient to erase this process's direct knowledge that it
        may already have crossed the provider-dispatch barrier before losing CAS.
        In that conflict-reload case StageGuard deliberately keeps execution
        uncertainty and requires reconciliation, preventing a stale approval from
        becoming executable again because of a regressed or non-monotonic store
        view.
        """
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
                # The durable winner says approved while this process says the
                # dispatch boundary may have been crossed. Report only bounded
                # unknown rather than falsely advertising either state as truth.
                self._uncertain_execution_phase = "unknown"
                self._execution_reconciliation_reason = "post_dispatch_checkpoint_regression"
                self._execution_reloaded = True
                return snapshot

            # Normal fail-closed restore handling for dispatching, legacy-v1, or
            # phase-unaware durable winners. ``prior_phase`` is intentionally not
            # restored: the authenticated winner defines the exposed phase unless
            # it contradicts direct process knowledge as in the approved case.
            self._guard_restored_production_approval()
            if self._execution_uncertain and phase is None and prior_phase == "dispatching":
                self._uncertain_execution_phase = "unknown"
                self._execution_reconciliation_reason = "phase_unavailable"
            return snapshot

    def execution_reconciliation_state(self) -> str:
        """Return a bounded operator-safe lifecycle state."""
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
        """Resolve an uncertain execution without replaying the approved action.

        The durable winner must already have been loaded. Production adapters
        that require provider reconciliation must return either ``accepted`` or
        ``not_found`` for the deterministic operation id. StageGuard then runs a
        fresh Grafana investigation, which clears the stale approval/outcome and
        creates a new evidence revision before remediation can ever be approved
        again.
        """
        with self._lock:
            if not self._execution_uncertain:
                raise RuntimeError("no uncertain remediation execution requires reconciliation")
            if not self._execution_reloaded:
                raise RuntimeError("durable checkpoint winner must be reloaded before reconciliation")
            provider_state = self._provider_reconciliation()
            if provider_state == "unknown":
                raise RuntimeError("remediation provider idempotency state is unresolved")

            self._allow_uncertainty_investigation = True
            try:
                snapshot = super().investigate(actor=actor)
            except Exception:
                raise
            else:
                self._clear_execution_uncertainty()
                return snapshot
            finally:
                self._allow_uncertainty_investigation = False
