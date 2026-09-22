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
- Raw PromQL/evidence/sample payloads must not be emitted by the normal release-smoke success report.
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
- Added a bounded safe-report builder so release success output has no API for raw PromQL, MCP evidence content, or sample values.
- Wired the safe-report builder into the production smoke and added a source-level release invariant preventing legacy raw success fields from returning.

## Latest run — 2026-09-22 — production safe-report integration

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/mcp_smoke_reporting.py`, and the existing production Prometheus-gate regression. Confirmed the prior run's blocker: the semantic evidence gate was correctly series-bound, but normal PASS output still serialized the raw PromQL query and a bounded `repr` of MCP evidence content.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `78c7dee24c6295587b2af800ec73937196ab6185`.
- Production PASS reporting now calls `build_safe_smoke_report(...)` only after datasource and expected-series evidence gates succeed.
- Removed the legacy `query` and `result_summary` fields from normal success JSON. The smoke no longer serializes `query_result` or MCP content on the PASS path.
- Added fail-closed translation from `SmokeReportError` to `McpError`; malformed/unsafe operator-visible metadata cannot bypass the normal smoke failure path.
- Added `runtime/tests/test_mcp_smoke_safe_reporting_gate.py` in commit `9b931e756d304d86e8ed8ecb5b1678be595e5c58`.
- The credential-free AST regression requires the safe-report import/call boundary, constrains the fields passed to it, requires normal `json.dumps` success serialization to use only the sanitized `report`, rejects the legacy `query`/`result_summary` success keys, and verifies reporter errors fail closed through `McpError`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the production integration and regression-test commits.
- Source inspection confirms normal PASS JSON is now produced only from `build_safe_smoke_report` output; the previous raw query/evidence success dictionary is gone.
- The new regression is credential-free, but this connector environment does not expose an executable repository checkout. Pytest and Docker acceptance were therefore not executed, and no new runtime-green claim is made.
- Historical validation numbers above remain historical rather than being silently promoted to current status.

### Decisions
1. Treat successful MCP release-smoke output strictly as an audit/status record, not a telemetry dump.
2. Keep normalized expected-series labels in PASS output because they identify what evidence identity was enforced; omit query syntax and evidence/sample values because they are unnecessary after verification.
3. Fail closed if even nominally safe report metadata violates the reporter's independent bounds/display-safety contract.
4. Protect the production call site with a source-level invariant in addition to unit tests for the report builder itself.
5. Avoid GitHub Actions execution because local validation is preferred and historical Actions storage pressure exists.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- The failure path intentionally retains bounded diagnostics for troubleshooting; a later security review should verify those diagnostics cannot expose secrets supplied by an upstream MCP error.

## Single best next step
Audit and harden MCP failure diagnostics so upstream JSON-RPC/tool errors cannot echo credentials or sensitive headers into logs, add credential-free redaction regressions, then run the focused MCP suites and pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke in an executable checkout.
