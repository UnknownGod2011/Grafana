# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, bounded append-only reconciliation audit events, a deterministic tamper-evident audit hash chain, and backward-compatible checkpoint schema v3 audit-chain binding wired into ordinary lifecycle, pre-dispatch, and reconciliation checkpoint writes when a durable audit reader is available. Audit integrity is now an explicit fixed-cardinality operator contract through incident state, readiness, and Prometheus metrics.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored `dispatching` and legacy ambiguous approvals require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, or failed audit integrity; execution phase, reconciliation reason, and audit-integrity telemetry are fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions; provider payloads, operation IDs, endpoints, credentials, generations, and raw exceptions are excluded.
- Reconciliation audit persistence must never regress the durable `dispatching` barrier back to `approved`.
- Audit-chain state uses domain-separated SHA-256, strict contiguous sequence numbers, and never advances its trusted head when the underlying audit append fails.
- Schema v3 is emitted only when a real durable-audit chain head is available; non-durable/in-memory callers remain on v2 rather than receiving a fake integrity proof.
- In the execution-safe runtime, an audit-integrity failure maps to fail-closed checkpoint readiness and lifecycle mutation is blocked before dispatch/reconciliation work.
- The authenticated checkpoint audit sequence is authoritative on restore. Durable audit events beyond that head are treated as uncommitted/orphan lineage and must never be adopted into runtime sequence or approval state.
- Invalid or internally failing audit-integrity values collapse to `failed`; they can never become metric labels or silently preserve readiness.

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
- Fixed-cardinality `audit_integrity={disabled,unbound_legacy,verified,failed}` exposure through `/v1/incident`, `/readyz`, and one-hot Prometheus metrics with independent fail-closed readiness behavior.

## Run log — 2026-09-08 — audit-integrity operator observability

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected `runtime/api.py`, `runtime/incident_service.py`, `runtime/tests/test_checkpoint_observability.py`, `runtime/tests/test_execution_reconciliation_observability.py`, the current repository head, and the previous orphan-tail handoff. Confirmed `IncidentService.audit_integrity_state()` already bounded internal values but the API still hid that state behind checkpoint aliases, leaving operators unable to distinguish audit tamper from ordinary checkpoint conflict/execution ambiguity.

### Exact changes made

1. Added a fixed audit-integrity API contract in `runtime/api.py`.
   - Added the only allowed operator states: `disabled`, `unbound_legacy`, `verified`, `failed`.
   - Added `_audit_integrity_state(service)` which uses the runtime getter, collapses invalid values and getter failures to `failed`, and treats truly legacy service stubs with no getter as `disabled` for backward-compatible tests/integration adapters.
   - Added `audit_integrity` to `/v1/incident` lifecycle views and all lifecycle-view responses produced after checkpoint reload/reconciliation.

2. Made audit failure an independent readiness gate.
   - `/readyz` now includes `checks.audit_integrity`.
   - `audit_integrity == failed` forces `ready=false` even when `checkpoint_state == synchronized`, so audit tamper is not dependent on execution-safe checkpoint aliasing.
   - The top-level exception fallback also emits `audit_integrity=failed` rather than omitting the check.

3. Added one-hot fixed-cardinality Prometheus telemetry.
   - Added `stageguard_audit_integrity{state="disabled|unbound_legacy|verified|failed"}` with exactly one active series.
   - No incident IDs, production IDs, operation IDs, provider URLs, credentials, exception text, or other dynamic identifiers are accepted as labels.
   - Invalid/internal values are converted to the existing fixed `failed` label before metrics are rendered.

4. Added `runtime/tests/test_audit_integrity_observability.py`.
   - Covers all four lifecycle-view states.
   - Proves failed audit integrity blocks readiness independently of synchronized checkpoint state.
   - Proves `disabled`, `unbound_legacy`, and `verified` do not override an otherwise healthy evidence plane.
   - Requires the metric to be one-hot with exactly the fixed label set and checks representative incident/provider/secret values are absent.
   - Requires invalid values and exceptions to collapse to `failed` for getter, readiness, and metrics.
   - Preserves explicit `disabled` semantics for legacy service stubs that do not implement the current getter.

### Tests / checks / results

- GitHub repository reads and source writes succeeded.
- Compared the implementation head against the previous handoff; the source delta is limited to `runtime/api.py` plus the new observability regression test before this `progress.md` update.
- Attempted the targeted credential-free suite with `python -m unittest tests.test_audit_integrity_observability tests.test_execution_reconciliation_observability tests.test_runtime_audit_checkpoint_binding` after a fresh clone.
- The clone again failed before Python started because the execution container cannot resolve `github.com` (`Could not resolve host: github.com`). These tests are therefore **not claimed green locally**.
- No GitHub Actions workflow was manually triggered or rerun.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were used.

### Decisions made

1. **Expose audit integrity separately from checkpoint state.** Operators need to distinguish lifecycle CAS contention, provider execution ambiguity, and cryptographic audit failure without reading logs or provider details.
2. **Treat invalid values as integrity failure.** A future bug or corrupt internal state must not introduce high-cardinality labels or preserve readiness accidentally.
3. **Keep labels fixed and payload-free.** Only the four state names are exported; no audit digest, sequence, incident ID, operation identity, provider endpoint, or actor becomes a Prometheus label.
4. **Do not make `unbound_legacy` fail readiness yet.** It explicitly communicates that an older/non-bound checkpoint lacks authenticated audit binding while preserving backward-compatible operation; production hardening can later add a policy knob requiring `verified` for selected deployments.
5. **Keep a missing getter compatible with legacy service stubs.** All current StageGuard runtime services expose `audit_integrity_state()`; treating absent methods as `disabled` avoids breaking older adapters while invalid/failing implementations still collapse to `failed`.

### Current blockers / unknowns

- The targeted tests still need execution in a complete local/CI checkout before a green result can be claimed.
- Multi-instance append-before-CAS can still leave orphan/duplicate events in Cloud Logging. Restore detects them safely, but a production-grade lineage/commit-marker strategy is still needed to distinguish the authenticated winner without sacrificing availability.
- There is not yet a deployment policy to require `verified` rather than merely reject `failed`; `unbound_legacy` is observable but currently allowed for backward compatibility.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Add an explicit production integrity policy (`allow_unbound_legacy` for migration vs `require_verified` for hardened deployments) wired through bootstrap/configuration and `/readyz`, default the Cloud Run production path to `require_verified` when durable checkpointing plus a durable audit reader are configured, and add startup/readiness tests proving production cannot accidentally run indefinitely on an unbound legacy checkpoint while local development remains backward compatible.**

## Previous run summary

The previous run rejected unauthenticated/orphan durable audit tails at restore so a crashed or CAS-losing writer cannot have its append-only tail silently adopted into the authenticated lifecycle lineage.
