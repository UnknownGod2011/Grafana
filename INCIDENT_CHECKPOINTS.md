# Incident lifecycle checkpoints

StageGuard keeps the operator audit trail and the mutable incident lifecycle as separate persistence concerns. Audit history answers **what happened**; the incident checkpoint answers **what state is safe to resume after a restart**.

## What is persisted

`stageguard.incident-checkpoint.v1` stores only the minimum server-side state needed to restore the active lifecycle:

- incident ID;
- exact deterministic evidence revision;
- deterministic `IncidentReport` and bounded evidence;
- matching human approval, when one exists;
- bounded remediation/recovery outcome, when already consumed;
- the latest local audit sequence.

The document carries a SHA-256 over canonical state and is rejected if malformed, oversized, scope-inconsistent, or if the restored revision does not equal a fresh hash of the restored report. An approval is accepted only when it exactly reconstructs the policy-owned action/production/target for that restored report and telemetry profile. An outcome cannot exist without an approval.

Provider credentials, Gemini output, arbitrary remediation metadata, endpoint details, bearer tokens, Grafana credentials, and browser state are never checkpointed. Restored action details are replaced with a fixed local marker and provider metadata is discarded.

## Local/free development

The CLI defaults to an atomic owner-only JSON checkpoint at:

```text
.stageguard/incident-checkpoint.json
```

The `.stageguard/` directory is ignored by Git. Writes use a temporary file, `fsync`, atomic `os.replace`, and mode `0600`. This is useful for local process/machine restarts but must not be confused with Cloud Run instance durability.

Disable checkpointing explicitly with:

```bash
--checkpoint-backend none
```

## Google Cloud / Cloud Run

For durable Cloud Run lifecycle state, set a deployment-owned bucket name:

```text
STAGEGUARD_CHECKPOINT_BUCKET=<private bucket>
```

Optionally set:

```text
STAGEGUARD_CHECKPOINT_OBJECT=stageguard/incident-checkpoint.json
```

The Cloud Run entrypoint enables the GCS checkpoint adapter only when the bucket variable is present. Otherwise it selects `--checkpoint-backend none`; StageGuard does not claim that ephemeral container disk is restart-safe.

The adapter uses Application Default Credentials and a fixed server-owned bucket/object mapping. The browser cannot select bucket names, object names, generations, or storage operations.

Each GCS write uses an object-generation precondition. Creation uses `if_generation_match=0`; updates reload the current object generation and require that exact generation on upload. A competing writer therefore fails instead of silently overwriting newer lifecycle state. This follows Google Cloud Storage's documented generation-precondition pattern for avoiding races and data corruption.

Recommended IAM scope is the narrowest bucket/object permission your deployment supports. Do not reuse Grafana credentials or remediation credentials for storage.

## Approval/restart safety

A checkpointed approval remains bound to the exact restored evidence revision. A new investigation always replaces the snapshot with `approval=None`, persists that new revision, and therefore invalidates the old approval before any later execution can occur.

If a remediation outcome was persisted, the approval is considered consumed after restart and `execute_approved()` refuses a second execution.

There is one unavoidable distributed-systems boundary: a process can terminate after an external remediation endpoint accepted a request but before the resulting checkpoint was committed. StageGuard's production remediation path therefore uses a deterministic operation ID derived from the report and action, and the production adapter sends that same idempotency identity on retries. The storage generation precondition additionally prevents two StageGuard writers from silently replacing one another's newer checkpoint.

## Current validation status

Credential-free unit coverage exists for local restart restoration, approval invalidation, consumed-approval restoration, checkpoint tamper rejection, provider-metadata stripping, GCS create/update generation preconditions, and object-name bounds.

A real GCS/Cloud Run acceptance test still requires a Google Cloud project, private bucket, ADC/service-account permissions, and a runnable checkout environment.
