# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, the exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Diagnostic traversal is restricted to exact JSON-like built-ins; hostile extension subclasses are opaque.
- Credential redaction covers sensitive mapping keys and common inline Bearer/Basic/URL/assignment forms.
- Diagnostic size limits are hard ceilings and truncation metadata must accurately describe discarded evidence when the marker fits.
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
- Added bounded semantic Prometheus evidence parsing aligned to official v1.4.1 `QueryPrometheusResult` and expected-label binding.
- Added safe success reporting with no API for raw PromQL, MCP evidence content, or sample values.
- Added and wired secret-aware MCP diagnostics for JSON-RPC/tool failures, including hostile-object protection, collision preservation, display-control escaping, quoted-assignment redaction, and strict output ceilings.

## Latest run — 2026-09-23 — exact truncation accounting

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py` and `runtime/tests/test_mcp_diagnostics.py`. The previous run made diagnostic caps strict, but the truncation marker under-reported information loss: it initialized the omitted count as `len(value) - limit`, even though the marker itself consumes part of the limit and therefore forces additional source characters to be discarded.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `298f4a52b2f7259c7ff9e34afcc55641d5a04e1e`.
- `_truncate()` now resolves the small marker-length/omitted-count fixed point so the reported count equals the actual number of discarded source characters whenever the complete marker fits.
- Added explicit handling for zero/non-positive limits while preserving the hard output ceiling.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `e1cb7641846af74ccf21ad3d1638bd46888048c6`.
- Added regressions proving exact omitted-character accounting and safe behavior across tiny limits.
- No cloud resources, credentials, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and test commits.
- Source inspection confirms the truncation algorithm converges by recalculating marker width until omitted count is stable.
- This connector environment still does not expose an executable checkout, so pytest/Docker acceptance was not run and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Treat truncation metadata as operational evidence: it must not materially understate discarded upstream data.
2. Preserve dependency-free startup behavior and strict byte/character ceilings.
3. Do not trigger noisy CI merely to compensate for the connector environment lacking an executable checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
