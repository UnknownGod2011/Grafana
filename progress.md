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

## Latest run — 2026-09-20 — system Git configuration isolation implemented

### Inspected at start

Read `progress.md` completely first. Inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_home_isolation.py`. Confirmed the prior run's finding: caller-provided `GIT_CONFIG_*` values were removed and HOME was isolated, but Git's machine/system configuration remained eligible for discovery because the runner did not install Git's documented no-system-config environment control.

### Exact changes made

- Added trusted `GIT_CONFIG_NOSYSTEM=1` to `VALIDATION_ENV_OVERRIDES` in `scripts/run_stageguard_validation.py`.
- Kept `GIT_CONFIG_` in the case-insensitive sensitive prefix set, so a caller-provided `GIT_CONFIG_NOSYSTEM=0` is stripped before the trusted value is installed.
- Added `runtime/tests/test_validation_git_system_config_isolation.py` with focused regression coverage proving hostile system/global Git config paths are removed, the trusted no-system override is reinstalled, Git remains non-interactive (`GIT_TERMINAL_PROMPT=0`, `GIT_PAGER=cat`), and ordinary configuration plus PATH survive.
- Added mixed-case sensitivity coverage for `GIT_CONFIG_NOSYSTEM`.
- No credentials, live Grafana instance, remediation target, Docker/cloud resources, or GitHub Actions workflow were touched.

### Checks / results

- Static inspection and repository edits completed successfully.
- No executable checkout is exposed by this connector, so the new tests and consolidated suite were not executed and no green test claim is made.
- The new test filename matches the existing `test_validation_*.py` validation-harness gate, so it is owned by the consolidated runner rather than becoming an intentionally unowned test.

### Decisions

1. System Git configuration is ambient host state and must not influence the isolated production validation process.
2. `GIT_CONFIG_NOSYSTEM=1` is installed only after caller environment filtering; callers cannot disable it through inherited environment state.
3. Retain isolated HOME for user/global configuration and retain PATH until a portable executable-resolution replacement is proven safe.
4. Prefer a focused new regression file over broad unrelated test churn; the validation gate already owns it by pattern.

### Blockers / unknowns

- This connector can inspect/update repository text but cannot execute the repository test suite.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout, fix every concrete failure it exposes, and only after that perform the pinned Grafana MCP 1.4.1 read-only smoke.
