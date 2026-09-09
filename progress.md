# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, and the anchor-aware + execution-safe service as the default bootstrap composition.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Production remediation uses deterministic idempotency identity and does not automatically replay ambiguous external side effects.
- `dispatching` is durably persisted before provider contact when the checkpoint store supports execution phases.
- Reconciliation is GET-only and ambiguous provider state requires fresh Grafana evidence before recovery completion.
- GCS checkpoints are HMAC-authenticated and generation-CAS protected.
- The authenticated checkpoint audit-chain head is lifecycle authority; losing-writer residue cannot manufacture lifecycle state.
- Audit anchors are authenticated compaction boundaries, not independent trust roots; promotion becomes authoritative only after checkpoint persistence succeeds.
- Branched-lineage verification and candidate reads are bounded and fail closed on state/candidate explosion or silent truncation.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Run log — 2026-09-09 — fake-cloud authenticated restart acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/bootstrap.py`, `runtime/incident_checkpoint.py`, `runtime/cloud_audit.py`, `runtime/durable_audit_reader.py`, `runtime/audit_anchor.py`, `runtime/api.py`, `runtime/incident_service.py`, and the existing bootstrap execution-safety regressions. Confirmed the previous handoff accurately identified the strongest remaining credential-free gap: constructor wiring was covered, but the real StageGuard GCS/Cloud Logging adapters had not yet been exercised together through a completed schema-v4 lifecycle and restart containing a losing writer branch.

### Exact changes made

1. Added `runtime/tests/test_fake_cloud_restart_acceptance.py`.
   - Uses the real `GoogleCloudStorageCheckpointStore`, `GoogleCloudLoggingAuditSink`, `GoogleCloudAuditReader`, `build_runtime`, and `AnchoredExecutionSafeIncidentService` production composition.
   - Supplies only in-memory fake bucket/blob and Cloud Logging logger primitives at the external provider boundary; no Google client library call, credential, network request, or live resource is required.
   - The fake GCS object model implements generation-aware `exists`, `reload`, conditional download, and conditional upload behavior, including HTTP-412-like precondition failures, so the real checkpoint adapter still performs HMAC serialization/verification and generation bookkeeping.
   - The fake Cloud Logging logger stores the real bounded `stageguard.audit.v1` documents produced by `GoogleCloudLoggingAuditSink` and implements the sequence/incident range contract consumed by the real branch-aware reader.
2. Added a full production-bootstrap lifecycle/restart acceptance path.
   - Drives investigation -> explicit approval -> successful remediation -> Grafana-style recovery verification through `build_runtime` with `audit_backend="cloud-logging"`, `checkpoint_backend="gcs"`, `require_verified`, and a bounded anchor cadence.
   - Verifies the original remediation adapter executes exactly once and the lifecycle reaches authenticated audit-integrity state.
   - Requires a real non-genesis anchor with an authenticated post-anchor suffix.
   - Injects a competing same-sequence Cloud Logging record only into that authenticated suffix, simulating append-before-CAS residue from a losing writer without modifying the signed checkpoint.
   - Reconstructs fresh production adapters on restart through `build_runtime`, using the same fake durable GCS object and Cloud Logging log identity.
   - Asserts the authenticated winning lineage restores `recovered`, `audit_integrity=verified`, synchronized checkpoint state, clear execution reconciliation, and the hardened `require_verified` policy.
   - Asserts the readiness-integrity policy is satisfied only because the restored state is exactly `verified`.
   - Proves restart invokes the replacement remediation adapter zero times and the previously consumed approval still cannot be executed again.
3. Kept repository/CI impact bounded.
   - Prepared the new regression and this progress handoff as one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- Repository inspection and Git object preparation succeeded through the connected GitHub integration.
- The new regression is deliberately credential-free and exercises real StageGuard adapter logic above the provider SDK boundary.
- This automation environment still does not expose a complete executable checkout/import path, so no green Python test-suite claim is made for this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.

### Decisions made

1. **Use real StageGuard cloud adapters over fake provider primitives, not fake StageGuard adapters.** This gives materially stronger coverage of checkpoint HMAC encoding/decoding, GCS generation semantics, structured audit serialization, Cloud Logging range filtering, anchor-aware lineage selection, and production bootstrap composition while remaining offline.
2. **Inject the loser branch after a non-genesis anchor.** That specifically exercises the bounded authenticated suffix path rather than falling back to full-history verification.
3. **Test the dangerous replay boundary.** The restart acceptance criterion includes a completed/consumed approval and asserts zero remediation calls during restart and on an attempted replay.
4. **Keep external cloud acceptance separate.** IAM policy, actual GCS generation preconditions, Cloud Logging query/retention behavior, and Cloud Run/IAP still require deliberate live-environment validation and should not be touched by an unattended development run.

### Current blockers / unknowns

- The new fake-cloud regression has not executed in a complete checkout during this run.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging query consistency/retention, Cloud Run/IAP browser flow, and Secret Manager wiring remains external-resource work.
- Live Grafana MCP acceptance against a real Grafana Cloud or self-hosted instance remains external-resource work.
- Automatic local or cloud audit compaction/retention is not implemented; authenticated anchors make a correctly chosen prefix safe to remove but StageGuard still does not perform destructive retention itself.
- A production remediation provider integration still requires an operator-owned endpoint and credentials for real acceptance.

## Single best next step

**Implement a non-destructive audit-retention planner/CLI that reads the authenticated schema-v4 checkpoint and reports the exact safe compaction boundary, candidate records/bytes eligible for removal, and refusal reasons without deleting anything. Add credential-free JSONL and Cloud Logging tests proving it never proposes deletion beyond the authenticated anchor, refuses unverified/unbound/conflicted state, and emits an operator-auditable plan that can later be connected to explicit retention tooling.**

## Previous run summary

The previous run added credential-free constructor tests proving the production GCS + Cloud Logging bootstrap selects one shared audit log identity, an observable GCS checkpoint store, the anchored execution-safe runtime, bounded anchor cadence, and hardened `require_verified` policy.
