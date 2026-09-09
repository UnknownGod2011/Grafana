# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, anchor-aware + execution-safe default bootstrap composition, non-destructive retention planning, and a local-only two-phase authenticated retention executor.

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
- Audit retention may never advance beyond the authenticated non-genesis anchor.
- Local destructive retention is two-phase: a signed plan binds the exact checkpoint state and exact audit-file digest, and execution revalidates both before mutation.
- Local retention always creates a recoverable owner-only backup before atomic replacement and preserves other incidents plus all post-anchor records.
- Cloud Logging deletion remains intentionally disabled until a provider-specific exhaustive safety contract exists.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Run log — 2026-09-09 — two-phase authenticated local retention executor

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/retention_planner.py`, `runtime/incident_checkpoint.py`, `runtime/incident_service.py`, and `runtime/tests/test_retention_planner.py`. Confirmed the previous handoff accurately identified the strongest safe unblocked gap: StageGuard could calculate an authenticated JSONL compaction boundary but had no explicit execution contract that bound operator intent to an exact checkpoint and exact source file before mutation.

### Exact changes made

1. Added `runtime/retention_executor.py`.
   - Introduces schema `stageguard.audit-retention-plan.v1` and immutable `LocalRetentionPlan` / `RetentionExecutionResult` records.
   - `prepare_local_retention_plan(...)` delegates boundary calculation to the existing read-only planner, requires verified/non-conflicted authenticated anchor state, hashes the exact checkpoint state, hashes the exact JSONL source, records exact eligible/scanned counts and bytes, and emits a SHA-256 + HMAC authenticated plan artifact.
   - Preparation checks file device/inode/size/mtime before and after inventory/hash work and refuses preparation if the file changed mid-plan.
2. Added fresh revalidation before destructive execution.
   - `execute_local_retention(...)` verifies plan schema, SHA-256, HMAC, incident identity, checkpoint-state digest, authenticated anchor sequence/head, audit file digest, and byte length.
   - The rewrite reparses every source record, preserves blank lines, other incidents, and every target-incident record after the authenticated boundary.
   - The rewrite recomputes the complete source digest while streaming and refuses if the candidate set or source bytes differ from the signed plan.
3. Added recoverability and atomic local replacement.
   - The executor writes to an owner-only temporary file in the source directory, fsyncs it, creates an owner-only full backup beside the audit file, fsyncs the backup and directory, then atomically replaces the JSONL path and fsyncs the directory again.
   - A custom backup path must remain beside the audit file and may not already exist or alias the source.
   - Failures before replacement leave the original audit file intact; failures after backup creation retain the recoverable backup.
4. Added an explicit CLI contract.
   - `prepare` writes a new owner-only signed plan artifact and refuses overwrite via `O_EXCL`.
   - `execute` requires that exact plan artifact plus a freshly loaded HMAC-authenticated checkpoint.
   - Signing material is read from an environment variable rather than argv; the only accepted prepare integrity state is `verified`.
   - No Cloud Logging deletion command was added.
5. Added `runtime/tests/test_retention_executor.py`.
   - Covers full two-phase success, exact preservation of post-anchor/other-incident records, exact recoverable backup contents, checkpoint drift refusal, audit-file drift refusal, plan tampering rejection, simulated atomic-replace failure with original preservation and backup recovery, and unverified-plan refusal.
6. Kept repository/CI impact bounded.
   - Prepared implementation, tests, and this handoff in one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- `runtime/retention_executor.py` and `runtime/tests/test_retention_executor.py` passed isolated Python syntax compilation before commit preparation.
- Repository inspection and Git object preparation succeeded through the connected GitHub integration.
- A complete repository test suite still cannot be executed in this automation environment, so no green-suite claim is made.
- No GitHub Actions workflow was manually triggered or rerun.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.
- Cloud Logging retention remains read-only/advisory; this run added destructive capability only for explicit local JSONL execution.

### Decisions made

1. **Bind operator intent to both checkpoint and source bytes.** A valid old plan cannot be reused after lifecycle movement or audit append/mutation.
2. **Require exact-plan execution rather than recalculating at execution time.** The presented HMAC plan is the operator-authorized candidate set; execution may only confirm it or refuse it.
3. **Back up before replace.** Local compaction is allowed to be destructive only after a byte-for-byte recovery copy has been durably written.
4. **Preserve unrelated and post-anchor evidence exactly.** Compaction targets only records for the signed incident at sequences `1..authenticated_anchor`.
5. **Keep provider deletion out of scope.** Cloud Logging inventory remains intentionally incomplete, so it is not eligible for this executor.
6. **Fail closed on drift and malformed input.** Checkpoint drift, file drift, plan tampering, malformed JSON/events, candidate-count mismatch, and backup conflicts all abort before replacing the source.

### Current blockers / unknowns

- The new executor regression suite has not run inside a complete repository checkout during this run.
- The local JSONL path still assumes an operator executes retention while StageGuard writers are quiescent. Exact source hashing detects observed drift before replacement, but there is no cross-process cooperative writer lock yet; adding one would close the remaining tiny append-vs-replace race for local development.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Close the remaining local compaction race by adding a small cross-process cooperative audit-file lock shared by `JsonlAuditLog.append`, JSONL candidate readers, retention planning, and retention execution. The executor should hold an exclusive lock from fresh source validation through backup + atomic replace, writers should take the same lock around append+fsync, and tests should prove an append cannot be lost or interleave with compaction. Keep the mechanism local-only and avoid changing Cloud Logging semantics.**

## Previous run summary

The previous run added the non-destructive authenticated audit-retention planner for exact local JSONL inventory and advisory Cloud Logging inventory, with strict refusal of unverified, conflicted, unbound, or genesis-anchor state.
