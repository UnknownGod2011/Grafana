# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, durable optimistic-concurrency checkpointing, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, authenticated winning-lineage selection, schema-v4 authenticated audit anchors, bounded-suffix restore, anchor-aware + execution-safe default bootstrap composition, HMAC-authenticated local and GCS checkpoint backends, non-destructive retention planning, a two-phase authenticated local retention executor, cooperative local audit-file coordination, cross-process lock coverage, and subprocess acceptance of the supported retention coordinator CLI through restart.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Production remediation uses deterministic idempotency identity and does not automatically replay ambiguous external side effects.
- `dispatching` is durably persisted before provider contact when the checkpoint store supports execution phases.
- Reconciliation is GET-only and ambiguous provider state requires fresh Grafana evidence before recovery completion.
- GCS checkpoints are HMAC-authenticated and generation-CAS protected.
- Local `signed-json` checkpoints are HMAC-authenticated and atomically owner-only persisted for credential-free hardened development/testing.
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

## Run log — 2026-09-09 — signed runtime retention → restart acceptance

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current `main` state and discovered concurrent work after the prior handoff: `runtime/signed_json_checkpoint.py` had added an authenticated atomic local checkpoint store, and `runtime/bootstrap.py` had wired it as the `signed-json` checkpoint backend. Inspected the existing coordinator CLI acceptance and bootstrap execution-safety regressions. Confirmed this new backend removed the prior need to synthesize/sign a checkpoint out-of-band and made the requested full credential-free restart proof practical.

### Exact changes made

1. Extended `runtime/tests/test_retention_coordinator_cli.py` with a full signed-runtime restart acceptance.
   - Boots the real runtime through `build_runtime` using `checkpoint_backend="signed-json"`, JSONL anchored audit, `require_verified`, and a one-event anchor cadence.
   - Drives a real incident through investigation → explicit human approval → successful remediation → Grafana-style recovery verification.
   - Confirms the first remediation adapter is contacted exactly once and the runtime reaches `audit_integrity=verified` with a non-genesis authenticated anchor.
   - Runs the documented `runtime/retention_coordinator.py prepare` and `execute` commands as separate subprocesses against the runtime-created signed checkpoint and audit file; the HMAC key remains environment-only.
   - Requires successful plan preparation/execution and a recovery backup.
   - Restarts through normal `build_runtime` using the same authenticated local checkpoint and compacted audit file.
   - Asserts verified audit integrity, `require_verified` policy retention, synchronized checkpoint state, clear execution reconciliation, recovered lifecycle state, zero remediation calls during restore, and rejection of replaying the already-consumed approval without contacting the replacement remediation adapter.
2. Strengthened the shared test metric fixture with the datasource identity and close contract required by normal bootstrap, and added a counting remediation fake plus deterministic recovery metric sequence.
3. Preserved scope and safety.
   - No production destructive behavior was broadened.
   - No Cloud Logging deletion was introduced.
   - No live Grafana, Gemini, Google Cloud, IAP, Secret Manager, or remediation resources were touched.
   - No GitHub Actions workflow was manually triggered or rerun.

### Tests / checks / results

- The new acceptance is fully credential-free by design and uses only temporary local state, deterministic fakes, the real signed local checkpoint serializer/store, the real coordinator subprocess CLI, and normal runtime bootstrap.
- This tool environment still does not expose an executable repository checkout, so the Python suite could not be run here; no green-suite claim is made.
- The repository write itself succeeded on current `main` after accounting for the concurrent signed-checkpoint commits.

### Decisions made

1. **Use the new `signed-json` runtime backend rather than manually signing fixture state.** This proves the coordinator can consume checkpoint bytes emitted by the normal runtime path and eliminates a test-only trust gap.
2. **Keep `require_verified` through restart.** The acceptance checks the hardened integrity policy remains configured rather than proving restore only under permissive legacy policy.
3. **Measure replay at the adapter boundary.** Restored lifecycle state alone is insufficient; the replacement remediation adapter must remain at zero calls both during startup and after an attempted replay.
4. **Keep retention local-only.** Cloud Logging deletion remains disabled because provider-side exhaustive deletion/retention semantics have not yet been proven to the same standard.

### Current blockers / unknowns

- The new end-to-end acceptance and the complete runtime suite have not executed inside a full checkout during this run.
- Windows `msvcrt.locking` behavior still needs empirical execution on an actual Windows host/runner despite spawn-based cross-platform test design.
- Real Google Cloud acceptance for GCS generation-CAS, Cloud Logging consistency/retention, Cloud Run/IAP, and Secret Manager remains external-resource work.
- Live Grafana MCP acceptance and a real production remediation provider still require operator-owned credentials/resources.

## Single best next step

**Run the focused retention/bootstrap tests and then the full runtime suite in a complete checkout, fix any integration defects immediately, and make the demo/operator path one-command reproducible: start the telemetry simulator + Prometheus/Loki/Grafana stack + official Grafana MCP + StageGuard cockpit, inject a deterministic live-media fault, investigate with Grafana evidence/Gemini briefing, approve remediation, show recovery verification, and emit a concise demo readiness report.**

## Previous run summary

The previous run added subprocess acceptance of the lock-coordinated retention CLI, proving exact-prefix compaction, backup creation, and fail-closed source-drift detection. Concurrent follow-up commits then added and wired the HMAC-authenticated local `signed-json` checkpoint backend, enabling this run's full runtime-created checkpoint → retention → restart replay-safety proof.
