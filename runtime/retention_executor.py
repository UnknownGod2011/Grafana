#!/usr/bin/env python3
"""Two-phase, local-only execution of authenticated StageGuard JSONL retention."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from incident_checkpoint import IncidentCheckpoint, checkpoint_document, parse_checkpoint_document
from incident_service import AuditEvent
from retention_planner import MAX_SCAN_BYTES, MAX_SCAN_RECORDS, plan_jsonl_retention

PLAN_SCHEMA = "stageguard.audit-retention-plan.v1"


@dataclass(frozen=True)
class LocalRetentionPlan:
    schema: str
    created_unix_ms: int
    incident_id: str
    audit_path: str
    checkpoint_state_sha256: str
    audit_file_sha256: str
    audit_file_bytes: int
    eligible_through_sequence: int
    anchor_head_sha256: str
    eligible_records: int
    eligible_bytes: int
    scanned_records: int
    scanned_bytes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RetentionExecutionResult:
    removed_records: int
    removed_bytes: int
    retained_records: int
    retained_bytes: int
    backup_path: str
    output_sha256: str


def _require_signing_key(signing_key: bytes) -> None:
    if not isinstance(signing_key, bytes) or len(signing_key) < 32:
        raise ValueError("retention signing key must be at least 32 bytes")


def _checkpoint_state_sha256(checkpoint: IncidentCheckpoint) -> str:
    return str(checkpoint_document(checkpoint)["sha256"])


def _canonical_plan(plan: LocalRetentionPlan) -> bytes:
    return json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")


def signed_plan_document(plan: LocalRetentionPlan, *, signing_key: bytes) -> dict[str, object]:
    _require_signing_key(signing_key)
    canonical = _canonical_plan(plan)
    return {
        "schema": PLAN_SCHEMA,
        "plan": plan.to_dict(),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "hmac_sha256": hmac.new(signing_key, canonical, hashlib.sha256).hexdigest(),
    }


def parse_signed_plan_document(document: dict, *, signing_key: bytes) -> LocalRetentionPlan:
    _require_signing_key(signing_key)
    if not isinstance(document, dict) or set(document) != {"schema", "plan", "sha256", "hmac_sha256"}:
        raise ValueError("invalid retention plan document")
    if document.get("schema") != PLAN_SCHEMA:
        raise ValueError("unsupported retention plan schema")
    raw_plan = document.get("plan")
    if not isinstance(raw_plan, dict):
        raise ValueError("invalid retention plan payload")
    expected_fields = set(LocalRetentionPlan.__dataclass_fields__)
    if set(raw_plan) != expected_fields:
        raise ValueError("invalid retention plan fields")
    plan = LocalRetentionPlan(**raw_plan)
    if plan.schema != PLAN_SCHEMA:
        raise ValueError("retention plan schema mismatch")
    if plan.eligible_through_sequence < 1 or plan.eligible_records < 0 or plan.eligible_bytes < 0:
        raise ValueError("invalid retention plan counts")
    if plan.audit_file_bytes < 0 or plan.scanned_records < 0 or plan.scanned_bytes < 0:
        raise ValueError("invalid retention plan scan metadata")
    if len(plan.audit_file_sha256) != 64 or len(plan.checkpoint_state_sha256) != 64:
        raise ValueError("invalid retention plan digest")
    canonical = _canonical_plan(plan)
    digest = hashlib.sha256(canonical).hexdigest()
    signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()
    if not isinstance(document.get("sha256"), str) or not hmac.compare_digest(digest, document["sha256"]):
        raise ValueError("retention plan integrity check failed")
    if not isinstance(document.get("hmac_sha256"), str) or not hmac.compare_digest(signature, document["hmac_sha256"]):
        raise ValueError("retention plan authenticity check failed")
    return plan


def _hash_file(path: Path, *, max_bytes: int = MAX_SCAN_BYTES) -> tuple[str, int]:
    if path.is_symlink():
        raise ValueError("audit path must not be a symlink")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("audit file exceeds retention safety bound")
            digest.update(chunk)
    return digest.hexdigest(), total


def prepare_local_retention_plan(
    checkpoint: IncidentCheckpoint,
    audit_path: str | Path,
    *,
    signing_key: bytes,
    audit_integrity_state: str,
    checkpoint_conflicted: bool = False,
    clock_ms=lambda: int(time.time() * 1000),
) -> dict[str, object]:
    """Create a signed operator artifact without modifying the audit file."""
    _require_signing_key(signing_key)
    path = Path(audit_path)
    if path.is_symlink():
        raise ValueError("audit path must not be a symlink")
    before = path.stat()
    inventory = plan_jsonl_retention(
        checkpoint,
        path,
        audit_integrity_state=audit_integrity_state,
        checkpoint_conflicted=checkpoint_conflicted,
    )
    if not inventory.safe_to_compact:
        raise ValueError(inventory.refusal_reason or "retention plan was refused")
    if not inventory.enumeration_complete:
        raise ValueError("local retention inventory must be complete")
    file_sha256, file_bytes = _hash_file(path)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        raise RuntimeError("audit file changed while retention plan was prepared")
    assert inventory.eligible_through_sequence is not None
    assert inventory.anchor_head_sha256 is not None
    assert inventory.eligible_records is not None
    assert inventory.eligible_bytes is not None
    assert inventory.scanned_records is not None
    assert inventory.scanned_bytes is not None
    plan = LocalRetentionPlan(
        schema=PLAN_SCHEMA,
        created_unix_ms=int(clock_ms()),
        incident_id=checkpoint.incident_id,
        audit_path=str(path.resolve()),
        checkpoint_state_sha256=_checkpoint_state_sha256(checkpoint),
        audit_file_sha256=file_sha256,
        audit_file_bytes=file_bytes,
        eligible_through_sequence=inventory.eligible_through_sequence,
        anchor_head_sha256=inventory.anchor_head_sha256,
        eligible_records=inventory.eligible_records,
        eligible_bytes=inventory.eligible_bytes,
        scanned_records=inventory.scanned_records,
        scanned_bytes=inventory.scanned_bytes,
    )
    return signed_plan_document(plan, signing_key=signing_key)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def execute_local_retention(
    plan_document: dict,
    checkpoint: IncidentCheckpoint,
    *,
    signing_key: bytes,
    backup_path: str | Path | None = None,
) -> RetentionExecutionResult:
    """Execute one exact signed plan after fresh checkpoint and file revalidation."""
    plan = parse_signed_plan_document(plan_document, signing_key=signing_key)
    path = Path(plan.audit_path)
    if path.is_symlink():
        raise ValueError("audit path must not be a symlink")
    if _checkpoint_state_sha256(checkpoint) != plan.checkpoint_state_sha256:
        raise RuntimeError("checkpoint changed after retention plan was prepared")
    if checkpoint.incident_id != plan.incident_id:
        raise RuntimeError("retention plan incident does not match checkpoint")
    if checkpoint.audit_anchor_sequence != plan.eligible_through_sequence:
        raise RuntimeError("authenticated retention boundary changed")
    if checkpoint.audit_anchor_head_sha256 != plan.anchor_head_sha256:
        raise RuntimeError("authenticated retention anchor changed")

    current_sha256, current_bytes = _hash_file(path)
    if current_sha256 != plan.audit_file_sha256 or current_bytes != plan.audit_file_bytes:
        raise RuntimeError("audit file changed after retention plan was prepared")

    parent = path.parent
    if backup_path is None:
        backup = parent / f"{path.name}.pre-retention-{plan.created_unix_ms}.bak"
    else:
        backup = Path(backup_path)
    if backup.resolve() == path.resolve():
        raise ValueError("backup path must differ from audit path")
    if backup.parent.resolve() != parent.resolve():
        raise ValueError("backup must be created beside the audit file")
    if backup.exists():
        raise FileExistsError("retention backup path already exists")
    if backup.is_symlink():
        raise ValueError("retention backup path must not be a symlink")

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.retention-", dir=parent)
    removed_records = 0
    removed_bytes = 0
    retained_records = 0
    retained_bytes = 0
    try:
        os.fchmod(fd, 0o600)
        source_digest = hashlib.sha256()
        source_bytes = 0
        with path.open("rb") as source, os.fdopen(fd, "wb", closefd=True) as output:
            for raw_line in source:
                source_digest.update(raw_line)
                source_bytes += len(raw_line)
                if not raw_line.strip():
                    output.write(raw_line)
                    retained_bytes += len(raw_line)
                    continue
                try:
                    event = AuditEvent(**json.loads(raw_line.decode("utf-8")))
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise RuntimeError("audit file became invalid during retention execution") from exc
                should_remove = (
                    event.incident_id == plan.incident_id
                    and 1 <= event.sequence <= plan.eligible_through_sequence
                )
                if should_remove:
                    removed_records += 1
                    removed_bytes += len(raw_line)
                else:
                    output.write(raw_line)
                    retained_records += 1
                    retained_bytes += len(raw_line)
            output.flush()
            os.fsync(output.fileno())

        if source_bytes != plan.audit_file_bytes or source_digest.hexdigest() != plan.audit_file_sha256:
            raise RuntimeError("audit file changed during retention execution")
        if removed_records != plan.eligible_records or removed_bytes != plan.eligible_bytes:
            raise RuntimeError("retention candidate set drifted from signed plan")

        shutil.copyfile(path, backup)
        os.chmod(backup, 0o600)
        with backup.open("rb") as backup_handle:
            os.fsync(backup_handle.fileno())
        _fsync_directory(parent)

        os.replace(tmp_name, path)
        os.chmod(path, 0o600)
        _fsync_directory(parent)
        output_sha256, _ = _hash_file(path)
        return RetentionExecutionResult(
            removed_records=removed_records,
            removed_bytes=removed_bytes,
            retained_records=retained_records,
            retained_bytes=retained_bytes,
            backup_path=str(backup),
            output_sha256=output_sha256,
        )
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def _load_signed_checkpoint_file(path: Path, signing_key: bytes) -> IncidentCheckpoint:
    raw = path.read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("checkpoint exceeds size limit")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("invalid checkpoint document")
    return parse_checkpoint_document(document, signing_key=signing_key, require_signature=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Prepare or execute explicit local StageGuard audit retention."
    )
    parser.add_argument("--signing-key-env", default="STAGEGUARD_CHECKPOINT_HMAC_KEY")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="write a signed, non-destructive retention plan")
    prepare.add_argument("--checkpoint", required=True, type=Path)
    prepare.add_argument("--audit-jsonl", required=True, type=Path)
    prepare.add_argument("--plan-out", required=True, type=Path)
    prepare.add_argument(
        "--audit-integrity-state",
        required=True,
        choices=("verified",),
        help="must be copied from a freshly verified StageGuard runtime status",
    )

    execute = subparsers.add_parser("execute", help="execute one exact signed retention plan")
    execute.add_argument("--checkpoint", required=True, type=Path)
    execute.add_argument("--plan", required=True, type=Path)
    execute.add_argument("--backup", type=Path)

    args = parser.parse_args(argv)
    key_text = os.environ.get(args.signing_key_env)
    if key_text is None:
        parser.error(f"missing signing key environment variable: {args.signing_key_env}")
    signing_key = key_text.encode("utf-8")
    _require_signing_key(signing_key)
    checkpoint = _load_signed_checkpoint_file(args.checkpoint, signing_key)

    if args.command == "prepare":
        document = prepare_local_retention_plan(
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
    result = execute_local_retention(
        document,
        checkpoint,
        signing_key=signing_key,
        backup_path=args.backup,
    )
    print(json.dumps({"status": "executed", **asdict(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
