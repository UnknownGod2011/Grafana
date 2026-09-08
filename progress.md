# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, bounded append-only reconciliation audit events, a deterministic tamper-evident audit hash chain, and backward-compatible checkpoint schema v3 audit-chain binding wired into ordinary lifecycle, pre-dispatch, and reconciliation checkpoint writes when a durable audit reader is available.

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
- The authenticated checkpoint audit sequence is authoritative on restore. Durable audit events beyond that head are treated as uncommitted/orphan lineage and must never be adopted into runtime sequence or approval state.

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
- Restore-time orphan-tail rejection so append-before-CAS losers cannot be silently adopted after restart.

## Run log — 2026-09-08 — restore-time orphan audit rejection

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected `runtime/incident_service.py`, `runtime/api.py`, `runtime/tests/test_runtime_audit_checkpoint_binding.py`, the latest source commits, and current commit-status state. Confirmed the previous runtime binding verified the authenticated audit prefix but `_apply_checkpoint()` still raised the in-memory sequence to the maximum durable audit sequence. That meant a crashed or CAS-losing writer could leave an append-only tail that was not authenticated by the winning checkpoint yet was silently adopted into process sequence state.

### Exact changes made

1. Closed restore-time orphan adoption in `runtime/incident_service.py`.
   - Added `_assert_no_audit_tail(incident_id, authenticated_sequence)`.
   - After verifying either a v3 authenticated chain head or a reconstructed readable legacy prefix, the runtime now performs a bounded durable read strictly after the authenticated/checkpoint sequence.
   - Any event beyond that head marks audit integrity `failed`; it is never treated as continuation of the winning lineage.
   - Removed the previous `_apply_checkpoint()` logic that used the maximum durable audit sequence.
   - Restored runtime `_sequence` now remains exactly the checkpoint sequence, preserving the authenticated winner as the source of truth.

2. Preserved conservative behavior for legacy readable checkpoints.
   - A complete legacy prefix can still be reconstructed when a durable reader exists.
   - A durable tail beyond the legacy checkpoint sequence now fails integrity instead of being silently absorbed.
   - Non-durable/in-memory deployments remain unchanged and do not claim schema-v3 integrity.

3. Extended `runtime/tests/test_runtime_audit_checkpoint_binding.py`.
   - Added a concrete orphan-tail case: create a valid v3 checkpoint at sequence 1, append an uncommitted sequence-2 `remediation_approved` event without updating the checkpoint, restart, and require `audit_integrity == failed`, fail-closed checkpoint state, checkpoint sequence preservation, no restored approval, and blocked investigation.
   - Added a conflicting duplicate case at the authenticated sequence with a different actor and requires fail-closed restore.
   - Existing v3 restart verification, mutation detection, and `dispatching` head-preservation tests remain intact.

### Tests / checks / results

- GitHub repository reads and source writes succeeded.
- Reviewed the resulting source diff after write; it contains only the intended orphan-tail guard, restore sequence change, and tests.
- Attempted the targeted credential-free local suite with `python -m unittest tests.test_runtime_audit_checkpoint_binding tests.test_audit_integrity tests.test_incident_checkpoint` after a fresh clone.
- The clone again failed before Python started because the execution container cannot resolve `github.com` (`Could not resolve host: github.com`). The updated tests are therefore **not claimed green locally**.
- GitHub reports no commit status contexts for the latest test commit; no Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were used.

### Decisions made

1. **Authenticated checkpoint state wins over append-only tail state.** A durable append is not committed StageGuard lineage until the matching checkpoint CAS succeeds.
2. **Fail closed rather than auto-truncate.** StageGuard does not mutate or delete suspicious durable audit events during restore; operators retain forensic evidence.
3. **Never infer approval from orphan audit events.** Lifecycle truth remains checkpoint-backed, so an uncommitted `remediation_approved` audit line cannot manufacture executable state.
4. **Keep restore reads bounded.** Detecting existence of a tail requires only one event beyond the authenticated head; there is no need to ingest arbitrary untrusted history.
5. **Do not weaken append-before-checkpoint ordering yet.** The existing ordering protects against persisting a chain head for an audit event that never became durable; lineage/commit markers remain the longer-term availability improvement.

### Current blockers / unknowns

- Dedicated `/readyz`, `/v1/incident`, and Prometheus `audit_integrity` fields/metrics are still not exposed; failed integrity currently surfaces through the existing fail-closed checkpoint gate.
- Multi-instance append-before-CAS can still leave orphan/duplicate events in Cloud Logging. Restore now detects them safely, but a production-grade lineage/commit-marker strategy is still needed to distinguish the authenticated winner without sacrificing availability.
- The updated runtime tests still need execution in a complete local/CI checkout before a green result can be claimed.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Expose `audit_integrity={disabled,unbound_legacy,verified,failed}` as an explicit fixed-cardinality operator contract through `/v1/incident`, `/readyz`, and one-hot Prometheus metrics, with `failed` forcing readiness false independently of checkpoint-state aliasing; then add API/metrics regression coverage proving unknown/internal values collapse to `failed` and no incident/provider identifiers appear in labels.**

## Previous run summary

The previous run wired real durable audit-chain state into runtime lifecycle, dispatching, and reconciliation checkpoints and made mutation of the authenticated audit prefix fail closed on restart.
