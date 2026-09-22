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
- Operator-visible smoke configuration rejects terminal/log-spoofing controls and bidi characters.
- Raw PromQL/evidence/sample payloads must not be emitted by the normal release-smoke success report.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before it is operator-visible.
- Untrusted extension/container subclasses are opaque to MCP diagnostics; sanitizer traversal is limited to exact JSON-like built-ins so attacker hooks cannot execute.
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
- Added bounded semantic Prometheus evidence parsing aligned to official v1.4.1 `QueryPrometheusResult`, expected-label binding, and bounded smoke configuration.
- Wired expected-series binding into the production MCP release smoke and protected it with a credential-free AST invariant.
- Hardened expected-label configuration against terminal/log spoofing while retaining safe printable Unicode.
- Added and wired a bounded safe-report builder so release success output has no API for raw PromQL, MCP evidence content, or sample values.
- Added and wired secret-aware MCP diagnostics for JSON-RPC/tool failures, with credential redaction, output bounds, display-control escaping, and hostile-object protection.
- Hardened diagnostics so arbitrary mapping keys and extension-defined container/scalar subclasses cannot execute attacker-controlled stringification, iteration, slicing, length, or mapping hooks.

## Latest run — 2026-09-23 — MCP diagnostic hostile-container hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py` and `runtime/tests/test_mcp_diagnostics.py`. The sanitizer no longer stringified arbitrary mapping keys, but it still used `isinstance()` for dict/list/tuple/string/numeric values. A malicious subclass could therefore enter a trusted traversal branch and execute overridden `items()`, slicing, `len()`, or related hooks. Normal `json.loads` MCP data is composed of exact built-ins, so there is no operational need to traverse extension-defined subclasses.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `4cf7db2df0093b74b567631a92e22fd74318b6f0`.
- Restricted structural traversal and scalar handling to exact built-in JSON-like types. Dict/list/tuple/str/int/float/bool subclasses are now treated as opaque values and represented only by type.
- Restricted sensitive-key inspection and primitive-key stringification to exact built-ins for the same reason.
- Preserved recursive secret redaction, inline credential redaction, display-control escaping, depth/item/string/final-output bounds, and useful plain-JSON error context.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `59441eade4ba0cafab1454dfba3aec056e96d2f1`.
- Added regressions proving hostile dict/list subclasses cannot execute traversal/length/slicing/repr hooks and hostile int/str subclasses cannot execute stringification/repr hooks.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Source inspection confirms traversal is now restricted to exact built-ins produced by normal JSON decoding; unknown/subclass values are reduced to a type marker before final built-in `repr()`.
- This connector environment does not expose an executable repository checkout, so pytest/Docker acceptance was not executed and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Prefer exact built-in traversal over attempting to safely introspect arbitrary Python extension types; MCP JSON-RPC does not require custom container subclasses.
2. Keep opaque type markers useful for triage while refusing to execute extension-defined hooks.
3. Do not trigger GitHub Actions solely for connector-authored hardening because local validation is preferred and historical Actions storage pressure exists.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The command-line redactor is separate from upstream-payload sanitization; its existing coverage should be rechecked during executable validation.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
