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
- Prometheus sample semantics are parsed separately from generic MCP-envelope validity; only samples under the official query result `data` field qualify as telemetry.
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
- Added bounded Prometheus evidence parsing and then aligned it to the pinned official `mcp-grafana v1.4.1` `QueryPrometheusResult` contract.

## Latest run — 2026-09-22 — official query-result contract verified

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py`, `runtime/mcp_prometheus_evidence.py`, and its regression suite. The production smoke still checks meaningful query content rather than semantic samples.

### Research / upstream verification

Inspected the source of official `grafana/mcp-grafana` tag `v1.4.1`, `tools/prometheus.go`. The pinned implementation defines `QueryPrometheusResult` with `Data model.Value` serialized as JSON key `data`, plus optional `hints` and `warnings`; `query_prometheus` returns that wrapper. This removes the prior uncertainty about where genuine Prometheus samples appear in the tool payload and gives StageGuard a stable pinned-version contract to validate against.

### Exact changes made

- Hardened `runtime/mcp_prometheus_evidence.py`: a sample now qualifies only when it is beneath an official query-result `data` field. The parser still tolerates MCP JSON text and structured transport envelopes, remains depth/size bounded, and recognizes instant `value` and range `values` sample pairs.
- This closes a false-positive class where sample-looking numeric pairs inside `hints`, `warnings`, metadata, or arbitrary envelope fields could previously count as telemetry.
- Updated the regression suite to model the pinned v1.4.1 response shape and added explicit rejection tests for sample lookalikes in `hints`, `warnings`, and bare sample objects without the query-result `data` envelope.
- Parser commit: `8e694e70f295b43dea68479209f56168820274fb`.
- Test commit: `fd0c64cc53a38b230a513586f3f1f90d1ca8688d`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the parser and regression updates.
- Static contract review is now grounded in the exact pinned upstream `v1.4.1` source rather than an assumed Prometheus HTTP envelope.
- This connector environment still does not expose an executable repository checkout, so the changed tests were not executed and no green test claim is made.

### Decisions

1. Treat the pinned upstream Go type as the semantic contract: only `QueryPrometheusResult.data` may establish telemetry evidence.
2. Do not accept sample-shaped values from hints/warnings/metadata.
3. Keep transport-envelope traversal separate from sample-field recognition.
4. The prior reason for withholding production integration (unknown v1.4.1 response schema) is now resolved by source verification; live Docker validation is still required for end-to-end serialization/transport behavior.

### Blockers / unknowns

- The Prometheus evidence, datasource-identity, and semantic MCP suites need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Wire `contains_prometheus_sample(query_result["content"])` into the production MCP smoke immediately after `_assert_tool_result("query_prometheus", query_result)`, failing closed when the pinned official response contains no sample; then execute the focused MCP suites and the Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance run to validate actual transport serialization end to end.
