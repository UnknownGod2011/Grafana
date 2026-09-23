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
- Prometheus sample timestamps must be finite JSON numbers; numeric-looking timestamp strings are not accepted as genuine Prometheus sample-pair evidence.
- Prometheus evidence traversal is limited to known MCP payload-bearing envelopes; warnings, hints, annotations, metadata, arbitrary extension fields, and `data` extension siblings on standard MCP content blocks cannot satisfy the release gate.
- MCP evidence parsing traverses only exact JSON-like built-ins; extension subclasses are opaque and cannot execute container/scalar hooks during validation.
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
- Hardened semantic evidence parsing so hostile dict/list/string/numeric subclasses and caller label mappings fail closed without extension-hook execution.
- Tightened Prometheus sample-pair semantics so timestamps must be finite JSON numbers rather than merely numeric-looking strings.
- Hardened standard MCP content blocks so extension fields named `data` cannot masquerade as a direct `QueryPrometheusResult`; only their actual payload slots are traversed.

## Latest run — 2026-09-23 — MCP content-block evidence boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and `runtime/tests/test_mcp_prometheus_evidence.py`. The previous traversal hardening correctly ignored warnings, annotations, hints, and arbitrary extension fields, but direct `data` acceptance still occurred on every traversed dictionary. That left a false-positive path where a standard MCP content block such as `{"type":"text", ...}` or `{"type":"resource", ...}` could carry an unrelated extension sibling named `data` with a valid-looking series and satisfy release evidence even though the block's real payload did not contain query evidence.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `ca8f200633861de003672b66d4bc1af420b666d0`.
- Added exact-string recognition for standard MCP content block types (`text`, `image`, `audio`, `resource`, `resource_link`).
- Direct `QueryPrometheusResult.data` acceptance is now disabled on those transport content-block dictionaries; evidence must be reached through the block's legitimate payload-bearing field such as `text` or `resource`.
- Preserved direct result acceptance for actual decoded/query-result objects and structured-content/result envelopes.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `19c123b09bfb4deed6ce4f65bbbc95e0c24ee6c5` with regressions proving `data` extension siblings on text/resource content blocks fail closed while legitimate text/resource/structuredContent payloads remain represented by the existing acceptance tests.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the implementation and regression-test commits.
- This runtime still does not provide an executable repository checkout through the GitHub connector, so pytest and Docker acceptance were not executed. No runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Treat MCP content blocks as transport envelopes, not as `QueryPrometheusResult` objects themselves.
2. Keep direct `data` acceptance for genuine decoded/structured query-result objects so the parser remains transport-tolerant without accepting unrelated content-block extensions.
3. Continue using exact built-in/string checks at this trust boundary; do not broaden parsing through coercion.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
