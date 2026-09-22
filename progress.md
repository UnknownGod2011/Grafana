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
- Prometheus sample semantics are parsed separately from generic MCP-envelope validity; arbitrary numbers or metadata do not count as telemetry.
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
- Hardened MCP evidence acceptance from envelope/content presence to bounded recursive meaningful-payload validation.
- Added a schema-aware datasource identity parser that accepts only exact string-valued `uid` fields and wired the release smoke to it.
- Added a bounded Prometheus evidence parser that recognizes actual instant/range samples while rejecting metadata-only, arbitrary numeric-pair, boolean, non-finite, empty-result, and over-depth lookalikes.

## Latest run — 2026-09-22 — Prometheus sample semantics prepared

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`. The release smoke currently proves datasource identity and generic meaningful query content, but still does not prove that `query_prometheus` returned an actual telemetry sample.

### Exact changes made

- Added `runtime/mcp_prometheus_evidence.py` with bounded, transport-tolerant Prometheus sample detection.
- The parser accepts standard Prometheus instant `value: [timestamp, value]` and range `values: [[timestamp, value], ...]` representations, including JSON serialized inside MCP text and already-structured MCP content.
- It rejects arbitrary numeric pairs not attached to Prometheus sample fields, booleans, non-finite values (`NaN`/`Inf`), metadata-only results, empty results, malformed JSON, and payloads beyond the nesting bound.
- Added `runtime/tests/test_mcp_prometheus_evidence.py` with 10 focused regression cases, including legitimate zero-valued telemetry.
- Parser commit: `9aab3da5a6a781f11e5bc937db4ce1854e24ee08`.
- Regression commit: `691c2f4c5fcf2c7c654e750cb65cb334d031d7a4`.
- Deliberately did not wire this parser into the release smoke yet: the pinned official MCP `1.4.1` query response has not been observed live, and enforcing an assumed representation at the release gate could create a false negative.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both new files.
- Static review confirms sample recognition is field-aware and bounded rather than a generic recursive numeric search.
- This connector environment does not expose an executable repository checkout, so the new tests and prior MCP semantic suites were not executed; no green result is claimed.

### Decisions

1. Keep MCP envelope/content validation, datasource identity, and Prometheus sample semantics as separate layers.
2. A finite numeric zero is valid telemetry; booleans and non-finite numeric strings are not.
3. Do not make the production smoke depend on the new parser until the exact pinned `mcp-grafana:1.4.1` response representation is observed.
4. Preserve historical executable results separately from connector-authored unexecuted changes.

### Blockers / unknowns

- The new Prometheus evidence tests plus datasource-identity and semantic MCP smoke suites need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- The exact pinned `query_prometheus` response representation remains unobserved.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Run the three focused MCP suites, then execute the pinned Grafana `13.2.1` + official MCP `1.4.1` acceptance gate. Compare the real `query_prometheus` payload with `mcp_prometheus_evidence.py`; if it matches the documented Prometheus sample shape, wire `contains_prometheus_sample()` into the release smoke so PASS requires at least one actual telemetry sample, and add the observed payload as a regression fixture.
