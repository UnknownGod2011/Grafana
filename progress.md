# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, bounded append-only reconciliation audit events, a deterministic tamper-evident audit hash chain, and backward-compatible checkpoint schema v3 audit-chain binding now wired into ordinary lifecycle, pre-dispatch, and reconciliation checkpoint writes when a durable audit reader is available.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored `dispatching` and legacy ambiguous approvals require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution phase and reconciliation reason telemetry are fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions; provider payloads, operation IDs, endpoints, credentials, generations, and raw exceptions are excluded.
- Reconciliation audit persistence must never regress the durable `dispatching` barrier back to `approved`.
- Audit-chain state uses domain-separated SHA-256, strict contiguous sequence numbers, and never advances its trusted head when the underlying audit append fails.
- Schema v3 is emitted only when a real durable-audit chain head is available; non-durable/in-memory callers remain on v2 rather than receiving a fake integrity proof.
- In the execution-safe runtime, an audit-integrity failure maps to fail-closed checkpoint readiness and lifecycle mutation is blocked before dispatch/reconciliation work.

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
- Crash-boundary and real SIGKILL acceptance across dispatch/provider boundaries.
- Real loopback TLS coverage for `HttpRemediationTransport` execution and GET-only reconciliation.
- Concrete HTTPS restart coverage for malformed, wrong-operation, unknown-state, and timeout reconciliation outcomes, including later authoritative recovery.
- Credential-free spawned-process GCS generation-CAS acceptance and service-level multi-instance dispatch/reconciliation races.
- Fixed-cardinality reconciliation-reason model in operator state, readiness, Prometheus telemetry, cockpit guidance, conflict matrices, and concrete crash/HTTPS tests.
- Append-only bounded reconciliation-attempt and recovery audit events integrated into the governed audit stream.
- Real TLS/SIGKILL acceptance checks reconciliation audit ordering and checkpoint sequence monotonicity across ambiguous reads, authoritative recovery, and restart.
- Credential-free tamper-evident audit-chain primitive with restart continuation and mutation/deletion/reordering detection tests.
- Backward-compatible checkpoint schema v3 representation for authenticated audit-chain sequence/head binding.
- Runtime lifecycle checkpoint binding for durable JSONL/explicit audit readers, including execution-safe `dispatching` and reconciliation checkpoints.
- Credential-free runtime regression coverage for v3 restart verification, durable audit mutation fail-closed behavior, and dispatch-barrier chain-head preservation.

## Run log — 2026-09-08 — runtime audit-chain binding

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected `runtime/audit_integrity.py`, `runtime/incident_service.py`, `runtime/execution_safety.py`, `runtime/incident_checkpoint.py`, `runtime/api.py`, `runtime/bootstrap.py`, `runtime/tests/test_audit_integrity.py`, and the existing checkpoint tests. Confirmed schema v3 existed but ordinary service writers and execution-safety checkpoints still emitted unbound v2 state.

### Exact changes made

1. Wired integrity-capable audit state into `IncidentService`.
   - Added fixed internal states: `disabled`, `unbound_legacy`, `verified`, `failed`.
   - Added durable audit-prefix replay and verification against authenticated v3 `audit_chain_sequence` / `audit_chain_head_sha256`.
   - Added deterministic reconstruction for readable legacy checkpoints without falsely calling the old history authenticated.
   - Added `_checkpoint_for_snapshot()` so ordinary checkpoint writes can bind the current chain head without duplicating serialization logic.
   - Audit events advance the local trusted chain only after the underlying audit append succeeds.
   - Lifecycle mutation fails closed once audit verification/advancement enters `failed`.

2. Made local JSONL a real restart-verifiable development path.
   - `JsonlAuditLog` now implements bounded incident/sequence reads over its append-only file.
   - `IncidentService` automatically uses the same JSONL object for readback, so JSON checkpoint + JSONL audit development runs can emit and verify schema v3 without extra wiring.
   - `MemoryAuditLog` remains non-durable by default; merely having an in-memory `read()` method does not cause checkpoints to claim durable audit integrity. Existing in-memory callers therefore remain schema v2/unbound unless an audit reader is explicitly supplied.

