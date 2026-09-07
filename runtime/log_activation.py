#!/usr/bin/env python3
"""Activation pin for StageGuard's bounded Loki evidence contract."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from log_evidence import DEFAULT_END, DEFAULT_START, MAX_CORROBORATION_LINES, LogQueryClient, uplink_loss_logql
from telemetry import TelemetryProfile

LOG_ACTIVATION_VERSION = 1
DEFAULT_TTL_SECONDS = 24 * 60 * 60
_MAX_ACTIVATION_BYTES = 64 * 1024


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def log_contract_payload(profile: TelemetryProfile) -> dict[str, Any]:
    """Return the exact policy-owned Loki contract that production will execute."""
    return {
        "logql": uplink_loss_logql(profile),
        "start": DEFAULT_START,
        "end": DEFAULT_END,
        "limit": MAX_CORROBORATION_LINES,
        "evidence_class": "causal_log",
        "required_event": "packet_loss_alarm",
        "production_id": profile.production_id,
        "affected_uplink": profile.affected_uplink,
    }


def log_contract_sha256(profile: TelemetryProfile) -> str:
    return _sha256(_canonical_json(log_contract_payload(profile)))


def datasource_sha256(datasource_identity: str) -> str:
    identity = datasource_identity.strip()
    if not identity:
        raise ValueError("Loki datasource identity is required")
    return _sha256(identity)


@dataclass(frozen=True)
class LogPreflightResult:
    production_id: str
    ready: bool
    query: str
    start: str
    end: str
    limit: int
    line_count: int
    truncated: bool
    status: str
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LogActivationRecord:
    version: int
    production_id: str
    contract_sha256: str
    datasource_sha256: str
    created_at_unix: int
    expires_at_unix: int
    preflight_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preflight_loki(client: LogQueryClient, profile: TelemetryProfile) -> LogPreflightResult:
    """Execute one bounded causal query and validate the evidence plane without requiring an incident.

    An empty result is valid during a healthy production. Truncation, malformed scope,
    or a returned event outside the configured production/uplink contract fails closed.
    """
    contract = log_contract_payload(profile)
    try:
        result = client.range(
            contract["logql"],
            start=contract["start"],
            end=contract["end"],
            limit=contract["limit"],
        )
    except Exception as exc:
        return LogPreflightResult(
            profile.production_id, False, contract["logql"], contract["start"], contract["end"],
            contract["limit"], 0, False, "error", f"{type(exc).__name__}: {exc}"
        )

    if result.truncated:
        return LogPreflightResult(
            profile.production_id, False, contract["logql"], result.start, result.end,
            contract["limit"], len(result.records), True, "ambiguous",
            "Loki preflight result was truncated"
        )

    for record in result.records:
        if record.labels.get(profile.production_label) != profile.production_id:
            return LogPreflightResult(
                profile.production_id, False, contract["logql"], result.start, result.end,
                contract["limit"], len(result.records), False, "ambiguous",
                "returned Loki record drifted from configured production scope"
            )
        if record.labels.get(profile.uplink_label) != profile.affected_uplink:
            return LogPreflightResult(
                profile.production_id, False, contract["logql"], result.start, result.end,
                contract["limit"], len(result.records), False, "ambiguous",
                "returned Loki record drifted from configured uplink scope"
            )

    return LogPreflightResult(
        profile.production_id, True, contract["logql"], result.start, result.end,
        contract["limit"], len(result.records), False, "ok"
    )


def _preflight_digest(preflight: LogPreflightResult) -> str:
    payload = {
        "production_id": preflight.production_id,
        "query": preflight.query,
        "start": preflight.start,
        "end": preflight.end,
        "limit": preflight.limit,
        "status": preflight.status,
        "truncated": preflight.truncated,
    }
    return _sha256(_canonical_json(payload))


def create_log_activation_record(
    profile: TelemetryProfile,
    datasource_identity: str,
    preflight: LogPreflightResult,
    *,
    now_unix: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> LogActivationRecord:
    if not preflight.ready or preflight.status != "ok" or preflight.truncated:
        raise ValueError("cannot activate Loki evidence that did not pass preflight")
    if preflight.production_id != profile.production_id:
        raise ValueError("Loki preflight production does not match telemetry profile")
    expected = log_contract_payload(profile)
    if (preflight.query, preflight.limit) != (expected["logql"], expected["limit"]):
        raise ValueError("Loki preflight contract does not match current evidence policy")
    if type(ttl_seconds) is not int or ttl_seconds <= 0 or ttl_seconds > 7 * 24 * 60 * 60:
        raise ValueError("ttl_seconds must be an integer between 1 and 604800")
    created = int(time.time()) if now_unix is None else int(now_unix)
    return LogActivationRecord(
        LOG_ACTIVATION_VERSION,
        profile.production_id,
        log_contract_sha256(profile),
        datasource_sha256(datasource_identity),
        created,
        created + ttl_seconds,
        _preflight_digest(preflight),
    )


def write_log_activation_record(path: str | Path, record: LogActivationRecord) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(record.to_dict()) + "\n").encode("utf-8")
    if len(payload) > _MAX_ACTIVATION_BYTES:
        raise ValueError("Loki activation record exceeds size limit")
    output.write_bytes(payload)


def load_log_activation_record(path: str | Path) -> LogActivationRecord:
    raw = Path(path).read_bytes()
    if len(raw) > _MAX_ACTIVATION_BYTES:
        raise ValueError("Loki activation record exceeds size limit")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Loki activation record must be valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("Loki activation record must be a JSON object")
    expected = set(LogActivationRecord.__dataclass_fields__)
    if set(document) != expected:
        raise ValueError("Loki activation record fields do not match the current schema")
    record = LogActivationRecord(**document)
    if record.version != LOG_ACTIVATION_VERSION:
        raise ValueError("unsupported Loki activation version")
    return record


def verify_log_activation_record(
    record: LogActivationRecord,
    profile: TelemetryProfile,
    datasource_identity: str,
    *,
    now_unix: int | None = None,
) -> None:
    now = int(time.time()) if now_unix is None else int(now_unix)
    if record.version != LOG_ACTIVATION_VERSION:
        raise ValueError("unsupported Loki activation version")
    if record.production_id != profile.production_id:
        raise ValueError("Loki activation production does not match telemetry profile")
    if record.contract_sha256 != log_contract_sha256(profile):
        raise ValueError("Loki evidence contract changed after activation preflight")
    if record.datasource_sha256 != datasource_sha256(datasource_identity):
        raise ValueError("Loki datasource identity changed after activation preflight")
    if now < record.created_at_unix:
        raise ValueError("Loki activation record is not yet valid")
    if now >= record.expires_at_unix:
        raise ValueError("Loki activation record is stale; rerun evidence preflight")
    if len(record.preflight_sha256) != 64:
        raise ValueError("Loki activation preflight digest is malformed")
