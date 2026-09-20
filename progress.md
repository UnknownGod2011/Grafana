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

## Latest run — 2026-09-20 — inherited Git repository-state isolation implemented

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_validation_git_system_config_isolation.py`. The runner already isolated Git credentials, helpers, config, attributes, editors and pagers, but the allow-by-omission approach still left Git repository-discovery and object-store controls such as `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_CEILING_DIRECTORIES`, `GIT_DISCOVERY_ACROSS_FILESYSTEM`, and `GIT_NAMESPACE` inherited from the caller. Those can redirect Git commands away from the checked-out StageGuard repository or toward caller-controlled object/index state.

### Exact changes made

- Broadened the case-insensitive sensitive environment prefix from the partial `GIT_CONFIG_`/`GIT_ATTR_` families to all inherited `GIT_*` variables.
- Kept the explicit trusted post-sanitization Git overrides: `GIT_CONFIG_NOSYSTEM=1`, `GIT_ATTR_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, and `GIT_PAGER=cat`.
- Extended `runtime/tests/test_validation_git_system_config_isolation.py` with hostile repository, worktree, index, object-store, discovery, namespace, config, and attribute controls in canonical/lower/mixed-case forms.
- Regression assertions continue to preserve `PATH` and ordinary non-sensitive environment configuration while ensuring hostile Git values cannot survive sanitization.
- Runner implementation commit: `d0218d3efcc81aadcbc0e8248175f2cfe5ffd037`.
- Regression-test commit: `606f28f6b41e9a2e8c2ffcc966abb1a472b26faa`.
- No credentials, live Grafana instance, remediation target, Docker/cloud resources, or GitHub Actions workflow were touched.

### Checks / results

- Repository inspection and static edits completed successfully.
- This connector does not expose an executable checkout, so the modified tests and consolidated validation suite were not executed; no new green-suite claim is made.
- The modified regression file remains owned by the existing `test_validation_*.py` validation-harness gate.

### Decisions

1. Validation should treat the entire inherited Git environment namespace as ambient caller state, rather than continuously enumerating individual Git variables as new gaps are discovered.
2. Only StageGuard's small trusted Git override set is reintroduced after sanitization; this makes the boundary easier to reason about and prevents repository/object-store redirection classes of bugs.
3. PATH remains intentionally preserved until a cross-platform executable-resolution replacement can be proven safe.
4. This closes the recurring Git-environment enumeration problem; future work should return to executable validation and product/runtime gaps rather than adding individual Git variables.

### Blockers / unknowns

- The repository connector can inspect/update text but cannot execute the test suite.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout, fix every concrete failure it exposes, and only after that perform the pinned Grafana MCP 1.4.1 read-only smoke.
