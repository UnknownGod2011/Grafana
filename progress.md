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
- Operator-visible smoke configuration rejects terminal/log-spoofing control and bidi characters before normalized identities are reported.
- Raw PromQL/evidence/sample payloads must not be emitted by the normal release-smoke success report.
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
- Hardened expected-label configuration against C0/C1 controls, Unicode line/paragraph separators, and bidi/isolate controls that could spoof operator-visible release logs while retaining safe printable Unicode values.
- Added a bounded safe-report builder and credential-free regressions so release success output can avoid raw PromQL, MCP evidence content, and sample values.

## Latest run — 2026-09-22 — MCP smoke evidence-log minimization

### Inspected at start
Read `progress.md` completely and inspected `runtime/mcp_smoke.py` plus its production Prometheus-gate regression. Confirmed that the semantic release gate is correctly expected-series-bound, but the success JSON still includes the configured raw PromQL query and a bounded `repr` of the raw MCP evidence content. That is unnecessary for a PASS record and can copy deployment labels or future sensitive telemetry into operator/CI logs.

### Exact changes made
- Added `runtime/mcp_smoke_reporting.py` in commit `2588227962de37d75781902bab0ae23c894ed90f`.
- Added `build_safe_smoke_report(...)`, which emits only bounded server identity, protocol version, explicitly read-only tool names, datasource UID, normalized expected-series labels, and `evidence=verified`.
- The report intentionally has no field for raw PromQL, MCP result content, or sample values.
- Added independent display-safety validation and bounds at the reporting boundary so future callers cannot bypass the existing configuration validation accidentally.
- Added `runtime/tests/test_mcp_smoke_reporting.py` in commit `73bc62a2d9b62b8cd8d08f86884d99e46405d7f3`.
- Added credential-free regressions for release-metadata shape, absence of query/result/content/sample fields, bidi/display-spoof rejection, label-count bounds, and deterministic tool-name deduplication/sorting.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both source/test commits.
- Source inspection confirms the new report builder cannot accept or emit raw evidence/query arguments through its API.
- Tests are credential-free, but this connector environment does not expose an executable checkout, so pytest and Docker acceptance were not executed; no new runtime-green claim is made.
- `mcp_smoke.py` is not yet wired to the new report builder, so its current success output still includes `query` and `result_summary`. This is explicitly tracked rather than overstating completion.

### Decisions
1. Treat successful release-smoke output as an audit/status record, not a telemetry dump.
2. Keep expected identity labels because they prove what series was enforced, but exclude raw query syntax and evidence values because they are unnecessary after semantic verification.
3. Put output sanitization in a dedicated module with a narrow API, making accidental evidence leakage harder than ad-hoc dictionary construction.
4. Avoid GitHub Actions execution because the project prioritizes local validation and historical Actions storage pressure exists.

### Blockers / unknowns
- The safe report builder still needs to replace the ad-hoc success dictionary in `mcp_smoke.py`.
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Wire `build_safe_smoke_report` into `runtime/mcp_smoke.py`, remove raw `query` and `result_summary` from normal PASS output, add an AST release invariant preventing those raw fields from returning, then execute the focused MCP suites and pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke in an executable checkout.
