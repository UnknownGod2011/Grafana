# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, and checkpoint schema v2 with a durable pre-side-effect remediation phase.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; a clean restart from durable `approved` therefore proves dispatch had not begun in that process lifetime.
- Restored `dispatching` and legacy-v1 pending approvals fail closed and require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use strict generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution-phase telemetry is fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.
- After CAS contention, process-local execution uncertainty is rebased from the authenticated durable winner, but direct knowledge that this process may already have crossed the dispatch barrier is never erased merely because a conflicting durable winner reports `approved`.

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
- End-to-end spawned-process `ExecutionSafeIncidentService` dispatch race over the generation-aware GCS backend, proving the durable `dispatching` CAS gates provider contact.
- End-to-end spawned-process reconciliation race from durable `dispatching`, proving exactly one fresh Grafana evidence revision becomes durable and the stale reconciler adopts that winner without remediation replay or redundant reconciliation.
- Service-level conflict-reload phase matrix for `none`, `approved`, `dispatching`, `resolved`, and `legacy_unknown`, including a fail-closed regression fix for contradictory post-dispatch `approved` winners.

## Run log — 2026-09-08 — conflict reload execution-phase matrix

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py` for restart ambiguity, dispatch barriers, conflict reload, and provider reconciliation;
- `runtime/tests/test_execution_safety.py` for the existing exception/CAS safety contract and local vs production adapter behavior;
- `runtime/incident_checkpoint.py` for schema-v2 phase validation and phase-capable store semantics;
- `runtime/remediation.py` for deterministic operation IDs and remediation outcome types;
- `runtime/incident_service.py` for explicit conflict reload, snapshot replacement, checkpoint writes, approval consumption, and lifecycle blocking.

### Exact changes made

1. Added `runtime/tests/test_execution_conflict_reload_phases.py`.
   - Creates a phase-capable conflict store and drives a real `ExecutionSafeIncidentService` through successful provider contact followed by a synthetic resolved-checkpoint CAS loss.
   - Replaces the durable winner with each relevant lifecycle phase and explicitly reloads it.
   - `none`: stale process ambiguity clears, no approval remains, and execution is impossible.
   - `resolved`: stale process ambiguity clears, the consumed approval remains non-executable, and provider call count stays one.
   - `dispatching`: remains `execution_uncertain`, reconciliation-gated, and bound to the same deterministic operation identity.
   - `legacy_unknown`: remains `execution_uncertain` and reconciliation-gated.
   - `approved`: verifies a process that already knows it may have crossed dispatch cannot treat a contradictory durable `approved` checkpoint as proof that the action is safe to execute again.

2. Hardened `runtime/execution_safety.py::reload_checkpoint_after_conflict()`.
   - Preserves the useful optimization from the previous run: durable winners with no approval (`none`) or an already-consumed outcome (`resolved`) clear obsolete process-local ambiguity immediately.
   - Keeps `dispatching` and `legacy_unknown` fail-closed through the existing restore guard.
   - Fixes the newly identified edge case for `approved`: a schema-v2 `approved` checkpoint is safe on a clean process restart, but it does not erase direct knowledge in the current process that provider dispatch may already have happened before CAS loss.
   - In this contradictory conflict-reload case StageGuard keeps `execution_uncertain`, preserves the deterministic operation identity, reports bounded execution phase `unknown`, requires reconciliation, and blocks remediation replay.
   - This distinction prevents regressed/non-monotonic/custom phase-capable store views from converting a possibly consumed stale approval back into an executable action.

### Tests / checks / results

- GitHub repository writes succeeded for both the new regression matrix and runtime hardening.
- Attempted credential-free local validation with:
  `python -m unittest tests.test_execution_conflict_reload_phases tests.test_execution_safety`.
- The execution environment failed during `git clone` before Python started because it could not resolve `github.com`; therefore the new tests are **not claimed as executed successfully here**.
- No GitHub Actions workflow was intentionally triggered, rerun, or modified.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Clean restart and conflict reload are different evidence contexts.** Durable `approved` proves the barrier was not crossed only when the process has no stronger local evidence to the contrary.
2. **Direct post-dispatch knowledge wins over a contradictory safe-looking checkpoint.** Once a process knows provider contact may have occurred, `approved` cannot make that same approval executable again without reconciliation.
3. **Only terminal/cleared durable winners erase ambiguity immediately.** `none` and `resolved` are sufficient to show the stale approval is gone or consumed; ambiguous/pending states remain gated.
4. **Expose contradiction as bounded `unknown`.** The operator surface must not falsely claim either `approved` or `dispatching` when durable and process-local evidence disagree.
5. **Never trade replay safety for convenience.** The fallback is an extra reconciliation + fresh Grafana investigation, not a second remediation execution.

### Current blockers / unknowns

- The new phase-matrix tests have not been executed in a full local checkout because the environment cannot currently resolve `github.com`.
- Real GCS generation semantics are covered by the existing credential-free multiprocess fake but still need a live/emulated acceptance environment before claiming provider-backed production validation.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Harden the operator/readiness surface for contradictory multi-instance handoff: add an explicit bounded reconciliation reason (`durable_dispatching`, `legacy_unknown`, `post_dispatch_checkpoint_regression`, `phase_unavailable`) to `/readyz` and operator state without leaking operation/provider identifiers, then add fixed-cardinality metrics and tests proving every execution-uncertain reason blocks readiness and no label can grow with incident/provider data.**

## Previous run — 2026-09-08 — multi-instance reconciliation CAS race

Hardened `runtime/execution_safety.py` so ordinary CAS losers rebase execution state from the authenticated durable winner and added `runtime/tests/test_execution_reconciliation_gcs_multiprocess_cas.py`. Two restored reconcilers race fresh Grafana evidence from durable `dispatching`; exactly one evidence revision wins CAS, the loser adopts it without another provider read/write, and remediation is never replayed.

## Previous run — 2026-09-08 — service-level GCS dispatch CAS race

Added `runtime/tests/test_execution_gcs_multiprocess_cas.py`. Two independently spawned StageGuard services restore the same approved GCS generation and race `execute_approved()`. Exactly one `dispatching` CAS winner can contact remediation; the stale loser remains conflict-blocked even after winner recovery, and provider-call count remains exactly one.

## Previous run — 2026-09-08 — multiprocess GCS generation CAS

Added a credential-free process-safe fake GCS backend and spawned-process generation-CAS acceptance. Two stores racing the same generation yield one winner/one conflict; an original stale loser remains unable to overwrite a later recovered checkpoint, and first-object creation is separately protected by generation 0.

## Previous run — 2026-09-08 — fail-closed HTTPS reconciliation ambiguity

Added concrete TLS/process-death reconciliation coverage for malformed JSON, wrong operation-id echoes, unknown provider state, and timeout. Every ambiguous result preserves `execution_uncertain`, blocks readiness, performs no second remediation POST, and requires later authoritative reconciliation plus fresh Grafana evidence.

## Previous run — 2026-09-08 — concrete HTTPS process-death replay safety

Added a real loopback TLS provider and spawned-process SIGKILL acceptance routed through `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, and `HttpRemediationTransport`. Proved zero POSTs when killed before HTTP dispatch and exactly one POST when killed after provider acceptance, with GET-only reconciliation and fresh Grafana evidence on restart.
