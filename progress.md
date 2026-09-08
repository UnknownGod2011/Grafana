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

## Run log — 2026-09-08 — fail-closed HTTPS reconciliation ambiguity

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/tests/test_http_subprocess_crash_recovery.py` for the existing real-TLS/SIGKILL restart harness;
- `runtime/http_remediation_transport.py` for strict GET reconciliation parsing and timeout behavior;
- `runtime/execution_safety.py` for `execution_uncertain` recovery semantics;
- `runtime/production_remediation.py` for bounded provider reconciliation and timeout configuration;
- `runtime/api.py` and `runtime/readiness.py` for fail-closed readiness composition.

### Exact changes made

1. Added `runtime/tests/test_http_subprocess_reconciliation_ambiguity.py`.
   - Reuses the real spawned-process hard-crash path after the HTTPS provider has accepted exactly one remediation POST.
   - Uses a switchable local TLS reconciliation provider that can return malformed JSON, a wrong operation-id echo, an unknown `pending` state, or a response delayed beyond the configured transport timeout.
   - Each ambiguity case asserts `reconcile_execution_uncertainty()` raises rather than clearing state.
   - Each case asserts checkpoint state remains `execution_uncertain` and execution phase remains durable `dispatching`.
   - Each case injects an otherwise healthy evidence readiness probe and proves StageGuard readiness still reports `ready=false` specifically because lifecycle execution is uncertain.
   - Each case proves the remediation POST count remains exactly one and the ambiguity path performs only GET reconciliation.
   - After switching the provider back to an authoritative `accepted` response, each case proves reconciliation can recover safely, fresh Grafana investigation clears the stale approval, phase returns to `none`, and no second POST is emitted.
   - A final restart verifies the recovered checkpoint has no executable stale approval.

2. Kept production behavior unchanged.
   - No TLS weakening, provider-detail persistence, retry expansion, or new remediation execution path was introduced.
   - The change is test-only and exercises the existing strict reconciliation contract through real HTTPS sockets and process death.

### Tests / checks / results

Attempted a fresh credential-free checkout and targeted test run without invoking GitHub Actions:

```text
python -m unittest \
  tests.test_http_subprocess_reconciliation_ambiguity \
  tests.test_http_subprocess_crash_recovery \
  tests.test_http_remediation_transport -v
```

The container failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new acceptance tests are **not claimed as executed successfully** in this environment. The repository write itself succeeded through the GitHub connector. No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Test ambiguity only after a provider-accepted POST.** This targets the highest-risk case: a real external side effect exists while StageGuard has only durable `dispatching`.
2. **Keep ambiguity recovery read-only.** Malformed/timeout/wrong provider answers never trigger remediation and cannot relax readiness.
3. **Prove readiness fail-closed independently from Grafana availability.** The test injects an otherwise healthy evidence probe so `ready=false` is attributable to `execution_uncertain`, not an unrelated MCP failure.
4. **Allow recovery only after a later authoritative lookup.** Once the provider returns a valid accepted state, StageGuard still gathers fresh Grafana evidence and discards the old approval before normal operation resumes.

### Current blockers / unknowns

- Local deterministic Python execution remains blocked because the execution container cannot resolve `github.com` for checkout.
- The hard-crash/TLS acceptance tests depend on POSIX `SIGKILL` and a local `openssl` executable; they skip rather than emulate those guarantees when unavailable.
- Real GCS two-instance acceptance, Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, and a real provider idempotency endpoint still require external credentials/resources.

## Single best next step

**Add a credential-free multi-process CAS acceptance harness around `GcsCheckpointStore` semantics using a local fake generation-aware object backend: race two StageGuard instances on approval/dispatch/recovery, prove exactly one generation winner at each mutation, prove the loser becomes conflict-blocked before provider contact where appropriate, and verify no stale instance can overwrite a recovered incident.**

## Previous run — 2026-09-08 — concrete HTTPS process-death replay safety

Added a real loopback TLS provider and spawned-process SIGKILL acceptance routed through `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, and `HttpRemediationTransport`. Proved zero POSTs when killed before HTTP dispatch and exactly one POST when killed after provider acceptance, with GET-only reconciliation and fresh Grafana evidence on restart.

## Previous run — 2026-09-08 — real process-death replay-safety acceptance

Added `runtime/tests/test_subprocess_crash_recovery.py` using a spawned interpreter, real `JsonCheckpointStore`, fsynced modeled provider state, and POSIX SIGKILL after durable `dispatching` and after modeled provider acceptance. Restart required reconciliation plus fresh Grafana evidence and never replayed remediation.

## Previous run — 2026-09-08 — remediation crash-boundary fault matrix

Added the in-process five-boundary crash matrix covering approval persistence, `dispatching` persistence, provider failure, Grafana recovery-verification failure, and resolved checkpoint CAS failure with explicit provider-call counts and readiness assertions.
