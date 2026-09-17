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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs credentials/Python injection controls, disables user-site packages/bytecode writes, and tests its own harness first.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — operator concurrency validation coverage

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator, its self-tests, the runtime test inventory, and the API concurrency contract. The production API already has a strong test proving that a blocked remediation provider does not block incident/readiness/metrics reads, that deadline telemetry becomes unhealthy, that competing mutations fail closed, and that remediation is not replayed. The execution-watchdog API contract also exists, but neither was explicitly owned by a dedicated fast production-concurrency gate.

### Changes / actions

- Added a first-class `operator concurrency` validation gate immediately after the operator API boundary gate.
- The gate owns exactly `test_api_concurrency.py` and `test_api_execution_watchdog.py`.
- Added a validator self-test pinning that exact ownership so deletion, rename, or accidental selection drift fails the harness instead of silently weakening concurrency coverage.
- Updated validator documentation to state the responsiveness/fail-closed purpose of this gate.
- Preserved path confinement, credential/Python-environment isolation, non-interactive execution, per-file timeouts, and no-CI/no-Docker behavior.
- No credentials, cloud resources, remediation targets, workflows, or unrelated repositories were touched.

### Checks / results

- Validator change committed as `1b8f4846c5e6246ea812990d3876c0b24c1969c6`.
- Harness coverage committed as `abff634bd4bb09302f0de9728f03d79be8aa8fac`.
- Repository inspection confirms both selected concurrency/watchdog test files exist on `main`.
- The concurrency test explicitly exercises real loopback HTTP serving with a deliberately blocked remediation fake and checks read responsiveness, watchdog/readiness/metrics state, competing-mutation rejection, and no replay.
- This connector environment does not expose an executable checkout, so no new test-pass claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Production incident-command software must remain observable while remediation I/O is slow or stuck; this is a first-class safety contract, not merely a performance concern.
2. Concurrency/watchdog tests belong immediately after ingress validation and before broader lifecycle gates so deadlock/replay regressions fail early.
3. Exact two-file ownership is intentional because these tests define the HTTP execution responsiveness/watchdog boundary.

### Blockers / unknowns

- The expanded consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list`, confirm the operator API, operator concurrency, and incident-lifecycle selections, then run `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before the pinned Grafana MCP 1.4.1 read-only live smoke.
