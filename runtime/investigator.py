#!/usr/bin/env python3
"""Bounded StageGuard incident investigator.

The investigator is deterministic: a read-only evidence source executes exactly
six policy-selected PromQL queries, then policy code decides whether telemetry
supports the bounded diagnosis. Telemetry names/labels are configurable only
through a validated TelemetryProfile; callers never submit raw PromQL.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile, investigation_queries

PRODUCTION_ID = DEFAULT_TELEMETRY_PROFILE.production_id
AFFECTED_FEED = DEFAULT_TELEMETRY_PROFILE.affected_feed
AFFECTED_UPLINK = DEFAULT_TELEMETRY_PROFILE.affected_uplink
HEALTHY_UPLINK = DEFAULT_TELEMETRY_PROFILE.healthy_uplink
QUERIES = investigation_queries(DEFAULT_TELEMETRY_PROFILE)


class MetricQueryClient(Protocol):
    def instant(self, promql: str) -> float | None: ...


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


def investigate(client: MetricQueryClient, profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE) -> IncidentReport:
    """Collect six fixed semantic evidence slots and return a bounded diagnosis."""
    queries = investigation_queries(profile)
    values = {name: client.instant(query) for name, (query, _) in queries.items()}

    def evidence(name: str, supports: bool | None) -> Evidence:
        query, threshold = queries[name]
        return Evidence(name, query, values[name], threshold, supports)

    items = (
        evidence("symptom", None if values["symptom"] is None else values["symptom"] > 1.0),
        evidence("causal", None if values["causal"] is None else values["causal"] > 5.0),
        evidence("contradiction_cpu", None if values["contradiction_cpu"] is None else values["contradiction_cpu"] < 80.0),
        evidence("contradiction_gpu", None if values["contradiction_gpu"] is None else values["contradiction_gpu"] < 80.0),
        evidence("healthy_peer_loss", None if values["healthy_peer_loss"] is None else values["healthy_peer_loss"] < 1.0),
        evidence("healthy_peer_drop", None if values["healthy_peer_drop"] is None else values["healthy_peer_drop"] < 1.0),
    )

    required_groups = {
        "symptom": ("symptom",), "causal": ("causal",),
        "contradiction": ("contradiction_cpu", "contradiction_gpu"),
        "healthy_peer": ("healthy_peer_loss", "healthy_peer_drop"),
    }
    missing = tuple(group for group, members in required_groups.items() if any(values[n] is None for n in members))
    if missing:
        return IncidentReport("abstain", profile.production_id, profile.affected_feed, None, 0.0,
            "Insufficient telemetry for a bounded root-cause diagnosis.", missing, items)

    if not values["symptom"] > 1.0:  # type: ignore[operator]
        return IncidentReport("no_incident", profile.production_id, profile.affected_feed, None, 0.95,
            f"{profile.affected_feed} dropped-frame rate is below the incident threshold.", (), items)

    causal = values["causal"] > 5.0  # type: ignore[operator]
    contradiction = values["contradiction_cpu"] < 80.0 and values["contradiction_gpu"] < 80.0  # type: ignore[operator]
    healthy_peer = values["healthy_peer_loss"] < 1.0 and values["healthy_peer_drop"] < 1.0  # type: ignore[operator]
    if causal and contradiction and healthy_peer:
        return IncidentReport("diagnosed", profile.production_id, profile.affected_feed,
            f"{profile.affected_uplink} packet loss", 0.97,
            f"{profile.affected_feed} is dropping frames while {profile.affected_uplink} has severe packet loss; encoder CPU/GPU and peer paths remain healthy.", (), items)

    return IncidentReport("abstain", profile.production_id, profile.affected_feed, None, 0.0,
        "The symptom is real, but the required evidence does not support the configured uplink hypothesis.", (), items)
