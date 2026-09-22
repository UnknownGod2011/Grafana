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
- Prometheus evidence can be bound to expected labels on the same sampled series; unrelated valid series cannot prove the requested StageGuard series.
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

## Latest run — 2026-09-22 — bound Prometheus release-gate adapter

### Inspected at start
Read `progress.md` completely. Inspected `runtime/mcp_smoke.py`, `runtime/tests/test_mcp_smoke_prometheus_gate.py`, the repository tree, and the existing expected-label configuration/evidence modules. Confirmed production `mcp_smoke.py` still calls `contains_prometheus_sample(query_result.get("content"))` without expected-label binding.

### Exact changes made
- Added `runtime/mcp_smoke_gate.py` in commit `1fea6b8347f26d7f232d5d98f754ae7c2e221fd0`.
- Added `assert_expected_prometheus_sample(content, raw_expected_labels)`, which parses the bounded label configuration, translates `SmokeConfigError` to a dedicated `PrometheusEvidenceError`, and calls `contains_prometheus_sample(..., expected_labels=labels)`.
- The gate returns the normalized enforced label map for safe reporting and emits a deterministic fail-closed error when only unrelated telemetry is returned.
- Added `runtime/tests/test_mcp_smoke_gate.py` in commit `be8ae0d389c67e77fab0803e41796fb28db9999a`, covering default identity acceptance, unrelated-series rejection, custom identity enforcement, and configuration-error translation.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression commits.
- Source inspection confirms the new adapter composes the existing bounded config parser with the existing semantic sample parser and keeps identity/sample matching on one series.
- This connector environment does not expose an executable checkout, so pytest and Docker acceptance were not executed; no new runtime-green claim is made.

### Decisions
1. Centralize expected-series release semantics in a small adapter instead of duplicating config/error logic inside the stdio client.
2. Keep invalid operator configuration fail-closed and distinguish it from valid configuration with missing/mismatched telemetry.
3. Preserve deterministic demo defaults while allowing real deployments to bind their own labels explicitly.

### Blockers / unknowns
- `runtime/mcp_smoke.py` still needs the final call-site integration: import the adapter, translate `PrometheusEvidenceError` to `McpError`, and pass `os.getenv("STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS")` with `query_result["content"]`.
- Focused MCP suites require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Wire `assert_expected_prometheus_sample(query_result.get("content"), os.getenv("STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS"))` into `runtime/mcp_smoke.py`, convert `PrometheusEvidenceError` into a clear `McpError`, and extend the AST release invariant to require the bound gate. Then execute the focused MCP suites and the pinned Grafana/MCP Docker acceptance in an executable checkout.
