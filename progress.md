# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable optimistic-concurrency checkpointing, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, anchor-aware + execution-safe default bootstrap composition, non-destructive retention planning, a two-phase authenticated local retention executor, cooperative local audit-file coordination, cross-process lock acceptance coverage, and subprocess acceptance of the supported retention coordinator CLI.

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

## Run log — 2026-09-09 — retention coordinator CLI subprocess acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/retention_coordinator.py`, `runtime/retention_planner.py`, `runtime/incident_checkpoint.py`, and the existing retention/locking regressions. Confirmed the highest-value unblocked gap was at the actual documented operator boundary: lower-level executor and lock behavior had coverage, but the supported coordinator CLI itself had not been exercised end-to-end through independent subprocesses.

### Exact changes made

1. Added `runtime/tests/test_retention_coordinator_cli.py`.
   - Builds a real StageGuard incident checkpoint via `IncidentService`, upgrades it to a schema-v4 authenticated anchor, and writes an HMAC-signed checkpoint document using the production checkpoint serializer.
   - Invokes `runtime/retention_coordinator.py prepare` in a subprocess with the signing key supplied only through `STAGEGUARD_CHECKPOINT_HMAC_KEY`.
   - Invokes the documented `execute` phase in a second subprocess against the exact generated signed plan.
   - Verifies the authenticated incident prefix is removed, all post-anchor records and other-incident records are preserved byte-for-byte, and the explicit recovery backup contains the complete original audit file with owner-only permissions.
   - Adds a fail-closed subprocess case where the audit file changes after plan preparation; execution must return non-zero, report source drift, leave the drifted source untouched, and create no backup.
2. Kept implementation surface small.
   - No production retention code changed because the operator contract already existed; this run adds executable acceptance at that boundary rather than duplicating logic.
   - No Cloud Logging deletion or broader destructive capability was introduced.
3. Kept repository/CI impact bounded.
   - Prepared the new regression and this progress handoff in one Git tree/commit/ref update.
   - Did not manually trigger or rerun GitHub Actions.

### Tests / checks / results

- The new test source passed isolated Python syntax compilation before commit preparation.
- The acceptance is credential-free and uses only temporary local files, a deterministic fake remediation adapter, and subprocess invocation of the actual coordinator script.
- The full repository/runtime suite still cannot be executed inside this automation environment, so no green-suite claim is made.
- No live Grafana, Gemini, GCS, Cloud Logging, Cloud Run, IAP, Secret Manager, remediation endpoint, or operator resource was touched.

### Decisions made

1. **Test the documented CLI rather than another internal helper.** The goal is to prove the exact operator path named in `AUDIT_RETENTION.md` composes checkpoint authentication, signed planning, coordination, compaction, and recovery backup correctly.
2. **Keep the signing key environment-only.** The subprocess regression mirrors the intended secret-handling contract and never places key material in argv.
3. **Include a stale-plan/source-drift negative path.** A destructive operator workflow needs explicit proof that a signed plan cannot be replayed after the source changes.
4. **Avoid unrelated production edits.** Existing coordinator/executor behavior was structurally sufficient; adding acceptance coverage delivered more value than refactoring stable code.

### Current blockers / unknowns

- The new CLI acceptance and existing runtime suite have not run inside a complete checkout during this run.
- Windows `msvcrt.locking` behavior still needs empirical execution on an actual Windows host/runner despite spawn-based cross-platform test design.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Extend the CLI acceptance into a full credential-free restart proof: create a real anchored/execution-safe runtime state with a consumed approval, run the documented coordinator prepare/execute subprocesses, restart through normal `build_runtime`, and assert `audit_integrity=verified`, hardened readiness, clear reconciliation, and zero remediation replay. Then run the focused and full runtime suites in a complete Linux/Windows checkout and fix any integration defects found.**

## Previous run summary

The previous run added spawn-based cross-process lock acceptance and `AUDIT_RETENTION.md`, establishing `runtime/retention_coordinator.py` as the sole supported operator-facing destructive local retention path.
