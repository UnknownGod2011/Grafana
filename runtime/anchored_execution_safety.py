#!/usr/bin/env python3
"""Execution-safe StageGuard service with authenticated audit-anchor restore.

This composition keeps the remediation dispatch/reconciliation barriers from
ExecutionSafeIncidentService while adding the bounded-suffix audit verification
and save-before-promote anchor lifecycle from AnchoredIncidentService.

Production remediation can spend seconds contacting a provider and then polling
Grafana for recovery evidence. Those external waits deliberately run without the
incident lifecycle lock so authenticated status/readiness requests remain
responsive. Lifecycle mutations are still fail-closed while one execution is in
flight, and all state promotion/checkpoint/audit work remains lock protected.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable

from anchored_incident_service import AnchoredIncidentService
from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError
from incident_service import IncidentSnapshot
from remediation import remediate_and_verify, remediation_operation_id, verify_recovery


DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS = 60.0
MIN_REMEDIATION_EXECUTION_SECONDS = 1.0
MAX_REMEDIATION_EXECUTION_SECONDS = 600.0


class AnchoredExecutionSafeIncidentService(
    AnchoredIncidentService,
    ExecutionSafeIncidentService,
):
    """Production-oriented composition of anchor integrity and execution safety.

    Both parents use cooperative ``super()``. The MRO is intentionally:
    AnchoredIncidentService -> ExecutionSafeIncidentService -> IncidentService,
    so anchor initialization happens before execution-safety initialization and
    both layers reach the stable IncidentService exactly once.

    The production composition also narrows lock scope around approved execution:
    dispatch/recovery I/O happens outside ``_lock`` while ``_execution_in_flight``
    blocks every competing lifecycle mutation through the existing consistency
    gate. Immutable incident snapshots remain readable during the wait.
    """

    def __init__(
        self,
        *args,
        execution_max_seconds: float = DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS,
        monotonic: Callable[[], float] | None = None,
        **kwargs,
    ) -> None:
        try:
            maximum = float(execution_max_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("execution_max_seconds must be a finite positive number") from exc
        if (
            isinstance(execution_max_seconds, bool)
            or not math.isfinite(maximum)
            or maximum < MIN_REMEDIATION_EXECUTION_SECONDS
            or maximum > MAX_REMEDIATION_EXECUTION_SECONDS
        ):
            raise ValueError("execution_max_seconds must be a finite positive number")
        self._execution_in_flight = False
        self._recovery_recheck_in_flight = False
        self._execution_started_monotonic: float | None = None
        self._execution_max_seconds = maximum
        self._execution_monotonic = monotonic or time.monotonic
        super().__init__(*args, **kwargs)

    def _read_execution_monotonic(self) -> float:
        """Read the watchdog clock without allowing malformed values to fail open."""
        try:
            raw_value = self._execution_monotonic()
        except Exception as exc:
            raise RuntimeError("remediation execution watchdog clock unavailable") from exc
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise RuntimeError("remediation execution watchdog clock unavailable")
        value = float(raw_value)
        if not math.isfinite(value):
            raise RuntimeError("remediation execution watchdog clock unavailable")
        return value

    def _execution_age_unlocked(self) -> float:
        if not self._execution_in_flight or self._execution_started_monotonic is None:
            return 0.0
        try:
            current = self._read_execution_monotonic()
        except RuntimeError:
            return self._execution_max_seconds + 1.0
        started = self._execution_started_monotonic
        if not math.isfinite(started) or current < started:
            return self._execution_max_seconds + 1.0
        age = current - started
        if not math.isfinite(age):
            return self._execution_max_seconds + 1.0
        return age

    def _execution_deadline_exceeded_unlocked(self) -> bool:
        return self._execution_in_flight and self._execution_age_unlocked() > self._execution_max_seconds

    def _require_checkpoint_consistency(self) -> None:
        if self._execution_in_flight:
            raise RuntimeError("remediation execution is already in progress; lifecycle changes are blocked")
        super()._require_checkpoint_consistency()

    def checkpoint_state(self) -> str:
        """Fail readiness closed when an active provider/recovery operation exceeds its bounded window."""
        with self._lock:
            if self._execution_deadline_exceeded_unlocked():
                return "execution_uncertain"
            return super().checkpoint_state()

    def execution_checkpoint_phase(self):
        """Expose active provider execution or recovery-only verification without provider detail."""
        with self._lock:
            if self._execution_in_flight:
                # A recovery recheck performs no provider mutation, so do not expose
                # it as a dispatching phase. ``resolved`` here means provider dispatch
                # has already completed; the active watchdog metric still shows that
                # fresh recovery evidence collection is in progress.
                return "resolved" if self._recovery_recheck_in_flight else "dispatching"
            return super().execution_checkpoint_phase()

    def remediation_execution_observability(self) -> dict[str, float | bool]:
        """Return fixed-cardinality execution watchdog state with no provider details."""
        with self._lock:
            active = self._execution_in_flight
            age = self._execution_age_unlocked()
            maximum = self._execution_max_seconds
        return {
            "active": active,
            "age_seconds": age,
            "max_seconds": maximum,
            "deadline_exceeded": bool(active and age > maximum),
        }

    def _mark_execution_uncertain(self, *, operation_id: str, dispatch_barrier: bool, reloaded: bool) -> None:
        """Preserve the parent execution-uncertainty semantics after provider contact."""
        self._execution_uncertain = True
        self._execution_uncertain_operation_id = operation_id
        self._uncertain_execution_phase = "dispatching" if dispatch_barrier else "unknown"
        self._execution_reconciliation_reason = (
            "durable_dispatching" if dispatch_barrier else "phase_unavailable"
        )
        self._execution_reloaded = reloaded

    def execute_approved(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        """Execute approved remediation without holding the lifecycle lock over I/O.

        The dispatch barrier is persisted while locked before any provider contact.
        Once ``_execution_in_flight`` is set, every mutation path using
        ``_require_checkpoint_consistency`` fails closed. The remote action and
        bounded Grafana recovery polling then run outside the lock, allowing
        status/readiness/metrics requests to observe the active ``dispatching``
        phase. Final outcome promotion, audit append, and checkpoint CAS happen
        under the lock again. A losing or failed final commit restores the
        pre-execution snapshot for reads while execution uncertainty keeps the
        already-dispatched provider action from being replayed.
        """
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                return super().execute_approved(actor=actor)
            self._require_checkpoint_consistency()
            if snapshot.outcome is not None:
                raise RuntimeError("this approval has already been consumed")

            operation_id = remediation_operation_id(snapshot.report, snapshot.approval)
            started_monotonic = self._read_execution_monotonic()
            dispatch_barrier = self._persist_dispatching_barrier(snapshot)
            self._execution_started_monotonic = started_monotonic
            self._recovery_recheck_in_flight = False
            self._execution_in_flight = True

        try:
            outcome = remediate_and_verify(
                snapshot.report,
                snapshot.approval,
                self._remediation,
                self._metrics,
                profile=self._profile,
                sleep=self._recovery_sleep,
            )
        except Exception:
            with self._lock:
                self._execution_in_flight = False
                self._execution_started_monotonic = None
                self._mark_execution_uncertain(
                    operation_id=operation_id,
                    dispatch_barrier=dispatch_barrier,
                    reloaded=True,
                )
            raise

        with self._lock:
            try:
                current = self._snapshot
                if (
                    current is None
                    or current.incident_id != snapshot.incident_id
                    or current.revision != snapshot.revision
                    or current.approval != snapshot.approval
                    or current.outcome is not None
                ):
                    raise RuntimeError("incident state changed during remediation execution")

                candidate = IncidentSnapshot(
                    snapshot.incident_id,
                    snapshot.revision,
                    snapshot.report,
                    snapshot.approval,
                    outcome,
                )
                payload = {
                    "revision": snapshot.revision,
                    "status": outcome.status,
                    "sample_count": len(outcome.samples),
                    "action_accepted": bool(outcome.action_result and outcome.action_result.accepted),
                }
                if outcome.action_result is not None and outcome.action_result.metadata:
                    payload["action_metadata"] = dict(outcome.action_result.metadata)
                return self._record_snapshot_transition(
                    candidate,
                    "remediation_completed",
                    actor.strip() or "stageguard",
                    payload,
                )
            except CheckpointConflictError:
                self._mark_execution_uncertain(
                    operation_id=operation_id,
                    dispatch_barrier=dispatch_barrier,
                    reloaded=False,
                )
                raise
            except Exception:
                self._snapshot = snapshot
                self._mark_execution_uncertain(
                    operation_id=operation_id,
                    dispatch_barrier=dispatch_barrier,
                    reloaded=True,
                )
                raise
            finally:
                self._execution_in_flight = False
                self._recovery_recheck_in_flight = False
                self._execution_started_monotonic = None

    def recheck_recovery(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        """Recheck Grafana recovery evidence without blocking reads or replaying remediation."""
        with self._lock:
            self._require_checkpoint_consistency()
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None or snapshot.outcome is None:
                raise RuntimeError("a completed accepted remediation is required before recovery recheck")
            previous = snapshot.outcome
            if previous.status != "recovery_unverified":
                raise RuntimeError("recovery recheck is only allowed while recovery remains unverified")
            if previous.action_result is None or previous.action_result.accepted is not True:
                raise RuntimeError("recovery recheck requires a previously accepted remediation action")

            started_monotonic = self._read_execution_monotonic()
            self._execution_started_monotonic = started_monotonic
            self._recovery_recheck_in_flight = True
            self._execution_in_flight = True

        try:
            outcome = verify_recovery(
                previous.action_result,
                self._metrics,
                profile=self._profile,
                sleep=self._recovery_sleep,
            )
        except Exception:
            # Recovery-only evidence collection has no provider side effect, so a
            # telemetry failure must not manufacture provider execution uncertainty.
            with self._lock:
                self._execution_in_flight = False
                self._recovery_recheck_in_flight = False
                self._execution_started_monotonic = None
            raise

        with self._lock:
            try:
                current = self._snapshot
                if (
                    current is None
                    or current.incident_id != snapshot.incident_id
                    or current.revision != snapshot.revision
                    or current.approval != snapshot.approval
                    or current.outcome != previous
                ):
                    raise RuntimeError("incident state changed during recovery recheck")

                candidate = IncidentSnapshot(
                    snapshot.incident_id,
                    snapshot.revision,
                    snapshot.report,
                    snapshot.approval,
                    outcome,
                )
                return self._record_snapshot_transition(
                    candidate,
                    "recovery_rechecked",
                    actor.strip() or "stageguard",
                    {
                        "revision": snapshot.revision,
                        "status": outcome.status,
                        "sample_count": len(outcome.samples),
                        "provider_replayed": False,
                    },
                )
            finally:
                self._execution_in_flight = False
                self._recovery_recheck_in_flight = False
                self._execution_started_monotonic = None
