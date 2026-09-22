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
- MCP release acceptance requires meaningful evidence payload, not merely a successful JSON-RPC/tool envelope, metadata, or structurally non-empty but blank nested containers.
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
- Hardened MCP evidence acceptance from envelope/content presence to meaningful recursively inspected payload presence.

## Latest run — 2026-09-22 — recursive MCP evidence validation

### Inspected at start

Read `progress.md` completely before deciding on work. Then inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`, including the prior evidence-payload gate and its fixtures.

### Finding

The previous gate correctly rejected missing content, empty arrays, blank top-level text, and metadata-only content, but treated any non-empty nested dictionary/list as payload. Consequently a response such as `{"type":"resource","resource":{"uri":"   "}}` or `{"resource":{"contents":[]}}` could still make the release smoke green without operational evidence.

### Exact changes made

- Added bounded recursive `_has_meaningful_value()` validation in `runtime/mcp_smoke.py`.
- Strings now qualify only when non-whitespace; dictionaries/lists qualify only if a descendant carries meaningful payload; finite numeric values and booleans remain valid serialized payload values; unsupported/null values do not qualify.
- Added `MAX_PAYLOAD_NESTING_DEPTH = 16` so recursive validation remains bounded even for adversarial nesting within the already frame-bounded MCP response.
- `_has_nonempty_content_payload()` now delegates payload values to this recursive validator while continuing to exclude top-level MCP metadata fields.
- Added regression cases for empty resource objects, whitespace-only nested URIs, empty nested contents, nested blank text, and a positive nested resource containing real telemetry text.
- Implementation commit: `30034d748648b4afef124c0b10f726bae4d8e93d`.
- Test commit: `a359e80184f1d1da75043fdaf749f5e1baf40b73`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation and regression-test updates.
- This connector environment does not expose an executable repository checkout, so these tests were not executed here and are not recorded as green.
- Static inspection confirms existing positive plain-text evidence and nested resource evidence remain accepted while structurally non-empty blank containers fail closed.

### Decisions

1. Release acceptance must recurse through structured MCP content rather than equating container non-emptiness with evidence.
2. Recursive inspection is depth-bounded independently of the existing stdio frame-size bound.
3. Keep serialization tolerance until the pinned MCP `1.4.1` response is observed live; do not prematurely hard-code one upstream result representation.
4. Continue avoiding noisy CI solely to validate connector-authored changes.

### Blockers / unknowns

- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute the semantic MCP contract tests and local Docker acceptance gate. Observe the real pinned MCP `1.4.1` `query_prometheus` payload through Grafana `13.2.1`; if it exposes a stable structured result, strengthen acceptance to verify that the requested StageGuard series actually contains a sample rather than merely a meaningful payload.
