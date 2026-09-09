#!/usr/bin/env python3
"""Lock-coordinated local StageGuard retention entrypoint.

This module wraps the authenticated two-phase retention executor with the same
cooperative file lock used by AnchoredJsonlAuditLog. It is intentionally local
only; Cloud Logging retention remains advisory/read-only.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from audit_file_lock import audit_file_lock
from incident_checkpoint import IncidentCheckpoint, parse_checkpoint_document
from retention_executor import (
    _require_signing_key,
    execute_local_retention,
    parse_signed_plan_document,
    prepare_local_retention_plan,
)


def coordinated_prepare_local_retention_plan(
    checkpoint: IncidentCheckpoint,
    audit_path: str | Path,
    *,
    signing_key: bytes,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    clock_ms=None,
) -> dict[str, object]:
    """Prepare an authenticated plan while writers/readers are excluded."""
    path = Path(audit_path)
    kwargs = {
        "signing_key": signing_key,
        "audit_integrity_state": audit_integrity_state,
        "checkpoint_conflicted": checkpoint_conflicted,
    }
    if clock_ms is not None:
        kwargs["clock_ms"] = clock_ms
    with audit_file_lock(path):
        return prepare_local_retention_plan(checkpoint, path, **kwargs)


def coordinated_execute_local_retention(
    plan_document: dict,
    checkpoint: IncidentCheckpoint,
    *,
    signing_key: bytes,
    backup_path: str | Path | None = None,
):
    """Execute one signed plan while holding the audit lock through replace.

    The wrapped executor still performs all of its normal checkpoint, HMAC,
    source-digest, candidate-set, backup, fsync, and atomic-replace validation.
    The outer lock closes the append-after-validation race.
    """
    plan = parse_signed_plan_document(plan_document, signing_key=signing_key)
    with audit_file_lock(plan.audit_path):
        return execute_local_retention(
            plan_document,
            checkpoint,
            signing_key=signing_key,
            backup_path=backup_path,
        )


def _load_signed_checkpoint(path: Path, signing_key: bytes) -> IncidentCheckpoint:
    raw = path.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("checkpoint exceeds size limit")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("invalid checkpoint document")
    return parse_checkpoint_document(document, signing_key=signing_key, require_signature=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or execute lock-coordinated local StageGuard audit retention."
    )
    parser.add_argument("--signing-key-env", default="STAGEGUARD_CHECKPOINT_HMAC_KEY")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="write a signed retention plan under the audit lock")
    prepare.add_argument("--checkpoint", required=True, type=Path)
    prepare.add_argument("--audit-jsonl", required=True, type=Path)
    prepare.add_argument("--plan-out", required=True, type=Path)
    prepare.add_argument("--audit-integrity-state", required=True, choices=("verified",))

    execute = subparsers.add_parser("execute", help="execute an exact signed plan under the audit lock")
    execute.add_argument("--checkpoint", required=True, type=Path)
    execute.add_argument("--plan", required=True, type=Path)
    execute.add_argument("--backup", type=Path)

    args = parser.parse_args(argv)
    key_text = os.environ.get(args.signing_key_env)
    if key_text is None:
        parser.error(f"missing signing key environment variable: {args.signing_key_env}")
    signing_key = key_text.encode("utf-8")
    _require_signing_key(signing_key)
    checkpoint = _load_signed_checkpoint(args.checkpoint, signing_key)

    if args.command == "prepare":
        document = coordinated_prepare_local_retention_plan(
            checkpoint,
            args.audit_jsonl,
            signing_key=signing_key,
            audit_integrity_state=args.audit_integrity_state,
        )
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
        fd = os.open(args.plan_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, encoded.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        print(json.dumps({"status": "prepared", "plan": str(args.plan_out)}, sort_keys=True))
        return 0

    document = json.loads(args.plan.read_text(encoding="utf-8"))
    result = coordinated_execute_local_retention(
        document,
        checkpoint,
        signing_key=signing_key,
        backup_path=args.backup,
    )
    print(json.dumps({"status": "executed", **asdict(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
