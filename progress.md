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
- Added a bounded, fail-closed expected-label configuration parser with deterministic StageGuard demo defaults and focused credential-free regressions.

## Latest run — 2026-09-22 — bounded release-smoke label configuration

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_prometheus_gate.py`. Confirmed that the production smoke currently calls `contains_prometheus_sample(query_result.get("content"))` without the identity binding added in the prior run, and that no bounded environment configuration contract yet exists for supplying expected labels.

### Exact changes made

- Added `runtime/mcp_smoke_config.py` in commit `7ba0d97cf80e4b8f5678d1684417afd7e95f04c9`.
- Added `expected_labels(raw)` for `STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS`: unset/blank input uses the deterministic demo identity `production_id=broadcast-alpha` and `uplink=uplink-b`; explicit configuration must be a non-empty JSON object of bounded string labels.
- Bounded the raw JSON to 2048 characters, label count to 16, each label name/value to 128 characters, and rejected control characters. Invalid JSON, arrays/scalars/null, empty objects, non-string values, oversized input, and excessive label counts fail closed with `SmokeConfigError`.
- Added `runtime/tests/test_mcp_smoke_config.py` in commit `0cfbd65b799a93195aa0dfeb96ce6a782a5c8c63`, covering defaults, custom labels, invalid/empty JSON shapes, non-string values, control characters, excessive labels, and oversized payloads.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression commits.
- Connector-level source inspection confirms the new parser is independent of credentials and Docker and does not infer identity from PromQL.
- This connector environment does not expose an executable repository checkout, so pytest and Docker acceptance were not executed; no new green runtime claim is made.

### Decisions

1. Keep expected-series identity explicit rather than attempting to parse arbitrary PromQL selectors.
2. Use deterministic StageGuard demo labels only when configuration is absent; an explicitly supplied empty object is rejected so operators cannot accidentally disable identity binding.
3. Keep configuration parsing in a small independently testable module so the security-sensitive stdio client does not accumulate parsing complexity.
4. Do not weaken the existing semantic parser: expected labels remain a subset match on the same series that supplies the accepted sample.

### Blockers / unknowns

- `runtime/mcp_smoke.py` still needs to import this parser, translate `SmokeConfigError` into `McpError`, and pass the parsed labels as `expected_labels=` to `contains_prometheus_sample`.
- Focused MCP suites still require execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- The live `query_prometheus` payload must be captured and sanitized to confirm the direct vector/matrix representation through the actual MCP transport.
- Production datasource HTTP method should be observed during live acceptance because upstream mcp-grafana has had method-sensitive query behavior.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution; historical full-suite failures/errors still need classification.

## Single best next step

Wire `expected_labels(os.getenv("STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS"))` into `runtime/mcp_smoke.py`, translate configuration failures into a clear fail-closed `McpError`, and call `contains_prometheus_sample(..., expected_labels=labels)`. Extend the smoke-level AST regression to require that binding. Then execute the focused MCP suites and Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance in an executable checkout.
