# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, bounded append-only reconciliation audit events, a deterministic tamper-evident audit hash chain, and a backward-compatible checkpoint schema v3 capable of authenticating the audit-chain sequence/head alongside lifecycle state.

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
- Checkpoint schema v3 is emitted only when both audit-chain sequence and head exist; ordinary callers remain on v2 until they provide a real integrity proof.

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

## Run log — 2026-09-08 — checkpoint schema v3 audit binding

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected `runtime/incident_checkpoint.py`, `runtime/audit_integrity.py`, `runtime/incident_service.py`, `runtime/execution_safety.py`, and `runtime/tests/test_incident_checkpoint.py`. Confirmed the prior run had a cryptographic audit-chain primitive but no durable checkpoint field capable of authenticating its trusted head.

### Exact changes made

1. Extended `runtime/incident_checkpoint.py` with checkpoint schema v3.
   - Added `stageguard.incident-checkpoint.v3`.
   - Added optional `audit_chain_sequence` and `audit_chain_head_sha256` fields to `IncidentCheckpoint`.
   - Added strict bounded validation: sequence/head must appear together, sequence must be a non-negative integer, the head must be lowercase 64-character SHA-256 hex, and sequence zero must use the fixed all-zero genesis digest.
   - Added a cross-field invariant that a restored v3 audit-chain sequence cannot exceed the lifecycle audit sequence stored in the same authenticated checkpoint.
   - The v3 values are inside the existing checkpoint canonical document and therefore protected by the same SHA-256 integrity digest and, for GCS production checkpoints, the existing HMAC authenticity check.

2. Preserved backward compatibility instead of forcing fake integrity state.
   - Existing lifecycle callers currently do not supply an audit-chain checkpoint.
   - `checkpoint_document()` therefore continues writing schema v2 when both audit-chain fields are absent.
   - Schema v3 is emitted only when a complete real binding is supplied.
   - v1 and v2 readers remain supported and restore the new fields as `None`.
   - This avoids falsely advertising tamper-evident audit continuity before `IncidentService` is wired to `ChainedAuditSink`.

3. Strengthened `runtime/tests/test_incident_checkpoint.py`.
   - Existing ordinary lifecycle serialization is explicitly required to remain v2 until a real binding exists.
   - Added v3 signed round-trip coverage for chain sequence/head.
   - Added rejection coverage for partial bindings, invalid non-genesis empty-chain heads, and audit-chain sequence values ahead of the lifecycle sequence.
   - Added HMAC authenticity coverage proving a chain-head mutation cannot be accepted by merely recomputing the public SHA-256 document digest.
   - Extended legacy-v1 coverage to require absent audit-chain state after restore.

### Tests / checks / results

- GitHub repository reads and source writes succeeded.
- The repository could not be cloned into the local execution container because DNS resolution for `github.com` still fails, so Python/unit-test execution could not start in this environment.
- The changed code was manually checked against the existing positional `IncidentCheckpoint` construction pattern; new fields were appended with defaults so existing call sites remain source-compatible.
- No GitHub Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production-remediation credentials/resources were used.
- The new tests are **not claimed green locally** until they run in a complete checkout.

### Decisions made

1. **Do not globally switch existing writers to v3 yet.** A v3 document without a real chain head would create misleading security semantics.
2. **Authenticate the chain binding inside the existing checkpoint envelope.** This lets the current GCS HMAC + generation-CAS mechanism protect lifecycle state and audit continuity atomically once the service supplies the head.
3. **Keep cryptographic implementation ownership in `audit_integrity.py`.** `incident_checkpoint.py` validates only the bounded serialized representation, avoiding a circular import through `incident_service.AuditEvent`.
4. **Reject impossible sequence relationships.** The audit chain cannot claim to contain an event beyond the lifecycle checkpoint sequence it is authenticating.
5. **Leave v1/v2 readable.** Existing deployments can upgrade without destructive checkpoint migration.

### Current blockers / unknowns

- `IncidentService` and `ExecutionSafeIncidentService` do not yet persist `ChainedAuditSink.checkpoint()` into the new v3 fields, so normal runtime checkpoints intentionally remain v2.
- Restore/reload does not yet verify durable audit events against the authenticated v3 head, and `/readyz` does not yet expose an `audit_integrity` state.
- The updated checkpoint tests still need execution in a complete local/CI checkout before a green result can be claimed.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Wire `IncidentService` to an integrity-capable audit sink/reader: persist the current `AuditChainCheckpoint` in every ordinary, dispatching, and reconciliation checkpoint; on v3 restore/reload verify the bounded durable audit suffix against the authenticated head; expose fixed-cardinality `audit_integrity` states such as `disabled`, `unbound_legacy`, `verified`, and `failed`; and make readiness fail closed on `failed` without changing the exactly-once remediation/reconciliation invariants.**

## Previous run summary

The previous run added the provider-neutral tamper-evident SHA-256 audit-chain primitive with deterministic restart continuation and deletion/reordering/mutation detection.
