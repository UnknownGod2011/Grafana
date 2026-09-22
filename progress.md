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
- Prometheus release acceptance additionally requires a genuine series-shaped sample under the official query result `data` field; warnings, hints, metadata, unbound sample pairs, and merely non-empty MCP content do not qualify.
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
- Added bounded Prometheus evidence parsing aligned to the pinned official `mcp-grafana v1.4.1` `QueryPrometheusResult` contract and wired it into the production release smoke.
- Hardened Prometheus semantic evidence so a qualifying `value`/`values` sample must belong to a Prometheus series object carrying a string-to-string `metric` label map.

## Latest run — 2026-09-22 — Prometheus series identity hardened

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_prometheus_evidence.py` and its focused regression suite. Found a remaining false-positive path: once traversal entered a legitimate top-level `data` subtree, any nested dictionary containing a numeric `value` or `values` pair could qualify, even when it was arbitrary metadata rather than a Prometheus vector/matrix series.

### Exact changes made

- Updated `runtime/mcp_prometheus_evidence.py` in commit `51e46348e20c4de0b1bda2abbe76b29194a74f37`.
- Added `_is_metric_map()` and now require a qualifying sample to be a sibling of a Prometheus `metric` label map.
- Require metric label keys and values to be strings, matching the Prometheus series-label representation while allowing the valid empty label map.
- Preserved finite-value checks, zero-valued samples, JSON-text/structured MCP transport support, payload-size bound, and nesting-depth bound.
- Updated `runtime/tests/test_mcp_prometheus_evidence.py` in commit `68a0fba71300b66c3703a8cca1aa612bcd497c3b`.
- Added regressions for sample fields without metric identity, nested sample lookalikes under `data`, and non-string metric labels; updated positive fixtures to be series-shaped.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression commits.
- Static review confirms positive instant/range/zero/structured cases now carry metric identity and negative cases exercise the newly closed false-positive path.
- This connector environment does not expose an executable repository checkout, so pytest and Docker acceptance were not executed; no new green runtime claim is made.

### Decisions

1. Treat a numeric pair alone as insufficient evidence, even inside `data`; bind samples to Prometheus series identity.
2. Allow an empty metric map because unlabeled Prometheus series are valid, but reject non-string label values as malformed evidence.
3. Keep bounded recursive traversal inside `data` for transport/model compatibility rather than assuming a single list depth.
4. Do not add more speculative response shapes before capturing the pinned official MCP response live.

### Blockers / unknowns

- Focused MCP suites still require execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke require an executable Docker checkout.
- The live `query_prometheus` payload must be captured and sanitized to confirm the stricter series identity gate matches the pinned upstream representation.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution; historical full-suite failures/errors still need classification.

## Single best next step

Run the focused MCP suites and Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance in an executable checkout. Capture the live `query_prometheus` response as a sanitized fixture and confirm its sample carries the expected `metric` sibling; if it does, retain this stricter gate and then classify remaining full-suite failures before expanding release logic.
