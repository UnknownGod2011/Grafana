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

## Latest run — 2026-09-22 — pinned Prometheus model.Value shape enforced

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_prometheus_evidence.py`, its focused regression suite, and the exact official `grafana/mcp-grafana` v1.4.1 `tools/prometheus.go` source. Upstream defines `QueryPrometheusResult.Data` as `prometheus/common/model.Value`; StageGuard's probe expects a metric series, so vector/matrix data is a direct JSON list of series objects. The previous parser still recursively searched arbitrary descendants below `data`, leaving a false-positive shape that the pinned upstream contract cannot emit.

### Exact changes made

- Updated `runtime/mcp_prometheus_evidence.py` in commit `08895531a051b03258ba297b7ea86a8f068e2676`.
- Replaced recursive traversal below `data` with direct vector/matrix series validation: `data` must be a list and a qualifying direct child must have a string-to-string `metric` map plus a finite `value` sample or at least one finite `values` sample.
- Kept bounded recursive traversal only for MCP transport/envelope discovery before reaching `QueryPrometheusResult`.
- Explicitly reject Prometheus scalar/string model values as StageGuard release evidence because the smoke probe is intended to prove a named telemetry series, not merely any valid PromQL model value.
- Preserved finite-value checks, zero-valued samples, JSON-text/structured MCP transport support, payload-size bound, and nesting-depth bound.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `a494c334fd1443d3cfe6ff5d578151564c1a9ebb`.
- Added regressions rejecting a nested series-shaped lookalike below `data` and a valid Prometheus scalar sample as insufficient StageGuard series evidence.
- Reviewed current official MCP material. A March 6, 2026 upstream issue documents `query_prometheus` failures for Grafana Prometheus datasources configured with `httpMethod: GET`; StageGuard's live acceptance should explicitly confirm its provisioned datasource method/path while validating v1.4.1.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation and regression commits.
- Source-level review is now aligned to the exact pinned v1.4.1 `QueryPrometheusResult` declaration rather than a speculative response shape.
- This connector environment does not expose an executable repository checkout, so pytest and Docker acceptance were not executed; no new green runtime claim is made.

### Decisions

1. Treat the pinned upstream Go type as the release-gate contract: tolerate MCP transport wrappers, but do not tolerate arbitrary structure inside `QueryPrometheusResult.data`.
2. Require series evidence rather than accepting scalar/string PromQL results because StageGuard's smoke is proving that its telemetry series is observable through Grafana.
3. Continue allowing an empty metric map because unlabeled Prometheus series are valid; require all present labels to be strings.
4. Avoid further speculative parser broadening before live capture of the pinned MCP response.

### Blockers / unknowns

- Focused MCP suites still require execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- The live `query_prometheus` payload must be captured and sanitized to confirm the direct vector/matrix representation through the actual MCP transport.
- The provisioned Prometheus datasource HTTP method should be observed during live acceptance because upstream mcp-grafana has had method-sensitive query behavior.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution; historical full-suite failures/errors still need classification.

## Single best next step

Run the focused MCP suites and Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance in an executable checkout. Capture the sanitized live `query_prometheus` response and datasource configuration, confirm the direct vector/matrix series shape and query transport method, then classify the remaining full-suite failures before expanding release logic.
