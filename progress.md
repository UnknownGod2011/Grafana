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
- The operator cockpit treats reconciliation reason as bounded safety guidance only; it never renders provider state, operation identity, endpoints, generations, credentials, or exception detail.

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
- Fixed-cardinality reconciliation-reason model for operator state, readiness, Prometheus telemetry, and same-origin recovery guidance.
- Concrete SIGKILL/HTTPS crash and ambiguity suites now assert the reconciliation-reason contract across restart, unresolved provider responses, authoritative recovery, and final clean restart.

## Run log — 2026-09-08 — concrete HTTPS reconciliation-reason acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/tests/test_http_subprocess_reconciliation_ambiguity.py` for malformed JSON, wrong operation echo, unknown provider state, timeout, later authoritative recovery, provider POST/GET accounting, and readiness behavior;
- `runtime/tests/test_http_subprocess_crash_recovery.py` for the two real SIGKILL boundaries around durable `dispatching` and provider acceptance;
- `runtime/execution_safety.py` for the fixed-cardinality `execution_reconciliation_reason()` contract and restored `dispatching` semantics;
- the current `runtime/tests` tree and latest commit status before writing.

### Exact changes made

1. Strengthened `runtime/tests/test_http_subprocess_reconciliation_ambiguity.py`.
   - A restart from the durable `dispatching` checkpoint must report `durable_dispatching` before reconciliation.
   - Malformed reconciliation JSON, a wrong operation-ID echo, an unknown provider state, and a bounded timeout must all leave the reason at `durable_dispatching` while execution remains uncertain.
   - `/readyz` composition is now required to expose `remediation_reconciliation_reason=durable_dispatching` while remaining not ready.
   - A later authoritative provider read may clear the reason only after the existing reconciliation path gathers fresh Grafana evidence and discards the stale approval.
   - After safe recovery, the live service and a fresh final restart must both report `clear`.
   - Existing invariants remain: exactly one original remediation POST, GET-only reconciliation, and no second POST during ambiguity or recovery.

2. Strengthened `runtime/tests/test_http_subprocess_crash_recovery.py`.
   - Both real process-death boundaries now assert that restart from durable `dispatching` yields `execution_uncertain`, phase `dispatching`, and reason `durable_dispatching`.
   - Successful reconciliation plus fresh evidence must transition the reason to `clear`.
   - A second restart must remain synchronized with `clear` and no executable stale approval.
   - Provider-call accounting remains unchanged: zero POSTs if killed before provider contact, exactly one POST if killed after provider acceptance, and one bodyless reconciliation GET in either case.

### Tests / checks / results

- GitHub repository reads and writes succeeded.
- Source commits created in this run:
  - `862a350abd660062a83b555b39c771e974fa303c` — HTTPS ambiguity reason assertions.
  - `1b50681f939bd9071e0eece2f9214f5620f6e8a8` — SIGKILL crash-recovery reason assertions.
- GitHub combined status for `1b50681f939bd9071e0eece2f9214f5620f6e8a8` reports zero status contexts; no GitHub Actions workflow was intentionally triggered or rerun.
- The updated tests are **not claimed as executed successfully in a full local checkout in this environment**.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **`durable_dispatching` survives provider ambiguity.** Malformed/timeout/unknown reconciliation results cannot downgrade or erase the bounded reason because the durable barrier still proves the provider may already have been contacted.
2. **`clear` is a post-recovery state, not merely a successful GET state.** The tests require the service to complete the existing fresh-evidence recovery path before the reason clears.
3. **Reason observability is now bound to real failure boundaries.** The contract is exercised through spawned processes, SIGKILL, the concrete HTTPS transport, durable JSON checkpoints, and readiness composition rather than only stubs.
4. **No-replay remains authoritative.** Adding observability assertions does not add retries or alternate remediation paths; provider POST counts remain the primary safety invariant.

### Current blockers / unknowns

- These updated acceptance tests still need execution in a complete local/CI environment with POSIX `SIGKILL` and `openssl` before a green result can be claimed.
- Real GCS generation behavior is covered by the credential-free multiprocess fake but still needs a live/emulated acceptance environment before provider-backed production validation can be claimed.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Add an operator-visible, append-only reconciliation audit event with a bounded result/reason schema for each reconciliation attempt (`accepted`, `not_found`, `unknown`) and recovery completion, while explicitly excluding provider payloads, operation IDs, endpoints, credentials, and raw exceptions. Then test that crash/ambiguity paths produce an auditable sequence without increasing metric cardinality or enabling remediation replay.**

## Previous run — 2026-09-08 — operator reconciliation guidance and transition contract

Wired the five-value bounded reconciliation reason into the same-origin cockpit and bound reason assertions to real conflict-reload transitions across durable `none`, `approved`, `dispatching`, `resolved`, and legacy winners.

## Previous run — 2026-09-08 — bounded reconciliation-reason observability

Added the five-value provider-detail-free reconciliation reason to execution safety, `/v1/incident`, `/readyz`, and one-hot Prometheus metrics, with fail-closed fallback to `phase_unavailable`.

## Previous run — 2026-09-08 — conflict reload execution-phase matrix

Added `runtime/tests/test_execution_conflict_reload_phases.py` and hardened conflict reload semantics so safe durable winners clear obsolete ambiguity while `dispatching`, legacy ambiguity, and contradictory post-dispatch `approved` states remain reconciliation-gated.

## Previous run — 2026-09-08 — multi-instance reconciliation CAS race

Hardened conflict rebasing and added a spawned-process reconciliation race from durable `dispatching`; exactly one fresh Grafana evidence revision becomes durable and the stale reconciler adopts that winner without remediation replay.

## Previous run — 2026-09-08 — service-level GCS dispatch CAS race

Two independently spawned StageGuard services restore the same approved GCS generation and race `execute_approved()`. Exactly one `dispatching` CAS winner can contact remediation; the stale loser remains conflict-blocked and provider-call count remains exactly one.

## Previous run — 2026-09-08 — concrete HTTPS replay safety

Added real loopback TLS/process-death acceptance for execution and GET-only reconciliation, including malformed, wrong-operation, unknown-state, and timeout outcomes. Ambiguity never causes a second remediation POST and later authoritative recovery requires fresh Grafana evidence.
