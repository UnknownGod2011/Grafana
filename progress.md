# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, the exact datasource UID, and a genuine Prometheus vector/matrix sample.
- Prometheus release evidence is bound to expected labels on the same sampled series; unrelated valid series cannot prove the requested StageGuard series.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline
- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest lifecycle/security hardening.
- Historical official Grafana MCP smoke: PASS on `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work
- Hardened lifecycle startup/cleanup, Docker timeouts, teardown verification, loopback publishing, and MCP container privileges/resources.
- Pinned Grafana `13.2.1` and official Grafana MCP `1.4.1`; release smoke verifies read-only tools and exact datasource UID.
- Added bounded semantic Prometheus evidence parsing aligned to official v1.4.1 `QueryPrometheusResult`, rejecting warnings/hints/metadata/scalars/nested lookalikes/non-finite samples.
- Added expected-label binding and bounded `STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS` parsing with deterministic demo defaults.
- Wired expected-series binding into the production MCP release smoke and protected it with a credential-free AST invariant.

## Latest run — 2026-09-22 — production expected-series MCP gate

### Inspected at start
Read `progress.md` completely. Inspected `runtime/mcp_smoke.py`, `runtime/mcp_smoke_gate.py`, and `runtime/tests/test_mcp_smoke_prometheus_gate.py`. Confirmed the adapter existed but production still called the unbound `contains_prometheus_sample(query_result.get("content"))`, so an unrelated valid series could still satisfy the final release call site.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `adb85355feb49422864dbe8417f7b5cfb19eb600`.
- Replaced the direct unbound semantic-parser import with `PrometheusEvidenceError` and `assert_expected_prometheus_sample` from `mcp_smoke_gate`.
- Production smoke now binds `query_result["content"]` to `STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS`; unset configuration uses the adapter's deterministic StageGuard demo defaults.
- Invalid expected-label configuration and mismatched/missing target-series telemetry are translated into `McpError` and fail the smoke closed.
- Successful output reports the normalized label map actually enforced, and PASS text now states that the configured StageGuard series was observed.
- Updated `runtime/tests/test_mcp_smoke_prometheus_gate.py` in commit `45d98521c446f784680b945709e2e40dc2fdace6`.
- Replaced the obsolete invariant requiring direct `contains_prometheus_sample` use with AST checks requiring the bound gate import, query-result plus expected-label configuration binding, and `PrometheusEvidenceError` -> `McpError` fail-closed translation.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both source commits.
- Source inspection confirms the production call site now uses the expected-series adapter and no longer imports/calls the unbound parser directly.
- The regression test is credential-free and statically enforces the new production invariant.
- This connector environment does not expose an executable checkout, so pytest and Docker acceptance were not executed; no new runtime-green claim is made.

### Decisions
1. Enforce expected-series identity at the final production release call site rather than relying on query text alone.
2. Preserve the adapter as the single place that composes bounded configuration parsing with semantic Prometheus evidence validation.
3. Surface normalized enforced labels in smoke output to make acceptance evidence auditable without exposing credentials.
4. Keep release failure behavior uniform by translating semantic/configuration failures into `McpError`.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP suites and the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke in an executable checkout. Capture a sanitized real `query_prometheus` payload and datasource configuration, verify that the live response satisfies the new expected-series gate, and fix any concrete compatibility failure before adding further release-path hardening.
