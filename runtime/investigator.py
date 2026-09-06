#!/usr/bin/env python3
"""Bounded StageGuard incident investigator.

The investigator is intentionally deterministic at this layer: an evidence
source executes a fixed set of PromQL queries, then policy code decides whether
the telemetry supports the seeded incident diagnosis. LLM/Gemini orchestration
can sit above this module later, but cannot bypass its evidence/abstention rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


PRODUCTION_ID = "broadcast-alpha"
AFFECTED_FEED = "cam-3"
AFFECTED_UPLINK = "uplink-b"
HEALTHY_UPLINK = "uplink-a"


class MetricQueryClient(Protocol):
    """Minimal read-only metric query boundary used by the investigator."""

    def instant(self, promql: str) -> float | None:
        """Return one scalar value, or None when evidence is unavailable."""


@dataclass(frozen=True)
class Evidence:
    evidence_class: str
    query: str
    value: float | None
    threshold: str
    supports_hypothesis: bool | None


@dataclass(frozen=True)
class IncidentReport:
    status: str
    production_id: str
    affected_feed: str
    hypothesis: str | None
    confidence: float
    summary: str
    missing_evidence: tuple[str, ...]
    evidence: tuple[Evidence, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["missing_evidence"] = list(self.missing_evidence)
        return payload


QUERIES = {
    "symptom": (
        f'rate(video_frames_dropped_total{{production_id="{PRODUCTION_ID}",feed_id="{AFFECTED_FEED}"}}[2m])',
        "> 1 dropped frame/s",
    ),
    "causal": (
        f'network_packet_loss_percent{{production_id="{PRODUCTION_ID}",uplink="{AFFECTED_UPLINK}"}}',
        "> 5% packet loss",
    ),
    "contradiction_cpu": (
        f'encoder_cpu_percent{{production_id="{PRODUCTION_ID}",feed_id="{AFFECTED_FEED}"}}',
        "< 80% CPU",
    ),
    "contradiction_gpu": (
        f'encoder_gpu_percent{{production_id="{PRODUCTION_ID}",feed_id="{AFFECTED_FEED}"}}',
        "< 80% GPU",
    ),
    "healthy_peer_loss": (
        f'network_packet_loss_percent{{production_id="{PRODUCTION_ID}",uplink="{HEALTHY_UPLINK}"}}',
        "< 1% packet loss",
    ),
    "healthy_peer_drop": (
        f'max(rate(video_frames_dropped_total{{production_id="{PRODUCTION_ID}",feed_id=~"cam-1|cam-2"}}[2m]))',
        "< 1 dropped frame/s",
    ),
}


def _evidence(name: str, value: float | None, supports: bool | None) -> Evidence:
    query, threshold = QUERIES[name]
    return Evidence(name, query, value, threshold, supports)


def investigate(client: MetricQueryClient) -> IncidentReport:
    """Collect the fixed evidence contract and return a bounded diagnosis.

    High-confidence diagnosis is impossible unless symptom, causal,
    contradiction, and healthy-peer evidence are all observable. This is a
    deliberate safety invariant: missing telemetry yields abstention rather
    than a plausible-sounding root cause.
    """

    values = {name: client.instant(query) for name, (query, _) in QUERIES.items()}

    evidence = (
        _evidence("symptom", values["symptom"], None if values["symptom"] is None else values["symptom"] > 1.0),
        _evidence("causal", values["causal"], None if values["causal"] is None else values["causal"] > 5.0),
        _evidence(
            "contradiction_cpu",
            values["contradiction_cpu"],
            None if values["contradiction_cpu"] is None else values["contradiction_cpu"] < 80.0,
        ),
        _evidence(
            "contradiction_gpu",
            values["contradiction_gpu"],
            None if values["contradiction_gpu"] is None else values["contradiction_gpu"] < 80.0,
        ),
        _evidence(
            "healthy_peer_loss",
            values["healthy_peer_loss"],
            None if values["healthy_peer_loss"] is None else values["healthy_peer_loss"] < 1.0,
        ),
        _evidence(
            "healthy_peer_drop",
            values["healthy_peer_drop"],
            None if values["healthy_peer_drop"] is None else values["healthy_peer_drop"] < 1.0,
        ),
    )

    required_groups = {
        "symptom": ("symptom",),
        "causal": ("causal",),
        "contradiction": ("contradiction_cpu", "contradiction_gpu"),
        "healthy_peer": ("healthy_peer_loss", "healthy_peer_drop"),
    }
    missing = tuple(
        group
        for group, members in required_groups.items()
        if any(values[name] is None for name in members)
    )
    if missing:
        return IncidentReport(
            status="abstain",
            production_id=PRODUCTION_ID,
            affected_feed=AFFECTED_FEED,
            hypothesis=None,
            confidence=0.0,
            summary="Insufficient telemetry for a bounded root-cause diagnosis.",
            missing_evidence=missing,
            evidence=evidence,
        )

    symptom_active = values["symptom"] > 1.0  # type: ignore[operator]
    if not symptom_active:
        return IncidentReport(
            status="no_incident",
            production_id=PRODUCTION_ID,
            affected_feed=AFFECTED_FEED,
            hypothesis=None,
            confidence=0.95,
            summary="Camera 3 dropped-frame rate is below the incident threshold.",
            missing_evidence=(),
            evidence=evidence,
        )

    causal = values["causal"] > 5.0  # type: ignore[operator]
    contradiction = values["contradiction_cpu"] < 80.0 and values["contradiction_gpu"] < 80.0  # type: ignore[operator]
    healthy_peer = values["healthy_peer_loss"] < 1.0 and values["healthy_peer_drop"] < 1.0  # type: ignore[operator]

    if causal and contradiction and healthy_peer:
        return IncidentReport(
            status="diagnosed",
            production_id=PRODUCTION_ID,
            affected_feed=AFFECTED_FEED,
            hypothesis="uplink-b packet loss",
            confidence=0.97,
            summary=(
                "Camera 3 is dropping frames while uplink-b has severe packet loss; "
                "encoder CPU/GPU are healthy and peer feeds/uplink-a remain healthy."
            ),
            missing_evidence=(),
            evidence=evidence,
        )

    return IncidentReport(
        status="abstain",
        production_id=PRODUCTION_ID,
        affected_feed=AFFECTED_FEED,
        hypothesis=None,
        confidence=0.0,
        summary="The symptom is real, but the required evidence does not support the uplink-b hypothesis.",
        missing_evidence=(),
        evidence=evidence,
    )
