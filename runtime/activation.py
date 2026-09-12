#!/usr/bin/env python3
"""Cryptographically pinned activation records for StageGuard telemetry profiles."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from onboarding import PreflightResult
from telemetry import TelemetryProfile

ACTIVATION_VERSION = 1
DEFAULT_TTL_SECONDS = 24 * 60 * 60
_MAX_ACTIVATION_BYTES = 128 * 1024


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def telemetry_profile_sha256(profile: TelemetryProfile) -> str:
    """Hash the complete validated semantic telemetry mapping."""
    payload = asdict(profile)
    payload["healthy_peer_feeds"] = list(profile.healthy_peer_feeds)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def datasource_sha256(datasource_identity: str) -> str:
    identity = datasource_identity.strip()
    if not identity:
        raise ValueError("datasource_identity is required")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActivationRecord:
    version: int
    production_id: str
    profile_sha256: str
    datasource_sha256: str
    created_at_unix: int
    expires_at_unix: int
    slot_digest_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slot_digest(preflight: PreflightResult) -> str:
    slots = [
        {
            "phase": slot.phase,
            "name": slot.name,
            "promql": slot.promql,
            "status": slot.status,
        }
        for slot in preflight.slots
    ]
    return hashlib.sha256(_canonical_json(slots).encode("utf-8")).hexdigest()


def _validate_successful_preflight(preflight: PreflightResult) -> None:
    if not preflight.ready:
        raise ValueError("cannot activate telemetry that did not pass preflight")
    if len(preflight.slots) != 8:
        raise ValueError("activation requires exactly eight preflight slots")
    for slot in preflight.slots:
        if slot.status != "ok":
            raise ValueError("activation requires all preflight slots to be ok")
        if isinstance(slot.value, bool) or not isinstance(slot.value, (int, float)):
            raise ValueError("activation requires every ok preflight slot to contain a numeric sample")
        if not math.isfinite(float(slot.value)):
            raise ValueError("activation requires every ok preflight slot to contain a finite sample")
        if slot.detail is not None:
            raise ValueError("activation requires ok preflight slots without error detail")


def create_activation_record(
    profile: TelemetryProfile,
    datasource_identity: str,
    preflight: PreflightResult,
    *,
    now_unix: int | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> ActivationRecord:
    """Create an activation record only from a complete successful eight-slot preflight."""
    _validate_successful_preflight(preflight)
    if preflight.production_id != profile.production_id:
        raise ValueError("preflight production does not match telemetry profile")
    if type(ttl_seconds) is not int or ttl_seconds <= 0 or ttl_seconds > 7 * 24 * 60 * 60:
        raise ValueError("ttl_seconds must be an integer between 1 and 604800")
    created = int(time.time()) if now_unix is None else int(now_unix)
    return ActivationRecord(
        version=ACTIVATION_VERSION,
        production_id=profile.production_id,
        profile_sha256=telemetry_profile_sha256(profile),
        datasource_sha256=datasource_sha256(datasource_identity),
        created_at_unix=created,
        expires_at_unix=created + ttl_seconds,
        slot_digest_sha256=_slot_digest(preflight),
    )


def write_activation_record(path: str | Path, record: ActivationRecord) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (_canonical_json(record.to_dict()) + "\n").encode("utf-8")
    if len(payload) > _MAX_ACTIVATION_BYTES:
        raise ValueError("activation record exceeds size limit")
    output.write_bytes(payload)


def load_activation_record(path: str | Path) -> ActivationRecord:
    raw = Path(path).read_bytes()
    if len(raw) > _MAX_ACTIVATION_BYTES:
        raise ValueError("activation record exceeds size limit")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("activation record must be valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("activation record must be a JSON object")
    expected = set(ActivationRecord.__dataclass_fields__)
    unknown = set(document) - expected
    missing = expected - set(document)
    if unknown:
        raise ValueError(f"unknown activation field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing activation field(s): {', '.join(sorted(missing))}")
    try:
        record = ActivationRecord(**document)
    except TypeError as exc:
        raise ValueError("activation record has invalid field types") from exc
    if type(record.version) is not int or record.version != ACTIVATION_VERSION:
        raise ValueError(f"unsupported activation version: {record.version!r}")
    for name in ("production_id", "profile_sha256", "datasource_sha256", "slot_digest_sha256"):
        if not isinstance(getattr(record, name), str):
            raise ValueError(f"activation.{name} must be a string")
    for name in ("created_at_unix", "expires_at_unix"):
        if type(getattr(record, name)) is not int:
            raise ValueError(f"activation.{name} must be an integer")
    return record


def verify_activation_record(
    record: ActivationRecord,
    profile: TelemetryProfile,
    datasource_identity: str,
    *,
    now_unix: int | None = None,
) -> None:
    """Fail closed if a runtime profile/datasource does not match the pinned preflight."""
    now = int(time.time()) if now_unix is None else int(now_unix)
    if record.version != ACTIVATION_VERSION:
        raise ValueError("unsupported activation record version")
    if record.production_id != profile.production_id:
        raise ValueError("activation production does not match telemetry profile")
    if record.profile_sha256 != telemetry_profile_sha256(profile):
        raise ValueError("telemetry profile changed after activation preflight")
    if record.datasource_sha256 != datasource_sha256(datasource_identity):
        raise ValueError("datasource identity changed after activation preflight")
    if now < record.created_at_unix:
        raise ValueError("activation record is not yet valid")
    if now >= record.expires_at_unix:
        raise ValueError("activation record is stale; rerun telemetry preflight")
    if len(record.slot_digest_sha256) != 64:
        raise ValueError("activation slot digest is malformed")
