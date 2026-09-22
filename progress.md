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

## Latest run — 2026-09-22 — configured datasource identity verification

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py`, its semantic acceptance tests, and current upstream `grafana/mcp-grafana` datasource implementation.

### Finding

The smoke required `list_datasources` to return meaningful content but never proved that the exact datasource subsequently passed to `query_prometheus` was actually present. A healthy Grafana containing only an unrelated datasource could therefore pass the discovery stage. Upstream `mcp-grafana` currently defines `list_datasources` specifically to discover datasource UIDs and its result summary includes `uid`, `name`, `type`, `id`, and `isDefault`, so StageGuard can safely make datasource identity part of release acceptance.

### Exact changes made

- Added bounded `_value_contains_string()` traversal that decodes JSON text where possible and compares the configured UID as an exact string rather than accepting substring matches.
- Added `_assert_datasource_present()` which first applies the existing semantic content checks and then requires the exact configured datasource UID to be represented in the MCP result.
- Changed the smoke to verify datasource identity before invoking `query_prometheus`.
- Updated the PASS contract to state that the configured datasource was resolved.
- Added regressions for an unrelated datasource, a UID that only contains the expected UID as a substring, official-style JSON text containing the exact UID, and structured non-text content containing the exact UID.
- Implementation commit: `9dfa5bbedfb3462efdccadc246fc8fc90ab86dfc`.
- Test commit: `5f1737df5ca3c949df87ccd0cb8f317b674a7eaa`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Research / attribution

- Inspected the current official `grafana/mcp-grafana` `tools/datasources.go`. `list_datasources` is documented as the discovery mechanism for available datasource UIDs and returns a `ListDatasourcesResult` whose datasource summaries include the UID. This is the upstream contract used for the new identity assertion.

### Checks / results

- GitHub accepted the implementation and regression-test updates.
- This connector environment does not expose an executable repository checkout, so the tests were not executed here and are not recorded as green.
- Static inspection confirms UID matching is exact after JSON decoding; `stageguard-prometheus-copy` does not satisfy `stageguard-prometheus`.

### Decisions

1. Datasource discovery is now an identity gate, not a generic connectivity check.
2. Keep serialization tolerance: official MCP may return JSON text today, but structured MCP content can be accepted without weakening exact UID matching.
3. Do not attempt to infer the configured datasource from a name or type; StageGuard's query contract is UID-bound.
4. Stop adding generic MCP payload heuristics after this boundary; the next semantic improvement should use the observed pinned `1.4.1` query result format.

### Blockers / unknowns

- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute the semantic MCP contract tests and local Docker acceptance gate. Observe the real pinned MCP `1.4.1` `query_prometheus` payload through Grafana `13.2.1`; if its result representation is stable, replace generic query-result payload acceptance with a query-specific assertion that the requested StageGuard series contains at least one real sample.
