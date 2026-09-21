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
- MCP release acceptance requires a non-empty evidence payload, not merely a successful JSON-RPC/tool envelope or metadata-only content object.
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
- Corrected runtime docs to healthy-baseline → explicit fault → recovery and documented one-off stdio MCP lifecycle.

## Latest run — 2026-09-22 — MCP evidence-payload hardening

### Inspected at start

Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/tests/test_mcp_smoke_semantic_acceptance.py`, and the runtime test inventory.

### Finding

The previous semantic gate rejected missing/empty content arrays, but still accepted any non-empty dictionary as evidence. Therefore metadata-only entries such as `{"type":"text","text":""}` or `{"type":"text","annotations":...}` could make release acceptance green without an actual evidence payload.

### Exact changes made

- Added `_has_nonempty_content_payload()` in `runtime/mcp_smoke.py`.
- MCP content now qualifies only when an object carries a non-empty payload beyond metadata fields (`type`, `mimeType`, annotations/meta).
- Blank/whitespace text, metadata-only objects, empty dictionaries, and non-object entries fail closed.
- Kept the acceptance format-tolerant for non-text MCP content carrying a real payload so StageGuard does not prematurely couple to one upstream serialization before the live `1.4.1` observation.
- Expanded `runtime/tests/test_mcp_smoke_semantic_acceptance.py` with metadata-only, blank-text, malformed-entry, and non-text-payload regression cases.
- Implementation commit: `75632513000fa193281dabf0ab3399d9be645aa1`.
- Test commit: `16ae605bfa044a9625676d9714882db12b6c4cf5`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression-test updates.
- This connector environment still does not expose an executable repository checkout, so the tests were not executed here and are not recorded as green.
- Static review confirms the prior accepted text fixture still has a non-empty `text` payload and the added resource fixture has a non-empty `resource` payload.

### Decisions

1. A release smoke must prove payload presence, not just MCP envelope/content-object presence.
2. Metadata does not count as operational evidence.
3. Keep payload detection serialization-tolerant until the pinned upstream `1.4.1` response is observed live; only then tighten to a more specific stable contract if justified.
4. Continue avoiding noisy CI solely to validate connector-authored changes.

### Blockers / unknowns

- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Execute the semantic MCP contract tests and local Docker acceptance gate. Observe the real pinned MCP `1.4.1` `query_prometheus` payload through Grafana `13.2.1`; if it exposes a stable structured result, strengthen acceptance to verify that the requested StageGuard series actually contains a sample rather than merely a non-empty payload.
