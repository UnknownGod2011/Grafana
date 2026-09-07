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

from activation import ActivationRecord, verify_activation_record
from gemini_commander import GeminiCommander, IncidentBriefing
from investigator import IncidentReport, MetricQueryClient, investigate, investigate_with_log_corroboration
from log_activation import LogActivationRecord
from log_evidence import LogQueryClient
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


def _briefing_digest(briefing: IncidentBriefing) -> str:
    canonical = json.dumps(briefing.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IncidentService:
    """Single-profile incident lifecycle with fail-closed approval semantics.

    The built-in deterministic demo profile may run without activation artifacts.
    Every non-default production mapping must present a matching metric activation
    record. Canonical production bootstrap also injects a verified Loki client and
    log activation, making correlated investigation mandatory there. Gemini, when
    configured, is advisory only and can brief only the exact current revision.
    """

    def __init__(
        self,
        metrics: MetricQueryClient,
        remediation: RemediationClient,
        audit: AuditSink,
        *,
        telemetry_profile: TelemetryProfile = DEFAULT_TELEMETRY_PROFILE,
        activation_record: ActivationRecord | None = None,
        datasource_identity: str | None = None,
        logs: LogQueryClient | None = None,
        log_activation_record: LogActivationRecord | None = None,
        commander: GeminiCommander | None = None,
        activation_now_unix: int | None = None,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        recovery_sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        is_demo_profile = telemetry_profile == DEFAULT_TELEMETRY_PROFILE
        if not is_demo_profile:
            if activation_record is None or datasource_identity is None:
                raise ValueError(
                    "non-default telemetry profiles require a successful activation preflight record"
                )
            verify_activation_record(
                activation_record,
                telemetry_profile,
                datasource_identity,
                now_unix=activation_now_unix,
            )
        elif activation_record is not None:
            if datasource_identity is None:
                raise ValueError("datasource_identity is required when activation_record is supplied")
            verify_activation_record(
                activation_record,
                telemetry_profile,
                datasource_identity,
                now_unix=activation_now_unix,
            )

        if (logs is None) != (log_activation_record is None):
            raise ValueError("logs and log_activation_record must be configured together")

        self._metrics = metrics
        self._logs = logs
        self._remediation = remediation
        self._audit = audit
        self._profile = telemetry_profile
        self._activation = activation_record
        self._log_activation = log_activation_record
        self._commander = commander
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
            if self._logs is None:
                report = investigate(self._metrics, self._profile)
            else:
                report = investigate_with_log_corroboration(self._metrics, self._logs, self._profile)
            incident_id = self._snapshot.incident_id if self._snapshot is not None else self._id_factory()
            snapshot = IncidentSnapshot(incident_id, _revision(report), report, None, None)
            self._snapshot = snapshot
            payload = {
                "revision": snapshot.revision,
                "status": report.status,
                "confidence": report.confidence,
                "evidence_mode": "metric+loki" if self._logs is not None else "metric-only",
            }
            if self._activation is not None:
                payload["activation_profile_sha256"] = self._activation.profile_sha256
                payload["activation_datasource_sha256"] = self._activation.datasource_sha256
            if self._log_activation is not None:
                payload["log_activation_contract_sha256"] = self._log_activation.contract_sha256
                payload["log_activation_datasource_sha256"] = self._log_activation.datasource_sha256
                payload["log_activation_preflight_sha256"] = self._log_activation.preflight_sha256
            self._record(
                incident_id,
                "investigation_completed",
                actor.strip() or "stageguard",
                payload,
            )
            return snapshot

    def briefing(
        self,
        *,
        incident_id: str,
        revision: str,
        actor: str = "stageguard",
    ) -> IncidentBriefing:
        """Generate an advisory briefing for exactly the current evidence revision.

        The model call executes while holding the lifecycle lock. A concurrent
        investigation therefore cannot advance the revision between validation and
        generation. No incident, approval, remediation, or recovery state is changed.
        """
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                raise RuntimeError("no incident has been investigated")
            if incident_id != snapshot.incident_id or revision != snapshot.revision:
                raise ValueError("briefing request does not match the current incident evidence revision")
            if self._commander is None:
                raise RuntimeError("Gemini briefing is not configured")

            normalized_actor = actor.strip() or "stageguard"
            try:
                briefing = self._commander.brief(snapshot.report)
            except Exception as exc:
                self._record(
                    snapshot.incident_id,
                    "briefing_failed",
                    normalized_actor,
                    {
                        "revision": snapshot.revision,
                        "error_type": type(exc).__name__,
                    },
                )
                raise RuntimeError("Gemini briefing generation failed") from exc

            self._record(
                snapshot.incident_id,
                "briefing_generated",
                normalized_actor,
                {
                    "revision": snapshot.revision,
                    "briefing_sha256": _briefing_digest(briefing),
                    "next_step": briefing.next_step,
                },
            )
            return briefing

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
            self._record(
                snapshot.incident_id,
                "remediation_approved",
                actor,
                {"revision": snapshot.revision, "action": approval.action, "target": approval.target},
            )
            return self._snapshot

    def execute_approved(self, *, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                raise RuntimeError("matching explicit approval is required before remediation")
            if snapshot.outcome is not None:
                raise RuntimeError("this approval has already been consumed")
            outcome = remediate_and_verify(
                snapshot.report,
                snapshot.approval,
                self._remediation,
                self._metrics,
                profile=self._profile,
                sleep=self._recovery_sleep,
            )
            self._snapshot = IncidentSnapshot(
                snapshot.incident_id,
                snapshot.revision,
                snapshot.report,
                snapshot.approval,
                outcome,
            )
            payload = {
                "revision": snapshot.revision,
                "status": outcome.status,
                "sample_count": len(outcome.samples),
                "action_accepted": bool(outcome.action_result and outcome.action_result.accepted),
            }
            if outcome.action_result is not None and outcome.action_result.metadata:
                payload["action_metadata"] = dict(outcome.action_result.metadata)
            self._record(
                snapshot.incident_id,
                "remediation_completed",
                actor.strip() or "stageguard",
                payload,
            )
            return self._snapshot
