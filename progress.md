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
- Opaque diagnostic type markers are themselves bounded and display-safe; mutable class names cannot become a log-spoofing or output-amplification surface.
- Sanitized mapping-key collisions must preserve each bounded diagnostic value rather than silently overwrite earlier evidence.
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
- Restricted diagnostic traversal to exact JSON-like built-ins and made extension-defined container/scalar subclasses opaque.
- Hardened opaque type markers against mutable hostile class names containing controls, bidi formatting, or oversized text.
- Preserved colliding sanitized mapping keys with deterministic bounded suffixes so one upstream diagnostic field cannot silently erase another.

## Latest run — 2026-09-23 — MCP sanitized-key collision hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py` and `runtime/tests/test_mcp_diagnostics.py`. The diagnostic sanitizer was secret-aware, display-safe, bounded, and protected from extension hooks, but different upstream mapping keys could collapse to the same sanitized display key. In particular, multiple opaque keys of the same extension type all render as `<Type-key>`. Building the sanitized Python dict therefore silently overwrote earlier diagnostic values, making failure evidence order-dependent and potentially hiding useful/redacted context.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `509edb3129ac3ffc570ac6a8063a133457bf94d7`.
- Added `_unique_key()` to preserve collisions using deterministic `#2`, `#3`, ... suffixes bounded by the existing maximum diagnostic item count.
- Collision handling operates only on already-sanitized trusted strings and the sanitized output dict; it does not invoke hooks on untrusted key objects.
- Preserved sensitive-key redaction based on the original exact-string key before the child value is admitted to diagnostics.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `9852503aa1f5d32bb76f555fec1017dc4edcf27e`.
- Added a regression proving two distinct opaque keys of the same type retain both failure values and receive stable display keys.
- Kept hostile-key hook protection by using identity hashing in the test key fixture rather than relying on a constant hash.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Source inspection confirms sanitized-key collisions no longer silently overwrite prior values and collision suffix generation does not touch untrusted objects.
- This connector environment does not expose an executable repository checkout, so pytest/Docker acceptance was not executed and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Preserve every bounded diagnostic field rather than accept last-write-wins behavior after display sanitization.
2. Resolve collisions after `_safe_key()` but retain sensitivity classification from the original key, keeping display identity and secret classification separate.
3. Keep the suffix space bounded by `MAX_DIAGNOSTIC_ITEMS`; the sanitizer already rejects wider diagnostic traversal.
4. Avoid GitHub Actions solely for this connector-authored change; executable local validation remains preferable.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The command-line redactor is separate from upstream-payload sanitization; its existing coverage should be rechecked during executable validation.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
