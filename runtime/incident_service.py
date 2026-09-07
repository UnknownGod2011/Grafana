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
from incident_checkpoint import CheckpointConflictError, CheckpointStore, IncidentCheckpoint
from investigator import IncidentReport, MetricQueryClient, investigate, investigate_with_log_corroboration
from log_activation import LogActivationRecord
from log_evidence import LogQueryClient
from remediation import Approval, RemediationClient, RemediationOutcome, remediate_and_verify, required_approval
from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile


class AuditSink(Protocol):
    def append(self, event: "AuditEvent") -> None: ...


class AuditReader(Protocol):
    def read(self, *, incident_id: str, after_sequence: int = 0, limit: int = 50) -> list["AuditEvent"]: ...


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


_TIMELINE_PAYLOAD_FIELDS = {
    "investigation_completed": ("revision", "status", "confidence", "evidence_mode"),
    "briefing_generated": ("revision", "briefing_sha256", "next_step"),
    "briefing_failed": ("revision", "error_type"),
    "remediation_approved": ("revision", "action"),
    "remediation_completed": ("revision", "status", "sample_count", "action_accepted"),
}
_MAX_TIMELINE_EVENTS = 512


def _actor_fingerprint(actor: str) -> str:
    return hashlib.sha256(actor.encode("utf-8")).hexdigest()[:12]


def _timeline_event(event: AuditEvent) -> dict[str, object]:
    allowed = _TIMELINE_PAYLOAD_FIELDS.get(event.event_type, ())
    payload = {key: event.payload[key] for key in allowed if key in event.payload}
    return {
        "sequence": event.sequence,
        "timestamp_unix_ms": event.timestamp_unix_ms,
        "event_type": event.event_type,
        "actor_ref": _actor_fingerprint(event.actor),
        "payload": payload,
    }


