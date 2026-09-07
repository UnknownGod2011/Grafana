# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → authenticated operator cockpit/timeline → durable Cloud Logging reconstruction → versioned incident lifecycle checkpoints → signed GCS persistence with strict generation CAS → bounded checkpoint observability → safe real-bucket CAS acceptance harness → fail-closed conflict recovery → Cloud Run/IAP deployment → liveness/readiness/self-observability`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Fresh investigation clears prior approval/outcome before persisting the new revision.
- Audit history and mutable lifecycle state remain separate persistence concerns.
- Restored checkpoints must match configured telemetry scope and recompute to the persisted evidence revision.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict object-generation compare-and-swap.
- A StageGuard instance may only replace the exact GCS generation it previously loaded or successfully wrote; it never re-reads the latest generation inside save and silently overwrites a winner.
- Generation conflicts fail closed and are observable separately from provider/storage failures.
- Once a checkpoint conflict occurs, lifecycle-changing work is blocked until an explicit load of the durable winner succeeds and the restored revision/scope/approval/outcome passes full validation.
- A failed checkpoint write is never automatically replayed or merged.
- The GCS acceptance harness uses only a UUID-scoped `stageguard/acceptance/` object and never reads or writes the production checkpoint object.
- Checkpoint metrics use only fixed labels and never expose bucket/object names, generations, incident IDs, revisions, credentials, provider exceptions, or signing material.
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and checkpoint signing material are not persisted.
- Standard Cloud Run production remediation remains disabled.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane and lifecycle checkpoint consistency; `/metrics` exposes non-sensitive readiness/checkpoint telemetry.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and writes/proxied tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric/Loki preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS production remediation transport with deterministic idempotency identity.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Cloud Logging audit sink.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled.
- `/healthz`, fail-closed `/readyz`, readiness caching/backoff, and Prometheus-format runtime self-observability.
- Authenticated same-origin operator cockpit for evidence, Gemini briefing, typed revision approval, execution and recovery state.
- Bounded incident audit timeline with sequence pagination, actor pseudonymization, payload allow-lists, and durable Cloud Logging reconstruction.
- Versioned `stageguard.incident-checkpoint.v1` lifecycle persistence.
- Atomic owner-only JSON local checkpoint store.
- GCS checkpoint store with ADC, fixed deployment-owned object mapping, HMAC authenticity, generation-bound reads, and strict pinned-generation compare-and-swap writes.
- Restart restoration of incident report/revision/approval/consumed outcome with fail-closed scope/revision validation.
- Bounded checkpoint conflict classification and Prometheus load/save/latency observability.
- Operator-runnable real-GCS two-writer CAS acceptance harness with isolated object namespace and generation-bound cleanup.
- IncidentService conflict-blocked state with explicit durable-winner reload/revalidation and authenticated HTTP recovery endpoint.

## Run log — 2026-09-07 — real-GCS CAS acceptance harness

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch;
- root repository contents and `scripts/`;
- `runtime/incident_checkpoint.py`;
- `runtime/tests/test_gcs_checkpoint.py`;
- `INCIDENT_CHECKPOINTS.md`.

The previous handoff correctly identified that the strongest remaining checkpoint increment was empirical two-instance GCS acceptance. No Google Cloud credentials are available in this runtime, so the most useful unblocked progress was to make that acceptance deterministic, safe, and operator-runnable using the production checkpoint adapter rather than a parallel test implementation.

### Exact changes made

Added `scripts/gcs_checkpoint_race_acceptance.py`:

- uses the production `GoogleCloudStorageCheckpointStore` and `ObservableCheckpointStore` implementations;
- requires `STAGEGUARD_CHECKPOINT_HMAC_KEY` from the environment and rejects keys shorter than 32 bytes;
- uses Application Default Credentials through `google-cloud-storage`;
- creates exactly one UUID-scoped object under `stageguard/acceptance/checkpoint-cas-<uuid>.json`;
- refuses to reuse a pre-existing acceptance object;
- seeds generation 1 with synthetic, non-production incident state;
- creates two independent store instances and requires both to load the same generation;
- writer A persists sequence 2;
- stale writer B attempts sequence 3 and must receive `CheckpointConflictError`;
- verifies a fresh reader still sees sequence 2, proving the stale writer did not replace the winner;
- verifies `stageguard_checkpoint_saves_total{result="conflict"} 1` from the losing observable store;
- by default deletes only the exact UUID-scoped object it created, with a generation-match delete precondition;
- supports `--keep` for deliberate operator inspection;
- surfaces cleanup failure with the isolated object URI while never scanning or touching the production checkpoint object.

Updated `INCIDENT_CHECKPOINTS.md` with the safe two-writer acceptance contract, exact environment/CLI usage, isolated object namespace/cleanup behavior, and least-privilege guidance.

### Commits produced this run

- `a1430e77` — add safe GCS checkpoint race acceptance harness
- `5cc89a2c` — document GCS checkpoint race acceptance

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

