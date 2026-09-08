# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, append-only reconciliation audit events, deterministic tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, restore-time orphan-tail rejection, explicit audit-integrity observability, hardened audit-integrity readiness policy, and operator-facing integrity migration guidance.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored ambiguity requires reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, failed audit integrity, or configured audit-integrity policy violation.
- Reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions.
- Audit-chain state uses domain-separated SHA-256 and strict contiguous sequence numbers.
- Schema v3 is emitted only when a real durable-audit chain head is available.
- The authenticated checkpoint audit sequence is authoritative on restore; orphan durable audit tails are rejected.
- Audit-integrity state/policy telemetry is fixed-cardinality; invalid values collapse fail-closed.

## Completed milestones

- Deterministic media telemetry simulator plus local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and strict evidence scope.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded outcomes.
- Revision-bound Gemini incident-commander briefing layer.
- Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, CAS conflict handling, operator recovery cockpit, execution phases, crash/SIGKILL ambiguity coverage, reconciliation reason model, bounded reconciliation audit events, tamper-evident audit chain, schema-v3 binding, restore-time audit verification, integrity observability/policy, and operator integrity-policy safety.

## Run log — 2026-09-09 — legacy-v2 to hardened-v3 migration acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_checkpoint.py`, `runtime/incident_service.py`, `runtime/api.py`, `runtime/readiness.py`, `runtime/tests/test_runtime_audit_checkpoint_binding.py`, and `runtime/tests/test_audit_integrity_policy.py`. Confirmed the prior handoff's highest-priority gap: policy/readiness and v3 binding were individually covered, but no credential-free acceptance test proved a legitimate persisted v2 lineage could migrate through hardened-unready into verified v3 and remain verified after restart without creating approval/remediation replay risk.

### Exact changes made

1. Added `runtime/tests/test_audit_integrity_migration.py`.
   - Uses the real `JsonCheckpointStore`, `JsonlAuditLog`, `IncidentService`, checkpoint serializer, readiness policy, and audit-chain restore logic.
   - Adds a small append-only audit wrapper that models a legitimate legacy deployment: audit events are durably written to JSONL, but no reader capability is exposed to the service, so a normal investigation emits a real schema-v2 checkpoint rather than a fabricated fixture.
   - Restarts the same durable checkpoint/audit pair with the real JSONL reader under `require_verified` and asserts `audit_integrity=unbound_legacy` plus readiness false.
   - Performs a normal investigation as the migration write; the reconstructed legacy chain is extended by one contiguous event and the checkpoint becomes schema v3 with matching lifecycle/audit sequence 2.
   - Asserts policy readiness becomes true only after the real v3 binding reports `verified`.
   - Restarts again from the same durable pair and asserts `verified`, `synchronized`, ready, sequence continuity, identical evidence revision, no stale approval/outcome, and zero remediation calls.
   - Reads the durable audit stream and requires exactly sequences `[1, 2]`, both legitimate `investigation_completed` events; no approval or remediation audit event is manufactured by migration.

### Tests / checks / results

- Repository inspection and Git object creation succeeded through the GitHub connector.
- The acceptance test is intentionally credential-free and uses temporary local stores; no cloud resource is required to execute it.
- This run could not execute the Python suite in a complete checkout from the current tool environment, so the new test is **not claimed green locally**.
- No GitHub Actions workflow was manually triggered or rerun, avoiding additional CI/storage noise.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Migration fixtures must be produced by StageGuard itself.** The test does not hand-author, patch, or recompute checkpoint digests; a real legacy-compatible service write creates v2.
2. **`require_verified` gates readiness, not recovery of a valid legacy lineage.** A complete legacy audit prefix can be reconstructed as `unbound_legacy`, then a legitimate lifecycle audit write seals v3. Failed integrity still blocks lifecycle mutation in the service itself.
3. **Migration must not imply remediation authority.** The acceptance path contains no approval and invokes the remediation adapter zero times before, during, and after restart.
4. **Restart is part of the proof.** A process-local transition to `verified` is insufficient; the persisted v3 head must verify against the durable JSONL audit stream in a fresh service instance.

### Current blockers / unknowns

- The new migration acceptance test still needs execution in a complete checkout before a green result can be claimed.
- The credential-free test uses the local SHA-256 protected checkpoint store; production GCS additionally HMAC-authenticates the same v3 state and still needs real generation/IAM acceptance against GCS.
- Multi-instance append-before-CAS can still leave orphan/duplicate events in Cloud Logging; restore rejects them safely, but a production lineage/commit-marker strategy remains desirable.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Design and implement a committed-lineage audit protocol for multi-instance production writers so append-before-CAS orphan events can be distinguished and safely compacted/ignored without weakening tamper detection: keep the current fail-closed restore behavior as the baseline, add a bounded checkpoint-backed lineage/commit marker, and prove with concurrent-writer tests that a losing writer cannot poison the winning audit lineage or cause remediation replay.**

## Previous run summary

The previous run surfaced audit-integrity state/policy in the operator cockpit, blocked lifecycle controls under hardened violations, added fail-closed browser handling for unknown states, documented safe migration guidance, and prohibited manual digest/checkpoint fabrication as a migration shortcut.
