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

## Latest run — 2026-09-20 — Python validation startup isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_home_isolation.py`. The runner already removed `PYTHONHOME`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONINSPECT`, and `PYTHONBREAKPOINT` and forced `PYTHONNOUSERSITE=1`, but still inherited several Python interpreter controls that could influence validation startup or redirect interpreter filesystem state.

### Changes / actions

- Added `PYTHONWARNINGS`, `PYTHONUSERBASE`, `PYTHONPYCACHEPREFIX`, and `PYTHONEXECUTABLE` to the case-insensitive validation denylist.
- This prevents inherited warning-filter/import behavior, host user-base discovery, caller-selected bytecode-cache roots, and executable-path overrides from crossing into validation subprocesses.
- Added regression coverage for canonical, lowercase, and mixed-case spellings while confirming `PATH` and ordinary environment configuration remain intact.
- Kept the change deliberately narrow rather than replacing the environment with a brittle global allowlist.
- No workflow, live service, cloud resource, Docker environment, Grafana instance, remediation target, or credentials were touched.

### Checks / results

- Runner hardening committed as `17c7664314ec70d6a694d5b48a0586fb16c61226`.
- Regression coverage committed as `aa08ee864a02660fe0b5ee0a73c74723953ab5a6`.
- Static inspection confirms these controls are removed by the same case-insensitive sanitizer before validation subprocess construction.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not expose an executable checkout for the Python suite.

### Decisions

1. Python-specific startup/path controls belong inside the same validation isolation boundary as credential homes, shell startup files, dynamic loaders, and language toolchain hooks.
2. `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1` remain explicit safe overrides; potentially host-directed Python path/startup controls are removed instead of rewritten.
3. `PATH` remains available because the repository has cross-platform tests that legitimately discover system executables; hardening it safely requires an explicit executable-resolution design rather than an arbitrary replacement.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