3. Preserved audit binding through the remediation safety state machine.
   - `ExecutionSafeIncidentService._persist_dispatching_barrier()` now uses the base checkpoint builder, so the pre-provider `dispatching` barrier carries the same authenticated audit-chain head.
   - Reconciliation-attempt events advance the chain after audit append and persist `dispatching` plus the new chain head atomically through the checkpoint store.
   - Successful bound writes promote reconstructed legacy state to `verified` only after checkpoint save succeeds.
   - Added a pre-dispatch consistency check so an audit-integrity failure cannot write a new dispatch barrier or reach provider execution.
   - Added the same consistency gate before provider reconciliation.

4. Closed the immediate readiness safety gap.
   - The execution-safe runtime maps `audit_integrity == failed` to the existing fail-closed `conflicted` checkpoint state.
   - This makes the current `/readyz` path return not-ready immediately on verified audit tamper, even before dedicated audit-integrity telemetry is added.

5. Added `runtime/tests/test_runtime_audit_checkpoint_binding.py`.
   - Requires JSONL-backed runtime checkpoints to emit schema v3 with a real 64-character chain head.
   - Requires restart to verify that head and remain synchronized.
   - Mutates a durable audit event without changing the checkpoint and requires restart state `failed`, fail-closed checkpoint state, and blocked investigation.
   - Requires the pre-provider `dispatching` barrier to preserve the already-authenticated chain sequence/head exactly rather than downgrading to v2.

### Tests / checks / results

- GitHub repository reads and source writes succeeded.
- Attempted a credential-free local checkout and targeted test run with `python -m unittest tests.test_runtime_audit_checkpoint_binding tests.test_audit_integrity tests.test_incident_checkpoint`.
- The checkout failed before Python started because the execution container still cannot resolve `github.com` (`Could not resolve host: github.com`). The new/affected tests are therefore **not claimed green locally**.
- GitHub reports no commit status contexts for the latest source-test commit; no Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were used.

### Decisions made

1. **Never auto-bind an in-memory audit sink.** A process-local reader is not durable restart evidence and must not cause schema v3 emission.
2. **Use the same JSONL file for local sink + reader.** This keeps the free/local path genuinely restart-verifiable without additional services.
3. **Keep append-before-checkpoint ordering for now.** The chain head advances only after the durable audit append succeeds, preserving the previous sink-failure invariant. CAS-loser orphan events are treated conservatively rather than silently selected away.
4. **Carry the current head through `dispatching` without adding an event.** The dispatch barrier is a lifecycle safety transition, not an audit event, so sequence/head remain unchanged while the authenticated checkpoint phase advances.
5. **Fail closed before provider contact when integrity is failed.** Audit tamper cannot be allowed to coexist with remediation execution merely because provider idempotency exists.
6. **Use existing checkpoint readiness as the immediate safety gate.** Dedicated `audit_integrity` readiness/metrics remain desirable, but false-ready behavior was removed first.

### Current blockers / unknowns

- Dedicated `/readyz`, `/v1/incident`, and Prometheus `audit_integrity` fields/metrics are not yet exposed; failed integrity currently surfaces through the existing `conflicted` checkpoint gate.
- A v3 restore currently verifies the authenticated prefix but the service still needs an explicit check for unauthenticated durable tail events left by a crashed/CAS-losing writer. Such a tail will cause the next chain append to fail, but it should be detected at restore time so readiness is immediately and specifically failed.
- Multi-instance append-before-CAS can leave orphan/duplicate audit events in Cloud Logging. The current strict verifier is safe but may sacrifice availability; a production-grade lineage/commit marker strategy is still needed so the authenticated winner can be distinguished without accepting mutation/reordering.
- The updated runtime tests still need execution in a complete local/CI checkout before a green result can be claimed.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Make audit integrity an explicit operator contract and close restore-time orphan detection: reject any durable sequence beyond the authenticated v3 chain head (including duplicate/conflicting sequence entries) before reporting readiness, expose fixed-cardinality `audit_integrity={disabled,unbound_legacy,verified,failed}` through `/v1/incident`, `/readyz`, and one-hot Prometheus metrics, and add a multi-instance CAS-loser acceptance test proving an orphan audit append cannot be mistaken for the authenticated checkpoint winner or permit remediation replay.**

## Previous run summary

The previous run introduced checkpoint schema v3 fields for an authenticated audit-chain sequence/head while deliberately leaving ordinary runtime writers on v2 until a real integrity proof existed.
