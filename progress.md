# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable optimistic-concurrency checkpointing, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, anchor-aware + execution-safe default bootstrap composition, non-destructive retention planning, a two-phase authenticated local retention executor, cooperative local audit-file coordination, and cross-process lock acceptance coverage.

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
- The supported operator-facing destructive-retention entrypoint is `runtime/retention_coordinator.py`; direct use of the lower-level executor is not part of the supported operational contract.
- Cloud Logging deletion remains intentionally disabled until a provider-specific exhaustive safety contract exists.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Run log — 2026-09-09 — cross-process retention-lock acceptance and operator contract

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, recent commits, `runtime/audit_file_lock.py`, `runtime/tests/test_audit_file_lock.py`, `runtime/retention_coordinator.py`, and `README.md`. Confirmed the previous handoff accurately identified two remaining local-retention gaps: existing regressions proved thread coordination but not independent-process exclusion, and the safe coordinated CLI was not yet documented as the sole supported operator path.

### Exact changes made

1. Added `runtime/tests/test_audit_file_lock_subprocess.py`.
   - Uses Python's `spawn` multiprocessing context so the lock holder and writer are genuinely independent child processes on both POSIX and Windows rather than fork-inheriting parent state.
   - One child acquires StageGuard's sidecar audit lock and signals readiness; a second child constructs `AnchoredJsonlAuditLog` and attempts a real append.
   - The regression asserts the writer starts but cannot complete while the first process holds the lock, then completes after release with exit code 0 and a readable persisted audit event.
   - Cleanup terminates lingering children on assertion failure to avoid hanging the suite.
2. Added `AUDIT_RETENTION.md`.
   - Documents the authenticated two-phase local retention safety contract, plan/checkpoint/source binding, backup + atomic replacement behavior, concurrency boundary, fail-closed conditions, and recovery guidance.
   - Declares `runtime/retention_coordinator.py` as the only supported operator-facing destructive-retention entrypoint.
   - Explicitly states that `runtime/retention_executor.py` is a lower-level implementation module whose direct invocation bypasses cooperative coordination and is therefore not an operator CLI contract.
   - Documents environment-only HMAC key handling and concrete `prepare` / `execute` commands without exposing secrets.
   - Keeps Cloud Logging deletion disabled/read-only and calls out non-cooperating external JSONL writers as outside the lock contract.
3. Kept repository/CI impact bounded.
   - Prepared the test, operator documentation, and progress handoff as one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- The new subprocess regression source passed isolated Python syntax compilation before Git object preparation.
- The test deliberately uses `multiprocessing.get_context("spawn")`, providing a Windows-compatible branch while also avoiding POSIX fork semantics that could make the acceptance less representative of independent processes.
- Repository-side full test execution is still unavailable in this automation environment, so no green-suite claim is made.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.
- No Cloud Logging destructive capability was added.

### Decisions made

1. **Use `spawn` for the acceptance test.** It exercises independent interpreter processes consistently across platforms and avoids accidentally proving only fork-inherited behavior.
2. **Test the real anchored writer, not only the lock helper.** The writer child executes `AnchoredJsonlAuditLog.append()`, so the regression covers the production-like local append integration.
3. **Keep retention coordination single-sourced.** Documentation points operators to the coordinator rather than adding another wrapper or duplicating executor logic.
4. **Do not broaden destructive scope.** This run improves proof and operability of local JSONL retention only; Cloud Logging remains read-only/advisory.
5. **Treat non-cooperating writers as unsupported during compaction.** StageGuard can serialize its own components, but cannot safely promise coordination with arbitrary processes that ignore the sidecar lock.

### Current blockers / unknowns

- The new subprocess acceptance and existing runtime suite have not run inside a complete checkout during this run.
- Windows `msvcrt.locking` behavior is covered by the cross-platform spawn test design but still needs execution on an actual Windows runner/host for empirical confirmation.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Run the full runtime suite in a complete checkout on Linux and Windows, fix any integration defects from the new subprocess regression, then add a credential-free retention/restart acceptance that executes the documented coordinator CLI as a subprocess end-to-end: prepare signed plan → execute compaction → restart through normal `build_runtime` → prove `audit_integrity=verified`, readiness remains hardened, and no consumed remediation approval is replayed.**

## Previous run summary

The previous run added cooperative sidecar locking shared by `AnchoredJsonlAuditLog` readers/writers and the retention coordinator, closing the in-process append-vs-compaction validation/replacement race for cooperating StageGuard components.
