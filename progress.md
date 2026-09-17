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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs credentials/Python injection controls, disables user-site packages/bytecode writes, tests its own harness first, validates runtime activation before operator/API gates, executes overlapping gate selections only once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — runtime activation validation coverage

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator, its self-tests, and the runtime test inventory. The validator had strong gates for operator ingress, concurrency, incident lifecycle, audit/timeline, execution safety, and Grafana MCP, but it did not explicitly validate StageGuard's configuration-to-runtime activation boundary even though `runtime/tests/test_activation.py` already contains dedicated activation behavior coverage.

### Changes / actions

- Added a `runtime activation` gate to `scripts/run_stageguard_validation.py` immediately after the validator self-test gate and before operator/API gates.
- The gate explicitly owns `runtime/tests/test_activation.py`, making activation/configuration regressions part of the recommended fail-closed local validation path rather than relying on an unrelated broader suite.
- Updated validator documentation to describe the configuration-to-runtime boundary as a production safety gate.
- Added a validator self-test that pins the runtime activation gate to `test_activation.py`, so deletion, rename, or selection drift fails visibly.
- No credentials, cloud resources, remediation targets, Docker, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator change committed as `df59f91b4ecbf60289c93e022151ae6b456dad88`.
- Harness regression committed as `3d29c32e931806b2d769a3969fde100d015c669e`.
- Static repository inspection confirms `runtime/tests/test_activation.py` exists as a direct regular repository test and the new gate is ordered before operator/API validation.
- This connector environment does not expose an executable checkout, so the new regression has not been repository-executed and no new green-test claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Runtime activation is a first-class production boundary: configuration must be proven safe before operator/API behavior is treated as deployable.
2. Keep the gate exact rather than using a broad activation wildcard; this makes unexpected test-layout drift fail closed instead of silently broadening execution.
3. Continue keeping live Docker/Grafana access outside the dependency-light validator so local validation does not unexpectedly consume credentials or external services.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`. Fix any activation or downstream failures before performing the pinned Grafana MCP 1.4.1 read-only live smoke.
