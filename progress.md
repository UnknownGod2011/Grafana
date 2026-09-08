# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, and checkpoint schema v2 with a durable pre-side-effect remediation phase.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; a clean restart from durable `approved` proves dispatch had not begun in that process lifetime.
- Restored `dispatching` and legacy-v1 pending approvals fail closed and require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use strict generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution-phase and reconciliation-reason telemetry are fixed-cardinality and provider-detail-free.
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
- Real spawned-process SIGKILL acceptance using `JsonCheckpointStore` across the two most dangerous remediation boundaries.
- Real loopback TLS coverage for `HttpRemediationTransport` execution and GET-only reconciliation.
- Concrete HTTPS restart coverage for malformed, wrong-operation, unknown-state, and timeout reconciliation outcomes, including later authoritative recovery.
- Credential-free spawned-process GCS generation-CAS acceptance with a process-safe fake object backend.
- End-to-end spawned-process `ExecutionSafeIncidentService` dispatch and reconciliation races over generation-aware GCS semantics.
- Service-level conflict-reload phase matrix for `none`, `approved`, `dispatching`, `resolved`, and `legacy_unknown`, including fail-closed contradictory `approved` handling.
- Fixed-cardinality reconciliation-reason model for operator state, readiness, and Prometheus telemetry.

## Run log — 2026-09-08 — bounded reconciliation-reason observability

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py` for restored ambiguity, post-dispatch exceptions, conflict reload, and reconciliation state;
- `runtime/api.py` for `/v1/incident`, `/readyz`, `/metrics`, bounded execution-phase handling, and fallback behavior;
- `runtime/operator_console.py` for the existing same-origin fail-closed recovery surface;
- `runtime/tests/test_checkpoint_observability.py` and `runtime/tests/test_api.py` for current low-cardinality and HTTP contracts;
- the repository root/runtime trees to confirm the change belongs in the existing safety/observability layer rather than a new subsystem.

### Exact changes made

1. Hardened `runtime/execution_safety.py` with an explicit bounded reconciliation reason.
   - Added only five values: `clear`, `durable_dispatching`, `legacy_unknown`, `post_dispatch_checkpoint_regression`, and `phase_unavailable`.
   - Restored schema-v2 `dispatching` maps to `durable_dispatching`.
   - Legacy-v1 ambiguous approval maps to `legacy_unknown`.
   - Stores that cannot prove an execution phase, plus post-provider failures without a durable phase barrier, map to `phase_unavailable`.
   - A contradictory conflict reload where this process may have dispatched but the durable winner reports `approved` maps to `post_dispatch_checkpoint_regression`.
   - Clearing execution uncertainty also clears the reason back to `clear`.
   - The public getter validates the enum and fails closed to `phase_unavailable`; it never returns incident IDs, operation IDs, endpoints, targets, actors, generations, provider states, or exception text.

2. Extended `runtime/api.py` operator/readiness observability.
   - `/v1/incident` and conflict/reconciliation lifecycle responses now include `execution_reconciliation_reason`.
   - `/readyz` includes `checks.remediation_reconciliation_reason` and remains non-ready for every `execution_uncertain` state.
   - `/metrics` exports one-hot `stageguard_remediation_reconciliation_reason{reason="..."}` across the fixed five-value enum.
   - Unexpected/throwing service values collapse to `phase_unavailable` rather than becoming a new label.
   - The fail-closed `/readyz` exception response also reports only `phase_unavailable`.
   - Bumped the HTTP server identifier from StageGuard/0.11 to StageGuard/0.12 for the operator-contract change.

3. Added `runtime/tests/test_execution_reconciliation_observability.py`.
   - Proves every non-clear bounded reason blocks readiness when execution is uncertain.
   - Proves the reconciliation-reason metric has exactly the fixed label set and exactly one active sample.
   - Proves incident IDs, operation-like IDs, provider URLs, and production IDs do not appear in the metric surface.
   - Proves arbitrary or exception-producing reason values collapse to `phase_unavailable`.
   - Proves lifecycle/operator state includes the bounded reason.
   - Proves the `ExecutionSafeIncidentService` getter itself refuses an unexpected internal reason.

### Tests / checks / results

- GitHub repository inspection and blob writes succeeded.
- Attempted a credential-free local checkout to run the targeted tests, but `git clone` failed before Python started with `Could not resolve host: github.com`.
- Therefore `python -m unittest tests.test_execution_reconciliation_observability tests.test_execution_conflict_reload_phases tests.test_execution_safety` is **not claimed as executed successfully in this environment**.
- No GitHub Actions workflow was intentionally triggered or rerun; the changes are grouped into one Git commit/ref update to minimize CI noise.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Reason is operational classification, not provider state.** Provider reconciliation still has only `accepted` / `not_found` / `unknown`; the new reason explains why StageGuard entered its fail-closed gate.
2. **No dynamic fallback labels.** Unknown values always become `phase_unavailable`.
3. **Contradictory multi-instance handoff is explicit.** `post_dispatch_checkpoint_regression` distinguishes a safety-significant regression from ordinary durable `dispatching` without exposing the operation identity.
4. **Readiness remains tied to the safety state, not the reason string.** Every execution-uncertain reason blocks readiness, so adding diagnosis cannot weaken the gate.
5. **Operator lifecycle JSON is the authoritative UI contract.** The same-origin cockpit can render reason-specific guidance without needing any sensitive provider details.

### Current blockers / unknowns

- The new observability tests have not executed in a full local checkout because this environment still cannot resolve `github.com` from the container runtime.
- Real GCS generation behavior is covered by the credential-free multiprocess fake but still needs a live/emulated acceptance environment before provider-backed production validation can be claimed.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Wire `execution_reconciliation_reason` into the same-origin operator cockpit with reason-specific, non-sensitive recovery guidance and add browser-asset tests for all four uncertain reasons. Then add reason-transition assertions to the existing conflict-reload/crash matrices so the UI/telemetry contract is proven against real `ExecutionSafeIncidentService` transitions rather than only an observability stub.**

## Previous run — 2026-09-08 — conflict reload execution-phase matrix

Added `runtime/tests/test_execution_conflict_reload_phases.py` and hardened conflict reload semantics so safe durable winners clear obsolete ambiguity while `dispatching`, legacy ambiguity, and contradictory post-dispatch `approved` states remain reconciliation-gated.

## Previous run — 2026-09-08 — multi-instance reconciliation CAS race

Hardened conflict rebasing and added a spawned-process reconciliation race from durable `dispatching`; exactly one fresh Grafana evidence revision becomes durable and the stale reconciler adopts that winner without remediation replay.

## Previous run — 2026-09-08 — service-level GCS dispatch CAS race

Two independently spawned StageGuard services restore the same approved GCS generation and race `execute_approved()`. Exactly one `dispatching` CAS winner can contact remediation; the stale loser remains conflict-blocked and provider-call count remains exactly one.

## Previous run — 2026-09-08 — concrete HTTPS replay safety

Added real loopback TLS/process-death acceptance for execution and GET-only reconciliation, including malformed, wrong-operation, unknown-state, and timeout outcomes. Ambiguity never causes a second remediation POST and later authoritative recovery requires fresh Grafana evidence.
