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
- Prometheus release acceptance requires a genuine vector/matrix series sample under the official query result `data` field; warnings, hints, metadata, scalars, nested lookalikes, unbound sample pairs, and merely non-empty MCP content do not qualify.
- Prometheus evidence can be bound to expected metric labels so an unrelated valid series cannot prove the requested StageGuard series.
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
- Added bounded Prometheus evidence parsing aligned to the pinned official `mcp-grafana v1.4.1` `QueryPrometheusResult` contract and wired it into the production release smoke.
- Hardened Prometheus evidence from generic numeric pairs to series-bound samples, then to the exact direct vector/matrix JSON shape emitted by the pinned upstream `model.Value` contract.
- Added optional expected-label binding so release evidence can prove the requested series rather than merely any valid Prometheus series.

## Latest run — 2026-09-22 — Prometheus evidence identity binding

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_prometheus_evidence.py`, its focused regression suite, and the production `runtime/mcp_smoke.py` call site. The production gate proves that a genuine vector/matrix sample came back, but the semantic parser previously accepted any valid series in the result. That leaves a correctness gap: an unrelated series could satisfy the evidence gate even when the smoke query is intended to prove a specific StageGuard production/uplink series.

### Exact changes made

- Updated `runtime/mcp_prometheus_evidence.py` in commit `e9dd57114a40a5419a8c3dcb1c533f0a9006d0e9`.
- Added optional `expected_labels` binding to `contains_prometheus_sample`; every expected key/value must occur on the same metric series that carries the accepted finite sample. Extra labels remain allowed.
- Invalid expected-label key/value types fail closed instead of silently disabling identity binding.
- Preserved the pinned v1.4.1 direct vector/matrix shape, finite sample checks, zero-valued samples, JSON-text/structured MCP support, payload-size bound, and nesting-depth bound.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `7d718740496239d9c2e8ee6da4620f4296e3f598`.
- Added regressions for successful subset-label binding, rejection of an unrelated valid series, requirement that identity and sample occur on the same series, and invalid expected-label types.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression commits.
- Connector-level source inspection confirms the API is backward-compatible when `expected_labels` is omitted.
- This connector environment does not expose an executable repository checkout, so pytest and Docker acceptance were not executed; no new green runtime claim is made.

### Decisions

1. Series identity is part of evidence correctness, not just sample-shape correctness.
2. Expected labels are an optional subset match so real deployments may retain additional labels such as region, cluster, or instance without weakening the gate.
3. Keep the parser generic and modular; do not hard-code StageGuard production IDs into the evidence library.
4. Do not yet change the production smoke call site until expected-label configuration is introduced cleanly and tested, rather than attempting to infer labels from arbitrary PromQL.

### Blockers / unknowns

- Focused MCP suites still require execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- The live `query_prometheus` payload must be captured and sanitized to confirm the direct vector/matrix representation through the actual MCP transport.
- The provisioned Prometheus datasource HTTP method should be observed during live acceptance because upstream mcp-grafana has had method-sensitive query behavior.
- Production `mcp_smoke.py` still needs an explicit, bounded expected-label configuration before it can enforce the new identity-aware parser path.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution; historical full-suite failures/errors still need classification.

## Single best next step

Add a bounded `STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS` configuration contract to `mcp_smoke.py` (with safe JSON parsing and StageGuard defaults), pass it to `contains_prometheus_sample`, and add smoke-level regressions proving that an unrelated valid series fails release acceptance. Then run the focused MCP suites and Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance in an executable checkout.
