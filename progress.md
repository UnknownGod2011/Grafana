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

## Latest run — 2026-09-20 — validation system Git configuration review

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, `runtime/tests/test_validation_home_isolation.py`, and the runtime test inventory. The runner already strips caller-provided `GIT_CONFIG_*` variables and uses an isolated HOME, but Git can still consult machine-level/system configuration because the sanitized child environment does not explicitly set `GIT_CONFIG_NOSYSTEM=1`.

### Changes / actions

- Audited the current validation environment boundary instead of adding another speculative credential-name filter.
- Identified a concrete remaining ambient-state path: `/etc/gitconfig` or platform-equivalent system Git configuration can affect validation subprocesses even though global/user Git configuration is isolated.
- Confirmed the correct hardening direction is to install a trusted `GIT_CONFIG_NOSYSTEM=1` override after sanitization; because `GIT_CONFIG_*` is intentionally stripped from caller input, the override must be installed by the runner itself, not inherited.
- Confirmed regression coverage should prove hostile caller values are removed and the trusted override is reinstalled, while existing `GIT_TERMINAL_PROMPT=0` and `GIT_PAGER=cat` behavior remains intact.
- Did not weaken `PATH`, execute live services, use credentials, touch Docker/Grafana/cloud resources, or trigger GitHub Actions.

### Checks / results

- Static repository inspection only; no green execution claim is made because this connector does not expose an executable checkout.
- The runtime test inventory remains extensive and includes validation ownership/full-coverage tests; the consolidated executable run is still necessary to classify actual failures.
- No production runtime behavior was changed in this run; this entry records the exact hardening gap so the next code change can be narrow and regression-tested rather than speculative.

### Decisions

1. System Git configuration is ambient executable/configuration state and should not influence a credential-isolated production validation run.
2. The trusted override must be applied after filtering, analogous to the existing non-interactive Git pager/prompt overrides.
3. Do not set a caller-controlled `GIT_CONFIG_SYSTEM` path or depend on `/dev/null`, which is less portable than Git's documented no-system-config control.
4. Keep the current isolated HOME behavior for user/global configuration and retain `PATH` until a cross-platform executable-resolution design is proven safe.

### Blockers / unknowns

- This connector can inspect and update repository text but cannot execute the repository test suite.
- The system-Git-config hardening still needs the runner and regression test edit in an executable/code-editing run.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Add the trusted `GIT_CONFIG_NOSYSTEM=1` post-sanitization override to `scripts/run_stageguard_validation.py`, add regression coverage in `test_validation_home_isolation.py`, then run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure before performing the pinned Grafana MCP 1.4.1 read-only smoke.
