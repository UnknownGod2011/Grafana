# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 with a durable pre-side-effect remediation phase, bounded reconciliation reasons, and bounded append-only reconciliation audit events.

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
- Real TLS/SIGKILL acceptance now checks reconciliation audit ordering and checkpoint sequence monotonicity across ambiguous reads, authoritative recovery, and restart.

## Run log — 2026-09-08 — HTTPS crash/reconciliation audit acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected the current real TLS/SIGKILL reconciliation ambiguity harness, reconciliation audit unit coverage, the execution-safety reconciliation flow, and the current `main` head.

### Exact changes made

1. Added `runtime/tests/test_http_reconciliation_audit_sequence.py`.
   - Reuses the existing concrete loopback HTTPS provider and real spawned-process `SIGKILL` boundary after provider acceptance.
   - Exercises malformed JSON, wrong operation-ID echo, unknown provider state, and timeout reconciliation modes.
   - Requires each ambiguous reconciliation call to append exactly one bounded `remediation_reconciliation_attempt.unknown.durable_dispatching` event.
   - Requires the durable checkpoint to remain `dispatching` and the checkpoint sequence to increase after the audited ambiguous read.
   - Switches the same provider to authoritative `accepted`, then requires one bounded accepted attempt and one recovered event after fresh Grafana investigation.
   - Requires checkpoint sequence monotonicity through recovery, durable phase `none`, synchronized/clear state on a fresh restart, and no stale approval.
   - Preserves the core exactly-once safety invariant: one remediation POST total and GET-only reconciliation traffic.

2. Kept CI noise low.
   - Prepared this test and the progress handoff for one atomic source commit/ref update rather than several sequential commits.
   - No workflow rerun or manual GitHub Actions invocation was requested.

### Tests / checks / results

- Repository reads and Git object writes through the GitHub connector succeeded.
- The new acceptance test has not been claimed green because this environment still does not provide a dependable full local checkout/runtime execution path.
- No GitHub Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production-remediation credentials/resources were used.

### Decisions made

1. **Audit safety is now asserted at the real network/crash boundary, not only through stubs.**
2. **Durable sequence monotonicity is part of the acceptance contract.** An audited ambiguous provider read must advance the governed checkpoint without erasing `dispatching`.
3. **Authoritative provider state alone is insufficient for recovery.** The recovered audit event is expected only after the existing fresh Grafana investigation path succeeds.
4. **Exactly-once remediation remains the primary invariant.** Auditability cannot create a replay path; reconciliation remains GET-only and the POST count remains one.

### Current blockers / unknowns

- The new acceptance test still needs execution in a complete local/CI checkout before a green result can be claimed.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Add tamper-evident reconciliation audit continuity across durable restart: persist and verify a bounded audit-chain digest/previous-event hash in checkpoint-backed audit state (without storing provider identifiers), then test that deletion, reordering, or mutation of reconciliation audit entries is detected and fails readiness closed while normal crash/recovery remains restart-safe.**

## Previous run summary

The previous run introduced bounded append-only reconciliation-attempt and recovery audit events and guaranteed that audit persistence cannot regress the durable `dispatching` barrier.
