# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — nonblocking production remediation execution

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the repository tree and deliberately moved away from repeated Google Cloud deployment-doctor hardening because the previous handoff recommended shifting to another unblocked production area if direct checkout execution remained unavailable.

Inspected the runtime path most relevant to live incident operation:
- `runtime/incident_service.py`
- `runtime/execution_safety.py`
- `runtime/anchored_execution_safety.py`
- `runtime/remediation.py`
- `runtime/api.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_execution_safety.py`
- `runtime/tests/test_anchored_execution_safety.py`

Confirmed `runtime/bootstrap.py` composes production with `AnchoredExecutionSafeIncidentService`.

Found a concrete operator-availability issue: the inherited `ExecutionSafeIncidentService.execute_approved()` held the service-wide re-entrant lifecycle lock while the remediation provider was contacted and while bounded Grafana recovery samples were collected. In production that external path can take seconds or longer. Because status, checkpoint, audit-integrity, execution-phase, readiness, and metrics views also acquire the same service lock, an operator could temporarily lose useful live visibility at exactly the point a remediation was being dispatched and verified.

### Exact changes made

1. Hardened the production-oriented `AnchoredExecutionSafeIncidentService` with a narrow-lock execution path.
   - Added `_execution_in_flight`, initialized before cooperative parent construction.
   - Persists the existing dispatch barrier while the lifecycle lock is held and before provider contact.
   - Marks the execution in flight, then releases the lifecycle lock before `remediate_and_verify()` contacts the remediation adapter and polls Grafana/Prometheus recovery telemetry.
   - Reacquires the lock before promoting the `RemediationOutcome`, appending the audit event, and saving the authenticated checkpoint.
   - Revalidates incident id, evidence revision, approval, and absence of an existing outcome before committing the result.

2. Kept competing lifecycle mutations fail-closed while external execution is active.
   - Overrode `_require_checkpoint_consistency()` so any mutation using the established consistency gate receives `remediation execution is already in progress; lifecycle changes are blocked` while `_execution_in_flight` is true.
   - A second `execute_approved()` therefore cannot replay the remote action.
   - Investigation, approval, briefing/reconciliation paths that use the same gate remain blocked until the active execution completes.

3. Preserved execution-uncertainty semantics.
   - Added a small `_mark_execution_uncertain()` helper that preserves the parent state machine fields and reason taxonomy.
   - Provider/recovery exceptions still move the lifecycle into an execution-uncertain fail-closed state rather than permitting a blind replay.
   - A post-action checkpoint CAS conflict still records `reload_required` semantics; generic post-contact failures retain the existing reloaded/uncertain behavior.
   - The existing durable `dispatching` checkpoint barrier remains authoritative for production adapters that require provider reconciliation.

4. Improved operator observability during the active wait.
   - `execution_checkpoint_phase()` now returns the existing fixed-cardinality `dispatching` phase while provider/recovery work is in flight.
   - The remote action and recovery polling no longer occupy `_lock`, so status/checkpoint/readiness/metrics reads can acquire it and report current state.
   - No provider detail, arbitrary operation text, target, query, or secret was added to the observability surface.

5. Expanded `runtime/tests/test_anchored_execution_safety.py` with a deterministic concurrency regression.
   - Added a `BlockingRemediation` fake controlled by `threading.Event` so the provider call can be held open without network access or sleeps.
   - While execution is blocked inside the fake provider, a separate operator-reader thread must obtain status, execution phase, and checkpoint state within a bounded interval.
   - The test asserts phase=`dispatching`, preserves the approved revision, and confirms checkpoint visibility remains available.
   - Concurrent `investigate()` and a second `execute_approved()` must fail with the in-progress guard.
   - The fake remediation call count must remain exactly one, proving the concurrent execute attempt cannot duplicate the side effect.
   - After the fake provider is released, normal Grafana recovery fixtures complete and the outcome must become `recovered` with execution phase=`resolved`.

Commits:
- `df6bccb7e12f9d30f738e459a6fbacd171f0a478` — keep operator reads responsive during remediation
- `9458cdcf7b3e262763fe9347e218aee4f53df00b` — test responsive reads during remediation

### Tests / checks / results

Validation available in this run:
- Re-fetched and reviewed the committed `runtime/anchored_execution_safety.py` after the write.
- Re-fetched and reviewed the committed concurrency regression after the write.
- Verified from repository source that the production bootstrap imports and composes `AnchoredExecutionSafeIncidentService`.
- The regression is credential-free and uses only local temporary files, deterministic metric values, and thread events; it creates no network/cloud side effects.

The exact committed unittest module still could not be executed from a fresh local repository checkout in this automation environment. No GitHub Actions workflow was created, triggered, or rerun merely to obtain this signal, so no full-suite green claim is made.

No external Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Fixed the concurrency boundary only in `AnchoredExecutionSafeIncidentService`, which is the production bootstrap composition, rather than changing the stable base `IncidentService` or legacy execution-safe service and increasing regression scope unnecessarily.
2. External provider and Grafana recovery I/O is the only work moved outside the lifecycle lock. Dispatch barriers, state promotion, audit append, authenticated anchor advancement, and checkpoint CAS remain serialized under `_lock`.
3. Reused the existing `dispatching` execution phase instead of creating a new public state/schema solely for in-process execution.
4. Competing mutations fail closed rather than queueing behind a potentially slow provider call. Operators receive an immediate bounded state error and can continue reading status/readiness/metrics.
5. No async job queue or background executor was introduced; the HTTP execute request keeps its existing synchronous completion semantics, minimizing API compatibility risk while making other ThreadingHTTPServer requests responsive.

### Current blockers / unknowns

- `runtime.tests.test_anchored_execution_safety` must be executed from a runnable checkout to validate the new concurrency regression against the complete import graph.
- The focused production runtime/API suite should be rerun once repository execution is available because this change intentionally alters lock timing.
- The historical full suite still needs systematic triage after repository execution is available.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- The synchronous `/v1/execute` request can still occupy one HTTP worker until recovery verification completes; other requests are now intended to remain responsive, but a future production load pass should determine whether an explicit operation-status resource is justified.

## Single best next step

**Run `runtime.tests.test_anchored_execution_safety` plus the focused execution-safety/API/readiness tests from a runnable checkout. If those pass, add an API-level concurrency regression using `ThreadingHTTPServer`: hold `/v1/execute` inside a blocking remediation fake and prove authenticated `/v1/incident`, `/readyz`, and `/metrics` remain responsive and expose the bounded `dispatching` state while all competing mutation endpoints fail closed.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Google Cloud project/region/service/image identifier grammar is centralized and shared by the deploy helper and deployment doctor.
- Live deployment preflight verifies the configured Cloud Run region against the current provider-reported region catalog.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment doctor validates required APIs, secrets/access, Cloud Logging permissions, checkpoint storage permissions, conditional Vertex prediction permission, image availability, live Cloud Run region availability, and deployment serialization boundaries; offline validation can never report deploy-ready.
- Deployment-doctor gcloud timeouts, OS invocation failures, and decode failures fail closed through sanitized nonzero results and retain probe-specific operational diagnostics.
- Production remediation now releases the lifecycle lock across provider contact and Grafana recovery polling while blocking competing mutations with an explicit in-flight guard.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
