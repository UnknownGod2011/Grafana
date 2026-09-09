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

## Run log — 2026-09-09 — default-bootstrap compaction/replay acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/bootstrap.py`, `runtime/tests/test_bootstrap_execution_safety.py`, `runtime/tests/test_anchored_execution_safety.py`, `runtime/incident_service.py`, and `runtime/remediation.py`. Confirmed the prior handoff accurately identified the remaining gap: anchor compaction had direct service-level coverage, and bootstrap selected the anchor-aware execution-safe composition, but there was no end-to-end acceptance test proving the normal `build_runtime` path can create a real completed lifecycle, physically lose the authenticated pre-anchor JSONL prefix, restart verified, and avoid replaying a consumed remediation.

### Exact changes made

1. Extended `runtime/tests/test_bootstrap_execution_safety.py` with a credential-free default-bootstrap acceptance test.
   - Uses the actual `build_runtime` constructor with `checkpoint_backend="json"`, real local JSONL audit storage, and `audit_anchor_interval=1`.
   - Drives a diagnosed incident through explicit approval and successful recovery verification.
   - Uses a counting remediation adapter and asserts the original runtime invokes it exactly once.
   - Reads the authenticated anchor sequence, physically deletes every audit record at or before that anchor, and preserves only any later suffix records.
   - Restarts through `build_runtime` using the same checkpoint/audit files and a fresh counting remediation adapter.
   - Asserts restart reports `audit_integrity=verified`, checkpoint state `synchronized`, execution reconciliation `clear`, and restores the completed approval/outcome.
   - Asserts restart itself performs zero remediation calls.
   - Attempts `execute_approved()` again and asserts the single-use approval remains consumed, with the replacement remediation adapter still at zero calls.
2. Strengthened the test fakes without changing production code.
   - `FakeMetrics` can now serve a deterministic sequence while retaining the previous constant-value default for existing bootstrap tests.
   - Added `CountingRemediation` and a compact diagnosed-plus-healthy-recovery fixture.
3. Kept repository/CI impact bounded.
   - Prepared the test and this handoff as one Git tree/commit/ref update rather than multiple file commits.
   - Did not trigger or rerun GitHub Actions.

### Tests / checks / results

- Repository reads and Git object preparation succeeded through the connected GitHub integration.
- The new acceptance path is deterministic and credential-free, but this automation environment still does not expose a complete executable checkout/import path, so no green Python test-suite claim is made for this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No live Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, remediation endpoint, or operator resource was touched.

### Decisions made

1. **Test a consumed approval rather than only an investigated checkpoint.** This exercises the more dangerous replay boundary: a remediation that already executed before compaction must remain consumed after restart and must not contact the adapter again.
2. **Compact using the authenticated anchor sequence, not an arbitrary line count.** The acceptance test now mirrors the actual safety contract operators/retention tooling must respect.
3. **Keep physical compaction external for now.** StageGuard can safely verify compacted prefixes, but automatic destructive retention remains intentionally separate from integrity verification until retention policy, backup behavior, and operator recovery semantics are specified.
4. **Do not spend CI/storage to validate one automation increment.** The project has a history of Actions storage/noise concerns, so no manual workflow execution was introduced.

### Current blockers / unknowns

- The expanded bootstrap regression has not executed in a complete checkout during this run.
- A constructor-only fake test for the GCS + Cloud Logging production composition is still missing.
- A real GCS + Cloud Logging schema-v4 restart has not been exercised against Google Cloud credentials/resources.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.
- Automatic local JSONL compaction/retention is not implemented; anchors only make a correctly chosen authenticated prefix safe to remove.

## Single best next step

**Add a constructor-only GCS + Cloud Logging bootstrap test using fakes/patching around `GoogleCloudStorageCheckpointStore.from_environment`, `GoogleCloudLoggingAuditSink.from_environment`, and `GoogleCloudAuditReader.from_environment`. Prove the production constructor selects one shared Cloud Logging identity, an observable GCS checkpoint store, `AnchoredExecutionSafeIncidentService`, hardened `require_verified` policy when invoked through the Cloud Run composition, and the configured anchor interval without requiring any Google credentials or touching live resources.**

## Previous run summary

The previous run activated `AnchoredExecutionSafeIncidentService` and `AnchoredJsonlAuditLog` in the default bootstrap, added bounded `--audit-anchor-interval` configuration, and preserved the existing Cloud Run security composition.
