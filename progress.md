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
- Crash-boundary fault-injection regression matrix for approval persistence, dispatch barrier persistence, provider execution, Grafana recovery verification, and resolved checkpoint persistence.
- Real spawned-process SIGKILL acceptance coverage using `JsonCheckpointStore` across the two most dangerous remediation boundaries.

## Run log — 2026-09-08 — real process-death replay-safety acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py` for durable `dispatching`, restore, and reconciliation semantics;
- `runtime/incident_checkpoint.py` for `JsonCheckpointStore` durability and execution-phase restoration;
- `runtime/tests/test_execution_crash_matrix.py` for the existing in-process fault matrix;
- `runtime/remediation.py` for deterministic operation identity and post-action Grafana verification;
- `runtime/http_remediation_transport.py` to confirm that production reconciliation remains GET-only and execution remains separated from lookup.

### Exact changes made

Added `runtime/tests/test_subprocess_crash_recovery.py`.

The new acceptance harness uses `multiprocessing` with the `spawn` start method so recovery is exercised in a fresh Python interpreter rather than by reusing process memory. It uses the real atomic `JsonCheckpointStore` on disk and validates two hard-crash boundaries with POSIX `SIGKILL`:

1. **After durable `dispatching`, before modeled provider acceptance**
   - the child verifies the on-disk checkpoint is already `dispatching`;
   - it is then SIGKILLed before recording a provider acceptance;
   - durable provider-call count remains 0;
   - restart restores `execution_uncertain` / `dispatching`;
   - provider reconciliation returns `not_found`;
   - StageGuard gathers fresh Grafana evidence, clears the stale approval, and performs no remediation execution.

2. **Immediately after modeled provider acceptance**
   - the child verifies durable `dispatching` first;
   - it durably records the deterministic operation id in a provider-call log, fsyncs that record, and is SIGKILLed before control can return to StageGuard;
   - durable provider-call count is exactly 1;
   - restart restores `execution_uncertain` / `dispatching`;
   - provider reconciliation returns `accepted`;
   - StageGuard gathers fresh Grafana evidence and performs zero replay calls;
   - a second restart remains synchronized with no approval, proving the stale approval cannot become executable again accidentally.

The test class is skipped on platforms without `SIGKILL` because the acceptance property intentionally depends on abrupt POSIX process-death semantics. Unexpected child paths use distinct non-SIGKILL exit codes so the parent can detect that the intended crash boundary was not reached.

### Tests / checks / results

Attempted a fresh credential-free clone and targeted execution:

```text
python -m unittest tests.test_subprocess_crash_recovery tests.test_execution_crash_matrix -v
```

The container again failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new acceptance harness and existing targeted suite are **not claimed as executed successfully** in this environment. No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were used.

### Decisions made

1. **Use a spawned interpreter instead of another exception-only test.** The safety claim now crosses a real process boundary and reloads only from disk.
2. **Use SIGKILL rather than `os._exit` for the acceptance boundary.** This better models abrupt worker/container loss where cleanup and normal exception unwinding cannot run.
3. **Persist the modeled provider acceptance separately and fsync it before the kill.** This makes the post-provider case explicit: the external side effect is durably known to have happened while StageGuard still has only `dispatching` locally.
4. **Keep recovery adapter execution-fatal.** Any accidental remediation call after restart raises immediately, making replay detectable instead of merely counting it.
5. **Require fresh Grafana investigation after reconciliation.** Provider state resolves ambiguity only; it never revives the stale approval or marks the incident recovered by itself.

### Current blockers / unknowns

- Local deterministic Python execution remains blocked because the container cannot resolve `github.com` for checkout.
- Real GCS two-instance acceptance, Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, and a real provider idempotency endpoint still require external credentials/resources.
- The subprocess harness models the remediation provider with an fsynced local call ledger rather than a network server. The production HTTP transport itself is separately covered by GET-only reconciliation and execution-transport tests.

## Single best next step

**Add a local credential-free HTTPS test server (ephemeral self-signed test certificate or injectable opener/SSL context) around `HttpRemediationTransport`, then run the same spawned-process crash acceptance through the concrete production transport. Prove one POST maximum across process death, GET-only reconciliation after restart, operation-id continuity, malformed/timeout fail-closed behavior, and fresh Grafana evidence before a new approval can exist.**

## Previous run — 2026-09-08 — remediation crash-boundary fault matrix

Added the in-process five-boundary crash matrix covering approval persistence, `dispatching` persistence, provider failure, Grafana recovery-verification failure, and resolved checkpoint CAS failure with explicit provider-call counts and readiness assertions.

## Previous run — 2026-09-08 — execution-phase observability

Added bounded execution-phase API/readiness/Prometheus observability and conservative fail-closed behavior for phase-unaware custom checkpoint stores.
