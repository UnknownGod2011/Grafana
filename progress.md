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
- Added regression contracts for Compose exposure, MCP hardening, readiness, lifecycle behavior, and incident rehearsal semantics.
- Corrected runtime docs to healthy-baseline → explicit fault → recovery and documented one-off stdio MCP lifecycle.

## Latest run — 2026-09-22 — MCP semantic smoke acceptance gate

### Inspected at start

Read `progress.md` completely. Inspected the repository tree, `runtime/mcp_smoke.py`, the MCP smoke contract tests, and current official/upstream MCP material relevant to Prometheus query behavior.

### Finding

`runtime/mcp_smoke.py` currently treats any `tools/call` response with no `isError=true` as success. That means the release smoke can report PASS when `query_prometheus` returns no `content` or an empty content array. For an evidence-plane acceptance test, a successful JSON-RPC envelope is not sufficient proof that Grafana actually returned telemetry. This is a false-positive acceptance path and is more important to close before relying on the pinned `1.4.1` live smoke.

### Exact changes made

- Added `runtime/tests/test_mcp_smoke_semantic_acceptance.py`.
- Added regression cases requiring a successful `query_prometheus` call with missing `content` or `content: []` to fail closed.
- Added a positive case preserving acceptance of a non-empty MCP text-content result containing StageGuard telemetry.
- Regression commit: `0f958bf1e38e993da73953e98134770e507eba09`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression test.
- The new negative tests are intentionally expected to fail against the current `_assert_tool_result` implementation; this is a red acceptance gate identifying a concrete false-positive path, not an executable-green claim.
- This connector environment still does not provide a runnable Docker checkout, so the accumulated Docker/MCP acceptance suite was not executed.

### Decisions

1. A read-only MCP smoke must prove non-empty evidence, not merely transport/tool-call success.
2. Keep the first semantic requirement format-tolerant: reject missing/empty content without prematurely coupling StageGuard to every field of upstream Prometheus result serialization.
3. Do not add CI solely to execute connector-authored changes; preserve the low-noise Actions policy.

### Blockers / unknowns

- `_assert_tool_result` must be hardened to reject missing/empty MCP content, then the new regression must be run.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Harden `_assert_tool_result` so missing or empty MCP `content` fails closed, run the MCP smoke contract tests, then execute the local Docker acceptance gate and verify that pinned MCP `1.4.1` returns actual non-empty StageGuard Prometheus evidence through Grafana.
