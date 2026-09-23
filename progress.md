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

## Latest run — 2026-09-23 — metaclass-safe opaque diagnostics

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py`, `runtime/tests/test_mcp_diagnostics.py`, and the runtime/test layout. The opaque-value path avoided object `__repr__`/`__str__`, but `_safe_type_name()` still evaluated `type(value).__name__`. A custom metaclass can override `__getattribute__`, so merely formatting an opaque extension object could execute extension code at the diagnostic trust boundary.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `28a57e600b348ebc0513489f6da8dfe9eefd252a`.
- `_safe_type_name()` now invokes `type.__getattribute__(cls, "__name__")` directly, bypassing custom metaclass `__getattribute__` implementations; lookup failure falls closed to `unknown`.
- Existing type-name display escaping and length bounding remain after the hook-free lookup.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `de6eb89defdda3100ecadf3ff2faa8d375cea031`.
- Added a hostile-metaclass regression whose `__getattribute__` raises if `__name__` is accessed through the extension hook; expected output remains the bounded opaque type marker.
- No cloud resources, credentials, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Attempted to obtain a real executable checkout with `git clone`, but this runtime's container has no outbound DNS/network access to GitHub (`Could not resolve host: github.com`), so pytest/Docker execution was not possible here.
- No new runtime-green claim is made; historical validation numbers above remain historical.

### Decisions
1. Opaque diagnostic rendering is a trust boundary: extension code must not execute through value hooks or through its metaclass.
2. Fail closed to a generic type marker if even built-in type-name lookup cannot be completed safely.
3. Do not trigger noisy GitHub Actions merely to compensate for this runtime's unavailable executable checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
