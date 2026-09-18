# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, fake-cloud durability/restart behavior, fake execution/reconciliation CAS concurrency, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate. Execution-safety and Cloud Run metrics-bridge ownership are exact-filename based so newly added tests cannot silently enter dependency-light validation.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — Cloud Run metrics-bridge validation ownership

### Inspected at start

Read `progress.md` completely first and inspected the repository tree, consolidated validation runner, existing cloud-runtime-metrics validation contract, and the five previously unowned metrics-bridge hardening suites: audience boundary, timeout/token bounds, inbound bridge authentication, redirect refusal, and sentinel-family validation. The repository inventory confirms these are distinct tests alongside the already-owned bridge and mocked acceptance contracts.

### Changes / actions

- Added `test_cloud_run_metrics_bridge_audience_boundary.py`, `test_cloud_run_metrics_bridge_bounds.py`, `test_cloud_run_metrics_bridge_inbound_auth.py`, `test_cloud_run_metrics_bridge_redirects.py`, and `test_cloud_run_metrics_bridge_sentinel_family.py` to the existing `cloud runtime metrics bridge` production-validation gate.
- Kept the gate exact-filename based; no `test_cloud_run_metrics*.py` wildcard was introduced, so a future credentialed/live test cannot silently enter the dependency-light validator.
- Strengthened `test_validation_cloud_runtime_metrics.py` to pin the complete seven-file audited set, require wildcard-free patterns, and preserve ordering before runtime observability.
- Reviewed the hardening contracts: audience tests use injected token suppliers/openers; bounds/auth tests use local loopback servers and mocks; redirect tests use loopback HTTP servers only; sentinel tests are pure payload validation. None require Google credentials, Cloud Run, Grafana, Docker, or a live remediation target.
- No credentials, Google Cloud resources, Grafana instances, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Repository/test inventory confirmed all five hardening modules exist and were previously outside the exact two-file cloud metrics gate.
- Metrics validation gate update committed as `652d82c070e8c8119645befc886ac152fc61a49c`.
- Ownership regression update committed as `4fa4292be027803800fd93e656f072269677d574`.
- The connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Security-sensitive Cloud Run bridge tests are safe for dependency-light validation only after explicit inspection; filename similarity is not sufficient classification.
2. Keep credentialed/live Cloud Run acceptance outside this gate unless it is separately audited and intentionally owned.
3. Preserve local loopback HTTP tests because they exercise real request/auth/redirect behavior without external network or cloud dependencies.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned tests need classification, notably `test_simulator.py` and live Gemini acceptance.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify and explicitly own the deterministic telemetry simulator contract (`test_simulator.py`) in production validation, then audit the remaining unowned set so `--require-full-coverage` can become a meaningful local release criterion without admitting credentialed/live acceptance tests.
