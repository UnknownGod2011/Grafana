# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path now includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, and the anchor-aware + execution-safe service as the default bootstrap composition.

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

## Run log — 2026-09-09 — production bootstrap activation of audit anchors

### Inspected at start

Read `progress.md` completely before deciding work. Inspected current `main`, `runtime/bootstrap.py`, `runtime/cloudrun_entrypoint.py`, `runtime/anchored_incident_service.py`, `runtime/anchored_execution_safety.py`, `runtime/audit_anchor.py`, `runtime/incident_service.py`, `runtime/tests/test_bootstrap_execution_safety.py`, and `runtime/tests/test_cloudrun_entrypoint.py`. Confirmed the previous handoff was accurate: the anchor-aware execution-safe composition existed but production/bootstrap still selected `ExecutionSafeIncidentService`, JSONL bootstrap still used `JsonlAuditLog`, and no operator configuration bounded anchor cadence.

### Exact changes made

1. Switched the default runtime constructor to `AnchoredExecutionSafeIncidentService`.
   - This activates authenticated anchor restore while retaining execution dispatch barriers, reconciliation, checkpoint conflict handling, and existing incident lifecycle semantics.
2. Switched the local JSONL audit backend to `AnchoredJsonlAuditLog`.
   - This preserves the sink contract while adding the exclusive `after_sequence` candidate enumeration required for compacted-prefix restart verification.
3. Added bounded `audit_anchor_interval` runtime configuration.
   - `build_runtime(..., audit_anchor_interval=...)` now defaults to `DEFAULT_ANCHOR_INTERVAL` (1024).
   - `--audit-anchor-interval` is available on the CLI.
   - Bootstrap rejects booleans, values below 1, and values above `MAX_VERIFICATION_SUFFIX_EVENTS` (2048), ensuring configured cadence cannot exceed the authenticated suffix verifier's hard bound.
4. Preserved the Cloud Run security composition.
   - `cloudrun_entrypoint.py` requires no special-case code: it continues to force IAP, Cloud Logging, non-loopback bind, disabled remediation, and `require_verified` whenever GCS durable checkpoints are configured; the new bootstrap default automatically supplies the anchor-aware service and conservative 1024-event cadence.
5. Extended `runtime/tests/test_bootstrap_execution_safety.py`.
   - Asserts default bootstrap returns `AnchoredExecutionSafeIncidentService` while still satisfying `ExecutionSafeIncidentService`.
   - Asserts JSONL bootstrap uses `AnchoredJsonlAuditLog`.
   - Asserts the conservative default interval, a custom bounded interval, and rejection of zero/oversized/boolean values.
6. Landed source, tests, and this handoff through one Git tree/commit/ref update to avoid repeated push-triggered CI noise.

### Tests / checks / results

- Repository reads and Git object construction succeeded through the connected GitHub integration.
- No GitHub Actions workflow was manually started or rerun.
- The automation environment still does not expose a complete repository checkout/import path suitable for executing the Python regression suite, so no green pytest/unittest claim is made for this change.
- The changed bootstrap surface is covered by focused unit regressions, but those tests still need execution in a complete checkout.
- No live Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, remediation endpoint, or operator resource was touched.

### Decisions made

1. **Activate the composed runtime now, but retain conservative defaults.** The composition had already been isolated and regression-specified; leaving production on the older class would make schema-v4 support unreachable through normal startup.
2. **Bound configuration by verifier capacity.** An anchor interval greater than the maximum authenticated suffix span could produce checkpoints that cannot be safely restored before the next anchor roll.
3. **Do not add a Cloud Run-only anchor flag.** A single bootstrap invariant avoids divergent local/production semantics; Cloud Run inherits the safe default while continuing to harden identity, audit, and checkpoint policy independently.
4. **Keep credentials out of argv.** The existing Cloud Run path continues to pass only environment-variable names/config selectors, not bucket secrets or HMAC material.

### Current blockers / unknowns

- The updated bootstrap regressions have not executed in a complete checkout during this run.
- A real GCS + Cloud Logging schema-v4 restart has not been exercised against Google Cloud credentials/resources.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.
- Automatic physical compaction/retention of local JSONL audit history is not yet implemented; anchors make such compaction safe to verify, but StageGuard does not yet perform destructive log compaction itself.

## Single best next step

**Add a credential-free bootstrap acceptance test that uses the default `build_runtime` path with a JSON checkpoint, a deliberately tiny anchor interval, real local JSONL audit events, physical deletion of the authenticated pre-anchor prefix, and a restart proving `audit_integrity=verified` plus no approval/remediation replay. Then add a constructor-only GCS + Cloud Logging wiring test using fakes so the production reader/sink/checkpoint composition is verified without touching Google Cloud.**

## Previous run summary

The previous run added `AnchoredExecutionSafeIncidentService`, combining anchor-aware bounded-suffix restore with the existing execution-safe remediation state machine while intentionally leaving bootstrap on the older service until this integration increment.
