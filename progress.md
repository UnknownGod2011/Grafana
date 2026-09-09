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
- Audit retention planning is read-only and may never propose a boundary beyond the authenticated non-genesis anchor.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Run log — 2026-09-09 — non-destructive authenticated audit-retention planner

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_checkpoint.py`, `runtime/audit_anchor.py`, `runtime/durable_audit_reader.py`, `runtime/anchored_incident_service.py`, `runtime/incident_service.py`, and the recent schema-v4/fake-cloud tests. Confirmed the previous handoff accurately identified the strongest remaining safe gap: StageGuard had authenticated compaction boundaries but no operator-safe tool for calculating what is eligible for retention removal.

### Exact changes made

1. Added `runtime/retention_planner.py`.
   - Introduces immutable `AuditRetentionPlan` output with incident/backend identity, safe/refused status, refusal reason, authenticated boundary/head, current chain sequence, eligible record/byte counts, scanned totals, and enumeration completeness.
   - `plan_authenticated_boundary(...)` refuses anything except `audit_integrity_state="verified"`, rejects checkpoint conflict, unbound checkpoints, missing anchors, genesis anchors, anchors beyond the authenticated head, and impossible chain/lifecycle ordering.
   - The only safe boundary emitted is `audit_anchor_sequence`; no function can advance it based on observed log contents.
2. Added exact local JSONL inventory.
   - `plan_jsonl_retention(...)` scans read-only, counts only records for the target incident at or before the authenticated anchor, reports exact line bytes eligible for removal, preserves same-sequence loser residue in the count, and never rewrites/truncates/unlinks the source.
   - Scans are bounded by configurable byte and record ceilings and fail closed on malformed JSON/events, invalid sequences, filesystem errors, or bound exhaustion.
3. Added Cloud Logging advisory inventory.
   - `plan_cloud_logging_retention(...)` calls only the branch-aware candidate reader through the authenticated anchor and never requests records above it.
   - Because Cloud Logging lookback/retention can make enumeration incomplete, the plan explicitly reports `enumeration_complete=false` and does not invent a byte count.
   - Provider/read errors become refusal plans rather than partial deletion authority.
4. Added a strict JSONL CLI.
   - Requires an HMAC-signed checkpoint document and a signing key of at least 32 bytes supplied through an environment variable.
   - Emits one machine-readable JSON plan and exits non-zero for a refused plan.
   - Performs no deletion and exposes no secret material in output.
5. Added `runtime/tests/test_retention_planner.py`.
   - Covers refusal of unverified, conflicted, unbound, and genesis-anchor state.
   - Proves exact JSONL record/byte accounting and byte-for-byte non-modification of the source.
   - Proves post-anchor records are never counted.
   - Proves Cloud Logging inventory requests `after_sequence=0` and `through_sequence=<authenticated anchor>` only, remains explicitly incomplete, and is not called at all when trust prerequisites fail.
6. Kept repository/CI impact bounded.
   - Prepared source, tests, and this handoff as one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- The new planner and test source both passed Python syntax compilation in isolated validation.
- Repository inspection and Git object preparation succeeded through the connected GitHub integration.
- A complete repository test suite still cannot be executed in this automation environment, so no green-suite claim is made.
- No GitHub Actions workflow was manually triggered or rerun.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.
- The retention implementation is deliberately non-destructive; it does not delete local files or provider log entries.

### Decisions made

1. **Separate deletion authority from inventory.** The planner can identify an authenticated boundary and observed/exact candidates, but it never performs retention mutation.
2. **Treat runtime `verified` plus non-conflicted schema-v4 anchor state as mandatory.** Merely seeing an anchor-shaped value is insufficient.
3. **Make JSONL exact but Cloud Logging advisory.** Local bytes can be counted deterministically; provider retention/lookback means Cloud Logging enumeration must not claim completeness without a separate exhaustive provider contract.
4. **Refuse genesis anchors.** Sequence zero is cryptographically valid but has no compactable history and should not produce a misleading “safe” plan.
5. **Bound inventory work.** Retention planning itself must not become an unbounded memory/IO path.

### Current blockers / unknowns

- The new planner tests have not run inside a complete repository checkout during this run.
- There is intentionally no destructive retention executor yet; any future executor must require an explicit operator action and revalidate the authenticated checkpoint immediately before mutation.
- Cloud Logging does not yet have a provider-specific exhaustive/delete adapter; current inventory is advisory by design.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Add an explicit two-phase retention execution contract for local JSONL only: generate a signed/hashed plan artifact, then require the operator to present that exact plan plus a freshly revalidated checkpoint before atomically rewriting the file. Keep deletion disabled by default, preserve all post-anchor and other-incident records, refuse stale plans/checkpoint drift, create a recoverable backup, and add crash/failure tests. Do not add Cloud Logging deletion until an equally strong provider-specific safety contract exists.**

## Previous run summary

The previous run added a credential-free fake-cloud end-to-end restart acceptance path using the real StageGuard GCS and Cloud Logging adapters over in-memory provider primitives, proving authenticated winner restore and zero remediation replay.
