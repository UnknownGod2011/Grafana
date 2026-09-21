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

## Latest run — 2026-09-21 — MCP contract regression coverage

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `docker-compose.yml` and `runtime/tests/test_compose_local_security.py`, with emphasis on whether the MCP runtime's existing least-privilege command/resource settings were protected against future configuration drift.

### Finding

The Compose file already constrains MCP to an opt-in profile, stdio transport, `--disable-write`, `--disable-proxied`, `datasource,prometheus,loki`, an eight-line Loki result cap, and bounded memory/CPU/PID resources. Existing security tests protected host exposure, container privileges, and token handling, but did not lock these application-level and resource-bounding invariants.

### Exact changes made

- Added `runtime/tests/test_mcp_compose_contract.py` with regression contracts for opt-in/stdio-only transport, the narrow read-only MCP tool surface, 256 MiB / 0.50 CPU / 128 PID limits, and the Loki result cap of 8.
- Commit: `cbdbd521b202dd2c82f61b8d7b1f047410d7e730`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the new regression suite.
- Static inspection confirms every asserted contract is present in the current Compose MCP service.
- No executable green claim is made: this connector environment does not provide a runnable checkout, so pytest and Docker startup remain pending.
- A proposed Grafana-health dependency hardening edit was not applied after the repository write boundary rejected that mutation; no partial configuration change was left behind.

### Decisions

1. Treat MCP application flags and resource bounds as security/reliability invariants, not informal configuration.
2. Keep these focused tests separate from host/container security tests so failures identify whether drift is transport/tool/resource-level versus Docker privilege/exposure-level.
3. Do not add CI solely for this suite; preserve the low-noise Actions policy.

### Blockers / unknowns

- Run `docker compose config` and start the `mcp` profile in a real Docker checkout to confirm the read-only root filesystem is compatible with upstream `1.4.1`.
- Run the accumulated lifecycle/security/MCP contract suites on Linux and Windows.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal and pinned `1.4.1` read-only MCP smoke remain required.

## Single best next step

Execute `docker compose config`, the Compose/MCP security tests, and an `mcp`-profile startup/read-only smoke in a real Docker checkout. If startup exposes a genuine Grafana-readiness race, add a verified Grafana healthcheck and `service_healthy` dependency rather than relying on container-start ordering.
