#!/usr/bin/env python3
"""Durable structured audit sink for Google Cloud Logging.

The sink receives already-governed ``AuditEvent`` objects from IncidentService,
re-validates their serialized shape/size, and writes one structured entry per
lifecycle event. It never accepts arbitrary log text, evidence bodies, prompts,
queries, or credentials.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Mapping, Protocol

from incident_service import AuditEvent


MAX_AUDIT_ENTRY_BYTES = 16 * 1024
MAX_AUDIT_PAYLOAD_KEYS = 32
_BLOCKED_KEY_FRAGMENTS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "promql",
    "logql",
    "raw_log",
    "log_body",
    "prompt",
    "endpoint",
)


class StructuredLogger(Protocol):
    def log_struct(self, info: Mapping[str, object], *, severity: str = "NOTICE") -> None: ...


def _validate_payload(payload: Mapping[str, object]) -> dict[str, object]:
    if len(payload) > MAX_AUDIT_PAYLOAD_KEYS:
        raise ValueError("audit payload has too many fields")
    clean: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            raise ValueError("audit payload keys must be bounded strings")
        lowered = key.lower()
        if any(fragment in lowered for fragment in _BLOCKED_KEY_FRAGMENTS):
            raise ValueError(f"audit payload key is not permitted: {key}")
        if isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
            raise ValueError(f"nested or binary audit payload is not permitted: {key}")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"unsupported audit payload value: {key}")
        if isinstance(value, str) and len(value.encode("utf-8")) > 2048:
            raise ValueError(f"audit payload value is too large: {key}")
        clean[key] = value
    return clean


def audit_event_document(event: AuditEvent) -> dict[str, object]:
    """Return the bounded structured document written to Cloud Logging."""
    if event.sequence < 1 or event.timestamp_unix_ms < 0:
        raise ValueError("invalid audit sequence or timestamp")
    if not event.incident_id or len(event.incident_id.encode("utf-8")) > 256:
        raise ValueError("invalid audit incident_id")
    if not event.event_type or len(event.event_type.encode("utf-8")) > 128:
        raise ValueError("invalid audit event_type")
    if not event.actor or len(event.actor.encode("utf-8")) > 512:
        raise ValueError("invalid audit actor")

    document: dict[str, object] = {
        "schema": "stageguard.audit.v1",
        "sequence": event.sequence,
        "timestamp_unix_ms": event.timestamp_unix_ms,
        "incident_id": event.incident_id,
        "event_type": event.event_type,
        "actor": event.actor,
        "payload": _validate_payload(event.payload),
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_AUDIT_ENTRY_BYTES:
        raise ValueError("audit entry is too large")
    return document


class GoogleCloudLoggingAuditSink:
    """Append StageGuard lifecycle events to one Google Cloud Logging log.

    Construction is credential-optional until this sink is explicitly selected.
    Production normally uses ADC attached to the Cloud Run service account.
    """

    def __init__(self, logger: StructuredLogger) -> None:
        self._logger = logger

    @classmethod
    def from_environment(
        cls,
        *,
        project: str | None = None,
        log_name: str = "stageguard-audit",
    ) -> "GoogleCloudLoggingAuditSink":
        normalized_name = log_name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise ValueError("Cloud Logging log name must be a bounded string")
        try:
            from google.cloud import logging as cloud_logging
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("google-cloud-logging is required for Cloud Logging audit") from exc
        client = cloud_logging.Client(project=project or None)
        return cls(client.logger(normalized_name))

    def append(self, event: AuditEvent) -> None:
        # log_struct creates a discrete Cloud Logging entry. Cloud Logging sinks
        # can then route this dedicated log to long-retention/locked storage.
        self._logger.log_struct(audit_event_document(event), severity="NOTICE")
