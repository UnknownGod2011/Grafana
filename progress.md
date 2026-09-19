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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at configuration/runtime boundaries, construction-frozen execution and reconciliation capabilities, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration. Provider descriptor faults fail closed.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-20 — validation temporary-directory isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_home_isolation.py`. The runner already isolated credential/configuration homes and many startup/injection channels, but still inherited host `TMPDIR`, `TMP`, and `TEMP`. That allowed validation children and libraries using the platform temporary-directory API to write into or consume a caller-selected host temporary tree rather than the disposable validation boundary.

### Changes / actions

- Added `TMPDIR`, `TMP`, and `TEMP` to the case-insensitive validation denylist so helper-level sanitized environments never retain caller-selected temporary roots.
- When an isolated validation home is supplied, create a dedicated `<isolated-home>/tmp` directory and explicitly set all three temporary-directory variables to that ephemeral path.
- Added regression coverage proving host temporary roots are removed without an isolated home, replaced by the disposable path with one, and recognized case-insensitively.
- Updated the prior isolated-home regression to use a real temporary directory because `_validation_env()` now intentionally creates its private temporary child.
- Preserved `PATH` and ordinary environment settings; no broad environment purge was introduced.
- No workflow, live service, cloud resource, Docker environment, Grafana instance, remediation target, or credentials were touched.

### Checks / results

- Runner hardening committed as `f0634875b7330ae5dc35ea7157a48a25696f2fa0`.
- Regression coverage committed as `459dc4d8e6196e3c9ff1ba48d5320fe6447041ec`.
- Static inspection confirms host temp variables are removed before validation subprocess construction and the replacement directory is nested beneath the already disposable `TemporaryDirectory` validation home.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not expose an executable checkout for the Python suite.

### Decisions

1. Temporary filesystem location is part of the validation isolation boundary: tests and subprocesses should not accidentally consume host-controlled temp state or leave validation artifacts outside the disposable root.
2. The runner explicitly sets all three common temp variables for cross-platform child-process behavior instead of relying on the parent Python process's cached `tempfile` choice.
3. The replacement temp root is created before subprocess launch and is automatically removed with the enclosing validation home.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
