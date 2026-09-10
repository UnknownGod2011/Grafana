# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — HTTP concurrency coverage for live remediation

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current HTTP/runtime concurrency path and the prior nonblocking production remediation implementation:
- `runtime/api.py`
- `runtime/tests/test_api.py`
- `runtime/tests/test_anchored_execution_safety.py`
- `runtime/anchored_execution_safety.py`
- `runtime/incident_service.py`
- `runtime/readiness.py`

Confirmed the HTTP server is `ThreadingHTTPServer`, `/v1/execute` remains intentionally synchronous per request, and production remediation now releases the lifecycle lock while the provider call and Grafana recovery polling are active. Confirmed status/readiness/metrics obtain lifecycle state through lock-protected service reads and therefore should remain responsive with the narrowed lock scope.

### Exact changes made

Added `runtime/tests/test_api_concurrency.py`, a credential-free end-to-end HTTP concurrency regression that exercises the real StageGuard HTTP server with `AnchoredExecutionSafeIncidentService` and a deterministic blocking remediation adapter.

The test now proves the following contract while the first authenticated `POST /v1/execute` is held inside the provider call:
1. Authenticated `GET /v1/incident` returns promptly and still exposes the approved evidence revision with no fabricated remediation outcome.
2. Unauthenticated `GET /readyz` returns promptly and reports `remediation_execution_phase=dispatching` even when readiness itself is 503 because the test intentionally has no live Grafana activation configuration.
3. Unauthenticated `GET /metrics` returns promptly and exports `stageguard_remediation_execution_phase{phase="dispatching"} 1`.
4. A competing authenticated `POST /v1/investigate` fails immediately with HTTP 409 rather than queuing behind the provider call.
5. A competing authenticated `POST /v1/execute` also fails immediately with HTTP 409.
6. The remediation fake call count remains exactly one, proving concurrent HTTP execution cannot replay the external side effect.
7. After the provider is released, the original execute request completes with a telemetry-verified `recovered` outcome and execution phase becomes `resolved`.

The harness uses only localhost sockets, temporary files, deterministic metric fixtures, and `threading.Event`; it requires no Grafana, Gemini, GCP, Secret Manager, IAM, or remediation credentials.

Commit:
- `b8cda0ff34494bfddce684be94ae859f37637039` — test HTTP visibility during remediation execution

### Tests / checks / results

Validation available in this run:
- Re-fetched and reviewed the committed `runtime/tests/test_api_concurrency.py` after the write.
- Cross-checked the assertions against `runtime/api.py`, including `/v1/incident`, `/readyz`, `/metrics`, HTTP 409 handling for `RuntimeError`, and `ThreadingHTTPServer` construction.
- Cross-checked the blocking fixture against `AnchoredExecutionSafeIncidentService.execute_approved()`: the service persists the dispatch barrier, sets `_execution_in_flight`, releases `_lock`, performs remediation/recovery I/O, and later reacquires the lock to promote the outcome.
- Confirmed `IncidentService.investigate()` and `approve()` use `_require_checkpoint_consistency()`, so the in-flight guard is the correct mutation gate for the production composition.

The exact committed unittest module still could not be executed from a local repository checkout in this automation environment. No GitHub Actions workflow was created, triggered, or rerun merely to obtain this signal, so no full-suite green claim is made.

No external Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Added a separate HTTP concurrency module instead of bloating the basic API unit-test class; the new test is specifically a production-composition/concurrency contract.
2. Used real localhost HTTP connections and the real `ThreadingHTTPServer` rather than invoking handlers directly, because worker-level concurrency is the behavior that matters in production.
3. Kept the original execute request synchronous. The test validates that other HTTP workers remain usable without introducing an async job API or changing public semantics.
4. Allowed `/readyz` to be either 200 or 503 in this credential-free harness and asserted the stronger property: it must return promptly and expose bounded `dispatching` state. Production evidence-plane readiness remains independently fail closed.
5. Used bounded 0.75-second responsiveness assertions with a 3-second blocking provider window; this is deliberately generous enough for CI scheduling noise while still detecting accidental lock serialization.

### Current blockers / unknowns

- `runtime.tests.test_api_concurrency` and `runtime.tests.test_anchored_execution_safety` still need execution from a runnable checkout to validate the complete import graph and timing assertions.
- The focused production runtime/API/readiness suite should be rerun once repository execution is available because the previous runtime change intentionally altered lock timing.
- The historical full suite still needs systematic triage after repository execution is available.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- `/v1/execute` still occupies one HTTP worker for the full provider + recovery-verification duration. The new regression protects parallel operator visibility, but high-concurrency production capacity has not yet been load-tested.

## Single best next step

**Move to operator/runtime resilience: add bounded execution-duration observability without exposing provider details. Export fixed-cardinality metrics for active remediation execution and elapsed execution age, plus a readiness warning/fail-closed threshold for an execution that exceeds its configured maximum recovery window. Cover the behavior with deterministic clock-driven tests so a wedged provider cannot remain silently `dispatching` forever.**

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
- Production remediation releases the lifecycle lock across provider contact and Grafana recovery polling while blocking competing mutations with an explicit in-flight guard.
- HTTP concurrency coverage now protects incident/readiness/metrics visibility and single-dispatch semantics while remediation is active.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
