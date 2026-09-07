#!/usr/bin/env python3
"""Fail-closed remediation execution uncertainty handling.

This layer closes the race where a remediation provider may have accepted an
operation immediately before the lifecycle checkpoint loses compare-and-swap.
It never retries the remote action. Recovery requires adopting the durable
checkpoint winner and then collecting a fresh Grafana investigation; production
adapters that declare reconciliation as required must additionally prove the
idempotent provider operation is no longer ambiguous.

A restored production checkpoint containing an unused approval is also treated
as uncertain. The checkpoint alone cannot prove whether a previous process sent
the deterministic operation before crashing. This conservative restart rule can
invalidate a genuinely unused approval, but it prevents a process restart from
turning ambiguous execution into an automatic replay.
"""
from __future__ import annotations

from typing import Literal

from incident_checkpoint import CheckpointConflictError
from incident_service import IncidentService, IncidentSnapshot
from remediation import remediation_operation_id

ReconciliationState = Literal["accepted", "not_found", "unknown"]


class ExecutionSafeIncidentService(IncidentService):
    """IncidentService with fail-closed remediation execution uncertainty."""

    def __init__(self, *args, **kwargs) -> None:
        self._execution_uncertain = False
        self._execution_uncertain_operation_id: str | None = None
        self._execution_reloaded = False
        self._allow_uncertainty_investigation = False
        super().__init__(*args, **kwargs)
        self._guard_restored_production_approval()

    def _guard_restored_production_approval(self) -> None:
        """Treat a restored unused production approval as execution-ambiguous.

        The durable checkpoint intentionally does not persist provider execution
        detail. After restart, an approval with no outcome therefore cannot prove
        that the prior process never contacted the remediation provider. For
        adapters requiring provider reconciliation, derive the same deterministic
        operation id and force reconciliation plus fresh Grafana evidence before
        any new approval can become actionable.
        """
        snapshot = self._snapshot
        requires = bool(getattr(self._remediation, "requires_operation_reconciliation", False))
        if snapshot is None or snapshot.approval is None or snapshot.outcome is not None or not requires:
            return
        self._execution_uncertain = True
        self._execution_uncertain_operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
        # super().__init__ has already loaded and validated the durable winner.
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

    def execute_approved(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                return super().execute_approved(actor=actor)
            operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
            try:
                return super().execute_approved(actor=actor)
            except CheckpointConflictError:
                # At this point IncidentService has already returned from
                # remediate_and_verify(), so the provider was contacted. Never
                # infer whether it executed from the losing checkpoint write.
                self._execution_uncertain = True
                self._execution_uncertain_operation_id = operation_id
                self._execution_reloaded = False
                raise

    def reload_checkpoint_after_conflict(self) -> IncidentSnapshot:
        with self._lock:
            snapshot = super().reload_checkpoint_after_conflict()
            if self._execution_uncertain:
                # Durable winner adoption resolves checkpoint ownership only.
                # It does not resolve the remote side-effect ambiguity.
                self._execution_reloaded = True
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

            # Fresh investigation is the only allowed lifecycle mutation while
            # uncertain. IncidentService.investigate deterministically clears the
            # old approval/outcome and persists the new evidence revision.
            self._allow_uncertainty_investigation = True
            try:
                snapshot = super().investigate(actor=actor)
            except Exception:
                # Any failure, including another checkpoint conflict, leaves the
                # uncertainty block in place.
                raise
            else:
                self._execution_uncertain = False
                self._execution_uncertain_operation_id = None
                self._execution_reloaded = False
                return snapshot
            finally:
                self._allow_uncertainty_investigation = False
