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
- MCP release acceptance requires meaningful evidence payload and proof that the exact configured Grafana datasource UID is visible before querying it.
- Prometheus release acceptance additionally requires a genuine sample under the official query result `data` field; warnings, hints, metadata, and merely non-empty MCP content do not qualify.
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
- Added Grafana readiness gating with `service_healthy`; readiness uses the official MCP integration convention for pinned Grafana `13.2.1`.
- Hardened MCP evidence acceptance from envelope/content presence to bounded recursive meaningful-payload validation.
- Added a schema-aware datasource identity parser that accepts only exact string-valued `uid` fields and wired the release smoke to it.
- Added bounded Prometheus evidence parsing aligned to the pinned official `mcp-grafana v1.4.1` `QueryPrometheusResult` contract: genuine telemetry must be under `data`.
- Wired the semantic Prometheus parser into the production MCP release smoke, closing the gap where warnings/hints could satisfy generic non-empty-content validation.

## Latest run — 2026-09-22 — production Prometheus semantic gate wired

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and confirmed the red regression from the prior run described a real production gap: `query_prometheus` ended with `_assert_tool_result(...)` and never invoked `contains_prometheus_sample`, so valid MCP content without telemetry could still reach PASS.

### Exact changes made

- Updated `runtime/mcp_smoke.py` in commit `2232b3c3ea6db3ae488e27e45b6b0fa7863144da`.
- Imported `contains_prometheus_sample` from `mcp_prometheus_evidence`.
- After generic `_assert_tool_result("query_prometheus", query_result)` validation, the release smoke now evaluates `contains_prometheus_sample(query_result.get("content"))` and raises `McpError` when no genuine sample is present.
- Updated PASS wording so a successful smoke explicitly means a genuine Prometheus telemetry sample was observed through Grafana, rather than merely non-empty evidence content.
- Preserved the existing ordering: protocol negotiation -> explicit read-only tool surface -> exact datasource UID discovery -> query execution -> generic MCP validity -> semantic Prometheus sample gate.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the production integration commit.
- Static inspection shows the previously added AST regression's required import and fail-closed semantic branch are now present in `main()`.
- This connector environment does not expose an executable repository checkout, so pytest and Docker acceptance were not executed; no new green runtime claim is made.

### Decisions

1. Keep generic MCP validity as a prerequisite rather than replacing it with semantic parsing; malformed/error responses should fail before telemetry interpretation.
2. Fail closed when the official Prometheus query response contains warnings, hints, or other meaningful content but no qualifying sample.
3. Keep the semantic gate immediately after query-result envelope validation so PASS cannot be emitted without telemetry evidence.
4. Do not broaden accepted Prometheus shapes until justified by the pinned official MCP contract or a captured live fixture.

### Blockers / unknowns

- The focused MCP suites need execution in a checkout, including the previously red AST regression that should now become green.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.

## Single best next step

Run the focused MCP suites and the Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance path in an executable checkout. Capture the live `query_prometheus` response as a sanitized regression fixture, verify the semantic parser accepts the real sample while rejecting warnings/hints-only responses, then classify any failures before adding further release-path logic.
