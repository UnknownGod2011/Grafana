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

## Run log — 2026-09-09 — credential-free production constructor wiring

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/bootstrap.py`, `runtime/cloudrun_entrypoint.py`, `runtime/incident_checkpoint.py`, `runtime/tests/test_bootstrap_execution_safety.py`, and `runtime/tests/test_cloudrun_entrypoint.py`. Confirmed the previous handoff accurately identified the remaining gap: local/default bootstrap had compaction and no-replay acceptance coverage, but the GCS + Cloud Logging production constructor wiring was not explicitly verified without credentials.

### Exact changes made

1. Added a credential-free GCS + Cloud Logging constructor test to `runtime/tests/test_bootstrap_execution_safety.py`.
   - Patches only the external Google constructors and server/service construction boundary; no Google client library call or network resource is required.
   - Proves `GoogleCloudStorageCheckpointStore.from_environment` receives the configured bucket, HMAC material, project, and object name through environment-backed bootstrap configuration.
   - Proves the Cloud Logging audit sink and audit reader receive the exact same project and log identity, preventing a split evidence/audit stream caused by divergent bootstrap names.
   - Proves the GCS store is wrapped in `ObservableCheckpointStore` before being passed into the runtime service.
   - Proves bootstrap selects `AnchoredExecutionSafeIncidentService`, passes the configured bounded audit-anchor interval, and applies `require_verified` to the service.
   - Proves the same service instance is handed to the HTTP server constructor.
2. Strengthened `runtime/tests/test_cloudrun_entrypoint.py`.
   - The no-GCS Cloud Run path now explicitly asserts `allow_unbound_legacy` rather than merely checking the checkpoint backend.
   - The durable GCS Cloud Run path now explicitly asserts `require_verified`, making the production hardening contract executable in tests.
   - Existing checks that bucket/HMAC secret values are not placed in argv remain intact.
3. Kept repository/CI impact bounded.
   - Prepared both test edits and this handoff as one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- Repository inspection and Git object preparation succeeded through the connected GitHub integration.
- The added tests are credential-free and isolate external constructors with `unittest.mock`; however, this automation environment still does not expose a complete executable checkout/import path, so no green Python suite claim is made for this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No live Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, remediation endpoint, or operator resource was touched.

### Decisions made

1. **Verify concrete constructor arguments instead of mocking the entire bootstrap helper.** This catches project/log-name drift and bucket/object wiring errors while still remaining credential-free.
2. **Assert the observable wrapper explicitly.** Production durability is not only about using GCS; checkpoint health must remain visible through StageGuard's bounded Prometheus telemetry surface.
3. **Keep Cloud Run policy tests separate from bootstrap constructor tests.** `cloudrun_entrypoint.py` owns immutable production hardening, while `bootstrap.py` owns adapter construction; testing both boundaries prevents one layer from silently weakening the other.
4. **Do not execute live cloud validation in an unattended development increment.** Real IAM, GCS generation-CAS, Cloud Logging retention/query behavior, and IAP still require deliberate external-resource acceptance.

### Current blockers / unknowns

- The expanded Python regressions have not executed in a complete checkout during this run.
- A real GCS + Cloud Logging schema-v4 restart has not been exercised against Google Cloud credentials/resources.
- The production path still lacks a credential-free end-to-end fake-cloud restart test that persists an authenticated checkpoint and reconstructs a branched Cloud Logging suffix through the normal bootstrap composition.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.
- Automatic local JSONL compaction/retention is not implemented; anchors only make a correctly chosen authenticated prefix safe to remove.

## Single best next step

**Add a credential-free fake-cloud restart acceptance test that uses the normal production bootstrap composition with an in-memory GCS checkpoint implementation and an in-memory Cloud Logging sink/reader pair sharing one log identity. Drive a completed lifecycle to schema v4, restart through `build_runtime`, and prove `audit_integrity=verified`, hardened readiness, anchor-aware suffix selection, and zero remediation replay even when the fake log contains a losing same-sequence writer branch.**

## Previous run summary

The previous run added a default-bootstrap compaction/no-remediation-replay acceptance test using real local JSON checkpoint and JSONL audit state.
