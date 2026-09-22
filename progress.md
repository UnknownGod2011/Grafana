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
- Prometheus sample semantics are parsed separately from generic MCP-envelope validity; only samples under the official query result `data` field qualify as telemetry.
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

## Latest run — 2026-09-22 — production semantic-gate regression added

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and confirmed the production release smoke still ends the `query_prometheus` path with `_assert_tool_result(...)`, which validates meaningful MCP content but does not call `contains_prometheus_sample`. The semantic parser exists separately, so the release path can still pass on a non-empty warning/hint payload with no telemetry sample.

### Exact changes made

- Added `runtime/tests/test_mcp_smoke_prometheus_gate.py` in commit `1653af1f8847683471b3e23a96ecb58f765c61d2`.
- The new credential-free AST regression requires the production smoke to import `contains_prometheus_sample` from `mcp_prometheus_evidence`.
- It also requires `main()` to use that parser against `query_result` in a fail-closed branch that raises `McpError` when semantic telemetry is absent.
- The test deliberately avoids Docker, credentials, network access, and brittle source-string matching; it encodes the release invariant structurally.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression-test commit.
- Static inspection confirms the new regression is expected to fail against the current production smoke because the semantic parser is not yet imported/wired there. This is intentional red-test-first coverage of the release defect.
- This connector environment does not expose an executable repository checkout, so pytest was not executed and no green test claim is made.

### Decisions

1. Treat generic MCP payload validity and Prometheus telemetry validity as separate gates.
2. Release acceptance must fail closed when `query_prometheus` returns valid MCP content but no genuine sample under the pinned v1.4.1 `data` contract.
3. Keep the regression credential-free so this invariant is testable without Grafana/Docker.
4. Do not weaken or mark the regression green until the production smoke itself enforces the semantic gate.

### Blockers / unknowns

- `runtime/mcp_smoke.py` still needs the surgical production wiring: import `contains_prometheus_sample`, call it after `_assert_tool_result("query_prometheus", query_result)`, and raise `McpError` if no sample exists.
- The focused MCP suites need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.

## Single best next step

Wire the now-regression-protected semantic gate into `runtime/mcp_smoke.py`: import `contains_prometheus_sample`, fail closed when `contains_prometheus_sample(query_result["content"])` is false, and update the PASS wording to state that a genuine Prometheus sample was observed. Then execute the focused MCP suites and Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance run when an executable checkout is available.
