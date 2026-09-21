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

## Latest run — 2026-09-21 — loopback-only local observability stack

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py`, its focused stop-lifecycle regression suite, the repository root, and `docker-compose.yml`.

### Finding

The local StageGuard API was already bound to `127.0.0.1`, and the watchdog fixture was explicitly loopback-only, but the Compose port mappings for the simulator (`9108`), Prometheus (`9090`), and Grafana (`3000`) used bare host ports. Docker therefore published those services on all host interfaces by default. This was inappropriate for a local fixture because the simulator exposes scenario mutation endpoints, Prometheus has no authentication in this stack, and Grafana uses a checked-in `stageguard-local-only` administrator password.

### Exact changes made

- Changed simulator publishing from `9108:9108` to `127.0.0.1:9108:9108`.
- Changed Prometheus publishing from `9090:9090` to `127.0.0.1:9090:9090`.
- Changed Grafana publishing from `3000:3000` to `127.0.0.1:3000:3000`.
- Retained the watchdog fixture's existing loopback-only `127.0.0.1:9111:9111` mapping.
- Added comments beside each mapping documenting the security reason so future edits do not casually reintroduce all-interface exposure.
- Implementation commit: `79dacc473b9b72a37ab120483f3c10fc6f5e3747`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the Compose update.
- Static inspection confirms every host-published service in `docker-compose.yml` is now explicitly loopback-bound.
- Existing local URLs in `demo_local.py` already use `127.0.0.1`, so no caller URL migration is required.
- No executable green claim is made: this connector environment does not provide a runnable checkout. `docker compose config`, focused lifecycle tests, and the live rehearsal remain pending execution.

### Decisions

1. A development stack with local-only credentials or unauthenticated control/metrics endpoints must be secure-by-default at the network binding layer.
2. Container-to-container connectivity is unaffected because Compose services continue to communicate on the internal Compose network; only host publication was narrowed.
3. No firewall assumptions are used as a substitute for explicit loopback binding.
4. No CI workflow was introduced solely for this validation, preserving the low-noise Actions policy.

### Blockers / unknowns

- Run `docker compose config` and the accumulated lifecycle suites in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated lifecycle and network-binding hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `docker compose config`, the accumulated local lifecycle suites on Linux/Windows, and consolidated validation; then run the unattended Docker cleanup rehearsal and pinned Grafana MCP `1.4.1` read-only smoke.
