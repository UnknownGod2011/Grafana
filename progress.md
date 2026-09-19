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

## Latest run — 2026-09-19 — validation Cloud SDK credential isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and its self-tests in `runtime/tests/test_stageguard_validation_runner.py`. The consolidated validation runner already scrubbed explicit Google credentials, metadata endpoints, proxy credentials, and many tool-specific configuration roots. However, `CLOUDSDK_CONFIG` was only redirected when an isolated home was supplied; direct callers of `_validation_env()` without `isolated_home` could retain an ambient gcloud configuration directory containing ADC or cached account credentials.

### Changes / actions

- Added `CLOUDSDK_CONFIG` to the exact sensitive-environment denylist so validation never inherits the caller's gcloud configuration root.
- Preserved the existing isolated-home behavior: when the production runner creates its temporary home it explicitly replaces `CLOUDSDK_CONFIG` with a path under that temporary directory after scrubbing the ambient value.
- Added regression coverage proving `_validation_env()` drops an ambient `CLOUDSDK_CONFIG` even when no isolated home is requested.
- Extended case-insensitive sensitive-name coverage to include `cloudsdk_config`.
- No credentials, live remediation targets, Grafana instances, Docker, cloud resources, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validation-runner hardening committed as `c6b6ca5d34bb7200afa58147fea2c5056050e44d`.
- Regression coverage committed as `76e16f29f30981f4caa588ce1a5e0af1fd569270`.
- Static inspection confirms ambient `CLOUDSDK_CONFIG` is removed before the optional isolated-home override is installed.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Credential isolation must hold for helper-level validation calls as well as the main runner; relying on `main()` always supplying an isolated home leaves a reusable security helper with surprising behavior.
2. Cloud SDK configuration is treated as a credential-discovery channel, not ordinary configuration, because gcloud/ADC state can be discovered from that directory without an explicit token environment variable.
3. The production runner continues to use a temporary gcloud root rather than simply omitting the variable, preventing fallback discovery through a real user home.
4. No CI workflow was added or triggered; validation remains intentionally local and quiet.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
