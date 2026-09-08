# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, hardened audit-integrity readiness policy, and authenticated winning-lineage selection for multi-writer append-before-CAS audit streams.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Production remediation uses deterministic idempotency identity and does not automatically replay ambiguous external side effects.
- `dispatching` is durably persisted before provider contact when the checkpoint store supports execution phases.
- Reconciliation is GET-only and ambiguous provider state requires fresh Grafana evidence before recovery completion.
- GCS checkpoints are HMAC-authenticated and generation-CAS protected.
- Audit chain state is domain-separated SHA-256 with contiguous sequence numbers.
- The authenticated checkpoint chain head is lifecycle authority; losing-writer audit residue cannot manufacture approval, outcome, recovery, or operator timeline state.
- Branched lineage selection and durable candidate reads are explicitly bounded and fail closed on candidate/state explosion or silent truncation.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Completed milestones

- Deterministic media telemetry simulator and local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and evidence-scope validation.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded outcomes/reasons.
- Revision-bound Gemini incident commander briefing layer.
- Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, CAS conflict handling, operator cockpit, crash/SIGKILL ambiguity coverage, tamper-evident audit chain, schema-v3 binding, integrity observability/policy, legacy-v2 to verified-v3 migration acceptance, and authenticated winning-lineage runtime restore.
- Authenticated audit-anchor foundation and Cloud Logging post-anchor candidate-range reads.

## Run log — 2026-09-09 — authenticated audit-anchor foundation

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/audit_integrity.py`, `runtime/incident_service.py`, `runtime/incident_checkpoint.py`, `runtime/durable_audit_reader.py`, `runtime/tests/test_runtime_audit_checkpoint_binding.py`, and `runtime/tests/test_durable_audit_reader.py`. Confirmed the highest-priority production limitation: verified restart still requires audit candidates from sequence 1 through the authenticated head, so a long-lived/high-churn incident can fail closed solely because Cloud Logging lookback or the 4096-candidate safety cap no longer contains the full historical prefix.

### Exact changes made

1. Added `runtime/audit_anchor.py`.
   - Defines `AuditAnchor` as a validated audit-chain checkpoint eligible for authenticated durable persistence.
   - Adds `roll_audit_anchor(...)`, which only promotes from an already trusted anchor to a monotonic verified current chain checkpoint after a configurable interval (default 1024 committed events).
   - Adds `select_anchored_committed_lineage(...)`, which verifies/selects only `(anchor.sequence, expected.sequence]` using the existing bounded winning-lineage algorithm.
   - Enforces a default maximum verification suffix of 2048 sequence positions and preserves the existing candidate/state fan-out bounds.
   - Makes the compaction boundary explicit: records at or before an authenticated anchor are not required for suffix integrity verification.
2. Extended `GoogleCloudAuditReader.read_candidates(...)` with an optional exclusive `after_sequence` lower bound.
   - Existing callers retain sequence-1 prefix behavior by default.
   - Anchor-aware callers can now issue Cloud Logging queries constrained to `sequence > anchor` and `sequence <= authenticated_head`.
   - Empty ranges return without querying; invalid/inverted ranges fail closed.
   - Same-sequence post-anchor competitors are still preserved for authenticated lineage selection, and the 4096-result sentinel behavior remains unchanged.
3. Added credential-free regression coverage.
   - `runtime/tests/test_audit_anchor.py` covers compacted-prefix independence, post-anchor competing writers, mutation/deletion detection, anchor substitution failure, suffix bounds, monotonic roll behavior, and exact empty-suffix matching.
   - `runtime/tests/test_anchored_cloud_audit_reader.py` covers the exclusive lower-bound filter, post-anchor competitor preservation, rejection of at/before-anchor results, and empty/inverted range handling.
4. Added `docs/audit-anchors.md` documenting the trust model, safe roll procedure, compaction semantics, bounds, and remaining checkpoint/runtime integration.
5. Research check: reviewed current official Google Cloud Logging documentation. The official guidance continues to recommend constraining queries with log name and narrow time ranges; StageGuard already does both and the anchor reader now additionally constrains the structured audit sequence range. Source reviewed on 2026-09-09: Google Cloud Logging query-language/troubleshooting documentation (last updated 2026-08-31 UTC).

### Tests / checks / results

- Repository reads and Git object writes succeeded through the connected GitHub integration.
- A fresh local clone was attempted before implementation and still failed before Python started because the execution container could not resolve `github.com`; therefore no local Python green result is claimed for this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **An anchor is not a new trust root.** It becomes trusted only after being included in the same authenticated durable checkpoint envelope that protects lifecycle state.
2. **The current authenticated chain head remains the commit marker.** The anchor only bounds how much history is required to reproduce that head.
3. **Compaction is allowed only at or before an authenticated anchor.** Post-anchor deletion/mutation remains fail-closed.
4. **Anchor promotion must be monotonic and derived from verified chain state.** Browser state, provider responses, raw Cloud Logging entries, or losing-writer appends can never create an anchor.
5. **Query bounds belong in the provider read itself.** Fetching the full prefix and filtering locally would not solve Cloud Logging lookback/result-limit availability risk.
6. **Backward compatibility is preserved.** Existing `read_candidates` callers omit `after_sequence` and behave as before until checkpoint schema/runtime wiring is complete.

### Current blockers / unknowns

- `IncidentCheckpoint` schema v3 does not yet persist an anchor, so production restart still starts verification from genesis. The new anchor primitive and ranged reader are not lifecycle authority until schema/runtime integration lands.
- `JsonlAuditLog.read_candidates` does not yet expose an anchor lower bound; local acceptance should be updated when runtime wiring is added.
- The execution container still cannot resolve `github.com`, so the new Python tests have not executed in a complete local checkout during this run.
- Cloud Logging candidate behavior is fake-logger tested only; real project pagination/filter/IAM acceptance remains an external-resource validation task.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Wire anchors into authenticated durable checkpoint state and runtime restore. Add a backward-compatible checkpoint schema that carries `audit_anchor_sequence` + `audit_anchor_head_sha256`, roll the anchor only after verified committed progress, make `IncidentService` request candidates with `after_sequence=anchor.sequence`, add the same ranged contract to `JsonlAuditLog`, and prove restart after deleting/aging all pre-anchor records remains `verified` while anchor substitution, committed post-anchor mutation, and stale approval/remediation branches still fail closed or remain unauthoritative.**

## Previous run summary

The previous run integrated authenticated winning-lineage selection into runtime restore and Cloud Logging candidate enumeration so benign same-sequence/post-head append-before-CAS residue no longer poisons a valid schema-v3 winner.
