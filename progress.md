# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now includes strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS checkpoints with strict generation CAS, fail-closed conflict recovery, remediation execution reconciliation, Cloud Run/IAP deployment, operator health/readiness/self-observability, a same-origin recovery cockpit, and checkpoint schema v2 with a durable pre-side-effect execution phase.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays an ambiguous side effect.
- Checkpoint schema v2 persists only a bounded execution phase (`none`, `approved`, `dispatching`, `resolved`); provider detail and operation ids remain outside durable checkpoint state.
- A production provider is never contacted until `dispatching` has been durably persisted.
- A v2 `approved` checkpoint proves dispatch has not started and can safely survive restart.
- A restored `dispatching` checkpoint or legacy-v1 pending approval is execution-ambiguous and requires reconciliation plus fresh Grafana evidence.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict generation compare-and-swap.
- `/healthz` proves process liveness only; `/readyz` also requires evidence-plane and lifecycle consistency.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with read-only datasource/Prometheus/Loki evidence tools.
- Deterministic incident investigation with bounded Loki corroboration.
- Strict configurable telemetry mapping, activation preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity and bounded Cloud Logging audit integration.
- Non-root Cloud Run image with embedded official Grafana MCP binary.
- `/healthz`, fail-closed `/readyz`, readiness caching/backoff, and Prometheus self-observability.
- Authenticated operator cockpit, bounded audit timeline, conflict reload, and execution reconciliation UX.
- Signed GCS lifecycle checkpoints with strict generation CAS and fixed-label observability.
- Provider-neutral GET-only reconciliation transport with bounded `accepted` / `not_found` / `unknown` states.
- Explicit production reconciliation endpoint wiring and concrete no-replay lifecycle coverage.
- Checkpoint schema v2 durable remediation execution phase with backward-compatible v1 restore.

