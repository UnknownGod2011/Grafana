#!/usr/bin/env python3
"""Versioned integrity-checked StageGuard incident checkpoint persistence.

Checkpoints are server-side lifecycle state only. They intentionally exclude
provider credentials, remediation metadata, arbitrary HTTP/provider details,
and Gemini content. Local JSON is credential-free; GCS is an optional durable
production adapter using ADC and optimistic object-generation preconditions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from investigator import Evidence, IncidentReport
from log_evidence import LogCorroboration
from remediation import ActionResult, Approval, RecoverySample, RemediationOutcome

SCHEMA = "stageguard.incident-checkpoint.v1"
_MAX_BYTES = 256 * 1024


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


def _safe_outcome_dict(outcome: RemediationOutcome | None) -> dict | None:
    if outcome is None:
        return None
    return {
        "status": outcome.status,
        "action_result": None if outcome.action_result is None else {
            "accepted": bool(outcome.action_result.accepted),
        },
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


def checkpoint_document(checkpoint: IncidentCheckpoint) -> dict:
    state = {
        "incident_id": checkpoint.incident_id,
        "revision": checkpoint.revision,
        "report": checkpoint.report.to_dict(),
        "approval": None if checkpoint.approval is None else asdict(checkpoint.approval),
        "outcome": _safe_outcome_dict(checkpoint.outcome),
        "sequence": checkpoint.sequence,
    }
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return {"schema": SCHEMA, "state": state, "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def parse_checkpoint_document(document: dict) -> IncidentCheckpoint:
    if set(document) != {"schema", "state", "sha256"} or document.get("schema") != SCHEMA:
        raise ValueError("unsupported incident checkpoint document")
    state = document.get("state")
    digest = document.get("sha256")
    if not isinstance(state, dict) or not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("invalid incident checkpoint document")
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual, digest):
        raise ValueError("incident checkpoint integrity check failed")
    required = {"incident_id", "revision", "report", "approval", "outcome", "sequence"}
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
    return IncidentCheckpoint(incident_id, revision, report, approval, outcome, sequence)


def _encode(checkpoint: IncidentCheckpoint) -> bytes:
    encoded = (json.dumps(checkpoint_document(checkpoint), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        raise ValueError("incident checkpoint exceeds size limit")
    return encoded


def _decode(raw: bytes) -> IncidentCheckpoint:
    if len(raw) > _MAX_BYTES:
        raise ValueError("incident checkpoint exceeds size limit")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid incident checkpoint JSON") from exc
    if not isinstance(document, dict):
        raise ValueError("invalid incident checkpoint JSON")
    return parse_checkpoint_document(document)


class JsonCheckpointStore:
    """Credential-free atomic local checkpoint store with owner-only permissions."""

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
    """Durable single-object checkpoint store with optimistic concurrency.

    The bucket and object name are deployment-owned configuration. The adapter
    never accepts a browser-supplied object path and imports google-cloud-storage
    lazily so local/free development stays lightweight.
    """

    def __init__(self, bucket, object_name: str = "stageguard/incident-checkpoint.json") -> None:
        name = object_name.strip().lstrip("/")
        if not name or ".." in name.split("/") or len(name) > 512:
            raise ValueError("invalid checkpoint object name")
        self._bucket = bucket
        self._object_name = name

    @classmethod
    def from_environment(cls, *, bucket_name: str, project: str | None = None, object_name: str = "stageguard/incident-checkpoint.json"):
        if not bucket_name.strip():
            raise ValueError("checkpoint bucket name is required")
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage is required for GCS checkpoints") from exc
        client = storage.Client(project=project)
        return cls(client.bucket(bucket_name.strip()), object_name)

    def load(self) -> IncidentCheckpoint | None:
        blob = self._bucket.blob(self._object_name)
        try:
            if not blob.exists():
                return None
            raw = blob.download_as_bytes()
        except Exception as exc:
            raise RuntimeError("incident checkpoint read failed") from exc
        return _decode(raw)

    def save(self, checkpoint: IncidentCheckpoint) -> None:
        encoded = _encode(checkpoint)
        blob = self._bucket.blob(self._object_name)
        try:
            exists = blob.exists()
            generation = None
            if exists:
                blob.reload()
                generation = blob.generation
            blob.upload_from_string(
                encoded,
                content_type="application/json",
                if_generation_match=generation if exists else 0,
            )
        except Exception as exc:
            raise RuntimeError("incident checkpoint write failed") from exc
