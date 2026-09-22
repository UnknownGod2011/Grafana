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

## Latest run — 2026-09-22 — datasource UID field-confusion regression

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`, concentrating on the configured datasource identity gate added in the preceding run.

### Finding

The new identity gate compares the configured UID as an exact string, which correctly rejects substring collisions, but `_value_contains_string()` searches every value in the decoded datasource response. Therefore an unrelated datasource such as `{\"uid\":\"other-prometheus\",\"name\":\"stageguard-prometheus\"}` can still satisfy the identity gate because its `name` equals the configured UID. This is a semantic field-confusion bug: release acceptance must prove a matching `uid` field, not merely find the UID string somewhere in the payload.

### Exact changes made

- Added `test_datasource_acceptance_does_not_confuse_name_with_uid` to `runtime/tests/test_mcp_smoke_semantic_acceptance.py`.
- The regression constructs an official-style `list_datasources` payload whose datasource name equals the configured UID while its actual UID is different, and requires `_assert_datasource_present()` to reject it.
- Test commit: `d2b2131f4cd66bffa1d084f3ce1941193fad132e`.
- Deliberately did not weaken or rewrite the test to fit the current implementation; this is a red regression contract exposing a real release-smoke false positive.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression-test update.
- Static inspection shows the current `_value_contains_string()` recursively examines all dictionary values, so the new regression is expected to fail until the implementation is made field-aware.
- This connector environment does not expose an executable repository checkout, so the test was not executed and no green result is claimed.

### Decisions

1. Datasource identity must be schema-aware: only a `uid` field may establish datasource identity.
2. Keep bounded traversal and JSON-text decoding because official MCP may serialize datasource results as text, but decoded structures must preserve field semantics.
3. Do not move on to query-result sample validation while the datasource identity gate still has this false-positive path.
4. Keep the new regression red until the implementation is fixed; do not report connector-authored tests as passing without execution.

### Blockers / unknowns

- `_assert_datasource_present()` still needs a field-aware bounded matcher that decodes JSON text but accepts the configured value only when it is associated with a `uid` key.
- The semantic MCP smoke tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Replace the generic `_value_contains_string()` datasource identity check with bounded, JSON-decoding, field-aware UID matching; make the new name-vs-UID regression pass alongside the existing exact-UID and structured-content cases. Then execute the semantic MCP suite and the pinned Grafana `13.2.1` + MCP `1.4.1` acceptance gate before tightening Prometheus sample semantics.
