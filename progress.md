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

## Latest run — 2026-09-22 — field-aware datasource identity implementation

### Inspected at start

Read `progress.md` completely before deciding on work. Inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_semantic_acceptance.py`, focusing on the red name-vs-UID field-confusion regression from the preceding run.

### Finding

The existing `_value_contains_string()` matcher is not schema-aware: after decoding MCP JSON text it recursively searches every dictionary value. An unrelated datasource can therefore pass the configured-UID gate when its `name` equals the expected UID. Datasource identity must be established only by a `uid` field.

### Exact changes made

- Added `runtime/mcp_datasource_identity.py` with `contains_datasource_uid()`.
- The matcher accepts identity only from an exact string value attached to a `uid` key; plain strings, datasource names, numeric UID lookalikes, and substring collisions do not qualify.
- MCP text content that looks like JSON is decoded before traversal so the matcher remains compatible with official MCP text serialization.
- Traversal is bounded to 16 levels and handles both JSON-text and structured MCP content.
- Added `runtime/tests/test_mcp_datasource_identity.py` covering official-style JSON text, name-vs-UID confusion, plain-string rejection, substring collisions, structured content, non-string UID rejection, nested legitimate UID discovery, and depth bounding.
- Implementation commit: `5e3f2f41f2203e69dd28df1b5d6007683a8d757a`.
- Test commit: `112f6738d04f405dcb06026e37732dd17ef930f1`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation and test files.
- Static inspection confirms the new matcher is field-aware and bounded.
- This connector environment does not expose an executable repository checkout, so the new tests were not executed and no green result is claimed.
- The existing `runtime/mcp_smoke.py` has not yet been wired to call the new matcher; therefore the preceding red integration regression remains intentionally unresolved at the release-smoke boundary.

### Decisions

1. Keep datasource identity parsing isolated and independently testable rather than expanding the already security-sensitive stdio client logic.
2. Only a `uid` field may establish datasource identity; names and arbitrary text are never identity evidence.
3. Preserve bounded JSON decoding because official MCP may serialize datasource results inside text content.
4. Do not claim the field-confusion bug fixed end-to-end until `_assert_datasource_present()` uses the new matcher and the semantic integration regression is executable-green.

### Blockers / unknowns

- `runtime/mcp_smoke.py` still needs to import `contains_datasource_uid` and replace `_value_contains_string()` at the datasource gate; the connector's whole-file write API makes a surgical one-line patch awkward, so this run avoided a risky wholesale rewrite of the stdio client.
- The semantic MCP smoke tests and new matcher tests still need execution in a checkout.
- `docker compose config`, Grafana `13.2.1` health observation, Viewer-token bootstrap, and hardened MCP `1.4.1` smoke still require an executable Docker checkout.
- Accumulated lifecycle/security/MCP tests need Linux and Windows execution.
- Historical full-suite failures/errors still need classification.
- A live unattended Docker rehearsal remains required after the hardening changes.

## Single best next step

Wire `runtime/mcp_smoke.py::_assert_datasource_present()` to `contains_datasource_uid()` and remove the generic `_value_contains_string()` identity path, then run both datasource-identity and semantic MCP suites. After that, execute the pinned Grafana `13.2.1` + MCP `1.4.1` acceptance gate before tightening Prometheus sample semantics.
