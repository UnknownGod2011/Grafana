# Authenticated Local Audit Retention

StageGuard supports destructive retention only for the local anchored JSONL audit backend. Cloud Logging retention remains advisory/read-only because StageGuard does not yet have an exhaustive provider-specific deletion contract.

## Safety contract

Local retention is explicitly two-phase and lock-coordinated:

1. `prepare` loads an HMAC-authenticated incident checkpoint, requires verified audit integrity and a non-genesis authenticated audit anchor, inventories the exact eligible JSONL records, hashes the exact checkpoint state and audit-file bytes, and writes a signed retention plan.
2. `execute` accepts only that exact signed plan, reloads the current authenticated checkpoint, revalidates checkpoint and audit-file digests plus the exact candidate set, creates an owner-only byte-for-byte backup, fsyncs durable state, and atomically replaces the audit file.
3. Both phases hold the same sidecar lock used by `AnchoredJsonlAuditLog` readers and writers, so cooperating StageGuard processes cannot append inside the validation-to-replace window.

Retention never advances beyond the authenticated anchor, and records for other incidents plus all post-anchor records are preserved.

## Supported operator entrypoint

Use only `runtime/retention_coordinator.py` for local destructive retention. `runtime/retention_executor.py` is a lower-level implementation module and is not an operator CLI contract because invoking it directly bypasses cooperative writer/read coordination.

The signing key is read from an environment variable rather than command-line arguments. The default name is `STAGEGUARD_CHECKPOINT_HMAC_KEY`.

Prepare a plan:

```bash
python runtime/retention_coordinator.py prepare \
  --checkpoint .stageguard/incident-checkpoint.json \
  --audit-jsonl .stageguard/audit.jsonl \
  --plan-out .stageguard/retention-plan.json \
  --audit-integrity-state verified
```

Review the generated plan artifact before execution. Then execute that exact artifact:

```bash
python runtime/retention_coordinator.py execute \
  --checkpoint .stageguard/incident-checkpoint.json \
  --plan .stageguard/retention-plan.json \
  --backup .stageguard/audit.pre-retention.backup.jsonl
```

Do not edit or recreate the plan between phases. Any HMAC failure, checkpoint drift, source-file drift, candidate-set drift, malformed input, backup conflict, or unsupported trust state causes a fail-closed refusal.

## Concurrency boundary

The coordinator and `AnchoredJsonlAuditLog` use `.<audit-name>.stageguard.lock` beside the audit file. StageGuard uses an in-process re-entrant lock plus an OS-level exclusive lock (`flock` on POSIX and `msvcrt.locking` on Windows). A spawn-based regression test verifies that a writer in a separate process cannot pass the lock while another process holds it.

This is a cooperative contract. External programs that write directly to the JSONL file without taking the StageGuard sidecar lock are unsupported during retention. Source-digest and candidate-set checks still detect many forms of drift, but operators should stop non-cooperating writers before compaction.

## Recovery

Execution creates the backup before atomic replacement. Keep the backup until the restarted runtime has successfully verified its authenticated audit suffix and readiness. If operator recovery is required, stop StageGuard writers, restore the backup to the original audit path, and restart normally so checkpoint/audit verification can fail closed if anything is inconsistent.
