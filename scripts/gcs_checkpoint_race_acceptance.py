#!/usr/bin/env python3
"""StageGuard GCS checkpoint CAS acceptance test.

Creates one unique StageGuard-owned object, makes two stores load the same
checkpoint generation, verifies exactly one stale writer loses with
CheckpointConflictError, verifies the winner is still durable, and removes
only the unique acceptance object unless --keep is supplied.

This script never reads or writes the production checkpoint object.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from incident_checkpoint import (  # noqa: E402
    CheckpointConflictError,
    GoogleCloudStorageCheckpointStore,
    IncidentCheckpoint,
    ObservableCheckpointStore,
)
from investigator import Evidence, IncidentReport  # noqa: E402


def _checkpoint(sequence: int) -> IncidentCheckpoint:
    report = IncidentReport(
        "diagnosed",
        "acceptance-production",
        "acceptance-feed",
        "synthetic checkpoint CAS acceptance",
        0.99,
        "synthetic bounded acceptance state",
        (),
        (Evidence("symptom", "acceptance-fixed-query", 1.0, ">0", True),),
    )
    canonical = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return IncidentCheckpoint("acceptance-incident", revision, report, None, None, sequence)


def _key_from_env() -> bytes:
    value = os.environ.get("STAGEGUARD_CHECKPOINT_HMAC_KEY", "")
    key = value.encode("utf-8")
    if len(key) < 32:
        raise SystemExit("STAGEGUARD_CHECKPOINT_HMAC_KEY must be at least 32 bytes")
    return key


def _cleanup(blob) -> None:
    """Delete only the exact acceptance generation we created."""
    blob.reload()
    generation = blob.generation
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise RuntimeError("acceptance cleanup could not establish object generation")
    blob.delete(if_generation_match=generation)


def run(bucket_name: str, *, project: str | None, keep: bool) -> int:
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise SystemExit("google-cloud-storage is required; install runtime requirements first") from exc

    bucket_name = bucket_name.strip()
    if not bucket_name:
        raise SystemExit("--bucket must not be empty")

    key = _key_from_env()
    object_name = f"stageguard/acceptance/checkpoint-cas-{uuid.uuid4().hex}.json"
    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    # Refuse to reuse an object. The UUID makes this extraordinarily unlikely,
    # but create-only semantics are part of the safety boundary.
    if blob.exists():
        raise RuntimeError("acceptance object unexpectedly already exists")

    seed = GoogleCloudStorageCheckpointStore(bucket, key, object_name)
    writer_a = ObservableCheckpointStore(GoogleCloudStorageCheckpointStore(bucket, key, object_name))
    writer_b = ObservableCheckpointStore(GoogleCloudStorageCheckpointStore(bucket, key, object_name))

    try:
        seed.save(_checkpoint(1))
        if writer_a.load() is None or writer_b.load() is None:
            raise RuntimeError("acceptance writers failed to load seeded checkpoint")

        writer_a.save(_checkpoint(2))
        try:
            writer_b.save(_checkpoint(3))
        except CheckpointConflictError:
            pass
        else:
            raise RuntimeError("stale writer unexpectedly overwrote the winning generation")

        verifier = GoogleCloudStorageCheckpointStore(bucket, key, object_name)
        winner = verifier.load()
        if winner is None or winner.sequence != 2:
            raise RuntimeError("winning checkpoint was not preserved after stale-writer conflict")

        metrics = writer_b.prometheus_metrics()
        expected_metric = 'stageguard_checkpoint_saves_total{result="conflict"} 1'
        if expected_metric not in metrics:
            raise RuntimeError("checkpoint conflict metric was not emitted")

        print("PASS: strict GCS checkpoint CAS preserved the winning state")
        print("PASS: stale writer produced CheckpointConflictError")
        print("PASS: checkpoint conflict metric incremented")
        return 0
    finally:
        if keep:
            print(f"Acceptance object retained by request: gs://{bucket_name}/{object_name}")
        else:
            try:
                if blob.exists():
                    _cleanup(blob)
            except Exception as exc:
                # Cleanup failure must be visible; the object is unique and contains
                # only synthetic acceptance data, but operators should remove it.
                print(f"WARNING: acceptance object cleanup failed: gs://{bucket_name}/{object_name}", file=sys.stderr)
                print(f"Cleanup error type: {type(exc).__name__}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate StageGuard GCS checkpoint stale-writer CAS behavior")
    parser.add_argument("--bucket", required=True, help="Private GCS bucket used for StageGuard checkpoints")
    parser.add_argument("--project", default=None, help="Optional Google Cloud project for ADC client construction")
    parser.add_argument("--keep", action="store_true", help="Retain the unique synthetic acceptance object for inspection")
    args = parser.parse_args()
    return run(args.bucket, project=args.project, keep=args.keep)


if __name__ == "__main__":
    raise SystemExit(main())