## Run log — 2026-09-08 — checkpoint schema v2 durable dispatch barrier

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/incident_checkpoint.py`;
- `runtime/incident_service.py` around checkpoint save/restore and `execute_approved()`;
- `runtime/execution_safety.py`;
- `runtime/remediation.py` approval and deterministic operation-id semantics;
- `runtime/tests/test_incident_checkpoint.py`;
- `runtime/tests/test_execution_safety.py`;
- `runtime/tests/test_gcs_checkpoint.py`;
- `EXECUTION_UNCERTAINTY.md`.

The prior handoff requested a durable authenticated remediation execution-phase marker. The important design constraint was to make the marker useful at the exact side-effect boundary rather than merely adding schema metadata.

### Exact changes made

Updated `runtime/incident_checkpoint.py`:

- introduced `stageguard.incident-checkpoint.v2` as the write schema while retaining v1 reads;
- added bounded execution phases `none`, `approved`, `dispatching`, and `resolved`;
- added strict lifecycle/phase consistency validation;
- ordinary checkpoint serialization derives `none`, `approved`, or `resolved` from approval/outcome state;
- v1 pending approvals restore internally as `legacy_unknown` because old checkpoints cannot prove whether dispatch occurred;
- execution phase is inside the canonical SHA-256/HMAC-authenticated state;
- `JsonCheckpointStore`, `GoogleCloudStorageCheckpointStore`, and `ObservableCheckpointStore` advertise execution-phase support.

Updated `runtime/execution_safety.py`:

- production adapters requiring operation reconciliation now persist an explicit `dispatching` checkpoint before any provider call;
- if that pre-dispatch CAS write fails, provider execution is never attempted and the failure remains an ordinary checkpoint conflict;
- after `dispatching` becomes durable, provider/verification failures become execution uncertainty and never trigger replay;
- a post-provider checkpoint conflict still enters `execution_uncertain` and requires durable-winner reload;
- v2 `approved` checkpoints are now safe to resume after restart because the durable dispatch barrier proves provider contact has not begun;
- restored `dispatching`, legacy-v1 `legacy_unknown`, and phase-unaware custom-store pending approvals remain fail-closed;
- restored ambiguous production state derives the same deterministic operation id server-side and still requires provider reconciliation plus fresh Grafana evidence.

Updated `runtime/tests/test_incident_checkpoint.py`:

- changed version assertion to v2;
- verifies derived `none`, `approved`, and `resolved` phases;
- verifies v1 pending approval migration to `legacy_unknown`;
- verifies execution-phase tampering fails HMAC authenticity even if the attacker recomputes the public SHA-256 digest;
- keeps provider metadata redaction and general tamper coverage.

Added `runtime/tests/test_execution_phase_v2.py`:

- proves `dispatching` is durable before the production remediation fake can be contacted;
- proves v2 `approved` restart remains synchronized and can execute without reconciliation;
- proves restored `dispatching` state enters `execution_uncertain`, blocks execution, reconciles without replay, and requires fresh evidence;
- proves legacy-v1 pending approvals remain fail-closed.

Updated `EXECUTION_UNCERTAINTY.md`:

- documents the v2 state machine and exact pre-side-effect dispatch barrier;
- documents backward-compatible v1 semantics;
- documents why `approved` can now safely survive restart while `dispatching` cannot;
- documents integrity/authenticity and provider-detail exclusion.

### Commits produced this run

- `03b03405` — add checkpoint v2 execution phase
- `06f92dfd` — persist remediation dispatch phase before side effects
- `2544393e` — test checkpoint v2 execution phase
- `fe13bc17` — add durable remediation dispatch-barrier tests
- `59bdfd8b` — fix legacy checkpoint approval fixture
- `441bab9b` — document checkpoint v2 dispatch barrier

### Tests / checks / results

Attempted credential-free local validation with:

```text
python -m unittest tests.test_incident_checkpoint tests.test_execution_phase_v2 tests.test_execution_safety
```

The fresh checkout failed before Python started because the execution container could not resolve `github.com` (`Could not resolve host: github.com`). Therefore the Python suite is **not claimed as executed successfully**.

A static compatibility pass caught and fixed an invalid legacy-test approval fixture (`Approval` contains `production_id`, not `reason`). Existing custom conflict-test stores intentionally do not advertise phase support, so their previous post-provider conflict semantics remain intact while real Json/GCS stores use the new barrier.

No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Persist before side effect, not after it.** `dispatching` must be durable before provider contact or the marker does not close the restart ambiguity window.
2. **Pre-dispatch CAS conflict is not execution uncertainty.** If the barrier cannot be persisted, StageGuard does not contact the provider.
3. **`approved` is now meaningful durable proof.** With v2, a production restart may preserve a genuinely unused approval without weakening replay safety.
4. **Legacy v1 remains conservative.** Pending v1 approvals restore as `legacy_unknown` and still require reconciliation/fresh evidence.
5. **Provider detail stays out of checkpoints.** Only the bounded lifecycle phase is authenticated; provider responses, credentials, endpoint detail, and deterministic operation ids remain server/runtime concerns.
6. **Custom stores remain backward compatible.** Stores that do not opt into phase support retain the previous conservative execution-safety behavior.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve GitHub for checkout.
- Real-GCS two-instance acceptance, Cloud Run/IAP browser acceptance, real provider idempotency lookup, and real Grafana MCP metric+Loki acceptance still require external credentials/resources.
- A crash after `dispatching` but before provider contact intentionally still requires reconciliation; the state machine favors false-positive reconciliation over any possibility of replay.

## Single best next step

**Make the `dispatching` barrier observable without exposing incident/provider identity: add fixed-label checkpoint execution-phase gauges/counters and readiness diagnostics, then add a crash-injection test matrix around every boundary (`approved` save → `dispatching` save → provider call → recovery verification → `resolved` save) to prove which restart states are executable, reconcilable, or conflict-blocked.**

## Previous run — 2026-09-08 — concrete reconciliation lifecycle + restart-safe approval boundary

Added concrete HTTP reconciliation lifecycle coverage and a conservative restart rule for production pending approvals. Checkpoint v2 above now refines that rule: genuinely unused v2 `approved` state can survive restart safely, while `dispatching` and legacy-v1 pending approvals remain execution-ambiguous.
