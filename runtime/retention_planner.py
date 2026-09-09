#!/usr/bin/env python3
"""Read-only retention planning for authenticated StageGuard audit anchors."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from incident_checkpoint import IncidentCheckpoint, parse_checkpoint_document
from incident_service import AuditEvent

MAX_SCAN_BYTES = 128 * 1024 * 1024
MAX_SCAN_RECORDS = 1_000_000


@dataclass(frozen=True)
class AuditRetentionPlan:
    incident_id: str
    backend: str
    safe_to_compact: bool
    refusal_reason: str | None
    eligible_through_sequence: int | None
    anchor_head_sha256: str | None
    audit_chain_sequence: int | None
    eligible_records: int | None = None
    eligible_bytes: int | None = None
    scanned_records: int | None = None
    scanned_bytes: int | None = None
    enumeration_complete: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _refusal(checkpoint: IncidentCheckpoint, backend: str, reason: str) -> AuditRetentionPlan:
    return AuditRetentionPlan(
        incident_id=checkpoint.incident_id,
        backend=backend,
        safe_to_compact=False,
        refusal_reason=reason,
        eligible_through_sequence=None,
        anchor_head_sha256=None,
        audit_chain_sequence=checkpoint.audit_chain_sequence,
    )


def plan_authenticated_boundary(
    checkpoint: IncidentCheckpoint,
    *,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    backend: str = "unknown",
) -> AuditRetentionPlan:
    """Return the only deletion boundary StageGuard may consider.

    The function is intentionally conservative. A plan is emitted only when the
    runtime has verified the authenticated audit lineage and the durable checkpoint
    has a non-genesis schema-v4 anchor. It never mutates audit storage.
    """
    if not isinstance(checkpoint, IncidentCheckpoint):
        raise TypeError("checkpoint must be an IncidentCheckpoint")
    if audit_integrity_state != "verified":
        return _refusal(checkpoint, backend, "audit integrity is not verified")
    if checkpoint_conflicted:
        return _refusal(checkpoint, backend, "checkpoint state is conflicted")
    if checkpoint.audit_chain_sequence is None or checkpoint.audit_chain_head_sha256 is None:
        return _refusal(checkpoint, backend, "checkpoint is not bound to an authenticated audit chain")
    if checkpoint.audit_anchor_sequence is None or checkpoint.audit_anchor_head_sha256 is None:
        return _refusal(checkpoint, backend, "checkpoint has no authenticated audit anchor")
    if checkpoint.audit_anchor_sequence <= 0:
        return _refusal(checkpoint, backend, "genesis anchor has no compactable prefix")
    if checkpoint.audit_anchor_sequence > checkpoint.audit_chain_sequence:
        return _refusal(checkpoint, backend, "audit anchor exceeds authenticated chain head")
    if checkpoint.audit_chain_sequence > checkpoint.sequence:
        return _refusal(checkpoint, backend, "audit chain exceeds lifecycle sequence")
    return AuditRetentionPlan(
        incident_id=checkpoint.incident_id,
        backend=backend,
        safe_to_compact=True,
        refusal_reason=None,
        eligible_through_sequence=checkpoint.audit_anchor_sequence,
        anchor_head_sha256=checkpoint.audit_anchor_head_sha256,
        audit_chain_sequence=checkpoint.audit_chain_sequence,
    )


def plan_jsonl_retention(
    checkpoint: IncidentCheckpoint,
    path: str | Path,
    *,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    max_scan_bytes: int = MAX_SCAN_BYTES,
    max_scan_records: int = MAX_SCAN_RECORDS,
) -> AuditRetentionPlan:
    """Produce an exact, non-destructive JSONL retention inventory."""
    base = plan_authenticated_boundary(
        checkpoint,
        audit_integrity_state=audit_integrity_state,
        checkpoint_conflicted=checkpoint_conflicted,
        backend="jsonl",
    )
    if not base.safe_to_compact:
        return base
    if not isinstance(max_scan_bytes, int) or isinstance(max_scan_bytes, bool) or max_scan_bytes < 1:
        raise ValueError("max_scan_bytes must be a positive integer")
    if not isinstance(max_scan_records, int) or isinstance(max_scan_records, bool) or max_scan_records < 1:
        raise ValueError("max_scan_records must be a positive integer")

    audit_path = Path(path)
    eligible_records = 0
    eligible_bytes = 0
    scanned_records = 0
    scanned_bytes = 0
    boundary = base.eligible_through_sequence
    assert boundary is not None

    try:
        with audit_path.open("rb") as handle:
            for raw_line in handle:
                scanned_bytes += len(raw_line)
                if scanned_bytes > max_scan_bytes:
                    return _refusal(checkpoint, "jsonl", "audit scan exceeded byte safety bound")
                if not raw_line.strip():
                    continue
                scanned_records += 1
                if scanned_records > max_scan_records:
                    return _refusal(checkpoint, "jsonl", "audit scan exceeded record safety bound")
                raw = json.loads(raw_line.decode("utf-8"))
                event = AuditEvent(**raw)
                if event.sequence < 1:
                    return _refusal(checkpoint, "jsonl", "audit log contains an invalid sequence")
                if event.incident_id == checkpoint.incident_id and event.sequence <= boundary:
                    eligible_records += 1
                    eligible_bytes += len(raw_line)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return _refusal(checkpoint, "jsonl", f"audit log could not be inventoried safely: {type(exc).__name__}")

    return AuditRetentionPlan(
        **{
            **base.to_dict(),
            "eligible_records": eligible_records,
            "eligible_bytes": eligible_bytes,
            "scanned_records": scanned_records,
            "scanned_bytes": scanned_bytes,
            "enumeration_complete": True,
        }
    )


def plan_observed_candidates(
    checkpoint: IncidentCheckpoint,
    events: Iterable[AuditEvent],
    *,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    backend: str = "cloud-logging",
) -> AuditRetentionPlan:
    """Inventory an observed provider candidate set without claiming completeness."""
    base = plan_authenticated_boundary(
        checkpoint,
        audit_integrity_state=audit_integrity_state,
        checkpoint_conflicted=checkpoint_conflicted,
        backend=backend,
    )
    if not base.safe_to_compact:
        return base
    boundary = base.eligible_through_sequence
    assert boundary is not None
    count = 0
    for event in events:
        if not isinstance(event, AuditEvent):
            raise TypeError("observed audit candidates must be AuditEvent values")
        if event.incident_id != checkpoint.incident_id:
            continue
        if event.sequence > boundary:
            raise ValueError("observed candidate exceeds authenticated retention boundary")
        if event.sequence < 1:
            raise ValueError("observed candidate has invalid sequence")
        count += 1
    return AuditRetentionPlan(
        **{
            **base.to_dict(),
            "eligible_records": count,
            "enumeration_complete": False,
        }
    )


def plan_cloud_logging_retention(
    checkpoint: IncidentCheckpoint,
    reader,
    *,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    limit: int = 4096,
) -> AuditRetentionPlan:
    """Read only candidates at/before the anchor; Cloud Logging inventory is advisory.

    Cloud Logging lookback/retention can make enumeration incomplete, so the plan
    intentionally leaves ``enumeration_complete`` false and never reports bytes.
    """
    base = plan_authenticated_boundary(
        checkpoint,
        audit_integrity_state=audit_integrity_state,
        checkpoint_conflicted=checkpoint_conflicted,
        backend="cloud-logging",
    )
    if not base.safe_to_compact:
        return base
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 4096:
        raise ValueError("limit must be between 1 and 4096")
    read_candidates = getattr(reader, "read_candidates", None)
    if not callable(read_candidates):
        return _refusal(checkpoint, "cloud-logging", "audit reader does not support candidate enumeration")
    boundary = base.eligible_through_sequence
    assert boundary is not None
    try:
        events = read_candidates(
            incident_id=checkpoint.incident_id,
            after_sequence=0,
            through_sequence=boundary,
            limit=limit,
        )
    except Exception as exc:
        return _refusal(checkpoint, "cloud-logging", f"audit candidates could not be inventoried safely: {type(exc).__name__}")
    if not isinstance(events, list):
        return _refusal(checkpoint, "cloud-logging", "audit reader returned an invalid candidate result")
    return plan_observed_candidates(
        checkpoint,
        events,
        audit_integrity_state=audit_integrity_state,
        checkpoint_conflicted=checkpoint_conflicted,
        backend="cloud-logging",
    )


def _load_signed_checkpoint(path: Path, signing_key: bytes) -> IncidentCheckpoint:
    if len(signing_key) < 32:
        raise ValueError("checkpoint signing key must be at least 32 bytes")
    raw = path.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("checkpoint exceeds size limit")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("invalid checkpoint document")
    return parse_checkpoint_document(document, signing_key=signing_key, require_signature=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan StageGuard JSONL audit retention without deleting records.")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--audit-jsonl", required=True, type=Path)
    parser.add_argument(
        "--signing-key-env",
        default="STAGEGUARD_CHECKPOINT_HMAC_KEY",
        help="environment variable containing the checkpoint HMAC key",
    )
    args = parser.parse_args(argv)
    key_text = os.environ.get(args.signing_key_env)
    if key_text is None:
        parser.error(f"missing signing key environment variable: {args.signing_key_env}")
    checkpoint = _load_signed_checkpoint(args.checkpoint, key_text.encode("utf-8"))
    plan = plan_jsonl_retention(
        checkpoint,
        args.audit_jsonl,
        audit_integrity_state="verified",
    )
    print(json.dumps(plan.to_dict(), sort_keys=True))
    return 0 if plan.safe_to_compact else 2


if __name__ == "__main__":
    raise SystemExit(main())
