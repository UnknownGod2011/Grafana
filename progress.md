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
- Production remediation accepts only canonical operation IDs, bounded canonical target identities, frozen execution/reconciliation capabilities, exact validated transport/reconciliation result types, and bounded finite policy configuration.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Latest run — 2026-09-20 — system Git attributes isolation implemented

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/run_stageguard_validation.py`, the validation test inventory, and `runtime/tests/test_validation_git_system_config_isolation.py`. The previous run had closed system Git configuration discovery with `GIT_CONFIG_NOSYSTEM=1`, but system-wide Git attributes remained ambient host state: Git can consult the system gitattributes file unless `GIT_ATTR_NOSYSTEM` is set.

### Exact changes made

- Added `GIT_ATTR_` to the validation runner's case-insensitive sensitive environment prefixes so caller-provided Git attribute controls cannot survive sanitization.
- Added trusted `GIT_ATTR_NOSYSTEM=1` after filtering, alongside the existing trusted `GIT_CONFIG_NOSYSTEM=1` override.
- Extended `runtime/tests/test_validation_git_system_config_isolation.py` to cover hostile Git attribute controls, attempted `GIT_ATTR_NOSYSTEM=0`, canonical/lower/mixed-case sensitivity, preservation of ordinary configuration and PATH, and retention of the trusted non-interactive Git settings.
- Runner implementation commit: `9695db6299780622c33686cb5fcf0c1181dec2ae`.
- Regression-test commit: `0465df0dbdafb7013f49e219692c1a81b949fa08`.
- No credentials, live Grafana instance, remediation target, Docker/cloud resources, or GitHub Actions workflow were touched.

### Checks / results

- Repository inspection and static edits completed successfully.
- This connector does not expose an executable checkout, so the modified tests and consolidated validation suite were not executed; no new green-suite claim is made.
- The modified regression file remains owned by the existing `test_validation_*.py` validation-harness gate.

### Decisions

1. System-wide Git attributes are ambient host policy and must not affect an isolated production validation process, just as system Git configuration must not.
2. Caller-supplied `GIT_ATTR_*` values are stripped before the trusted no-system-attributes value is installed, preventing inherited environment state from disabling the boundary.
3. PATH remains intentionally preserved until a cross-platform executable-resolution replacement can be proven safe; this run did not broaden into speculative PATH hardening.
4. The change is intentionally narrow and covered in the existing Git ambient-state regression module rather than creating another overlapping test file.

### Blockers / unknowns

- The repository connector can inspect/update text but cannot execute the test suite.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout, fix every concrete failure it exposes, and only after that perform the pinned Grafana MCP 1.4.1 read-only smoke.
