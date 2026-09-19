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

## Latest run — 2026-09-19 — validation dynamic-loader isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_home_isolation.py`. The harness already isolated credential/config homes, proxies, cloud credentials, Git configuration, TLS key logging, and TLS trust overrides. A higher-impact process-injection gap remained: Linux `LD_PRELOAD`/`LD_LIBRARY_PATH` and macOS `DYLD_*` variables could be inherited by validation children, allowing host-selected dynamic libraries or search paths to affect the Python test processes before application-level isolation applies.

### Changes / actions

- Added `LD_PRELOAD` and `LD_LIBRARY_PATH` to the case-insensitive validation environment denylist.
- Added the `DYLD_` family to the case-insensitive sensitive-prefix denylist, covering macOS loader controls such as `DYLD_INSERT_LIBRARIES`, `DYLD_LIBRARY_PATH`, and `DYLD_FRAMEWORK_PATH` without relying on an incomplete enumeration.
- Added regression coverage for canonical, lowercase, and mixed-case forms of Linux and representative macOS loader variables.
- Regression asserts the hostile loader path is absent while an ordinary environment setting remains intact.
- Kept the work inside the existing validation-harness ownership surface; no CI workflow was created or triggered.
- No credentials, live remediation targets, Grafana instances, Docker, cloud resources, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `f8ec8369924369f8304676d96dc1f8bd830f92b2`.
- Regression coverage committed as `bc35f76a0d887ccb4167dee657832e3038ba66e5`.
- Static inspection confirms loader variables are rejected case-insensitively by `_is_sensitive_env_name()` before validation child environments are constructed.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Dynamic-loader environment controls belong to the validation isolation boundary because they can alter executable behavior before Python test code or StageGuard safety checks run.
2. `DYLD_` is denied as a family rather than enumerating individual variables, reducing the risk of leaving an alternate Apple loader-control channel open.
3. Normal system loader configuration remains untouched; only caller-supplied process environment overrides are removed.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
