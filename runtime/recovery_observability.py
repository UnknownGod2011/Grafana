#!/usr/bin/env python3
"""Provider-detail-free recovery lifecycle observability for StageGuard.

This module deliberately derives only fixed-cardinality state from the durable
incident snapshot. It never exports incident IDs, evidence revisions, actors,
queries, datasource identities, provider metadata, or remediation targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import object as _object


RECOVERY_STATES = (
    "none",
    "approval_required",
    "action_failed",
    "recovery_unverified",
    "recovered",
    "unknown",
)


@dataclass(frozen=True)
class RecoveryObservability:
    state: str
    action_accepted: bool
    recheck_eligible: bool
    verified: bool
    sample_count: int
    checkpoint_phase_consistent: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "action_accepted": self.action_accepted,
            "recheck_eligible": self.recheck_eligible,
            "verified": self.verified,
            "sample_count": self.sample_count,
            "checkpoint_phase_consistent": self.checkpoint_phase_consistent,
        }


def _safe_sample_count(outcome: object | None) -> int:
    if outcome is None:
        return 0
    samples = getattr(outcome, "samples", ())
    if not isinstance(samples, tuple):
        return 0
    # Recovery verification itself is bounded. Keep this exporter defensive so
    # corrupted/injected state cannot create an unbounded metric value.
    return min(len(samples), 100)


def recovery_observability(snapshot: object | None, execution_phase: str) -> RecoveryObservability:
    """Derive a bounded recovery summary from durable lifecycle state.

    ``execution_phase`` is supplied separately because production runtimes may
    expose a durable phase through an execution-safety wrapper rather than the
    snapshot itself. Any outcome requires the durable phase to be ``resolved``.
    Unknown outcome statuses fail closed into the fixed ``unknown`` bucket.
    """
    outcome = None if snapshot is None else getattr(snapshot, "outcome", None)
    if outcome is None:
        phase_consistent = execution_phase in {
            "none",
            "approved",
            "dispatching",
            "legacy_unknown",
        }
        return RecoveryObservability(
            state="none",
            action_accepted=False,
            recheck_eligible=False,
            verified=False,
            sample_count=0,
            checkpoint_phase_consistent=phase_consistent,
        )

    raw_status = getattr(outcome, "status", None)
    state = raw_status if raw_status in RECOVERY_STATES and raw_status != "none" else "unknown"
    action = getattr(outcome, "action_result", None)
    accepted = getattr(action, "accepted", False) is True
    verified = state == "recovered"
    recheck_eligible = state == "recovery_unverified" and accepted
    return RecoveryObservability(
        state=state,
        action_accepted=accepted,
        recheck_eligible=recheck_eligible,
        verified=verified,
        sample_count=_safe_sample_count(outcome),
        checkpoint_phase_consistent=execution_phase == "resolved",
    )


def prometheus_recovery_metrics(snapshot: object | None, execution_phase: str) -> str:
    """Render fixed-cardinality Prometheus text for the recovery lifecycle."""
    view = recovery_observability(snapshot, execution_phase)
    lines = [
        "# HELP stageguard_recovery_state Current provider-detail-free durable recovery lifecycle state.",
        "# TYPE stageguard_recovery_state gauge",
    ]
    for state in RECOVERY_STATES:
        lines.append(
            f'stageguard_recovery_state{{state="{state}"}} {1 if view.state == state else 0}'
        )
    lines.extend(
        [
            "# HELP stageguard_recovery_action_accepted Whether the durable recovery outcome records literal provider acceptance.",
            "# TYPE stageguard_recovery_action_accepted gauge",
            f"stageguard_recovery_action_accepted {1 if view.action_accepted else 0}",
            "# HELP stageguard_recovery_recheck_eligible Whether only the no-replay Grafana recovery recheck path is currently eligible.",
            "# TYPE stageguard_recovery_recheck_eligible gauge",
            f"stageguard_recovery_recheck_eligible {1 if view.recheck_eligible else 0}",
            "# HELP stageguard_recovery_verified Whether fresh Grafana telemetry has proven recovery.",
            "# TYPE stageguard_recovery_verified gauge",
            f"stageguard_recovery_verified {1 if view.verified else 0}",
            "# HELP stageguard_recovery_sample_count Number of bounded recovery evidence samples in the durable outcome.",
            "# TYPE stageguard_recovery_sample_count gauge",
            f"stageguard_recovery_sample_count {view.sample_count}",
            "# HELP stageguard_recovery_checkpoint_phase_consistent Whether recovery outcome presence agrees with the durable execution phase.",
            "# TYPE stageguard_recovery_checkpoint_phase_consistent gauge",
            f"stageguard_recovery_checkpoint_phase_consistent {1 if view.checkpoint_phase_consistent else 0}",
        ]
    )
    return "\n".join(lines) + "\n"
