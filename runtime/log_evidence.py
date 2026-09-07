#!/usr/bin/env python3
"""Bounded semantic Loki corroboration for StageGuard diagnoses.

Callers never provide raw LogQL. A validated telemetry profile is converted into
one narrow causal log query, and the result must be complete and internally
consistent before it can corroborate an uplink-loss diagnosis.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol

from telemetry import TelemetryProfile, _label_value

MAX_CORROBORATION_LINES = 8
DEFAULT_START = "now-5m"
DEFAULT_END = "now"
_EVENT_FIELD = "event"
_PACKET_LOSS_EVENT = "packet_loss_alarm"


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    line: str
    labels: dict[str, str]
    structured_metadata: dict[str, str]
    parsed: dict[str, str]


@dataclass(frozen=True)
class LogQueryResult:
    records: tuple[LogRecord, ...]
    truncated: bool
    start: str
    end: str


class LogQueryClient(Protocol):
    def range(
        self,
        logql: str,
        *,
        start: str,
        end: str,
        limit: int,
    ) -> LogQueryResult: ...


@dataclass(frozen=True)
class LogCorroboration:
    status: str
    evidence_class: str
    query: str
    start: str
    end: str
    line_count: int
    supports_hypothesis: bool | None
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def uplink_loss_logql(profile: TelemetryProfile) -> str:
    """Build the one policy-owned causal LogQL query used by StageGuard.

    The stream selector is constrained by the same production/uplink bindings
    used for metrics. JSON parsing plus an equality filter requires an explicit
    machine event rather than free-text keyword matching.
    """
    production = _label_value(profile.production_id)
    uplink = _label_value(profile.affected_uplink)
    event = _label_value(_PACKET_LOSS_EVENT)
    return (
        f'{{{profile.production_label}="{production}",{profile.uplink_label}="{uplink}"}} '
        f'| json | {_EVENT_FIELD}="{event}"'
    )


def _event_from_record(record: LogRecord) -> str | None:
    parsed_event = record.parsed.get(_EVENT_FIELD)
    if parsed_event is not None:
        return parsed_event
    metadata_event = record.structured_metadata.get(_EVENT_FIELD)
    if metadata_event is not None:
        return metadata_event
    try:
        payload = json.loads(record.line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get(_EVENT_FIELD)
    return value if isinstance(value, str) else None


def corroborate_uplink_loss(
    client: LogQueryClient,
    profile: TelemetryProfile,
    *,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
) -> LogCorroboration:
    """Require complete, scope-consistent packet-loss alarm logs.

    Missing logs are treated as missing corroboration rather than evidence that
    the hypothesis is false. Truncation or scope/event disagreement is
    ambiguous and must fail closed at the orchestration layer.
    """
    query = uplink_loss_logql(profile)
    result = client.range(
        query,
        start=start,
        end=end,
        limit=MAX_CORROBORATION_LINES,
    )

    if result.truncated:
        return LogCorroboration(
            "ambiguous",
            "causal_log",
            query,
            result.start,
            result.end,
            len(result.records),
            None,
            "Loki reported a truncated result set; bounded corroboration is incomplete.",
        )
    if not result.records:
        return LogCorroboration(
            "missing",
            "causal_log",
            query,
            result.start,
            result.end,
            0,
            None,
            "No packet-loss alarm log was found in the bounded corroboration window.",
        )

    for record in result.records:
        production = record.labels.get(profile.production_label)
        uplink = record.labels.get(profile.uplink_label)
        if production != profile.production_id or uplink != profile.affected_uplink:
            return LogCorroboration(
                "ambiguous",
                "causal_log",
                query,
                result.start,
                result.end,
                len(result.records),
                None,
                "A returned log record disagreed with the configured production/uplink scope.",
            )
        if _event_from_record(record) != _PACKET_LOSS_EVENT:
            return LogCorroboration(
                "ambiguous",
                "causal_log",
                query,
                result.start,
                result.end,
                len(result.records),
                None,
                "A returned log record did not carry the required packet-loss event identity.",
            )

    return LogCorroboration(
        "corroborated",
        "causal_log",
        query,
        result.start,
        result.end,
        len(result.records),
        True,
        "Bounded Loki evidence independently corroborates the affected-uplink packet-loss alarm.",
    )
