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
- The local Grafana MCP evidence adapter is an on-demand stdio process, file-secret-backed, read-only, capability-free, cannot gain new privileges, and has an explicitly bounded read-only tool/result/resource contract.
- MCP startup waits for Grafana HTTP readiness rather than relying on container-start ordering.
- Local incident rehearsals establish a healthy telemetry baseline before fault injection.
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
- Bound the simulator, Prometheus, Grafana, and watchdog fixture host ports to `127.0.0.1`.
- Added regression contracts for the reviewed host-published surface and stdio-only MCP transport.
- Hardened the opt-in MCP container with a read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, file-backed token handling, and bounded resources/results.
- Added a Grafana HTTP healthcheck and changed MCP dependency semantics to `service_healthy`.
- Corrected the local runtime guide so its incident-replay instructions match the actual healthy-by-default Compose contract and documented that MCP is launched as a one-off stdio subprocess rather than a persistent network sidecar.
- Aligned the Grafana readiness probe with the official `grafana/mcp-grafana` integration stack for the exact pinned Grafana `13.2.1` image (`curl -sf /api/health`) and locked that command in the MCP Compose contract test.

## Latest run — 2026-09-22 — upstream-aligned Grafana readiness probe

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `docker-compose.yml` and `runtime/tests/test_mcp_compose_contract.py`, then checked current official Grafana and `grafana/mcp-grafana` sources for the pinned image's readiness convention.

### Findings

1. StageGuard's new readiness gate used `wget --spider` and still carried an explicit executable unknown about whether the pinned Grafana image supported that exact probe.
2. The official `grafana/mcp-grafana` repository currently runs the exact same `grafana/grafana:13.2.1` image and healthchecks it with `curl -sf http://localhost:3000/api/health`.
3. That upstream stack is stronger evidence for this exact integration/image pair than historical assumptions about Alpine utilities, so StageGuard can eliminate the unnecessary `wget` uncertainty without broadening privileges or adding dependencies.

### Exact changes made

- Changed the Grafana Compose healthcheck to `curl -sf http://localhost:3000/api/health` and matched upstream's 20 retries.
- Updated the healthcheck comment to record why this probe is selected.
- Strengthened `runtime/tests/test_mcp_compose_contract.py` to lock the exact upstream-compatible readiness command rather than merely checking that `/api/health` appears somewhere in the service.
- Compose commit: `ad06521056e3d028584fc37b93a653b1968ce065`.
- Contract-test commit: `a13dbf228184abd40217326239ae29c2ec9d73a6`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and test updates.
- Current upstream `grafana/mcp-grafana` Compose configuration provides direct static evidence that the exact pinned Grafana `13.2.1` image is expected to support this `curl` healthcheck.
- No executable green claim is made: this connector environment still does not provide a runnable Docker checkout.

### Decisions

1. Prefer the exact readiness convention exercised by Grafana's own MCP integration stack over maintaining a StageGuard-specific shell-tool assumption.
2. Keep the readiness endpoint on Grafana itself; do not expose MCP over HTTP merely to healthcheck it.
3. Keep the probe unauthenticated and local to the container because `/api/health` is only a readiness boundary, not an evidence query.
4. Do not add CI just to validate connector-authored changes; preserve the low-noise Actions policy.

### Blockers / unknowns

- Run `docker compose config` in a real checkout.
- Start the base stack and observe Grafana reach healthy with the revised upstream-aligned probe.
- Bootstrap the Viewer token and run `python runtime/mcp_smoke.py` against hardened `grafana/mcp-grafana:1.4.1`.
- Run accumulated lifecycle/security/MCP tests on Linux and Windows.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal remains required after these hardening changes.

## Single best next step

Execute the local Docker acceptance gate in a real checkout: `docker compose config`, start the base stack and verify Grafana reaches healthy using the upstream-aligned probe, bootstrap the Viewer token, run `python runtime/mcp_smoke.py` against pinned MCP `1.4.1`, and fix the first executable failure before adding further features.
