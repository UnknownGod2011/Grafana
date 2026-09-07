#!/usr/bin/env python3
"""Narrow restart-safe reader for StageGuard lifecycle audit entries."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol

from cloud_audit import audit_event_document
from incident_service import AuditEvent

MAX_READ_RESULTS = 101
DEFAULT_LOOKBACK_SECONDS = 24 * 60 * 60
MAX_LOOKBACK_SECONDS = 7 * 24 * 60 * 60


class EntryReader(Protocol):
    @property
    def full_name(self) -> str: ...

    def list_entries(
        self,
        *,
        filter_: str | None = None,
        order_by: str | None = None,
        max_results: int | None = None,
        page_size: int | None = None,
    ): ...


def _literal(value: str, *, max_bytes: int, field: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} must be a bounded non-empty string")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{escaped}"'


def _rfc3339(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_document(document: object, incident_id: str) -> AuditEvent:
    if not isinstance(document, Mapping):
        raise ValueError("audit entry payload must be a mapping")
    expected = {"schema", "sequence", "timestamp_unix_ms", "incident_id", "event_type", "actor", "payload"}
    if set(document) != expected:
        raise ValueError("audit entry has an unexpected document shape")
    if document.get("schema") != "stageguard.audit.v1" or document.get("incident_id") != incident_id:
        raise ValueError("audit entry does not match the requested StageGuard incident")

    sequence = document.get("sequence")
    timestamp_ms = document.get("timestamp_unix_ms")
    event_type = document.get("event_type")
    actor = document.get("actor")
    payload = document.get("payload")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError("audit sequence must be an integer")
    if not isinstance(timestamp_ms, int) or isinstance(timestamp_ms, bool):
        raise ValueError("audit timestamp must be an integer")
    if not isinstance(event_type, str) or not isinstance(actor, str) or not isinstance(payload, Mapping):
        raise ValueError("audit lifecycle fields are invalid")

    event = AuditEvent(sequence, timestamp_ms, incident_id, event_type, actor, dict(payload))
    audit_event_document(event)
    return event


class GoogleCloudAuditReader:
    """Read only one incident's audit-v1 entries from one configured logger."""

    def __init__(
        self,
        logger: EntryReader,
        *,
        lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ) -> None:
        if not isinstance(lookback_seconds, int) or isinstance(lookback_seconds, bool):
            raise ValueError("audit lookback must be an integer")
        if not 60 <= lookback_seconds <= MAX_LOOKBACK_SECONDS:
            raise ValueError("audit lookback must be between 60 seconds and 7 days")
        full_name = getattr(logger, "full_name", "")
        if not isinstance(full_name, str) or not full_name:
            raise ValueError("audit logger must expose its fully qualified log name")
        self._logger = logger
        self._log_literal = _literal(full_name, max_bytes=1024, field="log name")
        self._lookback_seconds = lookback_seconds
        self._clock_ms = clock_ms

    @classmethod
    def from_environment(
        cls,
        *,
        project: str | None = None,
        log_name: str = "stageguard-audit",
        lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
    ) -> "GoogleCloudAuditReader":
        normalized_name = log_name.strip()
        if not normalized_name or len(normalized_name) > 128:
            raise ValueError("Cloud Logging log name must be a bounded string")
        try:
            from google.cloud import logging as cloud_logging
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("google-cloud-logging is required for durable audit reads") from exc
        client = cloud_logging.Client(project=project or None)
        return cls(client.logger(normalized_name), lookback_seconds=lookback_seconds)

    def read(self, *, incident_id: str, after_sequence: int = 0, limit: int = 50) -> list[AuditEvent]:
        incident_literal = _literal(incident_id, max_bytes=256, field="incident_id")
        if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
            raise ValueError("after_sequence must be a non-negative integer")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_READ_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_READ_RESULTS}")

        now_ms = self._clock_ms()
        if not isinstance(now_ms, int) or isinstance(now_ms, bool) or now_ms < 0:
            raise RuntimeError("audit reader clock returned an invalid timestamp")
        cutoff_ms = max(0, now_ms - self._lookback_seconds * 1000)
        filter_ = " AND ".join(
            (
                f"logName={self._log_literal}",
                'jsonPayload.schema="stageguard.audit.v1"',
                f"jsonPayload.incident_id={incident_literal}",
                f"jsonPayload.sequence>{after_sequence}",
                f'timestamp>="{_rfc3339(cutoff_ms)}"',
            )
        )
        entries = self._logger.list_entries(
            filter_=filter_, order_by="ASCENDING", max_results=limit, page_size=min(limit, 100)
        )

        by_sequence: dict[int, AuditEvent] = {}
        for entry in entries:
            event = _parse_document(getattr(entry, "payload", None), incident_id)
            if event.timestamp_unix_ms < cutoff_ms or event.timestamp_unix_ms > now_ms + 60_000:
                raise ValueError("audit entry timestamp is outside the bounded read window")
            if event.sequence <= after_sequence:
                raise ValueError("audit entry sequence violated the requested lower bound")
            prior = by_sequence.get(event.sequence)
            if prior is not None and prior != event:
                raise ValueError("conflicting audit events share one sequence")
            by_sequence[event.sequence] = event
            if len(by_sequence) >= limit:
                break
        return [by_sequence[sequence] for sequence in sorted(by_sequence)]
