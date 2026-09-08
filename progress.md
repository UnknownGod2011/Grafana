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
- After CAS contention, process-local execution uncertainty is always rebased from the authenticated durable winner; a stale loser cannot force redundant reconciliation after another instance has already cleared the stale approval with fresh evidence.

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

## Run log — 2026-09-08 — multi-instance reconciliation CAS race

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/tests/test_execution_gcs_multiprocess_cas.py` for the existing service-level dispatch CAS harness;
- `runtime/tests/test_gcs_multiprocess_cas.py` for the process-safe generation-aware fake GCS backend;
- `runtime/execution_safety.py` for restart ambiguity, provider reconciliation, conflict reload, and fresh-investigation behavior;
- `runtime/incident_service.py` for checkpoint CAS behavior during `investigate()` and explicit conflict reload;
- `runtime/investigator.py` for the fixed six-query Grafana/Prometheus evidence contract and deterministic revision construction.

### Exact changes made

1. Hardened `runtime/execution_safety.py` conflict reload semantics.
   - Added `_clear_execution_uncertainty()` so ambiguity state is reset consistently.
   - Changed `reload_checkpoint_after_conflict()` to rebase execution-safety state from the authenticated durable checkpoint winner rather than blindly retaining the losing process's old `execution_uncertain` flag.
   - If another instance already reconciled successfully and persisted fresh evidence with no stale approval, the loser now becomes synchronized/clear immediately after explicit reload.
   - If the durable winner is still `dispatching` or legacy ambiguous, the ordinary restored-production guard re-enters fail-closed uncertainty with the correct deterministic operation identity.
   - A durable schema-v2 `approved` winner remains safe because it proves the dispatch barrier was not crossed.
   - Reused the new reset helper after successful `reconcile_execution_uncertainty()` to keep state transitions consistent.

2. Added `runtime/tests/test_execution_reconciliation_gcs_multiprocess_cas.py`.
   - Seeds a real authenticated schema-v2 `dispatching` checkpoint through `GoogleCloudStorageCheckpointStore` using the credential-free process-safe fake GCS backend.
   - Spawns two independent StageGuard services restored from the same generation and confirms both begin `execution_uncertain` / `dispatching` / reconciliation-ready.
   - Both receive an authoritative `accepted` provider reconciliation result and synchronize at a process barrier before collecting fresh Grafana evidence.
   - Each process receives a slightly different but healthy six-query evidence set so the generated revisions are distinct; therefore the durable winner is observable rather than accidentally identical.
   - Requires exactly one fresh-evidence checkpoint write to win GCS generation CAS and exactly one reconciler to receive `CheckpointConflictError`.
   - Requires zero remediation execution calls throughout reconciliation; only two provider reconciliation reads are allowed.
   - Holds the losing reconciler until the winning evidence revision is durable, then explicitly reloads the winner and verifies its stale process-local uncertainty clears without another provider reconciliation or another checkpoint write.
   - Verifies a clean third StageGuard instance restores exactly the winning revision, with no approval, phase `none`, synchronized checkpoint state, and no reconciliation requirement.

### Tests / checks / results

- GitHub repository writes succeeded.
- Attempted a credential-free local checkout and targeted unittest run:
  `python -m unittest tests.test_execution_reconciliation_gcs_multiprocess_cas tests.test_execution_gcs_multiprocess_cas`.
- The environment again failed before Python started because Git could not resolve `github.com`; therefore the new tests are **not claimed as executed successfully here**.
- No GitHub Actions workflow was intentionally triggered, rerun, or modified.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Rebase safety state from durable truth after conflict.** A process-local ambiguity flag is not authoritative once another instance has won CAS; the authenticated checkpoint is.
2. **Do not perform redundant reconciliation after adopting a cleared winner.** If the winner has already persisted fresh evidence and removed the stale approval, another provider lookup and evidence write adds contention without improving safety.
3. **Keep dispatching fail-closed.** Reload only clears stale ambiguity when the durable winner itself proves the ambiguous operation is no longer pending; `dispatching` and legacy-unknown remain reconciliation-gated.
4. **Use distinct evidence revisions in the race.** This proves exactly which instance won durable recovery instead of allowing identical deterministic reports to hide a write race.
5. **Keep reconciliation read-only.** The acceptance harness treats any remediation execution call during reconciliation as a test failure.

### Current blockers / unknowns

- The new multiprocess reconciliation acceptance test has not been executed in a full local checkout because the environment cannot currently resolve `github.com`.
- The process-safe GCS backend models generation preconditions but is not a substitute for a real GCS emulator/live two-instance Cloud Run acceptance run.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Add a service-level regression matrix for conflict reload rebasing across every durable execution phase (`none`, `approved`, `dispatching`, `resolved`, `legacy_unknown`): prove safe winners clear stale process-local ambiguity, ambiguous winners remain reconciliation-gated with the winner's deterministic operation identity, and no reload path can make an already-consumed or stale approval executable. Then use those invariants to harden readiness/operator-state reporting for multi-instance handoff.**

## Previous run — 2026-09-08 — service-level GCS dispatch CAS race

Added `runtime/tests/test_execution_gcs_multiprocess_cas.py`. Two independently spawned StageGuard services restore the same approved GCS generation and race `execute_approved()`. Exactly one `dispatching` CAS winner can contact remediation; the stale loser remains conflict-blocked even after winner recovery, and provider-call count remains exactly one.

## Previous run — 2026-09-08 — multiprocess GCS generation CAS

Added a credential-free process-safe fake GCS backend and spawned-process generation-CAS acceptance. Two stores racing the same generation yield one winner/one conflict; an original stale loser remains unable to overwrite a later recovered checkpoint, and first-object creation is separately protected by generation 0.

## Previous run — 2026-09-08 — fail-closed HTTPS reconciliation ambiguity

Added concrete TLS/process-death reconciliation coverage for malformed JSON, wrong operation-id echoes, unknown provider state, and timeout. Every ambiguous result preserves `execution_uncertain`, blocks readiness, performs no second remediation POST, and requires later authoritative reconciliation plus fresh Grafana evidence.

## Previous run — 2026-09-08 — concrete HTTPS process-death replay safety

Added a real loopback TLS provider and spawned-process SIGKILL acceptance routed through `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, and `HttpRemediationTransport`. Proved zero POSTs when killed before HTTP dispatch and exactly one POST when killed after provider acceptance, with GET-only reconciliation and fresh Grafana evidence on restart.
