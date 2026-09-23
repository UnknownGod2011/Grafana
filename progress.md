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
- Prometheus evidence traversal is limited to known MCP payload-bearing envelopes; warnings, hints, annotations, metadata, and arbitrary extension fields cannot satisfy the release gate.
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

## Latest run — 2026-09-23 — strict Prometheus timestamp evidence shape

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and its focused regression suite. The parser correctly rejected non-finite sample values and hostile scalar subclasses, but it used one permissive numeric helper for both positions of a Prometheus sample pair. That allowed a numeric-looking string in the timestamp position even though Prometheus JSON sample pairs encode timestamps as JSON numbers. A merely similar payload could therefore satisfy the release evidence gate.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `a4a3b29a21acea86d0370727ac032fccb8a5a6fe`.
- Split timestamp validation from sample-value validation: timestamps now require an exact finite built-in `int`/`float`, while sample values retain finite numeric-string support required by Prometheus JSON responses.
- Preserved the exact-built-in trust boundary so bools and extension subclasses cannot masquerade as numeric evidence or execute conversion hooks.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `2e303bda61df365cb4e4bd48d84bde2e9b221e30` with regressions rejecting numeric-looking string timestamps and non-finite numeric timestamps while preserving the existing evidence suite.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- No executable checkout is attached to this runtime, so pytest and Docker acceptance were not executed. No runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Release evidence should match the actual Prometheus wire shape, not merely values that can be coerced into an equivalent number.
2. Timestamp and sample-value positions intentionally have different validation rules because Prometheus JSON encodes them differently.
3. Keep the parser fail-closed and exact-built-in-only rather than adding coercion that broadens the trust boundary.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
