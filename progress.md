# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Prometheus evidence traversal is limited to known MCP payload-bearing envelopes; warnings, hints, annotations, metadata, and arbitrary extension fields cannot satisfy the release gate.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Diagnostic traversal is restricted to exact JSON-like built-ins; hostile extension subclasses are opaque.
- Opaque diagnostic formatting must not invoke value, container, key, or metaclass extension hooks.
- Credential redaction covers sensitive mapping keys and common inline Bearer/Basic/URL/assignment forms.
- Diagnostic size limits are hard ceilings and truncation metadata accurately describes discarded evidence when the marker fits.
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
- Added and wired secret-aware MCP diagnostics for JSON-RPC/tool failures, including hostile-object protection, collision preservation, display-control escaping, quoted-assignment redaction, strict output ceilings, exact truncation accounting, and metaclass-hook isolation.
- Restricted semantic evidence traversal to actual MCP payload-bearing envelope fields so nested warning/annotation/extension lookalikes cannot create a false-positive release acceptance.

## Latest run — 2026-09-23 — fail-closed MCP evidence envelope traversal

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/mcp_smoke_gate.py`, `runtime/mcp_prometheus_evidence.py`, and its focused tests. The semantic sample validator correctly required the pinned v1.4.1 direct vector/matrix shape beneath `data`, but its transport traversal recursively visited every dictionary value. Therefore a complete series-shaped `{"data": [...]}` object nested inside a warning, annotation, metadata field, or arbitrary extension could incorrectly satisfy release acceptance even when the real query result was empty.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `c895841f99481474de691df1e6224cd3ba8aa2a6`.
- Added an explicit allowlist of MCP payload-bearing envelope keys: `content`, `text`, `resource`, `structuredContent`, and `result`.
- Direct pinned `QueryPrometheusResult.data` acceptance remains unchanged, but traversal no longer descends into warnings, hints, annotations, metadata, or unknown extension fields.
- Updated module/docstring comments to make this trust boundary explicit.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `e5a576a245068ef2b454384e20b4d7659d556c95`.
- Added positive coverage for text and structured-content MCP envelopes.
- Added fail-closed regressions for a full valid-looking query result nested inside `warnings`, `annotations`, and an arbitrary vendor extension.
- Changed the depth-limit regression to use legitimate `content` envelopes, preserving actual bounded-traversal coverage after arbitrary-key recursion was removed.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Research / attribution
- Rechecked current Grafana MCP ecosystem material while evaluating the boundary. Official/community material continues to describe `query_prometheus` as the Grafana-backed PromQL evidence path and emphasizes service-account/Viewer-style access for read-oriented integrations. No third-party code was copied into StageGuard; the change is a local fail-closed parser policy around StageGuard's already-pinned upstream response contract.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- This run still has no executable repository checkout attached to Python/Docker, so the focused pytest suite and live Docker acceptance could not be executed here.
- No new runtime-green claim is made; historical validation numbers above remain historical.

### Decisions
1. Transport tolerance must not mean arbitrary recursive trust: only documented/known payload-bearing MCP envelope fields may lead to evidence.
2. Warning, hint, annotation, metadata, and vendor-extension material is contextual information, never proof that the requested StageGuard telemetry series exists.
3. Keep direct `QueryPrometheusResult.data` parsing strict and non-recursive so only the pinned vector/matrix model shape can satisfy the gate.
4. Do not trigger noisy GitHub Actions solely to compensate for the unavailable executable checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
