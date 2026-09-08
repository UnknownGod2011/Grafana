#!/usr/bin/env python3
"""Versioned integrity/authenticity checked StageGuard incident checkpoints."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from investigator import Evidence, IncidentReport
from log_evidence import LogCorroboration
from remediation import ActionResult, Approval, RecoverySample, RemediationOutcome

SCHEMA_V1 = "stageguard.incident-checkpoint.v1"
SCHEMA_V2 = "stageguard.incident-checkpoint.v2"
SCHEMA_V3 = "stageguard.incident-checkpoint.v3"
SCHEMA = SCHEMA_V3
_MAX_BYTES = 256 * 1024
_EXECUTION_PHASES = {"none", "approved", "dispatching", "resolved"}


class CheckpointConflictError(RuntimeError):
    """A bounded optimistic-concurrency failure; provider details are intentionally hidden."""


class CheckpointStore(Protocol):
    def load(self) -> "IncidentCheckpoint | None": ...
    def save(self, checkpoint: "IncidentCheckpoint") -> None: ...


@dataclass(frozen=True)
class IncidentCheckpoint:
    incident_id: str
    revision: str
    report: IncidentReport
    approval: Approval | None
    outcome: RemediationOutcome | None
    sequence: int
    # None means callers are using the ordinary lifecycle API; serialization
    # derives the precise v2/v3 phase from approval/outcome. ``legacy_unknown``
    # is internal-only and is produced when restoring an ambiguous v1 checkpoint.
    execution_phase: str | None = None
    # Schema v3 binds the append-only audit stream to the authenticated lifecycle
    # checkpoint. Both values must be supplied together. Existing callers that do
    # not yet provide them remain on schema v2 rather than emitting a fake proof.
    audit_chain_sequence: int | None = None
    audit_chain_head_sha256: str | None = None


def _derived_execution_phase(checkpoint: IncidentCheckpoint) -> str:
    if checkpoint.execution_phase is not None:
        return checkpoint.execution_phase
    if checkpoint.outcome is not None:
        return "resolved"
    if checkpoint.approval is not None:
        return "approved"
    return "none"


def _validate_execution_phase(
    phase: str,
    approval: Approval | None,
    outcome: RemediationOutcome | None,
    *,
    allow_legacy: bool = False,
) -> None:
    allowed = _EXECUTION_PHASES | ({"legacy_unknown"} if allow_legacy else set())
    if phase not in allowed:
        raise ValueError("invalid checkpoint execution phase")
    if phase == "none" and (approval is not None or outcome is not None):
        raise ValueError("checkpoint execution phase does not match lifecycle state")
    if phase in {"approved", "dispatching", "legacy_unknown"} and (approval is None or outcome is not None):
        raise ValueError("checkpoint execution phase does not match lifecycle state")
    if phase == "resolved" and (approval is None or outcome is None):
        raise ValueError("checkpoint execution phase does not match lifecycle state")


def _valid_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _validate_audit_chain_binding(sequence: object, head_sha256: object) -> None:
    if sequence is None and head_sha256 is None:
        return
    if sequence is None or head_sha256 is None:
        raise ValueError("checkpoint audit-chain sequence and head must be supplied together")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ValueError("invalid checkpoint audit-chain sequence")
    if not _valid_sha256(head_sha256):
        raise ValueError("invalid checkpoint audit-chain head")
    if sequence == 0 and head_sha256 != "0" * 64:
        raise ValueError("empty checkpoint audit chain must use genesis digest")


def _safe_outcome_dict(outcome: RemediationOutcome | None) -> dict | None:
    if outcome is None:
        return None
    return {
        "status": outcome.status,
        "action_result": None if outcome.action_result is None else {"accepted": bool(outcome.action_result.accepted)},
        "samples": [asdict(sample) for sample in outcome.samples],
        "summary": outcome.summary,
    }


def _report_from_dict(value: dict) -> IncidentReport:
    if not isinstance(value, dict):
        raise ValueError("invalid checkpoint report")
    evidence = tuple(Evidence(**item) for item in value.get("evidence", ()))
    log_raw = value.get("log_corroboration")
    log = None if log_raw is None else LogCorroboration(**log_raw)
    return IncidentReport(
        status=value["status"], production_id=value["production_id"], affected_feed=value["affected_feed"],
        hypothesis=value.get("hypothesis"), confidence=float(value["confidence"]), summary=value["summary"],
        missing_evidence=tuple(value.get("missing_evidence", ())), evidence=evidence, log_corroboration=log,
    )


def _outcome_from_dict(value: dict | None) -> RemediationOutcome | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("invalid checkpoint outcome")
    action_raw = value.get("action_result")
    action = None if action_raw is None else ActionResult(bool(action_raw["accepted"]), "restored checkpoint", {})
    samples = tuple(RecoverySample(**item) for item in value.get("samples", ()))
    return RemediationOutcome(str(value["status"]), action, samples, str(value["summary"]))


def _state(checkpoint: IncidentCheckpoint, *, include_audit_chain: bool) -> dict:
    phase = _derived_execution_phase(checkpoint)
    _validate_execution_phase(phase, checkpoint.approval, checkpoint.outcome)
    _validate_audit_chain_binding(checkpoint.audit_chain_sequence, checkpoint.audit_chain_head_sha256)
    state = {
        "incident_id": checkpoint.incident_id,
        "revision": checkpoint.revision,
        "report": checkpoint.report.to_dict(),
        "approval": None if checkpoint.approval is None else asdict(checkpoint.approval),
        "outcome": _safe_outcome_dict(checkpoint.outcome),
        "sequence": checkpoint.sequence,
        "execution_phase": phase,
    }
    if include_audit_chain:
        state["audit_chain_sequence"] = checkpoint.audit_chain_sequence
        state["audit_chain_head_sha256"] = checkpoint.audit_chain_head_sha256
    return state


def checkpoint_document(checkpoint: IncidentCheckpoint, *, signing_key: bytes | None = None) -> dict:
    has_audit_binding = checkpoint.audit_chain_sequence is not None or checkpoint.audit_chain_head_sha256 is not None
    _validate_audit_chain_binding(checkpoint.audit_chain_sequence, checkpoint.audit_chain_head_sha256)
    schema = SCHEMA_V3 if has_audit_binding else SCHEMA_V2
    state = _state(checkpoint, include_audit_chain=has_audit_binding)
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    signature = None if signing_key is None else hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
    return {"schema": schema, "state": state, "sha256": digest, "hmac_sha256": signature}


def parse_checkpoint_document(document: dict, *, signing_key: bytes | None = None, require_signature: bool = False) -> IncidentCheckpoint:
    if set(document) != {"schema", "state", "sha256", "hmac_sha256"} or document.get("schema") not in {SCHEMA_V1, SCHEMA_V2, SCHEMA_V3}:
        raise ValueError("unsupported incident checkpoint document")
    schema = document["schema"]
    state = document.get("state")
    digest = document.get("sha256")
    signature = document.get("hmac_sha256")
    if not isinstance(state, dict) or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("invalid incident checkpoint document")
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual = hashlib.sha256(canonical).hexdigest()
    if not hmac.compare_digest(actual, digest):
        raise ValueError("incident checkpoint integrity check failed")
    if require_signature and signing_key is None:
        raise ValueError("checkpoint signing key is required")
    if signing_key is not None:
        if not isinstance(signature, str) or len(signature) != 64:
            raise ValueError("incident checkpoint signature is required")
        expected = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("incident checkpoint authenticity check failed")
    elif require_signature or signature is not None:
        raise ValueError("signed incident checkpoint cannot be verified")

    v1_required = {"incident_id", "revision", "report", "approval", "outcome", "sequence"}
    v2_required = v1_required | {"execution_phase"}
    v3_required = v2_required | {"audit_chain_sequence", "audit_chain_head_sha256"}
    required = v1_required if schema == SCHEMA_V1 else (v2_required if schema == SCHEMA_V2 else v3_required)
    if set(state) != required:
        raise ValueError("invalid incident checkpoint state")
    incident_id = state["incident_id"]
    revision = state["revision"]
    sequence = state["sequence"]
    if not isinstance(incident_id, str) or not incident_id or len(incident_id) > 128:
        raise ValueError("invalid checkpoint incident_id")
    if not isinstance(revision, str) or len(revision) != 16:
        raise ValueError("invalid checkpoint revision")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise ValueError("invalid checkpoint sequence")
    report = _report_from_dict(state["report"])
    approval_raw = state["approval"]
    approval = None if approval_raw is None else Approval(**approval_raw)
    outcome = _outcome_from_dict(state["outcome"])

    if schema == SCHEMA_V1:
        # v1 has no pre-side-effect marker. A pending approval is therefore
        # execution-ambiguous for production adapters after restart.
        phase = "legacy_unknown" if approval is not None and outcome is None else (
            "resolved" if outcome is not None else "none"
        )
        _validate_execution_phase(phase, approval, outcome, allow_legacy=True)
    else:
        phase = state["execution_phase"]
        if not isinstance(phase, str):
            raise ValueError("invalid checkpoint execution phase")
        _validate_execution_phase(phase, approval, outcome)

    audit_chain_sequence = None
    audit_chain_head_sha256 = None
    if schema == SCHEMA_V3:
        audit_chain_sequence = state["audit_chain_sequence"]
        audit_chain_head_sha256 = state["audit_chain_head_sha256"]
        _validate_audit_chain_binding(audit_chain_sequence, audit_chain_head_sha256)
        if audit_chain_sequence > sequence:
            raise ValueError("checkpoint audit chain cannot exceed lifecycle audit sequence")
    return IncidentCheckpoint(
        incident_id,
        revision,
        report,
        approval,
        outcome,
        sequence,
        phase,
        audit_chain_sequence,
        audit_chain_head_sha256,
    )


def _encode(checkpoint: IncidentCheckpoint, *, signing_key: bytes | None = None) -> bytes:
    encoded = (json.dumps(checkpoint_document(checkpoint, signing_key=signing_key), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        raise ValueError("incident checkpoint exceeds size limit")
    return encoded


def _decode(raw: bytes, *, signing_key: bytes | None = None, require_signature: bool = False) -> IncidentCheckpoint:
    if len(raw) > _MAX_BYTES:
        raise ValueError("incident checkpoint exceeds size limit")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid incident checkpoint JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("invalid incident checkpoint JSON")
    return parse_checkpoint_document(document, signing_key=signing_key, require_signature=require_signature)


def _http_status(exc: BaseException) -> int | None:
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


class JsonCheckpointStore:
    """Credential-free atomic local checkpoint store with owner-only permissions."""

    supports_execution_phase = True

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> IncidentCheckpoint | None:
        if not self.path.exists():
            return None
        if self.path.is_symlink():
            raise ValueError("incident checkpoint path must not be a symlink")
        return _decode(self.path.read_bytes())

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        encoded = _encode(checkpoint)
        fd, tmp_name = tempfile.mkstemp(prefix=".checkpoint-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


class GoogleCloudStorageCheckpointStore:
    """Durable authenticated single-object checkpoint store with optimistic compare-and-swap semantics."""

    supports_execution_phase = True

    def __init__(self, bucket, signing_key: bytes, object_name: str = "stageguard/incident-checkpoint.json") -> None:
        name = object_name.strip().lstrip("/")
        if not name or ".." in name.split("/") or len(name) > 512:
            raise ValueError("invalid checkpoint object name")
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("checkpoint signing key must be at least 32 bytes")
        self._bucket = bucket
        self._object_name = name
        self._signing_key = signing_key
        self._generation_lock = threading.Lock()
        self._expected_generation: int | None = 0

    @classmethod
    def from_environment(
        cls,
        *,
        bucket_name: str,
        signing_key: str,
        project: str | None = None,
        object_name: str = "stageguard/incident-checkpoint.json",
    ):
        if not bucket_name.strip():
            raise ValueError("checkpoint bucket name is required")
        key = signing_key.encode("utf-8")
        if len(key) < 32:
            raise ValueError("checkpoint signing key must be at least 32 bytes")
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCS checkpoints") from exc
        client = storage.Client(project=project)
        return cls(client.bucket(bucket_name.strip()), key, object_name)

    def load(self) -> IncidentCheckpoint | None:
        blob = self._bucket.blob(self._object_name)
        with self._generation_lock:
            try:
                if not blob.exists():
                    self._expected_generation = 0
                    return None
                blob.reload()
                generation = blob.generation
                if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
                    raise RuntimeError("invalid checkpoint generation")
                raw = blob.download_as_bytes(if_generation_match=generation)
            except Exception as exc:
                if _http_status(exc) == 412:
                    raise CheckpointConflictError("incident checkpoint concurrent read conflict") from exc
                raise RuntimeError("incident checkpoint read failed") from exc
            checkpoint = _decode(raw, signing_key=self._signing_key, require_signature=True)
            self._expected_generation = generation
            return checkpoint

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        encoded = _encode(checkpoint, signing_key=self._signing_key)
        blob = self._bucket.blob(self._object_name)
        with self._generation_lock:
            expected_generation = self._expected_generation
            if expected_generation is None:
                raise RuntimeError("incident checkpoint generation is unavailable")
            try:
                blob.upload_from_string(
                    encoded,
                    content_type="application/json",
                    if_generation_match=expected_generation,
                )
                generation = blob.generation
                if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
                    raise RuntimeError("invalid checkpoint generation")
            except Exception as exc:
                if _http_status(exc) == 412:
                    raise CheckpointConflictError("incident checkpoint concurrent update conflict") from exc
                raise RuntimeError("incident checkpoint write failed") from exc
            self._expected_generation = generation


class ObservableCheckpointStore:
    """Checkpoint decorator exposing only fixed-label, non-sensitive Prometheus telemetry."""

    supports_execution_phase = True

    def __init__(self, inner: CheckpointStore, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._inner = inner
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._loads = {"ok": 0, "empty": 0, "failed": 0}
        self._saves = {"ok": 0, "conflict": 0, "failed": 0}
        self._last_latency = {"load": 0.0, "save": 0.0}
        self._last_operation_ok = 1

    def load(self) -> IncidentCheckpoint | None:
        started = self._monotonic()
        try:
            checkpoint = self._inner.load()
        except Exception:
            with self._lock:
                self._loads["failed"] += 1
                self._last_operation_ok = 0
            raise
        else:
            with self._lock:
                self._loads["empty" if checkpoint is None else "ok"] += 1
                self._last_operation_ok = 1
            return checkpoint
        finally:
            elapsed = max(0.0, self._monotonic() - started)
            with self._lock:
                self._last_latency["load"] = elapsed

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        started = self._monotonic()
        try:
            self._inner.save(checkpoint)
        except CheckpointConflictError:
            with self._lock:
                self._saves["conflict"] += 1
                self._last_operation_ok = 0
            raise
        except Exception:
            with self._lock:
                self._saves["failed"] += 1
                self._last_operation_ok = 0
            raise
        else:
            with self._lock:
                self._saves["ok"] += 1
                self._last_operation_ok = 1
        finally:
            elapsed = max(0.0, self._monotonic() - started)
            with self._lock:
                self._last_latency["save"] = elapsed

    def prometheus_metrics(self) -> str:
        with self._lock:
            lines = [
                "# HELP stageguard_checkpoint_last_operation_ok Whether the latest checkpoint operation succeeded.",
                "# TYPE stageguard_checkpoint_last_operation_ok gauge",
                f"stageguard_checkpoint_last_operation_ok {self._last_operation_ok}",
                "# HELP stageguard_checkpoint_loads_total Checkpoint loads by bounded result.",
                "# TYPE stageguard_checkpoint_loads_total counter",
            ]
            for result in ("ok", "empty", "failed"):
                lines.append(f'stageguard_checkpoint_loads_total{{result="{result}"}} {self._loads[result]}')
            lines.extend([
                "# HELP stageguard_checkpoint_saves_total Checkpoint saves by bounded result.",
                "# TYPE stageguard_checkpoint_saves_total counter",
            ])
            for result in ("ok", "conflict", "failed"):
                lines.append(f'stageguard_checkpoint_saves_total{{result="{result}"}} {self._saves[result]}')
            lines.extend([
                "# HELP stageguard_checkpoint_last_operation_latency_seconds Last checkpoint operation latency by operation.",
                "# TYPE stageguard_checkpoint_last_operation_latency_seconds gauge",
            ])
            for operation in ("load", "save"):
                lines.append(
                    f'stageguard_checkpoint_last_operation_latency_seconds{{operation="{operation}"}} '
                    f'{self._last_latency[operation]:.6f}'
                )
            return "\n".join(lines) + "\n"
