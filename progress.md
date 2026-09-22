# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- Local cleanup is ownership-aware, timeout-bounded, and verifies all Compose container states.
- Demo services without production authentication are loopback-only.
- Local Grafana MCP is opt-in/on-demand stdio, file-secret-backed, read-only, capability-free, no-new-privileges, and resource/result bounded.
- MCP startup waits for Grafana HTTP readiness; local rehearsals establish a healthy baseline before fault injection.
- MCP release acceptance requires meaningful evidence payload and proof that the exact configured Grafana datasource UID is visible before querying it.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest lifecycle/security hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Hardened local lifecycle startup/cleanup, Docker timeout handling, all-state teardown verification, and loopback-only host publishing.
- Pinned official Grafana MCP to `1.4.1`; disabled write/proxied tools; constrained tool groups, results, CPU/memory/PIDs, privileges, capabilities, root filesystem, transport, and token handling.
- Added Grafana readiness gating with `service_healthy`; readiness uses the official MCP integration convention for pinned Grafana `13.2.1`.
- Added regression contracts for Compose exposure, MCP hardening/readiness, lifecycle behavior, incident rehearsal semantics, and semantic MCP smoke acceptance.
- Corrected runtime docs to healthy-baseline -> explicit fault -> recovery and documented one-off stdio MCP lifecycle.
- Hardened MCP evidence acceptance from envelope/content presence to bounded recursive meaningful-payload validation, including nested metadata and status-flag rejection.
- Hardened MCP datasource discovery so a successful but unrelated `list_datasources` result cannot make the smoke proceed against an unverified configured UID.
- Added a schema-aware datasource identity parser that accepts only exact string-valued `uid` fields and wired the release smoke to it.

## Latest run — 2026-09-22 — field-aware datasource gate wired end-to-end

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and `runtime/mcp_datasource_identity.py`, focusing on the intentionally unresolved integration boundary from the preceding run.

### Finding

The standalone `contains_datasource_uid()` parser correctly enforces field-level identity, but `runtime/mcp_smoke.py::_assert_datasource_present()` was still using the older generic `_value_contains_string()` traversal. Consequently, the release smoke remained vulnerable to confusing an unrelated datasource `name` with the configured UID despite the new parser existing in the repository.

### Exact changes made

- Imported `contains_datasource_uid` from `mcp_datasource_identity` into `runtime/mcp_smoke.py`.
- Replaced `_assert_datasource_present()`'s generic arbitrary-value search with the schema-aware UID matcher.
- Removed the obsolete `_value_contains_string()` implementation from the smoke client so there is no alternate generic identity path left in that file.
- Preserved all existing stdio framing, timeout, bounded evidence, read-only tool-surface, query, and diagnostic behavior unchanged.
- Integration commit: `af7357aace1830e7ed2fbb429a33330f62190d0a`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the complete `runtime/mcp_smoke.py` replacement.
- Static inspection confirms `_assert_datasource_present()` now delegates datasource identity exclusively to `contains_datasource_uid()` after the existing meaningful-content gate.
- The generic `_value_contains_string()` identity helper is no longer present in `runtime/mcp_smoke.py`.
- This connector environment still does not expose an executable repository checkout, so `test_mcp_datasource_identity.py` and `test_mcp_smoke_semantic_acceptance.py` were not executed; no green test result is claimed.

### Decisions

1. Datasource identity now has one implementation path: exact string-valued `uid` fields through the bounded schema-aware parser.
2. Keep meaningful-content validation separate from identity validation: a response must satisfy both before StageGuard queries the datasource.
3. Do not add further speculative MCP payload heuristics until the pinned live implementation is observed.
4. Preserve historical validation claims separately from connector-authored changes that have not been executed.

### Blockers / unknowns

- The datasource-identity and semantic MCP smoke suites still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- The actual pinned `query_prometheus` response representation has not yet been observed, so StageGuard currently proves meaningful evidence rather than a specific requested series/sample.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute `runtime/tests/test_mcp_datasource_identity.py` and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`, then run the pinned Grafana `13.2.1` + official MCP `1.4.1` acceptance gate. Use the observed `query_prometheus` payload to add a narrowly schema-backed assertion that the requested StageGuard telemetry series contains at least one actual sample, rather than adding more generic heuristics.
