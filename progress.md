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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs credentials/Python injection controls, disables user-site packages/bytecode writes, tests its own harness first, executes overlapping gate selections only once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — validation subprocess launch failure handling

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, consolidated validator, and validator self-tests. The validator already handled non-zero child exits and `TimeoutExpired`, but an `OSError` from process creation (for example an unavailable interpreter/runtime resource) escaped `main()` as an unclassified traceback. That meant an infrastructure-level inability to execute a selected safety test was not represented through the validator's normal fail-closed result/reporting path.

### Changes / actions

- Updated `scripts/run_stageguard_validation.py` to catch `OSError` around each test subprocess launch.
- Launch errors are now emitted as `LAUNCH ERROR` diagnostics containing the selected test name and exception class/message.
- Launch errors are appended to the same gate-qualified failure list as non-zero exits and timeouts, preserving fail-fast and `--keep-going` semantics.
- Updated the runner module documentation to make this fail-closed behavior explicit.
- Added a harness regression that injects an interpreter-launch `OSError`, asserts exit code 1, and verifies both the launch diagnostic and gate-qualified failed-test summary.
- No credentials, cloud resources, remediation targets, Docker, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator hardening committed as `58069d9fb43b64465bdd5ea24420f676a11b0e4c`.
- Harness regression committed as `1a6ee55bafa7e653ce04f4395b21387e28585fe6`.
- Static inspection confirms `OSError` is caught at the same boundary as `TimeoutExpired`; the test remains marked failed and cannot produce a green validator result.
- This connector environment does not expose an executable checkout, so the new regression has not been repository-executed and no new green-test claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Failure to launch a required test is a validation failure, not an exceptional success-neutral condition.
2. Catch only expected process-launch OS failures; programming errors should continue surfacing rather than being hidden by an overly broad exception handler.
3. Preserve the existing fail-fast/keep-going behavior and gate-qualified reporting so local operators get actionable attribution.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before performing the pinned Grafana MCP 1.4.1 read-only live smoke.
