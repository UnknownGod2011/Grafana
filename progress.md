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
- Assignment-style credentials in diagnostics must be fully redacted even when quoted values contain whitespace or escaped quote characters.
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
- Hardened inline assignment redaction so quoted credentials containing spaces or escaped quote characters are removed as one complete value rather than leaking a tail.

## Latest run — 2026-09-23 — quoted credential diagnostic hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_diagnostics.py`, `runtime/tests/test_mcp_diagnostics.py`, the runtime tree, MCP smoke, semantic evidence gate/parser, and repository Actions state. The prior diagnostic hardening covered recursive keyed secrets, Bearer/Basic auth, URL passwords, unquoted assignments, hostile objects, display controls, and output bounds. A remaining concrete leak existed in assignment-style error strings: the assignment regex stopped at whitespace, so an upstream message such as `password="correct horse battery staple"` redacted only the first token and left the remainder operator-visible. Repository Actions currently reports zero workflow runs, so no noisy CI was triggered.

### Exact changes made
- Updated `runtime/mcp_diagnostics.py` in commit `18b1a0119af87caab7ff58aee5d695f08b22a274`.
- Changed assignment credential matching to consume complete single- or double-quoted values, including escaped characters, before falling back to the existing unquoted token form.
- Preserved the existing sensitive field names and replacement contract: only the field name/separator survive and the credential becomes `<redacted>`.
- Updated `runtime/tests/test_mcp_diagnostics.py` in commit `c16e4f8dca4c89340285639aab5e7e363b4e3ff3`.
- Added regression coverage for double-quoted passwords with spaces, single-quoted secrets with spaces, and a quoted API key containing an escaped quote; the test also proves adjacent non-secret operational context survives.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Source inspection confirms quoted assignment alternatives are matched before the unquoted fallback, preventing whitespace-delimited credential tails from surviving redaction.
- GitHub Actions API currently reports zero workflow runs for this repository; no CI execution was initiated solely for this connector-authored change.
- This connector environment does not expose an executable repository checkout, so pytest/Docker acceptance was not executed and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Fix the concrete secret-leak edge case rather than continue broad speculative sanitizer changes.
2. Keep redaction dependency-free and local to the MCP smoke path so release diagnostics remain available before application services start.
3. Preserve non-secret neighboring error context because operator triage still needs actionable failure information.
4. Do not add or trigger GitHub Actions merely to compensate for the missing executable checkout; the project explicitly prioritizes low-noise local validation.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The command-line redactor is separate from upstream-payload sanitization; its existing coverage should be rechecked during executable validation.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
