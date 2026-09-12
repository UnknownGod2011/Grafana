#!/usr/bin/env python3
"""Activation pin for StageGuard's bounded Loki evidence contract."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evidence_errors import EvidenceUnavailable
from log_evidence import DEFAULT_END, DEFAULT_START, MAX_CORROBORATION_LINES, LogQueryClient, uplink_loss_logql
from telemetry import TelemetryProfile

LOG_ACTIVATION_VERSION = 2
DEFAULT_TTL_SECONDS = 24 * 60 * 60
MAX_TTL_SECONDS = 7 * 24 * 60 * 60
_MAX_ACTIVATION_BYTES = 64 * 1024
_MAX_WINDOW_TEXT_LENGTH = 256
_SHA256_HEX_LENGTH = 64


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

    An empty result is valid during a healthy production. Expected evidence-source
    outages are redacted into a stable non-ready result. Programming/policy errors
    intentionally propagate instead of being disguised as telemetry unavailability.
    """
    contract = log_contract_payload(profile)
    try:
        result = client.range(
            contract["logql"],
            start=contract["start"],
            end=contract["end"],
            limit=contract["limit"],
        )
    except EvidenceUnavailable:
        return LogPreflightResult(
            profile.production_id, False, contract["logql"], contract["start"], contract["end"],
            contract["limit"], 0, False, "error", "evidence source unavailable"
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
        "line_count": preflight.line_count,
        "status": preflight.status,
        "truncated": preflight.truncated,
    }
    return _sha256(_canonical_json(payload))


def _validate_window_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > _MAX_WINDOW_TEXT_LENGTH:
        raise ValueError(f"Loki preflight {name} must be a bounded non-empty string")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValueError(f"Loki preflight {name} contains control characters")


def _validate_successful_preflight(profile: TelemetryProfile, preflight: LogPreflightResult) -> None:
    if not preflight.ready or preflight.status != "ok" or preflight.truncated:
        raise ValueError("cannot activate Loki evidence that did not pass preflight")
    if preflight.detail is not None:
        raise ValueError("Loki activation requires an ok preflight without error detail")
    if preflight.production_id != profile.production_id:
        raise ValueError("Loki preflight production does not match telemetry profile")
    expected = log_contract_payload(profile)
    if preflight.query != expected["logql"] or preflight.limit != expected["limit"]:
        raise ValueError("Loki preflight contract does not match current evidence policy")
    if type(preflight.line_count) is not int or not 0 <= preflight.line_count <= expected["limit"]:
        raise ValueError("Loki preflight line_count must be within the bounded query limit")
    _validate_window_text("start", preflight.start)
    _validate_window_text("end", preflight.end)


def _validate_sha256_hex(name: str, value: str) -> None:
    if len(value) != _SHA256_HEX_LENGTH or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"Loki activation.{name} must be a canonical SHA-256 hex digest")


def _validate_record_shape(record: LogActivationRecord) -> None:
    if type(record.version) is not int or record.version != LOG_ACTIVATION_VERSION:
        raise ValueError(f"unsupported Loki activation version: {record.version!r}")
    if not isinstance(record.production_id, str) or not record.production_id.strip():
        raise ValueError("Loki activation.production_id must be a non-empty string")
    if record.production_id != record.production_id.strip():
        raise ValueError("Loki activation.production_id must not contain boundary whitespace")
    for name in ("contract_sha256", "datasource_sha256", "preflight_sha256"):
        value = getattr(record, name)
        if not isinstance(value, str):
            raise ValueError(f"Loki activation.{name} must be a string")
        _validate_sha256_hex(name, value)
    for name in ("created_at_unix", "expires_at_unix"):
        value = getattr(record, name)
        if type(value) is not int:
            raise ValueError(f"Loki activation.{name} must be an integer")
        if value < 0:
            raise ValueError(f"Loki activation.{name} must be non-negative")
    if record.expires_at_unix <= record.created_at_unix:
        raise ValueError("Loki activation expiry must be after creation")
    if record.expires_at_unix - record.created_at_unix > MAX_TTL_SECONDS:
        raise ValueError("Loki activation lifetime exceeds the maximum allowed TTL")


def create_log_activation_record(
    profile: TelemetryProfile,
    datasource_identity: str,
    preflight: LogPreflightResult,
    *,
    now_unix: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> LogActivationRecord:
    _validate_successful_preflight(profile, preflight)
    if type(ttl_seconds) is not int or ttl_seconds <= 0 or ttl_seconds > MAX_TTL_SECONDS:
        raise ValueError(f"ttl_seconds must be an integer between 1 and {MAX_TTL_SECONDS}")
    if now_unix is None:
        created = int(time.time())
    else:
        if type(now_unix) is not int or now_unix < 0:
            raise ValueError("now_unix must be a non-negative integer")
        created = now_unix
    record = LogActivationRecord(
        LOG_ACTIVATION_VERSION,
        profile.production_id,
        log_contract_sha256(profile),
        datasource_sha256(datasource_identity),
        created,
        created + ttl_seconds,
        _preflight_digest(preflight),
    )
    _validate_record_shape(record)
    return record


def write_log_activation_record(path: str | Path, record: LogActivationRecord) -> None:
    _validate_record_shape(record)
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
    try:
        record = LogActivationRecord(**document)
    except TypeError as exc:
        raise ValueError("Loki activation record has invalid field types") from exc
    _validate_record_shape(record)
    return record


def verify_log_activation_record(
    record: LogActivationRecord,
    profile: TelemetryProfile,
    datasource_identity: str,
    *,
    now_unix: int | None = None,
) -> None:
    _validate_record_shape(record)
    if now_unix is None:
        now = int(time.time())
    else:
        if type(now_unix) is not int or now_unix < 0:
            raise ValueError("now_unix must be a non-negative integer")
        now = now_unix
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
