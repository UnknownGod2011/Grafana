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
- The local Grafana MCP evidence sidecar is stdio-only, file-secret-backed, read-only, capability-free, cannot gain new privileges, and has an explicitly bounded read-only tool/result/resource contract.
- MCP startup waits for Grafana HTTP readiness rather than relying on container-start ordering.
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
- Added regression contracts for the reviewed host-published surface and stdio-only MCP transport.
- Hardened the opt-in MCP container with a read-only root filesystem, all Linux capabilities dropped, and `no-new-privileges`; added tests that also guard file-backed read-only token handling.
- Added a dedicated MCP Compose contract suite covering opt-in/stdio transport, narrow read-only tool categories, bounded container resources, and the Loki result cap.
- Added a Grafana HTTP healthcheck and changed MCP dependency semantics to `service_healthy`, eliminating the known container-start/readiness race; added a regression contract for this boundary.

## Latest run — 2026-09-21 — Grafana readiness boundary for MCP

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `docker-compose.yml` and `runtime/tests/test_mcp_compose_contract.py`, focusing on the remaining documented risk that MCP could be started after the Grafana container existed but before Grafana's HTTP API was usable.

### Research / finding

Docker's current Compose documentation explicitly states that short-form `depends_on` guarantees startup ordering but does not wait for a dependency to be ready; `condition: service_healthy` plus a dependency healthcheck is the supported readiness mechanism. Grafana MCP's own `/healthz` is unavailable in stdio mode and, for HTTP transports, only proves the MCP HTTP server is up rather than Grafana connectivity. Therefore the correct readiness boundary belongs on the Grafana dependency itself, while MCP remains stdio-only.

### Exact changes made

- Added a bounded Grafana healthcheck against `http://localhost:3000/api/health` with a 10-second start period, 5-second interval, 3-second timeout, and 12 retries.
- Changed MCP's Grafana dependency from short syntax to `condition: service_healthy`.
- Extended `runtime/tests/test_mcp_compose_contract.py` with a regression that requires both the Grafana HTTP healthcheck and MCP's `service_healthy` dependency.
- Refactored the test helper slightly so the Grafana and MCP service sections can be asserted independently without adding a YAML parser dependency.
- Compose implementation commit: `6fe142d1952167d8dbfa015c3d3a3cb8430d3852`.
- Regression-test commit: `2b4075c3071cb579e9369e673bf784ac06e282ec`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both changes.
- Static inspection confirms the readiness contract is internally coherent with current Compose semantics.
- Current official Docker documentation was checked for `depends_on.condition: service_healthy` behavior.
- Current Grafana MCP documentation was checked to avoid incorrectly adding an MCP `/healthz` probe to stdio transport; Grafana documents that endpoint as unavailable for stdio and as process-health-only for HTTP transports.
- No executable green claim is made: this connector environment does not provide a runnable checkout, so `docker compose config`, image-level command availability, pytest, and live MCP startup remain pending.

### Decisions

1. Keep MCP stdio-only; do not weaken transport isolation merely to gain an MCP HTTP health endpoint.
2. Put readiness responsibility on Grafana because MCP's evidence operations require Grafana connectivity.
3. Use `service_healthy`, not sleeps or retry timing in the MCP command, so Compose models the dependency explicitly.
4. Keep the healthcheck bounded; a failed Grafana startup must eventually fail rather than stall indefinitely.
5. Preserve the low-noise policy: no CI workflow was added solely for this change.

### Blockers / unknowns

- Run `docker compose config` in a real checkout to validate the final Compose model.
- Confirm `wget` is present in the pinned `grafana/grafana:13.2.1` image and the `/api/health` probe succeeds there; if not, replace the probe with an image-native mechanism rather than installing packages ad hoc.
- Start the `mcp` profile and confirm the read-only root filesystem remains compatible with `grafana/mcp-grafana:1.4.1`.
- Run accumulated lifecycle/security/MCP tests on Linux and Windows.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal and pinned `1.4.1` read-only MCP smoke remain required.

## Single best next step

Execute `docker compose config` and a real `grafana` + `mcp` profile startup. Verify the Grafana healthcheck transitions to healthy, MCP waits for that transition, and a read-only MCP query succeeds under the hardened `1.4.1` container; then run the focused Compose/MCP regression suites.
