# Checkpoint conflict recovery

StageGuard treats a durable checkpoint compare-and-swap conflict as a lifecycle consistency fault, not as a transient write error.

## Safety contract

When a checkpoint save raises `CheckpointConflictError`, `IncidentService` enters the `conflicted` state immediately. While conflicted it refuses investigation, Gemini briefing writes, approval, and remediation execution. It does **not** retry the failed checkpoint write and does not attempt to merge approval-bearing state.

The losing process may still hold speculative in-memory state produced immediately before the failed save. Operators and API clients must therefore treat `/v1/incident` as informational until recovery completes. `/readyz` returns not-ready while the service is conflicted and `/metrics` exposes `stageguard_checkpoint_conflict_blocked 1`.

Recovery is explicit and authenticated:

```text
POST /v1/checkpoint/reload
{}
```

The endpoint is accepted only while a conflict is active. It loads the durable winner through the configured checkpoint store, re-runs the same revision, telemetry-scope, approval, and outcome validation used during startup restoration, replaces the local snapshot/sequence, discards speculative in-process timeline entries, and only then returns the service to `synchronized`.

If the durable object cannot be loaded or fails validation, recovery fails closed and the service remains conflicted. Restarting the process is also safe because startup restoration validates the durable winner from scratch.

## Important remediation caveat

A checkpoint conflict can theoretically occur after an external remediation provider accepted an idempotent operation but before StageGuard durably recorded the outcome. Production remediation must therefore continue to use the deterministic StageGuard operation identity documented in `OPERATIONS_AND_SAFETY.md`; the checkpoint conflict path never blindly replays a failed approval-bearing write.

After any conflict associated with a real production remediation attempt, the conservative operator procedure is:

1. reload the durable checkpoint;
2. inspect the winning incident/revision and provider-side idempotency record;
3. run a fresh Grafana investigation to establish current evidence;
4. obtain a new revision-bound approval only if remediation is still required.

Do not treat a successful checkpoint reload as proof that an external remediation did or did not execute.

## Observability

Useful bounded signals are:

```text
stageguard_checkpoint_saves_total{result="conflict"}
stageguard_checkpoint_conflict_blocked
stageguard_checkpoint_last_operation_ok
stageguard_checkpoint_last_operation_latency_seconds{operation="load"}
```

These metrics intentionally contain no incident IDs, revisions, GCS object names/generations, operator identities, credentials, provider exception strings, or HMAC material.