def _revision(report: IncidentReport) -> str:
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _briefing_digest(briefing: IncidentBriefing) -> str:
    canonical = json.dumps(briefing.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IncidentService:
    """Single-profile incident lifecycle with fail-closed approval semantics."""

    def __init__(
        self,
        metrics: MetricQueryClient,
        remediation: RemediationClient,
        audit: AuditSink,
        *,
        audit_reader: AuditReader | None = None,
        checkpoint_store: CheckpointStore | None = None,
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
                raise ValueError("non-default telemetry profiles require a successful activation preflight record")
            verify_activation_record(activation_record, telemetry_profile, datasource_identity, now_unix=activation_now_unix)
        elif activation_record is not None:
            if datasource_identity is None:
                raise ValueError("datasource_identity is required when activation_record is supplied")
            verify_activation_record(activation_record, telemetry_profile, datasource_identity, now_unix=activation_now_unix)
        if (logs is None) != (log_activation_record is None):
            raise ValueError("logs and log_activation_record must be configured together")

        self._metrics = metrics
        self._logs = logs
        self._remediation = remediation
        self._audit = audit
        self._audit_reader = audit_reader
        self._checkpoint_store = checkpoint_store
        self._profile = telemetry_profile
        self._activation = activation_record
        self._log_activation = log_activation_record
        self._commander = commander
        self._clock_ms = clock_ms
        self._id_factory = id_factory
        self._recovery_sleep = recovery_sleep
        self._snapshot: IncidentSnapshot | None = None
        self._sequence = 0
        self._timeline: list[AuditEvent] = []
        self._checkpoint_conflicted = False
        self._lock = threading.RLock()
        self._restore_checkpoint()

    def _validated_snapshot(self, checkpoint: IncidentCheckpoint) -> IncidentSnapshot:
        if checkpoint.revision != _revision(checkpoint.report):
            raise ValueError("incident checkpoint revision does not match restored evidence")
        if checkpoint.report.production_id != self._profile.production_id or checkpoint.report.affected_feed != self._profile.affected_feed:
            raise ValueError("incident checkpoint does not match configured telemetry scope")
        approval = checkpoint.approval
        if approval is not None:
            expected = required_approval(checkpoint.report, approval.approved_by, True, self._profile)
            if approval != expected:
                raise ValueError("incident checkpoint approval does not match restored evidence revision")
        if checkpoint.outcome is not None and approval is None:
            raise ValueError("incident checkpoint outcome cannot exist without approval")
        return IncidentSnapshot(
            checkpoint.incident_id, checkpoint.revision, checkpoint.report, checkpoint.approval, checkpoint.outcome
        )

    def _apply_checkpoint(self, checkpoint: IncidentCheckpoint) -> None:
        snapshot = self._validated_snapshot(checkpoint)
        sequence = checkpoint.sequence
        if self._audit_reader is not None:
            durable = self._audit_reader.read(incident_id=checkpoint.incident_id, after_sequence=0, limit=101)
            if durable:
                sequence = max(sequence, max(event.sequence for event in durable))
        self._snapshot = snapshot
        self._sequence = sequence

    def _restore_checkpoint(self) -> None:
        if self._checkpoint_store is None:
            return
        checkpoint = self._checkpoint_store.load()
        if checkpoint is None:
            return
        self._apply_checkpoint(checkpoint)

    def _require_checkpoint_consistency(self) -> None:
        if self._checkpoint_conflicted:
            raise RuntimeError("checkpoint conflict requires explicit reload before lifecycle changes")

    def checkpoint_state(self) -> str:
        with self._lock:
            if self._checkpoint_store is None:
                return "disabled"
            return "conflicted" if self._checkpoint_conflicted else "synchronized"

    def reload_checkpoint_after_conflict(self) -> IncidentSnapshot:
        """Explicitly adopt and revalidate the winning durable checkpoint after CAS contention."""
        with self._lock:
            if self._checkpoint_store is None:
                raise RuntimeError("checkpoint persistence is not configured")
            if not self._checkpoint_conflicted:
                raise RuntimeError("checkpoint reload is only permitted after a conflict")
            checkpoint = self._checkpoint_store.load()
            if checkpoint is None:
                raise RuntimeError("checkpoint conflict recovery could not load durable state")
            self._apply_checkpoint(checkpoint)
            # Discard speculative process-local events from the losing lifecycle view.
            # Durable audit reconstruction, when configured, remains the source of truth.
            self._timeline.clear()
            self._checkpoint_conflicted = False
            assert self._snapshot is not None
            return self._snapshot

    def _save_checkpoint(self) -> None:
        if self._checkpoint_store is None or self._snapshot is None:
            return
        snapshot = self._snapshot
        try:
            self._checkpoint_store.save(IncidentCheckpoint(
                snapshot.incident_id, snapshot.revision, snapshot.report, snapshot.approval, snapshot.outcome, self._sequence
            ))
        except CheckpointConflictError:
            self._checkpoint_conflicted = True
            raise

    def _record(self, incident_id: str, event_type: str, actor: str, payload: dict) -> None:
        self._sequence += 1
        event = AuditEvent(self._sequence, self._clock_ms(), incident_id, event_type, actor, payload)
        self._audit.append(event)
        self._timeline.append(event)
        if len(self._timeline) > _MAX_TIMELINE_EVENTS:
            del self._timeline[: len(self._timeline) - _MAX_TIMELINE_EVENTS]
        self._save_checkpoint()

    def status(self) -> IncidentSnapshot | None:
        with self._lock:
            return self._snapshot

    def audit_timeline(self, *, incident_id: str, after_sequence: int = 0, limit: int = 50) -> dict[str, object]:
        if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
            raise ValueError("after_sequence must be a non-negative integer")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                raise RuntimeError("no incident has been investigated")
            if incident_id != snapshot.incident_id:
                raise ValueError("timeline request does not match the current incident")
            candidates: list[AuditEvent] = []
            if self._audit_reader is not None:
                candidates.extend(self._audit_reader.read(
                    incident_id=incident_id, after_sequence=after_sequence, limit=min(limit + 1, 101)
                ))
            candidates.extend(event for event in self._timeline if event.incident_id == incident_id and event.sequence > after_sequence)
            by_sequence: dict[int, AuditEvent] = {}
            for event in candidates:
                existing = by_sequence.get(event.sequence)
                if existing is not None and existing != event:
                    raise RuntimeError("conflicting durable and in-process audit events")
                by_sequence[event.sequence] = event
            ordered = [by_sequence[sequence] for sequence in sorted(by_sequence)]
            selected = ordered[:limit]
            return {
                "incident_id": incident_id,
                "events": [_timeline_event(event) for event in selected],
                "next_after_sequence": selected[-1].sequence if selected else after_sequence,
                "has_more": len(ordered) > len(selected),
            }

    def investigate(self, actor: str = "stageguard") -> IncidentSnapshot:
        with self._lock:
            self._require_checkpoint_consistency()
            report = investigate(self._metrics, self._profile) if self._logs is None else investigate_with_log_corroboration(self._metrics, self._logs, self._profile)
            incident_id = self._snapshot.incident_id if self._snapshot is not None else self._id_factory()
            snapshot = IncidentSnapshot(incident_id, _revision(report), report, None, None)
            self._snapshot = snapshot
            payload = {"revision": snapshot.revision, "status": report.status, "confidence": report.confidence,
                       "evidence_mode": "metric+loki" if self._logs is not None else "metric-only"}
            if self._activation is not None:
                payload["activation_profile_sha256"] = self._activation.profile_sha256
                payload["activation_datasource_sha256"] = self._activation.datasource_sha256
            if self._log_activation is not None:
                payload["log_activation_contract_sha256"] = self._log_activation.contract_sha256
                payload["log_activation_datasource_sha256"] = self._log_activation.datasource_sha256
                payload["log_activation_preflight_sha256"] = self._log_activation.preflight_sha256
            self._record(incident_id, "investigation_completed", actor.strip() or "stageguard", payload)
            return snapshot

    def briefing(self, *, incident_id: str, revision: str, actor: str = "stageguard") -> IncidentBriefing:
        with self._lock:
            self._require_checkpoint_consistency()
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
                self._record(snapshot.incident_id, "briefing_failed", normalized_actor,
                             {"revision": snapshot.revision, "error_type": type(exc).__name__})
                raise RuntimeError("Gemini briefing generation failed") from exc
            self._record(snapshot.incident_id, "briefing_generated", normalized_actor,
                         {"revision": snapshot.revision, "briefing_sha256": _briefing_digest(briefing), "next_step": briefing.next_step})
            return briefing

    def approve(self, *, incident_id: str, revision: str, approved_by: str) -> IncidentSnapshot:
        with self._lock:
            self._require_checkpoint_consistency()
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
            self._require_checkpoint_consistency()
            snapshot = self._snapshot
            if snapshot is None or snapshot.approval is None:
                raise RuntimeError("matching explicit approval is required before remediation")
            if snapshot.outcome is not None:
                raise RuntimeError("this approval has already been consumed")
            outcome = remediate_and_verify(snapshot.report, snapshot.approval, self._remediation, self._metrics,
                                           profile=self._profile, sleep=self._recovery_sleep)
            self._snapshot = IncidentSnapshot(snapshot.incident_id, snapshot.revision, snapshot.report, snapshot.approval, outcome)
            payload = {"revision": snapshot.revision, "status": outcome.status, "sample_count": len(outcome.samples),
                       "action_accepted": bool(outcome.action_result and outcome.action_result.accepted)}
            if outcome.action_result is not None and outcome.action_result.metadata:
                payload["action_metadata"] = dict(outcome.action_result.metadata)
            self._record(snapshot.incident_id, "remediation_completed", actor.strip() or "stageguard", payload)
            return self._snapshot