Attempted a clean local validation with:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
PYTHONPATH=runtime python -m unittest runtime.tests.test_gcs_checkpoint runtime.tests.test_checkpoint_observability -v
```

The container failed before checkout with `Could not resolve host: github.com`. Therefore the Python suite and the new script were not claimed as executed successfully in that runtime.

## Run log — 2026-09-07 — checkpoint conflict recovery boundary

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository root/default branch;
- `runtime/incident_service.py`;
- `runtime/incident_checkpoint.py`;
- `runtime/tests/test_incident_checkpoint.py`;
- `runtime/tests/` inventory;
- `runtime/api.py`;
- `runtime/bootstrap.py`.

The highest-value unblocked issue was a multi-instance split-brain condition after a successful GCS conflict classification: the losing `IncidentService` could retain speculative local approval/outcome state even though its durable checkpoint save lost CAS. Without an explicit blocked state, that process could continue lifecycle work against state it no longer owned.

### Exact changes made

Updated `runtime/incident_service.py`:

- imports and handles `CheckpointConflictError` at the lifecycle persistence boundary;
- enters a durable `conflicted` process state immediately after any checkpoint CAS conflict;
- blocks investigation, Gemini briefing writes, approval, and remediation execution while conflicted;
- adds `checkpoint_state()` with bounded values `disabled`, `synchronized`, or `conflicted`;
- factors startup checkpoint validation into reusable `_validated_snapshot()` / `_apply_checkpoint()` helpers;
- adds `reload_checkpoint_after_conflict()` as the only in-process recovery path;
- reload requires an active conflict and configured persistence;
- reload loads the durable winner through the configured store (thereby repinning GCS generation), recomputes/validates the evidence revision, validates configured telemetry scope, reconstructs policy-owned approval, validates outcome/approval consistency, reconciles sequence with the durable audit reader, replaces the speculative local snapshot, clears speculative process-local timeline entries, and only then returns to `synchronized`;
- a failed reload leaves the service in `conflicted` state;
- no failed checkpoint write is retried automatically.

Added `runtime/tests/test_checkpoint_conflict_recovery.py` covering:

- conflict immediately blocks subsequent execute/investigate calls;
- no remediation call occurs from a losing speculative approval;
- explicit reload adopts the durable winner and clears the blocked state;
- a winning approval is adopted rather than merged with the loser's approval;
- missing durable state during recovery fails closed and keeps the service blocked;
- the reload method cannot be used as a general refresh endpoint when no conflict exists.

Updated `runtime/api.py`:

- `/readyz` now includes bounded checkpoint consistency and becomes HTTP 503 while conflict-blocked;
- `/metrics` now exposes `stageguard_checkpoint_conflict_blocked` as a zero/one gauge with no variable labels;
- authenticated `GET /v1/incident` includes the bounded checkpoint state;
- added authenticated `POST /v1/checkpoint/reload` with an empty body contract; it invokes only the explicit reload/revalidation path and accepts no object names, generations, revisions, provider details, or arbitrary merge data;
- bumped the API server version to `StageGuard/0.9`.

Added `CHECKPOINT_CONFLICT_RECOVERY.md` documenting the safety contract, operator recovery path, bounded metrics, and the important external-remediation caveat: a successful reload proves checkpoint ownership/state only, not whether a remote side effect happened before the losing persistence write.

### Commits produced this run

- `0275e8b7` — fail closed after checkpoint CAS conflicts
- `69411ade` — test checkpoint conflict recovery boundary
- `6da73949` — expose explicit checkpoint conflict recovery
- `f8ba6d7f` — document checkpoint conflict recovery

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

Attempted a fresh local checkout before implementation:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed with:

```text
Could not resolve host: github.com
```

The changed source was re-read through the GitHub connector after commit to verify that the conflict-state and reload/revalidation code landed. Because the container cannot obtain a checkout, the Python suite is **not claimed as executed successfully** in this run. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **A CAS conflict is a lifecycle consistency fault, not a retryable storage error.** The losing process becomes blocked immediately.
2. **Recovery is adoption, never merge/replay.** The process must load and fully validate the durable winner; caller data cannot participate in reconciliation.
3. **Readiness includes mutable-state consistency.** A process with healthy Grafana evidence but conflicted approval state is not production-ready.
4. **Recovery is authenticated but argument-free.** Operators can request revalidation, but cannot choose a generation/object/revision or inject replacement state.
5. **Speculative in-process timeline entries are discarded on successful adoption.** Durable audit reconstruction remains authoritative when configured.
6. **External remediation uncertainty is not hidden.** A checkpoint reload does not prove whether a provider-side action executed before a losing checkpoint save; deterministic remediation idempotency remains mandatory.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve `github.com` for checkout.
- The real-GCS race acceptance harness still needs execution against a private bucket with least-privilege ADC and a secret-backed HMAC key.
- The new HTTP conflict-recovery path needs live two-instance acceptance against GCS to verify the losing instance transitions `/readyz` to 503, exposes the blocked gauge, reloads the winner, and returns to 200 only after validation.
- A real checkpoint conflict that occurs after a production remediation provider accepted an operation remains an intentionally conservative ambiguity: the service never blindly replays the write/action, but provider-side idempotency/reconciliation must be checked before another remediation attempt.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The cockpit still needs real Cloud Run + IAP browser acceptance.
- Grafana MCP readiness and the full metric+Loki investigation path still need acceptance against a real Grafana Cloud or self-hosted instance.

## Single best next step

**Close the remaining remediation ambiguity after a checkpoint conflict: add an explicit `execution_uncertain` lifecycle state when a CAS conflict occurs after `remediate_and_verify()` has contacted the external remediation adapter. After durable-winner reload, keep approval/remediation blocked until a fresh Grafana investigation establishes current evidence (and, for production adapters, the deterministic provider idempotency record is reconciled). Add tests proving the same approval cannot be executed again merely because the durable winner still shows it as unconsumed.**
