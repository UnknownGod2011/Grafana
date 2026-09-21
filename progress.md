# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- Local cleanup is ownership-aware, timeout-bounded, and verifies all Compose container states.
- Demo services without production authentication are loopback-only.
- Local Grafana MCP is opt-in/on-demand stdio, file-secret-backed, read-only, capability-free, no-new-privileges, and resource/result bounded.
- MCP startup waits for Grafana HTTP readiness; local rehearsals establish a healthy baseline before fault injection.
- MCP release acceptance requires non-empty evidence content, not merely a successful JSON-RPC/tool envelope.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest lifecycle/security hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Hardened local lifecycle startup/cleanup, Docker timeout handling, all-state teardown verification, and loopback-only host publishing.
- Pinned official Grafana MCP to `1.4.1`; disabled write/proxied tools; constrained tool groups, results, CPU/memory/PIDs, privileges, capabilities, root filesystem, transport, and token handling.
- Added Grafana readiness gating with `service_healthy`; readiness uses the same `curl -sf http://localhost:3000/api/health` convention as the official MCP integration for pinned Grafana `13.2.1`.
- Added regression contracts for Compose exposure, MCP hardening/readiness, lifecycle behavior, incident rehearsal semantics, and semantic MCP smoke acceptance.
- Corrected runtime docs to healthy-baseline → explicit fault → recovery and documented one-off stdio MCP lifecycle.

## Latest run — 2026-09-22 — MCP semantic acceptance implementation

### Inspected at start

Read `progress.md` completely, then inspected `runtime/mcp_smoke.py` and the previously-added semantic acceptance gate.

### Finding

The prior run correctly introduced a red regression proving that `_assert_tool_result` accepted missing or empty MCP `content`. The implementation still needed to close that false-positive release path.

### Exact changes made

- Hardened `runtime/mcp_smoke.py::_assert_tool_result`.
- A tool response now fails closed when `content` is missing, is not a list, or is an empty list.
- It also rejects content arrays that contain no non-empty MCP content object, avoiding acceptance of structurally empty entries.
- Preserved the existing `isError=true` failure behavior and bounded diagnostics.
- Updated the final PASS text so it accurately claims non-empty Prometheus evidence rather than generic query execution.
- Implementation commit: `74c7a6b06c6ba24b57268cfb7869070b249e5391`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation update.
- The connector environment still does not expose an executable repository checkout, so the semantic regression tests and Docker acceptance suite were not run here. This is not recorded as an executable-green result.
- The implementation is intentionally format-tolerant: it establishes that MCP returned at least one non-empty content object without coupling StageGuard to an upstream Prometheus text serialization that may evolve.

### Decisions

1. Release smoke success must prove evidence presence in addition to JSON-RPC/tool success.
2. Keep semantic validation conservative at the MCP content-envelope boundary until pinned `1.4.1` is observed live; do not invent a stricter upstream payload schema before seeing the real response.
3. Continue avoiding CI churn solely to validate connector-authored changes.

### Blockers / unknowns

- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute the semantic MCP smoke contract tests and local Docker acceptance gate. Verify that pinned MCP `1.4.1` returns a real non-empty `query_prometheus` content payload through Grafana `13.2.1`; then tighten parsing only if the observed upstream payload demonstrates a stable, useful semantic contract beyond non-empty content.
