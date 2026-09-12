#!/usr/bin/env python3
"""Safe configuration loading and activation preflight for StageGuard telemetry.

The onboarding layer maps a versioned local JSON document into the existing
TelemetryProfile contract and proves all bounded semantic evidence slots against
a read-only MetricQueryClient before a profile can be considered active.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Protocol

from evidence_errors import EvidenceUnavailable
from telemetry import TelemetryProfile, investigation_queries, recovery_queries

CONFIG_VERSION = 1
_MAX_CONFIG_BYTES = 64 * 1024
_TOP_LEVEL_FIELDS = {"version", "profile"}
_PROFILE_FIELDS = {field.name for field in fields(TelemetryProfile)}


class MetricQueryClient(Protocol):
    def instant(self, promql: str) -> float | None: ...


@dataclass(frozen=True)
class PreflightSlot:
    phase: str
    name: str
    promql: str
    status: str
    value: float | None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightResult:
    production_id: str
    ready: bool
    slots: tuple[PreflightSlot, ...]

    @property
    def failures(self) -> tuple[PreflightSlot, ...]:
        return tuple(slot for slot in self.slots if slot.status != "ok")

    def to_dict(self) -> dict[str, Any]:
        return {
            "production_id": self.production_id,
            "ready": self.ready,
            "slots": [slot.to_dict() for slot in self.slots],
        }


def _expect_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def load_telemetry_profile(path: str | Path) -> TelemetryProfile:
    """Load one strict versioned profile without accepting extension fields."""
    config_path = Path(path)
    raw = config_path.read_bytes()
    if len(raw) > _MAX_CONFIG_BYTES:
        raise ValueError(f"telemetry config exceeds {_MAX_CONFIG_BYTES} bytes")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("telemetry config must be valid UTF-8 JSON") from exc

    document = _expect_object(document, "telemetry config")
    unknown = set(document) - _TOP_LEVEL_FIELDS
    if unknown:
        raise ValueError(f"unknown telemetry config field(s): {', '.join(sorted(unknown))}")
    missing = _TOP_LEVEL_FIELDS - set(document)
    if missing:
        raise ValueError(f"missing telemetry config field(s): {', '.join(sorted(missing))}")
    if type(document["version"]) is not int or document["version"] != CONFIG_VERSION:
        raise ValueError(f"unsupported telemetry config version: {document['version']!r}")

    profile_data = _expect_object(document["profile"], "profile")
    unknown_profile = set(profile_data) - _PROFILE_FIELDS
    if unknown_profile:
        raise ValueError(f"unknown profile field(s): {', '.join(sorted(unknown_profile))}")
    missing_profile = _PROFILE_FIELDS - set(profile_data)
    if missing_profile:
        raise ValueError(f"missing profile field(s): {', '.join(sorted(missing_profile))}")

    required_string_fields = _PROFILE_FIELDS - {"healthy_peer_feeds"}
    for key in required_string_fields:
        if not isinstance(profile_data[key], str):
            raise ValueError(f"profile.{key} must be a string")

    peers = profile_data["healthy_peer_feeds"]
    if not isinstance(peers, list) or not all(isinstance(item, str) for item in peers):
        raise ValueError("profile.healthy_peer_feeds must be an array of strings")
    profile_data = dict(profile_data)
    profile_data["healthy_peer_feeds"] = tuple(peers)

    return TelemetryProfile(**profile_data)


def preflight_telemetry(client: MetricQueryClient, profile: TelemetryProfile) -> PreflightResult:
    """Execute exactly eight bounded read-only checks and refuse ambiguous evidence.

    Evidence adapters must translate expected transport, protocol, datasource,
    and ambiguity failures into ``EvidenceUnavailable``. Only that expected
    operational failure is converted into a non-ready slot. Its exception text
    is deliberately not copied into the result because provider messages may
    contain URLs, credentials, or other sensitive integration details.

    Programming and policy errors are not swallowed here: unexpected exceptions
    propagate so broken onboarding code cannot be mistaken for ordinary telemetry
    unavailability.
    """
    checks: list[tuple[str, str, str]] = []
    checks.extend(
        ("investigation", name, query)
        for name, (query, _expectation) in investigation_queries(profile).items()
    )
    checks.extend(
        ("recovery", name, query)
        for name, (query, _threshold) in recovery_queries(profile).items()
    )
    if len(checks) != 8:
        raise RuntimeError("telemetry preflight contract must contain exactly eight checks")

    slots: list[PreflightSlot] = []
    for phase, name, promql in checks:
        try:
            value = client.instant(promql)
        except EvidenceUnavailable:
            slots.append(
                PreflightSlot(
                    phase=phase,
                    name=name,
                    promql=promql,
                    status="error",
                    value=None,
                    detail="evidence source unavailable",
                )
            )
            continue
        if value is None:
            slots.append(
                PreflightSlot(
                    phase=phase,
                    name=name,
                    promql=promql,
                    status="missing",
                    value=None,
                    detail="query returned no sample",
                )
            )
        else:
            slots.append(
                PreflightSlot(
                    phase=phase,
                    name=name,
                    promql=promql,
                    status="ok",
                    value=float(value),
                )
            )

    frozen_slots = tuple(slots)
    return PreflightResult(
        production_id=profile.production_id,
        ready=all(slot.status == "ok" for slot in frozen_slots),
        slots=frozen_slots,
    )
