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
- MCP release acceptance requires meaningful evidence payload, not merely a successful JSON-RPC/tool envelope, metadata, status flags, or structurally non-empty but blank nested containers.
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
- Added Grafana readiness gating with `service_healthy`; readiness uses the same `curl -sf http://localhost:3000/api/health` convention as the official MCP integration for pinned Grafana `13.2.1`.
- Added regression contracts for Compose exposure, MCP hardening/readiness, lifecycle behavior, incident rehearsal semantics, and semantic MCP smoke acceptance.
- Corrected runtime docs to healthy-baseline -> explicit fault -> recovery and documented one-off stdio MCP lifecycle.
- Hardened MCP evidence acceptance from envelope/content presence to bounded recursive meaningful-payload validation, including nested metadata and status-flag rejection.

## Latest run — 2026-09-22 — nested MCP metadata/status hardening

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected the repository tree, `runtime/mcp_smoke.py`, and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`.

### Finding

The recursive MCP evidence validator introduced in the prior run still treated booleans as evidence and traversed metadata dictionaries without key awareness. Therefore payloads such as `{"resource":{"ok":true}}`, `{"resource":{"cached":false}}`, or nested `annotations`/`meta` objects could make the release smoke green despite carrying no telemetry or datasource evidence.

### Exact changes made

- Added one shared `_CONTENT_METADATA_KEYS` set and apply it at every dictionary nesting level, not only at the outer MCP content object.
- Boolean values no longer qualify as operational evidence. This prevents generic status/cache flags from satisfying the smoke.
- Finite numeric values remain valid evidence so legitimate telemetry such as a zero-valued metric is not rejected.
- Preserved bounded recursion and serialization tolerance for actual strings, numeric samples, resources, and structured evidence.
- Expanded semantic regression coverage for nested `annotations`, `meta`, `_meta`, `ok=true`, `cached=false`, and positive numeric-zero telemetry.
- Implementation commit: `f5042266c02dff548f6666bb6ab3d55d88e4f93e`.
- Test commit: `5f096e6dd05822b1d6aa4eb6bd9693c2427ccc19`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression-test updates.
- This connector environment does not expose an executable repository checkout, so the tests were not executed here and are not recorded as green.
- Static inspection confirms numeric zero remains accepted while boolean-only and nested metadata-only structures now fail closed.

### Decisions

1. MCP metadata must remain metadata regardless of nesting depth; moving annotations/meta inside a resource cannot turn it into evidence.
2. Generic booleans are status, not evidence. Numeric zero remains evidence because zero is a legitimate telemetry sample.
3. Keep format tolerance until pinned MCP `1.4.1` is observed live; then prefer a query-specific sample assertion over further generic structural heuristics.
4. Do not add noisy CI solely to validate connector-authored changes.

### Blockers / unknowns

- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute the semantic MCP contract tests and local Docker acceptance gate. Observe the real pinned MCP `1.4.1` `query_prometheus` payload through Grafana `13.2.1`; if its result representation is stable, replace generic payload acceptance for `query_prometheus` with a query-specific assertion that the requested StageGuard series contains at least one real sample.
