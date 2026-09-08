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
- End-to-end spawned-process `ExecutionSafeIncidentService` race over the generation-aware GCS backend, proving the durable `dispatching` CAS gates provider contact.

## Run log — 2026-09-08 — service-level GCS dispatch CAS race

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/tests/test_gcs_multiprocess_cas.py` for the existing process-safe generation-aware fake GCS backend and storage-level race coverage;
- `runtime/execution_safety.py`, especially `_persist_dispatching_barrier()` and `execute_approved()`, to verify that a dispatch-barrier CAS conflict is raised before entering the provider execution path;
- `runtime/tests/test_execution_crash_matrix.py` for the expected recovery telemetry, remediation adapter shape, and fail-closed checkpoint-conflict semantics;
- `runtime/incident_checkpoint.py` for `GoogleCloudStorageCheckpointStore` generation tracking and schema-v2 execution phases;
- `runtime/remediation.py` for approval structure, deterministic idempotent execution, and telemetry-based recovery verification.

### Exact changes made

1. Added `runtime/tests/test_execution_gcs_multiprocess_cas.py`.
   - Seeds a signed schema-v2 `approved` checkpoint through the real `GoogleCloudStorageCheckpointStore` using the credential-free process-safe fake GCS backend.
   - Spawns two independent Python processes. Each constructs its own `GoogleCloudStorageCheckpointStore` and `ExecutionSafeIncidentService`, restores the exact same approved generation, and waits at a process barrier.
   - Both services race `execute_approved()` against the same durable checkpoint generation.
   - Requires exactly one service to persist `dispatching`; the losing service must receive `CheckpointConflictError` before remediation can be contacted.
   - Uses a process-shared remediation-call ledger and asserts exactly one provider execution across the race.
   - Requires the winner to finish Grafana/Prometheus recovery verification and persist `resolved`, giving the expected generation sequence `approved -> dispatching -> resolved`.
   - Keeps the losing process alive with its stale original generation. Only after recovery is durable is that loser released to call `execute_approved()` again; it must conflict a second time before provider contact.
   - Final verification loads the checkpoint through a fresh store and requires `resolved/recovered` to remain authoritative, generation to remain unchanged, and provider-call count to remain exactly one.

2. Tightened the new test after review.
   - Removed an unused shared-blob import.
   - Kept all production code unchanged; this run adds acceptance coverage only.

### Tests / checks / results

- Repository writes succeeded through the GitHub connector.
- Performed a local Python syntax compilation check on the new test header/import structure; no syntax error was found in that checked fragment.
- A deterministic repository-wide Python execution is still unavailable in this environment because previous checkout attempts fail before Python starts with DNS resolution errors for `github.com`; therefore the new multiprocess test is **not claimed as executed successfully here**.
- No GitHub Actions workflow was intentionally triggered, rerun, or modified.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Test the safety property at the service boundary.** Storage CAS alone is insufficient; the important invariant is that losing the `dispatching` CAS must imply zero provider calls.
2. **Use spawned processes, not threads.** Each StageGuard instance owns independent in-memory generation state, matching separate Cloud Run instances more closely than an in-process race.
3. **Keep the stale loser alive through winner recovery.** This proves a stale instance cannot become dangerous after the winner advances the checkpoint to `resolved`.
4. **Do not broaden retries.** The loser is expected to remain conflict-blocked until it explicitly reloads durable state; automatic retries could weaken the pre-side-effect safety boundary.

### Current blockers / unknowns

- The new end-to-end multiprocess acceptance test has not been executed in a full repository checkout in this environment.
- The process-safe GCS backend models generation preconditions but is not a substitute for a real GCS emulator/live two-instance Cloud Run acceptance run.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Add a multi-instance recovery/reconciliation race starting from durable `dispatching`: restore two services against the same ambiguous operation, let both obtain an authoritative provider reconciliation result, then race their fresh Grafana investigation checkpoint writes. Prove only one recovery revision becomes durable, the stale reconciler is conflict-blocked, neither instance can issue remediation during reconciliation, and a fresh restart adopts exactly the winning evidence revision with no stale approval.**

## Previous run — 2026-09-08 — multiprocess GCS generation CAS

Added a credential-free process-safe fake GCS backend and spawned-process generation-CAS acceptance. Two stores racing the same generation yield one winner/one conflict; an original stale loser remains unable to overwrite a later recovered checkpoint, and first-object creation is separately protected by generation 0.

## Previous run — 2026-09-08 — fail-closed HTTPS reconciliation ambiguity

Added concrete TLS/process-death reconciliation coverage for malformed JSON, wrong operation-id echoes, unknown provider state, and timeout. Every ambiguous result preserves `execution_uncertain`, blocks readiness, performs no second remediation POST, and requires later authoritative reconciliation plus fresh Grafana evidence.

## Previous run — 2026-09-08 — concrete HTTPS process-death replay safety

Added a real loopback TLS provider and spawned-process SIGKILL acceptance routed through `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, and `HttpRemediationTransport`. Proved zero POSTs when killed before HTTP dispatch and exactly one POST when killed after provider acceptance, with GET-only reconciliation and fresh Grafana evidence on restart.
