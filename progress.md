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

## Run log — 2026-09-08 — operator reconciliation guidance and transition contract

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/operator_console.py` for the same-origin lifecycle recovery UI, action gating, CSP-safe DOM rendering, and reconciliation workflow;
- `runtime/tests/test_operator_console.py` for current browser-asset and credential-leakage guarantees;
- `runtime/tests/test_execution_conflict_reload_phases.py` for real execution-state transitions across durable `none`, `approved`, `dispatching`, `resolved`, and legacy winners;
- current repository/runtime/test trees and the latest commit sequence before writing.

### Exact changes made

1. Wired `execution_reconciliation_reason` into the same-origin operator cockpit.
   - Added a dedicated lifecycle recovery reason panel rendered only while execution is uncertain.
   - The client accepts exactly the fixed reason set: `clear`, `durable_dispatching`, `legacy_unknown`, `post_dispatch_checkpoint_regression`, `phase_unavailable`.
   - Any unexpected value fails closed to `phase_unavailable`.
   - `/v1/incident`, checkpoint reload, and execution reconciliation responses now feed the bounded reason into the UI.
   - Guidance is distinct by failure mode and explicitly tells the operator when to reload durable state, reconcile through the idempotency status path, and require fresh Grafana evidence.
   - `durable_dispatching` guidance explicitly forbids a second remediation execution.
   - No operation ID, provider endpoint/state, checkpoint generation, credential, actor identity, or exception text is rendered or accepted.

2. Extended `runtime/tests/test_operator_console.py`.
   - Proves the new recovery-reason panel exists.
   - Proves all four uncertain reason values are embedded as a fixed allowlist.
   - Proves server `execution_reconciliation_reason` drives the client.
   - Proves guidance includes fresh Grafana evidence and explicit no-replay wording.
   - Retains assertions that `operation_id`, provider URLs, browser persistence, external URLs, and embedded credentials are absent.

3. Strengthened `runtime/tests/test_execution_conflict_reload_phases.py` so reason telemetry is tied to real service transitions.
   - A post-provider resolved-save conflict backed by durable `dispatching` must report `durable_dispatching`.
   - Durable `none` and `resolved` winners must clear the reason to `clear`.
   - Durable `dispatching` must remain `durable_dispatching`.
   - Legacy ambiguity must report `legacy_unknown`.
   - A contradictory durable `approved` winner after this process may have dispatched must report `post_dispatch_checkpoint_regression`.
   - Existing no-replay/provider-call-count assertions remain intact.

### Tests / checks / results

- GitHub repository reads and writes succeeded.
- Latest source commit before this progress update: `ed8db574d8c083ff8cf941fa97e8d43686f511eb`.
- GitHub combined commit status currently reports no status checks for that commit; no GitHub Actions workflow was intentionally triggered or rerun.
- Attempted a credential-free local checkout for direct Python execution, but the container still fails before Python starts with `Could not resolve host: github.com`.
- Therefore the targeted suite is **not claimed as executed successfully in this environment**.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **The browser consumes the bounded reason, never provider detail.** Recovery guidance is derived entirely from the five-value server contract.
2. **Unknown client values fail closed.** A future or malformed reason becomes `phase_unavailable`; it cannot create a permissive UI branch.
3. **Reason guidance cannot enable remediation.** Existing lifecycle blocking still controls investigation, briefing, approval, and execution; reason text is explanatory only.
4. **Real transition tests are authoritative.** The conflict-reload matrix now verifies the reason associated with actual `ExecutionSafeIncidentService` state rather than relying only on an observability stub.

### Current blockers / unknowns

- The updated operator and conflict-transition tests have not executed in a full local checkout because this environment still cannot resolve `github.com` from the container runtime.
- Real GCS generation behavior is covered by the credential-free multiprocess fake but still needs a live/emulated acceptance environment before provider-backed production validation can be claimed.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Add reconciliation-reason assertions to the concrete process-death / HTTPS ambiguity suites, especially malformed JSON, wrong-operation echo, unknown provider state, timeout, and later authoritative recovery. Prove those paths remain `durable_dispatching` while uncertainty persists, transition to `clear` only after authoritative reconciliation plus fresh Grafana evidence, and never issue a second remediation POST.**

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
