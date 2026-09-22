# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, the exact datasource UID, and a genuine Prometheus vector/matrix sample.
- Prometheus release evidence is bound to expected labels on the same sampled series; unrelated valid series cannot prove the requested StageGuard series.
- Operator-visible smoke configuration rejects terminal/log-spoofing control and bidi characters before normalized identities are reported.
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
- Hardened expected-label configuration against C0/C1 controls, Unicode line/paragraph separators, and bidi/isolate controls that could spoof operator-visible release logs while retaining safe printable Unicode values.

## Latest run — 2026-09-22 — MCP expected-label log-safety hardening

### Inspected at start
Read `progress.md` completely. Inspected `runtime/mcp_smoke.py`, `runtime/mcp_smoke_config.py`, `runtime/mcp_smoke_gate.py`, and `runtime/tests/test_mcp_smoke_config.py`. Confirmed that normalized expected labels are deliberately emitted in release-smoke output and can also appear in fail-closed diagnostics. The configuration parser rejected C0 controls and DEL but still admitted C1 controls plus Unicode line/paragraph separators and bidi/isolate controls, creating an avoidable terminal/log-spoofing surface for operator-visible release evidence.

### Exact changes made
- Updated `runtime/mcp_smoke_config.py` in commit `38b24de80a813fa3961f40cc9f588dc1804fee6a`.
- Added a bounded display-safety predicate aligned with the smoke client's existing terminal-safety policy: rejects C0 controls, C1 controls, DEL, U+2028/U+2029, bidi embedding/override controls U+202A..U+202E, and isolate controls U+2066..U+2069.
- Applied display-safety validation to both expected Prometheus label names and values before they can reach evidence diagnostics or normalized smoke output.
- Kept safe printable Unicode label values supported; the hardening is not an ASCII-only restriction.
- Updated `runtime/tests/test_mcp_smoke_config.py` in commit `64c7a41b9e9f55287dcd491bd068837c9386d416`.
- Added regression coverage for printable Unicode acceptance, U+2028, U+202E, U+2066, C1 U+0085, and an unsafe label name.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both source/test commits.
- Source inspection confirms expected-label identities remain bounded and now share the release smoke's operator-display safety boundary.
- The added tests are credential-free and require no Grafana or Docker runtime.
- This connector environment does not expose an executable checkout, so pytest and Docker acceptance were not executed; no new runtime-green claim is made.

### Decisions
1. Treat release-smoke output as a security boundary because expected labels are operator-visible and may be copied into CI/terminal logs.
2. Reject known visual-control code points rather than all non-ASCII text so legitimate printable Unicode deployment labels remain usable.
3. Keep this validation in the configuration parser so both success output and failure diagnostics receive the same protection.
4. Avoid GitHub Actions execution because the project explicitly prioritizes low-noise/local validation and historical Actions storage pressure exists.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Execute the focused MCP suites and the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke in an executable checkout. Capture a sanitized real `query_prometheus` payload and datasource configuration, verify that the live response satisfies the expected-series gate, and fix any concrete compatibility failure before adding further speculative release-path hardening.
