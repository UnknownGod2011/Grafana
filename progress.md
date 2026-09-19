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

## Latest run — 2026-09-19 — validation home credential-discovery isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The prior run correctly scrubbed ambient `CLOUDSDK_CONFIG`, but helper-level `_validation_env()` calls without `isolated_home` still preserved `HOME` and `USERPROFILE`. That leaves default per-user credential/config discovery reachable to SDKs that fall back to the user's home directory even after explicit credential variables and Cloud SDK configuration are removed. The production `main()` path was already safer because it replaces those homes with a temporary directory.

### Changes / actions

- Added `HOME` and `USERPROFILE` to the exact sensitive-environment denylist.
- Preserved production behavior: supplying `isolated_home` still reinstalls only temporary `HOME`, `USERPROFILE`, XDG/AppData roots, and `CLOUDSDK_CONFIG` after ambient values are scrubbed.
- Added `runtime/tests/test_validation_home_isolation.py`, automatically owned by the existing `validation harness` gate via `test_validation_*.py`.
- Added regressions proving helper-level validation drops HOME/USERPROFILE plus other credential-discovery roots, matching is case-insensitive, and isolated execution reinstalls only ephemeral roots.
- No credentials, live remediation targets, Grafana instances, Docker, cloud resources, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validation-runner hardening committed as `3be59f9ff22301a4b986d940523bc8d3eca62726`.
- Regression coverage committed as `4836d13639c1eff803766ddc5d8cc4171e667bf6`.
- Static inspection confirms ambient home roots are removed before optional isolated-home overrides are installed.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. `HOME` and `USERPROFILE` are credential-discovery channels in a credential-isolated validation process, not harmless environment metadata.
2. Helper-level isolation must be safe independently of `main()` so future callers cannot accidentally regain real-user credential discovery.
3. The main runner continues to provide an ephemeral home rather than leaving HOME absent, preserving deterministic SDK/tool behavior while isolating user state.
4. The new regression uses the existing validation-harness ownership pattern, avoiding a new gate or CI workflow.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
