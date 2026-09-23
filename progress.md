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
- Untrusted extension/container subclasses are opaque to MCP diagnostics; sanitizer traversal is limited to exact JSON-like built-ins.
- Opaque diagnostic type markers are bounded and display-safe; sanitized mapping-key collisions preserve each bounded value.
- Assignment-style credentials are fully redacted even when quoted values contain whitespace or escaped quotes.
- Diagnostic limits are hard ceilings: truncation metadata itself must fit inside the configured string/final-output limit.
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
- Wired expected-series binding into production release smoke and protected it with a credential-free AST invariant.
- Added and wired a bounded safe-report builder so success output has no API for raw PromQL, MCP evidence content, or sample values.
- Added and wired secret-aware MCP diagnostics for JSON-RPC/tool failures, with credential redaction, display-control escaping, hostile-object protection, collision preservation, and quoted-assignment redaction.
- Restricted diagnostic traversal to exact JSON-like built-ins and hardened opaque type markers.
- Made diagnostic string and final-output caps strict ceilings, including truncation metadata.

## Latest run — 2026-09-23 — strict diagnostic output ceilings

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py` and `runtime/tests/test_mcp_diagnostics.py`. The sanitizer was semantically bounded but its truncation implementation appended a marker *after* taking the configured number of characters. Therefore `MAX_DIAGNOSTIC_STRING_CHARS=512` and `MAX_DIAGNOSTIC_CHARS=2048` were not true upper bounds: hostile payloads could exceed each advertised cap by the marker length. Existing tests tolerated this with `len(rendered) < 2200`, so the contract regression was not detected.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `80d8c85f42e71fc97c3bd358ad5dba64344d31d7`.
- Added one dependency-free `_truncate(value, limit)` primitive that reserves room for its truncation marker and guarantees the returned string never exceeds `limit`.
- Routed both per-string sanitization and final diagnostic rendering through that primitive.
- Routed opaque type-name bounding through the same primitive, removing three subtly different truncation implementations.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `90fa754a7d651dee66b6be762cc4d992034f583b`.
- Tightened the wide-payload assertion to `<= MAX_DIAGNOSTIC_CHARS` and added explicit regressions proving both the per-string and final diagnostic limits include truncation metadata.
- Preserved the existing credential, hostile-object, display-spoofing, collision, Unicode, and operational-context regressions.
- No cloud resources, credentials, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the implementation and regression-test commits.
- Source-level inspection confirms `_truncate` computes marker size before slicing and is now the only truncation primitive in this module.
- The connector environment still does not expose an executable checkout, so pytest/Docker acceptance was not run and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Treat configured diagnostic sizes as security/resource contracts, not approximate targets.
2. Centralize truncation to prevent future call sites from repeating the append-after-cap bug.
3. Keep the change dependency-free because release smoke diagnostics must work before application services start.
4. Avoid noisy CI solely to compensate for the connector's missing executable checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- Command-line redactor coverage should be rechecked during executable validation.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
