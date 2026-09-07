# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → authenticated operator cockpit/timeline → durable Cloud Logging reconstruction → versioned incident lifecycle checkpoints → signed GCS persistence with strict generation CAS → bounded checkpoint observability → safe real-bucket CAS acceptance harness → Cloud Run/IAP deployment → liveness/readiness/self-observability`

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
- The GCS acceptance harness uses only a UUID-scoped `stageguard/acceptance/` object and never reads or writes the production checkpoint object.
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
- Operator-runnable real-GCS two-writer CAS acceptance harness with isolated object namespace and generation-bound cleanup.

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

Updated `INCIDENT_CHECKPOINTS.md`:

- added the safe two-writer acceptance contract;
- documented exact environment/CLI usage;
- documented isolated object namespace and cleanup behavior;
- documented least-privilege guidance and the fact that the harness never uses `STAGEGUARD_CHECKPOINT_OBJECT`.

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

The container failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore the Python suite and the new script are **not claimed as executed successfully in this runtime**. The script itself was re-read from GitHub after creation to verify the committed source. No Grafana, Loki, Gemini, IAP, Cloud Logging, Cloud Storage, Secret Manager, operator, or remediation credential was used, and no production/cloud resource was changed.

### Decisions made

1. **Acceptance must exercise production code.** The harness imports the real GCS checkpoint store and observability wrapper rather than duplicating CAS logic.
2. **Never test against the production checkpoint key.** Every run uses a random `stageguard/acceptance/` object.
3. **Cleanup must itself be concurrency-safe.** Default deletion uses the exact current generation precondition and only the unique object created by that invocation.
4. **Acceptance verifies observability as well as correctness.** A stale-writer 412 must become both `CheckpointConflictError` and the bounded conflict metric.
5. **No credential should enter source or argv.** The HMAC key is environment-only; ADC handles Google authentication.
6. **No blind conflict retry was introduced.** The production lifecycle remains fail-closed after contention.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve `github.com` for checkout.
- The new GCS race harness still needs execution against an actual private bucket with ADC/service-account permissions.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- A real deployment still needs secure injection of `STAGEGUARD_CHECKPOINT_HMAC_KEY`.
- Cloud Run multi-instance behavior still needs empirical testing with two actual processes/instances sharing one production checkpoint object after the isolated harness passes.
- The cockpit still needs real Cloud Run + IAP browser acceptance.
- Grafana MCP readiness and the full metric+Loki investigation path still need acceptance against a real Grafana Cloud or self-hosted instance.

## Single best next step

**Run `scripts/gcs_checkpoint_race_acceptance.py` against a private acceptance bucket with least-privilege ADC and a secret-backed HMAC key. Require all three PASS conditions (winner preserved, stale writer conflicts, conflict metric increments) and successful generation-bound cleanup. If that passes, add a bounded conflict-recovery state to `IncidentService` that forces explicit checkpoint reload + full lifecycle revalidation before the instance can accept another approval/remediation command; do not implement automatic replay of the failed write.**
