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
- Crash-boundary fault-injection regression matrix covering pre-approval persistence, dispatch barrier persistence, provider execution, Grafana recovery verification, and resolved checkpoint persistence.

## Run log — 2026-09-08 — remediation crash-boundary fault matrix

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py` for dispatch-barrier and reconciliation semantics;
- `runtime/incident_checkpoint.py` for phase-capable store behavior;
- `runtime/incident_service.py` for approval, provider execution, recovery verification, audit/checkpoint save ordering;
- `runtime/remediation.py` for deterministic idempotent execution and Grafana recovery sampling;
- `runtime/api.py` for readiness behavior;
- `runtime/tests/test_execution_phase_v2.py` for existing v2 coverage.

### Exact changes made

Added `runtime/tests/test_execution_crash_matrix.py` with a deterministic phase-capable checkpoint store, faulting provider, bounded metric sequence, and readiness stub.

The matrix now proves:

1. **Approval checkpoint save failure**
   - provider calls: 0;
   - durable phase remains `none`;
   - current process becomes `conflicted` and not ready;
   - restart is synchronized with no approval, so new human approval is required.

2. **`dispatching` barrier save failure**
   - provider calls: 0;
   - durable phase remains `approved`;
   - current process becomes `conflicted` and not ready;
   - restart safely restores the unused approval with no reconciliation requirement.

3. **Provider failure after durable barrier**
   - provider call count is exactly 1;
   - durable phase remains `dispatching`;
   - lifecycle becomes `execution_uncertain` and not ready;
   - restart cannot replay remediation; provider reconciliation plus fresh Grafana investigation clears the stale approval and requires a new human approval.

4. **Grafana recovery-verification failure after provider acceptance**
   - provider call count remains exactly 1;
   - durable phase remains `dispatching`;
   - restart is reconciliation-only and never invokes remediation again;
   - successful reconciliation still requires fresh Grafana evidence before normal lifecycle operation resumes.

5. **Resolved checkpoint CAS failure after verified recovery**
   - provider call count remains exactly 1;
   - durable winner remains `dispatching` even though process-local outcome was resolved;
   - current process reports `reload_required` execution uncertainty;
   - restart adopts the durable `dispatching` winner, reconciles without replay, gathers fresh evidence, removes the stale approval, and returns to ready state.

The tests use the real `_service_readiness()` composition with an evidence-plane-ready stub, so checkpoint conflict and execution uncertainty are asserted as readiness failures rather than inferred indirectly.

### Tests / checks / results

Attempted credential-free validation with a fresh clone and targeted unittest command. The container failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new test module and existing targeted suite are **not claimed as executed successfully** in this environment. No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were used.

### Decisions made

1. **Test the exact side-effect boundaries before adding more runtime complexity.** The production code already contains the correct v2 barrier; the highest-value increment was proving its crash semantics end to end.
2. **Assert provider-call counts explicitly.** Every post-barrier recovery path must demonstrate zero replay after restart.
3. **Use real readiness composition.** A lifecycle safety state is only production-useful if `/readyz` also fails closed.
4. **Preserve genuinely unused approvals.** A failed `dispatching` save proves provider contact did not happen, so a durable v2 `approved` checkpoint may safely survive restart.
5. **Discard stale approvals after ambiguity.** Even `not_found` reconciliation is followed by fresh Grafana investigation and a new approval requirement; reconciliation never revives or replays the old approval.

### Current blockers / unknowns

- Local deterministic Python execution remains blocked because the container cannot resolve `github.com` for checkout.
- Real GCS two-instance acceptance, Cloud Run/IAP browser acceptance, real provider idempotency lookup, and live Grafana MCP metric/Loki acceptance require external credentials/resources.
- The crash matrix models process failure at deterministic exception/CAS boundaries; it does not yet exercise an actual subprocess SIGKILL against a local durable JSON store.

## Single best next step

**Add a credential-free subprocess crash/restart acceptance harness using `JsonCheckpointStore` and a local fake idempotent remediation HTTP server. Kill the StageGuard process immediately after the durable `dispatching` checkpoint and immediately after provider acceptance, then restart from disk and prove there is no second remediation POST, reconciliation is required, fresh Grafana evidence is collected, and a new human approval is required before any later action.**

## Previous run — 2026-09-08 — execution-phase observability

Added the bounded execution-phase API/readiness/Prometheus view and restored conservative ambiguity semantics for phase-unaware custom checkpoint stores.
