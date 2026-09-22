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
- Upstream MCP failure material must pass through secret-aware bounded diagnostics before it is operator-visible.
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
- Hardened expected-label configuration against C0/C1 controls, Unicode line/paragraph separators, and bidi/isolate controls while retaining safe printable Unicode values.
- Added and wired a bounded safe-report builder so release success output has no API for raw PromQL, MCP evidence content, or sample values.
- Added a standalone secret-aware MCP diagnostic sanitizer plus credential-free regression coverage for recursive sensitive fields, inline credentials, auth URLs, bounds, and hostile object repr behavior.
- Wired that sanitizer into production JSON-RPC errors, malformed JSON-RPC results, and MCP tool `isError` content; removed the legacy raw-`repr` diagnostic helper and added a source invariant guarding the boundary.

## Latest run — 2026-09-23 — production MCP failure-diagnostic gate

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`. Confirmed the recorded gap remained: production failure paths still called `_bounded_diagnostic()`, whose raw `repr(value)` could expose secrets echoed by an upstream MCP/Grafana error despite output-length bounding.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `b02913f250c74482f99c15594d27685eb5aa5ada`.
- Imported `safe_diagnostic` from `mcp_diagnostics` and routed JSON-RPC `error`, malformed JSON-RPC `result`, and MCP tool `isError` content through it.
- Removed `_bounded_diagnostic()` and its raw `repr()` implementation, plus the now-unused local diagnostic-size constant.
- Preserved the existing bounded command redaction, protocol/tool/datasource checks, expected-series Prometheus evidence gate, and safe success reporter.
- Added `runtime/tests/test_mcp_smoke_diagnostic_gate.py` in commit `302431fba3a636d55854d4ab6796354d8c0f5789`.
- The source invariant requires the sanitizer import, forbids reintroduction of `_bounded_diagnostic`/raw `repr`, verifies the three untrusted upstream diagnostic sites cross `safe_diagnostic`, and guards stderr from direct upstream payload serialization.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the production wiring and regression-invariant commits.
- Source inspection confirms the three operator-visible upstream MCP diagnostic paths now cross the standalone secret-aware sanitizer.
- This connector environment does not expose an executable repository checkout, so pytest/Docker acceptance was not executed and no new runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Keep sanitization at the point where untrusted upstream material becomes text rather than attempting to redact the final top-level exception string.
2. Retain useful method/tool context outside the sanitizer while sanitizing only the untrusted payload.
3. Remove rather than deprecate the legacy raw-repr helper so future code cannot accidentally reuse the unsafe path.
4. Protect the integration with a cheap credential-free source invariant in addition to the sanitizer's behavioral unit tests.
5. Avoid GitHub Actions execution because local validation is preferred and historical Actions storage pressure exists.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The command-line redactor is separate from upstream-payload sanitization; its existing coverage should be rechecked during executable validation.

## Single best next step
Execute the focused MCP unit/invariant suites in a real checkout, fix any regressions, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` response as a regression fixture without logging credentials, raw PromQL, or sample values.
