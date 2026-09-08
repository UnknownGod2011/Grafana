# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, and checkpoint schema v2 with a durable pre-side-effect remediation phase.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; `approved` therefore proves dispatch has not begun.
- Restored `dispatching` and legacy-v1 pending approvals fail closed and require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use strict generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution-phase telemetry is fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.

## Completed milestones

- Deterministic media telemetry simulator plus local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and strict evidence scope.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded `accepted` / `not_found` / `unknown` states.
- Revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, strict CAS conflict handling, and operator recovery cockpit.
- Checkpoint schema v2 phases: `none`, `approved`, `dispatching`, `resolved`, with conservative legacy restore.
- Fixed-cardinality execution-phase readiness/Prometheus observability.
- Crash-boundary fault-injection regression matrix for approval persistence, dispatch barrier persistence, provider execution, Grafana recovery verification, and resolved checkpoint persistence.
- Real spawned-process SIGKILL acceptance coverage using `JsonCheckpointStore` across the two most dangerous remediation boundaries.
- Real loopback TLS coverage for `HttpRemediationTransport` execution and GET-only reconciliation.
- Spawned-process SIGKILL acceptance routed through the concrete HTTPS remediation transport and a local idempotent provider server.
- Concrete HTTPS restart coverage for malformed, wrong-operation, unknown-state, and timeout reconciliation outcomes, including later authoritative recovery.
- Credential-free spawned-process GCS generation-CAS acceptance with a process-safe fake object backend.

## Run log — 2026-09-08 — multiprocess GCS generation CAS

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/incident_checkpoint.py`, especially `GoogleCloudStorageCheckpointStore.load()` / `save()` and its `if_generation_match` handling;
- `runtime/tests/test_gcs_checkpoint.py` for existing sequential stale-writer coverage;
- `runtime/tests/test_checkpoint_conflict_recovery.py` for lifecycle conflict semantics;
- `runtime/execution_safety.py` for dispatch-barrier and execution-uncertainty interaction.

Also checked current official Google Cloud Storage documentation. Google documents generation preconditions as the mechanism for safe conditional read/modify/write operations: `if_generation_match=0` succeeds only when no live object exists, while an existing object's current generation can be supplied to prevent stale overwrites. This matches StageGuard's checkpoint-store design.

Official reference reviewed: https://docs.cloud.google.com/python/docs/reference/storage/latest/generation_metageneration (last updated 2026-08-25 UTC).

### Exact changes made

1. Added `runtime/tests/test_gcs_multiprocess_cas.py`.
   - Implements a credential-free, process-safe fake GCS object backend with atomic generation checks and the subset of `Blob` semantics used by `GoogleCloudStorageCheckpointStore`.
   - Uses Python `spawn` processes so each writer owns an independent `GoogleCloudStorageCheckpointStore` instance rather than sharing in-process store state.
   - Seeds generation 1, then has two child processes load that same generation and race writes. The acceptance assertion requires exactly one winner and exactly one bounded `CheckpointConflictError` loser.
   - After the first race, a fresh store adopts the durable winner and writes a newer modeled recovery checkpoint, advancing the generation again.
   - The original losing child is then released to retry using its still-stale generation. The retry must conflict again, proving a stale StageGuard instance cannot overwrite a newer recovered incident merely because time has passed or another process completed recovery.
   - Final verification loads the durable object through a new store and requires the recovered sequence to remain authoritative.
   - Adds a second spawned-process race for first-object creation, proving two independently initialized stores both observe empty state but `if_generation_match=0` permits only one creator.

2. Kept production behavior unchanged.
   - No GCS retry broadening, precondition weakening, credential use, network emulation inside production code, or checkpoint schema change was introduced.
   - The new backend exists only in tests and models the generation semantics StageGuard depends on.

### Tests / checks / results

The repository changes were written successfully through the GitHub connector. A deterministic local Python execution is still not available in this environment because prior checkout attempts fail before Python starts with DNS resolution errors for `github.com`; therefore these new tests are **not claimed as executed successfully here**.

No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Model the GCS contract, not Google credentials.** The test backend implements only the object/generation operations used by StageGuard, keeping acceptance deterministic and free.
2. **Use independent spawned processes.** This prevents an in-process Python lock or shared store field from accidentally proving a concurrency guarantee that production does not have.
3. **Keep the loser alive after its first conflict.** This makes the stronger stale-writer assertion possible: even after a fresh process advances the recovered checkpoint, the old process still cannot overwrite it.
4. **Cover create-only semantics separately.** StageGuard's initial checkpoint creation is protected by generation 0, so two empty-state instances must still yield exactly one durable creator.

### Current blockers / unknowns

- Local deterministic Python execution remains blocked by checkout/DNS limitations in the execution container.
- The new multiprocess harness validates the production GCS precondition contract without credentials, but it is not a substitute for a real GCS emulator/live two-instance acceptance run.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Lift the new generation-aware multiprocess backend into an end-to-end `ExecutionSafeIncidentService` concurrency acceptance test: race two independently restored services on the same approved checkpoint, prove only one can persist `dispatching` and therefore only that winner can contact remediation, then advance recovery and prove the stale loser remains conflict-blocked with zero provider calls.**

## Previous run — 2026-09-08 — fail-closed HTTPS reconciliation ambiguity

Added concrete TLS/process-death reconciliation coverage for malformed JSON, wrong operation-id echoes, unknown provider state, and timeout. Every ambiguous result preserves `execution_uncertain`, blocks readiness, performs no second remediation POST, and requires later authoritative reconciliation plus fresh Grafana evidence.

## Previous run — 2026-09-08 — concrete HTTPS process-death replay safety

Added a real loopback TLS provider and spawned-process SIGKILL acceptance routed through `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, and `HttpRemediationTransport`. Proved zero POSTs when killed before HTTP dispatch and exactly one POST when killed after provider acceptance, with GET-only reconciliation and fresh Grafana evidence on restart.

## Previous run — 2026-09-08 — real process-death replay-safety acceptance

Added `runtime/tests/test_subprocess_crash_recovery.py` using a spawned interpreter, real `JsonCheckpointStore`, fsynced modeled provider state, and POSIX SIGKILL after durable `dispatching` and after modeled provider acceptance. Restart required reconciliation plus fresh Grafana evidence and never replayed remediation.
