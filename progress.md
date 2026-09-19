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

## Latest run — 2026-09-20 — JVM build-tool isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_home_isolation.py`. The validation environment already isolated cloud credentials/config, credential discovery homes, proxies, Git config, TLS key/trust overrides, dynamic loaders, shell startup, language runtimes, .NET, and Go/Rust toolchain controls. Maven and Gradle still had ambient configuration/startup channels that could affect child processes.

### Changes / actions

- Added `MAVEN_OPTS`, `MAVEN_ARGS`, and `MAVEN_USER_HOME` to the validation denylist. Maven options can carry system properties or extension-classpath controls, while a caller-selected Maven home can expose host settings/configuration.
- Added `GRADLE_OPTS` and `GRADLE_USER_HOME`; a caller-selected Gradle user home can expose init scripts and other host-controlled build configuration to validation children.
- Added case-insensitive regression coverage for all five variables while verifying an ordinary setting remains intact.
- Kept filtering targeted rather than deleting broad `MAVEN_*`/`GRADLE_*` prefixes, reducing accidental disruption of benign build metadata.
- No workflow, live service, cloud resource, Docker environment, Grafana instance, remediation target, or credentials were touched.

### Checks / results

- Runner hardening committed as `9d7e8d7e2506ee01f24a59b53b3f91a9a22f1230`.
- Regression coverage committed as `2ce1cd013529158748c24d2ff3d17316d01e2544`.
- Static inspection confirms the five new controls are matched case-insensitively by `_is_sensitive_env_name()` and therefore removed before validation subprocess environments are constructed.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not expose an executable checkout for the Python suite.

### Decisions

1. Maven/Gradle startup/configuration controls belong inside the validation trust boundary because repository tests or helper scripts may invoke JVM build tools even though StageGuard's core runtime is Python.
2. The sanitizer remains explicit and auditable instead of using broad ecosystem prefixes.
3. `PATH` remains preserved because tests legitimately resolve system tools; safe replacement requires a deliberate cross-platform executable allowlist.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
