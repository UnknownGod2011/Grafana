#!/usr/bin/env python3
"""Approval-gated remediation and telemetry-based recovery verification.

This module deliberately separates three responsibilities:

1. Grafana/Prometheus provides read-only evidence via ``MetricQueryClient``.
2. A distinct ``RemediationClient`` performs an approved consequential action.
3. Recovery is declared only after post-action telemetry satisfies bounded
   health criteria for multiple consecutive observations.

An action returning success is never treated as proof of recovery.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Protocol

from investigator import AFFECTED_FEED, AFFECTED_UPLINK, PRODUCTION_ID, IncidentReport, MetricQueryClient


RECOVERY_QUERIES = {
    "packet_loss": (
        f'network_packet_loss_percent{{production_id="{PRODUCTION_ID}",uplink="{AFFECTED_UPLINK}"}}',
        1.0,
    ),
    "dropped_frames": (
        f'rate(video_frames_dropped_total{{production_id="{PRODUCTION_ID}",feed_id="{AFFECTED_FEED}"}}[2m])',
        1.0,
    ),
}


class RemediationClient(Protocol):
    """Write-capable boundary intentionally separate from Grafana evidence."""

    def recover_uplink(self, production_id: str, uplink: str) -> "ActionResult":
        """Perform the approved recovery action."""


@dataclass(frozen=True)
class Approval:
    approved: bool
    approved_by: str
    action: str
    production_id: str
    target: str


@dataclass(frozen=True)
class ActionResult:
    accepted: bool
    detail: str


@dataclass(frozen=True)
class RecoverySample:
    attempt: int
    packet_loss_percent: float | None
    dropped_frames_per_second: float | None
    healthy: bool


@dataclass(frozen=True)
class RemediationOutcome:
    status: str
    action_result: ActionResult | None
    samples: tuple[RecoverySample, ...]
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def required_approval(report: IncidentReport, approved_by: str, approved: bool) -> Approval:
    """Build the only approval shape accepted for the seeded diagnosis."""

    return Approval(
        approved=approved,
        approved_by=approved_by.strip(),
        action="recover_uplink",
        production_id=report.production_id,
        target=AFFECTED_UPLINK,
    )


def _approval_matches(report: IncidentReport, approval: Approval) -> bool:
    return (
        report.status == "diagnosed"
        and report.hypothesis == "uplink-b packet loss"
        and approval.approved
        and bool(approval.approved_by)
        and approval.action == "recover_uplink"
        and approval.production_id == report.production_id
        and approval.target == AFFECTED_UPLINK
    )


def remediate_and_verify(
    report: IncidentReport,
    approval: Approval,
    remediation: RemediationClient,
    metrics: MetricQueryClient,
    *,
    max_attempts: int = 6,
    required_consecutive_healthy: int = 2,
    poll_interval_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> RemediationOutcome:
    """Execute one approved action, then prove recovery from telemetry.

    Recovery requires both packet loss and dropped-frame rate to be observable
    and strictly below their bounded thresholds for ``required_consecutive_healthy``
    consecutive samples. Missing telemetry resets the healthy streak.
    """

    if not _approval_matches(report, approval):
        return RemediationOutcome(
            status="approval_required",
            action_result=None,
            samples=(),
            summary="Remediation was not executed because explicit matching human approval is required.",
        )

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if required_consecutive_healthy < 1:
        raise ValueError("required_consecutive_healthy must be >= 1")

    action = remediation.recover_uplink(report.production_id, AFFECTED_UPLINK)
    if not action.accepted:
        return RemediationOutcome(
            status="action_failed",
            action_result=action,
            samples=(),
            summary="The remediation endpoint rejected or failed the action; recovery was not inferred.",
        )

    samples: list[RecoverySample] = []
    healthy_streak = 0

    for attempt in range(1, max_attempts + 1):
        packet_loss = metrics.instant(RECOVERY_QUERIES["packet_loss"][0])
        dropped_frames = metrics.instant(RECOVERY_QUERIES["dropped_frames"][0])
        healthy = (
            packet_loss is not None
            and dropped_frames is not None
            and packet_loss < RECOVERY_QUERIES["packet_loss"][1]
            and dropped_frames < RECOVERY_QUERIES["dropped_frames"][1]
        )
        samples.append(RecoverySample(attempt, packet_loss, dropped_frames, healthy))

        healthy_streak = healthy_streak + 1 if healthy else 0
        if healthy_streak >= required_consecutive_healthy:
            return RemediationOutcome(
                status="recovered",
                action_result=action,
                samples=tuple(samples),
                summary="Recovery verified from consecutive healthy Grafana/Prometheus telemetry samples.",
            )

        if attempt < max_attempts:
            sleep(poll_interval_seconds)

    return RemediationOutcome(
        status="recovery_unverified",
        action_result=action,
        samples=tuple(samples),
        summary=(
            "The action was accepted, but bounded post-action telemetry did not prove recovery; "
            "keep the incident open."
        ),
    )


class SimulatorRemediationClient:
    """Local-only write adapter for the deterministic simulator.

    It refuses non-loopback targets to prevent this demo adapter from becoming
    an accidental generic remote actuator. Production remediation should use a
    separate authenticated adapter and credential store.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9108", timeout_seconds: float = 3.0) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("SimulatorRemediationClient only permits loopback HTTP targets")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def recover_uplink(self, production_id: str, uplink: str) -> ActionResult:
        if production_id != PRODUCTION_ID or uplink != AFFECTED_UPLINK:
            return ActionResult(False, "unsupported remediation target")

        request = urllib.request.Request(
            f"{self.base_url}/scenario/recover",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # network/protocol errors remain action failures
            return ActionResult(False, f"simulator remediation request failed: {type(exc).__name__}")

        accepted = response.status == 200 and payload.get("faulted") is False
        return ActionResult(accepted, "simulator accepted recovery action" if accepted else "unexpected simulator response")
