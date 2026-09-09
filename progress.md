# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable optimistic-concurrency checkpointing, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, anchor-aware + execution-safe default bootstrap composition, non-destructive retention planning, a two-phase authenticated local retention executor, and cooperative local audit-file coordination around writers/readers and retention.

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
- Local destructive retention is two-phase: a signed plan binds exact checkpoint state and exact audit-file bytes, then execution revalidates both before mutation.
- Local retention always creates a recoverable owner-only backup before atomic replacement and preserves other incidents plus all post-anchor records.
- Default local anchored JSONL appends and reads share the same cooperative sidecar lock used by coordinated retention, preventing an append from being lost in the validation-to-replace window.
- Cloud Logging deletion remains intentionally disabled until a provider-specific exhaustive safety contract exists.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Run log — 2026-09-09 — cooperative local audit/retention coordination

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_service.py`, `runtime/anchored_incident_service.py`, `runtime/retention_planner.py`, and `runtime/retention_executor.py`. Confirmed the previous handoff accurately identified the remaining local destructive-retention race: the executor revalidated the source digest before replacement, but an `append()` could still occur after that validation and before `os.replace`, allowing a successful concurrent audit append to be lost.

### Exact changes made

1. Added `runtime/audit_file_lock.py`.
   - Introduces one sidecar lock per local audit path (`.<audit-name>.stageguard.lock`).
   - Uses an in-process `threading.RLock` plus an OS-level exclusive lock: `fcntl.flock` on POSIX and one-byte `msvcrt.locking` on Windows.
   - Sidecar files are created with restrictive owner permissions where supported.
   - The mechanism is explicitly local-file only; no Cloud Logging semantics were changed.
2. Integrated locking into the default anchored local JSONL backend.
   - `AnchoredJsonlAuditLog.append()` now holds the cooperative lock through append + fsync.
   - `read()` and anchor-bounded `read_candidates()` take the same lock, so local readers cannot interleave with a retention replacement.
   - The stable base `JsonlAuditLog` remains unchanged; the normal StageGuard bootstrap already selects `AnchoredJsonlAuditLog` for the local anchored path.
3. Added `runtime/retention_coordinator.py` as the safe operator-facing local retention entrypoint.
   - `coordinated_prepare_local_retention_plan(...)` holds the audit lock across the existing complete inventory + source hashing preparation flow.
   - `coordinated_execute_local_retention(...)` parses/authenticates the exact signed plan, derives its audit path, then holds the same lock while the existing executor performs fresh checkpoint validation, source re-hashing, candidate rewrite, backup/fsync, atomic replace, and output hashing.
   - Existing HMAC/checkpoint/file-digest/candidate-count protections are preserved rather than reimplemented.
   - Includes a CLI with the same environment-only signing-key discipline and explicit `prepare` / `execute` phases. Cloud Logging deletion is not exposed.
4. Added `runtime/tests/test_audit_file_lock.py`.
   - Proves an anchored JSONL append blocks while the audit lock is held and completes afterward without loss.
   - Proves anchored candidate reads coordinate on the same lock.
   - Proves the coordinated execute wrapper holds the lock around the entire underlying executor call and blocks a concurrent append until execution leaves the critical section.
   - Proves plan preparation similarly excludes concurrent writers for the full preparation call.
5. Kept repository/CI impact bounded.
   - Apart from the initial lock-file commit, integrated source/tests/progress as one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- New locking and coordination code was reviewed for import/syntax consistency against the existing runtime modules before commit preparation.
- Focused regression coverage was added for the writer/read/retention coordination contract.
- A complete repository checkout/test runner is still unavailable in this automation environment, so no green-suite claim is made.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.
- Cloud Logging retention remains read-only/advisory.

### Decisions made

1. **Coordinate the concrete default local backend instead of rewriting the stable incident-service core.** Bootstrap already uses `AnchoredJsonlAuditLog`, so the production-like local path gains locking without broad unrelated changes.
2. **Use one lock identity for readers, writers, and destructive retention.** A successful append can no longer occur inside the signed-plan execution validation-to-replace window.
3. **Wrap the proven executor rather than duplicate it.** The coordinator supplies serialization only; HMAC authentication, checkpoint drift checks, source digests, exact candidate checks, backup/fsync, and atomic replacement remain single-sourced in `retention_executor.py`.
4. **Keep locking local-only.** Provider-backed audit stores need provider-specific consistency contracts, not a filesystem lock abstraction.
5. **Prefer fail-closed serialization over lock timeouts.** Local retention is an explicit operator action; silently proceeding because a lock timed out would be less safe than waiting for the cooperating writer/reader critical section to finish.

### Current blockers / unknowns

- The new lock regressions have not run inside a complete repository checkout during this run.
- The cooperative lock protects StageGuard components that use the shared lock. External processes that directly write the JSONL file without using StageGuard's lock remain outside the contract; source-digest checks still detect many such changes, but external non-cooperating writers must be considered unsupported during compaction.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Make the coordinated retention path the only documented/local CLI path and add a real subprocess acceptance test (POSIX plus a Windows-compatible branch) that holds the sidecar lock in one process while a second process attempts `AnchoredJsonlAuditLog.append()`, proving cross-process exclusion rather than only thread-level exclusion. Then run the full runtime suite in a complete checkout and fix any integration defects before expanding retention functionality.**

## Previous run summary

The previous run added `runtime/retention_executor.py`, providing signed two-phase local JSONL retention plans, fresh checkpoint/source revalidation, exact candidate-set checking, owner-only recoverable backup, fsync, and atomic replacement while leaving Cloud Logging deletion disabled.
