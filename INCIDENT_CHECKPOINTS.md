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

Each GCS write also uses an object-generation precondition. Creation uses `if_generation_match=0`; updates reload the current object generation and require that exact generation on upload. A competing writer therefore fails instead of silently overwriting newer lifecycle state. This follows Google Cloud Storage's documented generation-precondition pattern for avoiding races and data corruption.

Use the narrowest bucket/object IAM available. Bucket write permission alone is intentionally insufficient to forge lifecycle authorization because a valid HMAC is also required.

## Approval/restart safety

A checkpointed approval remains bound to the exact restored evidence revision. A new investigation always replaces the snapshot with `approval=None`, persists that new revision, and therefore invalidates the old approval before later execution.

If a remediation outcome was persisted, the approval is considered consumed after restart and `execute_approved()` refuses a second execution.

There is one unavoidable distributed-systems boundary: a process can terminate after an external remediation endpoint accepted a request but before the resulting checkpoint commit. StageGuard's production remediation path therefore uses a deterministic operation ID derived from the report and action, and the production adapter sends the same idempotency identity on retries. GCS generation preconditions additionally prevent concurrent StageGuard writers from silently replacing newer state.

## Current validation status

Credential-free unit coverage exists for local restart restoration, approval invalidation, consumed-approval restoration, checkpoint tamper rejection, provider-metadata stripping, GCS create/update generation preconditions, wrong-HMAC rejection, unsigned/forged-state rejection, short-key rejection, object-name bounds, and the Cloud Run startup requirement for a signing secret.

A real GCS/Cloud Run acceptance test still requires a Google Cloud project, private bucket, ADC/service-account permissions, injected checkpoint HMAC secret, and a runnable checkout environment.
