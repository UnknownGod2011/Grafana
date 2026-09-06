#!/usr/bin/env python3
"""Approval-gated remediation and telemetry-based recovery verification."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Protocol

from investigator import IncidentReport, MetricQueryClient
from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile, recovery_queries

RECOVERY_QUERIES = recovery_queries(DEFAULT_TELEMETRY_PROFILE)


class RemediationClient(Protocol):
    def recover_uplink(self, production_id: str, uplink: str) -> "ActionResult": ...


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


def required_approval(
    report: IncidentReport,
    approved_by: str,
    approved: bool,
    profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE,
) -> Approval:
    return Approval(approved, approved_by.strip(), "recover_uplink", report.production_id, profile.affected_uplink)


def _approval_matches(report: IncidentReport, approval: Approval, profile: TelemetryProfile) -> bool:
    return (
        report.status == "diagnosed"
        and report.hypothesis == f"{profile.affected_uplink} packet loss"
        and report.production_id == profile.production_id
        and report.affected_feed == profile.affected_feed
        and approval.approved
        and bool(approval.approved_by)
        and approval.action == "recover_uplink"
        and approval.production_id == report.production_id
        and approval.target == profile.affected_uplink
    )


def remediate_and_verify(
    report: IncidentReport,
    approval: Approval,
    remediation: RemediationClient,
    metrics: MetricQueryClient,
    *,
    profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE,
    max_attempts: int = 6,
    required_consecutive_healthy: int = 2,
    poll_interval_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> RemediationOutcome:
    """Execute one matching approved action, then prove recovery from bounded telemetry."""
    if not _approval_matches(report, approval, profile):
        return RemediationOutcome("approval_required", None, (),
            "Remediation was not executed because explicit matching human approval is required.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if required_consecutive_healthy < 1:
        raise ValueError("required_consecutive_healthy must be >= 1")

    action = remediation.recover_uplink(report.production_id, profile.affected_uplink)
    if not action.accepted:
        return RemediationOutcome("action_failed", action, (),
            "The remediation endpoint rejected or failed the action; recovery was not inferred.")

    queries = recovery_queries(profile)
    samples: list[RecoverySample] = []
    healthy_streak = 0
    for attempt in range(1, max_attempts + 1):
        packet_loss = metrics.instant(queries["packet_loss"][0])
        dropped_frames = metrics.instant(queries["dropped_frames"][0])
        healthy = (
            packet_loss is not None and dropped_frames is not None
            and packet_loss < queries["packet_loss"][1]
            and dropped_frames < queries["dropped_frames"][1]
        )
        samples.append(RecoverySample(attempt, packet_loss, dropped_frames, healthy))
        healthy_streak = healthy_streak + 1 if healthy else 0
        if healthy_streak >= required_consecutive_healthy:
            return RemediationOutcome("recovered", action, tuple(samples),
                "Recovery verified from consecutive healthy Grafana/Prometheus telemetry samples.")
        if attempt < max_attempts:
            sleep(poll_interval_seconds)

    return RemediationOutcome("recovery_unverified", action, tuple(samples),
        "The action was accepted, but bounded post-action telemetry did not prove recovery; keep the incident open.")


class SimulatorRemediationClient:
    """Local-only write adapter for the deterministic simulator."""

    def __init__(self, base_url: str = "http://127.0.0.1:9108", timeout_seconds: float = 3.0) -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("SimulatorRemediationClient only permits loopback HTTP targets")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def recover_uplink(self, production_id: str, uplink: str) -> ActionResult:
        profile = DEFAULT_TELEMETRY_PROFILE
        if production_id != profile.production_id or uplink != profile.affected_uplink:
            return ActionResult(False, "unsupported remediation target")
        request = urllib.request.Request(f"{self.base_url}/scenario/recover", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                status = response.status
        except Exception as exc:
            return ActionResult(False, f"simulator remediation request failed: {type(exc).__name__}")
        accepted = status == 200 and payload.get("faulted") is False
        return ActionResult(accepted, "simulator accepted recovery action" if accepted else "unexpected simulator response")
