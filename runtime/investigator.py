#!/usr/bin/env python3
"""Bounded StageGuard incident investigator.

The metric investigator is deterministic: a read-only evidence source executes
exactly six policy-selected PromQL queries. A stricter corroborated mode adds
one policy-selected Loki query only after the metric evidence independently
supports the configured diagnosis. Callers never submit raw PromQL or LogQL.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from evidence_errors import EvidenceUnavailable
from log_evidence import LogCorroboration, LogQueryClient, corroborate_uplink_loss
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
    log_corroboration: LogCorroboration | None = None
    unavailable_evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["missing_evidence"] = list(self.missing_evidence)
        payload["unavailable_evidence"] = list(self.unavailable_evidence)
        return payload


def _supports(name: str, value: float | None) -> bool | None:
    if value is None:
        return None
    if name == "symptom":
        return value > 1.0
    if name == "causal":
        return value > 5.0
    if name in {"contradiction_cpu", "contradiction_gpu"}:
        return value < 80.0
    if name in {"healthy_peer_loss", "healthy_peer_drop"}:
        return value < 1.0
    raise AssertionError(f"unknown bounded evidence slot: {name}")


def _items(queries: dict, values: dict[str, float | None]) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(name, query, values.get(name), threshold, _supports(name, values.get(name)))
        for name, (query, threshold) in queries.items()
    )


def _evidence_unavailable_report(
    profile: TelemetryProfile,
    queries: dict,
    values: dict[str, float | None],
    slot: str,
) -> IncidentReport:
    return IncidentReport(
        "abstain",
        profile.production_id,
        profile.affected_feed,
        None,
        0.0,
        "Required incident evidence is temporarily unavailable; no diagnosis or remediation is permitted.",
        (),
        _items(queries, values),
        unavailable_evidence=(slot,),
    )


def investigate(client: MetricQueryClient, profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE) -> IncidentReport:
    """Collect six fixed semantic metric evidence slots and return a diagnosis.

    Expected evidence-source transport/protocol failures become a structured
    abstention naming only the failed semantic slot. Exception text is never
    copied into the report. Programming/policy errors are deliberately not
    caught and continue to fail loudly.
    """
    queries = investigation_queries(profile)
    values: dict[str, float | None] = {}
    for name, (query, _) in queries.items():
        try:
            values[name] = client.instant(query)
        except EvidenceUnavailable:
            values[name] = None
            return _evidence_unavailable_report(profile, queries, values, name)

    items = _items(queries, values)
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


def investigate_with_log_corroboration(
    metrics: MetricQueryClient,
    logs: LogQueryClient,
    profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE,
) -> IncidentReport:
    """Require one independent bounded Loki corroboration for metric diagnosis."""
    metric_report = investigate(metrics, profile)
    if metric_report.status != "diagnosed":
        return metric_report

    try:
        corroboration = corroborate_uplink_loss(logs, profile)
    except EvidenceUnavailable:
        return IncidentReport(
            "abstain",
            profile.production_id,
            profile.affected_feed,
            None,
            0.0,
            "Required log evidence is temporarily unavailable; no diagnosis or remediation is permitted.",
            (),
            metric_report.evidence,
            None,
            ("causal_log",),
        )

    if corroboration.status != "corroborated":
        missing = ("causal_log",) if corroboration.status == "missing" else ()
        return IncidentReport(
            "abstain",
            profile.production_id,
            profile.affected_feed,
            None,
            0.0,
            "Metric evidence supports the configured uplink hypothesis, but bounded Loki corroboration is unavailable or ambiguous.",
            missing,
            metric_report.evidence,
            corroboration,
        )

    return IncidentReport(
        metric_report.status,
        metric_report.production_id,
        metric_report.affected_feed,
        metric_report.hypothesis,
        metric_report.confidence,
        metric_report.summary + " Loki packet-loss alarm evidence independently corroborates the causal path.",
        metric_report.missing_evidence,
        metric_report.evidence,
        corroboration,
    )
