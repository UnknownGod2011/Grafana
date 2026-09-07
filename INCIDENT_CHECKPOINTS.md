# Incident lifecycle checkpoints

StageGuard keeps the operator audit trail and mutable incident lifecycle as separate persistence concerns. Audit history answers **what happened**; the incident checkpoint answers **what state is safe to resume after a restart**.

## What is persisted

`stageguard.incident-checkpoint.v1` stores only the minimum server-side state needed to restore the active lifecycle: incident ID, exact deterministic evidence revision, deterministic `IncidentReport` and bounded evidence, matching human approval when present, bounded consumed remediation/recovery outcome, and the latest local audit sequence.

The document carries SHA-256 over canonical state. Production GCS checkpoints additionally carry HMAC-SHA-256 and are rejected unless the deployment supplies the matching secret key. This distinction matters: an unkeyed checksum detects corruption but must not allow a principal with bucket-write permission to forge an approved incident state.

On restore StageGuard recomputes the evidence revision, verifies telemetry scope, reconstructs the policy-owned approval target/action, rejects an outcome without approval, and fails closed on malformed or oversized state.

Provider credentials, Gemini output, arbitrary remediation metadata, endpoint details, bearer tokens, Grafana credentials, checkpoint signing keys, and browser state are never checkpointed. Restored action details use a fixed local marker and provider metadata is discarded.

## Local/free development

The CLI defaults to an atomic owner-only JSON checkpoint at `.stageguard/incident-checkpoint.json`. The directory is ignored by Git. Writes use a temporary file, `fsync`, atomic `os.replace`, and mode `0600`. This is useful for local process/machine restarts but is not Cloud Run durability. Disable it with `--checkpoint-backend none`.

## Google Cloud / Cloud Run

For durable Cloud Run lifecycle state configure both:

```text
STAGEGUARD_CHECKPOINT_BUCKET=<private bucket>
STAGEGUARD_CHECKPOINT_HMAC_KEY=<high-entropy secret, at least 32 bytes>
```

Optionally set:

```text
STAGEGUARD_CHECKPOINT_OBJECT=stageguard/incident-checkpoint.json
```

The HMAC key is deployment-owned secret material, is read only server-side, is never passed as a CLI argument, and must be managed separately from Grafana and remediation credentials. The Cloud Run entrypoint refuses GCS checkpoint mode if the key is absent. Without a checkpoint bucket it explicitly selects `--checkpoint-backend none`; StageGuard does not pretend ephemeral container disk is restart-safe.

The GCS adapter uses Application Default Credentials and a fixed server-owned bucket/object mapping. The browser cannot choose bucket names, object names, generations, signatures, or storage operations.

### Strict compare-and-swap semantics

Each GCS store instance pins the exact object generation it successfully loaded or wrote. The next save uses **that pinned generation** as `if_generation_match`; it does not re-read the latest generation immediately before upload. A fresh store that has not loaded an existing object may only attempt creation with `if_generation_match=0`.

This distinction is critical. If two StageGuard instances both restore generation `N`, instance A may write generation `N+1`, but instance B must still attempt its write against `N` and receive a conflict. Re-reading `N+1` inside B's save path would turn optimistic concurrency into a last-writer-wins overwrite and could replace a newer approval-bearing lifecycle state.

Reads are generation-bound as well: after metadata reload, StageGuard downloads bytes with `if_generation_match=<pinned generation>` so the validated HMAC/document corresponds to the generation that becomes the process's next compare-and-swap token.

HTTP 412 generation-precondition failures are mapped to bounded `CheckpointConflictError` values. Provider exception text is not exposed. A conflict does not advance the process-local generation token and never triggers a blind retry.

Use the narrowest bucket/object IAM available. Bucket write permission alone is intentionally insufficient to forge lifecycle authorization because a valid HMAC is also required.

## Checkpoint observability

Configured JSON and GCS stores are wrapped by `ObservableCheckpointStore`. `/metrics` includes fixed-label checkpoint telemetry alongside evidence-plane readiness metrics:

- `stageguard_checkpoint_last_operation_ok`
- `stageguard_checkpoint_loads_total{result="ok|empty|failed"}`
- `stageguard_checkpoint_saves_total{result="ok|conflict|failed"}`
- `stageguard_checkpoint_last_operation_latency_seconds{operation="load|save"}`

These metrics intentionally contain no bucket names, object names, generations, incident IDs, evidence revisions, actor IDs, credentials, exception strings, signing material, or provider details. A concurrency conflict is counted separately from a storage/provider failure so operators can distinguish expected optimistic-concurrency contention from an unavailable persistence plane.

Checkpoint conflicts remain fail-closed. The observability wrapper does not retry, merge, or overwrite newer state; it re-raises the conflict to the lifecycle caller. Any future retry policy must first reload and revalidate current lifecycle state rather than blindly replaying an approval-bearing checkpoint.

## Approval/restart safety

A checkpointed approval remains bound to the exact restored evidence revision. A new investigation always replaces the snapshot with `approval=None`, persists that new revision, and therefore invalidates the old approval before later execution.

If a remediation outcome was persisted, the approval is considered consumed after restart and `execute_approved()` refuses a second execution.

There is one unavoidable distributed-systems boundary: a process can terminate after an external remediation endpoint accepted a request but before the resulting checkpoint commit. StageGuard's production remediation path therefore uses a deterministic operation ID derived from the report and action, and the production adapter sends the same idempotency identity on retries. GCS generation preconditions additionally prevent concurrent StageGuard writers from silently replacing newer state.

## Current validation status

Credential-free unit coverage exists for local restart restoration, approval invalidation, consumed-approval restoration, checkpoint tamper rejection, provider-metadata stripping, GCS create/update generation preconditions, stale-writer conflict behavior, create-only behavior for a fresh uninitialized writer, generation-bound reads, bounded 412 classification, wrong-HMAC rejection, unsigned/forged-state rejection, short-key rejection, object-name bounds, checkpoint metric privacy/result classification, and the Cloud Run startup requirement for a signing secret.

A real GCS/Cloud Run acceptance test still requires a Google Cloud project, private bucket, ADC/service-account permissions, injected checkpoint HMAC secret, and a runnable checkout environment.
