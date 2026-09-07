# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → authenticated operator cockpit/timeline → durable Cloud Logging reconstruction → versioned incident lifecycle checkpoints → signed GCS persistence with strict generation CAS → bounded checkpoint observability → Cloud Run/IAP deployment → liveness/readiness/self-observability`

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
- Checkpoint metrics use only fixed labels and never expose bucket/object names, generations, incident IDs, revisions, credentials, provider exceptions, or signing material.
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and checkpoint signing material are not persisted.
- Standard Cloud Run production remediation remains disabled.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes non-sensitive readiness/checkpoint telemetry.

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

## Run log — 2026-09-07 — strict GCS compare-and-swap hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/incident_checkpoint.py`
- `runtime/incident_service.py`
- `runtime/tests/test_gcs_checkpoint.py`
- `INCIDENT_CHECKPOINTS.md`

The previous handoff called for a two-instance GCS race acceptance. While reviewing the code needed for that test, I found a correctness flaw that had to be fixed first: `GoogleCloudStorageCheckpointStore.save()` re-read the object's *current* generation immediately before every upload. Two instances could therefore both load generation `N`; instance A could write `N+1`; then instance B could reload `N+1` inside `save()` and overwrite it successfully. That is last-writer-wins behavior, not optimistic concurrency, and is unsafe for approval-bearing lifecycle state.

### Exact changes made

Updated `runtime/incident_checkpoint.py`:

- GCS store now maintains a process-local generation token protected by a lock;
- a fresh store starts with expected generation `0`, meaning create-only until it successfully loads an existing object;
- successful `load()` reloads object metadata, validates the generation, and downloads bytes with `if_generation_match=<that generation>`;
- only after the HMAC/document is successfully decoded is that generation accepted as the store's next compare-and-swap token;
- successful `save()` uses the previously pinned generation directly and never performs an `exists()`/`reload()` just before upload;
- after a successful upload, the returned blob generation becomes the next expected generation;
- HTTP 412 on a generation-bound read or write remains a bounded `CheckpointConflictError`;
- conflicts do not advance the local generation token and no automatic retry/merge/overwrite is attempted;
- provider exception text remains hidden.

Updated `runtime/tests/test_gcs_checkpoint.py`:

- fake downloads now enforce optional generation-match preconditions;
- renamed the normal update test to assert use of the generation pinned by the prior successful operation;
- added a two-writer stale-state regression: both instances load generation 1, writer A creates generation 2, writer B must conflict when still attempting generation 1, and the winner remains persisted;
- added a regression proving a fresh store cannot overwrite an existing object without first loading it;
- retained bounded conflict, HMAC, forgery, traversal, and signing-key tests.

Updated `INCIDENT_CHECKPOINTS.md`:

- corrected the prior documentation that said updates reload the current generation before upload;
- documented exact pinned-generation CAS semantics and why re-reading during save is unsafe;
- documented generation-bound reads and fail-closed conflict behavior;
- updated validation coverage to include stale-writer and fresh-writer cases.

### Commits produced this run

- `61b57f3d` — fix GCS checkpoint compare-and-swap semantics
- `670321a4` — test stale GCS checkpoint writer conflicts
- `0cdffb56` — document strict GCS checkpoint CAS boundary

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

The authenticated GitHub connector allowed direct repository inspection and edits, but this automation environment still does not expose a runnable repository checkout. Therefore the Python suite is **not claimed as passing in this run**. No Grafana, Loki, Gemini, IAP, Cloud Logging, Cloud Storage, Secret Manager, operator, or remediation credential was used, and no production resource was changed.

### Decisions made

1. **CAS must be based on restored state, not latest state.** The generation used for a write is the generation this process previously validated, not whatever generation exists when the write starts.
2. **Fresh writers are create-only.** A new process cannot overwrite an existing object until it has loaded and validated that object first.
3. **Reads are generation-bound.** The bytes whose HMAC is validated must correspond to the same generation that becomes the next write precondition.
4. **No blind conflict retry.** A 412 remains a hard lifecycle conflict until the caller reloads and revalidates state explicitly.
5. **Do not change readiness policy yet.** Persistence contention should not be conflated with Grafana evidence-plane readiness until empirical multi-instance behavior is measured.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because there is no runnable checkout path.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- GCS fake-client coverage is stronger, but the adapter still needs acceptance against an actual private bucket/service account.
- A real deployment still needs secure injection of `STAGEGUARD_CHECKPOINT_HMAC_KEY`.
- Cloud Run multi-instance behavior still needs empirical testing with two actual processes/instances sharing one object.
- The cockpit still needs real Cloud Run + IAP browser acceptance.
- Grafana MCP readiness and the full metric+Loki investigation path still need acceptance against a real Grafana Cloud or self-hosted instance.

## Single best next step

**Run the now-correct two-instance GCS acceptance in a runnable environment: have both StageGuard instances load the same signed checkpoint generation, let one persist the next lifecycle state, verify the stale writer receives `CheckpointConflictError` and increments `stageguard_checkpoint_saves_total{result="conflict"}`, then explicitly reload and revalidate the winning state. Only after that evidence should any narrowly scoped retry policy be considered, and never for replaying approval-bearing state blindly.**
