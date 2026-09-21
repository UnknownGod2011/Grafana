# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- Operator API and remediation boundaries reject ambiguous framing and unsafe mutation inputs.
- Local cleanup signals only structurally verified owned API processes and independently attempts every requested owned component.
- Compose teardown is timeout-bounded and verified against all project containers before success is reported.
- Local demo services that do not provide production-grade authentication are published on loopback only; checked-in demo credentials must never create a LAN-accessible service by default.
- Validation claims distinguish historical executable results from connector-authored changes that have not run in a checkout.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest lifecycle/security hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with opt-in cleanup and ownership-aware teardown.
- Hardened API startup/shutdown against stale metadata, PID reuse, invalid/special PIDs, unhealthy-but-owned processes, and partial cleanup.
- Made local Compose teardown truthful: failures aggregate, all-state project-container verification is required, and Docker commands are timeout-bounded.
- Added Grafana lifecycle alert/dashboard/runbook surfaces and pinned the official Grafana MCP image to `1.4.1` with write/proxied tools disabled.
- Bound the simulator, Prometheus, Grafana, and watchdog fixture host ports to `127.0.0.1` so local-only control surfaces, unauthenticated Prometheus, and the checked-in Grafana demo credential are not exposed to the developer's LAN by default.
- Added a regression contract that fails if any reviewed local Compose host port stops being loopback-only, if an unreviewed host publication appears, or if the stdio MCP sidecar gains a host port.

## Latest run — 2026-09-21 — Compose network-exposure regression guard

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository root, `docker-compose.yml`, and the runtime test layout.

### Finding

The previous run fixed the local network exposure itself, but the invariant existed only as configuration and comments. A later Compose edit could silently reintroduce Docker's all-interface publishing or add a new host-published service without security review. The stdio Grafana MCP sidecar likewise should not acquire a host port accidentally.

### Exact changes made

- Added `runtime/tests/test_compose_local_security.py`.
- The test records the four intentionally published local endpoints and requires the exact reviewed set: simulator `9108`, watchdog fixture `9111`, Prometheus `9090`, and Grafana `3000`.
- Every reviewed mapping must begin with `127.0.0.1:`; an unexpected additional host publication fails the contract so it receives explicit review rather than silently expanding exposure.
- Added a separate assertion that the stdio `mcp` service has no `ports:` block.
- Regression-guard commit: `a23c9ee961de268c938d92fb78ba2107bb640af2`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the new regression test.
- Static comparison against the current Compose file shows the test's expected mappings match the four existing loopback-only publications.
- No executable green claim is made: this connector environment does not provide a runnable checkout. The new pytest contract and `docker compose config` remain pending execution in a real checkout.

### Decisions

1. Network exposure is a security invariant and should be executable, not merely documented.
2. The contract intentionally requires explicit review when a fifth host-published service is introduced, even if it is loopback-bound.
3. MCP remains stdio-only in the local Compose profile; no TCP exposure is needed for StageGuard's current integration.
4. No CI workflow was added solely to run this test, preserving the low-noise Actions policy.

### Blockers / unknowns

- Run `docker compose config` and the accumulated lifecycle/security suites in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated lifecycle and network-binding hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `docker compose config` plus the accumulated local lifecycle/security tests in a real Linux/Windows checkout, then run consolidated validation, the unattended Docker cleanup rehearsal, and the pinned Grafana MCP `1.4.1` read-only smoke.
