#!/usr/bin/env python3
"""Audited StageGuard incident lifecycle orchestration."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from investigator import IncidentReport, MetricQueryClient, investigate
from remediation import Approval, RemediationClient, RemediationOutcome, remediate_and_verify, required_approval
from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile


class AuditSink(Protocol):
    def append(self, event: "AuditEvent") -> None: ...


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    timestamp_unix_ms: int
    incident_id: str
    event_type: str
    actor: str
    payload: dict


class MemoryAuditLog:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)


class JsonlAuditLog:
    """Append-only local-development audit sink with owner-only permissions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.close(fd)

    def append(self, event: AuditEvent) -> None:
        line = json.dumps(asdict(event), sort_keys=True, separators=(",", ":")) + "\n"
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)


@dataclass(frozen=True)
class IncidentSnapshot:
    incident_id: str
    revision: str
    report: IncidentReport
    approval: Approval | None
    outcome: RemediationOutcome | None

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "revision": self.revision,
            "report": self.report.to_dict(),
            "approval": None if self.approval is None else asdict(self.approval),
            "outcome": None if self.outcome is None else self.outcome.to_dict(),
        }


def _revision(report: IncidentReport) -> str:
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class IncidentService:
    """Single-profile incident lifecycle with fail-closed approval semantics."""

    def __init__(
        self,
        metrics: MetricQueryClient,
        remediation: RemediationClient,
        audit: AuditSink,
        *,
        telemetry_profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        recovery_sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._metrics = metrics
        self._remediation = remediation
        self._audit = audit
        self._profile = telemetry_profile
        self._clock_ms = clock_ms
        self._id_factory = id_factory
        self._recovery_sleep = recovery_sleep
        self._snapshot: IncidentSnapshot | None = None
        self._sequence = 0
        self._lock = threading.RLock()

    def _record(self, incident_id: str, event_type: str, actor: str, payload: dict) -> None:
        self._sequence += 1
        self._audit.append(AuditEvent(self._sequence, self._clock_ms(), incident_id, event_type, actor, payload))

    def status(self) -> IncidentSnapshot | None:
        with self._lock:
            return self._snapshot

    def investigate(self, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            report = investigate(self._metrics, self._profile)
            incident_id = self._snapshot.incident_id if self._snapshot is not None else self._id_factory()
            snapshot = IncidentSnapshot(incident_id, _revision(report), report, None, None)
            self._snapshot = snapshot
            self._record(incident_id, "investigation_completed", actor.strip() or "stageguard",
                {"revision": snapshot.revision, "status": report.status, "confidence": report.confidence})
            return snapshot

    def approve(self, *, incident_id: str, revision: str, approved_by: str) -> IncidentSnapshot:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                raise RuntimeError("no incident has been investigated")
            if incident_id != snapshot.incident_id or revision != snapshot.revision:
                raise ValueError("approval does not match the current incident evidence revision")
            actor = approved_by.strip()
            if not actor:
                raise ValueError("approved_by is required")
            if snapshot.report.status != "diagnosed":
                raise ValueError("only a diagnosed incident can be approved for remediation")
            approval = required_approval(snapshot.report, actor, True, self._profile)
            self._snapshot = IncidentSnapshot(snapshot.incident_id, snapshot.revision, snapshot.report, approval, None)
            self._record(snapshot.incident_id, "remediation_approved", actor,
                {"revision": snapshot.revision, "action": approval.action, "target": approval.target})
            return self._snapshot

    def execute_approved(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                raise RuntimeError("matching explicit approval is required before remediation")
            if snapshot.outcome is not None:
                raise RuntimeError("this approval has already been consumed")
            outcome = remediate_and_verify(snapshot.report, snapshot.approval, self._remediation, self._metrics,
                profile=self._profile, sleep=self._recovery_sleep)
            self._snapshot = IncidentSnapshot(snapshot.incident_id, snapshot.revision, snapshot.report,
                snapshot.approval, outcome)
            self._record(snapshot.incident_id, "remediation_completed", actor.strip() or "stageguard",
                {"revision": snapshot.revision, "status": outcome.status, "sample_count": len(outcome.samples),
                 "action_accepted": bool(outcome.action_result and outcome.action_result.accepted)})
            return self._snapshot
