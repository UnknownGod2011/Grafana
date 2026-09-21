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
- The local Grafana MCP evidence sidecar is stdio-only, file-secret-backed, read-only, capability-free, and cannot gain new privileges.
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

## Latest run — 2026-09-21 — MCP evidence-sidecar sandbox hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `docker-compose.yml`, the local Compose security regression test, and current official Grafana MCP authentication/install documentation. Verified specifically against the `v1.4.1` upstream authentication document that `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` is supported and reads the token from a file, including rotation-safe rereads.

### Finding

The MCP sidecar already had a strong application-level least-privilege contract (`--disable-write`, a narrow enabled-tool list, `--disable-proxied`, stdio-only transport, and a read-only token mount), but its container itself retained Docker's normal writable root filesystem and default Linux capability/privilege posture. For a component whose only job is read-only evidence retrieval over the network, those mutation privileges are unnecessary.

### Exact changes made

- Updated `docker-compose.yml` MCP service with `read_only: true`, `cap_drop: [ALL]`, and `security_opt: [no-new-privileges:true]` while preserving network access, stdio transport, and the existing read-only token mount.
- Extended `runtime/tests/test_compose_local_security.py` with an MCP section helper and executable contracts for the read-only root filesystem, all-capability drop, no-new-privileges, file-backed token variable, absence of an inline service-account token, and read-only token mount.
- Compose hardening commit: `ed3b0df9cf65fe41048d285dc40dd227979e625c`.
- Security regression commit: `d5ac48eaae261a7ef579eb540a376f7187601f5d`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression-test updates.
- Upstream Grafana MCP `v1.4.1` authentication documentation explicitly supports `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`, confirming StageGuard's mounted-secret mechanism is valid for the pinned release.
- Static review confirms the MCP service has no host port and no requested writable volume; the token bind remains `:ro`.
- No executable green claim is made: this connector environment does not provide a runnable checkout. `docker compose config`, container startup under the new sandbox, and pytest execution remain pending in a real checkout.

### Decisions

1. Defense in depth applies to the evidence plane: application-level read-only flags do not justify retaining unnecessary container mutation privileges.
2. Keep the token file mechanism rather than moving the secret into Compose environment values; upstream `v1.4.1` explicitly supports the file variable and token rotation.
3. Do not apply `read_only` blindly to Grafana or Prometheus because they have legitimate runtime write requirements; hardening remains service-specific.
4. No CI workflow was added solely for these tests, preserving the low-noise Actions policy.

### Blockers / unknowns

- Run `docker compose config` and start the `mcp` profile in a real Docker checkout to confirm the upstream image needs no writable root path at startup.
- Run the accumulated lifecycle/security suites on Linux and Windows, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated lifecycle/security hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `docker compose config`, the Compose security tests, and an `mcp`-profile startup/read-only smoke in a real Docker checkout; if the upstream image requires a writable ephemeral path, add only the minimum scoped `tmpfs` rather than relaxing the read-only root filesystem. Then run the accumulated Linux/Windows lifecycle suite and consolidated validation.
