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

## Latest run — 2026-09-22 — MCP lifecycle and rehearsal documentation integrity

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `docker-compose.yml`, `runtime/tests/test_mcp_compose_contract.py`, `runtime/README.md`, and the beginning of `runtime/mcp_smoke.py` to reconcile the documented operator flow with the actual Compose and MCP launcher behavior.

### Findings

1. `docker-compose.yml` explicitly starts the simulator with `STAGEGUARD_SCENARIO: healthy`, but `runtime/README.md` still claimed the stack starts faulted. That would make a new operator reset an already-healthy stack and obscured the intended acceptance sequence of baseline -> fault -> recovery.
2. The MCP service is correctly stdio-only and opt-in. `runtime/mcp_smoke.py` launches it with `docker compose run --rm -T mcp`, so it is a one-off process whose stdin/stdout are owned by the client, not a persistent sidecar that should be started with ordinary `docker compose up`.
3. The newly added `service_healthy` dependency is compatible with that launcher model: Compose starts/waits for dependencies before the one-off MCP process is attached to the smoke client.

### Exact changes made

- Corrected `runtime/README.md` to state that the local stack starts healthy.
- Simplified the deterministic rehearsal sequence to explicit fault injection, recovery, and optional reset to a fresh healthy baseline.
- Documented the actual MCP lifecycle: `docker compose run --rm -T mcp`, stdio transport, one-off container removal, no MCP host port, and Grafana readiness gating before launch.
- Documentation commit: `919e0694f01ed240819324b43007a0452c438dc8`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the runtime documentation update.
- Static cross-check confirms the revised operator instructions now agree with the current Compose `STAGEGUARD_SCENARIO: healthy` setting and `mcp_smoke.py` default launcher.
- Current Grafana container research also found historical upstream evidence that `wget` is present in the Alpine image family, but the exact pinned `13.2.1` image still needs executable verification; no stronger claim was recorded.
- No executable green claim is made: this connector environment does not provide a runnable Docker checkout.

### Decisions

1. Preserve healthy-by-default startup because acceptance should prove a clean baseline before injecting the seeded incident.
2. Keep MCP stdio/on-demand rather than adding an HTTP listener or trying to keep an unattached stdio process alive.
3. Treat operator documentation that contradicts runtime state as a correctness defect, not cosmetic cleanup.
4. Do not add CI merely to validate these connector-authored changes; preserve the low-noise GitHub Actions policy.

### Blockers / unknowns

- Run `docker compose config` in a real checkout.
- Confirm the pinned `grafana/grafana:13.2.1` image contains a working `wget` and that `/api/health` reaches healthy under the provisioned stack.
- Start the one-off MCP through `runtime/mcp_smoke.py` and confirm hardened `grafana/mcp-grafana:1.4.1` remains compatible with the read-only root filesystem.
- Run accumulated lifecycle/security/MCP tests on Linux and Windows.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal and pinned `1.4.1` read-only MCP smoke remain required.

## Single best next step

Execute the local Docker acceptance gate in a real checkout: `docker compose config`, start the base stack, verify Grafana becomes healthy, bootstrap the Viewer token, run `python runtime/mcp_smoke.py` against pinned MCP `1.4.1`, and then run the focused Compose/MCP regression suites. Fix the first executable failure found before adding further features.
