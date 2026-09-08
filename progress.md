# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 with a durable pre-side-effect remediation phase, bounded reconciliation reasons, bounded append-only reconciliation audit events, and a credential-free deterministic audit hash-chain primitive ready for checkpoint integration.

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
- Audit-chain state uses domain-separated SHA-256, strict contiguous sequence numbers, and never advances its trusted head when the underlying audit sink fails.

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

## Run log — 2026-09-08 — tamper-evident audit-chain foundation

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected `runtime/incident_checkpoint.py`, `runtime/incident_service.py`, `runtime/execution_safety.py`, `runtime/cloud_audit.py`, `runtime/durable_audit_reader.py`, the current HTTPS/SIGKILL reconciliation audit acceptance coverage, and the current `main` head.

### Exact changes made

1. Added `runtime/audit_integrity.py`.
   - Introduces a domain-separated SHA-256 chain over canonical `AuditEvent` documents.
   - Uses a fixed genesis digest and strict contiguous sequence enforcement.
   - Adds `AuditChainCheckpoint(sequence, head_sha256)` as the minimal bounded restart state intended for authenticated checkpoint persistence.
   - Supports bounded restart verification from an already trusted chain checkpoint, avoiding an architectural requirement to replay unbounded historical audit data.
   - Adds `ChainedAuditSink`, which advances chain state only after the wrapped audit sink successfully appends the event. A failed Cloud Logging/local sink write therefore cannot falsely publish an integrity head for an event that was never durably accepted.
   - The chain contains only hashes; it adds no provider operation IDs, endpoints, credentials, response bodies, Grafana query bodies, or raw exception text.

2. Added `runtime/tests/test_audit_integrity.py`.
   - Verifies deterministic chain heads across restart continuation.
   - Verifies deletion and reordering fail through strict sequence continuity.
   - Verifies same-sequence payload mutation fails against the expected authenticated head.
   - Verifies bounded continuation from a trusted intermediate chain checkpoint.
   - Verifies a wrapped sink failure leaves the trusted head at the prior value and permits a later clean retry without sequence corruption.
   - Verifies malformed digests and non-contiguous appends fail closed.

3. Kept GitHub/CI churn low.
   - The implementation, tests, and this handoff are being landed through one Git tree/commit update.
   - No workflow rerun or manual GitHub Actions invocation was requested.

### Tests / checks / results

- Repository reads and Git object writes through the GitHub connector succeeded.
- The new code is intentionally dependency-free beyond the existing StageGuard runtime modules.
- A complete local checkout/runtime is still unavailable in this execution environment, so the new test module is **not claimed green locally**.
- No GitHub Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production-remediation credentials/resources were used.

### Decisions made

1. **Separate cryptographic chain mechanics from storage policy.** The primitive is small, deterministic, and testable before checkpoint schema changes are made.
2. **Do not advance integrity state before durable append succeeds.** Otherwise a sink outage could make checkpoint integrity state refer to an event that does not exist in the durable audit stream.
3. **Support bounded continuation.** Production verification should be able to start from an authenticated prior chain checkpoint instead of depending on Cloud Logging retaining/replaying the entire lifetime of an incident.
4. **Sequence continuity is part of integrity.** Missing or reordered entries fail before digest comparison, while content mutation fails at the expected-head comparison.
5. **No sensitive audit material is added.** Only SHA-256 chain heads and sequence numbers need to cross the checkpoint boundary.

### Current blockers / unknowns

- The new audit-chain test file still needs execution in a complete local/CI checkout before a green result can be claimed.
- The chain primitive is not yet persisted inside `IncidentCheckpoint`; readiness therefore does not yet fail on durable audit-chain mismatch.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Integrate `AuditChainCheckpoint` into a backward-compatible checkpoint schema v3 and `IncidentService`: persist the trusted chain head with every lifecycle/reconciliation checkpoint, verify durable audit continuation on restore/reload, expose a fixed-cardinality `audit_integrity` readiness state, and add restart tests proving deletion/reordering/mutation fail readiness closed while normal SIGKILL reconciliation recovery remains green.**

## Previous run summary

The previous run bound reconciliation audit ordering and checkpoint sequence monotonicity to the real TLS/SIGKILL ambiguity path while preserving exactly one remediation POST and GET-only reconciliation.
